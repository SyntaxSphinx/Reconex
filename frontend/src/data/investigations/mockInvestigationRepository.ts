import type { InvestigationRepository } from './investigationRepository'
import {
  MOCK_INVESTIGATION_BUNDLES,
  buildMockInvestigationReport,
} from './mockInvestigationData'

export const mockInvestigationRepository: InvestigationRepository = {
  async getReport() {
    return buildMockInvestigationReport(
      MOCK_INVESTIGATION_BUNDLES.map((bundle) => bundle.record),
    )
  },

  async list() {
    return MOCK_INVESTIGATION_BUNDLES
  },

  async getByExceptionId(exceptionId: string) {
    return (
      MOCK_INVESTIGATION_BUNDLES.find(
        (bundle) => bundle.record.exception_id === exceptionId,
      ) ?? null
    )
  },
}
