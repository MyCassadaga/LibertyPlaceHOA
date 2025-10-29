import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { AxiosError } from 'axios';

import { fetchCurrentUser, login as apiLogin, setAuthToken } from '../services/api';
import { User } from '../types';

const STORAGE_KEY = 'hoa.token';

const readStoredToken = (): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored && stored !== 'null' ? stored : null;
};

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
  const [token, setToken] = useState<string | null>(() => readStoredToken());
  const [loading, setLoading] = useState<boolean>(() => !!readStoredToken());
  const hasBootstrapped = useRef(false);

  useEffect(() => {
    setAuthToken(token);
    if (typeof window !== 'undefined') {
      if (token) {
        window.localStorage.setItem(STORAGE_KEY, token);
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    }
  }, [token]);

  const refresh = useCallback(async () => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await fetchCurrentUser();
      setUser(me);
    } catch (error) {
      console.error('Failed to refresh user', error);
      setUser(null);
      setToken(null);
      setAuthToken(null);
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    }
    setLoading(false);
  }, [token]);

  const handleLogin = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setUser(null);
    try {
      const tokenResponse = await apiLogin(email, password);
      setToken(tokenResponse.access_token);
      setAuthToken(tokenResponse.access_token);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(STORAGE_KEY, tokenResponse.access_token);
      }
      const me = await fetchCurrentUser();
      setUser(me);
    } catch (error) {
      const axiosError = error as AxiosError<{ detail?: string }>;
      const status = axiosError?.response?.status;
      const detail = axiosError?.response?.data?.detail;
      const message =
        status === 401
          ? detail ?? 'Invalid credentials'
          : detail ?? 'Unable to sign in. Please try again.';
      setToken(null);
      setUser(null);
      setAuthToken(null);
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(STORAGE_KEY);
      }
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setLoading(false);
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    setUser(null);
    setAuthToken(null);
  }, []);

  useEffect(() => {
    if (hasBootstrapped.current) {
      return;
    }
    hasBootstrapped.current = true;
    if (token) {
      void refresh();
    } else {
      setLoading(false);
    }
  }, [token, refresh]);

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
