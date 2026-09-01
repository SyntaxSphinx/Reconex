"""Bank transaction domain model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TransactionType(str, Enum):
    """Bank transaction type enum."""

    CREDIT = "credit"
    DEBIT = "debit"


class BankTransaction(BaseModel):
    """Represents a merchant bank account transaction.
    
    All amounts are in integer paise.
    """

    bank_transaction_id: str = Field(..., description="Unique bank transaction identifier")
    transaction_date: datetime = Field(..., description="Transaction timestamp")
    description: str = Field(..., description="Transaction description")
    amount: int = Field(..., description="Transaction amount in paise", ge=0)
    transaction_type: TransactionType = Field(..., description="Credit or debit")
    utr: Optional[str] = Field(None, description="Unique Transaction Reference (UTR)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bank_transaction_id": "bank_txn_A1B2C3D4",
                "transaction_date": "2024-01-16T09:30:00",
                "description": "Settlement credit",
                "amount": 147000,
                "transaction_type": "credit",
                "utr": "UTR202401151234567",
            }
        }
    )
