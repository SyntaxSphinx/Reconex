"""Tests for Phase 2B reconciliation engine."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from backend.app.models import Payment, SettlementRecord, BankTransaction, PaymentStatus, SettlementEntityType, TransactionType
from backend.app.reconciliation import (
    CSVLoader,
    LoadedData,
    ReconciliationEngine,
    ReconciliationStatus,
    ResultLevel,
    SettlementBatch,
)
from backend.app.generator import CleanDataGenerator, GeneratorConfig
from backend.app.reconciliation.loader import CSVLoadError


# Helper to create test data
def make_payment(
    payment_id: str = "pay_001",
    order_id: str = "order_001",
    amount: int = 100000,
    status: PaymentStatus = PaymentStatus.CAPTURED,
    refund_amount: int = 0,
    payment_date: datetime = None,
) -> Payment:
    """Create a test payment."""
    if payment_date is None:
        payment_date = datetime(2024, 1, 15, 10, 0, 0)
    
    return Payment(
        payment_id=payment_id,
        order_id=order_id,
        customer_id="cust_001",
        amount=amount,
        currency="INR",
        payment_date=payment_date,
        status=status,
        refund_amount=refund_amount,
    )


def make_settlement(
    entity_id: str = "setl_001",
    settlement_id: str = "batch_001",
    settlement_utr: str = "UTR001",
    payment_id: str = "pay_001",
    order_id: str = "order_001",
    amount: int = 100000,
    credit: int = 97300,
    debit: int = 0,
    fee: int = 1800,
    tax: int = 324,
    entity_type: SettlementEntityType = SettlementEntityType.PAYMENT,
    settled_at: datetime = None,
) -> SettlementRecord:
    """Create a test settlement record."""
    if settled_at is None:
        settled_at = datetime(2024, 1, 16, 9, 0, 0)
    
    return SettlementRecord(
        entity_id=entity_id,
        type=entity_type,
        payment_id=payment_id,
        order_id=order_id,
        settlement_id=settlement_id,
        settlement_utr=settlement_utr,
        amount=amount,
        debit=debit,
        credit=credit,
        fee=fee,
        tax=tax,
        settled_at=settled_at,
        description=f"Settlement for {payment_id}",
    )


def make_bank_transaction(
    bank_transaction_id: str = "bank_001",
    utr: str = "UTR001",
    amount: int = 97300,
    transaction_type: TransactionType = TransactionType.CREDIT,
    transaction_date: datetime = None,
) -> BankTransaction:
    """Create a test bank transaction."""
    if transaction_date is None:
        transaction_date = datetime(2024, 1, 16, 10, 0, 0)
    
    return BankTransaction(
        bank_transaction_id=bank_transaction_id,
        transaction_date=transaction_date,
        description=f"Credit for {utr}",
        amount=amount,
        transaction_type=transaction_type,
        utr=utr,
    )


class TestReconciliationModels:
    """Test reconciliation data models."""
    
    def test_settlement_batch_no_conflicting_utrs(self):
        """Test settlement batch with consistent UTR."""
        batch = SettlementBatch(
            settlement_id="batch_001",
            settlement_utrs=["UTR001", "UTR001", "UTR001"],
            entity_ids=["setl_001", "setl_002", "setl_003"],
            total_credit_paise=300000,
            total_debit_paise=0,
            net_settlement_paise=300000,
            line_count=3,
        )
        
        assert not batch.has_conflicting_utrs()
        assert batch.primary_utr() == "UTR001"
    
    def test_settlement_batch_conflicting_utrs(self):
        """Test settlement batch with multiple UTRs."""
        batch = SettlementBatch(
            settlement_id="batch_001",
            settlement_utrs=["UTR001", "UTR002", "UTR001"],
            entity_ids=["setl_001", "setl_002", "setl_003"],
            total_credit_paise=300000,
            total_debit_paise=0,
            net_settlement_paise=300000,
            line_count=3,
        )
        
        assert batch.has_conflicting_utrs()
        assert batch.primary_utr() is None


class TestCSVLoader:
    """Test CSV loading and validation."""
    
    def test_load_invalid_directory(self):
        """Test loading from non-existent directory."""
        with pytest.raises(CSVLoadError):
            CSVLoader.load_all(Path("/invalid/path"))
    
    def test_normalize_str(self):
        """Test string normalization."""
        assert CSVLoader._normalize_str("  test  ") == "test"
        assert CSVLoader._normalize_str("") is None
        assert CSVLoader._normalize_str("   ") is None
        assert CSVLoader._normalize_str(None) is None


class TestCleanReconciliation:
    """Test clean reconciliation with no anomalies."""
    
    def test_fully_reconciled_payment(self):
        """Test payment that reconciles cleanly through all stages."""
        payment = make_payment()
        settlement = make_settlement()
        bank = make_bank_transaction()
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        results = run.payment_results
        summary = run.summary
        
        assert len(results) == 1
        result = results[0]
        
        assert result.primary_status == ReconciliationStatus.RECONCILED
        assert result.resolution_type == "AUTO_RECONCILED"
        assert result.level.value == "PAYMENT"
        assert result.evidence.payment_id == "pay_001"
        assert result.evidence.settlement_id == "batch_001"

        assert len(run.batch_results) == 1
        batch_result = run.batch_results[0]
        assert batch_result.level.value == "BATCH"
        assert batch_result.primary_status == ReconciliationStatus.RECONCILED
        assert batch_result.evidence.bank_transaction_id == "bank_001"
        assert batch_result.evidence.expected_amount_paise == 97300
        assert batch_result.evidence.actual_amount_paise == 97300
        
        assert summary.reconciled_count == 1
        assert summary.exception_count == 0
        assert summary.pending_count == 0
        assert summary.batch_reconciled_count == 1
    
    def test_multiple_payments_one_settlement_batch(self):
        """Test multiple payments in one settlement batch."""
        payment1 = make_payment(payment_id="pay_001", order_id="order_001", amount=100000)
        payment2 = make_payment(payment_id="pay_002", order_id="order_002", amount=200000)
        
        # Both payments have same settlement_id but different entity_ids
        settlement1 = make_settlement(
            entity_id="setl_001",
            payment_id="pay_001",
            order_id="order_001",
            settlement_id="batch_001",
            settlement_utr="UTR001",
            amount=100000,
            credit=97300,
        )
        
        settlement2 = make_settlement(
            entity_id="setl_002",
            payment_id="pay_002",
            order_id="order_002",
            settlement_id="batch_001",
            settlement_utr="UTR001",
            amount=200000,
            credit=194600,
        )
        
        # Bank credit = sum of both settlement credits
        bank = make_bank_transaction(utr="UTR001", amount=97300 + 194600)
        
        data = LoadedData(
            payments=[payment1, payment2],
            settlements=[settlement1, settlement2],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        results = run.payment_results
        summary = run.summary
        
        assert len(results) == 2
        assert all(r.primary_status == ReconciliationStatus.RECONCILED for r in results)
        assert summary.reconciled_count == 2
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert run.batch_results[0].evidence.actual_amount_paise == 97300 + 194600


class TestPendingStates:
    """Test pending settlement and bank credit detection."""
    
    def test_pending_settlement_within_window(self):
        """Test payment within settlement window (no settlement yet)."""
        # Payment is recent (1 day old)
        payment = make_payment(payment_date=datetime.utcnow() - timedelta(days=1))
        
        data = LoadedData(payments=[payment], settlements=[], bank_transactions=[])
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.PENDING_SETTLEMENT
        assert run.summary.pending_count == 1
    
    def test_pending_bank_credit_within_window(self):
        """Test settlement within bank credit window (no bank credit yet)."""
        # Payment and settlement exist, but no bank transaction
        # Settlement is recent (10 hours ago)
        payment = make_payment(payment_date=datetime.utcnow() - timedelta(days=2))
        settlement = make_settlement(settled_at=datetime.utcnow() - timedelta(hours=10))
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.PENDING_BANK_CREDIT
        assert run.batch_results[0].level == ResultLevel.BATCH


class TestMissingSettlement:
    """Test missing settlement detection."""
    
    def test_missing_settlement_beyond_window(self):
        """Test payment beyond settlement window (settlement is missing)."""
        # Payment is old (5 days)
        payment = make_payment(payment_date=datetime.utcnow() - timedelta(days=5))
        
        data = LoadedData(payments=[payment], settlements=[], bank_transactions=[])
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.MISSING_SETTLEMENT
        assert run.summary.exception_count == 1


class TestMissingBankCredit:
    """Test missing bank credit detection."""
    
    def test_missing_bank_credit_beyond_window(self):
        """Test settlement beyond bank credit window (bank credit is missing)."""
        # Payment and settlement exist, but bank transaction is missing
        # Settlement is old (2 days)
        payment = make_payment(payment_date=datetime.utcnow() - timedelta(days=3))
        settlement = make_settlement(settled_at=datetime.utcnow() - timedelta(days=2))
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.MISSING_BANK_CREDIT
        assert run.batch_results[0].level == ResultLevel.BATCH


class TestAmountMismatch:
    """Test amount mismatch detection."""
    
    def test_payment_settlement_amount_mismatch(self):
        """Test mismatch between payment and settlement amount."""
        payment = make_payment(amount=100000)
        settlement = make_settlement(amount=105000)  # Wrong amount
        bank = make_bank_transaction()
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        result = run.payment_results[0]
        
        assert (
            result.primary_status == ReconciliationStatus.AMOUNT_MISMATCH or
            ReconciliationStatus.AMOUNT_MISMATCH in result.secondary_findings
        )
        assert result.evidence.variance_paise == 5000
        assert result.evidence.abs_variance_paise == 5000
    
    def test_settlement_bank_amount_mismatch(self):
        """Test mismatch between settlement net and bank amount."""
        payment = make_payment(amount=100000)
        settlement = make_settlement(amount=100000, credit=97300)
        bank = make_bank_transaction(amount=95000)  # Wrong amount
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert ReconciliationStatus.AMOUNT_MISMATCH not in run.payment_results[0].secondary_findings
        
        assert len(run.batch_results) == 1
        batch_result = run.batch_results[0]
        assert batch_result.primary_status == ReconciliationStatus.AMOUNT_MISMATCH
        assert batch_result.level == ResultLevel.BATCH
        assert batch_result.evidence.abs_variance_paise == abs(95000 - 97300)
        assert batch_result.evidence.expected_amount_paise == 97300
        assert batch_result.evidence.actual_amount_paise == 95000
        assert batch_result.evidence.settlement_id == "batch_001"
        assert batch_result.evidence.settlement_utr == "UTR001"
        assert batch_result.evidence.bank_transaction_id == "bank_001"


class TestDuplicate:
    """Test duplicate detection."""
    
    def test_duplicate_settlement_lines(self):
        """Test detection of duplicate settlement lines for same payment."""
        payment = make_payment()
        
        # Two settlement lines for the same payment
        settlement1 = make_settlement(entity_id="setl_001", payment_id="pay_001")
        settlement2 = make_settlement(entity_id="setl_002", payment_id="pay_001")
        
        bank = make_bank_transaction()
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement1, settlement2],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.DUPLICATE
        assert len(run.payment_results[0].evidence.settlement_entity_ids) == 2


class TestRefundMismatch:
    """Test refund mismatch detection."""
    
    def test_refund_mismatch(self):
        """Test detection of refund amount mismatch."""
        # Payment has refund_amount
        payment = make_payment(refund_amount=10000)
        
        # Payment settlement line
        settlement_payment = make_settlement(
            entity_id="setl_001",
            payment_id="pay_001",
            entity_type=SettlementEntityType.PAYMENT,
        )
        
        # Refund settlement line with different amount
        settlement_refund = make_settlement(
            entity_id="setl_002",
            payment_id="pay_001",
            entity_type=SettlementEntityType.REFUND,
            debit=15000,  # Different from payment.refund_amount
            credit=0,
        )
        
        bank = make_bank_transaction()
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement_payment, settlement_refund],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        result = run.payment_results[0]
        
        assert (
            result.primary_status == ReconciliationStatus.REFUND_MISMATCH or
            ReconciliationStatus.REFUND_MISMATCH in result.secondary_findings
        )
        assert result.evidence.payment_refund_amount_paise == 10000
        assert result.evidence.settlement_refund_amount_paise == 15000


class TestUnmatchedReference:
    """Test unmatched reference detection."""
    
    def test_missing_utr(self):
        """Test settlement with no valid UTR."""
        payment = make_payment()
        settlement = make_settlement(settlement_utr="")  # Empty UTR
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.UNMATCHED_REFERENCE
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.UNMATCHED_REFERENCE


class TestUnknown:
    """Test UNKNOWN status for ambiguous/conflicting cases."""
    
    def test_conflicting_utrs_in_batch(self):
        """Test settlement batch with conflicting UTRs."""
        payment1 = make_payment(payment_id="pay_001", order_id="order_001")
        payment2 = make_payment(payment_id="pay_002", order_id="order_002")
        
        # Same settlement_id but different UTRs
        settlement1 = make_settlement(
            entity_id="setl_001",
            payment_id="pay_001",
            settlement_id="batch_001",
            settlement_utr="UTR001",
        )
        
        settlement2 = make_settlement(
            entity_id="setl_002",
            payment_id="pay_002",
            settlement_id="batch_001",
            settlement_utr="UTR002",  # Different UTR
        )
        
        data = LoadedData(
            payments=[payment1, payment2],
            settlements=[settlement1, settlement2],
            bank_transactions=[],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.UNKNOWN
        assert run.batch_results[0].level == ResultLevel.BATCH
        assert all(
            r.primary_status == ReconciliationStatus.UNMATCHED_REFERENCE
            for r in run.payment_results
        )
        assert all(r.primary_status != ReconciliationStatus.AMOUNT_MISMATCH for r in run.payment_results)
    
    def test_multiple_bank_transactions_same_utr(self):
        """Test multiple bank transactions with same UTR (ambiguous)."""
        payment = make_payment()
        settlement = make_settlement()
        
        # Two bank transactions with same UTR
        bank1 = make_bank_transaction(bank_transaction_id="bank_001", utr="UTR001")
        bank2 = make_bank_transaction(bank_transaction_id="bank_002", utr="UTR001")
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[bank1, bank2],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.UNKNOWN
        assert "Found" in (run.batch_results[0].evidence.conflict_reason or "")
    
    def test_bank_transaction_wrong_type(self):
        """Test bank transaction is debit instead of credit."""
        payment = make_payment()
        settlement = make_settlement()
        bank = make_bank_transaction(transaction_type=TransactionType.DEBIT)
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.UNKNOWN


class TestIntegerArithmetic:
    """Test that all amounts remain integer paise."""
    
    def test_no_float_in_results(self):
        """Test that all monetary values in results are integers."""
        payment = make_payment(amount=100000)
        settlement = make_settlement(amount=100000, credit=97300)
        bank = make_bank_transaction(amount=97300)
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        for result in list(run.payment_results) + list(run.batch_results):
            ev = result.evidence
            
            # All amounts should be None or int, never float
            if ev.payment_amount_paise is not None:
                assert isinstance(ev.payment_amount_paise, int)
            if ev.settlement_amount_paise is not None:
                assert isinstance(ev.settlement_amount_paise, int)
            if ev.bank_amount_paise is not None:
                assert isinstance(ev.bank_amount_paise, int)
            if ev.variance_paise is not None:
                assert isinstance(ev.variance_paise, int)
            if ev.abs_variance_paise is not None:
                assert isinstance(ev.abs_variance_paise, int)


class TestNonCapturedPayments:
    """Test handling of non-captured payments."""
    
    def test_pending_payment_not_reconciled(self):
        """Test that pending payments are not reconciled."""
        payment = make_payment(status=PaymentStatus.PENDING)
        
        data = LoadedData(payments=[payment], settlements=[], bank_transactions=[])
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        # Pending payments are marked as reconciled (they're not expected to have settlements)
        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert "not captured" in run.payment_results[0].message.lower()
    
    def test_failed_payment_not_reconciled(self):
        """Test that failed payments are not reconciled."""
        payment = make_payment(status=PaymentStatus.FAILED)
        
        data = LoadedData(payments=[payment], settlements=[], bank_transactions=[])
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert "not captured" in run.payment_results[0].message.lower()


class TestStatusPrecedence:
    """Test status precedence rules."""
    
    def test_amount_mismatch_takes_precedence_over_reconciled(self):
        """Test that AMOUNT_MISMATCH has higher precedence than RECONCILED."""
        payment = make_payment(amount=100000)
        settlement = make_settlement(amount=105000)  # Mismatch
        bank = make_bank_transaction(amount=97300)  # Correct for mismatched settlement
        
        data = LoadedData(
            payments=[payment],
            settlements=[settlement],
            bank_transactions=[bank],
        )
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        
        assert len(run.payment_results) == 1
        # Should report amount mismatch, not reconciled
        assert run.payment_results[0].primary_status == ReconciliationStatus.AMOUNT_MISMATCH


class TestGeneratedDataset:
    """Test reconciliation on actual generated dataset."""
    
    @pytest.mark.skipif(
        not Path("data/generated/payments.csv").exists(),
        reason="Generated dataset not found. Run: python -m scripts.generate_data --records 1000 --seed 42",
    )
    def test_reconcile_1000_record_dataset(self):
        """Test reconciliation on the 1000-record Phase 1 dataset."""
        data_dir = Path("data/generated")
        
        data = CSVLoader.load_all(data_dir)
        
        assert len(data.payments) > 0
        assert len(data.settlements) > 0
        assert len(data.bank_transactions) > 0
        
        engine = ReconciliationEngine(data)
        run = engine.reconcile()
        summary = run.summary
        
        # Should process all payments
        assert summary.payments_processed == len(data.payments)
        
        # Should have a mix of statuses
        assert summary.reconciled_count > 0
        
        # All payments should have a result
        assert len(run.payment_results) == len(data.payments)
        assert len(run.batch_results) == summary.settlement_batches_processed
        
        # Batch-level bank mismatches must not be copied onto every payment
        payment_amount_mismatches = [
            r for r in run.payment_results
            if r.primary_status == ReconciliationStatus.AMOUNT_MISMATCH
        ]
        batch_amount_mismatches = [
            r for r in run.batch_results
            if r.primary_status == ReconciliationStatus.AMOUNT_MISMATCH
        ]
        assert len(payment_amount_mismatches) == 0
        assert len(batch_amount_mismatches) > 0
        assert len(batch_amount_mismatches) == len(
            {r.evidence.settlement_id for r in batch_amount_mismatches}
        )
        
        # Summary counts should add up
        assert (
            summary.reconciled_count + summary.pending_count + summary.exception_count
            == summary.payments_processed
        )


class TestBatchLevelIsolation:
    """Batch-vs-bank findings must not be copied onto every payment."""

    def test_clean_1000_record_dataset_fully_reconciled(self):
        """A clean 1000-record dataset remains 1000/1000 reconciled."""
        generator = CleanDataGenerator(GeneratorConfig(num_records=1000, seed=42))
        payments, settlements, banks = generator.generate_clean_data()

        assert len(payments) == 1000
        assert len(banks) == 20

        data = LoadedData(
            payments=payments,
            settlements=settlements,
            bank_transactions=banks,
        )
        run = ReconciliationEngine(data).reconcile()

        assert run.summary.payments_processed == 1000
        assert run.summary.reconciled_count == 1000
        assert run.summary.pending_count == 0
        assert run.summary.exception_count == 0
        assert all(
            r.primary_status == ReconciliationStatus.RECONCILED
            for r in run.payment_results
        )
        assert run.summary.settlement_batches_processed == 20
        assert run.summary.batch_reconciled_count == 20
        assert run.summary.batch_exception_count == 0

    def test_batch_bank_mismatch_is_one_batch_result(self):
        """A batch-vs-bank mismatch produces exactly one batch AMOUNT_MISMATCH."""
        payment1 = make_payment(payment_id="pay_001", order_id="order_001", amount=100000)
        payment2 = make_payment(payment_id="pay_002", order_id="order_002", amount=200000)
        settlement1 = make_settlement(
            entity_id="setl_001",
            payment_id="pay_001",
            order_id="order_001",
            amount=100000,
            credit=97300,
        )
        settlement2 = make_settlement(
            entity_id="setl_002",
            payment_id="pay_002",
            order_id="order_002",
            amount=200000,
            credit=194600,
        )
        bank = make_bank_transaction(amount=250000)

        data = LoadedData(
            payments=[payment1, payment2],
            settlements=[settlement1, settlement2],
            bank_transactions=[bank],
        )
        run = ReconciliationEngine(data).reconcile()

        batch_mismatches = [
            r for r in run.batch_results
            if r.primary_status == ReconciliationStatus.AMOUNT_MISMATCH
        ]
        assert len(batch_mismatches) == 1
        assert batch_mismatches[0].level == ResultLevel.BATCH
        assert batch_mismatches[0].evidence.settlement_id == "batch_001"
        assert batch_mismatches[0].evidence.expected_amount_paise == 97300 + 194600
        assert batch_mismatches[0].evidence.actual_amount_paise == 250000
        assert batch_mismatches[0].evidence.variance_paise == 250000 - (97300 + 194600)
        assert batch_mismatches[0].evidence.bank_transaction_id == "bank_001"
        assert batch_mismatches[0].evidence.settlement_utr == "UTR001"
        assert "AMOUNT_MISMATCH" in (batch_mismatches[0].evidence.rule_applied or "")

        assert len(run.payment_results) == 2
        assert all(r.primary_status == ReconciliationStatus.RECONCILED for r in run.payment_results)
        assert all(
            ReconciliationStatus.AMOUNT_MISMATCH not in r.secondary_findings
            for r in run.payment_results
        )

    def test_valid_payments_not_amount_mismatch_from_batch_bank(self):
        """Valid payment↔settlement rows stay reconciled when the batch bank amount is wrong."""
        payment = make_payment()
        settlement = make_settlement()
        bank = make_bank_transaction(amount=1)

        run = ReconciliationEngine(
            LoadedData(
                payments=[payment],
                settlements=[settlement],
                bank_transactions=[bank],
            )
        ).reconcile()

        assert run.payment_results[0].primary_status == ReconciliationStatus.RECONCILED
        assert run.batch_results[0].primary_status == ReconciliationStatus.AMOUNT_MISMATCH

    def test_missing_bank_credit_is_one_batch_result(self):
        """MISSING_BANK_CREDIT is batch-level and is not multiplied into payment AMOUNT_MISMATCH."""
        payment1 = make_payment(
            payment_id="pay_001",
            order_id="order_001",
            payment_date=datetime.utcnow() - timedelta(days=5),
        )
        payment2 = make_payment(
            payment_id="pay_002",
            order_id="order_002",
            amount=200000,
            payment_date=datetime.utcnow() - timedelta(days=5),
        )
        settlement1 = make_settlement(
            entity_id="setl_001",
            payment_id="pay_001",
            order_id="order_001",
            settled_at=datetime.utcnow() - timedelta(days=2),
        )
        settlement2 = make_settlement(
            entity_id="setl_002",
            payment_id="pay_002",
            order_id="order_002",
            amount=200000,
            credit=194600,
            settled_at=datetime.utcnow() - timedelta(days=2),
        )

        run = ReconciliationEngine(
            LoadedData(
                payments=[payment1, payment2],
                settlements=[settlement1, settlement2],
                bank_transactions=[],
            )
        ).reconcile()

        assert all(r.primary_status == ReconciliationStatus.RECONCILED for r in run.payment_results)
        assert all(
            r.primary_status != ReconciliationStatus.AMOUNT_MISMATCH
            for r in run.payment_results
        )
        assert len(run.batch_results) == 1
        assert run.batch_results[0].primary_status == ReconciliationStatus.MISSING_BANK_CREDIT
        assert run.batch_results[0].level == ResultLevel.BATCH

    def test_corrupted_line_utr_is_payment_unmatched_reference(self):
        """Only the settlement line with a corrupted UTR is UNMATCHED_REFERENCE at payment level."""
        payment1 = make_payment(payment_id="pay_001", order_id="order_001")
        payment2 = make_payment(payment_id="pay_002", order_id="order_002")
        payment3 = make_payment(payment_id="pay_003", order_id="order_003")
        settlement1 = make_settlement(
            entity_id="setl_001",
            payment_id="pay_001",
            order_id="order_001",
            settlement_utr="UTR001",
        )
        settlement2 = make_settlement(
            entity_id="setl_002",
            payment_id="pay_002",
            order_id="order_002",
            settlement_utr="UTR001",
        )
        settlement3 = make_settlement(
            entity_id="setl_003",
            payment_id="pay_003",
            order_id="order_003",
            settlement_utr="UTR_CORRUPT",
        )

        run = ReconciliationEngine(
            LoadedData(
                payments=[payment1, payment2, payment3],
                settlements=[settlement1, settlement2, settlement3],
                bank_transactions=[],
            )
        ).reconcile()

        by_payment = {r.evidence.payment_id: r for r in run.payment_results}
        assert by_payment["pay_001"].primary_status == ReconciliationStatus.RECONCILED
        assert by_payment["pay_002"].primary_status == ReconciliationStatus.RECONCILED
        assert by_payment["pay_003"].primary_status == ReconciliationStatus.UNMATCHED_REFERENCE
        assert run.batch_results[0].primary_status == ReconciliationStatus.UNKNOWN

    def test_engine_does_not_read_ground_truth(self):
        """The reconciliation engine must not depend on ground_truth.json."""
        import inspect
        from backend.app.reconciliation import engine as engine_module
        from backend.app.reconciliation import loader as loader_module

        engine_src = inspect.getsource(engine_module)
        loader_src = inspect.getsource(loader_module)
        assert "ground_truth" not in engine_src
        assert "ground_truth" not in loader_src

