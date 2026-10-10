"""Authenticated hierarchy-independent learning entry point; no fake source/session rows."""
import logging
from pathlib import Path
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
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
    public_lesson_video,
    VideoCapacityError,
)
from ..services.video.educational_video import (
    VideoOptions, VideoMetadata, VideoSceneView, VideoScenesPage, VideoEvidenceView,
    SceneIndexResult, SceneSearchPage, SourceScenesPage,
    build_video_plan, generation_for, video_metadata, reconcile_scene_index, search_scenes,
)

router = APIRouter(prefix="/educational-content", tags=["Educational content"])


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=4000)


class NotesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    detail_level: Literal["concise", "standard", "detailed"] = "standard"
    regenerate: bool = False


class ResourceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    regenerate: bool = False


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
        "video": public_lesson_video(lesson.video),
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
        options = body or NotesRequest()
        return await run_in_threadpool(service.generate_notes, lesson, options.detail_level, options.regenerate)
    except ProviderFailure as error:
        raise HTTPException(503, {"code": error.category}) from None
    except Exception:
        raise generation_error("NOTES_GENERATION_FAILED") from None


@router.post("/{lesson_id}/diagram", response_model=FlowchartDiagram)
async def generate_lesson_diagram(lesson_id: str, repository: SourceDependency, body: ResourceRequest | None = None) -> FlowchartDiagram:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    try:
        return await run_in_threadpool(service.generate_diagram, lesson, (body or ResourceRequest()).regenerate)
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
async def start_lesson_video(lesson_id: str, repository: SourceDependency, body: VideoOptions | None = None) -> dict[str, Any]:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    
    # If already completed or running, return status
    options = body or VideoOptions()
    if options.regenerate and lesson.video and lesson.video.get("status") not in {"COMPLETED", "FAILED", "NOT_STARTED"}:
        raise HTTPException(409, {"code":"VIDEO_GENERATION_IN_PROGRESS"})
    if not options.regenerate and lesson.video and lesson.video.get("status") in ("QUEUED", "PLANNING", "GENERATING_AUDIO", "ALIGNING", "RENDERING", "COMPOSITING", "COMPLETED"):
        return public_lesson_video(lesson.video)
    
    try:
        plan = await run_in_threadpool(build_video_plan, service, lesson.content, options)
        return public_lesson_video(service.start_video_job(lesson, plan=plan, regenerate=options.regenerate))
    except HTTPException:
        raise
    except VideoCapacityError:
        raise HTTPException(429, {"code":"VIDEO_CAPACITY_REACHED"}, headers={"Retry-After":"30"}) from None
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
    return public_lesson_video(lesson.video)


@router.get("/{lesson_id}/video/stream")
async def stream_lesson_video(lesson_id: str, repository: SourceDependency, generation_id: str | None = Query(default=None, max_length=128)) -> FileResponse:
    repo = require_source_repository(repository)
    service = EducationalContentService(repo)
    lesson = await run_in_threadpool(service.get_lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, {"code": "LESSON_NOT_FOUND"})
    if generation_id is not None:
        lesson, generation = await run_in_threadpool(generation_for, repo, lesson_id, generation_id)
        artifact = generation.artifact
        selected = {"status":generation.status,"video_path":artifact.video_path if artifact else None}
    else:
        selected = lesson.video
        if not selected or selected.get("status") != "COMPLETED":
            completed = [g for g in lesson.video_generations.values() if g.status == "COMPLETED" and g.artifact and g.artifact.video_path]
            if completed:
                selected = {"status":"COMPLETED","job_id":completed[-1].job_id,"video_path":completed[-1].artifact.video_path}
        # Default and explicit playback enforce the same evidence permissions.
        if selected and selected.get("job_id") in lesson.video_generations:
            await run_in_threadpool(generation_for, repo, lesson_id, selected["job_id"])
    if not selected or selected.get("status") != "COMPLETED" or not selected.get("video_path"):
        raise HTTPException(404, {"code": "VIDEO_NOT_READY"})
    video_path = Path(selected["video_path"])
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


def _private_json(value: dict, schema: type[BaseModel]) -> JSONResponse:
    return JSONResponse(schema.model_validate(value).model_dump(mode="json"), headers={"Cache-Control":"private, no-store"})


@router.get("/{lesson_id}/video/metadata", response_model=VideoMetadata)
async def read_video_metadata(lesson_id: str, repository: SourceDependency,
                              generation_id: str | None = Query(default=None, max_length=128)) -> JSONResponse:
    repo = require_source_repository(repository)
    return _private_json(await run_in_threadpool(video_metadata, repo, lesson_id, generation_id), VideoMetadata)


@router.get("/{lesson_id}/video/scenes", response_model=VideoScenesPage)
async def read_video_scenes(lesson_id: str, repository: SourceDependency,
                            generation_id: str | None = Query(default=None, max_length=128),
                            offset: int = Query(default=0, ge=0, le=1000),
                            limit: int = Query(default=20, ge=1, le=50)) -> JSONResponse:
    repo = require_source_repository(repository)
    metadata = await run_in_threadpool(video_metadata, repo, lesson_id, generation_id)
    scenes = metadata["scenes"]
    return _private_json({"generation_id":metadata["generation_id"],"scenes":scenes[offset:offset+limit],
        "timing_status":metadata["timing_status"],"next_offset":offset+limit if len(scenes)>offset+limit else None}, VideoScenesPage)


@router.get("/{lesson_id}/video/scenes/{scene_id}", response_model=VideoSceneView)
async def read_video_scene(lesson_id: str, scene_id: str, repository: SourceDependency,
                           generation_id: str | None = Query(default=None, max_length=128)) -> JSONResponse:
    metadata = await run_in_threadpool(video_metadata, require_source_repository(repository), lesson_id, generation_id)
    scene = next((s for s in metadata["scenes"] if s["scene_id"] == scene_id),None)
    if scene is None:
        raise HTTPException(404, {"code":"VIDEO_SCENE_NOT_FOUND"})
    return _private_json(scene, VideoSceneView)


@router.get("/{lesson_id}/video/at", response_model=VideoSceneView)
async def resolve_video_timestamp(lesson_id: str, repository: SourceDependency,
                                   seconds: float = Query(ge=0, allow_inf_nan=False),
                                   generation_id: str | None = Query(default=None, max_length=128)) -> JSONResponse:
    metadata = await run_in_threadpool(video_metadata, require_source_repository(repository), lesson_id, generation_id)
    if metadata["timing_status"] != "MEASURED":
        raise HTTPException(409, {"code":"VIDEO_TIMING_UNAVAILABLE"})
    scene = next((s for s in metadata["scenes"] if s["timing"] and
                  s["timing"]["start_seconds"] <= seconds < s["timing"]["end_seconds"]),None)
    if scene is None:
        raise HTTPException(404, {"code":"VIDEO_TIMESTAMP_OUT_OF_RANGE"})
    return _private_json(scene, VideoSceneView)


@router.get("/{lesson_id}/video/evidence", response_model=VideoEvidenceView)
async def read_video_evidence(lesson_id: str, repository: SourceDependency,
                              scene_id: str | None = Query(default=None, max_length=128),
                              generation_id: str | None = Query(default=None, max_length=128)) -> JSONResponse:
    metadata = await run_in_threadpool(video_metadata, require_source_repository(repository), lesson_id, generation_id)
    scenes = [s for s in metadata["scenes"] if scene_id is None or s["scene_id"] == scene_id]
    if not scenes:
        raise HTTPException(404, {"code":"VIDEO_SCENE_NOT_FOUND"})
    return _private_json({"generation_id":metadata["generation_id"],"traceability_status":metadata["traceability_status"],
        "scenes":[{"scene_id":s["scene_id"],"timing":s["timing"],"evidence_references":s["evidence_references"]} for s in scenes]}, VideoEvidenceView)


@router.get("/{lesson_id}/video/captions")
async def read_video_captions(lesson_id: str, repository: SourceDependency,
                              generation_id: str | None = Query(default=None, max_length=128)) -> FileResponse:
    _, generation = await run_in_threadpool(generation_for, require_source_repository(repository), lesson_id, generation_id)
    if generation.status != "COMPLETED" or not generation.artifact or not generation.artifact.subtitle_path:
        raise HTTPException(404, {"code":"VIDEO_CAPTIONS_UNAVAILABLE"})
    path = Path(generation.artifact.subtitle_path).resolve()
    if not path.is_relative_to(settings.captions_dir.resolve()) or path.suffix != ".vtt" or not path.is_file():
        raise HTTPException(404, {"code":"VIDEO_CAPTIONS_UNAVAILABLE"})
    if generation.artifact.caption_quality == "SCENE_TIMED" and generation.artifact.timing_status == "MEASURED":
        from ..services.video.caption_validation import validate_scene_captions, CaptionValidationError
        try:
            await run_in_threadpool(validate_scene_captions, path, generation.plan,
                                    generation.artifact.scene_timeline, generation.artifact.duration_seconds)
        except CaptionValidationError:
            raise HTTPException(409, {"code":"VIDEO_CAPTIONS_INVALID"}) from None
    return FileResponse(path, media_type="text/vtt", headers={"Cache-Control":"private, no-store"})


@router.post("/{lesson_id}/video/reindex", response_model=SceneIndexResult)
async def retry_video_index(lesson_id: str, repository: SourceDependency,
                            generation_id: str = Query(min_length=1,max_length=128)) -> JSONResponse:
    return _private_json(await run_in_threadpool(reconcile_scene_index, require_source_repository(repository), lesson_id, generation_id), SceneIndexResult)


@router.get("/video-scenes/search", response_model=SceneSearchPage)
async def search_video_scenes(repository: SourceDependency, query: str = Query(min_length=1,max_length=1000),
                              offset: int = Query(default=0,ge=0,le=150), limit: int = Query(default=20,ge=1,le=50)) -> JSONResponse:
    return _private_json(await run_in_threadpool(search_scenes, require_source_repository(repository), query, offset, limit), SceneSearchPage)


@router.get("/video-sources/{source_id}/scenes", response_model=SourceScenesPage)
async def source_video_scenes(source_id: str, repository: SourceDependency,
                              source_version: int = Query(ge=1), chunk_id: str | None = Query(default=None,max_length=128),
                              content_id: str | None = Query(default=None,max_length=128),
                              offset: int = Query(default=0,ge=0,le=10000), limit: int = Query(default=20,ge=1,le=50)) -> JSONResponse:
    from ..services.video.educational_video import scenes_for_source
    return _private_json(await run_in_threadpool(scenes_for_source, require_source_repository(repository),
        source_id, source_version, chunk_id, content_id, offset, limit), SourceScenesPage)

