import type { AnalyticsRepository } from './analyticsRepository'
import { MOCK_ANALYTICS_WORKSPACE } from './mockAnalyticsData'

export const mockAnalyticsRepository: AnalyticsRepository = {
  async getWorkspace() {
    return MOCK_ANALYTICS_WORKSPACE
  },
}
