"""Reconciliation result models for Phase 2B."""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class ReconciliationStatus(str, Enum):
    """Primary reconciliation status.
    
    Precedence order (highest to lowest):
    1. UNKNOWN
    2. UNMATCHED_REFERENCE
    3. DUPLICATE
    4. REFUND_MISMATCH
    5. AMOUNT_MISMATCH
    6. MISSING_SETTLEMENT
    7. PENDING_SETTLEMENT
    8. MISSING_BANK_CREDIT
    9. PENDING_BANK_CREDIT
    10. RECONCILED
    """
    UNKNOWN = "UNKNOWN"
    UNMATCHED_REFERENCE = "UNMATCHED_REFERENCE"
    DUPLICATE = "DUPLICATE"
    REFUND_MISMATCH = "REFUND_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    PENDING_SETTLEMENT = "PENDING_SETTLEMENT"
    MISSING_BANK_CREDIT = "MISSING_BANK_CREDIT"
    PENDING_BANK_CREDIT = "PENDING_BANK_CREDIT"
    RECONCILED = "RECONCILED"


# Status precedence order (lower number = higher priority)
STATUS_PRECEDENCE = {
    ReconciliationStatus.UNKNOWN: 1,
    ReconciliationStatus.UNMATCHED_REFERENCE: 2,
    ReconciliationStatus.DUPLICATE: 3,
    ReconciliationStatus.REFUND_MISMATCH: 4,
    ReconciliationStatus.AMOUNT_MISMATCH: 5,
    ReconciliationStatus.MISSING_SETTLEMENT: 6,
    ReconciliationStatus.PENDING_SETTLEMENT: 7,
    ReconciliationStatus.MISSING_BANK_CREDIT: 8,
    ReconciliationStatus.PENDING_BANK_CREDIT: 9,
    ReconciliationStatus.RECONCILED: 10,
}


class ReconciliationEvidence(BaseModel):
    """Structured evidence for a reconciliation decision."""
    
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    settlement_id: Optional[str] = None
    settlement_entity_ids: list[str] = Field(default_factory=list)
    settlement_utr: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    
    payment_amount_paise: Optional[int] = None
    settlement_amount_paise: Optional[int] = None
    settlement_credit_paise: Optional[int] = None
    settlement_debit_paise: Optional[int] = None
    bank_amount_paise: Optional[int] = None
    
    expected_amount_paise: Optional[int] = None
    actual_amount_paise: Optional[int] = None
    variance_paise: Optional[int] = None
    abs_variance_paise: Optional[int] = None
    
    payment_refund_amount_paise: Optional[int] = None
    settlement_refund_amount_paise: Optional[int] = None
    
    rule_applied: Optional[str] = None
    conflict_reason: Optional[str] = None
    
    payment_date: Optional[datetime] = None
    settlement_date: Optional[datetime] = None
    bank_date: Optional[datetime] = None
    
    extra: dict[str, Any] = Field(default_factory=dict)


class ResultLevel(str, Enum):
    """Whether a result describes a payment or a settlement batch."""

    PAYMENT = "PAYMENT"
    BATCH = "BATCH"


class ReconciliationResult(BaseModel):
    """Result of reconciling a single payment or a single settlement batch."""

    primary_status: ReconciliationStatus
    evidence: ReconciliationEvidence
    level: ResultLevel = ResultLevel.PAYMENT
    secondary_findings: list[ReconciliationStatus] = Field(default_factory=list)
    resolution_type: Optional[str] = None  # AUTO_RECONCILED, AUTO_RESOLVED, or None
    message: Optional[str] = None


class SettlementBatch(BaseModel):
    """Aggregated view of all settlement lines in one batch."""
    
    settlement_id: str
    settlement_utrs: list[str] = Field(default_factory=list)  # Should be 1 for clean data
    entity_ids: list[str] = Field(default_factory=list)
    
    total_credit_paise: int = 0
    total_debit_paise: int = 0
    net_settlement_paise: int = 0
    total_fee_paise: int = 0
    total_tax_paise: int = 0
    
    line_count: int = 0
    payment_lines: int = 0
    refund_lines: int = 0
    adjustment_lines: int = 0
    
    settled_at: Optional[datetime] = None  # Earliest settlement timestamp
    
    def has_conflicting_utrs(self) -> bool:
        """Check if batch has multiple distinct non-empty UTRs."""
        non_empty_utrs = [utr for utr in self.settlement_utrs if utr and utr.strip()]
        return len(set(non_empty_utrs)) > 1
    
    def primary_utr(self) -> Optional[str]:
        """Return the single UTR if unambiguous, else None."""
        non_empty_utrs = [utr for utr in self.settlement_utrs if utr and utr.strip()]
        unique_utrs = list(set(non_empty_utrs))
        return unique_utrs[0] if len(unique_utrs) == 1 else None


class ReconciliationSummary(BaseModel):
    """Run-level summary metrics."""
    
    payments_processed: int = 0
    settlement_lines_processed: int = 0
    settlement_batches_processed: int = 0
    bank_transactions_processed: int = 0
    
    reconciled_count: int = 0
    pending_count: int = 0
    exception_count: int = 0
    
    status_counts: dict[str, int] = Field(default_factory=dict)
    
    total_expected_settlement_paise: int = 0
    total_matched_bank_paise: int = 0
    total_absolute_variance_paise: int = 0

    batch_status_counts: dict[str, int] = Field(default_factory=dict)
    batch_reconciled_count: int = 0
    batch_pending_count: int = 0
    batch_exception_count: int = 0
    
    processing_duration_seconds: float = 0.0
    
    run_timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReconciliationRun(BaseModel):
    """Full engine output with payment-level and batch-level results kept separate."""

    payment_results: list[ReconciliationResult] = Field(default_factory=list)
    batch_results: list[ReconciliationResult] = Field(default_factory=list)
    summary: ReconciliationSummary
