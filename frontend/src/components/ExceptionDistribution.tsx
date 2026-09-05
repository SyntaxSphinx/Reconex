import { Link } from 'react-router-dom'
import { STATUS_LABELS, typeTone } from '../lib/analyticsDisplay'
import { investigationsPath } from '../lib/investigationQuery'
import { paymentsPath } from '../lib/paymentQuery'
import { ELIGIBLE_STATUSES } from '../types/investigation'
import type { AnalyticsExceptionType, ExceptionImpactRow } from '../types/analytics'

const SIZE = 156
const STROKE = 18
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function ExceptionDistribution({
  rows,
  selectedType,
  hoveredType,
  onHoverType,
  onSelectType,
  periodLabel,
}: {
  rows: ExceptionImpactRow[]
  selectedType: AnalyticsExceptionType | 'all'
  hoveredType: AnalyticsExceptionType | null
  onHoverType: (type: AnalyticsExceptionType | null) => void
  onSelectType: (type: AnalyticsExceptionType | 'all') => void
  periodLabel: string
}) {
  const ranked = [...rows].sort((a, b) => b.count - a.count)
  const total = ranked.reduce((sum, row) => sum + row.count, 0)
  const focus = hoveredType ?? (selectedType === 'all' ? null : selectedType)

  if (total === 0) {
    return (
      <p className="text-secondary">
        No payment exceptions were recorded in the current run.
      </p>
    )
  }

  const focusRow = focus ? ranked.find((row) => row.type === focus) : null
  const centerShare = focusRow
    ? Math.round((focusRow.count / total) * 100)
    : null

  const dashes = ranked.map((row) => (row.count / total) * CIRCUMFERENCE)
  const arcs = ranked.map((row, index) => ({
    row,
    dash: dashes[index],
    offset: dashes.slice(0, index).reduce((sum, dash) => sum + dash, 0),
  }))

  return (
    <div className="an-dist">
      <div className="an-donut-wrap" aria-hidden="true">
        <svg
          className="an-donut"
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
        >
          <circle
            className="an-donut-track"
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
          />
          {arcs.map(({ row, dash, offset: start }) => {
            const muted = Boolean(focus && focus !== row.type)
            return (
              <circle
                key={row.type}
                className={`an-donut-arc an-tone-${typeTone(row.type)}${
                  muted ? ' is-muted' : ''
                }`}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
                strokeDashoffset={-start}
                onMouseEnter={() => onHoverType(row.type)}
                onMouseLeave={() => onHoverType(null)}
                onClick={() =>
                  onSelectType(selectedType === row.type ? 'all' : row.type)
                }
              />
            )
          })}
        </svg>
        <div className="an-donut-center">
          <p className="an-donut-value mono">
            {centerShare != null ? `${centerShare}%` : total}
          </p>
          <p className="an-donut-label">
            {focusRow ? STATUS_LABELS[focusRow.type] : 'payment exceptions'}
          </p>
          {!focusRow && (
            <p className="an-donut-period">{periodLabel.toLowerCase()}</p>
          )}
        </div>
      </div>

      <div className="an-dist-list">
        {ranked.map((row) => {
          const active = selectedType === row.type
          const muted = Boolean(focus && focus !== row.type)
          const share = Math.round((row.count / total) * 100)
          return (
            <div
              key={row.type}
              className={`an-dist-row${active ? ' is-active' : ''}${
                muted ? ' is-muted' : ''
              }`}
            >
              <button
                type="button"
                className="an-dist-hit"
                onMouseEnter={() => onHoverType(row.type)}
                onMouseLeave={() => onHoverType(null)}
                onClick={() => onSelectType(active ? 'all' : row.type)}
              >
                <span className="an-dist-name">
                  <span className={`an-swatch an-tone-${typeTone(row.type)}`} />
                  {STATUS_LABELS[row.type]}
                </span>
                <span className="an-dist-count mono">{row.count}</span>
                <span className="an-dist-share text-tertiary">{share}%</span>
              </button>
              {active && (
                <Link
                  className="an-dist-link"
                  to={
                    (ELIGIBLE_STATUSES as readonly string[]).includes(row.type)
                      ? investigationsPath({ queue: 'all', type: row.type })
                      : paymentsPath({ recon: row.type })
                  }
                >
                  {(ELIGIBLE_STATUSES as readonly string[]).includes(row.type)
                    ? 'View investigations'
                    : 'View payments'}
                </Link>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
