import type { ReconciliationStatus } from './investigation'

/**
 * Frontend-only payment contracts for the operations console mock.
 * Isolated so a real API repository can replace the mock without changing UI code.
 */

export const PaymentStatus = {
  AUTHORIZED: 'authorized',
  CAPTURED: 'captured',
  REFUNDED: 'refunded',
  FAILED: 'failed',
} as const

export type PaymentStatus = (typeof PaymentStatus)[keyof typeof PaymentStatus]

export type Payment = {
  payment_id: string
  order_id: string
  amount_paise: number
  currency: 'INR'
  payment_date: string
  payment_status: PaymentStatus
  reconciliation_status: ReconciliationStatus
  method: string
  settlement_id: string | null
  settlement_utr: string | null
  settlement_amount_paise: number | null
  variance_paise: number | null
  refund_amount_paise: number | null
  settlement_refund_amount_paise: number | null
  result_summary: string
  investigation_id: string | null
  incident_ids: string[]
}
