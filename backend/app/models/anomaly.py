"""Anomaly types and ground truth models."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AnomalyType(str, Enum):
    """Types of anomalies that can be injected into synthetic data."""

    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    MISSING_BANK_CREDIT = "MISSING_BANK_CREDIT"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE = "DUPLICATE"
    REFUND_MISMATCH = "REFUND_MISMATCH"
    UNMATCHED_REFERENCE = "UNMATCHED_REFERENCE"


class AnomalyRecord(BaseModel):
    """Ground truth record describing an injected anomaly.
    
    This is used for evaluation purposes only.
    The application does not use ground truth during reconciliation.
    """

    anomaly_id: str = Field(..., description="Unique anomaly identifier")
    anomaly_type: AnomalyType = Field(..., description="Type of anomaly")
    affected_entity_id: str = Field(..., description="Primary affected record identifier")
    affected_entity_type: str = Field(..., description="Type of affected entity (payment, settlement, bank)")
    expected_state: str = Field(..., description="What should have been present")
    actual_state: str = Field(..., description="What is actually present")
    variance: Optional[int] = Field(None, description="Amount variance in paise, if applicable")
    related_ids: Dict[str, Any] = Field(default_factory=dict, description="Related record identifiers")
    description: str = Field(..., description="Human-readable description of the anomaly")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "anomaly_id": "anom_001",
                "anomaly_type": "MISSING_SETTLEMENT",
                "affected_entity_id": "pay_A1B2C3D4E5F6",
                "affected_entity_type": "payment",
                "expected_state": "settlement record should exist",
                "actual_state": "settlement record missing",
                "variance": None,
                "related_ids": {"payment_id": "pay_A1B2C3D4E5F6"},
                "description": "Payment captured but settlement record deleted",
            }
        }
    )
