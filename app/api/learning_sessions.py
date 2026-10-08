"""Owned durable focused sessions; deployment pending is an explicit service state."""

from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .qa import _context, _safe_error
from ..services.learning_session import (
    CreateLearningSession,
    LearningSession,
    SessionView,
    SessionSelection,
    LearningSessionService,
    LearningSessionRepository,
    SessionStorageUnavailable,
)
from ..services.repositories.knowledge_repository import KnowledgeError

router = APIRouter(prefix="/learning-sessions", tags=["Focused learning"])


def storage_error() -> HTTPException:
    return HTTPException(
        503,
        {
            "code": "SESSION_STORAGE_UNAVAILABLE",
            "message": "Focused sessions are unavailable. Session storage deployment may be pending.",
        },
    )


@router.get("", response_model=list[LearningSession])
async def list_sessions(request: Request) -> list[LearningSession]:
    context = await _context(request)
    try:
        return await run_in_threadpool(LearningSessionRepository(context).list)
    except SessionStorageUnavailable:
        raise storage_error() from None
    except KnowledgeError as error:
        raise _safe_error(error) from None


@router.post("", response_model=LearningSession)
async def create_session(request: Request) -> LearningSession:
    context = await _context(request)
    try:
        body = CreateLearningSession.model_validate_json(await request.body())
        return await run_in_threadpool(LearningSessionService(context).create, body)
    except ValidationError:
        raise HTTPException(422, {"code": "INVALID_SCOPE"}) from None
    except SessionStorageUnavailable:
        raise storage_error() from None
    except KnowledgeError as error:
        raise _safe_error(error) from None


@router.get("/{session_id}", response_model=SessionView)
async def read_session(session_id: UUID, request: Request) -> SessionView:
    context = await _context(request)
    try:
        return await run_in_threadpool(LearningSessionService(context).get, session_id)
    except SessionStorageUnavailable:
        raise storage_error() from None
    except KnowledgeError as error:
        raise _safe_error(error) from None


@router.post("/{session_id}/selection", response_model=LearningSession)
async def change_session_selection(
    session_id: UUID, request: Request
) -> LearningSession:
    context = await _context(request)
    try:
        body = SessionSelection.model_validate_json(await request.body())
        return await run_in_threadpool(
            LearningSessionService(context).change_selection, session_id, body
        )
    except ValidationError:
        raise HTTPException(422, {"code": "INVALID_SCOPE"}) from None
    except SessionStorageUnavailable:
        raise storage_error() from None
    except KnowledgeError as error:
        raise _safe_error(error) from None


@router.post("/{session_id}/resume", response_model=LearningSession)
@router.post("/{session_id}/complete", response_model=LearningSession)
@router.post("/{session_id}/abandon", response_model=LearningSession)
async def session_operation(session_id: UUID, request: Request) -> LearningSession:
    context = await _context(request)
    if await request.body():
        raise HTTPException(422, {"code": "INVALID_SCOPE"})
    action = request.url.path.rsplit("/", 1)[-1]
    if action not in ("resume", "complete", "abandon"):
        raise HTTPException(422, {"code": "INVALID_SCOPE"})
    try:
        return await run_in_threadpool(
            LearningSessionService(context).transition, session_id, action
        )
    except SessionStorageUnavailable:
        raise storage_error() from None
    except KnowledgeError as error:
        raise _safe_error(error) from None


from ..services.grounded_notes import (
    GroundedNotesService,
    GroundedNotes,
    NotesOptions,
    NotesRequest,
    NotesError,
)
from ..core.reasoning import ProviderFailure


@router.post("/{session_id}/notes", response_model=GroundedNotes)
async def generate_session_notes(session_id: UUID, request: Request) -> GroundedNotes:
    """Generate only owned, session-scoped notes; there is no persistence or scope override."""
    context = await _context(request)
    try:
        options = NotesOptions.model_validate_json((await request.body()) or b"{}")
        body = NotesRequest(session_id=session_id, **options.model_dump())
        return await run_in_threadpool(GroundedNotesService(context).generate, body)
    except ValidationError:
        raise HTTPException(422, {"code": "INVALID_NOTES_REQUEST"}) from None
    except SessionStorageUnavailable:
        raise storage_error() from None
    except KnowledgeError as error:
        raise _safe_error(error) from None
    except ProviderFailure:
        raise HTTPException(503, {"code": "NOTES_PROVIDER_UNAVAILABLE"}) from None
    except NotesError as error:
        raise HTTPException(
            422 if error.code == "INVALID_NOTES" else 409, {"code": error.code}
        ) from None


from typing import Literal
from ..core.reasoning import ProviderFailure
from ..services.assessment.schemas import SessionAssessmentRequest, CanonicalSubmission, AssessmentStartResponse, AssessmentPerformance
from ..services.assessment.session_assessment import SessionAssessmentService, AssessmentInsufficientEvidence


async def _assessment_action(request: Request, learning_session_id: UUID,
                             action: Literal["start", "get", "submit", "result"],
                             assessment_id: str = "") -> AssessmentStartResponse | AssessmentPerformance:
    context = await _context(request)
    service = SessionAssessmentService(context)
    try:
        if action == "start":
            body = SessionAssessmentRequest.model_validate_json(await request.body())
            return await run_in_threadpool(service.start,learning_session_id,body)
        if action == "submit":
            submission = CanonicalSubmission.model_validate_json(await request.body())
            return await run_in_threadpool(service.submit,learning_session_id,assessment_id,submission)
        if action == "result":
            return await run_in_threadpool(service.result,learning_session_id,assessment_id)
        return await run_in_threadpool(service.get,learning_session_id,assessment_id)
    except ValidationError:
        raise HTTPException(422,{"code":"INVALID_ASSESSMENT_REQUEST"}) from None
    except AssessmentInsufficientEvidence:
        raise HTTPException(409,{"code":"INSUFFICIENT_EVIDENCE"}) from None
    except KnowledgeError as error:
        raise _safe_error(error) from None
    except SessionStorageUnavailable:
        raise storage_error() from None
    except ProviderFailure:
        raise HTTPException(503,{"code":"ASSESSMENT_PROVIDER_UNAVAILABLE"}) from None


@router.post("/{session_id}/assessment", response_model=AssessmentStartResponse)
async def start_session_assessment(session_id: UUID, request: Request) -> AssessmentStartResponse | AssessmentPerformance:
    return await _assessment_action(request,session_id,"start")


@router.get("/{session_id}/assessments/{assessment_id}",response_model=AssessmentStartResponse)
async def get_session_assessment(session_id: UUID, assessment_id: str, request: Request) -> AssessmentStartResponse | AssessmentPerformance:
    return await _assessment_action(request,session_id,"get",assessment_id)


@router.post("/{session_id}/assessments/{assessment_id}/submit",response_model=AssessmentPerformance)
async def submit_session_assessment(session_id: UUID, assessment_id: str, request: Request) -> AssessmentStartResponse | AssessmentPerformance:
    return await _assessment_action(request,session_id,"submit",assessment_id)


@router.get("/{session_id}/assessments/{assessment_id}/result",response_model=AssessmentPerformance)
async def get_session_assessment_result(session_id: UUID, assessment_id: str, request: Request) -> AssessmentStartResponse | AssessmentPerformance:
    return await _assessment_action(request,session_id,"result",assessment_id)
