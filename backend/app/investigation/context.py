"""Build bounded investigation context from deterministic reconciliation results.

Candidate records are selected only via strong deterministic identifiers that
the engine already resolved (payment_id, order_id, settlement_id,
settlement_utr, bank_transaction_id, entity_id). No fuzzy or amount-based
lookup happens here, and no data outside the supplied CSV records is consulted.
"""

from datetime import datetime
from typing import Optional

from backend.app.models import BankTransaction, Payment, SettlementRecord
from backend.app.reconciliation.loader import LoadedData
from backend.app.reconciliation.models import (
    ReconciliationResult,
    ReconciliationStatus,
    ResultLevel,
)

from .models import EvidenceItem, EvidenceSource, InvestigationContext

# Exceptions the AI investigator is allowed to look at. DUPLICATE,
# MISSING_SETTLEMENT, pending states and RECONCILED stay purely deterministic.
ELIGIBLE_STATUSES: frozenset[ReconciliationStatus] = frozenset(
    {
        ReconciliationStatus.UNKNOWN,
        ReconciliationStatus.AMOUNT_MISMATCH,
        ReconciliationStatus.MISSING_BANK_CREDIT,
        ReconciliationStatus.UNMATCHED_REFERENCE,
        ReconciliationStatus.REFUND_MISMATCH,
    }
)

# The AI may only classify within the deterministic status vocabulary.
ALLOWED_CLASSIFICATIONS: list[ReconciliationStatus] = sorted(
    ELIGIBLE_STATUSES, key=lambda status: status.value
)

# Exceptions where matched bank evidence must survive the cap.
BANK_PRIORITY_STATUSES: frozenset[ReconciliationStatus] = frozenset(
    {
        ReconciliationStatus.AMOUNT_MISMATCH,
        ReconciliationStatus.MISSING_BANK_CREDIT,
        ReconciliationStatus.UNKNOWN,
        ReconciliationStatus.UNMATCHED_REFERENCE,
    }
)

_SOURCE_DISPLAY_ORDER = (
    EvidenceSource.DETERMINISTIC,
    EvidenceSource.PAYMENT,
    EvidenceSource.SETTLEMENT,
    EvidenceSource.BANK,
)


def is_eligible(result: ReconciliationResult) -> bool:
    """Whether this deterministic result should be investigated by AI."""
    return result.primary_status in ELIGIBLE_STATUSES


def exception_id_for(result: ReconciliationResult) -> str:
    """Stable, deterministic exception identifier for one engine result."""
    evidence = result.evidence
    if result.level == ResultLevel.BATCH:
        key = evidence.settlement_id or evidence.settlement_utr or evidence.bank_transaction_id
    else:
        key = (
            evidence.payment_id
            or evidence.order_id
            or (evidence.settlement_entity_ids[0] if evidence.settlement_entity_ids else None)
            or evidence.settlement_id
        )
    return f"EXC-{result.level.value}-{key or 'UNIDENTIFIED'}"


def _fmt(value: object) -> str:
    """Format an evidence value as a string the AI reads verbatim."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class InvestigationContextBuilder:
    """Builds one bounded `InvestigationContext` per eligible exception.

    Source records are optional. Without them the AI still receives the
    deterministic evidence, and it must report insufficient evidence rather
    than infer records it was not given.
    """

    def __init__(self, data: Optional[LoadedData] = None, max_evidence_items: int = 40):
        self.max_evidence_items = max_evidence_items
        self.payments_by_id: dict[str, Payment] = {}
        self.payments_by_order_id: dict[str, Payment] = {}
        self.settlements_by_entity_id: dict[str, SettlementRecord] = {}
        self.settlements_by_settlement_id: dict[str, list[SettlementRecord]] = {}
        self.bank_by_id: dict[str, BankTransaction] = {}
        self.bank_by_utr: dict[str, list[BankTransaction]] = {}

        if data is not None:
            self._index(data)

    def _index(self, data: LoadedData) -> None:
        for payment in data.payments:
            self.payments_by_id.setdefault(payment.payment_id, payment)
            self.payments_by_order_id.setdefault(payment.order_id, payment)
        for line in data.settlements:
            self.settlements_by_entity_id.setdefault(line.entity_id, line)
            self.settlements_by_settlement_id.setdefault(line.settlement_id, []).append(line)
        for txn in data.bank_transactions:
            self.bank_by_id.setdefault(txn.bank_transaction_id, txn)
            if txn.utr and txn.utr.strip():
                self.bank_by_utr.setdefault(txn.utr.strip(), []).append(txn)

    def build(self, result: ReconciliationResult) -> InvestigationContext:
        """Assemble the bounded context for one deterministic exception."""
        exception_id = exception_id_for(result)
        evidence = result.evidence

        identifiers: dict[str, str] = {}
        for name, value in (
            ("payment_id", evidence.payment_id),
            ("order_id", evidence.order_id),
            ("settlement_id", evidence.settlement_id),
            ("settlement_utr", evidence.settlement_utr),
            ("bank_transaction_id", evidence.bank_transaction_id),
        ):
            if value:
                identifiers[name] = value
        if evidence.settlement_entity_ids:
            identifiers["entity_ids"] = ",".join(evidence.settlement_entity_ids)

        by_source: dict[EvidenceSource, list[tuple]] = {
            EvidenceSource.DETERMINISTIC: self._deterministic_items(result),
            EvidenceSource.PAYMENT: self._payment_items(result),
            EvidenceSource.SETTLEMENT: self._settlement_items(result),
            EvidenceSource.BANK: self._bank_items(result),
        }
        selected = self._select_items(by_source, result)
        dropped = sum(len(items) for items in by_source.values()) - len(selected)

        evidence_items = [
            EvidenceItem(
                evidence_id=f"EV{index:03d}",
                source=source,
                record_id=record_id,
                field=field,
                value=_fmt(value),
                relevance=relevance,
            )
            for index, (source, record_id, field, value, relevance) in enumerate(
                selected, start=1
            )
        ]

        return InvestigationContext(
            exception_id=exception_id,
            deterministic_status=result.primary_status,
            result_level=result.level,
            rule_applied=result.evidence.rule_applied,
            message=result.message,
            identifiers=identifiers,
            evidence=evidence_items,
            allowed_classifications=list(ALLOWED_CLASSIFICATIONS),
            evidence_dropped_count=dropped,
        )

    def _select_items(
        self,
        by_source: dict[EvidenceSource, list[tuple]],
        result: ReconciliationResult,
    ) -> list[tuple]:
        """Keep coverage across sources instead of truncating from the front.

        Bank-related exceptions reserve bank slots before leftover settlement
        lines can consume the cap.
        """
        if result.primary_status in BANK_PRIORITY_STATUSES:
            priority = (
                EvidenceSource.DETERMINISTIC,
                EvidenceSource.PAYMENT,
                EvidenceSource.BANK,
                EvidenceSource.SETTLEMENT,
            )
        else:
            priority = (
                EvidenceSource.DETERMINISTIC,
                EvidenceSource.PAYMENT,
                EvidenceSource.SETTLEMENT,
                EvidenceSource.BANK,
            )

        taken = {source: 0 for source in by_source}
        remaining = self.max_evidence_items
        present = [source for source in priority if by_source[source]]

        for source in present:
            if remaining <= 0:
                break
            taken[source] = 1
            remaining -= 1

        for source in present:
            if remaining <= 0:
                break
            extra = min(len(by_source[source]) - taken[source], remaining)
            taken[source] += extra
            remaining -= extra

        selected: list[tuple] = []
        for source in _SOURCE_DISPLAY_ORDER:
            selected.extend(by_source[source][: taken[source]])
        return selected

    def _deterministic_items(self, result: ReconciliationResult) -> list[tuple]:
        evidence = result.evidence
        record_id = exception_id_for(result)
        items: list[tuple] = [
            (
                EvidenceSource.DETERMINISTIC,
                record_id,
                "primary_status",
                result.primary_status.value,
                "Authoritative deterministic classification of this exception",
            )
        ]
        if result.secondary_findings:
            items.append(
                (
                    EvidenceSource.DETERMINISTIC,
                    record_id,
                    "secondary_findings",
                    ",".join(status.value for status in result.secondary_findings),
                    "Additional deterministic conditions detected on the same record",
                )
            )
        optional_fields = (
            ("rule_applied", evidence.rule_applied, "Deterministic rule that produced the status"),
            ("conflict_reason", evidence.conflict_reason, "Why the deterministic match was ambiguous"),
            ("expected_amount_paise", evidence.expected_amount_paise, "Expected amount in paise, computed deterministically"),
            ("actual_amount_paise", evidence.actual_amount_paise, "Actual amount in paise, computed deterministically"),
            ("variance_paise", evidence.variance_paise, "Deterministic variance in paise; authoritative"),
            ("payment_amount_paise", evidence.payment_amount_paise, "Payment amount in paise"),
            ("settlement_amount_paise", evidence.settlement_amount_paise, "Net settlement amount in paise"),
            ("settlement_credit_paise", evidence.settlement_credit_paise, "Total settlement credit in paise"),
            ("settlement_debit_paise", evidence.settlement_debit_paise, "Total settlement debit in paise"),
            ("bank_amount_paise", evidence.bank_amount_paise, "Bank credit amount in paise"),
            ("payment_refund_amount_paise", evidence.payment_refund_amount_paise, "Refund amount recorded on the payment"),
            ("settlement_refund_amount_paise", evidence.settlement_refund_amount_paise, "Refund amount recorded in settlement"),
        )
        for field, value, relevance in optional_fields:
            if value is not None:
                items.append((EvidenceSource.DETERMINISTIC, record_id, field, value, relevance))
        return items

    def _payment_items(self, result: ReconciliationResult) -> list[tuple]:
        evidence = result.evidence
        payment: Optional[Payment] = None
        if evidence.payment_id:
            payment = self.payments_by_id.get(evidence.payment_id)
        if payment is None and evidence.order_id:
            payment = self.payments_by_order_id.get(evidence.order_id)
        if payment is None:
            return []

        return [
            (EvidenceSource.PAYMENT, payment.payment_id, field, value, relevance)
            for field, value, relevance in (
                ("payment_id", payment.payment_id, "Payment identifier under investigation"),
                ("order_id", payment.order_id, "Order the payment belongs to"),
                ("amount", payment.amount, "Captured payment amount in paise"),
                ("currency", payment.currency, "Payment currency"),
                ("payment_date", payment.payment_date, "When the payment was captured"),
                ("status", payment.status.value, "Payment lifecycle status"),
                ("refund_amount", payment.refund_amount, "Refund recorded on the payment side"),
            )
        ]

    def _settlement_items(self, result: ReconciliationResult) -> list[tuple]:
        evidence = result.evidence
        lines: list[SettlementRecord] = []
        seen: set[str] = set()

        for entity_id in evidence.settlement_entity_ids:
            line = self.settlements_by_entity_id.get(entity_id)
            if line is not None and line.entity_id not in seen:
                seen.add(line.entity_id)
                lines.append(line)

        if result.level == ResultLevel.BATCH and evidence.settlement_id:
            for line in self.settlements_by_settlement_id.get(evidence.settlement_id, []):
                if line.entity_id not in seen:
                    seen.add(line.entity_id)
                    lines.append(line)

        lines.sort(key=lambda line: line.entity_id)

        items: list[tuple] = []
        for line in lines:
            items.extend(
                (EvidenceSource.SETTLEMENT, line.entity_id, field, value, relevance)
                for field, value, relevance in (
                    ("entity_id", line.entity_id, "Settlement line identifier"),
                    ("type", line.type.value, "Whether the line is a payment, refund or adjustment"),
                    ("payment_id", line.payment_id or "", "Payment the settlement line refers to"),
                    ("settlement_id", line.settlement_id, "Settlement batch the line belongs to"),
                    ("settlement_utr", line.settlement_utr, "Bank reference claimed by the settlement line"),
                    ("amount", line.amount, "Gross line amount in paise"),
                    ("debit", line.debit, "Debit component in paise"),
                    ("credit", line.credit, "Credit component in paise"),
                    ("fee", line.fee, "Fee component in paise"),
                    ("tax", line.tax, "Tax component in paise"),
                    ("settled_at", line.settled_at, "When the line was settled"),
                    ("description", line.description, "Settlement line description"),
                )
            )
        return items

    def _bank_items(self, result: ReconciliationResult) -> list[tuple]:
        evidence = result.evidence
        transactions: list[BankTransaction] = []
        if evidence.bank_transaction_id:
            txn = self.bank_by_id.get(evidence.bank_transaction_id)
            if txn is not None:
                transactions.append(txn)
        if not transactions and evidence.settlement_utr:
            transactions.extend(self.bank_by_utr.get(evidence.settlement_utr.strip(), []))

        transactions.sort(key=lambda txn: txn.bank_transaction_id)

        items: list[tuple] = []
        for txn in transactions:
            items.extend(
                (EvidenceSource.BANK, txn.bank_transaction_id, field, value, relevance)
                for field, value, relevance in (
                    ("bank_transaction_id", txn.bank_transaction_id, "Bank transaction identifier"),
                    ("transaction_date", txn.transaction_date, "When the bank posted the transaction"),
                    ("description", txn.description, "Bank narration"),
                    ("amount", txn.amount, "Bank transaction amount in paise"),
                    ("transaction_type", txn.transaction_type.value, "Credit or debit"),
                    ("utr", txn.utr or "", "Bank reference used for matching"),
                )
            )
        return items
