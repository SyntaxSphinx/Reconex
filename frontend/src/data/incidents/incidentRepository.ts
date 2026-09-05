import type { Incident } from '../../types/incident'

/**
 * Incidents have no backend domain model. This repository stays mock-only
 * and must not import payment, investigation, or run API repositories.
 * UI code should import only this module.
 */
export interface IncidentRepository {
  list(): Promise<Incident[]>
  getById(incidentId: string): Promise<Incident | null>
}

export { mockIncidentRepository as incidentRepository } from './mockIncidentRepository'
