"""Anomaly injection into clean synthetic data."""

import random
from typing import Dict, Iterable, List, Sequence, TypeVar

from backend.app.models import (
    Payment,
    SettlementRecord,
    SettlementEntityType,
    BankTransaction,
)
from backend.app.models.anomaly import AnomalyRecord, AnomalyType
from backend.app.generator.config import (
    GeneratorConfig,
    AnomalyConfig,
    cap_anomaly_counts,
    counts_from_rates,
)

T = TypeVar("T")


def unique_in_order(items: Iterable[T]) -> List[T]:
    """Return unique items preserving first-seen order.

    Membership uses a set; iteration never depends on set order.
    """
    seen: set[T] = set()
    ordered: List[T] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


class AnomalyInjector:
    """Injects controlled anomalies into clean data and tracks ground truth."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.rng = random.Random(config.seed + 1000)
        self.ground_truth: List[AnomalyRecord] = []
        self.anomaly_counter = 0
        self.counts: AnomalyConfig = AnomalyConfig()

    def _generate_anomaly_id(self) -> str:
        """Generate unique anomaly ID."""
        self.anomaly_counter += 1
        return f"anom_{self.anomaly_counter:06d}"

    def _resolve_counts(
        self,
        payments: Sequence[Payment],
        settlements: Sequence[SettlementRecord],
        bank_transactions: Sequence[BankTransaction],
    ) -> AnomalyConfig:
        if self.config.anomaly_config is not None:
            planned = self.config.anomaly_config
        else:
            planned = counts_from_rates(self.config.num_records, self.config.anomaly_rates)

        payment_settlement_count = sum(
            1
            for s in settlements
            if s.type == SettlementEntityType.PAYMENT and s.payment_id
        )
        return cap_anomaly_counts(
            planned,
            payment_settlement_count=payment_settlement_count,
            bank_count=len(bank_transactions),
        )

    def _bank_by_utr(
        self, bank_transactions: Sequence[BankTransaction]
    ) -> Dict[str, BankTransaction]:
        mapping: Dict[str, BankTransaction] = {}
        for bank_txn in bank_transactions:
            if bank_txn.utr and bank_txn.utr not in mapping:
                mapping[bank_txn.utr] = bank_txn
        return mapping

    def inject_missing_settlement(
        self,
        payments: List[Payment],
        settlements: List[SettlementRecord],
        bank_transactions: List[BankTransaction],
    ) -> None:
        """Remove settlement records for selected captured payments."""
        payment_to_settlement: Dict[str, SettlementRecord] = {}
        for settlement in settlements:
            if settlement.payment_id and settlement.type == SettlementEntityType.PAYMENT:
                if settlement.payment_id not in payment_to_settlement:
                    payment_to_settlement[settlement.payment_id] = settlement

        captured_payments = [p for p in payments if p.payment_id in payment_to_settlement]
        num_to_inject = min(self.counts.missing_settlement, len(captured_payments))
        if num_to_inject == 0:
            return

        selected_payments = self.rng.sample(captured_payments, num_to_inject)
        bank_by_utr = self._bank_by_utr(bank_transactions)

        for payment in selected_payments:
            settlement = payment_to_settlement[payment.payment_id]
            settlements.remove(settlement)
            related_bank = bank_by_utr.get(settlement.settlement_utr)

            self.ground_truth.append(
                AnomalyRecord(
                    anomaly_id=self._generate_anomaly_id(),
                    anomaly_type=AnomalyType.MISSING_SETTLEMENT,
                    affected_entity_id=payment.payment_id,
                    affected_entity_type="payment",
                    expected_state="Settlement record should exist",
                    actual_state="Settlement record missing; related bank credit is unchanged",
                    related_ids={
                        "payment_id": payment.payment_id,
                        "order_id": payment.order_id,
                        "removed_entity_id": settlement.entity_id,
                        "settlement_id": settlement.settlement_id,
                        "settlement_utr": settlement.settlement_utr,
                        "related_bank_transaction_id": (
                            related_bank.bank_transaction_id if related_bank else None
                        ),
                        "removed_credit_paise": settlement.credit,
                    },
                    description=(
                        f"Payment {payment.payment_id} captured but settlement "
                        f"{settlement.entity_id} removed; bank credit "
                        f"{related_bank.bank_transaction_id if related_bank else 'n/a'} still exists"
                    ),
                )
            )

    def inject_missing_bank_credit(
        self,
        settlements: List[SettlementRecord],
        bank_transactions: List[BankTransaction],
    ) -> None:
        """Remove bank transactions for selected settlement batches."""
        bank_by_utr = self._bank_by_utr(bank_transactions)
        eligible_utrs = unique_in_order(
            s.settlement_utr for s in settlements if s.settlement_utr in bank_by_utr
        )
        num_to_inject = min(self.counts.missing_bank_credit, len(eligible_utrs))
        if num_to_inject == 0:
            return

        selected_utrs = self.rng.sample(eligible_utrs, num_to_inject)

        for utr in selected_utrs:
            bank_txn = bank_by_utr[utr]
            bank_transactions.remove(bank_txn)
            affected_settlements = [s for s in settlements if s.settlement_utr == utr]
            settlement_ids = unique_in_order(s.settlement_id for s in affected_settlements)

            self.ground_truth.append(
                AnomalyRecord(
                    anomaly_id=self._generate_anomaly_id(),
                    anomaly_type=AnomalyType.MISSING_BANK_CREDIT,
                    affected_entity_id=bank_txn.bank_transaction_id,
                    affected_entity_type="bank_transaction",
                    expected_state="Bank credit should exist",
                    actual_state="Bank credit missing",
                    related_ids={
                        "removed_bank_transaction_id": bank_txn.bank_transaction_id,
                        "settlement_utr": utr,
                        "settlement_ids": settlement_ids,
                        "affected_entity_ids": [s.entity_id for s in affected_settlements],
                    },
                    description=f"Settlement batch UTR {utr} complete but bank credit removed",
                )
            )

    def inject_amount_mismatch(
        self,
        bank_transactions: List[BankTransaction],
    ) -> None:
        """Modify bank transaction amounts to create mismatches."""
        num_to_inject = min(self.counts.amount_mismatch, len(bank_transactions))
        if num_to_inject == 0:
            return

        selected_txns = self.rng.sample(bank_transactions, num_to_inject)

        for bank_txn in selected_txns:
            original_amount = bank_txn.amount
            percent = self.rng.randint(1, 10)
            sign = self.rng.choice((-1, 1))
            variance = original_amount * percent // 100 * sign
            if variance == 0:
                variance = sign
            new_amount = original_amount + variance
            if new_amount <= 0:
                variance = abs(variance)
                new_amount = original_amount + variance

            bank_txn.amount = new_amount

            self.ground_truth.append(
                AnomalyRecord(
                    anomaly_id=self._generate_anomaly_id(),
                    anomaly_type=AnomalyType.AMOUNT_MISMATCH,
                    affected_entity_id=bank_txn.bank_transaction_id,
                    affected_entity_type="bank_transaction",
                    expected_state=f"Amount should be {original_amount} paise",
                    actual_state=f"Amount is {new_amount} paise",
                    variance=variance,
                    related_ids={
                        "bank_transaction_id": bank_txn.bank_transaction_id,
                        "settlement_utr": bank_txn.utr,
                        "original_amount": original_amount,
                        "modified_amount": new_amount,
                        "percent": percent,
                    },
                    description=(
                        f"Bank transaction amount modified by {variance} paise ({percent}%)"
                    ),
                )
            )

    def inject_duplicate(
        self,
        settlements: List[SettlementRecord],
    ) -> None:
        """Duplicate settlement records to create duplicate anomalies."""
        num_to_inject = min(self.counts.duplicate, len(settlements))
        if num_to_inject == 0:
            return

        selected_settlements = self.rng.sample(settlements, num_to_inject)

        for settlement in selected_settlements:
            duplicate = settlement.model_copy(deep=True)
            duplicate.entity_id = f"{settlement.entity_id}_DUP"
            settlements.append(duplicate)

            self.ground_truth.append(
                AnomalyRecord(
                    anomaly_id=self._generate_anomaly_id(),
                    anomaly_type=AnomalyType.DUPLICATE,
                    affected_entity_id=settlement.entity_id,
                    affected_entity_type="settlement",
                    expected_state="Single settlement record",
                    actual_state="Duplicate settlement record exists",
                    related_ids={
                        "original_entity_id": settlement.entity_id,
                        "duplicate_entity_id": duplicate.entity_id,
                        "payment_id": settlement.payment_id,
                        "order_id": settlement.order_id,
                        "settlement_id": settlement.settlement_id,
                    },
                    description=(
                        f"Settlement {settlement.entity_id} duplicated as {duplicate.entity_id}"
                    ),
                )
            )

    def inject_refund_mismatch(
        self,
        payments: List[Payment],
        settlements: List[SettlementRecord],
    ) -> None:
        """Create a payment-side refund and a disagreeing settlement refund row."""
        payment_by_id = {p.payment_id: p for p in payments}
        seen_payment_ids: set[str] = set()
        eligible: List[SettlementRecord] = []
        for settlement in settlements:
            if settlement.type != SettlementEntityType.PAYMENT or not settlement.payment_id:
                continue
            if settlement.entity_id.endswith("_DUP"):
                continue
            if settlement.payment_id in seen_payment_ids:
                continue
            payment = payment_by_id.get(settlement.payment_id)
            if payment is None or payment.refund_amount != 0:
                continue
            seen_payment_ids.add(settlement.payment_id)
            eligible.append(settlement)

        num_to_inject = min(self.counts.refund_mismatch, len(eligible))
        if num_to_inject == 0:
            return

        selected_settlements = self.rng.sample(eligible, num_to_inject)

        for settlement in selected_settlements:
            payment = payment_by_id[settlement.payment_id]
            expected_refund = payment.amount * self.rng.randint(20, 50) // 100
            if expected_refund <= 0:
                expected_refund = 1

            delta_percent = self.rng.randint(10, 30)
            sign = self.rng.choice((-1, 1))
            delta = expected_refund * delta_percent // 100
            if delta == 0:
                delta = 1
            actual_refund = expected_refund + sign * delta
            if actual_refund <= 0:
                actual_refund = expected_refund + delta
            variance = actual_refund - expected_refund

            payment.refund_amount = expected_refund

            refund_settlement = SettlementRecord(
                entity_id=f"{settlement.entity_id}_RFND",
                type=SettlementEntityType.REFUND,
                payment_id=payment.payment_id,
                order_id=payment.order_id,
                settlement_id=settlement.settlement_id,
                settlement_utr=settlement.settlement_utr,
                amount=actual_refund,
                debit=actual_refund,
                credit=0,
                fee=0,
                tax=0,
                settled_at=settlement.settled_at,
                description=f"Refund for {payment.payment_id}",
            )
            settlements.append(refund_settlement)

            self.ground_truth.append(
                AnomalyRecord(
                    anomaly_id=self._generate_anomaly_id(),
                    anomaly_type=AnomalyType.REFUND_MISMATCH,
                    affected_entity_id=refund_settlement.entity_id,
                    affected_entity_type="settlement",
                    expected_state=(
                        f"Settlement refund amount should equal payment refund_amount "
                        f"{expected_refund} paise"
                    ),
                    actual_state=f"Settlement refund amount is {actual_refund} paise",
                    variance=variance,
                    related_ids={
                        "payment_id": payment.payment_id,
                        "order_id": payment.order_id,
                        "refund_entity_id": refund_settlement.entity_id,
                        "source_entity_id": settlement.entity_id,
                        "settlement_id": settlement.settlement_id,
                        "payment_refund_amount": expected_refund,
                        "settlement_refund_amount": actual_refund,
                    },
                    description=(
                        f"Payment {payment.payment_id} refund_amount {expected_refund} "
                        f"disagrees with settlement refund {actual_refund}"
                    ),
                )
            )

    def inject_unmatched_reference(
        self,
        settlements: List[SettlementRecord],
        bank_transactions: List[BankTransaction],
    ) -> None:
        """Corrupt matching identifiers (UTR) to create unmatched references."""
        num_to_inject = min(self.counts.unmatched_reference, len(settlements))
        if num_to_inject == 0:
            return

        selected_settlements = self.rng.sample(settlements, num_to_inject)
        bank_by_utr = self._bank_by_utr(bank_transactions)

        for settlement in selected_settlements:
            original_utr = settlement.settlement_utr
            related_bank = bank_by_utr.get(original_utr)
            suffix = f"{self.rng.randint(0, 9999):04d}"
            while original_utr.endswith(suffix):
                suffix = f"{self.rng.randint(0, 9999):04d}"
            corrupted_utr = original_utr[:-4] + suffix
            settlement.settlement_utr = corrupted_utr

            self.ground_truth.append(
                AnomalyRecord(
                    anomaly_id=self._generate_anomaly_id(),
                    anomaly_type=AnomalyType.UNMATCHED_REFERENCE,
                    affected_entity_id=settlement.entity_id,
                    affected_entity_type="settlement",
                    expected_state=f"UTR should be {original_utr}",
                    actual_state=f"UTR corrupted to {corrupted_utr}",
                    related_ids={
                        "entity_id": settlement.entity_id,
                        "settlement_id": settlement.settlement_id,
                        "payment_id": settlement.payment_id,
                        "order_id": settlement.order_id,
                        "original_utr": original_utr,
                        "corrupted_utr": corrupted_utr,
                        "related_bank_transaction_id": (
                            related_bank.bank_transaction_id if related_bank else None
                        ),
                    },
                    description=(
                        f"Settlement UTR corrupted from {original_utr} to {corrupted_utr}"
                    ),
                )
            )

    def inject_all_anomalies(
        self,
        payments: List[Payment],
        settlements: List[SettlementRecord],
        bank_transactions: List[BankTransaction],
    ) -> List[AnomalyRecord]:
        """Inject all configured anomaly types and return ground truth.

        Operates in-place on the provided lists.
        """
        self.ground_truth = []
        self.anomaly_counter = 0
        self.counts = self._resolve_counts(payments, settlements, bank_transactions)

        self.inject_missing_settlement(payments, settlements, bank_transactions)
        self.inject_missing_bank_credit(settlements, bank_transactions)
        self.inject_amount_mismatch(bank_transactions)
        self.inject_duplicate(settlements)
        self.inject_refund_mismatch(payments, settlements)
        self.inject_unmatched_reference(settlements, bank_transactions)

        return self.ground_truth
