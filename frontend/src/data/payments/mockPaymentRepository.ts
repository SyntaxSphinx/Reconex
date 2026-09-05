import type { PaymentRepository } from './paymentRepository'
import { MOCK_PAYMENTS } from './mockPaymentData'

export const mockPaymentRepository: PaymentRepository = {
  async list() {
    return MOCK_PAYMENTS
  },

  async getById(paymentId: string) {
    return MOCK_PAYMENTS.find((payment) => payment.payment_id === paymentId) ?? null
  },
}
