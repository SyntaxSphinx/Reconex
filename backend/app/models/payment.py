"""Payment domain model."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class PaymentStatus(str, Enum):
    """Payment status enum."""

    CAPTURED = "captured"
    PENDING = "pending"
    FAILED = "failed"


class Payment(BaseModel):
    """Represents a merchant payment record.

    All amounts are in integer paise (1 INR = 100 paise).
    """

    payment_id: str = Field(..., description="Unique payment identifier")
    order_id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Unique customer identifier")
    amount: int = Field(..., description="Payment amount in paise", ge=0)
    currency: str = Field(..., description="Currency code")
    payment_date: datetime = Field(..., description="Payment timestamp")
    status: PaymentStatus = Field(..., description="Payment status")
    refund_amount: int = Field(0, description="Payment-side refund amount in paise", ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_id": "pay_A1B2C3D4E5F6",
                "order_id": "order_X1Y2Z3A4B5",
                "customer_id": "cust_M1N2O3P4Q5",
                "amount": 150000,
                "currency": "INR",
                "payment_date": "2024-01-15T10:30:00",
                "status": "captured",
                "refund_amount": 0,
            }
        }
    )
