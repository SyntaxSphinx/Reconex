import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { WorkspaceRefreshProvider } from './workspaceRefresh'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { IncidentDetailPage } from './pages/IncidentDetailPage'
import { IncidentsPage } from './pages/IncidentsPage'
import { InvestigationDetailPage } from './pages/InvestigationDetailPage'
import { InvestigationsPage } from './pages/InvestigationsPage'
import { OverviewPage } from './pages/OverviewPage'
import { PaymentDetailPage } from './pages/PaymentDetailPage'
import { PaymentsPage } from './pages/PaymentsPage'
import './App.css'

function App() {
  return (
    <WorkspaceRefreshProvider>
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/investigations" element={<InvestigationsPage />} />
        <Route
          path="/investigations/:exceptionId"
          element={<InvestigationDetailPage />}
        />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
        <Route path="/payments" element={<PaymentsPage />} />
        <Route path="/payments/:paymentId" element={<PaymentDetailPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
    </WorkspaceRefreshProvider>
  )
}

export default App
