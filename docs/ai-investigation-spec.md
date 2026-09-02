# Reconex — AI Investigation Specification

## 1. Purpose

This document defines the role and boundaries of the AI Investigation Layer in Reconex.

The deterministic reconciliation engine remains the financial source of truth.

AI is introduced only after deterministic reconciliation has identified an exception that requires investigation.

The AI investigator does not replace deterministic reconciliation and does not directly modify financial records.

## 2. Phase 3 Objective

The AI layer should help a finance operator answer:

> Why did the deterministic reconciliation engine flag this exception, what evidence supports the likely cause, and what should I do next?

The AI should reduce investigation effort while remaining conservative.

Workflow:

```text
Source data
    ↓
Deterministic reconciliation
    ↓
Exception
    ↓
AI investigation
    ↓
Evidence + explanation + confidence + recommendation
    ↓
Human review / deterministic resolution
```

## 3. AI Responsibilities

AI MAY:
- investigate eligible reconciliation exceptions
- synthesize supplied payment, settlement and bank evidence
- identify plausible root causes
- explain discrepancies
- identify supporting and contradictory evidence
- recommend the next operational action
- assign a confidence score
- explicitly state when evidence is insufficient

AI MUST NOT:
- perform authoritative financial calculations
- replace deterministic matching
- invent missing transactions
- alter payment, settlement or bank records
- alter UTRs or identifiers
- create or delete financial records
- declare that money was received without source evidence
- override deterministic reconciliation
- read or use `ground_truth.json`
- silently mark an exception resolved

## 4. Eligible Exceptions

Initial AI targets:
1. `UNKNOWN`
2. `AMOUNT_MISMATCH`
3. `MISSING_BANK_CREDIT`
4. `UNMATCHED_REFERENCE`

Secondary target:
5. `REFUND_MISMATCH`

`DUPLICATE` and straightforward `MISSING_SETTLEMENT` cases should normally remain deterministic because their logic is already explicit.

AI should not be invoked for already reconciled records.

## 5. Investigation Context

The AI receives a bounded context containing only relevant evidence.

Possible payment fields:
- payment_id
- order_id
- amount
- currency
- payment_date
- status
- refund_amount

Possible settlement fields:
- entity_id
- type
- payment_id
- order_id
- settlement_id
- settlement_utr
- amount
- debit
- credit
- fee
- tax
- settled_at
- description

Possible bank fields:
- bank_transaction_id
- transaction_date
- description
- amount
- transaction_type
- utr

Deterministic evidence may include:
- exception status
- rule that fired
- expected amount
- actual amount
- variance
- related identifiers
- related record IDs
- batch information

## 6. Evidence Boundary

The AI operates only on supplied investigation context.

It MUST NOT:
- search the internet for transaction facts
- access the repository
- access unrelated application internals
- access hidden evaluation data
- access `ground_truth.json`
- infer facts from records it was not given

If required evidence is missing, it must say so.

## 7. Candidate Generation

The deterministic system remains responsible for selecting candidate records.

Candidate generation uses deterministic identifiers such as:
1. payment_id
2. entity_id
3. order_id
4. settlement_id
5. settlement_utr
6. bank_transaction_id

AI must not introduce fuzzy matching.

If multiple candidates remain plausible, AI must report the ambiguity rather than silently selecting one as fact.

## 8. Investigation Process

For each eligible exception:

1. Understand the deterministic exception: status, rule, expected/actual values, variance and identifiers.
2. Review the supplied relevant records.
3. AI may verify supplied arithmetic, but deterministic calculations remain authoritative.
4. Compare only explanations supported by supplied evidence.
5. Produce a structured finding with likely cause, evidence, contradiction, confidence and recommendation.

If AI arithmetic disagrees with the deterministic engine, the deterministic result wins and the discrepancy should be flagged.

## 9. Structured Output

AI must return typed JSON matching the application's schema.

Required concepts:

```json
{
  "exception_id": "EXC_001",
  "finding": "Likely settlement reference inconsistency",
  "classification": "UNMATCHED_REFERENCE",
  "confidence": 0.91,
  "supporting_evidence": [],
  "contradictory_evidence": [],
  "recommendation": "Review settlement reference mapping",
  "human_review_required": true,
  "financial_records_modified": false
}
```

The application must not treat an unstructured free-form response as authoritative.

## 10. Evidence Requirements

Every finding must be traceable to supplied records.

Evidence should identify:
- source
- record identifier
- field
- value
- relevance

The AI must distinguish:
- **Fact:** directly present in supplied data.
- **Inference:** conclusion derived from facts.
- **Recommendation:** proposed operational action.

These must not be conflated.

## 11. Confidence Policy

Confidence represents confidence in the investigation finding, not financial certainty.

- `0.90–1.00`: strong evidence, little meaningful contradiction
- `0.75–0.89`: good evidence, some uncertainty
- `0.50–0.74`: plausible but materially uncertain
- `< 0.50`: insufficient evidence

Confidence never grants permission to modify financial records.

Conflicting evidence should reduce confidence.

## 12. Human Review

Human review is required when:
- evidence is contradictory
- multiple candidates remain plausible
- the proposed explanation would materially affect financial records
- confidence is below the configured threshold
- the AI cannot establish a defensible explanation
- the case is outside supported scenarios

Default policy:

> If the AI cannot explain the exception from supplied evidence, escalate rather than guess.

## 13. Auto-Resolution Guardrails

AI must NOT directly perform auto-resolution.

An AI recommendation can become an automatic resolution only if:
1. a predefined deterministic resolution rule exists;
2. required evidence is present;
3. the deterministic rule independently confirms the condition;
4. the resolution is auditable.

Otherwise the recommendation goes to human review.

Keep automatic resolution minimal in Phase 3.

## 14. Example Investigation

For a conflicting-UTR `UNKNOWN` case, AI may conclude that the settlement references are inconsistent, cite the conflicting settlement and bank fields, recommend reference review, and require human review.

For an `AMOUNT_MISMATCH`, AI may explain a variance when supplied refund/adjustment evidence accounts for it. It must not invent an explanation.

For an unexplained variance, AI should explicitly report insufficient evidence and escalate.

## 15. Failure Handling

If AI:
- times out
- returns malformed JSON
- produces unsupported classifications
- violates the evidence boundary
- provides no defensible explanation

the application must fail safely.

The deterministic reconciliation result remains unchanged.

The exception remains unresolved and available for human review.

AI failure must never cause financial data loss or mutation.

## 16. AI Usage Disclosure

Reconex uses AI only for:
- exception investigation
- evidence synthesis
- root-cause hypothesis
- explanation
- confidence assessment
- recommended next action

Reconex does NOT use AI for:
- authoritative financial calculations
- deterministic reconciliation
- source-of-truth modification
- blind transaction matching
- creating or deleting financial records

This boundary must be reflected in the README and final submission.

## 17. Evaluation Plan

AI performance must be evaluated separately from deterministic reconciliation.

At minimum measure:
- investigation coverage
- correct root-cause classification
- evidence grounding
- unsupported-claim rate
- recommendation usefulness
- escalation correctness
- AI failure rate

AI must not receive `ground_truth.json` as input.

A separate evaluation harness may use ground truth to assess AI findings.

Distinguish:
- correct investigation
- partially correct investigation
- unsupported conclusion
- incorrect conclusion
- appropriate escalation

## 18. Phase 3 Non-Goals

Do NOT implement:
- autonomous financial decision making
- unrestricted agentic behavior
- autonomous record modification
- live production payment operations
- generic unrelated chatbot functionality
- broad web research
- fuzzy transaction matching
- predictive fraud scoring
- credit/risk scoring
- accounting ledger mutation

The AI exists specifically to investigate reconciliation exceptions.

## 19. Acceptance Criteria

Phase 3 is complete only when:
1. AI is invoked only for supported exception types.
2. AI receives bounded evidence.
3. AI cannot access ground truth.
4. AI returns typed structured output.
5. Every finding cites supplied evidence.
6. Facts, inferences and recommendations are distinguishable.
7. Confidence is explicit.
8. Uncertain cases escalate.
9. Financial source records are never modified by AI.
10. Deterministic reconciliation remains authoritative.
11. AI failures leave deterministic results unchanged.
12. AI behavior can be evaluated independently.
13. AI usage is clearly documented.

## 20. Architectural Principle

> Deterministic logic establishes financial truth. AI investigates the exceptions that deterministic logic cannot safely explain.

AI should make finance operations faster and more understandable, not make the financial system less trustworthy.
