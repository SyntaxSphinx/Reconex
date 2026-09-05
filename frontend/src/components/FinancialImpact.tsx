import {
  formatPaiseAsInr,
  leadingImpact,
  STATUS_LABELS,
  totalImpact,
  typeTone,
} from '../lib/analyticsDisplay'
import type { AnalyticsExceptionType, ExceptionImpactRow } from '../types/analytics'

export function FinancialImpact({
  rows,
  selectedType,
  hoveredType,
  onHoverType,
  onSelectType,
}: {
  rows: ExceptionImpactRow[]
  selectedType: AnalyticsExceptionType | 'all'
  hoveredType: AnalyticsExceptionType | null
  onHoverType: (type: AnalyticsExceptionType | null) => void
  onSelectType: (type: AnalyticsExceptionType | 'all') => void
}) {
  const focus = hoveredType ?? (selectedType === 'all' ? null : selectedType)
  const visible = focus ? rows.filter((row) => row.type === focus) : rows
  const total = totalImpact(visible)
  const grand = totalImpact(rows)
  const ranked = [...rows].sort((a, b) => b.impact_paise - a.impact_paise)
  const max = Math.max(1, ...ranked.map((row) => row.impact_paise))
  const lead = leadingImpact(rows)

  if (grand === 0) {
    return (
      <p className="text-secondary">
        No reconciliation variance was recorded in the current run.
      </p>
    )
  }

  const captionShare =
    focus && grand > 0
      ? Math.round((totalImpact(visible) / grand) * 100)
      : lead?.share

  return (
    <div className="an-impact">
      <p className="an-impact-total mono">{formatPaiseAsInr(total)}</p>
      <p className="an-impact-caption text-tertiary">
        {focus
          ? `${STATUS_LABELS[focus]} in the current run`
          : 'Ranked by reconciliation variance'}
        {captionShare != null ? ` · ${captionShare}% of impact` : ''}
      </p>
      <ul className="an-impact-list">
        {ranked.map((row, index) => {
          const active = selectedType === row.type
          const muted = Boolean(focus && focus !== row.type)
          const isLead = index === 0
          const share = Math.round((row.impact_paise / grand) * 100)
          return (
            <li key={row.type}>
              <button
                type="button"
                className={`an-impact-row${active ? ' is-active' : ''}${
                  muted ? ' is-muted' : ''
                }${isLead && !focus ? ' is-lead' : ''}`}
                onMouseEnter={() => onHoverType(row.type)}
                onMouseLeave={() => onHoverType(null)}
                onClick={() => onSelectType(active ? 'all' : row.type)}
              >
                <span className="an-impact-label">
                  <span className={`an-swatch an-tone-${typeTone(row.type)}`} />
                  {STATUS_LABELS[row.type]}
                </span>
                <span className="mono">{formatPaiseAsInr(row.impact_paise)}</span>
                <span className="an-dist-track an-impact-track" aria-hidden="true">
                  <span
                    className={`an-dist-bar an-tone-${typeTone(row.type)}`}
                    style={{ width: `${(row.impact_paise / max) * 100}%` }}
                  />
                </span>
                {isLead && (
                  <span className="an-impact-share text-tertiary">
                    {share}% of impact
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
