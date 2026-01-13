import React, { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import Layout from './components/Layout';
import { RequireAuth, RequireRole } from './components/AuthGuards';
import { useAuth } from './hooks/useAuth';
import FullPageSpinner from './components/feedback/FullPageSpinner';
import AppErrorBoundary from './components/feedback/AppErrorBoundary';
import { userHasRole } from './utils/roles';

const BillingPage = lazy(() => import('./pages/BillingPage'));
const CommunicationsPage = lazy(() => import('./pages/CommunicationsPage'));
const ContractsPage = lazy(() => import('./pages/ContractsPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const AdminWorkflowsPage = lazy(() => import('./pages/AdminWorkflowsPage'));
const OwnerProfilePage = lazy(() => import('./pages/OwnerProfilePage'));
const OwnersPage = lazy(() => import('./pages/OwnersPage'));
const ViolationsPage = lazy(() => import('./pages/ViolationsPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const ElectionsPage = lazy(() => import('./pages/ElectionsPage'));
const PublicVotePage = lazy(() => import('./pages/PublicVotePage'));
const ReconciliationPage = lazy(() => import('./pages/ReconciliationPage'));
const ARCPage = lazy(() => import('./pages/ARCPage'));
const BudgetPage = lazy(() => import('./pages/BudgetPage'));
const PaperworkPage = lazy(() => import('./pages/PaperworkPage'));
const AuditLogPage = lazy(() => import('./pages/AuditLogPage'));
const DocumentsPage = lazy(() => import('./pages/DocumentsPage'));
const MeetingsPage = lazy(() => import('./pages/MeetingsPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const TemplatesPage = lazy(() => import('./pages/TemplatesPage'));
const LegalPage = lazy(() => import('./pages/LegalPage'));

const App: React.FC = () => {
  const { user, loading } = useAuth();
  const loadingScreen = <FullPageSpinner label="Bootstrapping session…" />;
  const defaultRoute = userHasRole(user, 'LEGAL') ? '/legal' : '/dashboard';

  return (
    <AppErrorBoundary>
      <Suspense fallback={<FullPageSpinner label="Loading page…" />}>
        <Routes>
        <Route
          path="/login"
          element={user ? <Navigate to={defaultRoute} replace /> : loading ? loadingScreen : <LoginPage />}
        />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to={defaultRoute} replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="billing" element={<BillingPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="meetings" element={<MeetingsPage />} />
        <Route
          path="budget"
          element={
            <RequireRole allowed={['BOARD', 'TREASURER', 'SYSADMIN']}>
              <BudgetPage />
            </RequireRole>
          }
        />
        <Route
          path="board/paperwork"
          element={
            <RequireRole allowed={['BOARD', 'TREASURER', 'SECRETARY', 'SYSADMIN']}>
              <PaperworkPage />
            </RequireRole>
          }
        />
        <Route path="owner-profile" element={<OwnerProfilePage />} />
        <Route
          path="owners"
          element={
            <RequireRole allowed={["BOARD", "TREASURER", "SECRETARY", "SYSADMIN"]}>
              <OwnersPage />
            </RequireRole>
          }
        />
        <Route
          path="contracts"
          element={
            <RequireRole allowed={["BOARD", "TREASURER", "ATTORNEY", "SYSADMIN", "LEGAL"]}>
              <ContractsPage />
            </RequireRole>
          }
        />
        <Route
          path="communications"
          element={
            <RequireRole allowed={["BOARD", "SECRETARY", "SYSADMIN"]}>
              <CommunicationsPage />
            </RequireRole>
          }
        />
        <Route
          path="templates"
          element={
            <RequireRole allowed={["SYSADMIN"]}>
              <TemplatesPage />
            </RequireRole>
          }
        />
        <Route
          path="legal"
          element={
            <RequireRole allowed={["LEGAL", "SYSADMIN"]}>
              <LegalPage />
            </RequireRole>
          }
        />
        <Route
          path="violations"
          element={
            <RequireRole allowed={["BOARD", "TREASURER", "SYSADMIN", "SECRETARY", "ATTORNEY", "HOMEOWNER"]}>
              <ViolationsPage />
            </RequireRole>
          }
        />
        <Route
          path="elections"
          element={
            <RequireRole allowed={["BOARD", "SYSADMIN", "SECRETARY", "TREASURER", "ATTORNEY", "HOMEOWNER"]}>
              <ElectionsPage />
            </RequireRole>
          }
        />
        <Route
          path="arc"
          element={
            <RequireRole allowed={["BOARD", "ARC", "SYSADMIN", "SECRETARY", "TREASURER", "HOMEOWNER"]}>
              <ARCPage />
            </RequireRole>
          }
        />
        <Route
          path="reports"
          element={
            <RequireRole allowed={["BOARD", "SYSADMIN"]}>
              <ReportsPage />
            </RequireRole>
          }
        />
        <Route
          path="reconciliation"
          element={
            <RequireRole allowed={["BOARD", "TREASURER", "SYSADMIN"]}>
              <ReconciliationPage />
            </RequireRole>
          }
        />
        <Route
          path="admin"
          element={
            <RequireRole allowed={["SYSADMIN"]}>
              <AdminPage />
            </RequireRole>
          }
        />
        <Route
          path="admin/workflows"
          element={
            <RequireRole allowed={["SYSADMIN"]}>
              <AdminWorkflowsPage />
            </RequireRole>
          }
        />
        <Route
          path="audit-log"
          element={
            <RequireRole allowed={["SYSADMIN", "AUDITOR"]}>
              <AuditLogPage />
            </RequireRole>
          }
        />
      </Route>
      <Route path="/vote/:electionId" element={<PublicVotePage />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </AppErrorBoundary>
  );
};

export default App;
