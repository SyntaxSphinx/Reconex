"""Configuration for synthetic data generation."""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class AnomalyRates(BaseModel):
    """Anomaly rates per 1,000 payment records.

    Default rates produce 35 anomalies on a 1,000-record dataset (3.5%).
    Counts are derived with integer ceiling: (n * rate + 999) // 1000.
    """

    missing_settlement: int = Field(5, ge=0, description="MISSING_SETTLEMENT rate per 1000 records")
    missing_bank_credit: int = Field(5, ge=0, description="MISSING_BANK_CREDIT rate per 1000 records")
    amount_mismatch: int = Field(10, ge=0, description="AMOUNT_MISMATCH rate per 1000 records")
    duplicate: int = Field(5, ge=0, description="DUPLICATE rate per 1000 records")
    refund_mismatch: int = Field(5, ge=0, description="REFUND_MISMATCH rate per 1000 records")
    unmatched_reference: int = Field(5, ge=0, description="UNMATCHED_REFERENCE rate per 1000 records")


class AnomalyConfig(BaseModel):
    """Absolute anomaly counts after rate allocation and eligibility caps."""

    missing_settlement: int = Field(0, ge=0)
    missing_bank_credit: int = Field(0, ge=0)
    amount_mismatch: int = Field(0, ge=0)
    duplicate: int = Field(0, ge=0)
    refund_mismatch: int = Field(0, ge=0)
    unmatched_reference: int = Field(0, ge=0)

    @property
    def total_anomalies(self) -> int:
        """Calculate total number of planned anomalies."""
        return (
            self.missing_settlement
            + self.missing_bank_credit
            + self.amount_mismatch
            + self.duplicate
            + self.refund_mismatch
            + self.unmatched_reference
        )


def allocate_count(num_records: int, rate_per_thousand: int) -> int:
    """Ceiling of num_records * rate / 1000 using integer arithmetic only."""
    if num_records <= 0 or rate_per_thousand <= 0:
        return 0
    return (num_records * rate_per_thousand + 999) // 1000


def counts_from_rates(num_records: int, rates: AnomalyRates) -> AnomalyConfig:
    """Convert per-1000 rates into absolute counts for a dataset size."""
    return AnomalyConfig(
        missing_settlement=allocate_count(num_records, rates.missing_settlement),
        missing_bank_credit=allocate_count(num_records, rates.missing_bank_credit),
        amount_mismatch=allocate_count(num_records, rates.amount_mismatch),
        duplicate=allocate_count(num_records, rates.duplicate),
        refund_mismatch=allocate_count(num_records, rates.refund_mismatch),
        unmatched_reference=allocate_count(num_records, rates.unmatched_reference),
    )


def cap_anomaly_counts(
    counts: AnomalyConfig,
    *,
    payment_settlement_count: int,
    bank_count: int,
) -> AnomalyConfig:
    """Cap planned counts by eligible records.

    Always leave at least one bank transaction, and leave at least one
    bank transaction unmodified (neither removed nor amount-mismatched)
    when any banks exist.
    """
    missing_settlement = min(counts.missing_settlement, payment_settlement_count)

    max_missing_bank = max(0, bank_count - 1)
    missing_bank = min(counts.missing_bank_credit, max_missing_bank)

    remaining_banks = bank_count - missing_bank
    max_mismatch = max(0, remaining_banks - 1)
    amount_mismatch = min(counts.amount_mismatch, max_mismatch)

    return AnomalyConfig(
        missing_settlement=missing_settlement,
        missing_bank_credit=missing_bank,
        amount_mismatch=amount_mismatch,
        duplicate=min(counts.duplicate, payment_settlement_count),
        refund_mismatch=min(counts.refund_mismatch, payment_settlement_count),
        unmatched_reference=min(counts.unmatched_reference, payment_settlement_count),
    )


class GeneratorConfig(BaseModel):
    """Configuration for synthetic data generation."""

    num_records: int = Field(1000, description="Number of payment records to generate")
    seed: int = Field(42, description="Random seed for reproducibility")
    currency: str = Field("INR", description="Currency code")
    date_range_days: int = Field(30, description="Number of days to span")
    max_amount_paise: int = Field(1000000, description="Maximum payment amount in paise (10,000 INR)")
    fee_numerator: int = Field(18, description="Fee numerator (1.8% = 18/1000)")
    fee_denominator: int = Field(1000, description="Fee denominator")
    tax_numerator: int = Field(18, description="Tax numerator (18% = 18/100)")
    tax_denominator: int = Field(100, description="Tax denominator")
    payments_per_settlement: int = Field(50, description="Average payments per settlement batch")
    anomaly_rates: AnomalyRates = Field(
        default_factory=AnomalyRates,
        description="Rate-based anomaly allocation per 1000 records",
    )
    anomaly_config: Optional[AnomalyConfig] = Field(
        None,
        description="Optional absolute anomaly counts; overrides rates when set",
    )

    def calculate_fee(self, amount: int) -> int:
        """Fee in integer paise: amount * 18 / 1000 by default."""
        return amount * self.fee_numerator // self.fee_denominator

    def calculate_tax(self, fee: int) -> int:
        """Tax in integer paise: fee * 18 / 100 by default."""
        return fee * self.tax_numerator // self.tax_denominator

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "num_records": 1000,
                "seed": 42,
                "currency": "INR",
                "date_range_days": 30,
                "max_amount_paise": 1000000,
                "fee_numerator": 18,
                "fee_denominator": 1000,
                "tax_numerator": 18,
                "tax_denominator": 100,
                "payments_per_settlement": 50,
            }
        }
    )
