import type {
  InvestigationBundle,
  InvestigationReport,
} from '../../types/investigation'
import type { InvestigationRepository } from './investigationRepository'

async function readJson<T>(response: Response): Promise<T> {
  return (await response.json()) as T
}

function errorMessage(status: number, detail: unknown): string {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (
    detail &&
    typeof detail === 'object' &&
    'detail' in detail &&
    typeof (detail as { detail: unknown }).detail === 'string'
  ) {
    return (detail as { detail: string }).detail
  }
  return `Unable to load investigations (${status})`
}

async function rejectIfNotOk(response: Response): Promise<void> {
  if (response.ok) return
  let detail: unknown
  try {
    detail = await response.json()
  } catch {
    detail = undefined
  }
  throw new Error(errorMessage(response.status, detail))
}

export const investigationApiRepository: InvestigationRepository = {
  async getReport() {
    const response = await fetch('/api/investigations/report')
    await rejectIfNotOk(response)
    return readJson<InvestigationReport>(response)
  },

  async list() {
    const response = await fetch('/api/investigations')
    await rejectIfNotOk(response)
    return readJson<InvestigationBundle[]>(response)
  },

  async getByExceptionId(exceptionId: string) {
    const response = await fetch(
      `/api/investigations/${encodeURIComponent(exceptionId)}`,
    )
    if (response.status === 404) return null
    await rejectIfNotOk(response)
    return readJson<InvestigationBundle>(response)
  },
}
