import { Link } from 'react-router-dom'
import { InsightIcon } from '../assets/icons'
import {
  formatPaiseAsInr,
  leadingImpact,
  STATUS_LABELS,
} from '../lib/analyticsDisplay'
import { investigationsPath } from '../lib/investigationQuery'
import { paymentsPath } from '../lib/paymentQuery'
import { ELIGIBLE_STATUSES } from '../types/investigation'
import type { ExceptionImpactRow } from '../types/analytics'

function insightCopy(label: string, share: number): string {
  if (share >= 50) {
    return `${label} is driving the majority of financial impact.`
  }
  return `${label} accounts for the largest share of financial impact.`
}

export function OperationalInsight({
  rows,
  periodLabel,
}: {
  rows: ExceptionImpactRow[]
  periodLabel: string
}) {
  const lead = leadingImpact(rows)
  if (!lead) return null

  const label = STATUS_LABELS[lead.row.type]

  return (
    <section className="an-insight" aria-labelledby="an-insight-title">
      <div className="an-insight-panel">
        <div className="panel-heading">
          <InsightIcon />
          <h2 className="panel-label" id="an-insight-title">
            Operational insight
          </h2>
          <p className="an-section-note">{periodLabel}</p>
        </div>
        <p className="an-insight-copy">{insightCopy(label, lead.share)}</p>
        <dl className="an-insight-stats">
          <div>
            <dt>Total impact</dt>
            <dd className="mono">{formatPaiseAsInr(lead.row.impact_paise)}</dd>
          </div>
          <div>
            <dt>Share of impact</dt>
            <dd className="mono">{lead.share}%</dd>
          </div>
          {lead.row.count > 0 && (
            <div>
              <dt>Payment exceptions</dt>
              <dd className="mono">{lead.row.count}</dd>
            </div>
          )}
        </dl>
        <Link
          className="an-insight-link"
          to={
            (ELIGIBLE_STATUSES as readonly string[]).includes(lead.row.type)
              ? investigationsPath({ queue: 'all', type: lead.row.type })
              : paymentsPath({ recon: lead.row.type })
          }
        >
          {(ELIGIBLE_STATUSES as readonly string[]).includes(lead.row.type)
            ? 'View affected investigations'
            : 'View affected payments'}
        </Link>
      </div>
    </section>
  )
}
