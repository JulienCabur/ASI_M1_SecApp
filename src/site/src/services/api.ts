/**
 * Instance axios centralisée pour les appels au backend BFF.
 *
 * - `withCredentials: true` pour transporter le cookie session httpOnly.
 * - Interceptor de requête : pour toute mutation (POST/PUT/PATCH/DELETE), on
 *   relit le cookie CSRF `secuapp_csrf` (lisible côté JS car non httpOnly) et
 *   on le renvoie dans l'en-tête `X-CSRF-Token`. Le back compare cookie vs
 *   header (double-submit).
 * - Interceptor de réponse : on convertit les erreurs HTTP en `ApiError` pour
 *   garder une surface d'erreur stable côté consommateurs.
 */

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
  const method = (config.method ?? 'get').toLowerCase();
  if (MUTATION_METHODS.has(method)) {
    const csrf = readCsrfToken();
    if (csrf) config.headers.set('X-CSRF-Token', csrf);
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const body = error.response.data;
      const detail =
        body && typeof body === 'object' && 'detail' in body
          ? String((body as { detail: unknown }).detail)
          : error.response.statusText;
      return Promise.reject(new ApiError(detail, error.response.status, body));
    }
    return Promise.reject(new ApiError(error.message, 0, null));
  },
);
