/**
 * Frontend-only incident contracts for the operations console mock.
 * Isolated from backend investigation models so a real API repository
 * can replace the mock without changing UI code.
 */

export const IncidentStatus = {
  OPEN: 'OPEN',
  INVESTIGATING: 'INVESTIGATING',
  RESOLVED: 'RESOLVED',
} as const

export type IncidentStatus = (typeof IncidentStatus)[keyof typeof IncidentStatus]

export const IncidentSeverity = {
  CRITICAL: 'CRITICAL',
  HIGH: 'HIGH',
  MEDIUM: 'MEDIUM',
  LOW: 'LOW',
} as const

export type IncidentSeverity =
  (typeof IncidentSeverity)[keyof typeof IncidentSeverity]

export const IncidentType = {
  BANK_CREDIT_GAP: 'BANK_CREDIT_GAP',
  AMOUNT_VARIANCE_CLUSTER: 'AMOUNT_VARIANCE_CLUSTER',
  REFERENCE_MISMATCH_CLUSTER: 'REFERENCE_MISMATCH_CLUSTER',
  REFUND_CYCLE: 'REFUND_CYCLE',
  SETTLEMENT_DELAY: 'SETTLEMENT_DELAY',
} as const

export type IncidentType = (typeof IncidentType)[keyof typeof IncidentType]

export type Incident = {
  incident_id: string
  title: string
  summary: string
  severity: IncidentSeverity
  status: IncidentStatus
  type: IncidentType
  affected_exception_count: number
  affected_payment_count: number
  impact_paise: number
  last_updated: string
  opened_at: string
  owner: string
  window: string
  notes: string
  exception_types: string[]
  related_investigation_ids: string[]
}
