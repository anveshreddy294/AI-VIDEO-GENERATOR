"""Step 3 Video Engine Orchestrator.

Coordinates the complete remedial video generation pipeline:
VideoTargetMatrix -> Ollama Planner -> Manim Renderer -> TTS Narration -> Whisper Alignment -> FFmpeg Compositor.
Provides background task execution and job state persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...core.config import settings
from ..assessment.schemas import VideoTarget, VideoTargetMatrix
from .manim_renderer import render_video_plan
from .narration import extract_narration_script
from .scene_schema import VideoArtifact, VideoJobStatus, VideoPlan
from .tts import get_tts_provider
from .video_compositor import composite_remedial_video
from .video_planner import plan_video_for_target
from .whisper_alignment import get_whisper_aligner

logger = logging.getLogger(__name__)

# Global in-memory job registry for instant status tracking
_ACTIVE_JOBS: dict[str, VideoArtifact] = {}


def get_video_job(job_id: str) -> VideoArtifact | None:
    """Retrieve video job artifact by ID."""
    if job_id in _ACTIVE_JOBS:
        return _ACTIVE_JOBS[job_id]

    # Check disk
    job_file = settings.renders_dir / f"{job_id}_artifact.json"
    if job_file.exists():
        data = json.loads(job_file.read_text(encoding="utf-8"))
        artifact = VideoArtifact.model_validate(data)
        _ACTIVE_JOBS[job_id] = artifact
        return artifact

    return None


def _save_video_artifact(artifact: VideoArtifact) -> Path:
    """Persist video artifact record."""
    settings.renders_dir.mkdir(parents=True, exist_ok=True)
    job_file = settings.renders_dir / f"{artifact.job_id}_artifact.json"
    job_file.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    _ACTIVE_JOBS[artifact.job_id] = artifact
    return job_file


async def execute_video_generation_job(
    target: VideoTarget,
    job_id: str | None = None,
    mock_mode: bool = False,
) -> VideoArtifact:
    """Execute complete end-to-end Step 3 generation pipeline asynchronously."""
    jid = job_id or f"JOB_{uuid4().hex[:10].upper()}"

    artifact = VideoArtifact(
        job_id=jid,
        student_id=target.student_id or "STU_DEFAULT",
        source_id=target.source_id or "SRC_DEFAULT",
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        duration_seconds=float(target.target_seconds),
        status=VideoJobStatus.QUEUED,
        stage="QUEUED",
        progress=5,
        provenance_chunks=target.chunk_ids,
        source_content_ids=target.source_content_ids,
    )
    _save_video_artifact(artifact)

    try:
        # 1. Video Planning (LLM reasoning)
        artifact.status = VideoJobStatus.PLANNING
        artifact.stage = "Generating Video Plan"
        artifact.progress = 20
        _save_video_artifact(artifact)

        plan: VideoPlan = await asyncio.to_thread(
            plan_video_for_target,
            target=target,
            student_id=target.student_id,
            source_id=target.source_id,
        )

        # 2. Narration & Audio Synthesis (TTS)
        artifact.status = VideoJobStatus.GENERATING_AUDIO
        artifact.stage = "Synthesizing Narration Audio"
        artifact.progress = 40
        _save_video_artifact(artifact)

        script = extract_narration_script(plan)
        audio_path = settings.audio_dir / f"{jid}.wav"
        tts = get_tts_provider("mock" if mock_mode else None)
        await tts.generate_audio(
            text=script.full_text,
            output_path=audio_path,
            target_seconds=float(plan.duration_seconds),
        )
        artifact.audio_path = str(audio_path)

        # 3. Whisper Alignment & Subtitle Generation
        artifact.status = VideoJobStatus.ALIGNING
        artifact.stage = "Aligning Subtitles via Whisper"
        artifact.progress = 60
        _save_video_artifact(artifact)

        srt_path = settings.captions_dir / f"{jid}.srt"
        aligner = get_whisper_aligner(mock=mock_mode)
        align_meta = await asyncio.to_thread(
            aligner.align_and_transcribe,
            audio_path=audio_path,
            expected_narration=script.full_text,
            output_srt=srt_path,
        )
        artifact.subtitle_path = str(srt_path)

        # 4. Deterministic Manim Scene Rendering
        artifact.status = VideoJobStatus.RENDERING
        artifact.stage = "Rendering Animation Scenes"
        artifact.progress = 75
        _save_video_artifact(artifact)

        raw_video_path = settings.renders_dir / f"{jid}_visual.mp4"
        await asyncio.to_thread(render_video_plan, plan, raw_video_path)

        # 5. Final Audio/Video Composition
        artifact.status = VideoJobStatus.COMPOSITING
        artifact.stage = "Compositing Final MP4"
        artifact.progress = 90
        _save_video_artifact(artifact)

        final_mp4_path = settings.renders_dir / f"{jid}.mp4"
        await composite_remedial_video(
            video_mp4=raw_video_path,
            audio_wav=audio_path,
            output_mp4=final_mp4_path,
            subtitles_srt=srt_path,
        )

        artifact.video_path = str(final_mp4_path)
        artifact.status = VideoJobStatus.COMPLETED
        artifact.stage = "COMPLETED"
        artifact.progress = 100
        artifact.completed_at = datetime.now(timezone.utc).isoformat()
        _save_video_artifact(artifact)
        return artifact

    except Exception as exc:
        logger.error(f"[video_engine] Job {jid} failed: {exc}", exc_info=True)
        artifact.status = VideoJobStatus.FAILED
        artifact.stage = "FAILED"
        artifact.error = str(exc)
        _save_video_artifact(artifact)
        return artifact
