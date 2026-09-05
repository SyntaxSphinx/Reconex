import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ActivityIcon, AlertIcon, ImpactIcon, ListIcon, TrendIcon } from '../assets/icons'
import { AnalyticsTimeRange } from '../components/AnalyticsTimeRange'
import { EmptyState } from '../components/EmptyState'
import { ExceptionDistribution } from '../components/ExceptionDistribution'
import { ExceptionTrendChart } from '../components/ExceptionTrendChart'
import { FinancialImpact } from '../components/FinancialImpact'
import { InvestigationOutcomes } from '../components/InvestigationOutcomes'
import { OperationalInsight } from '../components/OperationalInsight'
import { ReconciliationHealthChart } from '../components/ReconciliationHealthChart'
import { ReconciliationHealthSnapshot } from '../components/ReconciliationHealthSnapshot'
import { useAnalyticsWorkspace } from '../hooks/useAnalytics'
import { useCurrentRun } from '../hooks/useCurrentRun'
import {
  ANALYTICS_EXCEPTION_TYPES,
  historyScopeLabel,
  outcomeRollup,
  reconRunDelta,
  STATUS_LABELS,
  workspaceWindow,
} from '../lib/analyticsDisplay'
import {
  parseAnalyticsRange,
  parseAnalyticsType,
} from '../lib/analyticsQuery'
import { scenarioLabel } from '../lib/scenarioDisplay'
import { AnalyticsRange, type AnalyticsExceptionType } from '../types/analytics'

export function AnalyticsPage() {
  const { workspace, error } = useAnalyticsWorkspace()
  const { run } = useCurrentRun()
  const [searchParams, setSearchParams] = useSearchParams()
  const [hoveredType, setHoveredType] = useState<AnalyticsExceptionType | null>(
    null,
  )

  const range = parseAnalyticsRange(searchParams.get('range')) ?? AnalyticsRange.DAYS_14
  const selectedType = parseAnalyticsType(searchParams.get('type')) ?? 'all'

  function setRange(next: AnalyticsRange) {
    const params = new URLSearchParams(searchParams)
    if (next === AnalyticsRange.DAYS_14) params.delete('range')
    else params.set('range', String(next))
    setSearchParams(params, { replace: true })
  }

  function setSelectedType(next: AnalyticsExceptionType | 'all') {
    const params = new URLSearchParams(searchParams)
    if (next === 'all') params.delete('type')
    else params.set('type', next)
    setSearchParams(params, { replace: true })
  }

  const windowed = useMemo(
    () => (workspace ? workspaceWindow(workspace, range) : null),
    [workspace, range],
  )

  const rollup = useMemo(
    () =>
      workspace ? outcomeRollup(workspace.investigations, selectedType) : null,
    [workspace, selectedType],
  )

  const period = useMemo(
    () => (workspace ? reconRunDelta(workspace.reconciliation) : null),
    [workspace],
  )
  const storedRuns = workspace?.reconciliation.length ?? 0
  const historyNote = workspace
    ? historyScopeLabel(windowed?.health.length ?? storedRuns, range)
    : ''
  const currentNote = 'Current run'

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Analytics</h1>
          <p className="text-secondary">
            Understand reconciliation trends, exception patterns and financial
            impact.
          </p>
        </div>
        {storedRuns >= 2 && (
          <AnalyticsTimeRange range={range} onChange={setRange} />
        )}
      </div>

      {error && (
        <EmptyState title="Unable to load analytics" description={error} />
      )}

      {workspace === null && !error && (
        <p className="text-secondary">Loading analytics…</p>
      )}

      {workspace && windowed && rollup && (
        <>
          <section className="an-section" aria-labelledby="an-recon-title">
            <div className="panel-heading">
              <ActivityIcon />
              <h2 className="panel-label" id="an-recon-title">
                {windowed.health.length >= 2
                  ? 'Reconciliation rate by run'
                  : 'Reconciliation history'}
              </h2>
              <p className="an-section-note">{historyNote}</p>
            </div>
            {windowed.health.length === 0 ? (
              <EmptyState
                title="No reconciliation runs"
                description="No stored runs are available yet. History grows by one point each time reconciliation is executed."
              />
            ) : windowed.health.length === 1 ? (
              run ? (
                <ReconciliationHealthSnapshot run={run} />
              ) : run === undefined ? (
                <p className="text-secondary">Loading current run…</p>
              ) : (
                <div className="an-recon-kpi">
                  <p className="an-recon-rate mono">
                    {windowed.health[0].reconciliation_rate.toFixed(1)}%
                  </p>
                  <p className="an-section-purpose">
                    One stored run · {scenarioLabel(windowed.health[0].scenario)} · {windowed.health[0].payments_processed.toLocaleString('en-IN')} payments
                  </p>
                </div>
              )
            ) : (
              <>
                <div className="an-recon-kpi">
                  <p className="an-recon-rate mono">
                    {windowed.health[windowed.health.length - 1].reconciliation_rate.toFixed(1)}%
                  </p>
                  {period && (
                    <p
                      className={`an-recon-delta${
                        period.delta > 0
                          ? ' is-up'
                          : period.delta < 0
                            ? ' is-down'
                            : ''
                      }`}
                    >
                      {period.delta > 0 ? '+' : ''}
                      {period.delta.toFixed(1)}pp vs previous run
                    </p>
                  )}
                </div>
                <ReconciliationHealthChart
                  key={range}
                  points={windowed.health}
                  fillArea
                />
              </>
            )}
          </section>
          <section className="an-section" aria-labelledby="an-exc-trend-title">
            <div className="panel-heading">
              <TrendIcon />
              <h2 className="panel-label" id="an-exc-trend-title">
                Exception trends
              </h2>
              <label className="panel-heading-action an-trend-filter">
                <span className="visually-hidden">Exception type</span>
                <select
                  className="an-trend-select"
                  value={selectedType}
                  onChange={(event) => {
                    const next = event.target.value
                    setSelectedType(
                      next === 'all' ? 'all' : (next as AnalyticsExceptionType),
                    )
                  }}
                >
                  <option value="all">All exceptions</option>
                  {ANALYTICS_EXCEPTION_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {STATUS_LABELS[type]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {windowed.trend.length < 2 ? (
              <EmptyState
                title="Not enough run history"
                description="Exception trends appear after at least two stored reconciliation runs. Missing days are not invented."
              />
            ) : (
              <ExceptionTrendChart
                key={selectedType}
                days={windowed.trend}
                selectedType={selectedType}
                hoveredType={hoveredType}
                onHoverType={setHoveredType}
                onSelectType={setSelectedType}
                periodLabel={historyNote}
              />
            )}
          </section>

          <OperationalInsight
            rows={windowed.financialImpact}
            periodLabel={currentNote}
          />

          <div className="an-split">
            <section className="an-section" aria-labelledby="an-dist-title">
              <div className="panel-heading">
                <AlertIcon />
                <h2 className="panel-label" id="an-dist-title">
                  Payment exceptions
                </h2>
                <p className="an-section-note">{currentNote}</p>
              </div>
              <p className="an-section-purpose">
                Payment-level exceptions in the current run. Total matches the
                run exception count.
              </p>
              <ExceptionDistribution
                rows={windowed.paymentExceptions}
                selectedType={selectedType}
                hoveredType={hoveredType}
                onHoverType={setHoveredType}
                onSelectType={setSelectedType}
                periodLabel={currentNote}
              />
            </section>

            <section className="an-section" aria-labelledby="an-impact-title">
              <div className="panel-heading">
                <ImpactIcon />
                <h2 className="panel-label" id="an-impact-title">
                  Financial impact
                </h2>
                <p className="an-section-note">{currentNote}</p>
              </div>
              <p className="an-section-purpose">
                Reconciliation variance by status, including batch-level impact.
                Categories can differ from payment exceptions.
              </p>
              <FinancialImpact
                rows={windowed.financialImpact}
                selectedType={selectedType}
                hoveredType={hoveredType}
                onHoverType={setHoveredType}
                onSelectType={setSelectedType}
              />
            </section>
          </div>

          <section className="an-section" aria-labelledby="an-outcomes-title">
            <div className="panel-heading">
              <ListIcon />
              <h2 className="panel-label" id="an-outcomes-title">
                Investigation outcomes
              </h2>
              <p className="an-section-note">
                Current investigation book
                {selectedType !== 'all' ? ' · filtered by type' : ''}
              </p>
            </div>
            <InvestigationOutcomes
              rollup={rollup}
              selectedType={selectedType}
            />
          </section>
        </>
      )}
    </div>
  )
}
