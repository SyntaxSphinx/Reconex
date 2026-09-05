import {
  EXCEPTION_TYPE_OPTIONS,
  QUEUE_FILTERS,
  type QueueFilter,
} from '../lib/investigationDisplay'
import type { ReconciliationStatus } from '../types/investigation'

type InvestigationFiltersProps = {
  queueFilter: QueueFilter
  exceptionType: ReconciliationStatus | 'all'
  search: string
  onQueueFilterChange: (filter: QueueFilter) => void
  onExceptionTypeChange: (value: ReconciliationStatus | 'all') => void
  onSearchChange: (value: string) => void
}

export function InvestigationFilters({
  queueFilter,
  exceptionType,
  search,
  onQueueFilterChange,
  onExceptionTypeChange,
  onSearchChange,
}: InvestigationFiltersProps) {
  return (
    <div className="inv-controls">
      <div className="inv-filter-tabs" role="tablist" aria-label="Investigation status">
        {QUEUE_FILTERS.map((filter) => (
          <button
            key={filter.value}
            type="button"
            role="tab"
            aria-selected={queueFilter === filter.value}
            className={`inv-filter-tab ${queueFilter === filter.value ? 'active' : ''}`}
            onClick={() => onQueueFilterChange(filter.value)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <div className="inv-control-fields">
        <label className="inv-select-label">
          <span className="visually-hidden">Exception type</span>
          <select
            className="inv-select"
            value={exceptionType}
            onChange={(event) =>
              onExceptionTypeChange(
                event.target.value === 'all'
                  ? 'all'
                  : (event.target.value as ReconciliationStatus),
              )
            }
          >
            <option value="all">All exception types</option>
            {EXCEPTION_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="inv-search-label">
          <span className="visually-hidden">
            Search by investigation ID, payment ID, or exception type
          </span>
          <input
            type="search"
            className="inv-search"
            placeholder="Search by investigation ID, payment ID, or exception type"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </label>
      </div>
    </div>
  )
}
