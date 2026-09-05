import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { InvestigationFilters } from '../components/InvestigationFilters'
import { InvestigationRow } from '../components/InvestigationRow'
import { useInvestigationList } from '../hooks/useInvestigations'
import {
  matchesQueueFilter,
  matchesSearch,
  type QueueFilter,
} from '../lib/investigationDisplay'
import {
  parseExceptionType,
  parseQueueFilter,
} from '../lib/investigationQuery'
import {
  InvestigationOutcome,
  ResultLevel,
  type ReconciliationStatus,
} from '../types/investigation'

export function InvestigationsPage() {
  const { items, error } = useInvestigationList()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')

  const queueFilter = parseQueueFilter(searchParams.get('queue')) ?? 'all'
  const exceptionType = parseExceptionType(searchParams.get('type')) ?? 'all'

  function setQueueFilter(next: QueueFilter) {
    const params = new URLSearchParams(searchParams)
    if (next === 'all') params.delete('queue')
    else params.set('queue', next)
    setSearchParams(params, { replace: true })
  }

  function setExceptionType(next: ReconciliationStatus | 'all') {
    const params = new URLSearchParams(searchParams)
    if (next === 'all') params.delete('type')
    else params.set('type', next)
    setSearchParams(params, { replace: true })
  }

  const outcomeCounts = useMemo(() => {
    const counts = {
      [InvestigationOutcome.INVESTIGATED]: 0,
      [InvestigationOutcome.ESCALATED]: 0,
      [InvestigationOutcome.FAILED]: 0,
    }
    if (!items) return counts
    for (const bundle of items) {
      counts[bundle.record.outcome] += 1
    }
    return counts
  }, [items])

  const levelBreakdown = useMemo(() => {
    if (!items) return null
    let payment = 0
    let batch = 0
    for (const bundle of items) {
      if (bundle.record.result_level === ResultLevel.BATCH) batch += 1
      else payment += 1
    }
    return { total: items.length, payment, batch }
  }, [items])

  const visible = useMemo(() => {
    if (!items) return []
    return items.filter((bundle) => {
      if (!matchesQueueFilter(bundle.record, queueFilter)) return false
      if (
        exceptionType !== 'all' &&
        bundle.record.deterministic_status !== exceptionType
      ) {
        return false
      }
      return matchesSearch(bundle, search)
    })
  }, [items, queueFilter, exceptionType, search])

  const hasActiveSearch = search.trim().length > 0
  const hasActiveFilters = queueFilter !== 'all' || exceptionType !== 'all'

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Investigations</h1>
          <p className="text-secondary">
            Review and resolve reconciliation exceptions.
          </p>
        </div>
        <div className="page-header-aside">
          <p className="page-header-count">
            {levelBreakdown
              ? `${levelBreakdown.total} investigation-eligible results · ${levelBreakdown.payment} payment + ${levelBreakdown.batch} batch`
              : items === null
                ? '—'
                : '0 investigations'}
          </p>
          {levelBreakdown && levelBreakdown.total > 0 && (
            <p className="page-header-note text-secondary">
              {outcomeCounts[InvestigationOutcome.ESCALATED]} escalated ·{' '}
              {outcomeCounts[InvestigationOutcome.INVESTIGATED]} investigated ·{' '}
              {outcomeCounts[InvestigationOutcome.FAILED]} failed
            </p>
          )}
        </div>
      </div>

      <InvestigationFilters
        queueFilter={queueFilter}
        exceptionType={exceptionType}
        search={search}
        onQueueFilterChange={setQueueFilter}
        onExceptionTypeChange={setExceptionType}
        onSearchChange={setSearch}
      />

      {items === null && !error && (
        <p className="text-secondary">Loading investigations…</p>
      )}

      {error && (
        <EmptyState
          title="Unable to load investigations"
          description={error}
        />
      )}

      {items !== null && items.length === 0 && !error && (
        <EmptyState
          title="No investigations"
          description="There are no eligible reconciliation exceptions to review."
        />
      )}

      {items !== null && items.length > 0 && visible.length === 0 && (
        <EmptyState
          title={hasActiveSearch ? 'No search results' : 'No matching investigations'}
          description={
            hasActiveSearch
              ? 'No investigations match that investigation ID, payment ID, or exception type.'
              : hasActiveFilters
                ? 'No investigations match the selected filters.'
                : 'There are no investigations to display.'
          }
        />
      )}

      {visible.length > 0 && (
        <div className="inv-queue" role="list">
          {visible.map((bundle) => (
            <InvestigationRow key={bundle.record.exception_id} bundle={bundle} />
          ))}
        </div>
      )}
    </div>
  )
}
