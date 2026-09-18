"""REST API routes for Step 3 Video Generation Engine.

Endpoints:
- POST /video/generate: Trigger video generation for diagnostic remediation targets.
- GET /video/status/{job_id}: Poll job status and progress percentage.
- GET /video/{video_id}/stream: Stream rendered MP4 video file.
- GET /video/{video_id}/subtitles: Return WebVTT subtitle track.
- GET /video/list/{student_id}: List all rendered remediation videos for a student.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..services.assessment.video_target import load_video_matrix
from ..services.video_gen.pipeline import (
    execute_video_generation_pipeline,
    load_videos_index,
)
from ..services.video_gen.schemas import VideoRenderJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Video Generation Engine"])

# Active in-memory jobs cache
ACTIVE_JOBS: Dict[str, VideoRenderJob] = {}


class GenerateVideoRequest(BaseModel):
    student_id: str = Field(..., description="ID of student needing remediation")
    source_id: str = Field(..., description="Source document ID")
    concept_id: Optional[str] = Field(
        default=None,
        description="Optional concept ID to generate video for. If omitted, generates for the first unmastered target.",
    )
    mock_mode: bool = Field(
        default=False,
        description="If True, synthesizes offline mock audio and deterministic scripts for zero-network testing.",
    )


class GenerateVideoResponse(BaseModel):
    job_id: str
    video_id: str
    concept_id: str
    concept_name: str
    status: str
    message: str


@router.post("/generate", response_model=GenerateVideoResponse)
async def generate_video_endpoint(
    req: GenerateVideoRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger personalized AI video generation for an unmastered concept."""
    # 1. Load VideoTargetMatrix
    matrix = load_video_matrix(req.student_id, req.source_id)
    if not matrix:
        raise HTTPException(
            status_code=404,
            detail=f"No VideoTargetMatrix found for student '{req.student_id}' and source '{req.source_id}'. "
            "Please run and submit an assessment first.",
        )

    if matrix.decision != "GENERATE_VIDEOS" or not matrix.videos:
        raise HTTPException(
            status_code=400,
            detail=f"VideoTargetMatrix decision is '{matrix.decision}'. No videos require remediation.",
        )

    # 2. Select matching target
    target = None
    if req.concept_id:
        # Check human intervention guardrail
        if req.concept_id in matrix.human_intervention_concepts:
            raise HTTPException(
                status_code=400,
                detail=f"Concept '{req.concept_id}' is marked for HUMAN INTERVENTION (>3 failures). "
                "Automated video generation is strictly prohibited by anti-loop guardrails.",
            )

        for v in matrix.videos:
            if v.concept_id == req.concept_id:
                target = v
                break
        if not target:
            raise HTTPException(
                status_code=404,
                detail=f"Concept '{req.concept_id}' is not in the pending video remediation list.",
            )
    else:
        # Pick first available video target
        target = matrix.videos[0]

    job_id = f"JOB_VGEN_{target.concept_id[:8]}_{req.student_id[:6]}"

    # 3. Create placeholder job in cache
    job = VideoRenderJob(
        job_id=job_id,
        video_id=f"VID_{job_id[9:]}",
        student_id=req.student_id,
        source_id=req.source_id,
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        status="pending",
        progress_percent=5,
        current_stage="Queued in background",
    )
    ACTIVE_JOBS[job_id] = job

    # 4. Background task runner
    async def _run_job():
        try:
            completed_job = await execute_video_generation_pipeline(
                target=target,
                student_id=req.student_id,
                source_id=req.source_id,
                job_id=job_id,
                mock_mode=req.mock_mode,
            )
            ACTIVE_JOBS[job_id] = completed_job
        except Exception as err:
            logger.error(f"[video_api] Error processing job {job_id}: {err}")
            if job_id in ACTIVE_JOBS:
                ACTIVE_JOBS[job_id].status = "failed"
                ACTIVE_JOBS[job_id].error_message = str(err)

    background_tasks.add_task(_run_job)

    return GenerateVideoResponse(
        job_id=job.job_id,
        video_id=job.video_id,
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        status="queued",
        message=f"Video rendering started for '{target.concept_name}' ({target.target_seconds}s target duration).",
    )


@router.get("/status/{job_id}", response_model=VideoRenderJob)
async def get_video_status(job_id: str):
    """Check progress and execution status of a video rendering job."""
    # Check in-memory cache first
    if job_id in ACTIVE_JOBS:
        return ACTIVE_JOBS[job_id]

    # Check disk registry
    idx = load_videos_index()
    for vid, meta in idx.items():
        if meta.get("job_id") == job_id:
            return VideoRenderJob(
                job_id=job_id,
                video_id=vid,
                student_id=meta["student_id"],
                source_id=meta["source_id"],
                concept_id=meta["concept_id"],
                concept_name=meta["concept_name"],
                status="completed",
                progress_percent=100,
                current_stage="Ready for playback",
                video_file_path=meta["video_file_path"],
                subtitles_file_path=meta.get("subtitles_file_path"),
                duration_seconds=meta.get("actual_duration_seconds"),
            )

    raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")


@router.get("/{video_id}/stream")
async def stream_video(video_id: str):
    """Stream MP4 video file for HTML5 playback."""
    idx = load_videos_index()
    meta = idx.get(video_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")

    video_path = Path(meta["video_file_path"])
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk.")

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{meta.get('concept_name', 'video')}.mp4",
    )


@router.get("/{video_id}/subtitles")
async def get_video_subtitles(video_id: str):
    """Return WebVTT subtitle track."""
    idx = load_videos_index()
    meta = idx.get(video_id)
    if not meta or not meta.get("subtitles_file_path"):
        raise HTTPException(status_code=404, detail=f"Subtitles for '{video_id}' not found.")

    sub_path = Path(meta["subtitles_file_path"])
    if not sub_path.exists():
        raise HTTPException(status_code=404, detail="Subtitle file not found on disk.")

    return FileResponse(
        path=str(sub_path),
        media_type="text/vtt",
        filename="subtitles.vtt",
    )


@router.get("/list/{student_id}")
async def list_student_videos(student_id: str):
    """List all completed remediation videos available for a student."""
    idx = load_videos_index()
    results = [meta for meta in idx.values() if meta.get("student_id") == student_id]
    return {"student_id": student_id, "videos": results}
