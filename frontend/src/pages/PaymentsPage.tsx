import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { PaymentFilters } from '../components/PaymentFilters'
import { PaymentRow } from '../components/PaymentRow'
import { usePaymentList } from '../hooks/usePayments'
import {
  isPaymentExceptionStatus,
  matchesPaymentSearch,
} from '../lib/paymentDisplay'
import {
  PAYMENT_RECON_EXCEPTIONS,
  parsePaymentStatus,
  parseReconStatus,
  type PaymentReconFilter,
} from '../lib/paymentQuery'
import type { PaymentStatus } from '../types/payment'

export function PaymentsPage() {
  const { items, error } = usePaymentList()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')

  const paymentStatus = parsePaymentStatus(searchParams.get('status')) ?? 'all'
  const reconStatus = parseReconStatus(searchParams.get('recon')) ?? 'all'

  function updateParam(key: string, value: string, defaultValue: string) {
    const params = new URLSearchParams(searchParams)
    if (value === defaultValue) params.delete(key)
    else params.set(key, value)
    setSearchParams(params, { replace: true })
  }

  const visible = useMemo(() => {
    if (!items) return []
    return items.filter((payment) => {
      if (paymentStatus !== 'all' && payment.payment_status !== paymentStatus) {
        return false
      }
      if (reconStatus === PAYMENT_RECON_EXCEPTIONS) {
        if (!isPaymentExceptionStatus(payment.reconciliation_status)) return false
      } else if (
        reconStatus !== 'all' &&
        payment.reconciliation_status !== reconStatus
      ) {
        return false
      }
      return matchesPaymentSearch(payment, search)
    })
  }, [items, paymentStatus, reconStatus, search])

  const hasActiveSearch = search.trim().length > 0
  const hasActiveFilters = paymentStatus !== 'all' || reconStatus !== 'all'

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Payments</h1>
          <p className="text-secondary">
            Inspect captured payments, settlement references, and reconciliation
            outcomes.
          </p>
        </div>
        <p className="page-header-count">
          {items === null
            ? '—'
            : reconStatus === PAYMENT_RECON_EXCEPTIONS
              ? `${visible.length} payment exceptions`
              : `${items.length} payments`}
        </p>
      </div>

      <PaymentFilters
        paymentStatus={paymentStatus}
        reconStatus={reconStatus}
        search={search}
        onPaymentStatusChange={(next: PaymentStatus | 'all') =>
          updateParam('status', next, 'all')
        }
        onReconStatusChange={(next: PaymentReconFilter) =>
          updateParam('recon', next, 'all')
        }
        onSearchChange={setSearch}
      />

      {items === null && !error && (
        <p className="text-secondary">Loading payments…</p>
      )}

      {error && (
        <EmptyState title="Unable to load payments" description={error} />
      )}

      {items !== null && items.length === 0 && !error && (
        <EmptyState
          title="No payments"
          description="There are no payments in the current dataset."
        />
      )}

      {items !== null && items.length > 0 && visible.length === 0 && (
        <EmptyState
          title={hasActiveSearch ? 'No search results' : 'No matching payments'}
          description={
            hasActiveSearch
              ? 'No payments match that payment ID or order ID.'
              : hasActiveFilters
                ? 'No payments match the selected filters.'
                : 'There are no payments to display.'
          }
        />
      )}

      {visible.length > 0 && (
        <div className="inv-queue" role="list">
          {visible.map((payment) => (
            <PaymentRow key={payment.payment_id} payment={payment} />
          ))}
        </div>
      )}
    </div>
  )
}
