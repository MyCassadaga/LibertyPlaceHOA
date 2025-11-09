import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import Layout from './components/Layout';
import { RequireAuth, RequireRole } from './components/AuthGuards';
import { useAuth } from './hooks/useAuth';
import BillingPage from './pages/BillingPage';
import CommunicationsPage from './pages/CommunicationsPage';
import ContractsPage from './pages/ContractsPage';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';
import AdminPage from './pages/AdminPage';
import OwnerProfilePage from './pages/OwnerProfilePage';
import OwnersPage from './pages/OwnersPage';
import ViolationsPage from './pages/ViolationsPage';
import ReportsPage from './pages/ReportsPage';
import ElectionsPage from './pages/ElectionsPage';
import PublicVotePage from './pages/PublicVotePage';
import ReconciliationPage from './pages/ReconciliationPage';
import ARCPage from './pages/ARCPage';
import BudgetPage from './pages/BudgetPage';
import PaperworkPage from './pages/PaperworkPage';
import AuditLogPage from './pages/AuditLogPage';
import DocumentsPage from './pages/DocumentsPage';
import MeetingsPage from './pages/MeetingsPage';

const App: React.FC = () => {
  const { user, loading } = useAuth();
  const loadingScreen = <div className="p-6 text-sm text-slate-500">Loading…</div>;

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/dashboard" replace /> : loading ? loadingScreen : <LoginPage />}
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="billing" element={<BillingPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="meetings" element={<MeetingsPage />} />
        <Route
          path="budget"
          element={
            <RequireRole allowed={['HOMEOWNER', 'BOARD', 'TREASURER', 'SYSADMIN']}>
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
            <RequireRole allowed={["BOARD", "TREASURER", "ATTORNEY", "SYSADMIN"]}>
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
            <RequireRole allowed={["ARC", "BOARD", "SYSADMIN", "SECRETARY", "HOMEOWNER"]}>
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
  );
};

export default App;
