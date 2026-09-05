import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { SampleDataNotice } from '../components/SampleDataNotice'
import { useIncident } from '../hooks/useIncidents'
import {
  SEVERITY_LABELS,
  STATUS_LABELS,
  TYPE_LABELS,
  formatIncidentTime,
  formatPaiseAsInr,
  severityClass,
  statusClass,
} from '../lib/incidentDisplay'
import type { Incident } from '../types/incident'

export function IncidentDetailPage() {
  const { incidentId } = useParams()
  const decodedId = incidentId ? decodeURIComponent(incidentId) : undefined
  const { incident, error } = useIncident(decodedId)

  if (error) {
    return (
      <div className="page">
        <DetailBackLink />
        <EmptyState title="Unable to load incident" description={error} />
      </div>
    )
  }

  if (incident === undefined) {
    return (
      <div className="page">
        <DetailBackLink />
        <p className="text-secondary">Loading incident…</p>
      </div>
    )
  }

  if (incident === null) {
    return (
      <div className="page">
        <DetailBackLink />
        <EmptyState
          title="Incident not found"
          description="No incident exists for this ID in the current mock dataset."
        />
      </div>
    )
  }

  return <IncidentDetail incident={incident} />
}

function DetailBackLink() {
  return (
    <p className="detail-back">
      <Link to="/incidents">Incidents</Link>
    </p>
  )
}

function IncidentDetail({ incident }: { incident: Incident }) {
  return (
    <div className="page detail-page">
      <DetailBackLink />

      <SampleDataNotice>
        Sample operational data — incidents are not yet connected to the
        reconciliation backend.
      </SampleDataNotice>

      <header className="detail-header">
        <div>
          <p className="inc-detail-kicker">{incident.incident_id}</p>
          <h1 className="detail-title">{incident.title}</h1>
          <p className="detail-header-meta">
            {TYPE_LABELS[incident.type]}
            <span className="detail-header-dot" aria-hidden="true">
              ·
            </span>
            Updated {formatIncidentTime(incident.last_updated)} IST
          </p>
        </div>
        <div className="inc-row-flags">
          <span className={`inc-severity ${severityClass(incident.severity)}`}>
            {SEVERITY_LABELS[incident.severity]}
          </span>
          <span className={`inc-status ${statusClass(incident.status)}`}>
            {STATUS_LABELS[incident.status]}
          </span>
        </div>
      </header>

      <section className="detail-section" aria-labelledby="inc-summary-label">
        <h2 className="detail-section-label" id="inc-summary-label">
          Summary
        </h2>
        <p className="detail-engine-copy">{incident.summary}</p>
      </section>

      <section className="detail-section" aria-labelledby="inc-impact-label">
        <h2 className="detail-section-label" id="inc-impact-label">
          Impact
        </h2>
        <dl className="inc-impact">
          <div>
            <dt>Exceptions</dt>
            <dd className="mono">{incident.affected_exception_count}</dd>
          </div>
          <div>
            <dt>Payments</dt>
            <dd className="mono">{incident.affected_payment_count}</dd>
          </div>
          <div>
            <dt>Amount</dt>
            <dd className="mono">{formatPaiseAsInr(incident.impact_paise)}</dd>
          </div>
        </dl>
      </section>

      <section className="detail-section" aria-labelledby="inc-types-label">
        <h2 className="detail-section-label" id="inc-types-label">
          Affected exception types
        </h2>
        <ul className="detail-quiet-list">
          {incident.exception_types.map((type) => (
            <li key={type}>{type}</li>
          ))}
        </ul>
      </section>

      <section className="detail-section" aria-labelledby="inc-related-label">
        <h2 className="detail-section-label" id="inc-related-label">
          Related investigations
        </h2>
        <ul className="inc-related">
          {incident.related_investigation_ids.map((exceptionId) => (
            <li key={exceptionId}>
              <span className="inc-related-sample">
                <code className="inc-related-id">{exceptionId}</code>
                <span className="inc-related-badge">Sample investigation</span>
              </span>
            </li>
          ))}
        </ul>
        <p className="detail-section-note">
          These references are sample IDs only. They are not linked to live
          investigation records.
        </p>
      </section>

      <section className="detail-section" aria-labelledby="inc-ops-label">
        <h2 className="detail-section-label" id="inc-ops-label">
          Operational context
        </h2>
        <dl className="detail-ids">
          <div className="detail-id">
            <dt>Owner</dt>
            <dd>{incident.owner}</dd>
          </div>
          <div className="detail-id">
            <dt>Window</dt>
            <dd>{incident.window}</dd>
          </div>
          <div className="detail-id">
            <dt>Opened</dt>
            <dd>{formatIncidentTime(incident.opened_at)} IST</dd>
          </div>
          <div className="detail-id">
            <dt>Last updated</dt>
            <dd>{formatIncidentTime(incident.last_updated)} IST</dd>
          </div>
        </dl>
        <p className="detail-section-note">{incident.notes}</p>
      </section>
    </div>
  )
}
