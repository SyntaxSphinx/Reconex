import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  AnalyticsIcon,
  InvestigationsIcon,
  OverviewIcon,
  PaymentsIcon,
  ReconexMark,
} from '../assets/icons'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: OverviewIcon, end: true },
  { to: '/investigations', label: 'Investigations', icon: InvestigationsIcon, end: false },
  { to: '/payments', label: 'Payments', icon: PaymentsIcon, end: false },
  { to: '/analytics', label: 'Analytics', icon: AnalyticsIcon, end: true },
] as const

function exceptionIdFromPath(pathname: string): string | undefined {
  const match = pathname.match(/^\/investigations\/([^/]+)$/)
  return match ? decodeURIComponent(match[1]) : undefined
}

function incidentIdFromPath(pathname: string): string | undefined {
  const match = pathname.match(/^\/incidents\/([^/]+)$/)
  return match ? decodeURIComponent(match[1]) : undefined
}

function paymentIdFromPath(pathname: string): string | undefined {
  const match = pathname.match(/^\/payments\/([^/]+)$/)
  return match ? decodeURIComponent(match[1]) : undefined
}

function breadcrumbLabel(
  pathname: string,
  exceptionId?: string,
  incidentId?: string,
  paymentId?: string,
) {
  if (pathname === '/') return 'Overview'
  if (exceptionId) return exceptionId
  if (incidentId) return incidentId
  if (paymentId) return paymentId
  if (pathname.startsWith('/investigations')) return 'Investigations'
  if (pathname.startsWith('/incidents')) return 'Incidents'
  if (pathname.startsWith('/payments')) return 'Payments'
  if (pathname.startsWith('/analytics')) return 'Analytics'
  return 'Overview'
}

export function AppLayout() {
  const location = useLocation()
  const exceptionId = exceptionIdFromPath(location.pathname)
  const incidentId = incidentIdFromPath(location.pathname)
  const paymentId = paymentIdFromPath(location.pathname)
  const label = breadcrumbLabel(
    location.pathname,
    exceptionId,
    incidentId,
    paymentId,
  )
  const onInvestigationDetail = Boolean(exceptionId)
  const onIncidentDetail = Boolean(incidentId)
  const onPaymentDetail = Boolean(paymentId)

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-mark">
            <span className="logo-icon" aria-hidden="true">
              <ReconexMark />
            </span>
            <h1 className="logo">Reconex</h1>
          </div>
          <p className="logo-subtitle">Reconciliation Engine</p>
        </div>

        <nav className="nav" aria-label="Primary">
          <p className="nav-caption">Operations</p>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <span className="nav-item-icon">
                  <Icon />
                </span>
                {item.label}
              </NavLink>
            )
          })}
        </nav>
      </aside>

      <div className="main-container">
        <header className="header">
          <div className="header-content">
            <div className="breadcrumb">
              {onInvestigationDetail ? (
                <>
                  <NavLink to="/investigations" className="breadcrumb-item">
                    Investigations
                  </NavLink>
                  <span className="breadcrumb-sep text-tertiary">/</span>
                  <span className="breadcrumb-item active">{label}</span>
                </>
              ) : onIncidentDetail ? (
                <>
                  <NavLink to="/incidents" className="breadcrumb-item">
                    Incidents
                  </NavLink>
                  <span className="breadcrumb-sep text-tertiary">/</span>
                  <span className="breadcrumb-item active">{label}</span>
                </>
              ) : onPaymentDetail ? (
                <>
                  <NavLink to="/payments" className="breadcrumb-item">
                    Payments
                  </NavLink>
                  <span className="breadcrumb-sep text-tertiary">/</span>
                  <span className="breadcrumb-item active">{label}</span>
                </>
              ) : (
                <span className="breadcrumb-item active">{label}</span>
              )}
            </div>

            <div className="header-actions">
              <button className="btn-ghost" type="button" aria-label="Notifications">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 16a2 2 0 001.985-1.75c.017-.137-.097-.25-.235-.25h-3.5c-.138 0-.252.113-.235.25A2 2 0 008 16z"/>
                  <path d="M8 1.918l-.797.161A4.002 4.002 0 004 6c0 .628-.134 2.197-.459 3.742-.16.767-.376 1.566-.663 2.258h10.244c-.287-.692-.502-1.49-.663-2.258C12.134 8.197 12 6.628 12 6a4.002 4.002 0 00-3.203-3.92L8 1.917zM14.22 12c.223.447.481.801.78 1H1c.299-.199.557-.553.78-1C2.68 10.2 3 6.88 3 6c0-2.42 1.72-4.44 4.005-4.901a1 1 0 111.99 0A5.002 5.002 0 0113 6c0 .88.32 4.2 1.22 6z"/>
                </svg>
              </button>

              <div className="user-menu">
                <div className="user-avatar">OP</div>
              </div>
            </div>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
