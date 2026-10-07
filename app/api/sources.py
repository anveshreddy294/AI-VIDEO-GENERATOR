"""Source-only provider boundary and owner-scoped durable read/retry APIs."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from ..core.config import settings
from ..core.supabase import AuthenticatedUser
from ..services.schemas import SourceRecord, ContentUnit
from ..services.repositories.source_repository import SourceVersion
from pydantic import JsonValue
from ..services.repositories.factory import get_source_repository
from ..services.repositories.source_repository import SupabaseSourceRepository
from ..services.security.auth import bearer_scheme, get_current_user, get_runtime
from ..services.security.source_scope import require_source_scope

router = APIRouter(prefix='/sources', tags=['Sources'])


async def source_repository(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]) -> SupabaseSourceRepository | None:
    """Require verified Supabase ownership only when the provider is explicitly Supabase."""
    if settings.database_provider in {'file', 'local'}:
        return None
    if settings.database_provider != 'supabase':
        raise HTTPException(503, 'Unknown database provider')
    if credentials is None:
        raise HTTPException(401, 'Bearer access token required')
    runtime = get_runtime()
    user: AuthenticatedUser = await run_in_threadpool(get_current_user, credentials.credentials, runtime)
    repository = get_source_repository(user=user, token=credentials.credentials, runtime=runtime)
    if not isinstance(repository, SupabaseSourceRepository):
        raise HTTPException(503, 'Supabase source provider unavailable')
    return repository


SourceDependency = Annotated[SupabaseSourceRepository | None, Depends(source_repository)]


def require_source_repository(repo: SupabaseSourceRepository | None) -> SupabaseSourceRepository:
    if repo is None:
        raise HTTPException(409, 'This endpoint requires Supabase source mode')
    return repo


@router.get('/{source_id}')
def read_source(source_id: str, repository: SourceDependency) -> SourceRecord:
    repo = require_source_repository(repository)
    record = repo.get_source(source_id)
    if record is None:
        raise HTTPException(404, 'Source not found')
    return record


@router.get('/{source_id}/versions/{version}')
def read_version(source_id: str, version: int, repository: SourceDependency) -> SourceVersion:
    _, row = require_source_scope(require_source_repository(repository), source_id, version)
    return row


@router.get('/{source_id}/content-units')
def read_units(source_id: str, repository: SourceDependency, version: int | None = None) -> dict[str, list[ContentUnit]]:
    repo = require_source_repository(repository)
    if repo.get_source(source_id) is None:
        raise HTTPException(404, 'Source not found')
    return {'content_units': repo.get_content_units(source_id, version)}


@router.post('/{source_id}/retry-index')
def retry_index(source_id: str, repository: SourceDependency) -> dict[str, JsonValue]:
    from ..services.ingestion.source_ingestion import index_committed_source
    repo = require_source_repository(repository)
    record = repo.get_source(source_id)
    if record is None:
        raise HTTPException(404, 'Source not found')
    return index_committed_source(repo, record)
