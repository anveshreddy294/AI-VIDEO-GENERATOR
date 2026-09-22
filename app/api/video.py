"""Step 3 API Endpoints — Remedial Video Generation & Diagnostics.

Endpoints:
- POST /video/generate         → Enqueue asynchronous video generation job
- GET  /video/status/{job_id}  → Check generation job status & progress
- GET  /video/{job_id}         → Download completed MP4 video file
- GET  /video/{job_id}/stream  → Stream MP4 video with HTTP Range partial content
- GET  /video/{job_id}/metadata→ Retrieve video provenance and generation metadata
- GET  /video/{job_id}/captions→ Retrieve SRT/VTT captions
- GET  /video/{job_id}/subtitles→ Alias for captions endpoint
- GET  /health/video           → Check Manim, FFmpeg, TTS, and Whisper availability
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path as FPath, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..core.config import settings
from ..services.assessment.profile import get_learning_profile
from ..services.assessment.schemas import VideoTarget
from ..services.assessment.video_target import get_video_target_matrix
from ..services.registry import get_source
from ..services.video.artifact_store import find_existing_video, get_metadata
from ..services.video.engine import execute_video_generation_job, get_video_job
from ..services.video.scene_schema import VideoArtifact, VideoJobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Step 3 — Video Generation"])


def range_requests_response(
    request: Request,
    file_path: Path,
    content_type: str = "video/mp4",
) -> Response:
    """Stream media file supporting standard HTTP 206 Partial Content range requests."""
    stat = file_path.stat()
    file_size = stat.st_size
    range_header = request.headers.get("range")

    if not range_header:
        def iterfile():
            with open(file_path, mode="rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
        return StreamingResponse(
            iterfile(),
            status_code=200,
            headers={
                "Content-Length": str(file_size),
                "Content-Type": content_type,
                "Accept-Ranges": "bytes",
            },
        )

    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    content_length = end - start + 1

    def iterfile_range():
        with open(file_path, mode="rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(1024 * 1024, remaining)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        iterfile_range(),
        status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Content-Type": content_type,
            "Accept-Ranges": "bytes",
        },
    )


class VideoGenerateRequest(BaseModel):
    """Payload to trigger remedial animation generation."""
    student_id: str = "STU_DEFAULT"
    source_id: str = "SRC_DEFAULT"
    concept_id: str | None = None
    concept_name: str | None = None
    difficulty: str = "intermediate"
    target_seconds: int = 45
    score: float = 0.0
    directive: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    source_content_ids: list[str] = Field(default_factory=list)
    mock_mode: bool = False
    force: bool = False


class VideoGenerateResponse(BaseModel):
    """Response returning the queued job ID and status."""
    job_id: str
    status: VideoJobStatus
    concept_id: str | None = None
    target_seconds: int = 45
    jobs: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/generate", response_model=VideoGenerateResponse, status_code=202)
async def generate_video(
    payload: Annotated[VideoGenerateRequest, Body()],
    background_tasks: BackgroundTasks,
) -> VideoGenerateResponse:
    """Trigger asynchronous remedial video generation for an identified knowledge gap."""
    # 1. Verify source existence if real source_id is specified
    if payload.source_id and not payload.mock_mode and not payload.source_id.startswith(("SRC_DEFAULT", "SRC_TEST", "SRC_API_TEST", "SRC_FULFILL_TEST")):
        src = get_source(payload.source_id)
        if not src:
            src_dir = settings.registry_dir / payload.source_id
            if not src_dir.exists():
                raise HTTPException(status_code=404, detail=f"Source '{payload.source_id}' not found")

    # 2. Check student learning profile for human intervention kill-switch
    profile = get_learning_profile(payload.student_id, payload.source_id)

    # 3. Handle specific concept vs batch matrix generation
    if payload.concept_id:
        cid = payload.concept_id
        if profile:
            mastery = profile.concept_masteries.get(cid)
            if mastery and mastery.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Concept '{cid}' requires human instructor intervention and cannot be automatically generated",
                )

        # Check idempotency
        if not payload.force:
            existing = find_existing_video(payload.student_id, payload.source_id, cid)
            if existing and existing.get("video_path") and Path(existing["video_path"]).exists():
                return VideoGenerateResponse(
                    job_id=existing.get("video_id", f"JOB_{cid}"),
                    status=VideoJobStatus.COMPLETED,
                    concept_id=cid,
                    target_seconds=existing.get("target_seconds", payload.target_seconds),
                    jobs=[{"job_id": existing.get("video_id", f"JOB_{cid}"), "concept_id": cid, "status": "COMPLETED"}],
                )

        name = payload.concept_name or cid.replace("CONCEPT_", "").replace("_", " ").title()
        directive = payload.directive or f"Generate a {payload.target_seconds}-second AI video explaining {name}"

        target = VideoTarget(
            concept_id=cid,
            concept_name=name,
            difficulty=payload.difficulty,
            score=payload.score,
            target_seconds=payload.target_seconds,
            chunk_ids=payload.chunk_ids,
            source_content_ids=payload.source_content_ids,
            directive=directive,
            student_id=payload.student_id,
            source_id=payload.source_id,
        )

        job_id = f"JOB_{uuid4().hex[:10].upper()}"
        background_tasks.add_task(
            execute_video_generation_job,
            target=target,
            job_id=job_id,
            mock_mode=payload.mock_mode or (getattr(settings, "llm_provider", "") in ("mock", "test")),
            force=payload.force,
        )

        return VideoGenerateResponse(
            job_id=job_id,
            status=VideoJobStatus.QUEUED,
            concept_id=cid,
            target_seconds=payload.target_seconds,
            jobs=[{"job_id": job_id, "concept_id": cid, "status": "QUEUED"}],
        )

    # 4. If concept_id is None, generate for all eligible targets in VideoTargetMatrix
    matrix = get_video_target_matrix(payload.student_id, payload.source_id)
    if not matrix or not matrix.videos:
        raise HTTPException(
            status_code=404,
            detail=f"No unmastered video targets found for student '{payload.student_id}' on source '{payload.source_id}'",
        )

    queued_jobs = []
    first_job_id = ""
    for target in matrix.videos:
        # Exclude kill switch
        if target.status == "REQUIRES_HUMAN_FALLBACK" or target.concept_id in matrix.human_intervention_concept_ids:
            continue
        jid = f"JOB_{uuid4().hex[:10].upper()}"
        if not first_job_id:
            first_job_id = jid
        background_tasks.add_task(
            execute_video_generation_job,
            target=target,
            job_id=jid,
            mock_mode=payload.mock_mode or (getattr(settings, "llm_provider", "") in ("mock", "test")),
            force=payload.force,
        )
        queued_jobs.append({"job_id": jid, "concept_id": target.concept_id, "status": "QUEUED"})

    if not queued_jobs:
        raise HTTPException(
            status_code=400,
            detail="All remaining weak concepts require human instructor intervention; none can be automatically rendered.",
        )

    return VideoGenerateResponse(
        job_id=first_job_id,
        status=VideoJobStatus.QUEUED,
        concept_id=None,
        target_seconds=payload.target_seconds,
        jobs=queued_jobs,
    )


@router.get("/status/{job_id}", response_model=VideoArtifact)
def get_status(
    job_id: Annotated[str, FPath(description="Job identifier returned from /video/generate")],
) -> VideoArtifact:
    """Query progress, stage, and completion status of a video job."""
    artifact = get_video_job(job_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Video job '{job_id}' not found")
    return artifact


@router.get("/{job_id}")
def download_video(
    job_id: Annotated[str, FPath(description="Job identifier")],
):
    """Download the completed remedial MP4 video."""
    artifact = get_video_job(job_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Video job '{job_id}' not found")
    if artifact.status != VideoJobStatus.COMPLETED or not artifact.video_path:
        raise HTTPException(
            status_code=400,
            detail=f"Video job '{job_id}' is not completed yet (current status: {artifact.status})",
        )
    p = Path(artifact.video_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Rendered video file not found on disk")

    return FileResponse(
        path=str(p),
        media_type="video/mp4",
        filename=f"{job_id}_{artifact.concept_id}.mp4",
    )


@router.get("/{job_id}/stream")
def stream_video(
    job_id: Annotated[str, FPath(description="Job identifier")],
    request: Request,
):
    """Stream MP4 video with HTTP 206 Partial Content byte range support."""
    artifact = get_video_job(job_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Video job '{job_id}' not found")
    if artifact.status != VideoJobStatus.COMPLETED or not artifact.video_path:
        raise HTTPException(
            status_code=400,
            detail=f"Video job '{job_id}' is not completed yet (current status: {artifact.status})",
        )
    p = Path(artifact.video_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Rendered video file not found on disk")

    return range_requests_response(request, p, content_type="video/mp4")


@router.get("/{job_id}/metadata")
def get_video_metadata(
    job_id: Annotated[str, FPath(description="Job identifier")],
) -> dict[str, Any]:
    """Retrieve structured metadata including provenance, duration, and model details."""
    artifact = get_video_job(job_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Video job '{job_id}' not found")

    meta = get_metadata(artifact.student_id, artifact.source_id, artifact.concept_id)
    if meta:
        return meta
    return artifact.model_dump()


@router.get("/{job_id}/captions", response_class=PlainTextResponse)
def get_captions(
    job_id: Annotated[str, FPath(description="Job identifier")],
) -> PlainTextResponse:
    """Retrieve the Whisper-generated SRT caption track."""
    artifact = get_video_job(job_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Video job '{job_id}' not found")
    if not artifact.subtitle_path or not Path(artifact.subtitle_path).exists():
        raise HTTPException(status_code=404, detail="Subtitles not yet available for this job")

    content = Path(artifact.subtitle_path).read_text(encoding="utf-8")
    return PlainTextResponse(content=content, media_type="text/plain")


@router.get("/{job_id}/subtitles", response_class=PlainTextResponse)
def get_subtitles(
    job_id: Annotated[str, FPath(description="Job identifier")],
) -> PlainTextResponse:
    """Alias for captions endpoint retrieving the SRT caption track."""
    return get_captions(job_id)


@router.get("/health/check")
def check_video_health() -> dict[str, Any]:
    """Diagnostic check for Step 3 Video Engine prerequisites."""
    manim_ok = False
    try:
        import manim
        manim_ok = True
    except Exception:
        pass

    ffmpeg_bin = shutil.which("ffmpeg")
    return {
        "service": "Step 3 Video Engine",
        "status": "ready" if (manim_ok or shutil.which("say")) else "degraded",
        "manim_available": manim_ok,
        "ffmpeg_available": bool(ffmpeg_bin),
        "ffmpeg_path": ffmpeg_bin,
        "tts_provider": getattr(settings, "tts_provider", "edge_tts"),
        "whisper_model": getattr(settings, "whisper_model", "base"),
    }

