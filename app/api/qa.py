"""Step 4 API - Source-Grounded Q&A with Dual-Traceability.

Endpoints:
- POST /qa/answer                          -> Generate grounded answer with source & video citations
- GET  /qa/traces/{user_id}/{source_id}    -> Retrieve historical answer traces for auditing
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from ..core.config import settings
from ..core.supabase import SupabaseError
from ..core.reasoning import ProviderFailure
from ..services.security.auth import require_access_token, get_runtime
from ..services.security.legacy_boundary import legacy_learning_boundary
from ..services.repositories.knowledge_repository import (
    KnowledgeRepository,
    KnowledgeError,
)
from ..services.retrieval import (
    RetrievalRequest,
    RetrievalService,
    EvidenceBundle,
    IndexUnavailable,
)
from ..services.qa.canonical_answer import CanonicalQARequest, generate_canonical_answer
from ..services.learning_session import (
    SessionQARequest,
    LearningSessionService,
    SessionStorageUnavailable,
)

from ..services.qa.grounded_answer import generate_grounded_answer, list_answer_traces
from ..services.schemas import QARequest, QAResponse
from ..db.vector_store import RetrievalUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["Step 4 - Grounded Q&A"])


@router.post(
    "/answer",
    response_model=QAResponse,
    summary="Ask question grounded strictly in uploaded study materials and video scenes",
    description=(
        "Answers a student question by retrieving authoritative Layer A source chunks and optional "
        "Layer B video scenes (if playback timestamp is provided). Citations are verified and "
        "untrusted context is isolated from prompt instructions."
    ),
)
async def ask_grounded_question(http_request: Request) -> QAResponse:
    if settings.database_provider == "supabase":
        return await _canonical_answer(http_request)
    request = QARequest.model_validate(await http_request.json())
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not request.source_id or not request.source_id.strip():
        raise HTTPException(status_code=400, detail="source_id is required.")

    try:
        response = await generate_grounded_answer(request)
        return response
    except RetrievalUnavailable:
        raise HTTPException(
            503,
            detail={
                "code": "RETRIEVAL_UNAVAILABLE",
                "message": "No compatible semantic vectors available for this source.",
            },
        ) from None
    except Exception as exc:
        logger.exception(
            "[qa] Error generating grounded answer for source %s", request.source_id
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate grounded answer. Please try again.",
        ) from exc


@router.get(
    "/traces/{user_id}/{source_id}",
    dependencies=[Depends(legacy_learning_boundary)],
    summary="Retrieve audit traces for Q&A transactions",
    description="Returns chronological audit traces of questions, retrieved chunks, active scenes, and validated citations.",
)
async def get_qa_traces(
    user_id: str,
    source_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    try:
        return list_answer_traces(user_id=user_id, source_id=source_id, limit=limit)
    except Exception as exc:
        logger.exception(
            "[qa] Failed to list answer traces for %s/%s", user_id, source_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve audit traces."
        ) from exc


def _safe_error(error: KnowledgeError) -> HTTPException:
    status = {
        "NOT_FOUND": 404,
        "NOT_READY": 409,
        "INVALID_SCOPE": 422,
        "PROVIDER_UNAVAILABLE": 503,
        "INVALID_PROVIDER_RESPONSE": 502,
        "PAYLOAD_TOO_LARGE": 413,
        "CONFLICT": 409,
    }[error.code]
    return HTTPException(
        status, {"code": error.code, "message": "Evidence scope unavailable"}
    )


async def _context(request: Request) -> KnowledgeRepository:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer ") or not header[7:].strip():
        raise HTTPException(401, "Bearer access token required")
    from ..services.repositories.factory import get_knowledge_repository
    from ..services.security.auth import auth_http_error

    try:
        return await run_in_threadpool(
            get_knowledge_repository, token=header[7:].strip(), runtime=get_runtime()
        )
    except SupabaseError as error:
        raise auth_http_error(error) from None


async def _canonical_answer(request: Request) -> QAResponse:
    context = await _context(request)
    try:
        raw = await request.body()
        from pydantic import TypeAdapter, JsonValue

        value = TypeAdapter(dict[str, JsonValue]).validate_json(raw)
        if "session_id" in value:
            session_request = SessionQARequest.model_validate_json(raw)
            body = await run_in_threadpool(
                LearningSessionService(context).qa_request, session_request
            )
        else:
            body = CanonicalQARequest.model_validate_json(raw)
    except (ValidationError, ValueError):
        raise HTTPException(
            422,
            {
                "code": "INVALID_SCOPE",
                "message": "Explicit source version and valid selectors required",
            },
        ) from None
    except KnowledgeError as error:
        raise _safe_error(error) from None
    except SessionStorageUnavailable:
        raise HTTPException(503, {"code": "SESSION_STORAGE_UNAVAILABLE"}) from None
    try:
        return await generate_grounded_answer(body, context=context)
    except KnowledgeError as error:
        raise _safe_error(error) from None
    except IndexUnavailable as error:
        raise HTTPException(
            503,
            {
                "code": error.code,
                "message": "Evidence service unavailable; retry later",
            },
        ) from None
    except ProviderFailure as error:
        raise HTTPException(
            503, {"code": "PROVIDER_UNAVAILABLE", "category": error.category}
        ) from None


@router.post("/evidence", response_model=EvidenceBundle)
async def retrieve_evidence(request: Request) -> EvidenceBundle:
    context = await _context(request)
    try:
        body = RetrievalRequest.model_validate(await request.json())
        return await run_in_threadpool(RetrievalService().retrieve, context, body)
    except (ValidationError, ValueError):
        raise HTTPException(422, {"code": "INVALID_SCOPE"}) from None
    except KnowledgeError as error:
        raise _safe_error(error) from None
    except IndexUnavailable as error:
        raise HTTPException(503, {"code": error.code}) from None
