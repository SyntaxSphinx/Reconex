"""Clean synthetic data generator without anomalies."""

import random
from datetime import datetime, timedelta
from typing import List, Tuple
from backend.app.models import (
    Payment,
    PaymentStatus,
    SettlementRecord,
    SettlementEntityType,
    BankTransaction,
    TransactionType,
)
from backend.app.generator.config import GeneratorConfig


class CleanDataGenerator:
    """Generates clean, internally consistent synthetic financial data."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self.start_date = datetime(2024, 1, 1, 0, 0, 0)

    def _generate_id(self, prefix: str, index: int) -> str:
        """Generate a unique ID with prefix."""
        return f"{prefix}_{self.rng.randint(100000, 999999)}_{index:06d}"

    def _generate_amount(self) -> int:
        """Generate a realistic payment amount in integer paise.

        Favors smaller amounts: 50% small, 35% medium, 15% large.
        """
        bucket = self.rng.randint(1, 100)
        if bucket <= 50:
            return self.rng.randint(10000, 100000)
        if bucket <= 85:
            return self.rng.randint(100000, 500000)
        return self.rng.randint(500000, self.config.max_amount_paise)

    def _calculate_fee_and_tax(self, amount: int) -> Tuple[int, int]:
        """Calculate fee and tax in integer paise."""
        fee = self.config.calculate_fee(amount)
        tax = self.config.calculate_tax(fee)
        return fee, tax

    def _generate_date(self, base_date: datetime, offset_hours: int) -> datetime:
        """Generate a timestamp with some random variation."""
        offset_minutes = self.rng.randint(-60, 60)
        return base_date + timedelta(hours=offset_hours, minutes=offset_minutes)

    def generate_clean_data(
        self,
    ) -> Tuple[List[Payment], List[SettlementRecord], List[BankTransaction]]:
        """Generate clean synthetic data with consistent relationships.

        Returns:
            Tuple of (payments, settlements, bank_transactions)
        """
        payments: List[Payment] = []
        settlements: List[SettlementRecord] = []
        bank_transactions: List[BankTransaction] = []

        for i in range(self.config.num_records):
            hours_offset = (i * self.config.date_range_days * 24) // self.config.num_records
            payment_date = self._generate_date(self.start_date, hours_offset)

            payment = Payment(
                payment_id=self._generate_id("pay", i),
                order_id=self._generate_id("order", i),
                customer_id=self._generate_id("cust", i % 200),
                amount=self._generate_amount(),
                currency=self.config.currency,
                payment_date=payment_date,
                status=PaymentStatus.CAPTURED,
                refund_amount=0,
            )
            payments.append(payment)

        num_batches = max(1, self.config.num_records // self.config.payments_per_settlement)
        payments_per_batch = self.config.num_records // num_batches

        settlement_idx = 0
        for batch_num in range(num_batches):
            start_idx = batch_num * payments_per_batch
            end_idx = (
                start_idx + payments_per_batch
                if batch_num < num_batches - 1
                else self.config.num_records
            )
            batch_payments = payments[start_idx:end_idx]

            if not batch_payments:
                continue

            last_payment_date = max(p.payment_date for p in batch_payments)
            settlement_date = last_payment_date + timedelta(
                days=self.rng.randint(1, 2), hours=self.rng.randint(0, 12)
            )

            settlement_id = self._generate_id("batch", batch_num)
            settlement_utr = (
                f"UTR{settlement_date.strftime('%Y%m%d')}{self.rng.randint(1000000, 9999999)}"
            )

            total_credit = 0

            for payment in batch_payments:
                fee, tax = self._calculate_fee_and_tax(payment.amount)
                credit = payment.amount - fee - tax

                settlement = SettlementRecord(
                    entity_id=self._generate_id("setl", settlement_idx),
                    type=SettlementEntityType.PAYMENT,
                    payment_id=payment.payment_id,
                    order_id=payment.order_id,
                    settlement_id=settlement_id,
                    settlement_utr=settlement_utr,
                    amount=payment.amount,
                    debit=0,
                    credit=credit,
                    fee=fee,
                    tax=tax,
                    settled_at=settlement_date,
                    description=f"Payment settlement for {payment.payment_id}",
                )
                settlements.append(settlement)
                total_credit += credit
                settlement_idx += 1

            bank_txn = BankTransaction(
                bank_transaction_id=self._generate_id("bank_txn", batch_num),
                transaction_date=settlement_date + timedelta(hours=self.rng.randint(1, 4)),
                description=f"Settlement credit for batch {settlement_id}",
                amount=total_credit,
                transaction_type=TransactionType.CREDIT,
                utr=settlement_utr,
            )
            bank_transactions.append(bank_txn)

        return payments, settlements, bank_transactions
