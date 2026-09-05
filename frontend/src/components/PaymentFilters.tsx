import {
  PAYMENT_STATUS_OPTIONS,
  RECON_STATUS_OPTIONS,
} from '../lib/paymentDisplay'
import {
  PAYMENT_RECON_EXCEPTIONS,
  type PaymentReconFilter,
} from '../lib/paymentQuery'
import type { PaymentStatus } from '../types/payment'

type PaymentFiltersProps = {
  paymentStatus: PaymentStatus | 'all'
  reconStatus: PaymentReconFilter
  search: string
  onPaymentStatusChange: (value: PaymentStatus | 'all') => void
  onReconStatusChange: (value: PaymentReconFilter) => void
  onSearchChange: (value: string) => void
}

export function PaymentFilters({
  paymentStatus,
  reconStatus,
  search,
  onPaymentStatusChange,
  onReconStatusChange,
  onSearchChange,
}: PaymentFiltersProps) {
  return (
    <div className="inv-controls">
      <div className="inv-control-fields pay-control-fields">
        <label className="inv-select-label">
          <span className="visually-hidden">Payment status</span>
          <select
            className="inv-select"
            value={paymentStatus}
            onChange={(event) =>
              onPaymentStatusChange(
                event.target.value === 'all'
                  ? 'all'
                  : (event.target.value as PaymentStatus),
              )
            }
          >
            <option value="all">All payment statuses</option>
            {PAYMENT_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="inv-select-label">
          <span className="visually-hidden">Reconciliation status</span>
          <select
            className="inv-select"
            value={reconStatus}
            onChange={(event) => {
              const next = event.target.value
              if (next === 'all') onReconStatusChange('all')
              else if (next === PAYMENT_RECON_EXCEPTIONS) {
                onReconStatusChange(PAYMENT_RECON_EXCEPTIONS)
              } else onReconStatusChange(next as PaymentReconFilter)
            }}
          >
            <option value="all">All reconciliation statuses</option>
            <option value={PAYMENT_RECON_EXCEPTIONS}>Payment exceptions</option>
            {RECON_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="inv-search-label">
          <span className="visually-hidden">Search by payment ID or order ID</span>
          <input
            type="search"
            className="inv-search"
            placeholder="Search by payment ID or order ID"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </label>
      </div>
    </div>
  )
}
