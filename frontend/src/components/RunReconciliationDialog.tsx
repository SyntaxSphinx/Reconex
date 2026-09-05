import { useEffect, useRef, useState } from 'react'
import { overviewRepository } from '../data/overview/overviewRepository'
import { formatPercent } from '../lib/overviewDisplay'
import { scenarioLabel } from '../lib/scenarioDisplay'
import type { CurrentRun } from '../types/overview'
import { useWorkspaceRefresh } from '../hooks/useWorkspaceRefresh'

type Phase = 'confirm' | 'running' | 'complete'

type RunReconciliationDialogProps = {
  open: boolean
  scenario: string
  onClose: () => void
}

export function RunReconciliationDialog({
  open,
  scenario,
  onClose,
}: RunReconciliationDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const { refresh } = useWorkspaceRefresh()
  const [phase, setPhase] = useState<Phase>('confirm')
  const [result, setResult] = useState<CurrentRun | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const node = dialogRef.current
    if (!node) return

    if (open && !node.open) {
      setPhase('confirm')
      setResult(null)
      setError(null)
      node.showModal()
    }
    if (!open && node.open) {
      node.close()
    }
  }, [open])

  useEffect(() => {
    const node = dialogRef.current
    if (!node) return

    const onDialogClose = () => {
      setPhase('confirm')
      setResult(null)
      setError(null)
      onClose()
    }

    node.addEventListener('close', onDialogClose)
    return () => node.removeEventListener('close', onDialogClose)
  }, [onClose])

  function cancel() {
    dialogRef.current?.close()
  }

  function finish() {
    refresh()
    dialogRef.current?.close()
  }

  function run() {
    setPhase('running')
    setError(null)
    overviewRepository
      .createRun(scenario)
      .then((next) => {
        setResult(next)
        setPhase('complete')
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Unable to run reconciliation')
        setPhase('confirm')
      })
  }

  return (
    <dialog
      ref={dialogRef}
      className="run-dialog"
      aria-labelledby="run-dialog-title"
      aria-hidden={!open}
    >
      {open && phase === 'confirm' && (
        <>
          <p className="run-dialog-kicker">Reconciliation engine</p>
          <h2 id="run-dialog-title" className="run-dialog-title">
            Run reconciliation
          </h2>
          <p className="run-dialog-copy">
            The loaded dataset will be processed as {scenarioLabel(scenario)} by
            the existing reconciliation engine. This does not call the AI
            investigator.
          </p>
          {error && <p className="text-secondary">{error}</p>}
          <div className="run-dialog-actions">
            <button type="button" className="btn-secondary" onClick={cancel}>
              Cancel
            </button>
            <button type="button" className="btn-primary" onClick={run}>
              Run Reconciliation
            </button>
          </div>
        </>
      )}

      {open && phase === 'running' && (
        <>
          <p className="run-dialog-kicker">Reconciliation engine</p>
          <h2 id="run-dialog-title" className="run-dialog-title">
            Processing dataset
          </h2>
          <p className="run-dialog-copy">
            Running ReconciliationEngine.reconcile() on the loaded workspace
            data…
          </p>
        </>
      )}

      {open && phase === 'complete' && result && (
        <>
          <h2 id="run-dialog-title" className="run-dialog-title">
            Run complete
          </h2>
          <p className="run-dialog-meta">
            <span className="mono">{result.run_id}</span>
            <span> · {scenarioLabel(result.scenario)}</span>
          </p>
          <dl className="run-dialog-result">
            <div>
              <dt>Payments processed</dt>
              <dd>{result.payments_processed.toLocaleString('en-IN')}</dd>
            </div>
            <div>
              <dt>Reconciled</dt>
              <dd>
                {result.reconciled_count.toLocaleString('en-IN')} ·{' '}
                {formatPercent(result.reconciled_percent)}
              </dd>
            </div>
            <div>
              <dt>Exceptions</dt>
              <dd>
                {result.exception_count.toLocaleString('en-IN')} ·{' '}
                {formatPercent(result.exception_percent)}
              </dd>
            </div>
            <div>
              <dt>Reconciliation rate</dt>
              <dd>{formatPercent(result.reconciliation_rate)}</dd>
            </div>
          </dl>
          <div className="run-dialog-actions">
            <button type="button" className="btn-primary" onClick={finish}>
              View results
            </button>
          </div>
        </>
      )}
    </dialog>
  )
}
