"""Fail closed until legacy learning consumers have canonical tenant repositories."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from ...core.config import settings
from ...core.supabase import SupabaseConfigurationError, SupabaseError
from .auth import auth_http_error, bearer_scheme, get_runtime


def require_local_learning_storage() -> None:
    """Local legacy persistence is available only under an explicit local provider."""
    if settings.database_provider not in {'file', 'local'}:
        raise SupabaseConfigurationError('Canonical learning persistence is not integrated')


async def legacy_learning_boundary(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    """Authenticate before rejecting unsupported handlers; never inspect local resources."""
    if settings.database_provider in {'file', 'local'}:
        return
    if request.url.path == "/api/learning/explain":
        return
    if settings.database_provider != 'supabase':
        raise HTTPException(503, detail={'code': 'INVALID_DATABASE_PROVIDER',
                                       'message': 'Database provider is unavailable.'})
    if credentials is None:
        raise HTTPException(401, 'Bearer access token required',
                            headers={'WWW-Authenticate': 'Bearer'})
    try:
        user = await run_in_threadpool(get_runtime().verify_user, credentials.credentials)
    except SupabaseError as error:
        raise auth_http_error(error) from None
    request.state.authenticated_user = user
    for name in ('user_id', 'student_id'):
        label = request.path_params.get(name)
        if label is not None and str(label) != str(user.user_id):
            raise HTTPException(404, 'Resource not found')
    raise HTTPException(409, detail={'code': 'SUPABASE_LEARNING_NOT_INTEGRATED',
                                   'message': 'This operation requires canonical learning persistence and evidence verification.'})
