import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { IncidentFilters } from '../components/IncidentFilters'
import { IncidentRow } from '../components/IncidentRow'
import { SampleDataNotice } from '../components/SampleDataNotice'
import { useIncidentList } from '../hooks/useIncidents'
import {
  isActiveIncident,
  matchesIncidentQueue,
  matchesIncidentSearch,
  type IncidentQueueFilter,
} from '../lib/incidentDisplay'
import {
  parseIncidentQueue,
  parseIncidentSeverity,
  parseIncidentType,
} from '../lib/incidentQuery'
import type { IncidentSeverity, IncidentType } from '../types/incident'

export function IncidentsPage() {
  const { items, error } = useIncidentList()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')

  const queueFilter = parseIncidentQueue(searchParams.get('queue')) ?? 'open'
  const severity = parseIncidentSeverity(searchParams.get('severity')) ?? 'all'
  const incidentType = parseIncidentType(searchParams.get('type')) ?? 'all'

  function updateParam(key: string, value: string, defaultValue: string) {
    const params = new URLSearchParams(searchParams)
    if (value === defaultValue) params.delete(key)
    else params.set(key, value)
    setSearchParams(params, { replace: true })
  }

  const activeCount = useMemo(
    () => items?.filter((incident) => isActiveIncident(incident)).length ?? 0,
    [items],
  )

  const visible = useMemo(() => {
    if (!items) return []
    return items.filter((incident) => {
      if (!matchesIncidentQueue(incident, queueFilter)) return false
      if (severity !== 'all' && incident.severity !== severity) return false
      if (incidentType !== 'all' && incident.type !== incidentType) return false
      return matchesIncidentSearch(incident, search)
    })
  }, [items, queueFilter, severity, incidentType, search])

  const hasActiveSearch = search.trim().length > 0
  const hasActiveFilters =
    queueFilter !== 'all' || severity !== 'all' || incidentType !== 'all'

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Incidents</h1>
          <p className="text-secondary">
            Track broader reconciliation and operational issues that span multiple
            exceptions.
          </p>
        </div>
        <p className="page-header-count">
          {items === null ? '—' : `${activeCount} active`}
        </p>
      </div>

      <SampleDataNotice>
        Sample operational data — incidents are not yet connected to the
        reconciliation backend.
      </SampleDataNotice>

      <IncidentFilters
        queueFilter={queueFilter}
        severity={severity}
        incidentType={incidentType}
        search={search}
        onQueueFilterChange={(next: IncidentQueueFilter) =>
          updateParam('queue', next, 'open')
        }
        onSeverityChange={(next: IncidentSeverity | 'all') =>
          updateParam('severity', next, 'all')
        }
        onTypeChange={(next: IncidentType | 'all') =>
          updateParam('type', next, 'all')
        }
        onSearchChange={setSearch}
      />

      {items === null && !error && (
        <p className="text-secondary">Loading incidents…</p>
      )}

      {error && (
        <EmptyState title="Unable to load incidents" description={error} />
      )}

      {items !== null && items.length === 0 && !error && (
        <EmptyState
          title="No incidents"
          description="There are no operational incidents in the current dataset."
        />
      )}

      {items !== null && items.length > 0 && visible.length === 0 && (
        <EmptyState
          title={hasActiveSearch ? 'No search results' : 'No matching incidents'}
          description={
            hasActiveSearch
              ? 'No incidents match that incident ID, title, or type.'
              : hasActiveFilters
                ? 'No incidents match the selected filters.'
                : 'There are no incidents to display.'
          }
        />
      )}

      {visible.length > 0 && (
        <div className="inv-queue" role="list">
          {visible.map((incident) => (
            <IncidentRow key={incident.incident_id} incident={incident} />
          ))}
        </div>
      )}
    </div>
  )
}
