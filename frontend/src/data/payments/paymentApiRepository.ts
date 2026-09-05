import type { Payment } from '../../types/payment'
import type { PaymentRepository } from './paymentRepository'

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
  return `Unable to load payments (${status})`
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

export const paymentApiRepository: PaymentRepository = {
  async list() {
    const response = await fetch('/api/payments')
    await rejectIfNotOk(response)
    return readJson<Payment[]>(response)
  },

  async getById(paymentId: string) {
    const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}`)
    if (response.status === 404) return null
    await rejectIfNotOk(response)
    return readJson<Payment>(response)
  },
}
