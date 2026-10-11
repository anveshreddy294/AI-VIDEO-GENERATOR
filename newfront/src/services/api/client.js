import { ApiError, parseApiError } from './errors.js';

const SESSION_KEY = 'visualai.auth.session';
const DEFAULT_TIMEOUT_MS = 30_000;
const GENERATION_TIMEOUT_MS = 180_000;
let refreshPromise = null;

export function getApiBaseUrl() {
  return (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/$/, '');
}

export function getStoredSession() {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw);
    if (!stored?.session?.access_token || !stored?.session?.refresh_token) return null;
    return stored;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  const expiresAt = Date.now() + Math.max(0, Number(session.expires_in || 3600) - 30) * 1000;
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify({ session, expiresAt }));
}

export function clearStoredSession() {
  window.sessionStorage.removeItem(SESSION_KEY);
}

async function refreshSession() {
  const stored = getStoredSession();
  if (!stored?.session?.refresh_token) throw new ApiError('Session refresh token is missing', { status: 401, code: 'AUTHENTICATION_REQUIRED' });
  if (!refreshPromise) {
    refreshPromise = fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ refresh_token: stored.session.refresh_token })
    }).then(async response => {
      if (!response.ok) throw await parseApiError(response);
      const result = await response.json();
      if (!result.session) throw new ApiError('The authentication service returned no session', { status: 502, code: 'INVALID_RESPONSE' });
      saveSession(result.session);
      return result;
    }).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function shouldRefresh(stored) {
  return stored && Number.isFinite(stored.expiresAt) && stored.expiresAt <= Date.now();
}

async function requestOnce(path, options = {}, signal) {
  const {
    body,
    method = 'GET',
    headers: customHeaders = {},
    timeoutMs = DEFAULT_TIMEOUT_MS,
    auth = true,
    ...fetchOptions
  } = options;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  const headers = new Headers(customHeaders);
  if (body !== undefined && !(body instanceof FormData)) headers.set('Content-Type', 'application/json');
  headers.set('Accept', 'application/json');

  const stored = auth ? getStoredSession() : null;
  if (auth && shouldRefresh(stored)) await refreshSession();
  const current = auth ? getStoredSession() : null;
  if (auth && current?.session?.access_token) headers.set('Authorization', `Bearer ${current.session.access_token}`);

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...fetchOptions,
      method,
      headers,
      body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      cache: 'no-store'
    });
    return response;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

export async function apiRequest(path, options = {}, { retryAuth = true } = {}) {
  let response;
  try {
    response = await requestOnce(path, options, options.signal);
  } catch (error) {
    if (error?.name === 'AbortError') throw error;
    if (error?.status === 401) clearStoredSession();
    throw error;
  }
  if (response.status === 401 && options.auth !== false && retryAuth && getStoredSession()?.session?.refresh_token) {
    try {
      await refreshSession();
      response = await requestOnce(path, options, options.signal);
    } catch (refreshError) {
      clearStoredSession();
      throw refreshError;
    }
  }
  if (!response.ok) {
    if (response.status === 401) clearStoredSession();
    throw await parseApiError(response);
  }
  return response;
}

export async function jsonRequest(path, options = {}, config = {}) {
  const response = await apiRequest(path, options, config);
  if (response.status === 204) return null;
  try {
    return await response.json();
  } catch {
    throw new ApiError('The backend returned an invalid response shape', { status: 502, code: 'INVALID_RESPONSE' });
  }
}

export const requestTimeouts = {
  default: DEFAULT_TIMEOUT_MS,
  generation: GENERATION_TIMEOUT_MS,
  upload: 120_000,
  video: 30_000
};
