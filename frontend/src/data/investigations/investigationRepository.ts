import type {
  InvestigationBundle,
  InvestigationReport,
} from '../../types/investigation'

/**
 * Data-access contract for investigations.
 * UI code should import only this module.
 */
export interface InvestigationRepository {
  getReport(): Promise<InvestigationReport>
  list(): Promise<InvestigationBundle[]>
  getByExceptionId(exceptionId: string): Promise<InvestigationBundle | null>
}

export { investigationApiRepository as investigationRepository } from './investigationApiRepository'
