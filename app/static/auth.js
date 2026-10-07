// @ts-check
/**
 * @typedef {{access_token:string, refresh_token:string, token_type:string, expires_in:number}} Session
 * @typedef {{confirmation_required:boolean, session:Session|null, user_id:string|null}} AuthResult
 * @typedef {{session:Session, expiresAt:number}} StoredSession
 */
(function () {
    'use strict';
    const STORAGE_KEY = 'visualai.auth.session';
    const MILLISECONDS_PER_SECOND = 1000;
    const REFRESH_MARGIN_MS = 30000;
    /** @type {Promise<void>|null} */
    let refreshInFlight = null;

    /** @param {unknown} value @returns {value is Session} */
    function isSession(value) {
        if (!value || typeof value !== 'object') return false;
        const session = /** @type {Record<string, unknown>} */ (value);
        return typeof session.access_token === 'string' && !!session.access_token &&
            typeof session.refresh_token === 'string' && !!session.refresh_token &&
            typeof session.token_type === 'string' && session.token_type.toLowerCase() === 'bearer' &&
            typeof session.expires_in === 'number' && Number.isFinite(session.expires_in) && session.expires_in > 0;
    }

    /** @param {unknown} value @returns {value is StoredSession} */
    function isStoredSession(value) {
        if (!value || typeof value !== 'object') return false;
        const stored = /** @type {Record<string, unknown>} */ (value);
        return isSession(stored.session) && typeof stored.expiresAt === 'number' && Number.isFinite(stored.expiresAt);
    }

    /** @returns {StoredSession|null} */
    function readSession() {
        try {
            const raw = sessionStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            const saved = /** @type {unknown} */ (JSON.parse(raw));
            if (!isStoredSession(saved)) throw new Error('Invalid stored session');
            return saved;
        } catch {
            sessionStorage.removeItem(STORAGE_KEY);
            return null;
        }
    }

    /** @param {AuthResult} result */
    function saveSession(result) {
        const session = result.session;
        if (!session || !session.access_token || !session.refresh_token ||
            session.token_type.toLowerCase() !== 'bearer' || !Number.isFinite(session.expires_in)) {
            throw new Error('Authentication did not return a valid session.');
        }
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({session,
            expiresAt: Date.now() + session.expires_in * MILLISECONDS_PER_SECOND}));
    }

    function expireSession() {
        sessionStorage.removeItem(STORAGE_KEY);
        window.location.assign('/login?reason=expired');
    }

    /** @param {string} path @param {Record<string, string>} body @returns {Promise<AuthResult>} */
    async function authRequest(path, body) {
        const response = await fetch(path, {method: 'POST', cache: 'no-store',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
        if (!response.ok) {
            // Map safe provider categories locally; never render upstream message text.
            /** @type {Record<string, string>} */
            const messages = {
                signup_disabled: 'New account registration is disabled. Contact the project administrator.',
                email_provider_disabled: 'Email registration is disabled. Contact the project administrator.',
                email_address_not_authorized: 'Confirmation email cannot be sent to this address. The project administrator must configure SMTP.',
                over_email_send_rate_limit: 'Confirmation email sending is rate limited. Try again later or contact the project administrator.',
                over_request_rate_limit: 'Too many authentication requests. Please try again later.',
                weak_password: 'Choose a stronger password that meets the account password requirements.',
                email_address_invalid: 'Enter a valid email address.',
                user_already_exists: 'An account already exists. Sign in instead.',
                email_exists: 'An account already exists. Sign in instead.',
                email_not_confirmed: 'Verify your email before signing in.',
                invalid_credentials: 'Email or password was not accepted.',
                unexpected_failure: 'Authentication email delivery failed. Contact the project administrator.',
                validation_failed: 'Check the email address and password requirements.'
            };
            let errorCode = '';
            try {
                const failure = await response.json();
                if (failure && typeof failure === 'object' && failure.detail &&
                    typeof failure.detail.code === 'string') errorCode = failure.detail.code;
            } catch { /* Fall back to safe HTTP-status messages for non-JSON failures. */ }
            if (Object.prototype.hasOwnProperty.call(messages, errorCode)) throw new Error(messages[errorCode]);
            throw new Error(response.status === 401 ? 'Email or password was not accepted.' :
                response.status === 422 ? 'Check the email address and password requirements.' :
                'Authentication is unavailable. Please try again.');
        }
        const value = /** @type {unknown} */ (await response.json());
        if (!value || typeof value !== 'object') throw new Error('Invalid authentication response.');
        const result = /** @type {Record<string, unknown>} */ (value);
        if (typeof result.confirmation_required !== 'boolean' ||
            !(result.session === null || isSession(result.session)) ||
            !(result.user_id === null || typeof result.user_id === 'string')) {
            throw new Error('Invalid authentication response.');
        }
        return /** @type {AuthResult} */ (result);
    }

    /** @param {string} email @param {string} password */
    async function login(email, password) {
        const result = await authRequest('/api/auth/login', {email, password});
        saveSession(result);
    }

    /** @param {string} email @param {string} password @param {string} fullName @returns {Promise<boolean>} */
    async function signup(email, password, fullName) {
        const result = await authRequest('/api/auth/signup', {email, password, full_name: fullName});
        if (result.confirmation_required) {
            sessionStorage.removeItem(STORAGE_KEY);
            return false;
        }
        saveSession(result);
        return true;
    }

    /** @returns {Promise<void>} */
    async function refreshSession() {
        if (!refreshInFlight) {
            refreshInFlight = (async () => {
                const saved = readSession();
                if (!saved) throw new Error('Sign in to continue.');
                const result = await authRequest('/api/auth/refresh', {refresh_token: saved.session.refresh_token});
                saveSession(result);
            })().finally(() => { refreshInFlight = null; });
        }
        return refreshInFlight;
    }

    /** @param {string} path @param {RequestInit} [options] @returns {Promise<Response>} */
    async function protectedFetch(path, options = {}) {
        const target = new URL(path, window.location.origin);
        if (target.origin !== window.location.origin) throw new Error('Protected requests must use this application.');
        let saved = readSession();
        if (!saved) {
            expireSession();
            throw new Error('Sign in to continue.');
        }
        if (Date.now() >= saved.expiresAt - REFRESH_MARGIN_MS) {
            try { await refreshSession(); }
            catch {
                expireSession();
                throw new Error('Your session expired. Please sign in again.');
            }
        }
        /** @returns {Promise<Response>} */
        const send = () => {
            saved = readSession();
            if (!saved) throw new Error('Sign in to continue.');
            const headers = new Headers(options.headers);
            headers.set('Authorization', 'Bearer ' + saved.session.access_token);
            return fetch(target.href, {...options, headers, cache: 'no-store'});
        };
        let response = await send();
        if (response.status === 401) {
            try {
                await refreshSession();
                response = await send();
            } catch {
                expireSession();
                throw new Error('Your session expired. Please sign in again.');
            }
            if (response.status === 401) {
                expireSession();
                throw new Error('Your session expired. Please sign in again.');
            }
        }
        return response;
    }

    /** @returns {Promise<{user_id:string,email:string|null}>} */
    async function currentIdentity() {
        const response = await protectedFetch('/api/auth/me');
        if (!response.ok) throw new Error('Could not verify your signed-in account.');
        const value = /** @type {unknown} */ (await response.json());
        if (!value || typeof value !== 'object') throw new Error('Invalid account response.');
        const identity = /** @type {Record<string, unknown>} */ (value);
        if (typeof identity.user_id !== 'string' || !(identity.email === null || typeof identity.email === 'string')) {
            throw new Error('Invalid account response.');
        }
        return {user_id: identity.user_id, email: identity.email};
    }

    async function logout() {
        try { await protectedFetch('/api/auth/logout', {method: 'POST'}); }
        finally {
            sessionStorage.removeItem(STORAGE_KEY);
            window.location.assign('/login');
        }
    }

    Object.assign(window, {VisualAIAuth: {login, signup, protectedFetch, currentIdentity, logout}});
})();
