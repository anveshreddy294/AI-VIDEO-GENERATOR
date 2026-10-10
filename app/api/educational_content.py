"""Authenticated hierarchy-independent learning entry point; no fake source/session rows."""
import logging
from pathlib import Path
from typing import Any, Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from ..core.config import settings

logger = logging.getLogger(__name__)

from .sources import SourceDependency, require_source_repository
from ..core.reasoning import ProviderFailure
from ..services.educational_content import (
    AssessmentSubmission,
    AskResponse,
    ContentRequest,
    EducationalAssessment,
    EducationalContent,
    EducationalContentService,
    EducationalNotes,
    FlowchartDiagram,
    PublicAssessment,
    PublicDescriptive,
    PublicMCQ,
    SubmissionResult,
)

router = APIRouter(prefix="/educational-content", tags=["Educational content"])


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=4000)


class NotesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    detail_level: Literal["concise", "standard", "detailed"] = "standard"


def generation_error(code: str) -> HTTPException:
    logger.exception("Educational lesson operation failed: %s", code)
    return HTTPException(503, {"code": code})


@router.post("", response_model=EducationalContent)
async def generate_content(body: ContentRequest, repository: SourceDependency) -> EducationalContent:
    repo = require_source_repository(repository)
    try:
        return await run_in_threadpool(EducationalContentService(repo).generate, body)
    except PermissionError:
        raise HTTPException(404, {"code": "CONTENT_UNAVAILABLE"}) from None
    except ProviderFailure as error:
        raise HTTPException(503, {"code": error.category}) from None
    except (ValidationError, ValueError) as error:
        import logging

        logger = logging.getLogger(__name__)

        if isinstance(error, ValidationError):
            logger.error(
                "EDUCATIONAL_CONTENT_INVALID validation: %s",
                [
                    (item["loc"], item["type"])
                    for item in error.errors(
                        include_input=False,
                        include_context=False
                    )
                ],
                exc_info=False,
            )
        else:
            logger.error(
                "EDUCATIONAL_CONTENT_INVALID ValueError: %s",
                type(error).__name__,
                exc_info=False,
            )

        raise HTTPException(
            422,
            {"code": "EDUCATIONAL_CONTENT_INVALID",
             "message": "The model returned an invalid lesson. Retry generation; no lesson was saved.",
             "retryable": True}
        ) from None
    except Exception:
        raise generation_error("EDUCATIONAL_CONTENT_FAILED") from None


@router.get("")
async def list_lessons(repository: SourceDependency) -> dict[str, list[dict[str, Any]]]:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lessons = await run_in_threadpool(service.list_lessons)
    return {"lessons": lessons}


@router.get("/{lesson_id}")
async def get_lesson_detail(lesson_id: str, repository: SourceDependency) -> dict[str, Any]:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    
    # Strip secret answer keys from public response
    public_assessment = None
    if lesson.assessment is not None:
        public_assessment = PublicAssessment(
            assessment_id=lesson.assessment.assessment_id,
            lesson_id=lesson.assessment.lesson_id,
            mcqs=[PublicMCQ(question_id=q.question_id, prompt=q.prompt, options=q.options) for q in lesson.assessment.mcqs],
            descriptive=PublicDescriptive(question_id=lesson.assessment.descriptive.question_id, prompt=lesson.assessment.descriptive.prompt),
            created_at=lesson.assessment.created_at,
        ).model_dump(mode="json")

    return {
        "lesson_id": lesson.lesson_id,
        "user_id": str(lesson.user_id),
        "topic": lesson.topic,
        "source_id": lesson.source_id,
        "source_version": lesson.source_version,
        "content": lesson.content.model_dump(mode="json"),
        "notes": lesson.notes.model_dump(mode="json") if lesson.notes else None,
        "diagram": lesson.diagram.model_dump(mode="json") if lesson.diagram else None,
        "assessment": public_assessment,
        "submissions": lesson.submissions,
        "video": lesson.video,
        "ask_history": lesson.ask_history,
        "progress": lesson.progress,
        "created_at": lesson.created_at,
        "updated_at": lesson.updated_at,
    }


@router.post("/{lesson_id}/notes", response_model=EducationalNotes)
async def generate_lesson_notes(lesson_id: str, repository: SourceDependency, body: NotesRequest | None = None) -> EducationalNotes:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    try:
        return await run_in_threadpool(service.generate_notes, lesson, (body or NotesRequest()).detail_level)
    except ProviderFailure as error:
        raise HTTPException(503, {"code": error.category}) from None
    except Exception:
        raise generation_error("NOTES_GENERATION_FAILED") from None


@router.post("/{lesson_id}/diagram", response_model=FlowchartDiagram)
async def generate_lesson_diagram(lesson_id: str, repository: SourceDependency) -> FlowchartDiagram:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    try:
        return await run_in_threadpool(service.generate_diagram, lesson)
    except ProviderFailure as error:
        raise HTTPException(503, {"code": error.category}) from None
    except Exception:
        raise generation_error("DIAGRAM_GENERATION_FAILED") from None


@router.post("/{lesson_id}/assessment", response_model=PublicAssessment)
async def generate_lesson_assessment(lesson_id: str, repository: SourceDependency) -> PublicAssessment:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    try:
        assessment: EducationalAssessment = await run_in_threadpool(service.generate_assessment, lesson)
        return PublicAssessment(
            assessment_id=assessment.assessment_id,
            lesson_id=assessment.lesson_id,
            mcqs=[PublicMCQ(question_id=q.question_id, prompt=q.prompt, options=q.options) for q in assessment.mcqs],
            descriptive=PublicDescriptive(question_id=assessment.descriptive.question_id, prompt=assessment.descriptive.prompt),
            created_at=assessment.created_at,
        )
    except ProviderFailure as error:
        raise HTTPException(503, {"code": error.category}) from None
    except Exception:
        raise generation_error("ASSESSMENT_GENERATION_FAILED") from None


@router.post("/{lesson_id}/assessment/submit", response_model=SubmissionResult)
async def submit_lesson_assessment(lesson_id: str, submission: AssessmentSubmission, repository: SourceDependency) -> SubmissionResult:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    try:
        return await run_in_threadpool(service.grade_assessment, lesson, submission)
    except ProviderFailure as error:
        raise HTTPException(503, {"code": error.category}) from None
    except ValidationError:
        raise generation_error("ASSESSMENT_GRADING_FAILED") from None
    except ValueError:
        raise HTTPException(422, {"code": "ASSESSMENT_SUBMISSION_INVALID"}) from None
    except Exception:
        raise generation_error("ASSESSMENT_GRADING_FAILED") from None


@router.post("/{lesson_id}/video")
async def start_lesson_video(lesson_id: str, repository: SourceDependency) -> dict[str, Any]:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    
    # If already completed or running, return status
    if lesson.video and lesson.video.get("status") in ("QUEUED", "PLANNING", "GENERATING_AUDIO", "ALIGNING", "RENDERING", "COMPOSITING", "COMPLETED"):
        return lesson.video
    
    try:
        plan = await run_in_threadpool(service.create_video_plan, lesson.content)
        return service.start_video_job(lesson, plan=plan)
    except ValueError:
        logger.exception("Invalid educational video plan")
        raise HTTPException(422, {"code": "VIDEO_PLAN_INVALID"}) from None
    except Exception:
        raise generation_error("VIDEO_START_FAILED") from None


@router.get("/{lesson_id}/video/status")
async def get_lesson_video_status(lesson_id: str, repository: SourceDependency) -> dict[str, Any]:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    if not lesson.video:
        return {"status": "NOT_STARTED", "progress": 0, "stage": "Not started"}
    return lesson.video


@router.get("/{lesson_id}/video/stream")
async def stream_lesson_video(lesson_id: str, repository: SourceDependency) -> FileResponse:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    if not lesson.video or not lesson.video.get("video_path"):
        raise HTTPException(404, {"code": "VIDEO_NOT_READY"})
    video_path = Path(lesson.video["video_path"])
    try:
        video_path.resolve().relative_to(settings.renders_dir.resolve())
    except ValueError:
        raise HTTPException(404, {"code": "VIDEO_FILE_MISSING"}) from None
    if not video_path.is_file():
        raise HTTPException(404, {"code": "VIDEO_FILE_MISSING"})
    return FileResponse(video_path, media_type="video/mp4", headers={"Accept-Ranges": "bytes", "Cache-Control": "private, no-store"})


@router.post("/{lesson_id}/ask", response_model=AskResponse)
async def ask_lesson_question(lesson_id: str, body: AskRequest, repository: SourceDependency) -> AskResponse:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    try:
        return await run_in_threadpool(service.ask, lesson, body.question)
    except ProviderFailure as error:
        raise HTTPException(503, {"code": error.category}) from None
    except ValueError:
        raise HTTPException(422, {"code": "ASK_INVALID"}) from None
    except Exception:
        raise generation_error("ASK_FAILED") from None

