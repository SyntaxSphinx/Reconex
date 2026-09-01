# PHASE 2B AUDIT REPORT — INVESTIGATION COMPLETE

**DO NOT COMMIT THIS FILE**

---

## EXECUTIVE SUMMARY

**CRITICAL BUG CONFIRMED**: The reconciliation engine compares **individual payment amounts** against **entire settlement batch bank amounts**. This is architecturally incorrect and explains why 537 payments (53.7%) show AMOUNT_MISMATCH.

The engine operates at payment-level granularity but performs batch-level comparisons, causing every payment in a batch with a bank amount mismatch to report the same batch-level variance.

---

## 1. PAYMENT-LEVEL VS BATCH-LEVEL RECONCILIATION ❌

### Code Path

```
Payment (individual)
  → Settlement line (individual) via payment_id
  → Settlement batch (aggregated)  via settlement_id
  → Bank transaction (batch-level) via settlement_utr
```

### The Bug

**Lines 340-349 in `engine.py`:**

```python
# Check amount (Rule 11)
if bank_txn.amount != batch.net_settlement_paise:
    variance = bank_txn.amount - batch.net_settlement_paise
    # Only set variance if not already set...
    if evidence.variance_paise is None:
        evidence.expected_amount_paise = batch.net_settlement_paise  # ← BATCH
        evidence.actual_amount_paise = bank_txn.amount              # ← BATCH
        evidence.variance_paise = variance                          # ← BATCH
        evidence.abs_variance_paise = abs(variance)
    findings.append(ReconciliationStatus.AMOUNT_MISMATCH)
```

**The engine compares:**
- `batch.net_settlement_paise` (sum of ~50 payments)
- vs `bank_txn.amount` (sum of ~50 settlement credits)

**Then assigns this batch-level mismatch to EVERY payment in the batch.**

### Evidence: Batch batch_706658_000000

- **Payment rows**: 51
- **Actual payments**: 50
- **Batch net**: 11,549,272 paise
- **Bank amount**: 11,780,591 paise
- **Batch variance**: 231,319 paise

**Result**: All 50+ payments in this batch report identical variance of 231,319 paise:

```
pay_216739_000000: Expected 11,549,272, Actual 11,780,591, Variance 231,319
pay_246316_000001: Expected 11,549,272, Actual 11,780,591, Variance 231,319
pay_671858_000002: Expected 11,549,272, Actual 11,780,591, Variance 231,319
...
```

But `pay_216739_000000` is only 42,098 paise (0.4% of batch).
It should not be compared against 11 million paise.

### All 20 Batches

| Batch | Payments | Batch Net (paise) | Bank (paise) | Comparison | Payments Affected |
|-------|----------|-------------------|--------------|------------|-------------------|
| batch_240829_000008 | 50 | 11,136,089 | 10,072,162 | MISMATCH | ~50 |
| batch_303974_000016 | 50 | 10,409,348 | N/A | NO BANK | ~50 |
| batch_366881_000013 | 50 | 10,571,775 | 10,254,622 | MISMATCH | ~50 |
| batch_421549_000014 | 50 | 11,281,473 | 12,000,499 | MISMATCH | ~50 |
| batch_430738_000018 | 50 | 12,696,209 | N/A | NO BANK | ~50 |
| batch_446620_000003 | 50 | 12,225,070 | 12,225,070 | MATCH | 50 reconciled ✓ |
| batch_462814_000004 | 50 | 9,797,475 | N/A | NO BANK | ~50 |
| batch_469348_000001 | 49 | 9,570,112 | 10,495,002 | MISMATCH | ~49 |
| batch_544536_000019 | 49 | 13,722,828 | 13,051,504 | MISMATCH | ~49 |
| batch_625465_000009 | 50 | 14,478,545 | N/A | NO BANK | 0 (UNKNOWN wins) |
| batch_670792_000010 | 50 | 14,158,210 | N/A | NO BANK | 50 |
| batch_706658_000000 | 50 | 11,549,272 | 11,780,591 | MISMATCH | ~50 |
| batch_719284_000012 | 50 | 12,717,869 | N/A | NO BANK | 50 |
| batch_803571_000007 | 49 | 11,673,856 | 13,753,314 | MISMATCH | ~49 |
| batch_819368_000005 | 49 | 11,008,857 | 10,208,725 | MISMATCH | ~49 |
| batch_922405_000002 | 49 | 13,986,756 | 15,191,853 | MISMATCH | ~49 |
| batch_960072_000015 | 50 | 11,272,097 | N/A | NO BANK | 0 (UNKNOWN wins) |
| batch_962057_000006 | 50 | 13,187,688 | 13,187,688 | MATCH | 50 reconciled ✓ |
| batch_972600_000017 | 50 | 14,410,849 | 13,853,258 | MISMATCH | ~50 |
| batch_973846_000011 | 50 | 14,663,756 | 13,836,898 | MISMATCH | ~50 |

**Analysis:**
- Only 2 batches match perfectly → 100 reconciled payments
- 10 batches with AMOUNT_MISMATCH → ~500 payments marked with batch-level mismatch
- 5 batches with NO BANK → 150 MISSING_BANK_CREDIT
- 4 batches with conflicting UTRs → 199 UNKNOWN
- 5 payments with DUPLICATE
- 5 payments with MISSING_SETTLEMENT

Total: 537 AMOUNT_MISMATCH is explained by ~11 batch-level mismatches * ~50 payments each.

---

## 2. RECONCILIATION RESULT GRANULARITY ✓

**Confirmed from code (lines 378-390):**

```python
def reconcile(self) -> tuple[list[ReconciliationResult], ReconciliationSummary]:
    ...
    for payment in self.data.payments:
        result = self._reconcile_payment(payment, batches)
        results.append(result)
```

**One `ReconciliationResult` represents ONE PAYMENT.**

- Result count: 1000
- Payment count: 1000
- 1:1 relationship ✓

### Batch Exception Propagation

When a batch-level issue exists (e.g., MISSING_BANK_CREDIT), **every payment** in that batch receives that status (or higher precedence).

Example: `batch_670792_000010` has no bank transaction.
- Affected payments: 50
- Results with MISSING_BANK_CREDIT: 50

This is correct behavior IF the reconciliation is batch-level.
But the architecture claims to be payment-level.

**Problem**: The granularity mismatch creates false positives. A single payment cannot be independently reconciled when the bank comparison is batch-level.

---

## 3. MISSING BANK CREDIT ⚠️

### Ground Truth vs Results

| Settlement ID | GT Anomaly | Payments | Bank Exists | Results w/ MISSING_BANK_CREDIT |
|---------------|------------|----------|-------------|-------------------------------|
| batch_670792_000010 | YES | 50 | NO | 50 |
| batch_625465_000009 | YES | 50 | NO | **0** |
| batch_960072_000015 | YES | 50 | NO | **0** |
| batch_719284_000012 | YES | 50 | NO | 50 |
| batch_430738_000018 | YES | 50 | NO | 50 |

**Total**: 150 MISSING_BANK_CREDIT results (should be ~250)

### Why Only 150?

**Status precedence wins:**
- `batch_625465_000009`: Has UNMATCHED_REFERENCE (corrupted UTR) → UNKNOWN wins (priority 1) over MISSING_BANK_CREDIT (priority 8)
- `batch_960072_000015`: Has UNMATCHED_REFERENCE (corrupted UTR) → UNKNOWN wins

**This is correct precedence behavior.**

The issue is that ground truth has 5 MISSING_BANK_CREDIT anomalies, but 2 of those batches ALSO have UNMATCHED_REFERENCE anomalies, which take precedence.

From a reconciliation standpoint, "the UTRs don't match" is more severe than "the bank credit is missing" — you can't even determine which bank credit to look for.

**Conclusion**: 150 is correct given precedence. The apparent discrepancy is ground truth mixing anomaly types in the same batch.

---

## 4. AMOUNT MISMATCH ❌

**Total:** 537 results

**Root cause:** Payment-level results showing batch-level variance.

### Sample 10 Examples (ALL FROM SAME BATCH)

All 10 examples show identical variance because they're all in `batch_706658_000000`:

| Payment ID | Payment Amount | Batch Net | Bank Amount | Variance | 
|------------|----------------|-----------|-------------|----------|
| pay_216739_000000 | 42,098 | 11,549,272 | 11,780,591 | 231,319 |
| pay_246316_000001 | 888,323 | 11,549,272 | 11,780,591 | 231,319 |
| pay_671858_000002 | 116,663 | 11,549,272 | 11,780,591 | 231,319 |
| pay_198246_000003 | 415,631 | 11,549,272 | 11,780,591 | 231,319 |
| pay_688508_000004 | 467,696 | 11,549,272 | 11,780,591 | 231,319 |
| pay_539898_000005 | 245,852 | 11,549,272 | 11,780,591 | 231,319 |
| pay_106814_000006 | 65,392 | 11,549,272 | 11,780,591 | 231,319 |
| pay_391369_000007 | 676,472 | 11,549,272 | 11,780,591 | 231,319 |
| pay_197251_000008 | 55,082 | 11,549,272 | 11,780,591 | 231,319 |
| pay_377370_000009 | 740,870 | 11,549,272 | 11,780,591 | 231,319 |

**Every payment is showing the BATCH-level comparison.**

The rule should be comparing payment amount vs settlement line amount (already done on line 232), NOT payment vs entire batch bank amount.

---

## 5. UNKNOWN ✓

**Total:** 199 results

**Single cause:** Conflicting UTRs in settlement batch

| Batch | Conflict Reason | Count |
|-------|----------------|-------|
| batch_462814_000004 | Multiple UTRs: ['UTR202401098473671', 'UTR202401098477055', 'UTR202401098470744'] | 50 |
| batch_625465_000009 | Multiple UTRs: ['UTR202401179567820', 'UTR202401179563292'] | 50 |
| batch_960072_000015 | Multiple UTRs: ['UTR202401263942647', 'UTR202401263940561'] | 50 |
| batch_303974_000016 | Multiple UTRs: ['UTR202401278629590', 'UTR202401278624053'] | 49 |

**Root cause:** Ground truth UNMATCHED_REFERENCE anomalies corrupt individual settlement line UTRs. When a batch has mixed valid and corrupted UTRs, the engine correctly detects conflicting metadata.

**Analysis:**
- Ground truth has 5 UNMATCHED_REFERENCE anomalies
- These corrupt 1 settlement line per batch
- But the batch still has 49-50 OTHER settlement lines with correct UTRs
- Engine sees multiple distinct UTRs → flags as UNKNOWN

**This is CORRECT behavior per Rule 6:**
> "If a batch contains multiple distinct non-null UTRs: UNKNOWN / conflicting settlement metadata. The engine must not silently choose one UTR."

**Conclusion:** All 199 UNKNOWN results are legitimate detections of batch inconsistency caused by synthetic anomalies.

---

## 6. REFUND MISMATCH ⚠️

### Ground Truth: 5 anomalies
### Reconciliation Results: 4

| Payment ID | GT Expected | GT Actual | Settlement ID | Result Status | Why |
|------------|-------------|-----------|---------------|---------------|-----|
| pay_695403_000777 | 82,578 | 65,237 | batch_960072_000015 | **UNKNOWN** | Conflicting UTRs (priority 1) wins over REFUND_MISMATCH (priority 4) |
| pay_801474_000047 | 38,954 | 32,722 | batch_706658_000000 | REFUND_MISMATCH ✓ | Correctly detected |
| pay_446305_000568 | 100,147 | 84,124 | batch_973846_000011 | REFUND_MISMATCH ✓ | Correctly detected |
| pay_548580_000712 | 34,270 | 39,753 | batch_421549_000014 | REFUND_MISMATCH ✓ | Correctly detected |
| pay_947732_000864 | 24,232 | 19,628 | batch_972600_000017 | REFUND_MISMATCH ✓ | Correctly detected |

**Why only 4?**

`pay_695403_000777` is in `batch_960072_000015`, which has conflicting UTRs due to UNMATCHED_REFERENCE anomaly on a different payment.

**Status precedence:**
- UNKNOWN (priority 1) beats REFUND_MISMATCH (priority 4)

**This is correct precedence behavior.**

All 4 other REFUND_MISMATCH cases are correctly detected with AMOUNT_MISMATCH as secondary finding (correct precedence: 4 < 5).

**Conclusion:** The missing 1 is due to precedence, not a detection bug.

---

## 7. STATUS PRECEDENCE ✓

### Actual Precedence (from code)

```
1. UNKNOWN
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

### Comparison to Spec (reconciliation-rules.md, Rule 16)

**Spec says:**
```
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

**MATCH ✓** — Implementation matches specification exactly.

### Examples with Multiple Findings

All 4 cases show REFUND_MISMATCH (priority 4) with AMOUNT_MISMATCH (priority 5) secondary:

```
pay_801474_000047:  REFUND_MISMATCH (4) > AMOUNT_MISMATCH (5) ✓
pay_446305_000568:  REFUND_MISMATCH (4) > AMOUNT_MISMATCH (5) ✓
pay_548580_000712:  REFUND_MISMATCH (4) > AMOUNT_MISMATCH (5) ✓
pay_947732_000864:  REFUND_MISMATCH (4) > AMOUNT_MISMATCH (5) ✓
```

**Precedence is correctly applied throughout.**

---

## 8. CLEAN BASELINE ✓

### Clean Dataset (seed 42, no anomalies)

- Payments: 1000
- Settlement lines: 1000
- Settlement batches: 20
- Bank transactions: 20

### Reconciliation Results

```
Reconciled:    1000 (100.0%)
Pending:       0
Exceptions:    0
```

**PERFECT RECONCILIATION ✓**

**Conclusion:** The engine correctly reconciles clean data. All exceptions in the anomaly dataset are due to:
1. Legitimate synthetic anomalies (199 UNKNOWN, 5 DUPLICATE, 5 MISSING_SETTLEMENT)
2. The batch-level comparison bug (537 AMOUNT_MISMATCH)
3. Batch-level exception propagation (150 MISSING_BANK_CREDIT)

---

## 9. GROUND TRUTH INDEPENDENCE ✓

**Confirmed:** No references to `ground_truth.json` in any reconciliation code.

```bash
$ grep -r "ground_truth" backend/app/reconciliation/
(no results)
```

Engine reads only:
- `payments.csv`
- `settlement_recon.csv`
- `bank_transactions.csv`

---

## 10. FINAL DIAGNOSIS

### A. CONFIRMED BUGS

**BUG #1: Payment-level results with batch-level bank comparison**

**Location:** `engine.py`, lines 340-349

**Problem:**
```python
if bank_txn.amount != batch.net_settlement_paise:
    variance = bank_txn.amount - batch.net_settlement_paise
    ...
    evidence.expected_amount_paise = batch.net_settlement_paise  # ← WRONG
    evidence.actual_amount_paise = bank_txn.amount              # ← WRONG
```

The engine compares the entire settlement batch net against the bank transaction, then assigns that batch-level variance to EVERY individual payment in the batch.

**Impact:**
- 537 payments flagged with AMOUNT_MISMATCH
- All share batch-level variance (e.g., 50 payments all show 231,319 paise variance)
- Makes payment-level reconciliation meaningless

**Correct behavior:**
- Payment amount vs settlement line amount: ✓ Already done (line 232)
- Batch net vs bank amount: Should be batch-level validation only
- Payment result should reflect payment-level match, NOT batch-level

---

### B. SUSPECTED BUGS

None. Other apparent issues are correct behavior given precedence rules.

---

### C. CORRECT BEHAVIOR

1. **Status precedence** ✓ — Matches spec exactly
2. **UNKNOWN for conflicting UTRs** ✓ — Correct detection per Rule 6
3. **REFUND_MISMATCH detection** ✓ — 4/5 detected (5th overridden by precedence)
4. **Clean data reconciliation** ✓ — 100% reconciled
5. **MISSING_BANK_CREDIT propagation** ✓ — All payments in affected batches correctly flagged
6. **No ground truth dependency** ✓ — Engine is independent

---

### D. MINIMAL CHANGES REQUIRED

**OPTION 1: Separate payment-level and batch-level reconciliation**

Make two result types:
- `PaymentReconciliationResult` — payment vs settlement line only
- `BatchReconciliationResult` — batch net vs bank transaction

Keep them independent. Do NOT propagate batch-level mismatches to individual payments.

**OPTION 2: Remove bank comparison from payment results**

Lines 340-349: Delete the bank amount comparison logic from `_reconcile_payment()`.

Add batch-level validation as a separate post-process:
- After all payments reconciled
- Validate each batch net vs bank transaction
- Report batch-level mismatches separately

**OPTION 3: Document current behavior as "batch-aware payment reconciliation"**

If the current behavior is intentional (every payment in a batch inherits batch-level status), document it clearly:

> "Payment reconciliation is batch-aware. When a batch-level exception exists (e.g., bank amount mismatch), all payments in that batch are marked with the batch-level status to ensure no payment is considered reconciled when the batch itself has unresolved issues."

Then rename statuses to clarify:
- `AMOUNT_MISMATCH` → `BATCH_AMOUNT_MISMATCH` (when it's batch-level)
- `AMOUNT_MISMATCH` → `PAYMENT_AMOUNT_MISMATCH` (when it's payment vs settlement line)

---

### RECOMMENDED FIX

**OPTION 2** is cleanest:

1. Remove lines 340-349 from `_reconcile_payment()`
2. Payment reconciliation ends at: "Does my settlement line exist and match my payment?"
3. Add separate batch validation:
   ```python
   def validate_batch(self, batch: SettlementBatch, bank_txn: BankTransaction) -> bool:
       return bank_txn.amount == batch.net_settlement_paise
   ```
4. Report batch-level issues in summary or separate batch results

This maintains payment-level granularity while still detecting batch-level problems.

---

## INVESTIGATION COMPLETE

**DO NOT modify files.**
**DO NOT implement fixes.**
**DO NOT commit changes.**

This report provides precise diagnosis for implementation in a future phase.

