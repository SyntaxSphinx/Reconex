import type { CurrentRun, ReconciliationHealthPoint } from '../../types/overview'
import { apiGet, apiGetOrNull, apiPost } from '../http'
import type { OverviewRepository } from './overviewRepository'

export const overviewApiRepository: OverviewRepository = {
  async getReconciliationHealth() {
    return apiGet<ReconciliationHealthPoint[]>(
      '/api/runs',
      'Unable to load reconciliation health',
    )
  },

  async getCurrentRun() {
    return apiGetOrNull<CurrentRun>('/api/runs/current', 'Unable to load current run')
  },

  async createRun(scenario = 'normal') {
    return apiPost<CurrentRun>('/api/runs', 'Unable to run reconciliation', {
      scenario,
    })
  },
}
