import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { fetchCurrentUser, login as apiLogin, setAuthToken } from '../services/api';
import { User } from '../types';

type AuthContextValue = {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  const refresh = useCallback(async () => {
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const me = await fetchCurrentUser();
      setUser(me);
    } catch (error) {
      console.error('Failed to refresh user', error);
      setUser(null);
      setToken(null);
    }
  }, [token]);

  const handleLogin = useCallback(async (email: string, password: string) => {
    setLoading(true);
    try {
      const tokenResponse = await apiLogin(email, password);
      setToken(tokenResponse.access_token);
      const me = await fetchCurrentUser();
      setUser(me);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setAuthToken(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, loading, login: handleLogin, logout, refresh }),
    [user, token, loading, handleLogin, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
};
