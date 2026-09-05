import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { useInvestigation } from '../hooks/useInvestigations'
import { paymentDetailPath } from '../lib/paymentQuery'
import {
  LEVEL_LABELS,
  OUTCOME_LABELS,
  STATUS_LABELS,
  classificationDisagrees,
  deterministicAmountGroups,
  evidenceById,
  evidenceHighlights,
  formatConfidence,
  formatPaiseAsInr,
  guardrailLabel,
  investigationJourney,
  investigationRecommendation,
  investigationSummary,
  primaryIdentifier,
  resolveEvidenceRefs,
  type EvidenceHighlight,
  type JourneyStep,
} from '../lib/investigationDisplay'
import { EvidenceSource, InvestigationOutcome } from '../types/investigation'
import type {
  AIInvestigation,
  EvidenceItem,
  InvestigationBundle,
  InvestigationContext,
  InvestigationRecord,
} from '../types/investigation'

export function InvestigationDetailPage() {
  const { exceptionId } = useParams()
  const decodedId = exceptionId ? decodeURIComponent(exceptionId) : undefined
  const { bundle, error } = useInvestigation(decodedId)

  if (error) {
    return (
      <div className="page">
        <DetailBackLink />
        <EmptyState title="Unable to load investigation" description={error} />
      </div>
    )
  }

  if (bundle === undefined) {
    return (
      <div className="page">
        <DetailBackLink />
        <p className="text-secondary">Loading investigation…</p>
      </div>
    )
  }

  if (bundle === null) {
    return (
      <div className="page">
        <DetailBackLink />
        <EmptyState
          title="Investigation not found"
          description="No investigation exists for this exception ID."
        />
      </div>
    )
  }

  return <InvestigationDetail bundle={bundle} />
}

function DetailBackLink() {
  return (
    <p className="detail-back">
      <Link to="/investigations">Investigations</Link>
    </p>
  )
}

function InvestigationDetail({ bundle }: { bundle: InvestigationBundle }) {
  const { record, context } = bundle
  const investigation = record.investigation ?? null
  const disagrees = classificationDisagrees(record)
  const cited = evidenceById(context)
  const amountGroups = deterministicAmountGroups(context)
  const highlights = evidenceHighlights(record, context).filter((item) => {
    if (amountGroups.length === 0) return true
    // Amounts stay visible in the comparison block; keep identity highlights here.
    return !['Expected', 'Actual', 'Variance', 'Payment refund', 'Settlement refund'].includes(
      item.label,
    )
  })
  const summary = investigationSummary(record, context)
  const recommendation = investigationRecommendation(record)
  const journey = investigationJourney(record, context)
  const subject = primaryIdentifier(record, context)
  const failed = record.outcome === InvestigationOutcome.FAILED

  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)

  async function runAiInvestigation() {
    setAiLoading(true)
    setAiError(null)
    try {
      const response = await fetch(
        `/api/investigations/${encodeURIComponent(record.exception_id)}/run-ai`,
        { method: 'POST' },
      )
      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(data.detail || `Request failed: ${response.status}`)
      }
      // Reload the page to show the new AI investigation
      window.location.reload()
    } catch (err) {
      setAiError(err instanceof Error ? err.message : 'AI investigation failed')
      setAiLoading(false)
    }
  }

  return (
    <div className="page detail-page inv-console">
      <DetailBackLink />

      <header className="detail-header inv-console-header">
        <div>
          <p className="inc-detail-kicker">Investigation console</p>
          <h1 className="inv-console-title">
            {STATUS_LABELS[record.deterministic_status]}
          </h1>
          <p className="detail-header-meta">
            <span className="mono">{record.exception_id}</span>
            <span className="detail-header-dot" aria-hidden="true">
              ·
            </span>
            {LEVEL_LABELS[record.result_level]}
            {subject && (
              <>
                <span className="detail-header-dot" aria-hidden="true">
                  ·
                </span>
                {subject.label}{' '}
                {subject.label === 'Payment' ? (
                  <Link
                    className="pay-related-link mono"
                    to={paymentDetailPath(subject.value)}
                  >
                    {subject.value}
                  </Link>
                ) : (
                  <span className="mono">{subject.value}</span>
                )}
              </>
            )}
          </p>
        </div>
        <p
          className={`detail-outcome inv-console-outcome inv-outcome-${record.outcome.toLowerCase()}`}
        >
          {OUTCOME_LABELS[record.outcome]}
        </p>
      </header>

      <JourneyStrip steps={journey} />

      <section className="detail-section inv-console-hero" aria-labelledby="what-happened">
        <h2 className="detail-section-label" id="what-happened">
          What happened
        </h2>
        <p className="inv-console-summary">{summary}</p>
        {record.human_review_required && (
          <p className="detail-review inv-console-review">
            Human review required. The deterministic reconciliation result is
            unchanged until an operator acts on the underlying records.
          </p>
        )}
      </section>

      <section className="detail-section" aria-labelledby="evidence-label">
        <h2 className="detail-section-label" id="evidence-label">
          Evidence
        </h2>
        <p className="detail-section-note">
          Facts supplied by the reconciliation engine and source records for this
          exception only.
        </p>

        {highlights.length > 0 && (
          <div className="inv-evidence-grid">
            {highlights.map((item) => (
              <EvidenceCard key={item.id} item={item} />
            ))}
          </div>
        )}

        {amountGroups.length > 0 && (
          <div className="inv-mismatch-block">
            <h3 className="detail-block-title">Amount comparison</h3>
            <div className="detail-compare inv-amount-compare">
              {amountGroups.flatMap((group) =>
                group.figures.map((figure) => (
                  <div
                    key={`${group.id}-${figure.field}`}
                    className={`detail-compare-item${
                      figure.field === 'variance_paise' ? ' is-variance' : ''
                    }`}
                  >
                    <p className="detail-compare-label">{figure.label}</p>
                    <p className="detail-compare-value">
                      {figure.paise < 0 ? '−' : ''}
                      {formatPaiseAsInr(Math.abs(figure.paise))}
                    </p>
                  </div>
                )),
              )}
            </div>
          </div>
        )}

        <EngineFacts record={record} context={context} />
      </section>

      <section className="detail-section" aria-labelledby="reasoning-label">
        <h2 className="detail-section-label" id="reasoning-label">
          Investigation reasoning
        </h2>
        <div className="inv-conclude">
          <div className="inv-reason-grid">
            <article className="inv-reason-card">
              <p className="inv-reason-kicker">Deterministic engine</p>
              <p className="inv-reason-body">
                {record.deterministic_rule ||
                  'The reconciliation engine classified this exception from settlement and bank evidence.'}
              </p>
              <p className="inv-reason-meta mono">
                {record.deterministic_status} · authoritative
              </p>
            </article>

            <article className="inv-reason-card inv-reason-card-ai">
              <p className="inv-reason-kicker">AI-assisted investigation</p>
              {failed && (
                <>
                  <p className="inv-reason-body">
                    {record.failure_reason ??
                      'The investigator could not complete this case.'}
                  </p>
                  <p className="inv-reason-meta">
                    No AI finding · deterministic result remains authoritative
                  </p>
                </>
              )}
              {!failed && !investigation && !aiLoading && (
                <>
                  <p className="inv-reason-body">
                    No AI investigation has been run for this exception yet. The
                    case is escalated for human review on the deterministic
                    finding alone.
                  </p>
                  <p className="inv-reason-meta">Not run · hypothesis unavailable</p>
                  <button
                    type="button"
                    className="inv-ai-run-button"
                    onClick={runAiInvestigation}
                    disabled={aiLoading}
                  >
                    Run AI Investigation
                  </button>
                  {aiError && <p className="inv-ai-error">{aiError}</p>}
                </>
              )}
              {aiLoading && (
                <>
                  <p className="inv-reason-body">Investigating this exception...</p>
                  <p className="inv-reason-meta">AI analysis in progress</p>
                </>
              )}
              {investigation && (
                <>
                  <p className="inv-reason-body">{investigation.finding}</p>
                  <dl className="inv-reason-scan">
                    <div>
                      <dt>AI classification</dt>
                      <dd>
                        {STATUS_LABELS[investigation.classification]}
                        {disagrees && (
                          <span className="inv-reason-flag"> differs from engine</span>
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Confidence</dt>
                      <dd className="mono">
                        {formatConfidence(investigation.confidence)}
                      </dd>
                    </div>
                  </dl>
                  {disagrees && (
                    <p className="detail-disagree-note">
                      Classifications differ. deterministic_status remains
                      authoritative.
                    </p>
                  )}
                </>
              )}
            </article>
          </div>

          <div className="inv-action-block" aria-labelledby="action-label">
            <h2 className="detail-section-label" id="action-label">
              Recommended action
            </h2>
            <div className="inv-action">
              <p className="inv-action-kicker">
                {recommendation.source === 'ai'
                  ? 'From AI investigation'
                  : 'From deterministic status'}
              </p>
              <p className="inv-action-body">{recommendation.text}</p>
              <p className="detail-section-note">
                No resolve or mutate action is available from this console. Correct
                source records externally, then re-run reconciliation.
              </p>
            </div>
          </div>
        </div>
      </section>

      <EvidenceAppendix
        context={context}
        investigation={investigation}
        cited={cited}
      />

      {(record.guardrail_violations.length > 0 ||
        record.invalid_evidence_references.length > 0) && (
        <section className="detail-section detail-section-secondary">
          {record.guardrail_violations.length > 0 && (
            <>
              <h2 className="detail-section-label">Guardrail violations</h2>
              <ul className="detail-quiet-list">
                {record.guardrail_violations.map((violation) => (
                  <li key={violation}>
                    <span className="mono">{violation}</span>
                    <span className="text-tertiary">
                      {' '}
                      {guardrailLabel(violation)}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {record.invalid_evidence_references.length > 0 && (
            <p className="detail-secondary-note">
              Invalid references:{' '}
              <span className="mono">
                {record.invalid_evidence_references.join(', ')}
              </span>
            </p>
          )}
        </section>
      )}
    </div>
  )
}

function JourneyStrip({ steps }: { steps: JourneyStep[] }) {
  return (
    <ol className="inv-journey" aria-label="Investigation journey">
      {steps.map((step, index) => (
        <li
          key={step.id}
          className={`inv-journey-step inv-journey-${step.state}`}
        >
          {index > 0 && <span className="inv-journey-rule" aria-hidden="true" />}
          <span className="inv-journey-dot" aria-hidden="true" />
          <span className="inv-journey-label">{step.label}</span>
        </li>
      ))}
    </ol>
  )
}

function EvidenceCard({ item }: { item: EvidenceHighlight }) {
  return (
    <div
      className={`inv-evidence-card${item.tone === 'mismatch' ? ' is-mismatch' : ''}`}
    >
      <p className="inv-evidence-label">{item.label}</p>
      <p className={`inv-evidence-value${item.mono ? ' mono' : ''}`}>{item.value}</p>
    </div>
  )
}

function EngineFacts({
  record,
  context,
}: {
  record: InvestigationRecord
  context: InvestigationContext | null
}) {
  const identifiers = context?.identifiers ?? {}
  const entries = Object.entries(identifiers)

  return (
    <div className="inv-engine-facts">
      <h3 className="detail-block-title">Engine identifiers</h3>
      {entries.length === 0 ? (
        <p className="text-secondary">No identifiers were supplied for this exception.</p>
      ) : (
        <dl className="detail-ids">
          {entries.map(([key, value]) => (
            <div key={key} className="detail-id">
              <dt>{key}</dt>
              <dd className="mono">
                {key === 'payment_id' ? (
                  <Link className="pay-related-link" to={paymentDetailPath(value)}>
                    {value}
                  </Link>
                ) : (
                  value
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {context?.message || record.deterministic_rule ? (
        <div className="inv-engine-meta">
          {context?.message && (
            <p className="detail-engine-copy">
              <span className="detail-inline-label">Engine message</span>
              {context.message}
            </p>
          )}
          {record.deterministic_rule && (
            <p className="detail-engine-copy">
              <span className="detail-inline-label">Rule applied</span>
              {record.deterministic_rule}
            </p>
          )}
        </div>
      ) : null}
    </div>
  )
}

function EvidenceAppendix({
  context,
  investigation,
  cited,
}: {
  context: InvestigationContext | null
  investigation: AIInvestigation | null
  cited: Map<string, EvidenceItem>
}) {
  const supporting = investigation
    ? resolveEvidenceRefs(investigation.supporting_evidence, cited)
    : []
  const contradictory = investigation
    ? resolveEvidenceRefs(investigation.contradictory_evidence, cited)
    : []
  const hasContextEvidence = Boolean(context && context.evidence.length > 0)

  if (!investigation && !hasContextEvidence) return null

  return (
    <section
      className="detail-section inv-console-ledger"
      aria-labelledby="evidence-appendix"
    >
      <h2 className="detail-section-label" id="evidence-appendix">
        Full evidence ledger
      </h2>
      <p className="detail-section-note">
        {investigation
          ? 'AI citations first, then the full bounded context. '
          : 'Bounded context assembled for this exception. '}
        Deterministic items are engine facts; payment, settlement and bank items
        are source records.
      </p>

      {investigation && (
        <>
          <h3 className="detail-block-title">Supporting evidence</h3>
          {supporting.length === 0 ? (
            <p className="text-secondary">No supporting evidence citations.</p>
          ) : (
            <CitedEvidenceList entries={supporting} />
          )}
          {contradictory.length > 0 && (
            <>
              <h3 className="detail-block-title">Contradictory evidence</h3>
              <CitedEvidenceList entries={contradictory} />
            </>
          )}
        </>
      )}

      {hasContextEvidence && context && (
        <div className="detail-all-evidence">
          <h3 className="detail-block-title">All supplied evidence</h3>
          {context.evidence_dropped_count > 0 && (
            <p className="detail-section-note">
              {context.evidence_dropped_count} additional items were dropped from
              the bounded context.
            </p>
          )}
          <EvidenceTable items={context.evidence} />
        </div>
      )}
    </section>
  )
}

function CitedEvidenceList({
  entries,
}: {
  entries: { ref: string; item: EvidenceItem | undefined }[]
}) {
  return (
    <table className="evidence-cited">
      <thead>
        <tr>
          <th>ID</th>
          <th>Source</th>
          <th>Field</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(({ ref, item }) => (
          <tr key={ref}>
            <td className="mono">{ref}</td>
            <td>
              {item ? (
                <EvidenceSourceLabel source={item.source} />
              ) : (
                <span className="text-tertiary">Citation only</span>
              )}
            </td>
            <td className="mono">{item?.field ?? '—'}</td>
            <td className="mono">{item?.value ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EvidenceTable({ items }: { items: EvidenceItem[] }) {
  return (
    <table className="evidence-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Source</th>
          <th>Record</th>
          <th>Field</th>
          <th>Value</th>
          <th>Relevance</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.evidence_id}>
            <td className="mono">{item.evidence_id}</td>
            <td>
              <EvidenceSourceLabel source={item.source} />
            </td>
            <td className="mono">{item.record_id}</td>
            <td className="mono">{item.field}</td>
            <td className="mono">{item.value}</td>
            <td className="text-tertiary">{item.relevance}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EvidenceSourceLabel({ source }: { source: EvidenceItem['source'] }) {
  return (
    <span
      className={
        source === EvidenceSource.DETERMINISTIC
          ? 'evidence-source-deterministic'
          : 'evidence-source-record'
      }
    >
      {source}
    </span>
  )
}
