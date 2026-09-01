"""Explicit ground-truth to engine-result mapping for Phase 2C evaluation.

Ground truth records the injected *cause*. The engine reports observed
*symptoms*. These are not always the same object.

Primary expected statuses (cause → engine classification):

- MISSING_SETTLEMENT     → payment MISSING_SETTLEMENT or PENDING_SETTLEMENT
- MISSING_BANK_CREDIT    → batch MISSING_BANK_CREDIT or PENDING_BANK_CREDIT
- AMOUNT_MISMATCH        → batch AMOUNT_MISMATCH
- DUPLICATE              → payment DUPLICATE
- REFUND_MISMATCH        → payment REFUND_MISMATCH
- UNMATCHED_REFERENCE    → payment UNMATCHED_REFERENCE

Known downstream effects (cause → extra engine symptom that is NOT a false positive):

- MISSING_SETTLEMENT  → batch AMOUNT_MISMATCH
  Removing a settlement credit leaves the original bank amount in place.
- DUPLICATE           → batch AMOUNT_MISMATCH
  An extra payment line increases batch net versus the original bank credit.
- REFUND_MISMATCH     → batch AMOUNT_MISMATCH
  The disagreeing refund debit changes batch net versus the original bank credit.
- UNMATCHED_REFERENCE → batch UNKNOWN
  One corrupted line UTR makes the batch UTR set conflicting (Rule 6).

Not mapped (not a downstream exemption):

- MISSING_BANK_CREDIT observed as batch UNKNOWN because a co-located
  UNMATCHED_REFERENCE made UTRs conflict. That is incorrect classification
  of the missing-bank cause (Rule 16 precedence), while the batch UNKNOWN
  result itself is explained as a downstream effect of UNMATCHED_REFERENCE.
"""

from backend.app.models.anomaly import AnomalyType
from backend.app.reconciliation.models import ReconciliationStatus, ResultLevel


EXPECTED_PRIMARY_STATUS: dict[AnomalyType, frozenset[ReconciliationStatus]] = {
    AnomalyType.MISSING_SETTLEMENT: frozenset(
        {
            ReconciliationStatus.MISSING_SETTLEMENT,
            ReconciliationStatus.PENDING_SETTLEMENT,
        }
    ),
    AnomalyType.MISSING_BANK_CREDIT: frozenset(
        {
            ReconciliationStatus.MISSING_BANK_CREDIT,
            ReconciliationStatus.PENDING_BANK_CREDIT,
        }
    ),
    AnomalyType.AMOUNT_MISMATCH: frozenset({ReconciliationStatus.AMOUNT_MISMATCH}),
    AnomalyType.DUPLICATE: frozenset({ReconciliationStatus.DUPLICATE}),
    AnomalyType.REFUND_MISMATCH: frozenset({ReconciliationStatus.REFUND_MISMATCH}),
    AnomalyType.UNMATCHED_REFERENCE: frozenset({ReconciliationStatus.UNMATCHED_REFERENCE}),
}

EXPECTED_RESULT_LEVEL: dict[AnomalyType, ResultLevel] = {
    AnomalyType.MISSING_SETTLEMENT: ResultLevel.PAYMENT,
    AnomalyType.MISSING_BANK_CREDIT: ResultLevel.BATCH,
    AnomalyType.AMOUNT_MISMATCH: ResultLevel.BATCH,
    AnomalyType.DUPLICATE: ResultLevel.PAYMENT,
    AnomalyType.REFUND_MISMATCH: ResultLevel.PAYMENT,
    AnomalyType.UNMATCHED_REFERENCE: ResultLevel.PAYMENT,
}


class DownstreamRule:
    """One documented cause → extra engine symptom relationship."""

    def __init__(
        self,
        cause: AnomalyType,
        effect_status: ReconciliationStatus,
        effect_level: ResultLevel,
        reason: str,
    ) -> None:
        self.cause = cause
        self.effect_status = effect_status
        self.effect_level = effect_level
        self.reason = reason


DOWNSTREAM_RULES: tuple[DownstreamRule, ...] = (
    DownstreamRule(
        cause=AnomalyType.MISSING_SETTLEMENT,
        effect_status=ReconciliationStatus.AMOUNT_MISMATCH,
        effect_level=ResultLevel.BATCH,
        reason="Removed settlement credit leaves the original bank amount unchanged",
    ),
    DownstreamRule(
        cause=AnomalyType.DUPLICATE,
        effect_status=ReconciliationStatus.AMOUNT_MISMATCH,
        effect_level=ResultLevel.BATCH,
        reason="Duplicate payment line increases batch net versus the original bank credit",
    ),
    DownstreamRule(
        cause=AnomalyType.REFUND_MISMATCH,
        effect_status=ReconciliationStatus.AMOUNT_MISMATCH,
        effect_level=ResultLevel.BATCH,
        reason="Refund debit changes batch net versus the original bank credit",
    ),
    DownstreamRule(
        cause=AnomalyType.UNMATCHED_REFERENCE,
        effect_status=ReconciliationStatus.UNKNOWN,
        effect_level=ResultLevel.BATCH,
        reason="Corrupted line UTR makes the batch UTR set conflicting",
    ),
)
