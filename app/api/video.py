"""Step 3 API Endpoints — Remedial Video Generation & Diagnostics.

Endpoints:
- POST /video/generate         → Enqueue asynchronous video generation job
- GET  /video/status/{job_id}  → Check generation job status & progress
- GET  /video/{job_id}         → Stream completed MP4 video file
- GET  /video/{job_id}/captions→ Retrieve SRT/VTT captions
- GET  /health/video           → Check Manim, FFmpeg, TTS, and Whisper availability
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path as FPath, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ..core.config import settings
from ..services.assessment.schemas import VideoTarget
from ..services.video.engine import execute_video_generation_job, get_video_job
from ..services.video.scene_schema import VideoArtifact, VideoJobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Step 3 — Video Generation"])


class VideoGenerateRequest(BaseModel):
    """Payload to trigger remedial animation generation."""
    student_id: str = "STU_DEFAULT"
    source_id: str = "SRC_DEFAULT"
    concept_id: str
    concept_name: str | None = None
    difficulty: str = "intermediate"
    target_seconds: int = 45
    score: float = 0.0
    directive: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    source_content_ids: list[str] = Field(default_factory=list)
    mock_mode: bool = False


class VideoGenerateResponse(BaseModel):
    """Response returning the queued job ID."""
    job_id: str
    status: VideoJobStatus
    concept_id: str
    target_seconds: int


@router.post("/generate", response_model=VideoGenerateResponse, status_code=202)
async def generate_video(
    payload: Annotated[VideoGenerateRequest, Body()],
    background_tasks: BackgroundTasks,
) -> VideoGenerateResponse:
    """Trigger asynchronous remedial video generation for an identified knowledge gap."""
    name = payload.concept_name or payload.concept_id.replace("CONCEPT_", "").replace("_", " ").title()
    directive = payload.directive or f"Generate a {payload.target_seconds}-second AI video explaining {name}"

    target = VideoTarget(
        concept_id=payload.concept_id,
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

    from uuid import uuid4
    job_id = f"JOB_{uuid4().hex[:10].upper()}"

    # Enqueue background task
    background_tasks.add_task(
        execute_video_generation_job,
        target=target,
        job_id=job_id,
        mock_mode=payload.mock_mode or (getattr(settings, "llm_provider", "") in ("mock", "test")),
    )

    return VideoGenerateResponse(
        job_id=job_id,
        status=VideoJobStatus.QUEUED,
        concept_id=payload.concept_id,
        target_seconds=payload.target_seconds,
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
    """Stream or download the completed remedial MP4 video."""
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
