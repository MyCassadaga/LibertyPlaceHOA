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
import OwnerProfilePage from './pages/OwnerProfilePage';
import OwnersPage from './pages/OwnersPage';

const App: React.FC = () => {
  const { user } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />}
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
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default App;
