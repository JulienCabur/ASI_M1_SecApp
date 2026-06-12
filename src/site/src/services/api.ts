import axios, { type AxiosError, type AxiosInstance } from 'axios';

export const API_BASE = '/fastapi';
const CSRF_COOKIE_NAME = 'secuapp_csrf';
const MUTATION_METHODS = new Set(['post', 'put', 'patch', 'delete']);

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

const readCsrfToken = (): string | null => {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  config.headers.set('X-Request-Timestamp', new Date().toISOString());
  const method = (config.method ?? 'get').toLowerCase();
  if (MUTATION_METHODS.has(method)) {
    const csrf = readCsrfToken();
    if (csrf) config.headers.set('X-CSRF-Token', csrf);
  }
  return config;
});

const extractDetailMessage = (body: unknown, fallback: string): string => {
  if (!body || typeof body !== 'object' || !('detail' in body)) return fallback;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const msg = (detail as { message: unknown }).message;
    if (typeof msg === 'string') return msg;
  }
  return fallback;
};

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const body = error.response.data;
      const detail = extractDetailMessage(body, error.response.statusText);
      return Promise.reject(new ApiError(detail, error.response.status, body));
    }
    return Promise.reject(new ApiError(error.message, 0, null));
  },
);
