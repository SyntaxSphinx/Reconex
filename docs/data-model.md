# Reconex Data Model

This document describes the data model for Reconex Phase 1.

## Overview

Reconex works with three core datasets:

1. **Merchant Payments** - Payment transactions initiated by customers
2. **Settlement Reconciliation Records** - Settlement processing records linking payments to settlement batches
3. **Bank Transactions** - Merchant bank account transactions (credits/debits)

## Data Relationships

```
Payment
    |
    | (payment_id, order_id)
    v
Settlement Reconciliation Record
    |
    | (settlement_id, settlement_utr)
    v
Settlement Batch
    |
    | (settlement_utr matches utr)
    v
Bank Transaction
```

### Key Principles

- Multiple payments can belong to one settlement batch
- Multiple settlement records can share the same `settlement_id` (batch)
- A settlement batch typically corresponds to one bank credit transaction
- Settlement records link individual payments to their settlement batch via `settlement_utr`

## Dataset Specifications

### 1. Merchant Payments

Represents payment transactions captured by the merchant.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `payment_id` | string | Unique payment identifier | `pay_123456_000001` |
| `order_id` | string | Unique order identifier | `order_789012_000001` |
| `customer_id` | string | Unique customer identifier | `cust_345678_000042` |
| `amount` | integer | Payment amount in paise | `150000` (1,500 INR) |
| `currency` | string | Currency code | `INR` |
| `payment_date` | datetime | Payment timestamp (ISO 8601) | `2024-01-15T10:30:00` |
| `status` | enum | Payment status | `captured`, `pending`, `failed` |
| `refund_amount` | integer | Payment-side refund amount in paise | `0` |

**Notes:**
- Phase 1 primarily generates `captured` payments for settlement reconciliation
- All amounts are in integer paise (1 INR = 100 paise)
- Payment IDs and order IDs are unique across the dataset
- `refund_amount` is `0` unless a `REFUND_MISMATCH` anomaly is injected

### 2. Settlement Reconciliation Records

Links payments/refunds to settlement batches and tracks fees/taxes.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `entity_id` | string | Unique settlement entity identifier | `setl_123456_000001` |
| `type` | enum | Entity type | `payment`, `refund`, `adjustment` |
| `payment_id` | string (nullable) | Related payment ID | `pay_123456_000001` |
| `order_id` | string (nullable) | Related order ID | `order_789012_000001` |
| `settlement_id` | string | Settlement batch identifier | `batch_123456_000001` |
| `settlement_utr` | string | Settlement bank reference (UTR) | `UTR202401151234567` |
| `amount` | integer | Transaction gross amount in paise | `150000` |
| `debit` | integer | Debit amount in paise | `0` |
| `credit` | integer | Credit amount in paise | `147000` |
| `fee` | integer | Fee charged in paise | `2700` |
| `tax` | integer | Tax on fee in paise | `300` |
| `settled_at` | datetime | Settlement timestamp (ISO 8601) | `2024-01-16T09:00:00` |
| `description` | string | Settlement description | `Payment settlement for pay_123456_000001` |

**Notes:**
- `credit = amount - fee - tax` for normal payment settlements
- Multiple records can share the same `settlement_id` (part of same batch)
- `settlement_utr` is the link to bank transactions
- Phase 1 primarily generates `payment` type entities
- `REFUND_MISMATCH` adds a `refund` type row linked to an existing payment

### 3. Bank Transactions

Represents transactions in the merchant's bank account.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `bank_transaction_id` | string | Unique bank transaction identifier | `bank_txn_123456_000001` |
| `transaction_date` | datetime | Transaction timestamp (ISO 8601) | `2024-01-16T09:30:00` |
| `description` | string | Transaction description | `Settlement credit for batch_123456_000001` |
| `amount` | integer | Transaction amount in paise | `147000` |
| `transaction_type` | enum | Credit or debit | `credit`, `debit` |
| `utr` | string (nullable) | Unique Transaction Reference | `UTR202401151234567` |

**Notes:**
- `utr` matches `settlement_utr` in settlement records
- Phase 1 primarily generates `credit` transactions (settlement credits)
- Bank transaction amount should match the sum of `credit` fields in related settlement records

## Amount Calculation

For a payment settlement, all arithmetic is integer-only:

```
fee    = amount * 18 // 1000    # 1.8%
tax    = fee * 18 // 100        # 18% GST on fee
credit = amount - fee - tax
```

**Example:**
- Payment: 150,000 paise (1,500 INR)
- Fee: `150000 * 18 // 1000` = 2,700 paise
- Tax: `2700 * 18 // 100` = 486 paise
- Credit: 146,814 paise

**Important**: All calculations use integer arithmetic. No floating-point numbers.

## Assumptions

### Settlement Timing
- Settlements occur 1-2 days after payment capture
- Bank credit appears within hours after settlement processing

### Settlement Batching
- Default: ~50 payments per settlement batch
- Configurable via `GeneratorConfig.payments_per_settlement`

### Fee Structure
- Fee: `amount * 18 // 1000` (1.8%, configurable as integer numerator/denominator)
- Tax: `fee * 18 // 100` (18% GST on fee)
- These are simplified assumptions for hackathon purposes

### Anomaly Allocation
- Default rates are per 1,000 payment records: 5, 5, 10, 5, 5, 5 (3.5% total)
- Counts use integer ceiling: `(n * rate + 999) // 1000`
- Counts are capped by eligible records
- At least one bank transaction is left in place
- At least one remaining bank transaction is left unmodified when any banks exist

### Customer Distribution
- Synthetic customer IDs are reused across payments
- No real customer information is used

## Anomaly Types

Phase 1 implements 6 anomaly families:

| Anomaly Type | Description | Implementation |
|--------------|-------------|----------------|
| `MISSING_SETTLEMENT` | Payment captured but settlement record missing | Remove settlement record; leave related bank credit in place |
| `MISSING_BANK_CREDIT` | Settlement complete but bank credit missing | Remove bank transaction while preserving settlements |
| `AMOUNT_MISMATCH` | Bank transaction amount differs from expected | Modify bank amount by an integer 1–10% |
| `DUPLICATE` | Duplicate settlement records | Duplicate a settlement record with new entity_id |
| `REFUND_MISMATCH` | Payment refund disagrees with settlement refund | Set `payment.refund_amount` and add a `type=refund` settlement row with a different amount |
| `UNMATCHED_REFERENCE` | Corrupted UTR or matching identifier | Corrupt one settlement row's `settlement_utr` |

## Ground Truth Format

Ground truth is stored in JSON format for evaluation purposes:

```json
{
  "seed": 42,
  "num_records": 1000,
  "total_anomalies": 35,
  "anomalies": [
    {
      "anomaly_id": "anom_000001",
      "anomaly_type": "MISSING_SETTLEMENT",
      "affected_entity_id": "pay_123456_000042",
      "affected_entity_type": "payment",
      "expected_state": "Settlement record should exist",
      "actual_state": "Settlement record missing; related bank credit is unchanged",
      "variance": null,
      "related_ids": {
        "payment_id": "pay_123456_000042",
        "order_id": "order_789012_000042",
        "removed_entity_id": "setl_123456_000042",
        "settlement_id": "batch_123456_000000",
        "settlement_utr": "UTR202401151234567",
        "related_bank_transaction_id": "bank_txn_123456_000000",
        "removed_credit_paise": 146814
      },
      "description": "Payment captured but settlement record removed; bank credit still exists"
    }
  ]
}
```

## File Formats

### CSV Format

All CSV files use:
- UTF-8 encoding
- Header row with field names
- ISO 8601 datetime format
- Empty string for nullable fields

### JSON Format

Ground truth uses:
- UTF-8 encoding
- 2-space indentation
- no runtime timestamps (`seed` and `num_records` only)

## Data Integrity Constraints

### Clean Data (Before Anomaly Injection)

1. Every `captured` payment has exactly one settlement record
2. Every settlement record references a valid payment
3. Every settlement batch has exactly one bank credit
4. Bank credit amount equals sum of settlement credits in that batch
5. All IDs are unique within their entity type
6. All amounts are positive integers
7. Settlement dates are after payment dates
8. Bank transaction dates are at or after settlement dates

### After Anomaly Injection

Some of these constraints are intentionally violated to create evaluation scenarios.

## Reproducibility

- Data generation is deterministic when using the same seed
- Same seed produces byte-for-byte identical CSV and ground-truth files across processes
- Unique collections preserve first-seen list order; set iteration is not used as a sample source
- Anomaly injection uses `seed + 1000` to keep anomaly RNG independent of clean generation

## Limitations

This is a simplified model for hackathon purposes:

- Does not model all Razorpay settlement nuances
- Simplified fee structure (real fees vary by merchant, payment method, etc.)
- No support for international payments, currency conversion, etc.
- No support for failed settlements, reversals, chargebacks (yet)
- Bank transaction model is simplified (real bank statements vary significantly)

These limitations are acceptable for Phase 1. Future phases may add complexity as needed.
