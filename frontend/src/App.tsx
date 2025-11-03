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
import ReconciliationPage from './pages/ReconciliationPage';
import ARCPage from './pages/ARCPage';

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
            <RequireRole allowed={["BOARD", "TREASURER", "SYSADMIN"]}>
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
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default App;
