import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { userHasAnyRole } from '../utils/roles';

export const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading your session…</div>;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
};

export const RequireRole: React.FC<{ children: React.ReactNode; allowed: string[] }> = ({
  children,
  allowed,
}) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Checking access…</div>;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!userHasAnyRole(user, allowed)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
