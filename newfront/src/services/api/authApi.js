import { jsonRequest, apiRequest, saveSession, clearStoredSession } from './client.js';

function storeResult(result) {
  if (result?.session) saveSession(result.session);
  return result;
}

export const authApi = {
  login: async (email, password) => storeResult(await jsonRequest('/api/auth/login', { method: 'POST', body: { email, password }, auth: false })),
  signup: async (email, password, fullName) => storeResult(await jsonRequest('/api/auth/signup', { method: 'POST', body: { email, password, full_name: fullName || null }, auth: false })),
  refresh: async () => storeResult(await jsonRequest('/api/auth/refresh', { method: 'POST', body: { refresh_token: JSON.parse(window.sessionStorage.getItem('visualai.auth.session') || '{}')?.session?.refresh_token }, auth: false })),
  me: () => jsonRequest('/api/auth/me'),
  logout: async () => {
    try { await apiRequest('/api/auth/logout', { method: 'POST' }); } finally { clearStoredSession(); }
  }
};
