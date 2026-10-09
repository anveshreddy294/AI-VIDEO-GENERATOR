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
        tolerant = options.tolerant_diagrams if "tolerant_diagrams" in options.model_fields_set else True
        ai_supp = options.include_ai_supplemental if "include_ai_supplemental" in options.model_fields_set else True
        dump = options.model_dump()
        dump["tolerant_diagrams"] = tolerant
        dump["include_ai_supplemental"] = ai_supp
        body = NotesRequest(session_id=session_id, **dump)
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


from ..services.mastery.session_learning import SessionLearningService, LearningProgress, FinalizeAssessment


async def _learning_action(request: Request, session_id: UUID, action: Literal["get", "finalize", "complete", "reassess"], job_id: str = "") -> LearningProgress | AssessmentStartResponse:
    context = await _context(request)
    service = SessionLearningService(context)
    try:
        if action == "finalize":
            body = FinalizeAssessment.model_validate_json(await request.body())
            return await run_in_threadpool(service.finalize,session_id,body.assessment_id)
        if action == "reassess":
            assessment = SessionAssessmentRequest.model_validate_json(await request.body())
            return await run_in_threadpool(service.reassess,session_id,job_id,assessment)
        if action == "complete":
            if await request.body():
                raise HTTPException(422,{"code":"INVALID_LEARNING_REQUEST"})
            return await run_in_threadpool(service.complete,session_id,job_id)
        return await run_in_threadpool(service.get,session_id)
    except ValidationError:
        raise HTTPException(422,{"code":"INVALID_LEARNING_REQUEST"}) from None
    except AssessmentInsufficientEvidence:
        raise HTTPException(409,{"code":"INSUFFICIENT_EVIDENCE"}) from None
    except KnowledgeError as error:
        raise _safe_error(error) from None
    except SessionStorageUnavailable:
        raise storage_error() from None
    except ProviderFailure:
        raise HTTPException(503,{"code":"ASSESSMENT_PROVIDER_UNAVAILABLE"}) from None


@router.get("/{session_id}/mastery",response_model=LearningProgress)
async def get_session_mastery(session_id: UUID,request: Request) -> LearningProgress | AssessmentStartResponse:
    return await _learning_action(request,session_id,"get")


@router.post("/{session_id}/mastery/finalize",response_model=LearningProgress)
async def finalize_session_mastery(session_id: UUID,request: Request) -> LearningProgress | AssessmentStartResponse:
    return await _learning_action(request,session_id,"finalize")


@router.post("/{session_id}/remediation/{job_id}/complete",response_model=LearningProgress)
async def complete_session_remediation(session_id: UUID,job_id: str,request: Request) -> LearningProgress | AssessmentStartResponse:
    return await _learning_action(request,session_id,"complete",job_id)


@router.post("/{session_id}/remediation/{job_id}/reassessment",response_model=AssessmentStartResponse)
async def reassess_session_remediation(session_id: UUID,job_id: str,request: Request) -> LearningProgress | AssessmentStartResponse:
    return await _learning_action(request,session_id,"reassess",job_id)


from fastapi import BackgroundTasks
from fastapi.responses import FileResponse
from ..services.video.session_video import SessionVideo, SessionVideoStatus, render_session_video


@router.post("/{session_id}/remediation/{job_id}/video", response_model=SessionVideoStatus)
async def start_remediation_video(session_id: UUID, job_id: str, request: Request, background_tasks: BackgroundTasks) -> SessionVideoStatus:
    context = await _context(request)
    if (await request.body()) not in (b"", b"{}"):
        raise HTTPException(422, {"code": "INVALID_LEARNING_REQUEST"})
    adapter = SessionVideo(context, session_id, job_id)
    try:
        status, target = await run_in_threadpool(adapter.prepare)
        if target is not None:
            background_tasks.add_task(render_session_video, adapter, target, status.job_id)
        return status
    except KnowledgeError as error:
        raise _safe_error(error) from None


@router.get("/{session_id}/remediation/{job_id}/video", response_model=SessionVideoStatus)
async def read_remediation_video(session_id: UUID, job_id: str, request: Request) -> SessionVideoStatus:
    context = await _context(request)
    adapter = SessionVideo(context, session_id, job_id)
    try:
        return await run_in_threadpool(adapter.status)
    except KnowledgeError as error:
        raise _safe_error(error) from None


@router.get("/{session_id}/remediation/{job_id}/video/stream")
async def stream_remediation_video(session_id: UUID, job_id: str, request: Request) -> FileResponse:
    context = await _context(request)
    try:
        path = await run_in_threadpool(SessionVideo(context, session_id, job_id).stream_path)
        return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "private, no-store"})
    except KnowledgeError as error:
        raise _safe_error(error) from None
