"""API DTOs for reconciliation runs. Thin projections of engine output."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.investigation.models import InvestigationContext, InvestigationRecord


class HealthPoint(BaseModel):
    """One stored reconciliation run, matching the frontend health series."""

    run_id: str
    run_date: str
    reconciliation_rate: float
    payments_processed: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    batch_status_counts: dict[str, int] = Field(default_factory=dict)
    scenario: str = "normal"


class CreateRunRequest(BaseModel):
    """Optional body for POST /api/runs. Omitted scenario is Normal Day."""

    scenario: str = "normal"


class CurrentRunResponse(BaseModel):
    """Latest ReconciliationSummary plus computed percentages."""

    run_id: str
    run_date: str
    run_timestamp: str
    payments_processed: int
    reconciled_count: int
    pending_count: int
    exception_count: int
    reconciled_percent: float
    pending_percent: float
    exception_percent: float
    reconciliation_rate: float
    status_counts: dict[str, int] = Field(default_factory=dict)
    batch_status_counts: dict[str, int] = Field(default_factory=dict)
    impact_by_status: dict[str, int] = Field(default_factory=dict)
    scenario: str = "normal"


class ExceptionTrendDay(BaseModel):
    date: str
    counts: dict[str, int] = Field(default_factory=dict)


class ExceptionImpactRow(BaseModel):
    type: str
    count: int
    impact_paise: int


class AnalyticsWorkspaceResponse(BaseModel):
    """Run-history analytics. One trend day per stored run; no fabricated days."""

    as_of: str
    reconciliation: list[HealthPoint] = Field(default_factory=list)
    exception_trend: list[ExceptionTrendDay] = Field(default_factory=list)
    distribution: list[ExceptionImpactRow] = Field(default_factory=list)
    investigations: list[InvestigationRecord] = Field(default_factory=list)


class PaymentResponse(BaseModel):
    """Projected payment for the operations console. Not the CSV Payment model."""

    payment_id: str
    order_id: str
    amount_paise: int
    currency: str
    payment_date: str
    payment_status: str
    reconciliation_status: str
    method: str = ""
    settlement_id: str | None = None
    settlement_utr: str | None = None
    settlement_amount_paise: int | None = None
    variance_paise: int | None = None
    refund_amount_paise: int | None = None
    settlement_refund_amount_paise: int | None = None
    result_summary: str = ""
    investigation_id: str | None = None
    incident_ids: list[str] = Field(default_factory=list)


class InvestigationBundleResponse(BaseModel):
    """Eligible exception plus bounded context. Matches the frontend bundle."""

    record: InvestigationRecord
    context: InvestigationContext | None = None
