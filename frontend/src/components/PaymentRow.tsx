import { Link } from 'react-router-dom'
import {
  PAYMENT_STATUS_LABELS,
  STATUS_LABELS,
  formatPaiseAsInr,
  formatPaymentTime,
  paymentStatusClass,
  reconStatusClass,
  settlementReference,
} from '../lib/paymentDisplay'
import { paymentDetailPath } from '../lib/paymentQuery'
import type { Payment } from '../types/payment'

type PaymentRowProps = {
  payment: Payment
}

export function PaymentRow({ payment }: PaymentRowProps) {
  const reference = settlementReference(payment)

  return (
    <Link to={paymentDetailPath(payment.payment_id)} className="inv-queue-row pay-row">
      <div className="inv-queue-main">
        <div className="inv-primary">
          <span className="inv-id">{payment.payment_id}</span>
          <span className="inv-sep text-tertiary">/</span>
          <span className="inv-type">{payment.order_id}</span>
        </div>
        <div className="inv-meta inc-row-meta">
          <span className="inv-meta-item">
            <span className="text-tertiary">Amount</span>
            <span className="mono">{formatPaiseAsInr(payment.amount_paise)}</span>
          </span>
          <span className="inv-meta-item">
            <span className="text-tertiary">Paid</span>
            <span>{formatPaymentTime(payment.payment_date)} IST</span>
          </span>
          {reference && (
            <span className="inv-meta-item">
              <span className="text-tertiary">
                {payment.settlement_utr ? 'UTR' : 'Settlement'}
              </span>
              <code>{reference}</code>
            </span>
          )}
        </div>
      </div>
      <div className="inc-row-flags pay-row-flags">
        <span className={`pay-status ${paymentStatusClass(payment.payment_status)}`}>
          {PAYMENT_STATUS_LABELS[payment.payment_status]}
        </span>
        <span
          className={`pay-recon ${reconStatusClass(payment.reconciliation_status)}`}
        >
          {STATUS_LABELS[payment.reconciliation_status]}
        </span>
      </div>
    </Link>
  )
}
