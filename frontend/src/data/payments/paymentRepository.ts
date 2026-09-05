import type { Payment } from '../../types/payment'

/**
 * Data-access contract for payments.
 * UI code should import only this module.
 */
export interface PaymentRepository {
  list(): Promise<Payment[]>
  getById(paymentId: string): Promise<Payment | null>
}

export { paymentApiRepository as paymentRepository } from './paymentApiRepository'
