import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { scenarioLabel } from '../lib/scenarioDisplay'
import type { ReconciliationHealthPoint } from '../types/overview'

const HEIGHT = 280
const PAD = { top: 12, right: 12, bottom: 36, left: 44 }

type PlottedPoint = ReconciliationHealthPoint & {
  x: number
  y: number
}

/** Parse run instant from run_id (`run_YYYYMMDD_HHMMSS`) when present. */
function runInstant(point: Pick<ReconciliationHealthPoint, 'run_id' | 'run_date'>): Date {
  const match = /^run_(\d{8})_(\d{6})/.exec(point.run_id)
  if (match) {
    const [, day, time] = match
    return new Date(
      `${day.slice(0, 4)}-${day.slice(4, 6)}-${day.slice(6, 8)}T${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`,
    )
  }
  return new Date(`${point.run_date}T00:00:00`)
}

function formatDayMonth(date: Date): string {
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function formatClock(date: Date): string {
  return date.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatAxisLabel(
  point: ReconciliationHealthPoint,
  sameDayDuplicate: boolean,
): string {
  const instant = runInstant(point)
  if (!sameDayDuplicate) return formatDayMonth(instant)
  return `${formatDayMonth(instant)} ${formatClock(instant)}`
}

function formatTooltipWhen(point: ReconciliationHealthPoint): string {
  const instant = runInstant(point)
  const hasClock = /^run_\d{8}_\d{6}/.test(point.run_id)
  if (!hasClock) {
    return instant.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  }
  return instant.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatRate(value: number): string {
  return `${value.toFixed(1)}%`
}

function niceDomain(values: number[]): { min: number; max: number; ticks: number[] } {
  const rawMin = Math.min(...values)
  const rawMax = Math.max(...values)
  const paddedMin = Math.max(0, rawMin - 1.5)
  const paddedMax = Math.min(100, rawMax + 1.2)
  const min = Math.floor(paddedMin)
  const max = Math.ceil(paddedMax)
  const span = Math.max(max - min, 4)
  const step = span <= 6 ? 1 : span <= 12 ? 2 : 5
  const start = Math.floor(min / step) * step
  const end = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let tick = start; tick <= end; tick += step) ticks.push(tick)
  return { min: start, max: end, ticks }
}

function linePath(points: PlottedPoint[]): string {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(' ')
}

function areaPath(points: PlottedPoint[], baselineY: number): string {
  if (points.length === 0) return ''
  const last = points[points.length - 1]
  const first = points[0]
  return `${linePath(points)} L ${last.x.toFixed(1)} ${baselineY.toFixed(1)} L ${first.x.toFixed(1)} ${baselineY.toFixed(1)} Z`
}

export function ReconciliationHealthChart({
  points,
  fillArea = false,
}: {
  points: ReconciliationHealthPoint[]
  fillArea?: boolean
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const pathRef = useRef<SVGPathElement>(null)
  const [width, setWidth] = useState(720)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  // Manual selection is valid only for the history tip that existed when chosen.
  // When a newer run arrives, selection snaps back to the latest stored run.
  const [manualRunId, setManualRunId] = useState<string | null>(null)
  const [manualAnchorLatestId, setManualAnchorLatestId] = useState<string | null>(
    null,
  )
  const latestRunId = points.length > 0 ? points[points.length - 1].run_id : null

  const resolvedSelectedIndex = useMemo(() => {
    if (points.length === 0) return null
    if (
      manualRunId != null &&
      manualAnchorLatestId != null &&
      manualAnchorLatestId === latestRunId
    ) {
      const index = points.findIndex((point) => point.run_id === manualRunId)
      if (index >= 0) return index
    }
    return points.length - 1
  }, [points, manualRunId, manualAnchorLatestId, latestRunId])

  useEffect(() => {
    const node = wrapRef.current
    if (!node) return

    const update = () => setWidth(Math.max(node.clientWidth, 320))
    update()

    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const { plotted, ticks, yMin, yMax, xLabels } = useMemo(() => {
    const plotW = width - PAD.left - PAD.right
    const plotH = HEIGHT - PAD.top - PAD.bottom
    const { min, max, ticks: yTicks } = niceDomain(points.map((p) => p.reconciliation_rate))
    const last = points.length - 1

    const plottedPoints = points.map((point, index) => ({
      ...point,
      x: PAD.left + (last <= 0 ? plotW / 2 : (index / last) * plotW),
      y: PAD.top + ((max - point.reconciliation_rate) / (max - min)) * plotH,
    }))

    const dateCounts = new Map<string, number>()
    for (const point of points) {
      dateCounts.set(point.run_date, (dateCounts.get(point.run_date) ?? 0) + 1)
    }

    const tickEvery = points.length > 20 ? 5 : points.length > 10 ? 2 : 1
    const labels = points
      .map((point, index) => ({
        index,
        label: formatAxisLabel(point, (dateCounts.get(point.run_date) ?? 0) > 1),
      }))
      .filter((_, index) => index === 0 || index === last || index % tickEvery === 0)

    return {
      plotted: plottedPoints,
      ticks: yTicks,
      yMin: min,
      yMax: max,
      xLabels: labels,
    }
  }, [points, width])

  const d = useMemo(() => linePath(plotted), [plotted])
  const plotH = HEIGHT - PAD.top - PAD.bottom

  useEffect(() => {
    const path = pathRef.current
    if (!path || plotted.length === 0) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const length = path.getTotalLength()
    path.style.strokeDasharray = `${length}`
    path.style.strokeDashoffset = `${length}`
    const frame = requestAnimationFrame(() => {
      path.style.transition = 'stroke-dashoffset 700ms ease-out'
      path.style.strokeDashoffset = '0'
    })

    return () => {
      cancelAnimationFrame(frame)
      path.style.transition = ''
      path.style.strokeDasharray = ''
      path.style.strokeDashoffset = ''
    }
  }, [d, plotted.length])

  const hover = hoverIndex !== null ? plotted[hoverIndex] : null
  const selected = resolvedSelectedIndex !== null ? plotted[resolvedSelectedIndex] : null
  const active = hover ?? selected
  const tooltipBelow = Boolean(active && active.y < 72)

  function nearestIndex(clientX: number) {
    const node = wrapRef.current
    if (!node || plotted.length === 0) return null
    const rect = node.getBoundingClientRect()
    const x = clientX - rect.left
    let best = 0
    let bestDist = Number.POSITIVE_INFINITY
    plotted.forEach((point, index) => {
      const dist = Math.abs(point.x - x)
      if (dist < bestDist) {
        best = index
        bestDist = dist
      }
    })
    return best
  }

  function selectIndex(index: number | null) {
    if (index === null || index < 0 || index >= points.length) return
    setManualRunId(points[index].run_id)
    setManualAnchorLatestId(latestRunId)
  }

  function onChartKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (plotted.length === 0) return
    const current = resolvedSelectedIndex ?? plotted.length - 1
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
      event.preventDefault()
      selectIndex(Math.min(current + 1, plotted.length - 1))
    }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
      event.preventDefault()
      selectIndex(Math.max(current - 1, 0))
    }
    if (event.key === 'Home') {
      event.preventDefault()
      selectIndex(0)
    }
    if (event.key === 'End') {
      event.preventDefault()
      selectIndex(plotted.length - 1)
    }
  }

  return (
    <div
      ref={wrapRef}
      className="health-chart"
      tabIndex={0}
      role="listbox"
      aria-label="Reconciliation rate across recent reconciliation runs"
      aria-activedescendant={
        selected ? `health-run-${selected.run_id}` : undefined
      }
      onMouseLeave={() => setHoverIndex(null)}
      onMouseMove={(event) => setHoverIndex(nearestIndex(event.clientX))}
      onClick={(event) => selectIndex(nearestIndex(event.clientX))}
      onKeyDown={onChartKeyDown}
    >
      <svg
        className="health-svg"
        width={width}
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        aria-hidden="true"
      >
        {ticks.map((tick) => {
          const y = PAD.top + ((yMax - tick) / (yMax - yMin)) * plotH
          return (
            <g key={tick}>
              <line
                className="health-grid"
                x1={PAD.left}
                x2={width - PAD.right}
                y1={y}
                y2={y}
              />
              <text className="health-axis-label" x={PAD.left - 8} y={y + 4} textAnchor="end">
                {tick}%
              </text>
            </g>
          )
        })}

        {xLabels.map(({ index, label }) => (
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

        {fillArea && plotted.length > 0 && (
          <path
            className="health-area"
            d={areaPath(plotted, PAD.top + plotH)}
          />
        )}

        <path ref={pathRef} className="health-line" d={d} fill="none" />

        {plotted.map((point, index) => {
          const isLatest = index === plotted.length - 1
          const isSelected = resolvedSelectedIndex === index
          return (
            <circle
              key={point.run_id}
              id={`health-run-${point.run_id}`}
              className={`health-point${isSelected ? ' health-point-selected' : ''}${
                isLatest ? ' health-point-latest' : ''
              }`}
              cx={point.x}
              cy={point.y}
              r={isLatest ? 5 : isSelected ? 4.5 : 3}
              role="option"
              aria-selected={isSelected}
            />
          )
        })}

        {active && (
          <line
            className="health-hover-rule"
            x1={active.x}
            x2={active.x}
            y1={PAD.top}
            y2={PAD.top + plotH}
          />
        )}
      </svg>

      {active && (
        <div
          className={`health-tooltip${selected && !hover ? ' is-selected' : ''}`}
          style={{
            left: Math.min(Math.max(active.x, 96), width - 96),
            top: tooltipBelow ? Math.min(active.y + 14, HEIGHT - 8) : Math.max(active.y - 12, 8),
            transform: tooltipBelow ? 'translate(-50%, 0)' : 'translate(-50%, -100%)',
          }}
        >
          <p className="health-tooltip-date">{formatTooltipWhen(active)}</p>
          <p className="health-tooltip-value">{formatRate(active.reconciliation_rate)}</p>
          <p className="health-tooltip-meta">
            {scenarioLabel(active.scenario)} ·{' '}
            {active.payments_processed.toLocaleString('en-IN')} payments
          </p>
        </div>
      )}

      {selected && (
        <p className="visually-hidden" aria-live="polite">
          Selected run {formatTooltipWhen(selected)}:{' '}
          {formatRate(selected.reconciliation_rate)},{' '}
          {scenarioLabel(selected.scenario)},{' '}
          {selected.payments_processed.toLocaleString('en-IN')} payments
        </p>
      )}
    </div>
  )
}
