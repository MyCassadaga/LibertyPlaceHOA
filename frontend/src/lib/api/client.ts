import axios, { AxiosError } from 'axios';

const DEFAULT_API_BASE = 'http://localhost:8000';

const normalizeApiBase = (value: string | undefined): string => {
  if (!value) return '';
  const trimmed = value.trim();
  if (!trimmed) return '';
  return trimmed.replace(/\/+$/, '');
};

export const getApiBase = (): string => {
  const normalized = normalizeApiBase(import.meta.env.VITE_API_BASE as string | undefined);
  return normalized || DEFAULT_API_BASE;
};

export const API_BASE_URL = getApiBase();

export type ApiErrorPayload = {
  detail?: string;
  errors?: unknown;
};

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export const publicApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export const setAuthToken = (token: string | null): void => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
};

const logApiError = (error: AxiosError<ApiErrorPayload>) => {
  if (import.meta.env.DEV) {
    console.error('[API]', error.message, error.response?.data ?? error);
  }
};

const responseInterceptor = (error: AxiosError<ApiErrorPayload>) => {
  logApiError(error);
  return Promise.reject(error);
};

api.interceptors.response.use(undefined, responseInterceptor);
publicApi.interceptors.response.use(undefined, responseInterceptor);
