import { Link } from 'react-router-dom'
import {
  LEVEL_LABELS,
  OUTCOME_LABELS,
  STATUS_LABELS,
  amountPaiseFromContext,
  classificationDisagrees,
  formatConfidence,
  formatPaiseAsInr,
  primaryIdentifier,
} from '../lib/investigationDisplay'
import type { InvestigationBundle } from '../types/investigation'

type InvestigationRowProps = {
  bundle: InvestigationBundle
}

export function InvestigationRow({ bundle }: InvestigationRowProps) {
  const { record, context } = bundle
  const identifier = primaryIdentifier(record, context)
  const amountPaise = amountPaiseFromContext(context)
  const disagrees = classificationDisagrees(record)
  const confidence = record.investigation?.confidence

  return (
    <Link
      to={`/investigations/${encodeURIComponent(record.exception_id)}`}
      className="inv-queue-row"
    >
      <div className="inv-queue-main">
        <div className="inv-primary">
          <span className="inv-id">{record.exception_id}</span>
          <span className="inv-sep text-tertiary">/</span>
          <span className="inv-type">{STATUS_LABELS[record.deterministic_status]}</span>
          {disagrees && (
            <span className="inv-flag">AI classification differs</span>
          )}
          {record.human_review_required && (
            <span className="inv-flag inv-flag-review">Review required</span>
          )}
        </div>
        <div className="inv-meta">
          <span className="inv-meta-item">
            <span className="text-tertiary">Level</span>
            <span>{LEVEL_LABELS[record.result_level]}</span>
          </span>
          {identifier && (
            <span className="inv-meta-item">
              <span className="text-tertiary">{identifier.label}</span>
              <code>{identifier.value}</code>
            </span>
          )}
          {amountPaise !== null && (
            <span className="inv-meta-item">
              <span className="text-tertiary">Amount</span>
              <span className="mono">{formatPaiseAsInr(amountPaise)}</span>
            </span>
          )}
          {confidence !== undefined && (
            <span className="inv-meta-item">
              <span className="text-tertiary">Confidence</span>
              <span className="mono">{formatConfidence(confidence)}</span>
            </span>
          )}
        </div>
      </div>
      <span className={`inv-outcome inv-outcome-${record.outcome.toLowerCase()}`}>
        {OUTCOME_LABELS[record.outcome]}
      </span>
    </Link>
  )
}
