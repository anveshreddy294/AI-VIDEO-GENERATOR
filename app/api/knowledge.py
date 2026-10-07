"""One authenticated read-only canonical version knowledge endpoint."""

from __future__ import annotations
from typing import Annotated
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from ..core.config import settings
from ..core.supabase import SupabaseRuntime
from ..services.knowledge_models import KnowledgeMap
from ..services.knowledge_service import KnowledgeService
from ..services.repositories.knowledge_repository import (
    KnowledgeError,
    KnowledgeRepository,
)
from ..services.repositories.factory import get_knowledge_repository
from ..services.security.auth import get_runtime, require_access_token

router = APIRouter(prefix="/sources", tags=["Knowledge"])


def knowledge_repository(
    token: Annotated[str, Depends(require_access_token)],
    runtime: Annotated[SupabaseRuntime, Depends(get_runtime)],
) -> KnowledgeRepository:
    if settings.database_provider in {"file", "local"}:
        raise HTTPException(
            409,
            detail={
                "code": "NOT_READY",
                "message": "Canonical knowledge requires Supabase mode.",
            },
        )
    if settings.database_provider != "supabase":
        raise HTTPException(
            503,
            detail={
                "code": "PROVIDER_UNAVAILABLE",
                "message": "Knowledge provider unavailable.",
            },
        )
    return get_knowledge_repository(token=token, runtime=runtime)


@router.get(
    "/{source_id}/versions/{version}/knowledge",
    response_model=KnowledgeMap,
    operation_id="read_canonical_source_version_knowledge",
    responses={
        401: {"description": "Verified Bearer token required"},
        404: {"description": "Source version unavailable"},
        409: {"description": "Canonical provider not integrated in file mode"},
        422: {"description": "Invalid exact scope"},
        413: {"description": "Map exceeds bounded response limit"},
        502: {"description": "Invalid canonical provider response"},
        503: {"description": "Knowledge provider unavailable"},
    },
)
def read_knowledge(
    source_id: str,
    version: int,
    request: Request,
    response: Response,
    repository: Annotated[KnowledgeRepository, Depends(knowledge_repository)],
) -> KnowledgeMap:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    try:
        if request.query_params:
            raise KnowledgeError("INVALID_SCOPE")
        scope = repository.scope(source_id, version)
        return KnowledgeService(repository).get_knowledge_map(
            scope, request_id=str(uuid4())
        )
    except KnowledgeError as error:
        status = {
            "NOT_FOUND": 404,
            "NOT_READY": 409,
            "INVALID_SCOPE": 422,
            "PROVIDER_UNAVAILABLE": 503,
            "INVALID_PROVIDER_RESPONSE": 502,
            "PAYLOAD_TOO_LARGE": 413,
            "CONFLICT": 409,
        }[error.code]
        message = (
            "Source version unavailable"
            if error.code == "NOT_FOUND"
            else "Knowledge request could not be completed"
        )
        raise HTTPException(
            status,
            detail={"code": error.code, "message": message},
            headers={"Cache-Control": "private, no-store", "Vary": "Authorization"},
        ) from None
