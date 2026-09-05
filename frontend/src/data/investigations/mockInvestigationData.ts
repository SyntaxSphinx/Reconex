import {
  ELIGIBLE_STATUSES,
  EvidenceSource,
  GuardrailViolation,
  InvestigationOutcome,
  ReconciliationStatus,
  ResultLevel,
  type EvidenceItem,
  type InvestigationBundle,
  type InvestigationContext,
  type InvestigationRecord,
  type InvestigationReport,
} from '../../types/investigation'

function evidenceItem(
  index: number,
  source: EvidenceItem['source'],
  record_id: string,
  field: string,
  value: string | number,
  relevance: string,
): EvidenceItem {
  return {
    evidence_id: `EV${String(index).padStart(3, '0')}`,
    source,
    record_id,
    field,
    value: String(value),
    relevance,
  }
}

function contextFor(
  record: InvestigationRecord,
  identifiers: Record<string, string>,
  evidence: EvidenceItem[],
  extras?: Pick<InvestigationContext, 'message'> & {
    rule_applied?: string | null
    evidence_dropped_count?: number
  },
): InvestigationContext {
  return {
    exception_id: record.exception_id,
    deterministic_status: record.deterministic_status,
    result_level: record.result_level,
    rule_applied: extras?.rule_applied ?? record.deterministic_rule ?? null,
    message: extras?.message ?? null,
    identifiers,
    evidence,
    allowed_classifications: [...ELIGIBLE_STATUSES],
    evidence_dropped_count:
      extras?.evidence_dropped_count ?? record.evidence_dropped_count,
  }
}

function recordWithCounts(
  record: Omit<
    InvestigationRecord,
    'evidence_count' | 'evidence_dropped_count' | 'financial_records_modified'
  > & {
    evidence_count?: number
    evidence_dropped_count?: number
  },
  evidenceCount: number,
): InvestigationRecord {
  return {
    ...record,
    evidence_count: record.evidence_count ?? evidenceCount,
    evidence_dropped_count: record.evidence_dropped_count ?? 0,
    financial_records_modified: false,
  }
}

const amountMismatchBatch = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1042',
    deterministic_status: ReconciliationStatus.AMOUNT_MISMATCH,
    deterministic_rule: 'AMOUNT_MISMATCH: Batch net does not match bank credit',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.INVESTIGATED,
    human_review_required: false,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1042',
      finding:
        'The settlement batch net of 97,300 paise does not equal the matched bank credit of 90,000 paise. The 7,300 paise variance is present in the deterministic evidence and is not explained by the supplied settlement lines.',
      classification: ReconciliationStatus.AMOUNT_MISMATCH,
      confidence: 0.92,
      supporting_evidence: ['EV001', 'EV005', 'EV006', 'EV012'],
      contradictory_evidence: [],
      recommendation:
        'Confirm the bank credit with the settlement provider and review whether a fee or adjustment line is missing from the batch.',
      human_review_required: false,
      financial_records_modified: false,
    },
  },
  14,
)

const amountMismatchPaymentDisagree = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL',
    deterministic_status: ReconciliationStatus.AMOUNT_MISMATCH,
    deterministic_rule: 'AMOUNT_MISMATCH: Payment amount does not match settlement credit',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [
      GuardrailViolation.CLASSIFICATION_DISAGREES_WITH_ENGINE,
    ],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL',
      finding:
        'The payment and settlement amounts differ, but the settlement UTR also fails to match the bank reference. The more useful next step may be a reference review.',
      classification: ReconciliationStatus.UNMATCHED_REFERENCE,
      confidence: 0.78,
      supporting_evidence: ['EV001', 'EV004', 'EV008'],
      contradictory_evidence: [],
      recommendation:
        'Keep the deterministic amount-mismatch classification and separately verify the settlement UTR against the bank credit.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  11,
)

const missingBankCreditEscalated = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1108',
    deterministic_status: ReconciliationStatus.MISSING_BANK_CREDIT,
    deterministic_rule: 'MISSING_BANK_CREDIT: Beyond bank credit window',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.CONFIDENCE_BELOW_THRESHOLD],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1108',
      finding:
        'Settlement batch_1108 claims UTR1108, but no matching bank credit was supplied. The expected credit of 1,24,500 rupees cannot be confirmed from the available evidence.',
      classification: ReconciliationStatus.MISSING_BANK_CREDIT,
      confidence: 0.61,
      supporting_evidence: ['EV001', 'EV003', 'EV007'],
      contradictory_evidence: [],
      recommendation:
        'Ask the bank operations team to locate a credit for UTR1108 or confirm that the settlement UTR is incorrect.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  9,
)

const missingBankCreditFailed = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1184',
    deterministic_status: ReconciliationStatus.MISSING_BANK_CREDIT,
    deterministic_rule: 'MISSING_BANK_CREDIT: Beyond bank credit window',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.FAILED,
    investigation: null,
    human_review_required: true,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason: 'Provider failure: LLM request timed out',
  },
  8,
)

const unknownConflictingUtrs = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1071',
    deterministic_status: ReconciliationStatus.UNKNOWN,
    deterministic_rule: 'UNKNOWN: Conflicting UTRs in settlement batch',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.CONTRADICTORY_EVIDENCE],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1071',
      finding:
        'Settlement lines in this batch cite two different UTRs. The deterministic engine correctly marked the batch UNKNOWN because the bank reference is ambiguous.',
      classification: ReconciliationStatus.UNKNOWN,
      confidence: 0.84,
      supporting_evidence: ['EV001', 'EV003'],
      contradictory_evidence: ['EV008'],
      recommendation:
        'Have operations confirm which UTR is authoritative for batch_1071 before matching a bank credit.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  10,
)

const unmatchedReferenceInvestigated = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_NrL9wK0yU3oSqM',
    deterministic_status: ReconciliationStatus.UNMATCHED_REFERENCE,
    deterministic_rule: 'UNMATCHED_REFERENCE: Settlement line has no valid UTR',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.INVESTIGATED,
    human_review_required: false,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-PAYMENT-pay_NrL9wK0yU3oSqM',
      finding:
        'The settlement line attached to this payment has UTR_CORRUPT, which does not match the batch majority reference. No alternate bank row was supplied.',
      classification: ReconciliationStatus.UNMATCHED_REFERENCE,
      confidence: 0.88,
      supporting_evidence: ['EV001', 'EV006', 'EV008'],
      contradictory_evidence: [],
      recommendation:
        'Correct the settlement UTR on the payment line and re-run reconciliation.',
      human_review_required: false,
      financial_records_modified: false,
    },
  },
  10,
)

const refundMismatchLowConfidence = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_OsM0xL1zV4pTrN',
    deterministic_status: ReconciliationStatus.REFUND_MISMATCH,
    deterministic_rule:
      'REFUND_MISMATCH: Payment refund does not match settlement refund',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.CONFIDENCE_BELOW_THRESHOLD],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-PAYMENT-pay_OsM0xL1zV4pTrN',
      finding:
        'The payment records a 5,000 paise refund while the settlement side shows 0. The supplied lines do not include a refund settlement entity, so the cause is only partly explained.',
      classification: ReconciliationStatus.REFUND_MISMATCH,
      confidence: 0.71,
      supporting_evidence: ['EV001', 'EV005', 'EV006'],
      contradictory_evidence: [],
      recommendation:
        'Confirm whether a refund settlement line is missing or the payment-side refund was recorded in error.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  10,
)

const unknownFailedJson = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_PtN1yM2aW5qUsP',
    deterministic_status: ReconciliationStatus.UNKNOWN,
    deterministic_rule: 'UNKNOWN: Insufficient deterministic match',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.FAILED,
    investigation: null,
    human_review_required: true,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason: 'Response was not valid JSON: Expected a JSON object at the top level',
  },
  6,
)

const amountMismatchHallucinated = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1203',
    deterministic_status: ReconciliationStatus.AMOUNT_MISMATCH,
    deterministic_rule: 'AMOUNT_MISMATCH: Batch net does not match bank credit',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.HALLUCINATED_EVIDENCE_REFERENCE],
    invalid_evidence_references: ['EV999'],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1203',
      finding:
        'Batch net is short of the bank credit. A cited evidence item was removed because it was not in the supplied context.',
      classification: ReconciliationStatus.AMOUNT_MISMATCH,
      confidence: 0.8,
      supporting_evidence: ['EV001', 'EV004'],
      contradictory_evidence: [],
      recommendation:
        'Review the remaining supplied variance evidence before adjusting the batch.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  12,
)

const refundMismatchInvestigated = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ',
    deterministic_status: ReconciliationStatus.REFUND_MISMATCH,
    deterministic_rule:
      'REFUND_MISMATCH: Payment refund does not match settlement refund',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.INVESTIGATED,
    human_review_required: false,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ',
      finding:
        'Payment refund of 24,500 paise is recorded, while settlement refund is 12,000 paise. Both figures are present in the deterministic evidence.',
      classification: ReconciliationStatus.REFUND_MISMATCH,
      confidence: 0.86,
      supporting_evidence: ['EV001', 'EV005', 'EV006'],
      contradictory_evidence: [],
      recommendation:
        'Reconcile the remaining 12,500 paise refund against a missing refund settlement line.',
      human_review_required: false,
      financial_records_modified: false,
    },
  },
  11,
)

const unmatchedReferenceProse = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1255',
    deterministic_status: ReconciliationStatus.UNMATCHED_REFERENCE,
    deterministic_rule: 'UNMATCHED_REFERENCE: Settlement line has no valid UTR',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.UNGROUNDED_IDENTIFIER_IN_PROSE],
    invalid_evidence_references: ['UTR999999'],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1255',
      finding:
        'The batch contains a settlement line whose UTR does not match the majority reference.',
      classification: ReconciliationStatus.UNMATCHED_REFERENCE,
      confidence: 0.83,
      supporting_evidence: ['EV001', 'EV004'],
      contradictory_evidence: [],
      recommendation:
        'Remap the batch to UTR999999 before closing.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  8,
)

const amountMismatchFailedSchema = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_RvP3aO4cY7sWuR',
    deterministic_status: ReconciliationStatus.AMOUNT_MISMATCH,
    deterministic_rule: 'AMOUNT_MISMATCH: Payment amount does not match settlement credit',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.FAILED,
    investigation: null,
    human_review_required: true,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason:
      'Response did not match the investigation schema: 3 error(s)',
  },
  9,
)

const unknownInvestigated = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1090',
    deterministic_status: ReconciliationStatus.UNKNOWN,
    deterministic_rule: 'UNKNOWN: Conflicting UTRs in settlement batch',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.INVESTIGATED,
    human_review_required: false,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1090',
      finding:
        'Two settlement lines in the batch carry distinct UTRs. The engine left the batch UNKNOWN because a single bank reference cannot be chosen from the supplied evidence.',
      classification: ReconciliationStatus.UNKNOWN,
      confidence: 0.81,
      supporting_evidence: ['EV001', 'EV002', 'EV004'],
      contradictory_evidence: [],
      recommendation:
        'Obtain the intended UTR from the settlement file owner and re-run the batch.',
      human_review_required: false,
      financial_records_modified: false,
    },
  },
  9,
)

const missingBankNoSupport = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1312',
    deterministic_status: ReconciliationStatus.MISSING_BANK_CREDIT,
    deterministic_rule: 'MISSING_BANK_CREDIT: Beyond bank credit window',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.NO_SUPPORTING_EVIDENCE],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1312',
      finding:
        'No bank credit was supplied for this settlement. The model did not cite a usable evidence item after sanitization.',
      classification: ReconciliationStatus.MISSING_BANK_CREDIT,
      confidence: 0.55,
      supporting_evidence: [],
      contradictory_evidence: [],
      recommendation:
        'Escalate to treasury to confirm whether the credit is delayed or the UTR is wrong.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  7,
)

const unmatchedIdMismatch = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_SwQ4bP5dZ8tXvS',
    deterministic_status: ReconciliationStatus.UNMATCHED_REFERENCE,
    deterministic_rule: 'UNMATCHED_REFERENCE: Settlement line has no valid UTR',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.EXCEPTION_ID_MISMATCH],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-PAYMENT-pay_SwQ4bP5dZ8tXvS',
      finding:
        'The settlement UTR on this payment does not match the batch majority. The response exception_id was corrected to the engine identifier.',
      classification: ReconciliationStatus.UNMATCHED_REFERENCE,
      confidence: 0.79,
      supporting_evidence: ['EV001', 'EV005'],
      contradictory_evidence: [],
      recommendation:
        'Correct the settlement reference on the payment line and re-run matching.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  8,
)

const amountMismatchClaimedMod = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1330',
    deterministic_status: ReconciliationStatus.AMOUNT_MISMATCH,
    deterministic_rule: 'AMOUNT_MISMATCH: Batch net does not match bank credit',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.CLAIMED_FINANCIAL_MODIFICATION],
    invalid_evidence_references: [],
    failure_reason: null,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1330',
      finding:
        'The bank credit is 8,200 paise below the settlement net. Financial records were not changed.',
      classification: ReconciliationStatus.AMOUNT_MISMATCH,
      confidence: 0.9,
      supporting_evidence: ['EV001', 'EV005', 'EV006'],
      contradictory_evidence: [],
      recommendation:
        'Do not adjust source records. Confirm the posted bank amount with the acquiring bank.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  13,
)

const refundMismatchFailed = recordWithCounts(
  {
    exception_id: 'EXC-PAYMENT-pay_TxR5cQ6eA9uYwT',
    deterministic_status: ReconciliationStatus.REFUND_MISMATCH,
    deterministic_rule:
      'REFUND_MISMATCH: Payment refund does not match settlement refund',
    result_level: ResultLevel.PAYMENT,
    outcome: InvestigationOutcome.FAILED,
    investigation: null,
    human_review_required: true,
    guardrail_violations: [],
    invalid_evidence_references: [],
    failure_reason: 'Unexpected provider error: socket exploded',
  },
  8,
)

const amountMismatchDroppedEvidence = recordWithCounts(
  {
    exception_id: 'EXC-BATCH-batch_1401',
    deterministic_status: ReconciliationStatus.AMOUNT_MISMATCH,
    deterministic_rule: 'AMOUNT_MISMATCH: Batch net does not match bank credit',
    result_level: ResultLevel.BATCH,
    outcome: InvestigationOutcome.ESCALATED,
    human_review_required: true,
    guardrail_violations: [GuardrailViolation.CONFIDENCE_BELOW_THRESHOLD],
    invalid_evidence_references: [],
    failure_reason: null,
    evidence_count: 8,
    evidence_dropped_count: 18,
    investigation: {
      exception_id: 'EXC-BATCH-batch_1401',
      finding:
        'The batch net differs from the bank credit. Several settlement lines were dropped from the investigation context, so the explanation is incomplete.',
      classification: ReconciliationStatus.AMOUNT_MISMATCH,
      confidence: 0.68,
      supporting_evidence: ['EV001', 'EV004'],
      contradictory_evidence: [],
      recommendation:
        'Review the full settlement file for batch_1401; the investigator did not receive every line.',
      human_review_required: true,
      financial_records_modified: false,
    },
  },
  8,
)

function bundles(): InvestigationBundle[] {
  return [
    {
      record: amountMismatchBatch,
      context: contextFor(
        amountMismatchBatch,
        {
          settlement_id: 'batch_1042',
          settlement_utr: 'UTR1042',
          bank_transaction_id: 'bank_txn_1042',
          entity_ids: 'setl_1042a,setl_1042b',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1042', 'primary_status', 'AMOUNT_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1042', 'rule_applied', 'AMOUNT_MISMATCH: Batch net does not match bank credit', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1042', 'expected_amount_paise', 97300, 'Expected amount in paise, computed deterministically'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1042', 'actual_amount_paise', 90000, 'Actual amount in paise, computed deterministically'),
          evidenceItem(5, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1042', 'variance_paise', 7300, 'Deterministic variance in paise; authoritative'),
          evidenceItem(6, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1042', 'settlement_amount_paise', 97300, 'Net settlement amount in paise'),
          evidenceItem(7, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1042', 'bank_amount_paise', 90000, 'Bank credit amount in paise'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1042a', 'settlement_id', 'batch_1042', 'Settlement batch the line belongs to'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1042a', 'credit', 97300, 'Credit component in paise'),
          evidenceItem(10, EvidenceSource.SETTLEMENT, 'setl_1042a', 'settlement_utr', 'UTR1042', 'Bank reference claimed by the settlement line'),
          evidenceItem(11, EvidenceSource.BANK, 'bank_txn_1042', 'bank_transaction_id', 'bank_txn_1042', 'Bank transaction identifier'),
          evidenceItem(12, EvidenceSource.BANK, 'bank_txn_1042', 'amount', 90000, 'Bank transaction amount in paise'),
          evidenceItem(13, EvidenceSource.BANK, 'bank_txn_1042', 'utr', 'UTR1042', 'Bank reference used for matching'),
          evidenceItem(14, EvidenceSource.BANK, 'bank_txn_1042', 'transaction_type', 'credit', 'Credit or debit'),
        ],
        { message: 'Settlement batch net differs from bank credit' },
      ),
    },
    {
      record: amountMismatchPaymentDisagree,
      context: contextFor(
        amountMismatchPaymentDisagree,
        {
          payment_id: 'pay_MqK8vJ9xT2nRpL',
          order_id: 'order_MqK8vJ9x',
          settlement_id: 'batch_1048',
          settlement_utr: 'UTR1048X',
          entity_ids: 'setl_1048a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL', 'primary_status', 'AMOUNT_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL', 'rule_applied', 'AMOUNT_MISMATCH: Payment amount does not match settlement credit', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL', 'payment_amount_paise', 4560000, 'Payment amount in paise'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL', 'settlement_amount_paise', 4410000, 'Net settlement amount in paise'),
          evidenceItem(5, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL', 'variance_paise', 150000, 'Deterministic variance in paise; authoritative'),
          evidenceItem(6, EvidenceSource.PAYMENT, 'pay_MqK8vJ9xT2nRpL', 'payment_id', 'pay_MqK8vJ9xT2nRpL', 'Payment identifier under investigation'),
          evidenceItem(7, EvidenceSource.PAYMENT, 'pay_MqK8vJ9xT2nRpL', 'amount', 4560000, 'Captured payment amount in paise'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1048a', 'settlement_utr', 'UTR1048X', 'Bank reference claimed by the settlement line'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1048a', 'credit', 4410000, 'Credit component in paise'),
          evidenceItem(10, EvidenceSource.PAYMENT, 'pay_MqK8vJ9xT2nRpL', 'order_id', 'order_MqK8vJ9x', 'Order the payment belongs to'),
          evidenceItem(11, EvidenceSource.PAYMENT, 'pay_MqK8vJ9xT2nRpL', 'status', 'captured', 'Payment lifecycle status'),
        ],
        { message: 'Payment amount differs from settlement credit' },
      ),
    },
    {
      record: missingBankCreditEscalated,
      context: contextFor(
        missingBankCreditEscalated,
        {
          settlement_id: 'batch_1108',
          settlement_utr: 'UTR1108',
          entity_ids: 'setl_1108a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1108', 'primary_status', 'MISSING_BANK_CREDIT', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1108', 'rule_applied', 'MISSING_BANK_CREDIT: Beyond bank credit window', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1108', 'expected_amount_paise', 12450000, 'Expected amount in paise, computed deterministically'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1108', 'settlement_amount_paise', 12450000, 'Net settlement amount in paise'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1108a', 'settlement_id', 'batch_1108', 'Settlement batch the line belongs to'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1108a', 'settlement_utr', 'UTR1108', 'Bank reference claimed by the settlement line'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1108a', 'credit', 12450000, 'Credit component in paise'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1108a', 'entity_id', 'setl_1108a', 'Settlement line identifier'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1108a', 'type', 'payment', 'Whether the line is a payment, refund or adjustment'),
        ],
        { message: 'No bank credit found for settlement UTR' },
      ),
    },
    {
      record: missingBankCreditFailed,
      context: contextFor(
        missingBankCreditFailed,
        {
          settlement_id: 'batch_1184',
          settlement_utr: 'UTR_MISSING_1184',
          entity_ids: 'setl_1184a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1184', 'primary_status', 'MISSING_BANK_CREDIT', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1184', 'rule_applied', 'MISSING_BANK_CREDIT: Beyond bank credit window', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1184', 'expected_amount_paise', 87634000, 'Expected amount in paise, computed deterministically'),
          evidenceItem(4, EvidenceSource.SETTLEMENT, 'setl_1184a', 'settlement_id', 'batch_1184', 'Settlement batch the line belongs to'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1184a', 'settlement_utr', 'UTR_MISSING_1184', 'Bank reference claimed by the settlement line'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1184a', 'credit', 87634000, 'Credit component in paise'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1184a', 'amount', 90000000, 'Gross line amount in paise'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1184a', 'entity_id', 'setl_1184a', 'Settlement line identifier'),
        ],
        { message: 'No bank credit found for settlement UTR' },
      ),
    },
    {
      record: unknownConflictingUtrs,
      context: contextFor(
        unknownConflictingUtrs,
        {
          settlement_id: 'batch_1071',
          entity_ids: 'setl_1071a,setl_1071b',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1071', 'primary_status', 'UNKNOWN', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1071', 'rule_applied', 'UNKNOWN: Conflicting UTRs in settlement batch', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1071', 'conflict_reason', "Multiple UTRs in batch: ['UTR1071A', 'UTR1071B']", 'Why the deterministic match was ambiguous'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1071', 'settlement_amount_paise', 14289000, 'Net settlement amount in paise'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1071a', 'entity_id', 'setl_1071a', 'Settlement line identifier'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1071a', 'settlement_utr', 'UTR1071A', 'Bank reference claimed by the settlement line'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1071a', 'credit', 8000000, 'Credit component in paise'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1071b', 'settlement_utr', 'UTR1071B', 'Bank reference claimed by the settlement line'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1071b', 'credit', 6289000, 'Credit component in paise'),
          evidenceItem(10, EvidenceSource.SETTLEMENT, 'setl_1071b', 'entity_id', 'setl_1071b', 'Settlement line identifier'),
        ],
        { message: 'Settlement batch has conflicting UTRs' },
      ),
    },
    {
      record: unmatchedReferenceInvestigated,
      context: contextFor(
        unmatchedReferenceInvestigated,
        {
          payment_id: 'pay_NrL9wK0yU3oSqM',
          order_id: 'order_NrL9wK0y',
          settlement_id: 'batch_1114',
          settlement_utr: 'UTR_CORRUPT',
          entity_ids: 'setl_1114a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_NrL9wK0yU3oSqM', 'primary_status', 'UNMATCHED_REFERENCE', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_NrL9wK0yU3oSqM', 'rule_applied', 'UNMATCHED_REFERENCE: Settlement line has no valid UTR', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_NrL9wK0yU3oSqM', 'payment_amount_paise', 6720000, 'Payment amount in paise'),
          evidenceItem(4, EvidenceSource.PAYMENT, 'pay_NrL9wK0yU3oSqM', 'payment_id', 'pay_NrL9wK0yU3oSqM', 'Payment identifier under investigation'),
          evidenceItem(5, EvidenceSource.PAYMENT, 'pay_NrL9wK0yU3oSqM', 'amount', 6720000, 'Captured payment amount in paise'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1114a', 'settlement_utr', 'UTR_CORRUPT', 'Bank reference claimed by the settlement line'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1114a', 'payment_id', 'pay_NrL9wK0yU3oSqM', 'Payment the settlement line refers to'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1114a', 'settlement_id', 'batch_1114', 'Settlement batch the line belongs to'),
          evidenceItem(9, EvidenceSource.PAYMENT, 'pay_NrL9wK0yU3oSqM', 'order_id', 'order_NrL9wK0y', 'Order the payment belongs to'),
          evidenceItem(10, EvidenceSource.PAYMENT, 'pay_NrL9wK0yU3oSqM', 'status', 'captured', 'Payment lifecycle status'),
        ],
        { message: 'Settlement line UTR does not match batch majority' },
      ),
    },
    {
      record: refundMismatchLowConfidence,
      context: contextFor(
        refundMismatchLowConfidence,
        {
          payment_id: 'pay_OsM0xL1zV4pTrN',
          order_id: 'order_OsM0xL1z',
          settlement_id: 'batch_1120',
          entity_ids: 'setl_1120a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_OsM0xL1zV4pTrN', 'primary_status', 'REFUND_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_OsM0xL1zV4pTrN', 'rule_applied', 'REFUND_MISMATCH: Payment refund does not match settlement refund', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_OsM0xL1zV4pTrN', 'payment_amount_paise', 890000, 'Payment amount in paise'),
          evidenceItem(4, EvidenceSource.PAYMENT, 'pay_OsM0xL1zV4pTrN', 'refund_amount', 5000, 'Refund recorded on the payment side'),
          evidenceItem(5, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_OsM0xL1zV4pTrN', 'payment_refund_amount_paise', 5000, 'Refund amount recorded on the payment'),
          evidenceItem(6, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_OsM0xL1zV4pTrN', 'settlement_refund_amount_paise', 0, 'Refund amount recorded in settlement'),
          evidenceItem(7, EvidenceSource.PAYMENT, 'pay_OsM0xL1zV4pTrN', 'payment_id', 'pay_OsM0xL1zV4pTrN', 'Payment identifier under investigation'),
          evidenceItem(8, EvidenceSource.PAYMENT, 'pay_OsM0xL1zV4pTrN', 'amount', 890000, 'Captured payment amount in paise'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1120a', 'type', 'payment', 'Whether the line is a payment, refund or adjustment'),
          evidenceItem(10, EvidenceSource.SETTLEMENT, 'setl_1120a', 'credit', 865000, 'Credit component in paise'),
        ],
        { message: 'Refund amounts differ' },
      ),
    },
    {
      record: unknownFailedJson,
      context: contextFor(
        unknownFailedJson,
        {
          payment_id: 'pay_PtN1yM2aW5qUsP',
          order_id: 'order_PtN1yM2a',
          settlement_id: 'batch_1126',
          entity_ids: 'setl_1126a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_PtN1yM2aW5qUsP', 'primary_status', 'UNKNOWN', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_PtN1yM2aW5qUsP', 'rule_applied', 'UNKNOWN: Insufficient deterministic match', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_PtN1yM2aW5qUsP', 'conflict_reason', 'Payment has settlement lines but no usable bank reference', 'Why the deterministic match was ambiguous'),
          evidenceItem(4, EvidenceSource.PAYMENT, 'pay_PtN1yM2aW5qUsP', 'payment_id', 'pay_PtN1yM2aW5qUsP', 'Payment identifier under investigation'),
          evidenceItem(5, EvidenceSource.PAYMENT, 'pay_PtN1yM2aW5qUsP', 'amount', 215000, 'Captured payment amount in paise'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1126a', 'settlement_utr', '', 'Bank reference claimed by the settlement line'),
        ],
        { message: 'Payment could not be classified from supplied identifiers' },
      ),
    },
    {
      record: amountMismatchHallucinated,
      context: contextFor(
        amountMismatchHallucinated,
        {
          settlement_id: 'batch_1203',
          settlement_utr: 'UTR1203',
          bank_transaction_id: 'bank_txn_1203',
          entity_ids: 'setl_1203a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1203', 'primary_status', 'AMOUNT_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1203', 'expected_amount_paise', 3100000, 'Expected amount in paise, computed deterministically'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1203', 'actual_amount_paise', 2980000, 'Actual amount in paise, computed deterministically'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1203', 'variance_paise', 120000, 'Deterministic variance in paise; authoritative'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1203a', 'credit', 3100000, 'Credit component in paise'),
          evidenceItem(6, EvidenceSource.BANK, 'bank_txn_1203', 'amount', 2980000, 'Bank transaction amount in paise'),
          evidenceItem(7, EvidenceSource.BANK, 'bank_txn_1203', 'utr', 'UTR1203', 'Bank reference used for matching'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1203a', 'settlement_id', 'batch_1203', 'Settlement batch the line belongs to'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1203a', 'settlement_utr', 'UTR1203', 'Bank reference claimed by the settlement line'),
          evidenceItem(10, EvidenceSource.BANK, 'bank_txn_1203', 'transaction_type', 'credit', 'Credit or debit'),
          evidenceItem(11, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1203', 'bank_amount_paise', 2980000, 'Bank credit amount in paise'),
          evidenceItem(12, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1203', 'settlement_amount_paise', 3100000, 'Net settlement amount in paise'),
        ],
        { message: 'Settlement batch net differs from bank credit' },
      ),
    },
    {
      record: refundMismatchInvestigated,
      context: contextFor(
        refundMismatchInvestigated,
        {
          payment_id: 'pay_QuO2zN3bX6rVtQ',
          order_id: 'order_QuO2zN3b',
          settlement_id: 'batch_1211',
          entity_ids: 'setl_1211a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ', 'primary_status', 'REFUND_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ', 'rule_applied', 'REFUND_MISMATCH: Payment refund does not match settlement refund', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ', 'payment_amount_paise', 2450000, 'Payment amount in paise'),
          evidenceItem(4, EvidenceSource.PAYMENT, 'pay_QuO2zN3bX6rVtQ', 'refund_amount', 24500, 'Refund recorded on the payment side'),
          evidenceItem(5, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ', 'payment_refund_amount_paise', 24500, 'Refund amount recorded on the payment'),
          evidenceItem(6, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ', 'settlement_refund_amount_paise', 12000, 'Refund amount recorded in settlement'),
          evidenceItem(7, EvidenceSource.PAYMENT, 'pay_QuO2zN3bX6rVtQ', 'payment_id', 'pay_QuO2zN3bX6rVtQ', 'Payment identifier under investigation'),
          evidenceItem(8, EvidenceSource.PAYMENT, 'pay_QuO2zN3bX6rVtQ', 'amount', 2450000, 'Captured payment amount in paise'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1211a', 'type', 'refund', 'Whether the line is a payment, refund or adjustment'),
          evidenceItem(10, EvidenceSource.SETTLEMENT, 'setl_1211a', 'debit', 12000, 'Debit component in paise'),
          evidenceItem(11, EvidenceSource.SETTLEMENT, 'setl_1211a', 'payment_id', 'pay_QuO2zN3bX6rVtQ', 'Payment the settlement line refers to'),
        ],
        { message: 'Refund amounts differ' },
      ),
    },
    {
      record: unmatchedReferenceProse,
      context: contextFor(
        unmatchedReferenceProse,
        {
          settlement_id: 'batch_1255',
          settlement_utr: 'UTR1255',
          entity_ids: 'setl_1255a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1255', 'primary_status', 'UNMATCHED_REFERENCE', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1255', 'rule_applied', 'UNMATCHED_REFERENCE: Settlement line has no valid UTR', 'Deterministic rule that produced the status'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1255', 'settlement_amount_paise', 5400000, 'Net settlement amount in paise'),
          evidenceItem(4, EvidenceSource.SETTLEMENT, 'setl_1255a', 'settlement_utr', 'UTR1255X', 'Bank reference claimed by the settlement line'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1255a', 'settlement_id', 'batch_1255', 'Settlement batch the line belongs to'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1255a', 'credit', 5400000, 'Credit component in paise'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1255a', 'entity_id', 'setl_1255a', 'Settlement line identifier'),
          evidenceItem(8, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1255', 'conflict_reason', 'Line UTR does not match batch majority UTR1255', 'Why the deterministic match was ambiguous'),
        ],
        { message: 'Settlement line UTR does not match batch majority' },
      ),
    },
    {
      record: amountMismatchFailedSchema,
      context: contextFor(
        amountMismatchFailedSchema,
        {
          payment_id: 'pay_RvP3aO4cY7sWuR',
          order_id: 'order_RvP3aO4c',
          settlement_id: 'batch_1260',
          entity_ids: 'setl_1260a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_RvP3aO4cY7sWuR', 'primary_status', 'AMOUNT_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_RvP3aO4cY7sWuR', 'payment_amount_paise', 1890000, 'Payment amount in paise'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_RvP3aO4cY7sWuR', 'settlement_amount_paise', 1760000, 'Net settlement amount in paise'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_RvP3aO4cY7sWuR', 'variance_paise', 130000, 'Deterministic variance in paise; authoritative'),
          evidenceItem(5, EvidenceSource.PAYMENT, 'pay_RvP3aO4cY7sWuR', 'payment_id', 'pay_RvP3aO4cY7sWuR', 'Payment identifier under investigation'),
          evidenceItem(6, EvidenceSource.PAYMENT, 'pay_RvP3aO4cY7sWuR', 'amount', 1890000, 'Captured payment amount in paise'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1260a', 'credit', 1760000, 'Credit component in paise'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1260a', 'settlement_id', 'batch_1260', 'Settlement batch the line belongs to'),
          evidenceItem(9, EvidenceSource.PAYMENT, 'pay_RvP3aO4cY7sWuR', 'status', 'captured', 'Payment lifecycle status'),
        ],
        { message: 'Payment amount differs from settlement credit' },
      ),
    },
    {
      record: unknownInvestigated,
      context: contextFor(
        unknownInvestigated,
        {
          settlement_id: 'batch_1090',
          entity_ids: 'setl_1090a,setl_1090b',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1090', 'primary_status', 'UNKNOWN', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1090', 'conflict_reason', "Multiple UTRs in batch: ['UTR1090A', 'UTR1090B']", 'Why the deterministic match was ambiguous'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1090', 'settlement_amount_paise', 9900000, 'Net settlement amount in paise'),
          evidenceItem(4, EvidenceSource.SETTLEMENT, 'setl_1090a', 'settlement_utr', 'UTR1090A', 'Bank reference claimed by the settlement line'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1090b', 'settlement_utr', 'UTR1090B', 'Bank reference claimed by the settlement line'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1090a', 'credit', 5100000, 'Credit component in paise'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1090b', 'credit', 4800000, 'Credit component in paise'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1090a', 'entity_id', 'setl_1090a', 'Settlement line identifier'),
          evidenceItem(9, EvidenceSource.SETTLEMENT, 'setl_1090b', 'entity_id', 'setl_1090b', 'Settlement line identifier'),
        ],
        { message: 'Settlement batch has conflicting UTRs' },
      ),
    },
    {
      record: missingBankNoSupport,
      context: contextFor(
        missingBankNoSupport,
        {
          settlement_id: 'batch_1312',
          settlement_utr: 'UTR1312',
          entity_ids: 'setl_1312a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1312', 'primary_status', 'MISSING_BANK_CREDIT', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1312', 'expected_amount_paise', 4320000, 'Expected amount in paise, computed deterministically'),
          evidenceItem(3, EvidenceSource.SETTLEMENT, 'setl_1312a', 'settlement_utr', 'UTR1312', 'Bank reference claimed by the settlement line'),
          evidenceItem(4, EvidenceSource.SETTLEMENT, 'setl_1312a', 'credit', 4320000, 'Credit component in paise'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1312a', 'settlement_id', 'batch_1312', 'Settlement batch the line belongs to'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1312a', 'entity_id', 'setl_1312a', 'Settlement line identifier'),
          evidenceItem(7, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1312', 'rule_applied', 'MISSING_BANK_CREDIT: Beyond bank credit window', 'Deterministic rule that produced the status'),
        ],
        { message: 'No bank credit found for settlement UTR' },
      ),
    },
    {
      record: unmatchedIdMismatch,
      context: contextFor(
        unmatchedIdMismatch,
        {
          payment_id: 'pay_SwQ4bP5dZ8tXvS',
          order_id: 'order_SwQ4bP5d',
          settlement_id: 'batch_1318',
          settlement_utr: 'UTR_BAD_1318',
          entity_ids: 'setl_1318a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_SwQ4bP5dZ8tXvS', 'primary_status', 'UNMATCHED_REFERENCE', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_SwQ4bP5dZ8tXvS', 'payment_amount_paise', 760000, 'Payment amount in paise'),
          evidenceItem(3, EvidenceSource.PAYMENT, 'pay_SwQ4bP5dZ8tXvS', 'payment_id', 'pay_SwQ4bP5dZ8tXvS', 'Payment identifier under investigation'),
          evidenceItem(4, EvidenceSource.PAYMENT, 'pay_SwQ4bP5dZ8tXvS', 'amount', 760000, 'Captured payment amount in paise'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1318a', 'settlement_utr', 'UTR_BAD_1318', 'Bank reference claimed by the settlement line'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1318a', 'payment_id', 'pay_SwQ4bP5dZ8tXvS', 'Payment the settlement line refers to'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1318a', 'settlement_id', 'batch_1318', 'Settlement batch the line belongs to'),
          evidenceItem(8, EvidenceSource.PAYMENT, 'pay_SwQ4bP5dZ8tXvS', 'order_id', 'order_SwQ4bP5d', 'Order the payment belongs to'),
        ],
        { message: 'Settlement line UTR does not match batch majority' },
      ),
    },
    {
      record: amountMismatchClaimedMod,
      context: contextFor(
        amountMismatchClaimedMod,
        {
          settlement_id: 'batch_1330',
          settlement_utr: 'UTR1330',
          bank_transaction_id: 'bank_txn_1330',
          entity_ids: 'setl_1330a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1330', 'primary_status', 'AMOUNT_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1330', 'expected_amount_paise', 6500000, 'Expected amount in paise, computed deterministically'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1330', 'actual_amount_paise', 5680000, 'Actual amount in paise, computed deterministically'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1330', 'variance_paise', 820000, 'Deterministic variance in paise; authoritative'),
          evidenceItem(5, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1330', 'settlement_amount_paise', 6500000, 'Net settlement amount in paise'),
          evidenceItem(6, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1330', 'bank_amount_paise', 5680000, 'Bank credit amount in paise'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1330a', 'credit', 6500000, 'Credit component in paise'),
          evidenceItem(8, EvidenceSource.BANK, 'bank_txn_1330', 'amount', 5680000, 'Bank transaction amount in paise'),
          evidenceItem(9, EvidenceSource.BANK, 'bank_txn_1330', 'utr', 'UTR1330', 'Bank reference used for matching'),
          evidenceItem(10, EvidenceSource.SETTLEMENT, 'setl_1330a', 'settlement_id', 'batch_1330', 'Settlement batch the line belongs to'),
          evidenceItem(11, EvidenceSource.SETTLEMENT, 'setl_1330a', 'settlement_utr', 'UTR1330', 'Bank reference claimed by the settlement line'),
          evidenceItem(12, EvidenceSource.BANK, 'bank_txn_1330', 'bank_transaction_id', 'bank_txn_1330', 'Bank transaction identifier'),
          evidenceItem(13, EvidenceSource.BANK, 'bank_txn_1330', 'transaction_type', 'credit', 'Credit or debit'),
        ],
        { message: 'Settlement batch net differs from bank credit' },
      ),
    },
    {
      record: refundMismatchFailed,
      context: contextFor(
        refundMismatchFailed,
        {
          payment_id: 'pay_TxR5cQ6eA9uYwT',
          order_id: 'order_TxR5cQ6e',
          settlement_id: 'batch_1342',
          entity_ids: 'setl_1342a',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_TxR5cQ6eA9uYwT', 'primary_status', 'REFUND_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_TxR5cQ6eA9uYwT', 'payment_refund_amount_paise', 18000, 'Refund amount recorded on the payment'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-PAYMENT-pay_TxR5cQ6eA9uYwT', 'settlement_refund_amount_paise', 0, 'Refund amount recorded in settlement'),
          evidenceItem(4, EvidenceSource.PAYMENT, 'pay_TxR5cQ6eA9uYwT', 'payment_id', 'pay_TxR5cQ6eA9uYwT', 'Payment identifier under investigation'),
          evidenceItem(5, EvidenceSource.PAYMENT, 'pay_TxR5cQ6eA9uYwT', 'refund_amount', 18000, 'Refund recorded on the payment side'),
          evidenceItem(6, EvidenceSource.PAYMENT, 'pay_TxR5cQ6eA9uYwT', 'amount', 320000, 'Captured payment amount in paise'),
          evidenceItem(7, EvidenceSource.SETTLEMENT, 'setl_1342a', 'type', 'payment', 'Whether the line is a payment, refund or adjustment'),
          evidenceItem(8, EvidenceSource.SETTLEMENT, 'setl_1342a', 'credit', 305000, 'Credit component in paise'),
        ],
        { message: 'Refund amounts differ' },
      ),
    },
    {
      record: amountMismatchDroppedEvidence,
      context: contextFor(
        amountMismatchDroppedEvidence,
        {
          settlement_id: 'batch_1401',
          settlement_utr: 'UTR1401',
          bank_transaction_id: 'bank_txn_1401',
          entity_ids: 'setl_1401a,setl_1401b',
        },
        [
          evidenceItem(1, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1401', 'primary_status', 'AMOUNT_MISMATCH', 'Authoritative deterministic classification of this exception'),
          evidenceItem(2, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1401', 'expected_amount_paise', 22100000, 'Expected amount in paise, computed deterministically'),
          evidenceItem(3, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1401', 'actual_amount_paise', 21000000, 'Actual amount in paise, computed deterministically'),
          evidenceItem(4, EvidenceSource.DETERMINISTIC, 'EXC-BATCH-batch_1401', 'variance_paise', 1100000, 'Deterministic variance in paise; authoritative'),
          evidenceItem(5, EvidenceSource.SETTLEMENT, 'setl_1401a', 'credit', 11000000, 'Credit component in paise'),
          evidenceItem(6, EvidenceSource.SETTLEMENT, 'setl_1401b', 'credit', 11100000, 'Credit component in paise'),
          evidenceItem(7, EvidenceSource.BANK, 'bank_txn_1401', 'amount', 21000000, 'Bank transaction amount in paise'),
          evidenceItem(8, EvidenceSource.BANK, 'bank_txn_1401', 'utr', 'UTR1401', 'Bank reference used for matching'),
        ],
        {
          message: 'Settlement batch net differs from bank credit',
          evidence_dropped_count: 18,
        },
      ),
    },
  ]
}

export const MOCK_INVESTIGATION_BUNDLES: InvestigationBundle[] = bundles()

export function buildMockInvestigationReport(
  records: InvestigationRecord[],
): InvestigationReport {
  return {
    records,
    total_results: records.length,
    eligible_exceptions: records.length,
    skipped_not_eligible: 0,
    investigated: records.filter((r) => r.outcome === InvestigationOutcome.INVESTIGATED)
      .length,
    escalated: records.filter((r) => r.outcome === InvestigationOutcome.ESCALATED).length,
    failed: records.filter((r) => r.outcome === InvestigationOutcome.FAILED).length,
    human_review_required_count: records.filter((r) => r.human_review_required).length,
    financial_records_modified: false,
  }
}
