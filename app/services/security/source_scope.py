"""Strict owner/source/integer-version contract validated against canonical records."""
from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from ...core.supabase import SupabaseResponseError
from ..repositories.source_repository import SourceVersion, SupabaseSourceRepository

MAX_SOURCE_VERSION = 2**31 - 1  # Deployed source_versions.version is PostgreSQL integer.

class SourceScope(BaseModel):
    """Server-owned immutable scope; display version labels are never relational keys."""
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    user_id: UUID
    source_id: Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')]
    source_version: Annotated[StrictInt, Field(gt=0, le=MAX_SOURCE_VERSION)]


def vector_version(version: int) -> str:
    """Map a positive relational integer to the existing Qdrant display representation."""
    if type(version) is not int or not 0 < version <= MAX_SOURCE_VERSION:
        raise ValueError('Source version must be a positive integer')
    return f'v{version}'


def relational_version(label: str) -> int:
    """Accept only canonical vN labels; never coerce arbitrary numbers or latest aliases."""
    if not isinstance(label, str) or re.fullmatch(r'v[1-9][0-9]*', label) is None:
        raise ValueError('Invalid source version display identifier')
    version = int(label[1:])
    vector_version(version)
    return version


def require_source_scope(
    repository: SupabaseSourceRepository, source_id: str, version: int,
) -> tuple[SourceScope, SourceVersion]:
    """Validate the caller-token binding and exact version; never select latest implicitly."""
    try:
        scope = SourceScope(user_id=repository.user.user_id, source_id=source_id,
                            source_version=version)
    except ValidationError:
        raise HTTPException(422, 'Invalid source scope') from None
    # The repository's JWT, not a supplied owner object, determines canonical ownership.
    verified = repository.runtime.verify_user(repository._token)
    if verified.user_id != scope.user_id:
        raise HTTPException(404, 'Source version not found')
    source = repository.get_source(source_id)
    row = repository.get_source_version(source_id, version) if source is not None else None
    if row is None:
        raise HTTPException(404, 'Source version not found')
    if (row.user_id != scope.user_id or row.source_id != source_id or row.version != version
            or row.source_version != vector_version(version)):
        raise SupabaseResponseError('Canonical source scope mismatch')
    return scope, row
