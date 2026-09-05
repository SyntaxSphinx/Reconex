import {
  INCIDENT_QUEUE_FILTERS,
  SEVERITY_OPTIONS,
  TYPE_OPTIONS,
  type IncidentQueueFilter,
} from '../lib/incidentDisplay'
import type { IncidentSeverity, IncidentType } from '../types/incident'

type IncidentFiltersProps = {
  queueFilter: IncidentQueueFilter
  severity: IncidentSeverity | 'all'
  incidentType: IncidentType | 'all'
  search: string
  onQueueFilterChange: (filter: IncidentQueueFilter) => void
  onSeverityChange: (value: IncidentSeverity | 'all') => void
  onTypeChange: (value: IncidentType | 'all') => void
  onSearchChange: (value: string) => void
}

export function IncidentFilters({
  queueFilter,
  severity,
  incidentType,
  search,
  onQueueFilterChange,
  onSeverityChange,
  onTypeChange,
  onSearchChange,
}: IncidentFiltersProps) {
  return (
    <div className="inv-controls">
      <div className="inv-filter-tabs" role="tablist" aria-label="Incident status">
        {INCIDENT_QUEUE_FILTERS.map((filter) => (
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
          <span className="visually-hidden">Severity</span>
          <select
            className="inv-select"
            value={severity}
            onChange={(event) =>
              onSeverityChange(
                event.target.value === 'all'
                  ? 'all'
                  : (event.target.value as IncidentSeverity),
              )
            }
          >
            <option value="all">All severities</option>
            {SEVERITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="inv-select-label">
          <span className="visually-hidden">Incident type</span>
          <select
            className="inv-select"
            value={incidentType}
            onChange={(event) =>
              onTypeChange(
                event.target.value === 'all'
                  ? 'all'
                  : (event.target.value as IncidentType),
              )
            }
          >
            <option value="all">All incident types</option>
            {TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="inv-search-label">
          <span className="visually-hidden">
            Search by incident ID, title, or type
          </span>
          <input
            type="search"
            className="inv-search"
            placeholder="Search by incident ID, title, or type"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </label>
      </div>
    </div>
  )
}
