import type { OverviewRepository } from './overviewRepository'
import { MOCK_RECONCILIATION_HEALTH } from './mockReconciliationHealth'

/** Unused leftover. Overview reads overviewApiRepository. */
export const mockOverviewRepository: OverviewRepository = {
  async getReconciliationHealth() {
    return MOCK_RECONCILIATION_HEALTH
  },

  async getCurrentRun() {
    return null
  },

  async createRun() {
    throw new Error('Mock overview repository does not execute runs')
  },
}
