# Reconex — Deterministic Reconciliation Rules

**Project:** Reconex — AI Finance Controller  
**Phase:** 2A / 2B specification  
**Status:** Pre-implementation rules freeze  
**Version:** 0.1  

---

## 1. Purpose

This document defines the deterministic rules used by Reconex to reconcile three synthetic merchant-side data sources:

1. `payments.csv`
2. `settlement_recon.csv`
3. `bank_transactions.csv`

The purpose is to establish a reproducible financial truth layer before any AI investigation occurs.

The reconciliation engine must make decisions using only the supplied source data and these rules. It must never read or depend on `ground_truth.json`.

Razorpay's public documentation describes settlement reconciliation using transaction-level settlement records, settlement IDs and UTRs, and provides settlement information such as amount, fees, tax and status. These concepts inform the synthetic model used by Reconex; Reconex is not a reproduction of Razorpay's production ledger. [Razorpay Settlement Reconciliation API](https://razorpay.com/docs/api/settlements/fetch-recon/) [Razorpay Settlements Entity](https://razorpay.com/docs/api/settlements/entity/)

---

## 2. Scope

### Included

- deterministic input validation;
- safe normalization;
- payment-to-settlement reconciliation;
- settlement-batch aggregation;
- settlement-to-bank reconciliation;
- refund reconciliation;
- duplicate detection;
- pending-state handling;
- exception classification;
- structured evidence for every result;
- run-level summary metrics.

### Excluded from this phase

- LLM/AI investigation;
- machine learning;
- fuzzy/probabilistic matching;
- live Razorpay API calls;
- MCP;
- frontend behavior;
- autonomous financial changes;
- actual movement of money.

---

## 3. Financial Model

The synthetic flow is:

```text
Merchant payment
      ↓
Razorpay-style settlement records
      ↓
Settlement batch
      ↓
Merchant bank credit
```

A settlement is a batch-level movement of funds. Multiple settlement transaction lines may belong to one `settlement_id`. Razorpay's settlement reconciliation API associates transaction lines with a settlement and exposes `settlement_utr` for the bank reference. [Razorpay API](https://razorpay.com/docs/api/settlements/fetch-recon/)

Reconex uses integer paise for every monetary value.

---

## 4. Source Records

### 4.1 Payment

The merchant-side financial event.

Key identifiers:

- `payment_id`
- `order_id`

Primary monetary field:

- `amount`

Relevant state:

- `captured`
- `pending`
- `failed`
- `refunded`

Synthetic-only field:

- `refund_amount`

### 4.2 Settlement reconciliation line

A transaction-level entry inside a settlement batch.

Key fields:

- `entity_id`
- `type`
- `payment_id`
- `order_id`
- `settlement_id`
- `settlement_utr`
- `amount`
- `credit`
- `debit`
- `fee`
- `tax`
- `settled_at`

The `type` is one of:

- `payment`
- `refund`
- `adjustment`

Razorpay's documented reconciliation API also supports `transfer`; Reconex does not model transfers in this MVP because they are outside the merchant-payment reconciliation loop we are implementing. [Razorpay API](https://razorpay.com/docs/api/settlements/fetch-recon/)

### 4.3 Bank transaction

The merchant-side external bank record.

Key fields:

- `bank_transaction_id`
- `transaction_date`
- `amount`
- `transaction_type`
- `utr`

For settlement credits, `utr` is the primary bank-side reference.

Razorpay documents UTR as the bank-traceable reference for a settlement and recommends using it to reconcile settlement funds against the bank statement. [Razorpay FAQ](https://razorpay.com/docs/payments/settlements/faqs/) [Razorpay Webhooks](https://razorpay.com/docs/webhooks/settlements/)

---

## 5. Normalization Rules

Normalization must never change the underlying financial meaning.

Allowed normalization:

- trim leading/trailing whitespace from identifiers;
- parse supported date/time representations into a canonical internal datetime;
- parse monetary fields into integer paise;
- normalize enum values to their documented canonical representation.

Not allowed:

- fuzzy identifier correction;
- replacing missing IDs with guessed IDs;
- changing amounts to force a match;
- choosing between conflicting records arbitrarily.

Malformed input must produce a structured validation error rather than being silently discarded.

---

## 6. Settlement Grouping

All settlement lines with the same `settlement_id` belong to the same settlement batch.

For each batch, calculate:

- `total_credit = sum(credit)`
- `total_debit = sum(debit)`
- `net_settlement = total_credit - total_debit`
- total `fee`
- total `tax`
- number of lines
- unique `settlement_utr` values

### UTR consistency

A clean synthetic settlement batch is expected to have one UTR.

If a batch contains multiple distinct non-null UTRs:

```text
UNKNOWN / conflicting settlement metadata
```

The engine must not silently choose one UTR.

### Important arithmetic rule

`credit` and `debit` are already the transaction-level movement representation. Do not subtract `fee`, `tax`, refunds or adjustments a second time when calculating `net_settlement`.

Fees, tax, refunds and adjustments remain available as diagnostic components.

---

## 7. Payment ↔ Settlement Matching

The engine should determine whether each captured payment has an appropriate settlement-side representation.

### Rule 7.1 — Exact payment ID

If a settlement line has a non-null `payment_id` and exactly one payment record has that `payment_id`, this is the strongest payment-level identifier.

For a `payment` settlement line, Razorpay documentation notes that `payment_id` may be null; therefore absence of `payment_id` must not automatically be treated as an error. [Razorpay API](https://razorpay.com/docs/api/settlements/fetch-recon/)

### Rule 7.2 — Exact order ID

If `payment_id` is unavailable, an exact `order_id` relationship may be used when it identifies one unambiguous payment.

### Rule 7.3 — Ambiguous relationship

If multiple candidate payments share the same usable identifier and the engine cannot distinguish them deterministically:

```text
UNMATCHED_REFERENCE
```

The engine must not guess.

### Rule 7.4 — No amount-only reconciliation

Matching based only on amount is never sufficient to mark a payment as reconciled.

Amount may be used as supporting evidence after a relationship has been established.

### Rule 7.5 — No fuzzy matching in Phase 2B

Approximate string similarity and probabilistic candidate matching are outside this phase.

---

## 8. Payment Amount Consistency

For a clean payment settlement relationship:

```text
settlement payment amount == payment.amount
```

subject to the synthetic model's explicit refund/adjustment representation.

A disagreement that cannot be explained by the corresponding refund/adjustment structure becomes an `AMOUNT_MISMATCH` or `REFUND_MISMATCH`, depending on the cause.

Do not modify either source value.

---

## 9. Refund Reconciliation

Refunds are represented as `type = refund` settlement lines.

For a clean synthetic case:

```text
payment.refund_amount
    ==
absolute total of linked settlement refund debit
```

The exact linkage uses available `payment_id` and/or `order_id` references.

### Refund mismatch

If the payment-side refund amount and settlement-side refund amount disagree:

```text
REFUND_MISMATCH
```

The result must record:

- payment ID;
- order ID;
- settlement ID;
- expected refund amount;
- observed refund amount;
- variance;
- affected settlement line IDs.

The engine must not alter the refund values to make them agree.

---

## 10. Settlement ↔ Bank Matching

For each settlement batch, use its `settlement_utr` to locate the corresponding bank credit.

### Rule 10.1 — One exact UTR match

If exactly one bank transaction has:

```text
bank.utr == settlement.settlement_utr
```

and the transaction is a credit:

continue to amount validation.

### Rule 10.2 — No bank match

If no bank transaction has the settlement UTR:

- determine whether the settlement is still within the synthetic bank-credit window;
- if yes → `PENDING_BANK_CREDIT`;
- if no → `MISSING_BANK_CREDIT`.

### Rule 10.3 — Multiple bank matches

If multiple bank credits have the same settlement UTR:

```text
UNKNOWN
```

with a conflict reason.

Do not pick one arbitrarily.

### Rule 10.4 — Wrong transaction direction

A matching UTR on a bank debit does not satisfy the required settlement credit relationship.

Treat as a bank reconciliation exception.

---

## 11. Settlement Amount ↔ Bank Amount

Once an unambiguous bank transaction has been identified, compare:

```text
settlement.net_settlement
vs
bank.credit_amount
```

Default tolerance:

```text
0 paise
```

If the values are equal:

```text
bank leg reconciled
```

If they differ by more than tolerance:

```text
AMOUNT_MISMATCH
```

The result must include:

- settlement ID;
- settlement UTR;
- expected settlement amount;
- bank transaction ID;
- observed bank amount;
- signed variance;
- absolute variance.

Do not use a tolerance merely to make synthetic noise disappear.

This comparison is a **batch-level** result. It must not be copied onto every payment that belongs to the batch.

---

## 12. Pending Settlement

A payment without a settlement record is not immediately considered missing.

The engine must use the synthetic settlement-timing assumption already defined by the Phase 1 generator.

### Within expected settlement window

```text
PENDING_SETTLEMENT
```

No escalation.

### Beyond expected settlement window

```text
MISSING_SETTLEMENT
```

Human review is required.

The timing rule is a **project simulation assumption**, not a claim that every Razorpay merchant uses the same settlement cycle. Razorpay documents that settlement cycles can vary by account/business configuration and currently describes standard cycles in its settlement documentation. [Razorpay Settlements](https://razorpay.com/docs/payments/settlements/) [Razorpay FAQ](https://razorpay.com/docs/payments/settlements/faqs/)

---

## 13. Pending Bank Credit

A settlement may have been processed while the corresponding bank credit has not yet appeared in the bank statement.

Razorpay explicitly notes that `settlement.processed` indicates the transfer has been initiated and does not necessarily mean the funds are already reflected in the bank account; UTR can be used to reconcile the settlement with the bank statement. [Razorpay Webhooks](https://razorpay.com/docs/webhooks/settlements/)

Therefore Reconex distinguishes:

### Within synthetic bank-credit window

```text
PENDING_BANK_CREDIT
```

### Beyond synthetic bank-credit window

```text
MISSING_BANK_CREDIT
```

The bank-credit timing window is a project simulation parameter, not a production Razorpay SLA.

---

## 14. Duplicate Detection

The engine must detect duplicate financial events without treating legitimate refunds as duplicates.

A potential duplicate requires multiple records that represent the same event according to a deterministic identity key.

Strong signals include:

- identical `payment_id`;
- identical `order_id`;
- same `settlement_id`;
- same transaction type;
- same amount;
- same relevant timestamp/reference.

A payment line and its legitimate refund line are **not** duplicates merely because they share a payment/order reference.

When a duplicate is established:

```text
DUPLICATE
```

The result must include all involved entity IDs and the identity rule that caused the classification.

---

## 15. Unmatched Reference

If a settlement line contains a corrupted or otherwise unusable reference and no deterministic relationship can be established:

```text
UNMATCHED_REFERENCE
```

The engine must not replace it with a fuzzy match.

Candidate records may be surfaced as evidence for later AI investigation, but a candidate is not a reconciliation.

---

## 16. Final Result Precedence

A single financial case may exhibit multiple symptoms. The engine needs a deterministic precedence so results are stable.

Use the following order when deciding the primary status:

```text
1. UNKNOWN / conflicting metadata
2. UNMATCHED_REFERENCE
3. DUPLICATE
4. REFUND_MISMATCH
5. AMOUNT_MISMATCH
6. MISSING_SETTLEMENT
7. PENDING_SETTLEMENT
8. MISSING_BANK_CREDIT
9. PENDING_BANK_CREDIT
10. RECONCILED
```

This is the **primary-status precedence**, not permission to discard secondary evidence.

The result should retain secondary findings where useful.

Example:

```text
Primary status: AMOUNT_MISMATCH
Secondary finding: REFUND_MISMATCH
```

The implementation should avoid producing contradictory primary statuses for the same case.

---

## 17. Auto-Reconciled vs Auto-Resolved

### AUTO_RECONCILED

Use when deterministic rules prove that the records agree.

Example:

```text
payment identified
↓
settlement identified
↓
settlement batch consistent
↓
UTR matches exactly one bank credit
↓
settlement net == bank credit
↓
AUTO_RECONCILED
```

### AUTO_RESOLVED

Use only when a predefined deterministic rule safely explains a discrepancy.

Phase 2B should keep the number of such rules intentionally small.

The engine must never use an LLM or confidence score to turn an uncertain case into `AUTO_RESOLVED`.

### Human review

Cases requiring judgment remain unresolved and are represented for later investigation.

---

## 18. Structured Evidence

Every result must retain enough evidence to answer:

> "Why did Reconex classify this record this way?"

Evidence should include, when applicable:

- payment ID;
- order ID;
- settlement ID;
- settlement line IDs;
- settlement UTR;
- bank transaction ID;
- payment amount;
- settlement amount/credit/debit;
- bank amount;
- calculated variance;
- relevant timestamps;
- rule ID/name that fired.

Evidence must reference source records rather than generated prose.

---

## 19. Error and Failure Behavior

The engine must fail safely.

### Invalid input

Return structured validation errors.

### Missing required column

Reject the affected input source.

### Missing optional identifier

Continue if another documented relationship is sufficient.

### Ambiguous match

Do not guess. Return `UNMATCHED_REFERENCE` or `UNKNOWN` according to the specific rule.

### Conflicting metadata

Do not choose arbitrarily. Return `UNKNOWN` with evidence.

### Unsupported scenario

Return an explicit unresolved result rather than pretending reconciliation succeeded.

---

## 20. Run-Level Outputs

Every reconciliation run must report:

- payments processed;
- settlement lines processed;
- settlement batches processed;
- bank transactions processed;
- reconciled count;
- pending count;
- exception count;
- count by primary status;
- total expected settlement value;
- total matched bank value;
- total absolute variance;
- processing duration.

These metrics describe system behavior. They are not ground-truth accuracy metrics; those belong to Phase 2C.

### Result granularity

The engine emits two result lists:

1. **Payment-level** — one result per payment. This covers payment ↔ settlement line conditions only: missing/pending settlement, duplicate settlement lines, payment-amount vs settlement-line amount, refund mismatch, and an unusable identifier on that payment's own settlement line.
2. **Batch-level** — one result per `settlement_id`. This covers settlement batch ↔ bank credit: UTR consistency, missing/pending bank credit, ambiguous bank matches, wrong transaction direction, and `net_settlement` vs bank amount.

A batch-level `AMOUNT_MISMATCH` (`batch.net_settlement != bank.amount`) is recorded once for that batch. Payments whose payment ↔ settlement relationship is valid remain `RECONCILED` at payment level.

---

## 21. Phase 2B Non-Goals

Do not implement in this phase:

- fuzzy matching;
- probabilistic matching;
- anomaly prediction;
- LLM explanation;
- AI classification;
- natural-language queries;
- human-review UI;
- automatic changes to the financial source data.

These are intentionally deferred so that the deterministic baseline can be evaluated independently.

---

## 22. Phase 2B Acceptance Criteria

Phase 2B is complete only when:

1. The engine processes all three Phase 1 source datasets.
2. The engine makes deterministic decisions without reading ground truth.
3. All defined statuses are covered by tests.
4. The clean benchmark dataset reconciles without unexplained discrepancies.
5. Each Phase 1 injected anomaly category produces the expected primary status where applicable.
6. Ambiguous cases are not auto-resolved.
7. Monetary calculations use integer paise.
8. The engine emits structured evidence for every decision.
9. The full test suite passes.
10. The engine can be called programmatically for later Phase 2C evaluation.

---

## 23. Design Principle

```text
Financial truth
      ↓
Deterministic rules
      ↓
Reconciliation result
      ↓
Evidence
      ↓
Later AI investigation
```

**The deterministic layer establishes what happened. The AI layer will later help explain what it means and what should happen next.**
