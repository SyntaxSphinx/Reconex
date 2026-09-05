import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { usePayment } from '../hooks/usePayments'
import { incidentDetailPath } from '../lib/incidentQuery'
import { investigationDetailPath } from '../lib/investigationQuery'
import {
  PAYMENT_STATUS_LABELS,
  STATUS_LABELS,
  formatPaiseAsInr,
  formatPaymentTime,
  hasVariance,
  paymentStatusClass,
  reconStatusClass,
} from '../lib/paymentDisplay'
import type { Payment } from '../types/payment'

export function PaymentDetailPage() {
  const { paymentId } = useParams()
  const decodedId = paymentId ? decodeURIComponent(paymentId) : undefined
  const { payment, error } = usePayment(decodedId)

  if (error) {
    return (
      <div className="page">
        <DetailBackLink />
        <EmptyState title="Unable to load payment" description={error} />
      </div>
    )
  }

  if (payment === undefined) {
    return (
      <div className="page">
        <DetailBackLink />
        <p className="text-secondary">Loading payment…</p>
      </div>
    )
  }

  if (payment === null) {
    return (
      <div className="page">
        <DetailBackLink />
        <EmptyState
          title="Payment not found"
          description="No payment exists for this ID in the current reconciliation run."
        />
      </div>
    )
  }

  return <PaymentDetail payment={payment} />
}

function DetailBackLink() {
  return (
    <p className="detail-back">
      <Link to="/payments">Payments</Link>
    </p>
  )
}

function PaymentDetail({ payment }: { payment: Payment }) {
  const showRefund =
    payment.refund_amount_paise !== null ||
    payment.settlement_refund_amount_paise !== null

  return (
    <div className="page detail-page">
      <DetailBackLink />

      <header className="detail-header">
        <div>
          <p className="inc-detail-kicker">{payment.order_id}</p>
          <h1 className="detail-title">{payment.payment_id}</h1>
          <p className="detail-header-meta">
            {payment.method.trim() ? (
              <>
                {payment.method}
                <span className="detail-header-dot" aria-hidden="true">
                  ·
                </span>
              </>
            ) : null}
            {formatPaymentTime(payment.payment_date)} IST
          </p>
        </div>
        <div className="inc-row-flags">
          <span className={`pay-status ${paymentStatusClass(payment.payment_status)}`}>
            {PAYMENT_STATUS_LABELS[payment.payment_status]}
          </span>
          <span
            className={`pay-recon ${reconStatusClass(payment.reconciliation_status)}`}
          >
            {STATUS_LABELS[payment.reconciliation_status]}
          </span>
        </div>
      </header>

      <section className="detail-section" aria-labelledby="pay-info-label">
        <h2 className="detail-section-label" id="pay-info-label">
          Payment
        </h2>
        <dl className="inc-impact">
          <div>
            <dt>Amount</dt>
            <dd className="mono">{formatPaiseAsInr(payment.amount_paise)}</dd>
          </div>
          <div>
            <dt>Currency</dt>
            <dd>{payment.currency}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{PAYMENT_STATUS_LABELS[payment.payment_status]}</dd>
          </div>
        </dl>
        <dl className="detail-ids">
          <div className="detail-id">
            <dt>Order ID</dt>
            <dd className="mono">{payment.order_id}</dd>
          </div>
          <div className="detail-id">
            <dt>Payment date</dt>
            <dd>{formatPaymentTime(payment.payment_date)} IST</dd>
          </div>
          {payment.method.trim() ? (
            <div className="detail-id">
              <dt>Method</dt>
              <dd>{payment.method}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <section className="detail-section" aria-labelledby="pay-settlement-label">
        <h2 className="detail-section-label" id="pay-settlement-label">
          Settlement
        </h2>
        {payment.settlement_id ? (
          <dl className="detail-ids">
            <div className="detail-id">
              <dt>Settlement ID</dt>
              <dd className="mono">{payment.settlement_id}</dd>
            </div>
            <div className="detail-id">
              <dt>UTR</dt>
              <dd className="mono">{payment.settlement_utr ?? '—'}</dd>
            </div>
            <div className="detail-id">
              <dt>Settlement amount</dt>
              <dd className="mono">
                {payment.settlement_amount_paise !== null
                  ? formatPaiseAsInr(payment.settlement_amount_paise)
                  : '—'}
              </dd>
            </div>
            {showRefund && (
              <>
                <div className="detail-id">
                  <dt>Payment refund</dt>
                  <dd className="mono">
                    {payment.refund_amount_paise !== null
                      ? formatPaiseAsInr(payment.refund_amount_paise)
                      : '—'}
                  </dd>
                </div>
                <div className="detail-id">
                  <dt>Settlement refund</dt>
                  <dd className="mono">
                    {payment.settlement_refund_amount_paise !== null
                      ? formatPaiseAsInr(payment.settlement_refund_amount_paise)
                      : '—'}
                  </dd>
                </div>
              </>
            )}
          </dl>
        ) : (
          <p className="text-secondary">
            No settlement line is attached to this payment yet.
          </p>
        )}
      </section>

      <section className="detail-section" aria-labelledby="pay-recon-label">
        <h2 className="detail-section-label" id="pay-recon-label">
          Reconciliation
        </h2>
        <p className="detail-engine-type">
          {STATUS_LABELS[payment.reconciliation_status]}
        </p>
        {hasVariance(payment) && payment.variance_paise !== null && (
          <dl className="inc-impact pay-variance">
            <div>
              <dt>Variance</dt>
              <dd className="mono">{formatPaiseAsInr(payment.variance_paise)}</dd>
            </div>
          </dl>
        )}
        <p className="detail-engine-copy">{payment.result_summary}</p>
      </section>

      <section className="detail-section" aria-labelledby="pay-related-label">
        <h2 className="detail-section-label" id="pay-related-label">
          Related records
        </h2>
        {payment.investigation_id || payment.incident_ids.length > 0 ? (
          <dl className="detail-ids">
            {payment.investigation_id && (
              <div className="detail-id">
                <dt>Investigation</dt>
                <dd>
                  <Link
                    className="pay-related-link"
                    to={investigationDetailPath(payment.investigation_id)}
                  >
                    {payment.investigation_id}
                  </Link>
                </dd>
              </div>
            )}
            {payment.incident_ids.length > 0 && (
              <div className="detail-id">
                <dt>
                  {payment.incident_ids.length === 1 ? 'Incident' : 'Incidents'}
                </dt>
                <dd>
                  <ul className="inc-related">
                    {payment.incident_ids.map((incidentId) => (
                      <li key={incidentId}>
                        <Link to={incidentDetailPath(incidentId)}>{incidentId}</Link>
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
            )}
          </dl>
        ) : (
          <p className="text-secondary">
            This payment is not linked to an investigation or incident.
          </p>
        )}
      </section>
    </div>
  )
}
