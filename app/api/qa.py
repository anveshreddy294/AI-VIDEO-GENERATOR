"""Step 4 API — Source-Grounded Q&A with Dual-Traceability.

Endpoints:
- POST /qa/answer                          -> Generate grounded answer with source & video citations
- GET  /qa/traces/{user_id}/{source_id}    -> Retrieve historical answer traces for auditing
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..services.qa.grounded_answer import generate_grounded_answer, list_answer_traces
from ..services.schemas import QARequest, QAResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["Step 4 — Grounded Q&A"])


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
async def ask_grounded_question(request: QARequest) -> QAResponse:
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not request.source_id or not request.source_id.strip():
        raise HTTPException(status_code=400, detail="source_id is required.")

    try:
        response = await generate_grounded_answer(request)
        return response
    except Exception as exc:
        logger.exception("[qa] Error generating grounded answer for source %s", request.source_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate grounded answer. Please try again.",
        ) from exc


@router.get(
    "/traces/{user_id}/{source_id}",
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
        logger.exception("[qa] Failed to list answer traces for %s/%s", user_id, source_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve audit traces.") from exc
