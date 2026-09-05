import { Link } from 'react-router-dom'
import {
  SEVERITY_LABELS,
  STATUS_LABELS,
  TYPE_LABELS,
  formatIncidentTime,
  formatPaiseAsInr,
  severityClass,
  statusClass,
} from '../lib/incidentDisplay'
import { incidentDetailPath } from '../lib/incidentQuery'
import type { Incident } from '../types/incident'

type IncidentRowProps = {
  incident: Incident
}

export function IncidentRow({ incident }: IncidentRowProps) {
  return (
    <Link
      to={incidentDetailPath(incident.incident_id)}
      className="inv-queue-row inc-row"
    >
      <div className="inv-queue-main">
        <div className="inv-primary">
          <span className="inv-id">{incident.incident_id}</span>
          <span className="inv-sep text-tertiary">/</span>
          <span className="inv-type">{incident.title}</span>
        </div>
        <div className="inv-meta inc-row-meta">
          <span className="inv-meta-item">
            <span className="text-tertiary">Type</span>
            <span>{TYPE_LABELS[incident.type]}</span>
          </span>
          <span className="inv-meta-item">
            <span className="text-tertiary">Affected</span>
            <span>
              {incident.affected_exception_count} exceptions ·{' '}
              {incident.affected_payment_count} payments
            </span>
          </span>
          <span className="inv-meta-item">
            <span className="text-tertiary">Impact</span>
            <span className="mono">{formatPaiseAsInr(incident.impact_paise)}</span>
          </span>
          <span className="inv-meta-item">
            <span className="text-tertiary">Updated</span>
            <span>{formatIncidentTime(incident.last_updated)} IST</span>
          </span>
        </div>
      </div>
      <div className="inc-row-flags">
        <span className={`inc-severity ${severityClass(incident.severity)}`}>
          {SEVERITY_LABELS[incident.severity]}
        </span>
        <span className={`inc-status ${statusClass(incident.status)}`}>
          {STATUS_LABELS[incident.status]}
        </span>
      </div>
    </Link>
  )
}
