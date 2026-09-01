"""Settlement reconciliation domain model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class SettlementEntityType(str, Enum):
    """Settlement entity type enum."""

    PAYMENT = "payment"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class SettlementRecord(BaseModel):
    """Represents a settlement reconciliation record.
    
    Settlement records link payments/refunds to settlement batches.
    All amounts are in integer paise.
    """

    entity_id: str = Field(..., description="Unique entity identifier")
    type: SettlementEntityType = Field(..., description="Entity type")
    payment_id: Optional[str] = Field(None, description="Related payment ID")
    order_id: Optional[str] = Field(None, description="Related order ID")
    settlement_id: str = Field(..., description="Settlement batch identifier")
    settlement_utr: str = Field(..., description="Settlement bank reference (UTR)")
    amount: int = Field(..., description="Transaction amount in paise", ge=0)
    debit: int = Field(0, description="Debit amount in paise", ge=0)
    credit: int = Field(0, description="Credit amount in paise", ge=0)
    fee: int = Field(0, description="Fee amount in paise", ge=0)
    tax: int = Field(0, description="Tax amount in paise", ge=0)
    settled_at: datetime = Field(..., description="Settlement timestamp")
    description: str = Field(..., description="Settlement description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "setl_A1B2C3D4E5F6",
                "type": "payment",
                "payment_id": "pay_A1B2C3D4E5F6",
                "order_id": "order_X1Y2Z3A4B5",
                "settlement_id": "batch_001",
                "settlement_utr": "UTR202401151234567",
                "amount": 150000,
                "debit": 0,
                "credit": 147000,
                "fee": 2700,
                "tax": 300,
                "settled_at": "2024-01-16T09:00:00",
                "description": "Payment settlement",
            }
        }
    )
