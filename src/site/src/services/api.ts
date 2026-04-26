/**
 * Helper centralisé pour les appels API vers le backend BFF.
 *
 * - `credentials: 'include'` pour transporter le cookie session httpOnly.
 * - Pour toute mutation (POST/PUT/PATCH/DELETE), on relit le cookie CSRF
 *   `secuapp_csrf` (lisible côté JS car non httpOnly) et on le renvoie dans
 *   l'en-tête `X-CSRF-Token`. Le back compare cookie vs header (double-submit).
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/fastapi';
const CSRF_COOKIE_NAME = 'secuapp_csrf';
const MUTATION_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

const readCsrfToken = (): string | null => {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

interface ApiOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

export const apiFetch = async <T = unknown>(path: string, options: ApiOptions = {}): Promise<T> => {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = new Headers(options.headers);

  let body: BodyInit | undefined;
  if (options.body !== undefined && options.body !== null) {
    if (options.body instanceof FormData || options.body instanceof Blob) {
      body = options.body as BodyInit;
    } else {
      headers.set('Content-Type', 'application/json');
      body = JSON.stringify(options.body);
    }
  }

  if (MUTATION_METHODS.has(method)) {
    const csrf = readCsrfToken();
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    method,
    headers,
    credentials: 'include',
    body,
  });

  const contentType = response.headers.get('content-type') ?? '';
  const parsed: unknown =
    response.status === 204
      ? null
      : contentType.includes('application/json')
        ? await response.json()
        : await response.text();

  if (!response.ok) {
    const detail =
      parsed && typeof parsed === 'object' && 'detail' in parsed
        ? (parsed as { detail: string }).detail
        : response.statusText;
    throw new ApiError(detail, response.status, parsed);
  }

  return parsed as T;
};
