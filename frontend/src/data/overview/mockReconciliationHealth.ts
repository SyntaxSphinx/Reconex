import type { ReconciliationHealthPoint } from '../../types/overview'

/** Recent daily runs ending on the latest Overview run (4 Sep 2026). */
export const MOCK_RECONCILIATION_HEALTH: ReconciliationHealthPoint[] = [
  { run_id: 'run_2026_08_22', run_date: '2026-08-22', reconciliation_rate: 94.8, payments_processed: 980 },
  { run_id: 'run_2026_08_23', run_date: '2026-08-23', reconciliation_rate: 95.1, payments_processed: 1002 },
  { run_id: 'run_2026_08_24', run_date: '2026-08-24', reconciliation_rate: 94.2, payments_processed: 996 },
  { run_id: 'run_2026_08_25', run_date: '2026-08-25', reconciliation_rate: 93.6, payments_processed: 1014 },
  { run_id: 'run_2026_08_26', run_date: '2026-08-26', reconciliation_rate: 94.0, payments_processed: 988 },
  { run_id: 'run_2026_08_27', run_date: '2026-08-27', reconciliation_rate: 95.4, payments_processed: 1008 },
  { run_id: 'run_2026_08_28', run_date: '2026-08-28', reconciliation_rate: 95.8, payments_processed: 1021 },
  { run_id: 'run_2026_08_29', run_date: '2026-08-29', reconciliation_rate: 94.9, payments_processed: 997 },
  { run_id: 'run_2026_08_30', run_date: '2026-08-30', reconciliation_rate: 93.2, payments_processed: 1005 },
  { run_id: 'run_2026_08_31', run_date: '2026-08-31', reconciliation_rate: 94.6, payments_processed: 1011 },
  { run_id: 'run_2026_09_01', run_date: '2026-09-01', reconciliation_rate: 95.7, payments_processed: 999 },
  { run_id: 'run_2026_09_02', run_date: '2026-09-02', reconciliation_rate: 96.1, payments_processed: 1004 },
  { run_id: 'run_2026_09_03', run_date: '2026-09-03', reconciliation_rate: 95.9, payments_processed: 1007 },
  { run_id: 'run_2026_09_04', run_date: '2026-09-04', reconciliation_rate: 96.4, payments_processed: 1000 },
]
