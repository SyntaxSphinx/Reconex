import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ANALYTICS_EXCEPTION_TYPES,
  formatAxisDate,
  formatTooltipDate,
  STATUS_LABELS,
  typeTone,
} from '../lib/analyticsDisplay'
import type {
  AnalyticsExceptionType,
  ExceptionTrendDay,
} from '../types/analytics'

const HEIGHT = 248
const PAD = { top: 12, right: 8, bottom: 36, left: 36 }

type HoveredSegment = {
  index: number
  type: AnalyticsExceptionType
}

function dayTotal(day: ExceptionTrendDay): number {
  return ANALYTICS_EXCEPTION_TYPES.reduce(
    (sum, type) => sum + (day.counts[type] ?? 0),
    0,
  )
}

function todayCount(
  days: ExceptionTrendDay[],
  type: AnalyticsExceptionType | 'all',
): number {
  const last = days[days.length - 1]
  if (!last) return 0
  return type === 'all' ? dayTotal(last) : (last.counts[type] ?? 0)
}

export function ExceptionTrendChart({
  days,
  selectedType,
  hoveredType,
  onHoverType,
  onSelectType,
  periodLabel,
}: {
  days: ExceptionTrendDay[]
  selectedType: AnalyticsExceptionType | 'all'
  hoveredType: AnalyticsExceptionType | null
  onHoverType: (type: AnalyticsExceptionType | null) => void
  onSelectType: (type: AnalyticsExceptionType | 'all') => void
  periodLabel: string
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(720)
  const [hover, setHover] = useState<HoveredSegment | null>(null)

  useEffect(() => {
    const node = wrapRef.current
    if (!node) return
    const update = () => setWidth(Math.max(node.clientWidth, 320))
    update()
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const { plotted, ticks, yMax, xTicks } = useMemo(() => {
    const plotW = width - PAD.left - PAD.right
    const plotH = HEIGHT - PAD.top - PAD.bottom
    const totals = days.map(dayTotal)
    const rawMax = Math.max(4, ...totals)
    const max = Math.ceil(rawMax / 2) * 2
    const step = max <= 6 ? 2 : max <= 12 ? 2 : 4
    const yTicks: number[] = []
    for (let tick = 0; tick <= max; tick += step) yTicks.push(tick)
    const last = days.length - 1
    const slot = last <= 0 ? plotW : plotW / days.length
    const barWidth = Math.max(5, Math.min(16, slot * 0.46))

    const plottedDays = days.map((day, index) => {
      const xCenter =
        PAD.left + (last <= 0 ? plotW / 2 : index * slot + slot / 2)
      const x = xCenter - barWidth / 2
      let yCursor = PAD.top + plotH
      const segments = ANALYTICS_EXCEPTION_TYPES.map((type) => {
        const count = day.counts[type] ?? 0
        const height = max === 0 ? 0 : (count / max) * plotH
        yCursor -= height
        return { type, count, x, y: yCursor, width: barWidth, height }
      })
      return { ...day, x: xCenter, total: dayTotal(day), segments }
    })

    const tickEvery = days.length > 14 ? 5 : days.length > 8 ? 2 : 1
    const labels = days
      .map((day, index) => ({ index, label: formatAxisDate(day.date) }))
      .filter((_, index) => {
        if (index === 0 || index === last) return true
        if (index % tickEvery !== 0) return false
        return last - index >= tickEvery
      })

    return { plotted: plottedDays, ticks: yTicks, yMax: max, xTicks: labels }
  }, [days, width])

  const plotH = HEIGHT - PAD.top - PAD.bottom
  const focusType = hoveredType ?? (selectedType === 'all' ? null : selectedType)
  const hoverDay = hover ? plotted[hover.index] : null
  const hoverSegment = hover
    ? hoverDay?.segments.find((segment) => segment.type === hover.type)
    : undefined
  const latest = todayCount(days, selectedType)
  const caption =
    selectedType === 'all'
      ? `Payment exceptions by stored run, stacked by type · ${periodLabel}`
      : `${STATUS_LABELS[selectedType]} by stored run · ${periodLabel}`

  return (
    <div>
      <div className="an-trend-meta">
        <p className="an-trend-caption text-tertiary">{caption}</p>
        {days.length > 0 && (
          <div className="an-trend-today">
            <p className="an-trend-today-value mono">{latest}</p>
            <p className="an-trend-today-label">
              {selectedType === 'all'
                ? latest === 1
                  ? 'exception this run'
                  : 'exceptions this run'
                : `${STATUS_LABELS[selectedType].toLowerCase()} this run`}
            </p>
          </div>
        )}
      </div>
      <div ref={wrapRef} className="health-chart an-trend-chart">
        <svg
          className="health-svg"
          width={width}
          height={HEIGHT}
          viewBox={`0 0 ${width} ${HEIGHT}`}
          aria-hidden="true"
        >
          {ticks.map((tick) => {
            const y = PAD.top + ((yMax - tick) / yMax) * plotH
            return (
              <g key={tick}>
                <line
                  className="health-grid"
                  x1={PAD.left}
                  x2={width - PAD.right}
                  y1={y}
                  y2={y}
                />
                <text
                  className="health-axis-label"
                  x={PAD.left - 8}
                  y={y + 4}
                  textAnchor="end"
                >
                  {tick}
                </text>
              </g>
            )
          })}

          <line
            className="an-stack-baseline"
            x1={PAD.left}
            x2={width - PAD.right}
            y1={PAD.top + plotH}
            y2={PAD.top + plotH}
          />

          {xTicks.map(({ index, label }) => (
            <text
              key={`${label}-${index}`}
              className="health-axis-label"
              x={plotted[index].x}
              y={HEIGHT - 10}
              textAnchor="middle"
            >
              {label}
            </text>
          ))}

          {plotted.map((day, index) =>
            day.segments
              .filter((segment) => segment.height > 0)
              .map((segment) => {
                const muted = Boolean(focusType && focusType !== segment.type)
                const active = hover?.index === index && hover.type === segment.type
                return (
                  <rect
                    key={`${day.date}-${segment.type}`}
                    className={`an-stack-seg an-tone-${typeTone(segment.type)}${
                      muted ? ' is-muted' : ''
                    }${active ? ' is-hover' : ''}`}
                    x={segment.x}
                    y={segment.y}
                    width={segment.width}
                    height={segment.height}
                    rx={1}
                    onMouseEnter={() => {
                      setHover({ index, type: segment.type })
                      onHoverType(segment.type)
                    }}
                    onMouseLeave={() => {
                      setHover(null)
                      onHoverType(null)
                    }}
                    onClick={() =>
                      onSelectType(
                        selectedType === segment.type ? 'all' : segment.type,
                      )
                    }
                  />
                )
              }),
          )}
        </svg>

        {hoverDay && hoverSegment && (
          <div
            className="health-tooltip an-trend-tooltip"
            style={{
              left: Math.min(Math.max(hoverDay.x, 108), width - 108),
              top: Math.max(hoverSegment.y - 8, 8),
              transform: 'translate(-50%, -100%)',
            }}
          >
            <p className="health-tooltip-date">{formatTooltipDate(hoverDay.date)}</p>
            <p className="an-trend-tooltip-type">
              <span
                className={`an-swatch an-tone-${typeTone(hoverSegment.type)}`}
              />
              {STATUS_LABELS[hoverSegment.type]}
            </p>
            <p className="health-tooltip-value">{hoverSegment.count}</p>
            <p className="health-tooltip-meta">
              {hoverSegment.count === 1 ? 'exception' : 'exceptions'}
            </p>
          </div>
        )}
      </div>

      <div className="an-legend" role="group" aria-label="Exception types">
        {ANALYTICS_EXCEPTION_TYPES.map((type) => {
          const active = selectedType === type
          const muted = Boolean(focusType && focusType !== type)
          const highlighted = hoveredType === type
          return (
            <button
              key={type}
              type="button"
              className={`an-legend-item${active ? ' is-active' : ''}${
                muted ? ' is-muted' : ''
              }${highlighted ? ' is-hover' : ''}`}
              onMouseEnter={() => onHoverType(type)}
              onMouseLeave={() => onHoverType(null)}
              onClick={() => onSelectType(active ? 'all' : type)}
            >
              <span className={`an-swatch an-tone-${typeTone(type)}`} />
              {STATUS_LABELS[type]}
            </button>
          )
        })}
      </div>
    </div>
  )
}
