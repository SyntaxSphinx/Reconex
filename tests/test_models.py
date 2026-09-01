"""Tests for domain models."""

from datetime import datetime
import pytest
from backend.app.models import (
    Payment,
    PaymentStatus,
    SettlementRecord,
    SettlementEntityType,
    BankTransaction,
    TransactionType,
)


def test_payment_model():
    """Test Payment model validation."""
    payment = Payment(
        payment_id="pay_123456",
        order_id="order_789012",
        customer_id="cust_345678",
        amount=150000,
        currency="INR",
        payment_date=datetime(2024, 1, 15, 10, 30, 0),
        status=PaymentStatus.CAPTURED,
    )

    assert payment.payment_id == "pay_123456"
    assert payment.amount == 150000
    assert payment.status == PaymentStatus.CAPTURED
    assert payment.refund_amount == 0


def test_payment_refund_amount_must_be_integer_paise():
    """refund_amount is integer paise and rejects negatives."""
    payment = Payment(
        payment_id="pay_123456",
        order_id="order_789012",
        customer_id="cust_345678",
        amount=150000,
        currency="INR",
        payment_date=datetime(2024, 1, 15, 10, 30, 0),
        status=PaymentStatus.CAPTURED,
        refund_amount=2500,
    )
    assert payment.refund_amount == 2500
    assert isinstance(payment.refund_amount, int)

    with pytest.raises(Exception):
        Payment(
            payment_id="pay_123456",
            order_id="order_789012",
            customer_id="cust_345678",
            amount=150000,
            currency="INR",
            payment_date=datetime(2024, 1, 15, 10, 30, 0),
            status=PaymentStatus.CAPTURED,
            refund_amount=-1,
        )


def test_payment_negative_amount():
    """Test that negative amounts are rejected."""
    with pytest.raises(Exception):
        Payment(
            payment_id="pay_123456",
            order_id="order_789012",
            customer_id="cust_345678",
            amount=-1000,
            currency="INR",
            payment_date=datetime(2024, 1, 15, 10, 30, 0),
            status=PaymentStatus.CAPTURED,
        )


def test_settlement_model():
    """Test SettlementRecord model validation."""
    settlement = SettlementRecord(
        entity_id="setl_123456",
        type=SettlementEntityType.PAYMENT,
        payment_id="pay_123456",
        order_id="order_789012",
        settlement_id="batch_001",
        settlement_utr="UTR202401151234567",
        amount=150000,
        debit=0,
        credit=147000,
        fee=2700,
        tax=300,
        settled_at=datetime(2024, 1, 16, 9, 0, 0),
        description="Payment settlement",
    )

    assert settlement.entity_id == "setl_123456"
    assert settlement.type == SettlementEntityType.PAYMENT
    assert settlement.credit == 147000


def test_refund_settlement_model():
    """Refund settlement rows are a valid entity type."""
    settlement = SettlementRecord(
        entity_id="setl_123456_RFND",
        type=SettlementEntityType.REFUND,
        payment_id="pay_123456",
        order_id="order_789012",
        settlement_id="batch_001",
        settlement_utr="UTR202401151234567",
        amount=2500,
        debit=2500,
        credit=0,
        fee=0,
        tax=0,
        settled_at=datetime(2024, 1, 16, 9, 0, 0),
        description="Refund",
    )
    assert settlement.type == SettlementEntityType.REFUND
    assert settlement.debit == 2500


def test_bank_transaction_model():
    """Test BankTransaction model validation."""
    bank_txn = BankTransaction(
        bank_transaction_id="bank_txn_123456",
        transaction_date=datetime(2024, 1, 16, 9, 30, 0),
        description="Settlement credit",
        amount=147000,
        transaction_type=TransactionType.CREDIT,
        utr="UTR202401151234567",
    )

    assert bank_txn.bank_transaction_id == "bank_txn_123456"
    assert bank_txn.transaction_type == TransactionType.CREDIT
    assert bank_txn.amount == 147000
