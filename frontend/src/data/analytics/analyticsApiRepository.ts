import type { AnalyticsWorkspace } from '../../types/analytics'
import { apiGet } from '../http'
import type { AnalyticsRepository } from './analyticsRepository'

export const analyticsApiRepository: AnalyticsRepository = {
  async getWorkspace() {
    return apiGet<AnalyticsWorkspace>('/api/analytics', 'Unable to load analytics')
  },
}
