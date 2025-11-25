import axios, { AxiosError } from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

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
