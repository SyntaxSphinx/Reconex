/** Overview metrics used by the frontend. Isolated from investigation contracts. */

export type ReconciliationHealthPoint = {
  run_id: string
  run_date: string
  reconciliation_rate: number
  payments_processed: number
  scenario?: string
}

export type CurrentRun = {
  run_id: string
  run_date: string
  run_timestamp: string
  payments_processed: number
  reconciled_count: number
  pending_count: number
  exception_count: number
  reconciled_percent: number
  pending_percent: number
  exception_percent: number
  reconciliation_rate: number
  status_counts: Record<string, number>
  batch_status_counts: Record<string, number>
  impact_by_status: Record<string, number>
  scenario?: string
}
