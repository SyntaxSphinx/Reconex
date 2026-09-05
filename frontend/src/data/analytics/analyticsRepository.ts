import type { AnalyticsWorkspace } from '../../types/analytics'

/**
 * Data-access contract for the analytics workspace.
 * UI code should import only this module.
 */
export interface AnalyticsRepository {
  getWorkspace(): Promise<AnalyticsWorkspace>
}

export { analyticsApiRepository as analyticsRepository } from './analyticsApiRepository'
