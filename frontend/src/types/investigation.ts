/**
 * Frontend copies of the backend investigation contracts.
 * Field names and shapes match backend/app/investigation/models.py
 * and backend/app/reconciliation/models.py. Do not add invented fields.
 */

export const ReconciliationStatus = {
  UNKNOWN: 'UNKNOWN',
  UNMATCHED_REFERENCE: 'UNMATCHED_REFERENCE',
  DUPLICATE: 'DUPLICATE',
  REFUND_MISMATCH: 'REFUND_MISMATCH',
  AMOUNT_MISMATCH: 'AMOUNT_MISMATCH',
  MISSING_SETTLEMENT: 'MISSING_SETTLEMENT',
  PENDING_SETTLEMENT: 'PENDING_SETTLEMENT',
  MISSING_BANK_CREDIT: 'MISSING_BANK_CREDIT',
  PENDING_BANK_CREDIT: 'PENDING_BANK_CREDIT',
  RECONCILED: 'RECONCILED',
} as const

export type ReconciliationStatus =
  (typeof ReconciliationStatus)[keyof typeof ReconciliationStatus]

export const ResultLevel = {
  PAYMENT: 'PAYMENT',
  BATCH: 'BATCH',
} as const

export type ResultLevel = (typeof ResultLevel)[keyof typeof ResultLevel]

export const InvestigationOutcome = {
  INVESTIGATED: 'INVESTIGATED',
  ESCALATED: 'ESCALATED',
  FAILED: 'FAILED',
} as const

export type InvestigationOutcome =
  (typeof InvestigationOutcome)[keyof typeof InvestigationOutcome]

export const EvidenceSource = {
  PAYMENT: 'PAYMENT',
  SETTLEMENT: 'SETTLEMENT',
  BANK: 'BANK',
  DETERMINISTIC: 'DETERMINISTIC',
} as const

export type EvidenceSource = (typeof EvidenceSource)[keyof typeof EvidenceSource]

export const GuardrailViolation = {
  EXCEPTION_ID_MISMATCH: 'EXCEPTION_ID_MISMATCH',
  UNSUPPORTED_CLASSIFICATION: 'UNSUPPORTED_CLASSIFICATION',
  HALLUCINATED_EVIDENCE_REFERENCE: 'HALLUCINATED_EVIDENCE_REFERENCE',
  NO_SUPPORTING_EVIDENCE: 'NO_SUPPORTING_EVIDENCE',
  CLAIMED_FINANCIAL_MODIFICATION: 'CLAIMED_FINANCIAL_MODIFICATION',
  CONFIDENCE_BELOW_THRESHOLD: 'CONFIDENCE_BELOW_THRESHOLD',
  CONTRADICTORY_EVIDENCE: 'CONTRADICTORY_EVIDENCE',
  CLASSIFICATION_DISAGREES_WITH_ENGINE: 'CLASSIFICATION_DISAGREES_WITH_ENGINE',
  UNGROUNDED_IDENTIFIER_IN_PROSE: 'UNGROUNDED_IDENTIFIER_IN_PROSE',
} as const

export type GuardrailViolation =
  (typeof GuardrailViolation)[keyof typeof GuardrailViolation]

export const ELIGIBLE_STATUSES: readonly ReconciliationStatus[] = [
  ReconciliationStatus.UNKNOWN,
  ReconciliationStatus.AMOUNT_MISMATCH,
  ReconciliationStatus.MISSING_BANK_CREDIT,
  ReconciliationStatus.UNMATCHED_REFERENCE,
  ReconciliationStatus.REFUND_MISMATCH,
]

export type EvidenceItem = {
  evidence_id: string
  source: EvidenceSource
  record_id: string
  field: string
  value: string
  relevance: string
}

export type InvestigationContext = {
  exception_id: string
  deterministic_status: ReconciliationStatus
  result_level: ResultLevel
  rule_applied?: string | null
  message?: string | null
  identifiers: Record<string, string>
  evidence: EvidenceItem[]
  allowed_classifications: ReconciliationStatus[]
  evidence_dropped_count: number
}

export type AIInvestigation = {
  exception_id: string
  finding: string
  classification: ReconciliationStatus
  confidence: number
  supporting_evidence: string[]
  contradictory_evidence: string[]
  recommendation: string
  human_review_required: boolean
  financial_records_modified: boolean
}

export type InvestigationRecord = {
  exception_id: string
  deterministic_status: ReconciliationStatus
  deterministic_rule?: string | null
  result_level: ResultLevel
  outcome: InvestigationOutcome
  investigation?: AIInvestigation | null
  human_review_required: boolean
  guardrail_violations: GuardrailViolation[]
  invalid_evidence_references: string[]
  failure_reason?: string | null
  evidence_count: number
  evidence_dropped_count: number
  financial_records_modified: boolean
}

export type InvestigationReport = {
  records: InvestigationRecord[]
  total_results: number
  eligible_exceptions: number
  skipped_not_eligible: number
  investigated: number
  escalated: number
  failed: number
  human_review_required_count: number
  financial_records_modified: boolean
}

export type InvestigationBundle = {
  record: InvestigationRecord
  context: InvestigationContext | null
}
