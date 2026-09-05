import type { ReconciliationHealthPoint } from './overview'
import {
  InvestigationOutcome,
  type InvestigationRecord,
  type ReconciliationStatus,
} from './investigation'

/**
 * Analytics contracts. Field names match GET /api/analytics.
 */

export const AnalyticsRange = {
  DAYS_7: 7,
  DAYS_14: 14,
  DAYS_30: 30,
} as const

export type AnalyticsRange = (typeof AnalyticsRange)[keyof typeof AnalyticsRange]

export const ANALYTICS_EXCEPTION_TYPES = [
  'AMOUNT_MISMATCH',
  'MISSING_BANK_CREDIT',
  'UNKNOWN',
  'UNMATCHED_REFERENCE',
  'REFUND_MISMATCH',
  'DUPLICATE',
  'MISSING_SETTLEMENT',
] as const

export type AnalyticsExceptionType = (typeof ANALYTICS_EXCEPTION_TYPES)[number]

export type ExceptionTrendDay = {
  date: string
  counts: Record<AnalyticsExceptionType, number>
}

export type ExceptionImpactRow = {
  type: AnalyticsExceptionType
  count: number
  impact_paise: number
}

export type AnalyticsWorkspace = {
  as_of: string
  reconciliation: ReconciliationHealthPoint[]
  exception_trend: ExceptionTrendDay[]
  distribution: ExceptionImpactRow[]
  investigations: InvestigationRecord[]
}

export type OutcomeRollup = {
  total: number
  counts: Record<(typeof InvestigationOutcome)[keyof typeof InvestigationOutcome], number>
  confidence_values: number[]
}

export type { ReconciliationStatus }
