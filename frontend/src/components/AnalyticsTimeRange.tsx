import {
  RANGE_OPTIONS,
} from '../lib/analyticsDisplay'
import type { AnalyticsRange } from '../types/analytics'

type AnalyticsTimeRangeProps = {
  range: AnalyticsRange
  onChange: (range: AnalyticsRange) => void
}

export function AnalyticsTimeRange({ range, onChange }: AnalyticsTimeRangeProps) {
  return (
    <div className="an-range" role="tablist" aria-label="Time range">
      {RANGE_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={range === option.value}
          className={`inv-filter-tab ${range === option.value ? 'active' : ''}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
