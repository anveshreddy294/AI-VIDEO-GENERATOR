"""Shared Supabase transport, server-verified identity and scoped profiles.

GoTrue /user performs cryptographic JWT verification for every supported signing
algorithm. Claims are parsed only AFTER that trusted server accepts the token;
issuer, audience, expiry and UUID identity are additionally checked here.
"""
from __future__ import annotations

import base64
import binascii
import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, JsonValue, StrictInt, TypeAdapter, ValidationError

from .config import Settings, settings

JSON_VALUE = TypeAdapter(JsonValue)
JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class SupabaseError(RuntimeError):
    """Public-safe Supabase failure; never contains upstream bodies or credentials."""


class SupabaseConfigurationError(SupabaseError):
    """Required environment configuration is missing or invalid."""


class SupabaseUnavailable(SupabaseError):
    """Supabase is unreachable, rate limited or returns a server failure."""


class SupabaseAuthenticationError(SupabaseError):
    """Credentials or verified token claims are invalid."""


class SupabaseResponseError(SupabaseError):
    """Supabase returned an unexpected response or rejected an operation."""


class SupabaseConflict(SupabaseResponseError):
    """A database uniqueness conflict, without forwarding the upstream body."""


AUTH_ERROR_MESSAGES: dict[str, str] = {
    "signup_disabled": "New account registration is disabled. Contact the project administrator.",
    "email_provider_disabled": "Email registration is disabled. Contact the project administrator.",
    "email_address_not_authorized": "Confirmation email cannot be sent to this address. The project administrator must configure SMTP.",
    "over_email_send_rate_limit": "Confirmation email sending is rate limited. Try again later or contact the project administrator.",
    "over_request_rate_limit": "Too many authentication requests. Please try again later.",
    "weak_password": "Choose a stronger password that meets the account password requirements.",
    "email_address_invalid": "Enter a valid email address.",
    "user_already_exists": "An account already exists. Sign in instead.",
    "email_exists": "An account already exists. Sign in instead.",
    "email_not_confirmed": "Verify your email before signing in.",
    "invalid_credentials": "Email or password was not accepted.",
    "unexpected_failure": "Authentication email delivery failed. Contact the project administrator.",
    "validation_failed": "Check the email address and password requirements.",
}


class SupabaseAuthOperationError(SupabaseError):
    """Preserve provider category without exposing its raw message or request credentials."""
    def __init__(self, code: str, status_code: int) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(AUTH_ERROR_MESSAGES.get(code, "Authentication request failed. Please try again later."))


@dataclass(frozen=True)
class SupabaseConfig:
    """Environment-only credentials; repr intentionally excludes all keys."""

    url: str
    public_key: str = field(repr=False)
    admin_key: str = field(default='', repr=False)
    audience: str = 'authenticated'
    timeout_seconds: float = 10.0
    confirmation_redirect_url: str = ''

    @classmethod
    def from_settings(cls, config: Settings) -> SupabaseConfig:
        return cls(config.supabase_url, config.supabase_publishable_key or config.supabase_anon_key,
                   config.supabase_secret_key or config.supabase_service_role_key,
                   config.supabase_jwt_audience, config.supabase_timeout_seconds, config.supabase_auth_redirect_url)

    def validate(self) -> None:
        """Reject credential-bearing URLs; confirmation redirects are configured server-side."""
        if self.confirmation_redirect_url:
            try:
                redirect = urlsplit(self.confirmation_redirect_url)
            except ValueError:
                raise SupabaseConfigurationError('Supabase confirmation redirect is invalid') from None
            local = redirect.scheme == 'http' and redirect.hostname in {'localhost', '127.0.0.1', '::1'}
            if (not redirect.hostname or (redirect.scheme != 'https' and not local) or
                    redirect.username or redirect.password or redirect.query or redirect.fragment or
                    redirect.path != '/login'):
                raise SupabaseConfigurationError('Supabase confirmation redirect must be an application login URL')
        try:
            parsed = urlsplit(self.url)
        except ValueError:
            raise SupabaseConfigurationError('Supabase URL is invalid') from None
        local_http = parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}
        if (not self.public_key or not parsed.hostname or
                (parsed.scheme != 'https' and not local_http) or parsed.username or
                parsed.password or parsed.query or parsed.fragment or parsed.path not in {'', '/'} or
                not self.audience or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise SupabaseConfigurationError('Supabase runtime configuration is missing or invalid')
        if self.public_key.startswith('sb_secret_'):
            raise SupabaseConfigurationError('Supabase public credential must not be a backend secret')


class JWTClaims(BaseModel):
    """Required claims checked after Auth server signature verification."""

    model_config = ConfigDict(strict=True, extra='allow')
    sub: str
    iss: str
    aud: str | list[str]
    exp: StrictInt
    nbf: StrictInt | None = None
    role: Literal['authenticated']


class AuthServerUser(BaseModel):
    """Minimal authoritative user data returned by Supabase Auth."""

    id: UUID
    email: str | None = None


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    email: str | None
    claims: Mapping[str, JsonValue] = field(repr=False)


class Profile(BaseModel):
    id: UUID
    full_name: str | None = None
    role: Literal['student', 'instructor', 'admin']
    created_at: str
    updated_at: str


class SupabaseRuntime:
    """One reusable HTTP pool; user/admin credentials are supplied per request."""

    def __init__(self, config: SupabaseConfig, *, transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        config.validate()
        self.config = config
        self._clock = clock
        self._http = httpx.Client(base_url=config.url.rstrip('/'), timeout=config.timeout_seconds,
                                  follow_redirects=False, transport=transport)

    def close(self) -> None:
        self._http.close()

    def _request(self, method: Literal['GET', 'POST', 'DELETE'], path: str, *,
                 token: str | None = None, admin: bool = False,
                 params: Mapping[str, str] | None = None,
                 body: dict[str, JsonValue] | None = None,
                 prefer: str | None = None, auth_operation: bool = False) -> JsonValue:
        if not path.startswith('/') or path.startswith('//'):
            raise SupabaseResponseError('Invalid Supabase endpoint')
        key = self.config.admin_key if admin else self.config.public_key
        if not key:
            raise SupabaseConfigurationError('Supabase backend credentials are not configured')
        headers = {'apikey': key, 'Accept': 'application/json'}
        if token is not None:
            headers['Authorization'] = f'Bearer {token}'
        elif admin and not key.startswith('sb_secret_'):
            headers['Authorization'] = f'Bearer {key}'
        if prefer:
            headers['Prefer'] = prefer
        try:
            response = self._http.request(method, path, headers=headers, params=params, json=body)
        except httpx.RequestError:
            raise SupabaseUnavailable('Supabase connection failed') from None
        if auth_operation and not response.is_success:
            try:
                failure = response.json()
            except ValueError:
                failure = None
            code = failure.get('code') if isinstance(failure, dict) else None
            # Only identifier-shaped categories may cross the public boundary; no raw error text.
            import re
            if not isinstance(code, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
                code = ('over_request_rate_limit' if response.status_code == 429 else 'auth_request_failed')
            raise SupabaseAuthOperationError(code, response.status_code)
        if response.status_code in {401, 403}:
            raise SupabaseAuthenticationError('Supabase authentication or authorization failed')
        if response.status_code == 429 or response.status_code >= 500:
            raise SupabaseUnavailable('Supabase service is unavailable')
        if response.status_code == 409:
            raise SupabaseConflict('Supabase write conflict')
        if not response.is_success:
            raise SupabaseResponseError('Supabase rejected the operation')
        if not response.content:
            return None
        try:
            return JSON_VALUE.validate_python(response.json())
        except (ValueError, ValidationError):
            raise SupabaseResponseError('Invalid Supabase response') from None

    def admin_request(self, method: Literal['GET', 'POST', 'DELETE'], path: str, *,
                      params: Mapping[str, str] | None = None,
                      body: dict[str, JsonValue] | None = None) -> JsonValue:
        """Backend-only transport; callers MUST separately authorize their operation."""
        return self._request(method, path, admin=True, params=params, body=body)

    def user_request(self, method: Literal['GET', 'POST', 'DELETE'], path: str, *, token: str,
                     params: Mapping[str, str] | None = None,
                     body: dict[str, JsonValue] | None = None) -> JsonValue:
        """Use the caller token with a public API key, preserving database RLS."""
        return self._request(method, path, token=token, params=params, body=body)

    def verify_user(self, token: str) -> AuthenticatedUser:
        """Verify signature at GoTrue, then validate project-specific token claims."""
        if len(token.split('.')) != 3:
            raise SupabaseAuthenticationError('Invalid access token')
        server_response = self._request('GET', '/auth/v1/user', token=token)
        try:
            server_user = AuthServerUser.model_validate(server_response)
            payload = token.split('.')[1]
            decoded = base64.b64decode(payload + '=' * (-len(payload) % 4), altchars=b'-_', validate=True)
            claims = JSON_OBJECT.validate_python(json.loads(decoded))
            checked = JWTClaims.model_validate(claims)
            subject = UUID(checked.sub)
        except (ValueError, ValidationError, binascii.Error, UnicodeDecodeError):
            raise SupabaseAuthenticationError('Invalid access token') from None
        audiences = [checked.aud] if isinstance(checked.aud, str) else checked.aud
        if (subject != server_user.id or checked.iss != self.config.url.rstrip('/') + '/auth/v1' or
                self.config.audience not in audiences or checked.exp <= self._clock() or
                (checked.nbf is not None and checked.nbf > self._clock())):
            raise SupabaseAuthenticationError('Invalid access token claims')
        return AuthenticatedUser(subject, server_user.email, claims)

    def ensure_profile(self, user: AuthenticatedUser, token: str) -> Profile:
        """Idempotent caller-scoped provisioning; never upsert privileged fields."""
        params = {'id': f'eq.{user.user_id}', 'select': 'id,full_name,role,created_at,updated_at'}
        rows = self.user_request('GET', '/rest/v1/profiles', token=token, params=params)
        if rows == []:
            self._request('POST', '/rest/v1/profiles', token=token, params={'on_conflict': 'id'},
                          body={'id': str(user.user_id)}, prefer='resolution=ignore-duplicates,return=minimal')
            rows = self.user_request('GET', '/rest/v1/profiles', token=token, params=params)
        try:
            if not isinstance(rows, list) or len(rows) != 1:
                raise ValueError('Expected one profile')
            profile = Profile.model_validate(rows[0])
            if profile.id != user.user_id:
                raise ValueError('Profile owner mismatch')
            return profile
        except (ValueError, ValidationError):
            raise SupabaseResponseError('Supabase profile provisioning failed') from None

    def signup(self, email: str, password: str, full_name: str | None = None) -> JsonValue:
        body: dict[str, JsonValue] = {'email': email, 'password': password}
        if full_name:
            body['data'] = {'full_name': full_name}
        return self._request('POST', '/auth/v1/signup', body=body, auth_operation=True,
                             params={'redirect_to': self.config.confirmation_redirect_url}
                             if self.config.confirmation_redirect_url else None)

    def login(self, email: str, password: str) -> JsonValue:
        """Auth failure responses are intentionally generic, including wrong passwords."""
        try:
            return self._request('POST', '/auth/v1/token', params={'grant_type': 'password'},
                                 body={'email': email, 'password': password}, auth_operation=True)
        except SupabaseAuthOperationError as error:
            if error.code == 'auth_request_failed' and error.status_code < 500:
                raise SupabaseAuthenticationError('Login failed') from None
            raise
        except SupabaseResponseError:
            raise SupabaseAuthenticationError('Login failed') from None

    def refresh(self, refresh_token: str) -> JsonValue:
        try:
            return self._request('POST', '/auth/v1/token', params={'grant_type': 'refresh_token'},
                                 body={'refresh_token': refresh_token})
        except SupabaseResponseError:
            raise SupabaseAuthenticationError('Session refresh failed') from None

    def logout(self, token: str) -> None:
        self._request('POST', '/auth/v1/logout', token=token, params={'scope': 'local'})

    def health(self) -> dict[str, bool | str]:
        """Actual Auth-service reachability; credentials and tokens are never returned."""
        try:
            self._request('GET', '/auth/v1/health')
        except SupabaseError:
            return {'configured': True, 'reachable': False, 'status': 'unreachable'}
        return {'configured': True, 'reachable': True, 'status': 'connected'}


@lru_cache(maxsize=1)
def get_supabase_runtime() -> SupabaseRuntime:
    """Lazily initialize exactly one connection pool for the process lifetime."""
    return SupabaseRuntime(SupabaseConfig.from_settings(settings))


def close_supabase_runtime() -> None:
    if get_supabase_runtime.cache_info().currsize:
        get_supabase_runtime().close()
        get_supabase_runtime.cache_clear()
