import { useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { ReconciliationHealthChart } from '../components/ReconciliationHealthChart'
import { ReconciliationHealthSnapshot } from '../components/ReconciliationHealthSnapshot'
import { RunReconciliationDialog } from '../components/RunReconciliationDialog'
import { useCurrentRun } from '../hooks/useCurrentRun'
import { useInvestigationList } from '../hooks/useInvestigations'
import { useReconciliationHealth } from '../hooks/useReconciliationHealth'
import {
  OUTCOME_LABELS,
  STATUS_LABELS,
  amountPaiseFromContext,
  formatConfidence,
  formatPaiseAsInr,
  primaryIdentifier,
} from '../lib/investigationDisplay'
import {
  investigationDetailPath,
  investigationsPath,
} from '../lib/investigationQuery'
import {
  exceptionProfileRows,
  formatRunWhen,
  runOutcomes,
} from '../lib/overviewDisplay'
import { PAYMENT_RECON_EXCEPTIONS, paymentsPath } from '../lib/paymentQuery'
import {
  ReconciliationScenario,
  SCENARIO_OPTIONS,
  scenarioLabel,
} from '../lib/scenarioDisplay'
import type { CurrentRun } from '../types/overview'
import { ActivityIcon, AlertIcon, ListIcon, SnapshotIcon } from '../assets/icons'

export function OverviewPage() {
  const [runOpen, setRunOpen] = useState(false)
  const [scenario, setScenario] = useState<ReconciliationScenario>(
    ReconciliationScenario.NORMAL,
  )
  const [activeOutcome, setActiveOutcome] = useState<string | null>(null)
  const { run, error } = useCurrentRun()

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="page-kicker">Operations console</p>
          <h1>Reconciliation Overview</h1>
          <p className="page-meta">
            {run === undefined
              ? 'Loading current run…'
              : run
                ? `Last run: ${formatRunWhen(run.run_timestamp)} IST · ${scenarioLabel(run.scenario)} · ${run.payments_processed.toLocaleString('en-IN')} payments processed`
                : 'No reconciliation run has been executed'}
          </p>
        </div>
        <div className="run-actions">
          <label className="inv-select-label">
            <span className="visually-hidden">Reconciliation scenario</span>
            <select
              className="inv-select run-scenario-select"
              value={scenario}
              onChange={(event) =>
                setScenario(event.target.value as ReconciliationScenario)
              }
            >
              {SCENARIO_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setRunOpen(true)}
          >
            Run Reconciliation
          </button>
        </div>
      </div>

      <RunReconciliationDialog
        open={runOpen}
        scenario={scenario}
        onClose={() => setRunOpen(false)}
      />

      <ReconciliationHealthSection />

      <div className="overview-current">
        <section className="run-summary" aria-labelledby="run-snapshot-title">
          <div className="panel-heading">
            <SnapshotIcon />
            <h2 className="panel-label" id="run-snapshot-title">
              Run Snapshot
            </h2>
            {run && (
              <p className={`run-summary-hint${activeOutcome ? ' is-active' : ''}`} role="status">
                {(() => {
                  const outcome = runOutcomes(run).find((item) => item.tone === activeOutcome)
                  if (!outcome) return ''
                  return `${outcome.label} · ${outcome.count} · ${outcome.percent}`
                })()}
              </p>
            )}
          </div>
          {error && (
            <EmptyState title="Unable to load current run" description={error} />
          )}
          {run === undefined && !error && (
            <p className="text-secondary">Loading current run…</p>
          )}
          {run === null && !error && (
            <EmptyState
              title="No reconciliation run has been executed"
              description="Run reconciliation to see the current snapshot from the engine."
            />
          )}
          {run && (
            <RunSnapshot
              run={run}
              activeOutcome={activeOutcome}
              setActiveOutcome={setActiveOutcome}
            />
          )}
        </section>

        <section className="exception-panel" aria-labelledby="exception-profile-title">
          <div className="panel-heading">
            <AlertIcon />
            <h2 className="panel-label" id="exception-profile-title">
              Exception Profile
            </h2>
          </div>
          {run && <ExceptionProfile run={run} />}
          {run === null && !error && (
            <p className="text-secondary">
              Exception counts will appear after a reconciliation run.
            </p>
          )}
          <div className="panel-footer">
            <Link
              to={paymentsPath({ recon: PAYMENT_RECON_EXCEPTIONS })}
              className="btn-ghost"
            >
              View payment exceptions
            </Link>
          </div>
        </section>
      </div>

      <RecentInvestigationsSection />
    </div>
  )
}

function RecentInvestigationsSection() {
  const { items, error } = useInvestigationList()
  const eligibleCount = items?.length

  return (
    <section className="investigations-band" aria-labelledby="recent-investigations-title">
      <div className="panel-heading">
        <ListIcon />
        <h2 className="panel-label" id="recent-investigations-title">
          Recent Investigations
        </h2>
        <Link
          to={investigationsPath({ queue: 'all' })}
          className="btn-ghost panel-heading-action"
        >
          {eligibleCount != null
            ? `View ${eligibleCount} investigation-eligible`
            : 'View investigation-eligible'}
        </Link>
      </div>
      <RecentInvestigations items={items} error={error} />
    </section>
  )
}

function RunSnapshot({
  run,
  activeOutcome,
  setActiveOutcome,
}: {
  run: CurrentRun
  activeOutcome: string | null
  setActiveOutcome: (tone: string | null) => void
}) {
  const outcomes = runOutcomes(run)

  return (
    <>
      <div
        className="run-summary-bar"
        aria-label="Payment outcome distribution"
        onMouseLeave={() => setActiveOutcome(null)}
      >
        {outcomes.map((outcome) => {
          const className = [
            'run-summary-segment',
            `run-summary-segment-${outcome.tone}`,
            activeOutcome && activeOutcome !== outcome.tone ? 'is-muted' : '',
          ]
            .filter(Boolean)
            .join(' ')

          const label = `${outcome.label}: ${outcome.count} payments (${outcome.percent})`

          if (outcome.tone === 'exceptions') {
            return (
              <Link
                key={outcome.label}
                to={paymentsPath({ recon: PAYMENT_RECON_EXCEPTIONS })}
                className={className}
                style={{ width: outcome.percent }}
                aria-label={`${label}. View payment exceptions`}
                onMouseEnter={() => setActiveOutcome(outcome.tone)}
                onFocus={() => setActiveOutcome(outcome.tone)}
                onBlur={() => setActiveOutcome(null)}
              />
            )
          }

          return (
            <button
              key={outcome.label}
              type="button"
              className={className}
              style={{ width: outcome.percent }}
              aria-label={label}
              onMouseEnter={() => setActiveOutcome(outcome.tone)}
              onFocus={() => setActiveOutcome(outcome.tone)}
              onBlur={() => setActiveOutcome(null)}
            />
          )
        })}
      </div>
      <div className="run-summary-body">
        <div className="run-summary-outcomes">
          {outcomes.map((outcome) => {
            const className = `run-stat run-stat-${outcome.tone}${
              activeOutcome === outcome.tone ? ' is-active' : ''
            }`

            if (outcome.tone === 'exceptions') {
              return (
                <Link
                  key={outcome.label}
                  to={paymentsPath({ recon: PAYMENT_RECON_EXCEPTIONS })}
                  className={className}
                  onMouseEnter={() => setActiveOutcome(outcome.tone)}
                  onMouseLeave={() => setActiveOutcome(null)}
                  onFocus={() => setActiveOutcome(outcome.tone)}
                  onBlur={() => setActiveOutcome(null)}
                >
                  <div className="run-stat-label">
                    <span className={`run-stat-tick run-stat-tick-${outcome.tone}`} />
                    {outcome.label}
                  </div>
                  <div className="run-stat-value">{outcome.count}</div>
                  <div className="run-stat-meta">{outcome.percent}</div>
                </Link>
              )
            }

            return (
              <button
                key={outcome.label}
                type="button"
                className={className}
                onMouseEnter={() => setActiveOutcome(outcome.tone)}
                onMouseLeave={() => setActiveOutcome(null)}
                onFocus={() => setActiveOutcome(outcome.tone)}
                onBlur={() => setActiveOutcome(null)}
              >
                <div className="run-stat-label">
                  <span className={`run-stat-tick run-stat-tick-${outcome.tone}`} />
                  {outcome.label}
                </div>
                <div className="run-stat-value">{outcome.count}</div>
                {outcome.tone !== 'reconciled' && (
                  <div className="run-stat-meta">{outcome.percent}</div>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </>
  )
}

function ExceptionProfile({ run }: { run: CurrentRun }) {
  const rows = exceptionProfileRows(run)
  const maxCount = Math.max(0, ...rows.map((row) => row.count))

  if (rows.length === 0) {
    return (
      <p className="text-secondary">
        This run has no payment-level exceptions to profile.
      </p>
    )
  }

  return (
    <div className="exception-profile">
      {rows.map((row) => {
        const width = maxCount > 0 ? `${(row.count / maxCount) * 100}%` : '0%'
        return (
          <Link
            key={row.statusKey}
            to={row.href}
            className="exception-profile-row"
            aria-label={`${row.type}, ${row.count} cases, ${row.impact}. View related records`}
          >
            <div className="exception-profile-top">
              <p className="exception-profile-name">{row.type}</p>
              <p className="exception-profile-impact">{row.impact}</p>
              <p className="exception-profile-status exception-status-review">
                Review required
              </p>
            </div>
            <div className="exception-profile-track">
              <span className="exception-profile-rail">
                <span
                  className="exception-profile-bar"
                  style={{ '--bar-width': width } as CSSProperties}
                />
              </span>
              <span className="exception-profile-count mono">{row.count}</span>
              <span className="exception-profile-go" aria-hidden="true">
                →
              </span>
            </div>
          </Link>
        )
      })}
    </div>
  )
}

function ReconciliationHealthSection() {
  const { points, error } = useReconciliationHealth()
  const { run } = useCurrentRun()

  return (
    <section className="health-section" aria-labelledby="health-title">
      <div className="health-section-header">
        <ActivityIcon />
        <h2 id="health-title">Reconciliation Health</h2>
      </div>
      {error && <p className="text-secondary">{error}</p>}
      {points === null && !error && (
        <p className="text-secondary">Loading reconciliation health…</p>
      )}
      {points && points.length === 0 && !error && (
        <p className="text-secondary">
          No reconciliation health history is available.
        </p>
      )}
      {points && points.length === 1 && run && (
        <ReconciliationHealthSnapshot run={run} />
      )}
      {points && points.length === 1 && !run && (
        <p className="text-secondary">
          One stored run is available. Load the current run to see the
          reconciliation snapshot.
        </p>
      )}
      {points && points.length >= 2 && (
        <ReconciliationHealthChart points={points} />
      )}
    </section>
  )
}

function RecentInvestigations({
  items,
  error,
}: {
  items: ReturnType<typeof useInvestigationList>['items']
  error: string | null
}) {
  if (error) {
    return <p className="text-secondary">{error}</p>
  }

  if (items === null) {
    return <p className="text-secondary">Loading recent investigations…</p>
  }

  const recent = items.slice(0, 3)

  if (recent.length === 0) {
    return (
      <p className="text-secondary">
        No recent investigations are available in the current dataset.
      </p>
    )
  }

  return (
    <div className="investigations-list">
      {recent.map((bundle) => {
        const { record, context } = bundle
        const identifier = primaryIdentifier(record, context)
        const amountPaise = amountPaiseFromContext(context)
        const confidence = record.investigation?.confidence

        return (
          <Link
            key={record.exception_id}
            to={investigationDetailPath(record.exception_id)}
            className="inv-row"
          >
            <div className="inv-primary">
              <span className="inv-id">{record.exception_id}</span>
              <span className="inv-sep text-tertiary">/</span>
              <span className="inv-type">
                {STATUS_LABELS[record.deterministic_status]}
              </span>
              <span className="inv-status text-tertiary">
                {OUTCOME_LABELS[record.outcome]}
              </span>
            </div>
            <div className="inv-meta">
              {identifier && (
                <span className="inv-meta-item">
                  <span className="text-tertiary">{identifier.label}</span>{' '}
                  <code>{identifier.value}</code>
                </span>
              )}
              {amountPaise !== null && (
                <span className="inv-meta-item">
                  <span className="text-tertiary">Amount</span>{' '}
                  <span className="mono">{formatPaiseAsInr(amountPaise)}</span>
                </span>
              )}
              {confidence !== undefined && (
                <span className="inv-meta-item">
                  <span className="text-tertiary">Confidence</span>{' '}
                  <span className="mono">{formatConfidence(confidence)}</span>
                </span>
              )}
            </div>
            <span className="inv-row-go" aria-hidden="true">
              →
            </span>
          </Link>
        )
      })}
    </div>
  )
}
