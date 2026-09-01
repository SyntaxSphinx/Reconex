"""Reconciliation engine for Phase 2B."""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional
import time

from backend.app.models import (
    Payment,
    SettlementRecord,
    PaymentStatus,
    SettlementEntityType,
    TransactionType,
)
from .models import (
    ReconciliationStatus,
    ReconciliationEvidence,
    ReconciliationResult,
    ResultLevel,
    SettlementBatch,
    ReconciliationSummary,
    ReconciliationRun,
    STATUS_PRECEDENCE,
)
from .loader import LoadedData


class ReconciliationEngine:
    """Deterministic reconciliation engine."""

    # Synthetic timing assumptions from Phase 1
    SETTLEMENT_WINDOW_DAYS = 3  # Payments should settle within 3 days
    BANK_CREDIT_WINDOW_HOURS = 24  # Bank credits should appear within 24 hours of settlement

    def __init__(self, data: LoadedData):
        self.data = data

        # Build lookup indexes
        self.payments_by_id: dict[str, Payment] = {}
        self.payments_by_order_id: dict[str, list[Payment]] = defaultdict(list)
        self.settlements_by_id: dict[str, list[SettlementRecord]] = defaultdict(list)
        self.settlements_by_payment_id: dict[str, list[SettlementRecord]] = defaultdict(list)
        self.settlements_by_order_id: dict[str, list[SettlementRecord]] = defaultdict(list)
        self.bank_by_utr: dict[str, list[BankTransaction]] = defaultdict(list)

        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes for fast matching."""
        for payment in self.data.payments:
            self.payments_by_id[payment.payment_id] = payment
            self.payments_by_order_id[payment.order_id].append(payment)

        for settlement in self.data.settlements:
            self.settlements_by_id[settlement.settlement_id].append(settlement)
            if settlement.payment_id:
                self.settlements_by_payment_id[settlement.payment_id].append(settlement)
            if settlement.order_id:
                self.settlements_by_order_id[settlement.order_id].append(settlement)

        for bank_txn in self.data.bank_transactions:
            if bank_txn.utr:
                self.bank_by_utr[bank_txn.utr].append(bank_txn)

    def _build_settlement_batches(self) -> dict[str, SettlementBatch]:
        """Group settlement lines by settlement_id into batches."""
        batches: dict[str, SettlementBatch] = {}

        for settlement_id, lines in self.settlements_by_id.items():
            total_credit = sum(line.credit for line in lines)
            total_debit = sum(line.debit for line in lines)
            net_settlement = total_credit - total_debit
            total_fee = sum(line.fee for line in lines)
            total_tax = sum(line.tax for line in lines)

            utrs = [line.settlement_utr for line in lines]
            entity_ids = [line.entity_id for line in lines]

            payment_lines = sum(1 for line in lines if line.type == SettlementEntityType.PAYMENT)
            refund_lines = sum(1 for line in lines if line.type == SettlementEntityType.REFUND)
            adjustment_lines = sum(1 for line in lines if line.type == SettlementEntityType.ADJUSTMENT)

            settled_at = min((line.settled_at for line in lines), default=None)

            batches[settlement_id] = SettlementBatch(
                settlement_id=settlement_id,
                settlement_utrs=utrs,
                entity_ids=entity_ids,
                total_credit_paise=total_credit,
                total_debit_paise=total_debit,
                net_settlement_paise=net_settlement,
                total_fee_paise=total_fee,
                total_tax_paise=total_tax,
                line_count=len(lines),
                payment_lines=payment_lines,
                refund_lines=refund_lines,
                adjustment_lines=adjustment_lines,
                settled_at=settled_at,
            )

        return batches

    def _find_payment_settlement_lines(self, payment: Payment) -> list[SettlementRecord]:
        """Find settlement lines for a payment using deterministic matching."""
        if payment.payment_id in self.settlements_by_payment_id:
            candidates = self.settlements_by_payment_id[payment.payment_id]
            return [s for s in candidates if s.type == SettlementEntityType.PAYMENT]

        if payment.order_id in self.settlements_by_order_id:
            candidates = self.settlements_by_order_id[payment.order_id]
            payments_with_order = self.payments_by_order_id[payment.order_id]
            if len(payments_with_order) == 1:
                return [s for s in candidates if s.type == SettlementEntityType.PAYMENT]

        return []

    def _find_refund_settlement_lines(self, payment: Payment) -> list[SettlementRecord]:
        """Find refund settlement lines for a payment."""
        refund_lines = []

        if payment.payment_id in self.settlements_by_payment_id:
            candidates = self.settlements_by_payment_id[payment.payment_id]
            refund_lines.extend([s for s in candidates if s.type == SettlementEntityType.REFUND])

        if payment.order_id in self.settlements_by_order_id:
            candidates = self.settlements_by_order_id[payment.order_id]
            for s in candidates:
                if s.type == SettlementEntityType.REFUND and s not in refund_lines:
                    refund_lines.append(s)

        return refund_lines

    @staticmethod
    def _majority_utr(batch: SettlementBatch) -> Optional[str]:
        """Return the unique most-common non-empty UTR, or None if there is no majority."""
        counts = Counter(utr for utr in batch.settlement_utrs if utr and utr.strip())
        if not counts:
            return None
        max_count = max(counts.values())
        winners = sorted(utr for utr, count in counts.items() if count == max_count)
        if len(winners) != 1:
            return None
        return winners[0]

    def _check_duplicate(
        self, payment: Payment, settlement_lines: list[SettlementRecord]
    ) -> Optional[ReconciliationResult]:
        """Check for duplicate settlement lines for the same payment."""
        payment_lines = [s for s in settlement_lines if s.type == SettlementEntityType.PAYMENT]

        if len(payment_lines) > 1:
            evidence = ReconciliationEvidence(
                payment_id=payment.payment_id,
                order_id=payment.order_id,
                settlement_entity_ids=[s.entity_id for s in payment_lines],
                settlement_id=payment_lines[0].settlement_id if payment_lines else None,
                rule_applied="DUPLICATE: Multiple payment settlement lines",
                extra={
                    "duplicate_count": len(payment_lines),
                    "entity_ids": [s.entity_id for s in payment_lines],
                },
            )
            return ReconciliationResult(
                primary_status=ReconciliationStatus.DUPLICATE,
                evidence=evidence,
                level=ResultLevel.PAYMENT,
                message=f"Found {len(payment_lines)} duplicate payment settlement lines",
            )

        return None

    def _finalize_payment_result(
        self,
        findings: list[ReconciliationStatus],
        evidence: ReconciliationEvidence,
    ) -> ReconciliationResult:
        """Apply precedence to payment-level findings only."""
        if findings:
            primary_status = min(findings, key=lambda s: STATUS_PRECEDENCE[s])
            secondary = [f for f in findings if f != primary_status]
            if not evidence.rule_applied:
                evidence.rule_applied = f"{primary_status.value}: Primary finding"
            return ReconciliationResult(
                primary_status=primary_status,
                evidence=evidence,
                level=ResultLevel.PAYMENT,
                secondary_findings=secondary,
                message=f"Primary: {primary_status}, Secondary: {secondary}",
            )

        if not evidence.rule_applied:
            evidence.rule_applied = "RECONCILED: Payment and settlement line match"
        return ReconciliationResult(
            primary_status=ReconciliationStatus.RECONCILED,
            evidence=evidence,
            level=ResultLevel.PAYMENT,
            resolution_type="AUTO_RECONCILED",
            message="Payment and settlement line match",
        )

    def _reconcile_payment(
        self, payment: Payment, batches: dict[str, SettlementBatch]
    ) -> ReconciliationResult:
        """Reconcile a single payment against its settlement line(s) only."""
        findings: list[ReconciliationStatus] = []
        evidence = ReconciliationEvidence(
            payment_id=payment.payment_id,
            order_id=payment.order_id,
        )

        if payment.status != PaymentStatus.CAPTURED:
            evidence.rule_applied = f"Payment status: {payment.status}"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.RECONCILED,
                evidence=evidence,
                level=ResultLevel.PAYMENT,
                resolution_type="AUTO_RECONCILED",
                message=f"Payment status is {payment.status}, not captured",
            )

        settlement_lines = self._find_payment_settlement_lines(payment)

        duplicate_result = self._check_duplicate(payment, settlement_lines)
        if duplicate_result:
            return duplicate_result

        if not settlement_lines:
            hours_since_payment = (datetime.utcnow() - payment.payment_date).total_seconds() / 3600
            days_since_payment = hours_since_payment / 24

            evidence.payment_amount_paise = payment.amount
            evidence.payment_date = payment.payment_date
            evidence.extra = {"days_since_payment": days_since_payment}

            if days_since_payment <= self.SETTLEMENT_WINDOW_DAYS:
                evidence.rule_applied = "PENDING_SETTLEMENT: Within settlement window"
                return ReconciliationResult(
                    primary_status=ReconciliationStatus.PENDING_SETTLEMENT,
                    evidence=evidence,
                    level=ResultLevel.PAYMENT,
                    message=(
                        f"Payment is {days_since_payment:.1f} days old, "
                        f"within {self.SETTLEMENT_WINDOW_DAYS}-day window"
                    ),
                )

            evidence.rule_applied = "MISSING_SETTLEMENT: Beyond settlement window"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.MISSING_SETTLEMENT,
                evidence=evidence,
                level=ResultLevel.PAYMENT,
                message=(
                    f"Payment is {days_since_payment:.1f} days old, "
                    f"beyond {self.SETTLEMENT_WINDOW_DAYS}-day window"
                ),
            )

        settlement_line = next(
            (s for s in settlement_lines if s.type == SettlementEntityType.PAYMENT),
            None,
        )
        if not settlement_line:
            evidence.rule_applied = "UNKNOWN: No payment-type settlement line found"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.UNKNOWN,
                evidence=evidence,
                level=ResultLevel.PAYMENT,
                message="Settlement lines exist but none are payment-type",
            )

        evidence.settlement_id = settlement_line.settlement_id
        evidence.settlement_entity_ids = [settlement_line.entity_id]
        evidence.settlement_amount_paise = settlement_line.amount
        evidence.payment_amount_paise = payment.amount
        evidence.settlement_utr = settlement_line.settlement_utr or None
        evidence.settlement_date = settlement_line.settled_at

        if settlement_line.amount != payment.amount:
            variance = settlement_line.amount - payment.amount
            evidence.expected_amount_paise = payment.amount
            evidence.actual_amount_paise = settlement_line.amount
            evidence.variance_paise = variance
            evidence.abs_variance_paise = abs(variance)
            findings.append(ReconciliationStatus.AMOUNT_MISMATCH)

        refund_lines = self._find_refund_settlement_lines(payment)
        settlement_refund_total = sum(abs(line.debit) for line in refund_lines)
        evidence.payment_refund_amount_paise = payment.refund_amount
        evidence.settlement_refund_amount_paise = settlement_refund_total

        if payment.refund_amount != settlement_refund_total:
            if evidence.variance_paise is None:
                variance = settlement_refund_total - payment.refund_amount
                evidence.expected_amount_paise = payment.refund_amount
                evidence.actual_amount_paise = settlement_refund_total
                evidence.variance_paise = variance
                evidence.abs_variance_paise = abs(variance)

            if refund_lines:
                evidence.settlement_entity_ids.extend([line.entity_id for line in refund_lines])

            findings.append(ReconciliationStatus.REFUND_MISMATCH)

        batch = batches.get(settlement_line.settlement_id)
        if not batch:
            evidence.rule_applied = "UNKNOWN: Settlement batch not found"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.UNKNOWN,
                evidence=evidence,
                level=ResultLevel.PAYMENT,
                message="Settlement batch not found in batch index",
            )

        line_utr = (settlement_line.settlement_utr or "").strip()
        if not line_utr:
            findings.append(ReconciliationStatus.UNMATCHED_REFERENCE)
            if not evidence.rule_applied:
                evidence.rule_applied = "UNMATCHED_REFERENCE: Settlement line has no valid UTR"
        elif batch.has_conflicting_utrs():
            majority = self._majority_utr(batch)
            if majority is None or line_utr != majority:
                findings.append(ReconciliationStatus.UNMATCHED_REFERENCE)
                if not evidence.rule_applied:
                    evidence.rule_applied = (
                        "UNMATCHED_REFERENCE: Settlement line UTR does not match batch majority"
                    )
                    evidence.conflict_reason = (
                        f"Line UTR {line_utr} is not the majority UTR in batch {batch.settlement_id}"
                    )

        return self._finalize_payment_result(findings, evidence)

    def _reconcile_batch(self, batch: SettlementBatch) -> ReconciliationResult:
        """Reconcile one settlement batch against its bank credit."""
        evidence = ReconciliationEvidence(
            settlement_id=batch.settlement_id,
            settlement_entity_ids=list(batch.entity_ids),
            settlement_credit_paise=batch.total_credit_paise,
            settlement_debit_paise=batch.total_debit_paise,
            settlement_amount_paise=batch.net_settlement_paise,
            expected_amount_paise=batch.net_settlement_paise,
            settlement_date=batch.settled_at,
        )

        if batch.has_conflicting_utrs():
            distinct_utrs = sorted({utr for utr in batch.settlement_utrs if utr and utr.strip()})
            evidence.rule_applied = "UNKNOWN: Conflicting UTRs in settlement batch"
            evidence.conflict_reason = f"Multiple UTRs in batch: {distinct_utrs}"
            evidence.extra = {"settlement_utrs": distinct_utrs}
            return ReconciliationResult(
                primary_status=ReconciliationStatus.UNKNOWN,
                evidence=evidence,
                level=ResultLevel.BATCH,
                message="Settlement batch has conflicting UTRs",
            )

        utr = batch.primary_utr()
        if not utr:
            evidence.rule_applied = "UNMATCHED_REFERENCE: No valid UTR"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.UNMATCHED_REFERENCE,
                evidence=evidence,
                level=ResultLevel.BATCH,
                message="Settlement batch has no valid UTR",
            )

        evidence.settlement_utr = utr
        bank_transactions = self.bank_by_utr.get(utr, [])

        if not bank_transactions:
            if batch.settled_at:
                hours_since_settlement = (
                    datetime.utcnow() - batch.settled_at
                ).total_seconds() / 3600
                evidence.extra = {"hours_since_settlement": hours_since_settlement}
                if hours_since_settlement <= self.BANK_CREDIT_WINDOW_HOURS:
                    evidence.rule_applied = "PENDING_BANK_CREDIT: Within bank credit window"
                    return ReconciliationResult(
                        primary_status=ReconciliationStatus.PENDING_BANK_CREDIT,
                        evidence=evidence,
                        level=ResultLevel.BATCH,
                        message=(
                            f"Settlement is {hours_since_settlement:.1f} hours old, "
                            f"within {self.BANK_CREDIT_WINDOW_HOURS}-hour window"
                        ),
                    )

            evidence.rule_applied = "MISSING_BANK_CREDIT: Beyond bank credit window"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.MISSING_BANK_CREDIT,
                evidence=evidence,
                level=ResultLevel.BATCH,
                message="No bank credit found for settlement UTR",
            )

        if len(bank_transactions) > 1:
            bank_ids = [b.bank_transaction_id for b in bank_transactions]
            evidence.rule_applied = "UNKNOWN: Multiple bank transactions with same UTR"
            evidence.conflict_reason = f"Found {len(bank_transactions)} bank transactions with UTR {utr}"
            evidence.extra = {"bank_transaction_ids": bank_ids}
            return ReconciliationResult(
                primary_status=ReconciliationStatus.UNKNOWN,
                evidence=evidence,
                level=ResultLevel.BATCH,
                message=f"Multiple bank transactions found with UTR {utr}",
            )

        bank_txn = bank_transactions[0]
        evidence.bank_transaction_id = bank_txn.bank_transaction_id
        evidence.bank_amount_paise = bank_txn.amount
        evidence.actual_amount_paise = bank_txn.amount
        evidence.bank_date = bank_txn.transaction_date

        if bank_txn.transaction_type != TransactionType.CREDIT:
            evidence.rule_applied = "UNKNOWN: Bank transaction is not a credit"
            evidence.conflict_reason = f"Expected credit, got {bank_txn.transaction_type}"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.UNKNOWN,
                evidence=evidence,
                level=ResultLevel.BATCH,
                message=(
                    f"Bank transaction {bank_txn.bank_transaction_id} is "
                    f"{bank_txn.transaction_type}, expected credit"
                ),
            )

        if bank_txn.amount != batch.net_settlement_paise:
            variance = bank_txn.amount - batch.net_settlement_paise
            evidence.variance_paise = variance
            evidence.abs_variance_paise = abs(variance)
            evidence.rule_applied = "AMOUNT_MISMATCH: Settlement batch net vs bank credit"
            return ReconciliationResult(
                primary_status=ReconciliationStatus.AMOUNT_MISMATCH,
                evidence=evidence,
                level=ResultLevel.BATCH,
                message=(
                    f"Batch net {batch.net_settlement_paise} paise != "
                    f"bank credit {bank_txn.amount} paise"
                ),
            )

        evidence.variance_paise = 0
        evidence.abs_variance_paise = 0
        evidence.rule_applied = "RECONCILED: Settlement batch net matches bank credit"
        return ReconciliationResult(
            primary_status=ReconciliationStatus.RECONCILED,
            evidence=evidence,
            level=ResultLevel.BATCH,
            resolution_type="AUTO_RECONCILED",
            message="Settlement batch net matches bank credit",
        )

    @staticmethod
    def _status_bucket_counts(
        results: list[ReconciliationResult],
    ) -> tuple[dict[str, int], int, int, int]:
        status_counts: dict[str, int] = defaultdict(int)
        reconciled_count = 0
        pending_count = 0
        exception_count = 0
        pending_statuses = {
            ReconciliationStatus.PENDING_SETTLEMENT,
            ReconciliationStatus.PENDING_BANK_CREDIT,
        }

        for result in results:
            status_counts[result.primary_status.value] += 1
            if result.primary_status == ReconciliationStatus.RECONCILED:
                reconciled_count += 1
            elif result.primary_status in pending_statuses:
                pending_count += 1
            else:
                exception_count += 1

        return dict(status_counts), reconciled_count, pending_count, exception_count

    def reconcile(self) -> ReconciliationRun:
        """Run payment-level and batch-level reconciliation separately."""
        start_time = time.time()

        batches = self._build_settlement_batches()

        payment_results: list[ReconciliationResult] = []
        for payment in self.data.payments:
            payment_results.append(self._reconcile_payment(payment, batches))

        batch_results: list[ReconciliationResult] = []
        for settlement_id in sorted(batches):
            batch_results.append(self._reconcile_batch(batches[settlement_id]))

        payment_status_counts, reconciled_count, pending_count, exception_count = (
            self._status_bucket_counts(payment_results)
        )
        batch_status_counts, batch_reconciled, batch_pending, batch_exception = (
            self._status_bucket_counts(batch_results)
        )

        total_variance = 0
        for result in payment_results:
            if result.evidence.abs_variance_paise:
                total_variance += result.evidence.abs_variance_paise
        for result in batch_results:
            if result.evidence.abs_variance_paise:
                total_variance += result.evidence.abs_variance_paise

        duration = time.time() - start_time

        summary = ReconciliationSummary(
            payments_processed=len(self.data.payments),
            settlement_lines_processed=len(self.data.settlements),
            settlement_batches_processed=len(batches),
            bank_transactions_processed=len(self.data.bank_transactions),
            reconciled_count=reconciled_count,
            pending_count=pending_count,
            exception_count=exception_count,
            status_counts=payment_status_counts,
            total_expected_settlement_paise=sum(
                p.amount for p in self.data.payments if p.status == PaymentStatus.CAPTURED
            ),
            total_matched_bank_paise=sum(
                b.amount
                for b in self.data.bank_transactions
                if b.transaction_type == TransactionType.CREDIT
            ),
            total_absolute_variance_paise=total_variance,
            batch_status_counts=batch_status_counts,
            batch_reconciled_count=batch_reconciled,
            batch_pending_count=batch_pending,
            batch_exception_count=batch_exception,
            processing_duration_seconds=duration,
        )

        return ReconciliationRun(
            payment_results=payment_results,
            batch_results=batch_results,
            summary=summary,
        )
