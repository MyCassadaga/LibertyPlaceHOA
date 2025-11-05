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

import {
  fetchCurrentUser,
  login as apiLogin,
  refreshSession,
  setAuthToken,
} from '../services/api';
import { User } from '../types';

const ACCESS_STORAGE_KEY = 'hoa.token';
const REFRESH_STORAGE_KEY = 'hoa.refresh';

const readStoredTokens = (): { access: string | null; refresh: string | null } => {
  if (typeof window === 'undefined') {
    return { access: null, refresh: null };
  }
  const access = window.localStorage.getItem(ACCESS_STORAGE_KEY);
  const refresh = window.localStorage.getItem(REFRESH_STORAGE_KEY);
  return {
    access: access && access !== 'null' ? access : null,
    refresh: refresh && refresh !== 'null' ? refresh : null,
  };
};

type AuthContextValue = {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string, otp?: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const stored = readStoredTokens();
  const [token, setToken] = useState<string | null>(() => stored.access);
  const [refreshToken, setRefreshToken] = useState<string | null>(() => stored.refresh);
  const [loading, setLoading] = useState<boolean>(() => !!stored.access || !!stored.refresh);
  const hasBootstrapped = useRef(false);

  useEffect(() => {
    setAuthToken(token);
    if (typeof window !== 'undefined') {
      if (token) {
        window.localStorage.setItem(ACCESS_STORAGE_KEY, token);
      } else {
        window.localStorage.removeItem(ACCESS_STORAGE_KEY);
      }
      if (refreshToken) {
        window.localStorage.setItem(REFRESH_STORAGE_KEY, refreshToken);
      } else {
        window.localStorage.removeItem(REFRESH_STORAGE_KEY);
      }
    }
  }, [token, refreshToken]);

  const persistTokens = useCallback((access: string | null, refreshValue: string | null) => {
    setToken(access);
    setRefreshToken(refreshValue);
    setAuthToken(access);
    if (typeof window !== 'undefined') {
      if (access) {
        window.localStorage.setItem(ACCESS_STORAGE_KEY, access);
      } else {
        window.localStorage.removeItem(ACCESS_STORAGE_KEY);
      }
      if (refreshValue) {
        window.localStorage.setItem(REFRESH_STORAGE_KEY, refreshValue);
      } else {
        window.localStorage.removeItem(REFRESH_STORAGE_KEY);
      }
    }
  }, []);

  const attemptServerRefresh = useCallback(async () => {
    if (!refreshToken) {
      return false;
    }
    try {
      const refreshed = await refreshSession({ refresh_token: refreshToken });
      persistTokens(refreshed.access_token, refreshed.refresh_token);
      return true;
    } catch (error) {
      console.error('Failed to refresh session', error);
      persistTokens(null, null);
      setUser(null);
      return false;
    }
  }, [refreshToken, persistTokens]);

  const refresh = useCallback(async () => {
    if (!token && !refreshToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await fetchCurrentUser();
      setUser(me);
    } catch (error) {
      console.warn('Access token invalid, attempting refresh');
      const refreshed = await attemptServerRefresh();
      if (refreshed) {
        try {
          const me = await fetchCurrentUser();
          setUser(me);
        } catch (fetchError) {
          console.error('Failed to load user after refresh', fetchError);
          setUser(null);
        }
      } else {
        setUser(null);
      }
    }
    setLoading(false);
  }, [token, refreshToken, attemptServerRefresh]);

  const handleLogin = useCallback(async (email: string, password: string, otp?: string) => {
    setLoading(true);
    setUser(null);
    try {
      const tokenResponse = await apiLogin(email, password, otp);
      persistTokens(tokenResponse.access_token, tokenResponse.refresh_token);
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
      persistTokens(null, null);
      setUser(null);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  }, [persistTokens]);

  const logout = useCallback(() => {
    persistTokens(null, null);
    setLoading(false);
    setUser(null);
  }, [persistTokens]);

  useEffect(() => {
    if (hasBootstrapped.current) {
      return;
    }
    hasBootstrapped.current = true;
    if (token || refreshToken) {
      void refresh();
    } else {
      setLoading(false);
    }
  }, [token, refreshToken, refresh]);

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
