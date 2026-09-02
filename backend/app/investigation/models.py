"""Typed models for the Phase 3B AI investigation layer.

The deterministic reconciliation engine remains the financial source of truth.
These models describe an *investigation* of an exception, never a financial fact.

Note on structural guardrails:
`AIInvestigation` intentionally has no amount, UTR, identifier or timestamp
fields. The AI therefore has no schema slot in which to return a financial
value, so it cannot supply authoritative financial data even if it tries.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.reconciliation.models import ReconciliationStatus, ResultLevel


class EvidenceSource(str, Enum):
    """Where a piece of supplied evidence came from."""

    PAYMENT = "PAYMENT"
    SETTLEMENT = "SETTLEMENT"
    BANK = "BANK"
    DETERMINISTIC = "DETERMINISTIC"


class EvidenceItem(BaseModel):
    """One bounded, addressable evidence item supplied to the investigator.

    Values are pre-formatted strings produced by the deterministic engine so the
    AI reads them as given facts rather than recomputing them.
    """

    evidence_id: str
    source: EvidenceSource
    record_id: str
    field: str
    value: str
    relevance: str


class InvestigationContext(BaseModel):
    """The complete bounded context handed to the AI for one exception.

    Nothing outside this object is available to the AI.
    """

    exception_id: str
    deterministic_status: ReconciliationStatus
    result_level: ResultLevel
    rule_applied: Optional[str] = None
    message: Optional[str] = None
    identifiers: dict[str, str] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    allowed_classifications: list[ReconciliationStatus] = Field(default_factory=list)
    evidence_dropped_count: int = 0

    def evidence_ids(self) -> set[str]:
        return {item.evidence_id for item in self.evidence}


class AIInvestigation(BaseModel):
    """Validated AI investigation response.

    `extra="forbid"` rejects any field the schema does not define, which blocks
    an AI attempt to smuggle in amounts, identifiers or resolution instructions.

    confidence is confidence in the *investigation finding*, not financial
    certainty, and never grants permission to modify financial records.
    """

    model_config = ConfigDict(extra="forbid")

    exception_id: str
    finding: str
    classification: ReconciliationStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradictory_evidence: list[str] = Field(default_factory=list)
    recommendation: str
    human_review_required: bool
    financial_records_modified: bool = False


class InvestigationOutcome(str, Enum):
    """Result of attempting to investigate one exception."""

    INVESTIGATED = "INVESTIGATED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class GuardrailViolation(str, Enum):
    """Reasons an AI response was flagged rather than accepted as-is."""

    EXCEPTION_ID_MISMATCH = "EXCEPTION_ID_MISMATCH"
    UNSUPPORTED_CLASSIFICATION = "UNSUPPORTED_CLASSIFICATION"
    HALLUCINATED_EVIDENCE_REFERENCE = "HALLUCINATED_EVIDENCE_REFERENCE"
    NO_SUPPORTING_EVIDENCE = "NO_SUPPORTING_EVIDENCE"
    CLAIMED_FINANCIAL_MODIFICATION = "CLAIMED_FINANCIAL_MODIFICATION"
    CONFIDENCE_BELOW_THRESHOLD = "CONFIDENCE_BELOW_THRESHOLD"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    CLASSIFICATION_DISAGREES_WITH_ENGINE = "CLASSIFICATION_DISAGREES_WITH_ENGINE"
    UNGROUNDED_IDENTIFIER_IN_PROSE = "UNGROUNDED_IDENTIFIER_IN_PROSE"


class InvestigationRecord(BaseModel):
    """An investigation attached to one deterministic exception.

    `deterministic_status` and `deterministic_rule` are copied from the engine
    result and are never derived from the AI response.
    """

    exception_id: str
    deterministic_status: ReconciliationStatus
    deterministic_rule: Optional[str] = None
    result_level: ResultLevel
    outcome: InvestigationOutcome
    investigation: Optional[AIInvestigation] = None
    human_review_required: bool = True
    guardrail_violations: list[GuardrailViolation] = Field(default_factory=list)
    invalid_evidence_references: list[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None
    evidence_count: int = 0
    evidence_dropped_count: int = 0
    financial_records_modified: bool = False


class InvestigationReport(BaseModel):
    """Run-level investigation output. JSON serializable."""

    records: list[InvestigationRecord] = Field(default_factory=list)
    total_results: int = 0
    eligible_exceptions: int = 0
    skipped_not_eligible: int = 0
    investigated: int = 0
    escalated: int = 0
    failed: int = 0
    human_review_required_count: int = 0
    financial_records_modified: bool = False
