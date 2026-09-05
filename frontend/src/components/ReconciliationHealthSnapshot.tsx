import { formatPercent } from '../lib/overviewDisplay'
import { scenarioLabel } from '../lib/scenarioDisplay'
import type { CurrentRun } from '../types/overview'

type ReconciliationHealthSnapshotProps = {
  run: CurrentRun
}

export function ReconciliationHealthSnapshot({
  run,
}: ReconciliationHealthSnapshotProps) {
  const rate = formatPercent(run.reconciliation_rate)

  return (
    <div className="health-snapshot">
      <div className="health-snapshot-main">
        <p className="health-snapshot-rate mono" aria-label={`Reconciliation rate ${rate}`}>
          {rate}
        </p>
        <div
          className="health-snapshot-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={run.reconciliation_rate}
          aria-label="Reconciled share of payments"
        >
          <span
            className="health-snapshot-fill"
            style={{ width: `${Math.min(100, Math.max(0, run.reconciliation_rate))}%` }}
          />
        </div>
      </div>

      <p className="health-snapshot-note text-secondary">
        One reconciliation run · {scenarioLabel(run.scenario)} ·{' '}
        {run.payments_processed.toLocaleString('en-IN')} payments processed. Run
        reconciliation again to build history.
      </p>
    </div>
  )
}
