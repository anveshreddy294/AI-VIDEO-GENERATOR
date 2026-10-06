"""Verified Supabase user boundary; caller labels never authorize ownership."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ...core.config import settings
from ...core.supabase import (
    AuthenticatedUser, SupabaseAuthenticationError, SupabaseConfigurationError,
    SupabaseError, SupabaseResponseError, SupabaseRuntime, SupabaseUnavailable,
    get_supabase_runtime,
)

bearer_scheme = HTTPBearer(auto_error=False)


def is_supabase_auth_configured() -> bool:
    return bool(settings.supabase_url and (settings.supabase_publishable_key or settings.supabase_anon_key))


def auth_http_error(error: SupabaseError) -> HTTPException:
    if isinstance(error, SupabaseAuthenticationError):
        return HTTPException(401, 'Authentication failed', headers={'WWW-Authenticate': 'Bearer'})
    if isinstance(error, (SupabaseConfigurationError, SupabaseUnavailable)):
        return HTTPException(503, 'Supabase authentication service unavailable')
    if isinstance(error, SupabaseResponseError):
        return HTTPException(502, 'Supabase operation failed')
    return HTTPException(502, 'Supabase operation failed')


def get_runtime() -> SupabaseRuntime:
    try:
        return get_supabase_runtime()
    except SupabaseError as error:
        raise auth_http_error(error) from None


def require_access_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]) -> str:
    if credentials is None:
        raise HTTPException(401, 'Bearer access token required', headers={'WWW-Authenticate': 'Bearer'})
    return credentials.credentials


def get_current_user(token: Annotated[str, Depends(require_access_token)],
                     runtime: Annotated[SupabaseRuntime, Depends(get_runtime)]) -> AuthenticatedUser:
    """Resolve verified UUID and explicitly provision its RLS-scoped profile."""
    try:
        user = runtime.verify_user(token)
        runtime.ensure_profile(user, token)
        return user
    except SupabaseError as error:
        raise auth_http_error(error) from None


def extract_authenticated_user_id(authorization: str | None = None,
                                  fallback_user_id: str | None = None) -> str:
    """Compatibility entry point: fallback_user_id is metadata and never trusted."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(401, 'Bearer access token required', headers={'WWW-Authenticate': 'Bearer'})
    try:
        return str(get_supabase_runtime().verify_user(authorization.split(' ', 1)[1].strip()).user_id)
    except SupabaseError as error:
        raise auth_http_error(error) from None
