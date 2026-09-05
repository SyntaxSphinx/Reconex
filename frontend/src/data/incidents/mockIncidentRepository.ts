import type { IncidentRepository } from './incidentRepository'
import { MOCK_INCIDENTS } from './mockIncidentData'

export const mockIncidentRepository: IncidentRepository = {
  async list() {
    return MOCK_INCIDENTS
  },

  async getById(incidentId: string) {
    return MOCK_INCIDENTS.find((incident) => incident.incident_id === incidentId) ?? null
  },
}
