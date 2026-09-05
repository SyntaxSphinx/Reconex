import type { CurrentRun, ReconciliationHealthPoint } from '../../types/overview'

/**
 * Data-access contract for Overview metrics.
 * UI code should import only this module.
 */
export interface OverviewRepository {
  getReconciliationHealth(): Promise<ReconciliationHealthPoint[]>
  getCurrentRun(): Promise<CurrentRun | null>
  createRun(scenario?: string): Promise<CurrentRun>
}

export { overviewApiRepository as overviewRepository } from './overviewApiRepository'
