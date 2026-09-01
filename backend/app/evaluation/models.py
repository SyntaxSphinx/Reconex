"""Typed evaluation report models. JSON serializable via model_dump(mode='json')."""

from typing import Optional, Any
from pydantic import BaseModel, Field

from backend.app.models.anomaly import AnomalyType
from backend.app.reconciliation.models import ReconciliationStatus, ResultLevel


class IdentifierSet(BaseModel):
    """Identifiers used to bind ground truth to an engine result."""

    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    settlement_id: Optional[str] = None
    settlement_utr: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    entity_id: Optional[str] = None
    match_keys: list[str] = Field(default_factory=list)


class EngineResultRef(BaseModel):
    """Compact reference to one engine result for the evaluation report."""

    level: ResultLevel
    primary_status: ReconciliationStatus
    secondary_findings: list[ReconciliationStatus] = Field(default_factory=list)
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    settlement_id: Optional[str] = None
    settlement_utr: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    settlement_entity_ids: list[str] = Field(default_factory=list)
    rule_applied: Optional[str] = None
    expected_amount_paise: Optional[int] = None
    actual_amount_paise: Optional[int] = None
    variance_paise: Optional[int] = None


class AnomalyEvaluation(BaseModel):
    """Evaluation of one ground-truth anomaly."""

    anomaly_id: str
    anomaly_type: AnomalyType
    outcome: str
    identifiers: IdentifierSet
    expected_statuses: list[str] = Field(default_factory=list)
    observed_status: Optional[str] = None
    observed_level: Optional[ResultLevel] = None
    matched_result: Optional[EngineResultRef] = None
    miss_reason: Optional[str] = None


class DownstreamEffect(BaseModel):
    """An engine exception explained as a documented consequence of a GT cause."""

    anomaly_id: str
    cause_type: AnomalyType
    effect_status: ReconciliationStatus
    effect_level: ResultLevel
    reason: str
    result: EngineResultRef


class FalsePositive(BaseModel):
    """An engine exception not explained by a GT primary match or downstream rule."""

    result: EngineResultRef
    reason: str = "No ground-truth cause or documented downstream rule explains this exception"


class TypeMetrics(BaseModel):
    """Per-anomaly-type counts.

    ground_truth_count: injected anomalies of this type.
    correctly_detected: unique match and observed status is in the expected set.
    missed: no unique identifier match to an engine result.
    incorrectly_classified: unique match but observed status is not expected.
    """

    anomaly_type: str
    ground_truth_count: int = 0
    correctly_detected: int = 0
    missed: int = 0
    incorrectly_classified: int = 0


class OverallMetrics(BaseModel):
    """Overall evaluation metrics.

    detection_rate (recall):
        (correctly_detected + incorrectly_classified) / total_ground_truth_anomalies
        Fraction of GT anomalies uniquely matched to an engine result, regardless
        of whether the class is correct.

    classification_accuracy:
        correctly_detected / (correctly_detected + incorrectly_classified)
        Fraction of matched GT anomalies whose engine status is in the expected set.
        None when nothing was matched.

    exact_recall:
        correctly_detected / total_ground_truth_anomalies
        Fraction of GT anomalies that were both matched and correctly classified.

    false_positives:
        Engine exception results not used as a GT primary match and not explained
        as a documented downstream effect.

    missed_anomalies / false_negatives:
        GT anomalies with no unique engine-result match.
    """

    total_ground_truth_anomalies: int = 0
    correctly_detected: int = 0
    missed_anomalies: int = 0
    incorrectly_classified: int = 0
    false_positives: int = 0
    detection_rate: float = 0.0
    classification_accuracy: Optional[float] = None
    exact_recall: float = 0.0
    metric_definitions: dict[str, str] = Field(default_factory=dict)


class EvaluationReport(BaseModel):
    """JSON-serializable evaluation report."""

    seed: Optional[int] = None
    num_records: Optional[int] = None
    metrics: OverallMetrics
    by_type: list[TypeMetrics] = Field(default_factory=list)
    detected: list[AnomalyEvaluation] = Field(default_factory=list)
    missed: list[AnomalyEvaluation] = Field(default_factory=list)
    incorrectly_classified: list[AnomalyEvaluation] = Field(default_factory=list)
    false_positive_details: list[FalsePositive] = Field(default_factory=list)
    downstream_effects: list[DownstreamEffect] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
