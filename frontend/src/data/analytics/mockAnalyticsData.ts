import { MOCK_RECONCILIATION_HEALTH } from '../overview/mockReconciliationHealth'
import { MOCK_INVESTIGATION_BUNDLES } from '../investigations/mockInvestigationData'
import type { ReconciliationHealthPoint } from '../../types/overview'
import {
  type AnalyticsExceptionType,
  type AnalyticsWorkspace,
  type ExceptionImpactRow,
  type ExceptionTrendDay,
} from '../../types/analytics'

/**
 * Earlier daily runs that extend Overview health to a 30-day window.
 * 14-day and 7-day views reuse MOCK_RECONCILIATION_HEALTH as-is.
 */
const EARLIER_HEALTH: ReconciliationHealthPoint[] = [
  { run_id: 'run_2026_08_06', run_date: '2026-08-06', reconciliation_rate: 93.1, payments_processed: 968 },
  { run_id: 'run_2026_08_07', run_date: '2026-08-07', reconciliation_rate: 93.4, payments_processed: 981 },
  { run_id: 'run_2026_08_08', run_date: '2026-08-08', reconciliation_rate: 92.8, payments_processed: 990 },
  { run_id: 'run_2026_08_09', run_date: '2026-08-09', reconciliation_rate: 93.9, payments_processed: 1003 },
  { run_id: 'run_2026_08_10', run_date: '2026-08-10', reconciliation_rate: 94.2, payments_processed: 995 },
  { run_id: 'run_2026_08_11', run_date: '2026-08-11', reconciliation_rate: 94.0, payments_processed: 987 },
  { run_id: 'run_2026_08_12', run_date: '2026-08-12', reconciliation_rate: 93.5, payments_processed: 1012 },
  { run_id: 'run_2026_08_13', run_date: '2026-08-13', reconciliation_rate: 94.6, payments_processed: 998 },
  { run_id: 'run_2026_08_14', run_date: '2026-08-14', reconciliation_rate: 95.0, payments_processed: 1006 },
  { run_id: 'run_2026_08_15', run_date: '2026-08-15', reconciliation_rate: 94.3, payments_processed: 991 },
  { run_id: 'run_2026_08_16', run_date: '2026-08-16', reconciliation_rate: 93.8, payments_processed: 1009 },
  { run_id: 'run_2026_08_17', run_date: '2026-08-17', reconciliation_rate: 94.1, payments_processed: 1001 },
  { run_id: 'run_2026_08_18', run_date: '2026-08-18', reconciliation_rate: 94.7, payments_processed: 984 },
  { run_id: 'run_2026_08_19', run_date: '2026-08-19', reconciliation_rate: 95.2, payments_processed: 1016 },
  { run_id: 'run_2026_08_20', run_date: '2026-08-20', reconciliation_rate: 94.4, payments_processed: 992 },
  { run_id: 'run_2026_08_21', run_date: '2026-08-21', reconciliation_rate: 94.5, payments_processed: 1005 },
]

const RECONCILIATION: ReconciliationHealthPoint[] = [
  ...EARLIER_HEALTH,
  ...MOCK_RECONCILIATION_HEALTH,
]

/**
 * Daily new exceptions by type. Recent days follow the incident story
 * (refund cycle, settlement delay, credit gap, amount cluster).
 * Counts are [amount, missing bank, unknown, unmatched, refund].
 */
const DAILY_COUNTS: Record<string, [number, number, number, number, number]> = {
  '2026-08-06': [1, 0, 1, 0, 0],
  '2026-08-07': [1, 1, 0, 0, 0],
  '2026-08-08': [2, 0, 1, 1, 0],
  '2026-08-09': [1, 1, 0, 0, 0],
  '2026-08-10': [2, 1, 1, 0, 0],
  '2026-08-11': [1, 0, 0, 1, 0],
  '2026-08-12': [2, 1, 1, 0, 0],
  '2026-08-13': [1, 1, 0, 0, 1],
  '2026-08-14': [2, 0, 1, 0, 0],
  '2026-08-15': [1, 1, 0, 1, 0],
  '2026-08-16': [2, 1, 1, 0, 0],
  '2026-08-17': [1, 0, 0, 0, 0],
  '2026-08-18': [2, 1, 1, 0, 1],
  '2026-08-19': [1, 1, 0, 0, 0],
  '2026-08-20': [2, 1, 1, 1, 0],
  '2026-08-21': [2, 1, 0, 0, 0],
  '2026-08-22': [2, 1, 1, 0, 0],
  '2026-08-23': [1, 1, 0, 1, 0],
  '2026-08-24': [3, 1, 1, 0, 0],
  '2026-08-25': [2, 2, 1, 0, 1],
  '2026-08-26': [2, 1, 0, 1, 0],
  '2026-08-27': [1, 1, 1, 0, 0],
  '2026-08-28': [2, 1, 0, 0, 0],
  '2026-08-29': [2, 1, 1, 0, 1],
  '2026-08-30': [3, 2, 1, 1, 2],
  '2026-08-31': [2, 1, 1, 0, 1],
  '2026-09-01': [3, 3, 1, 0, 0],
  '2026-09-02': [3, 4, 1, 1, 1],
  '2026-09-03': [6, 5, 2, 1, 1],
  '2026-09-04': [5, 6, 2, 3, 1],
}

function countsFor(tuple: [number, number, number, number, number]) {
  return {
    AMOUNT_MISMATCH: tuple[0],
    MISSING_BANK_CREDIT: tuple[1],
    UNKNOWN: tuple[2],
    UNMATCHED_REFERENCE: tuple[3],
    REFUND_MISMATCH: tuple[4],
    DUPLICATE: 0,
    MISSING_SETTLEMENT: 0,
  } satisfies Record<AnalyticsExceptionType, number>
}

const EXCEPTION_TREND: ExceptionTrendDay[] = RECONCILIATION.map((point) => ({
  date: point.run_date,
  counts: countsFor(DAILY_COUNTS[point.run_date] ?? [0, 0, 0, 0, 0]),
}))

/**
 * Current exception book — same totals and impact as Overview Exception Profile.
 */
const DISTRIBUTION: ExceptionImpactRow[] = [
  { type: 'AMOUNT_MISMATCH', count: 42, impact_paise: 24560000 },
  { type: 'MISSING_BANK_CREDIT', count: 28, impact_paise: 87634000 },
  { type: 'UNKNOWN', count: 18, impact_paise: 14289000 },
  { type: 'UNMATCHED_REFERENCE', count: 8, impact_paise: 6720000 },
  { type: 'REFUND_MISMATCH', count: 4, impact_paise: 2450000 },
]

export const MOCK_ANALYTICS_WORKSPACE: AnalyticsWorkspace = {
  as_of: '2026-09-04',
  reconciliation: RECONCILIATION,
  exception_trend: EXCEPTION_TREND,
  distribution: DISTRIBUTION,
  investigations: MOCK_INVESTIGATION_BUNDLES.map((bundle) => bundle.record),
}
