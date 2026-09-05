"""Build API snapshots from an existing ReconciliationRun. No engine logic."""

from __future__ import annotations

from datetime import datetime

from backend.app.api.schemas import (
    AnalyticsWorkspaceResponse,
    CurrentRunResponse,
    ExceptionImpactRow,
    ExceptionTrendDay,
    HealthPoint,
    InvestigationBundleResponse,
    PaymentResponse,
)
from backend.app.workspace.scenarios import SCENARIO_NORMAL
from backend.app.workspace.utr_display import payment_facing_utr, with_payment_facing_utrs
from backend.app.investigation.context import exception_id_for, is_eligible
from backend.app.investigation.models import (
    InvestigationContext,
    InvestigationOutcome,
    InvestigationRecord,
    InvestigationReport,
)
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.reconciliation.models import (
    ReconciliationResult,
    ReconciliationRun,
    ReconciliationStatus,
    ResultLevel,
)


def percent(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def reconciliation_rate(reconciled_count: int, payments_processed: int) -> float:
    """Share of payments the engine marked RECONCILED."""
    return percent(reconciled_count, payments_processed)


def run_date_from_timestamp(timestamp: datetime) -> str:
    return timestamp.date().isoformat()


def allocate_run_id(timestamp: datetime, existing_ids: set[str]) -> str:
    base = f"run_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    if base not in existing_ids:
        return base
    suffix = 2
    candidate = f"{base}_{suffix}"
    while candidate in existing_ids:
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate


def impact_by_status(run: ReconciliationRun) -> dict[str, int]:
    """Sum abs_variance_paise for each primary_status across payment and batch results."""
    totals: dict[str, int] = {status.value: 0 for status in ReconciliationStatus}
    for result in list(run.payment_results) + list(run.batch_results):
        variance = result.evidence.abs_variance_paise or 0
        totals[result.primary_status.value] += variance
    return {status: amount for status, amount in totals.items() if amount}


def health_point(
    run_id: str,
    run: ReconciliationRun,
    scenario: str = SCENARIO_NORMAL,
) -> HealthPoint:
    summary = run.summary
    return HealthPoint(
        run_id=run_id,
        run_date=run_date_from_timestamp(summary.run_timestamp),
        reconciliation_rate=reconciliation_rate(
            summary.reconciled_count, summary.payments_processed
        ),
        payments_processed=summary.payments_processed,
        status_counts=dict(summary.status_counts),
        batch_status_counts=dict(summary.batch_status_counts),
        scenario=scenario,
    )


def current_run_response(
    run_id: str,
    run: ReconciliationRun,
    scenario: str = SCENARIO_NORMAL,
) -> CurrentRunResponse:
    summary = run.summary
    processed = summary.payments_processed
    rate = reconciliation_rate(summary.reconciled_count, processed)
    return CurrentRunResponse(
        run_id=run_id,
        run_date=run_date_from_timestamp(summary.run_timestamp),
        run_timestamp=summary.run_timestamp.isoformat(),
        payments_processed=processed,
        reconciled_count=summary.reconciled_count,
        pending_count=summary.pending_count,
        exception_count=summary.exception_count,
        reconciled_percent=percent(summary.reconciled_count, processed),
        pending_percent=percent(summary.pending_count, processed),
        exception_percent=percent(summary.exception_count, processed),
        reconciliation_rate=rate,
        status_counts=dict(summary.status_counts),
        batch_status_counts=dict(summary.batch_status_counts),
        impact_by_status=impact_by_status(run),
        scenario=scenario,
    )


def map_payment_status(payment: Payment) -> str:
    """Map domain payment status onto the frontend payment_status values."""
    if payment.refund_amount > 0:
        return "refunded"
    if payment.status == PaymentStatus.PENDING:
        return "authorized"
    return payment.status.value


def project_payment(
    payment: Payment,
    result: ReconciliationResult | None,
) -> PaymentResponse:
    """Join one CSV payment with its payment-level reconciliation result."""
    evidence = result.evidence if result is not None else None
    investigation_id = None
    if result is not None and is_eligible(result):
        investigation_id = exception_id_for(result)

    refund = payment.refund_amount if payment.refund_amount > 0 else None

    return PaymentResponse(
        payment_id=payment.payment_id,
        order_id=payment.order_id,
        amount_paise=payment.amount,
        currency=payment.currency,
        payment_date=payment.payment_date.isoformat(),
        payment_status=map_payment_status(payment),
        reconciliation_status=(
            result.primary_status.value if result is not None else ReconciliationStatus.UNKNOWN.value
        ),
        method="",
        settlement_id=evidence.settlement_id if evidence is not None else None,
        settlement_utr=payment_facing_utr(
            payment.payment_id,
            evidence.settlement_utr if evidence is not None else None,
        ),
        settlement_amount_paise=(
            evidence.settlement_amount_paise if evidence is not None else None
        ),
        variance_paise=evidence.variance_paise if evidence is not None else None,
        refund_amount_paise=refund,
        settlement_refund_amount_paise=(
            evidence.settlement_refund_amount_paise if evidence is not None else None
        ),
        result_summary=(result.message or "") if result is not None else "",
        investigation_id=investigation_id,
        incident_ids=[],
    )


def payment_results_by_id(run: ReconciliationRun) -> dict[str, ReconciliationResult]:
    indexed: dict[str, ReconciliationResult] = {}
    for result in run.payment_results:
        if result.level != ResultLevel.PAYMENT:
            continue
        payment_id = result.evidence.payment_id
        if payment_id:
            indexed[payment_id] = result
    return indexed


def run_results(run: ReconciliationRun) -> list[ReconciliationResult]:
    return list(run.payment_results) + list(run.batch_results)


def eligible_results(run: ReconciliationRun) -> list[ReconciliationResult]:
    return [result for result in run_results(run) if is_eligible(result)]


def deterministic_investigation_record(
    result: ReconciliationResult,
    context: InvestigationContext,
) -> InvestigationRecord:
    """Placeholder record when an exception is eligible but AI has not run."""
    return InvestigationRecord(
        exception_id=context.exception_id,
        deterministic_status=result.primary_status,
        deterministic_rule=result.evidence.rule_applied,
        result_level=result.level,
        outcome=InvestigationOutcome.ESCALATED,
        investigation=None,
        human_review_required=True,
        guardrail_violations=[],
        invalid_evidence_references=[],
        failure_reason=None,
        evidence_count=len(context.evidence),
        evidence_dropped_count=context.evidence_dropped_count,
        financial_records_modified=False,
    )


def investigation_bundle(
    result: ReconciliationResult,
    context: InvestigationContext,
    record: InvestigationRecord | None = None,
) -> InvestigationBundleResponse:
    display_context = with_payment_facing_utrs(context, result)
    return InvestigationBundleResponse(
        record=record or deterministic_investigation_record(result, display_context),
        context=display_context,
    )


ANALYTICS_EXCEPTION_TYPES = (
    "AMOUNT_MISMATCH",
    "MISSING_BANK_CREDIT",
    "UNKNOWN",
    "UNMATCHED_REFERENCE",
    "REFUND_MISMATCH",
    "DUPLICATE",
    "MISSING_SETTLEMENT",
)

_NON_EXCEPTION_STATUSES = {
    ReconciliationStatus.RECONCILED.value,
    ReconciliationStatus.PENDING_SETTLEMENT.value,
    ReconciliationStatus.PENDING_BANK_CREDIT.value,
}


def payment_exception_counts(status_counts: dict[str, int]) -> dict[str, int]:
    """Payment-level exceptions only. Batch results are not added in."""
    return {
        status: count
        for status, count in status_counts.items()
        if count > 0 and status not in _NON_EXCEPTION_STATUSES
    }


def analytics_workspace(
    run: ReconciliationRun,
    history: list[HealthPoint],
    investigation_records: list[InvestigationRecord],
) -> AnalyticsWorkspaceResponse:
    """Project stored runs + the current exception book. No invented days."""
    trend: list[ExceptionTrendDay] = []
    for point in history:
        payment_counts = dict(point.status_counts)
        trend.append(
            ExceptionTrendDay(
                date=point.run_date,
                counts={
                    status: payment_counts.get(status, 0)
                    for status in ANALYTICS_EXCEPTION_TYPES
                },
            )
        )

    payment_counts = dict(run.summary.status_counts)
    impact = impact_by_status(run)
    distribution = [
        ExceptionImpactRow(
            type=status,
            count=payment_counts.get(status, 0),
            impact_paise=impact.get(status, 0),
        )
        for status in ANALYTICS_EXCEPTION_TYPES
    ]
    known_types = set(ANALYTICS_EXCEPTION_TYPES)
    for status, count in payment_exception_counts(payment_counts).items():
        if status in known_types:
            continue
        distribution.append(
            ExceptionImpactRow(
                type=status,
                count=count,
                impact_paise=impact.get(status, 0),
            )
        )

    return AnalyticsWorkspaceResponse(
        as_of=run_date_from_timestamp(run.summary.run_timestamp),
        reconciliation=list(history),
        exception_trend=trend,
        distribution=distribution,
        investigations=investigation_records,
    )


def investigation_report_from_records(
    run: ReconciliationRun,
    records: list[InvestigationRecord],
) -> InvestigationReport:
    """Aggregate the same counts investigate_run would, without calling the LLM."""
    all_results = run_results(run)
    eligible = [result for result in all_results if is_eligible(result)]
    return InvestigationReport(
        records=records,
        total_results=len(all_results),
        eligible_exceptions=len(eligible),
        skipped_not_eligible=len(all_results) - len(eligible),
        investigated=sum(
            1 for record in records if record.outcome == InvestigationOutcome.INVESTIGATED
        ),
        escalated=sum(
            1 for record in records if record.outcome == InvestigationOutcome.ESCALATED
        ),
        failed=sum(1 for record in records if record.outcome == InvestigationOutcome.FAILED),
        human_review_required_count=sum(
            1 for record in records if record.human_review_required
        ),
        financial_records_modified=False,
    )
