import { EmptyState } from './EmptyState'
import {
  medianConfidence,
  STATUS_LABELS,
} from '../lib/analyticsDisplay'
import { formatConfidence, OUTCOME_LABELS } from '../lib/investigationDisplay'
import { InvestigationOutcome } from '../types/investigation'
import type { AnalyticsExceptionType, OutcomeRollup } from '../types/analytics'

const OUTCOME_ORDER = [
  InvestigationOutcome.INVESTIGATED,
  InvestigationOutcome.ESCALATED,
  InvestigationOutcome.FAILED,
] as const

export function InvestigationOutcomes({
  rollup,
  selectedType,
}: {
  rollup: OutcomeRollup
  selectedType: AnalyticsExceptionType | 'all'
}) {
  if (rollup.total === 0) {
    return (
      <EmptyState
        title="No investigations"
        description={
          selectedType === 'all'
            ? 'There are no investigation outcomes in the current dataset.'
            : `No investigations are classified as ${STATUS_LABELS[selectedType]}.`
        }
      />
    )
  }

  const max = Math.max(1, ...OUTCOME_ORDER.map((outcome) => rollup.counts[outcome]))
  const median = medianConfidence(rollup.confidence_values)

  return (
    <div className="an-outcomes">
      <ul className="an-outcomes-list">
        {OUTCOME_ORDER.map((outcome) => {
          const count = rollup.counts[outcome]
          const share = Math.round((count / rollup.total) * 100)
          return (
            <li key={outcome} className="an-outcomes-row">
              <span className="an-outcomes-label">{OUTCOME_LABELS[outcome]}</span>
              <span className="an-outcomes-count mono">{count}</span>
              <span className="text-tertiary">{share}%</span>
              <span className="an-dist-track" aria-hidden="true">
                <span
                  className={`an-outcome-bar an-outcome-${outcome.toLowerCase()}`}
                  style={{ width: `${(count / max) * 100}%` }}
                />
              </span>
            </li>
          )
        })}
      </ul>
      {median !== null ? (
        <p className="an-outcomes-confidence text-secondary">
          Median confidence {formatConfidence(median)} ·{' '}
          {rollup.confidence_values.length} of {rollup.total} investigations
          include a score.
        </p>
      ) : (
        <p className="an-outcomes-confidence text-secondary">
          None of these investigations include a confidence score.
        </p>
      )}
    </div>
  )
}
