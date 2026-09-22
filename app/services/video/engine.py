"""Step 3 Video Engine Orchestrator.

Coordinates the complete remedial video generation pipeline:
VideoTargetMatrix -> Ollama Planner -> Manim Renderer -> TTS Narration -> Whisper Alignment -> FFmpeg Compositor.
Provides background task execution and job state persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...core.config import settings
from ..assessment.schemas import VideoTarget, VideoTargetMatrix
from ..pipeline_tracker import job_manager
from ..schemas import LayerBVideoSceneChunk
from .artifact_store import find_existing_video, store_video_artifacts
from .manim_renderer import render_video_plan
from .narration import extract_narration_script
from .scene_schema import VideoArtifact, VideoJobStatus, VideoPlan
from .scene_validator import validate_video_plan
from .tts import get_tts_provider
from .video_compositor import composite_remedial_video, probe_media, validate_video_artifact
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
    force: bool = False,
    mock_tts: bool | None = None,
) -> VideoArtifact:
    """Execute complete end-to-end Step 3 generation pipeline asynchronously."""
    jid = job_id or f"JOB_{uuid4().hex[:10].upper()}"
    student_id = target.student_id or "STU_DEFAULT"
    source_id = target.source_id or "SRC_DEFAULT"
    log_prefix = f"[video][job={jid}][source={source_id}][concept={target.concept_id}]"

    # Idempotency check: reuse existing completed video if force is False
    if not force:
        existing = find_existing_video(student_id, source_id, target.concept_id)
        if existing and existing.get("video_path") and Path(existing["video_path"]).exists():
            logger.info("%s Reusing existing completed video artifact from %s", log_prefix, existing["video_path"])
            artifact = VideoArtifact(
                job_id=jid,
                student_id=student_id,
                source_id=source_id,
                concept_id=target.concept_id,
                concept_name=target.concept_name,
                duration_seconds=float(existing.get("actual_seconds", target.target_seconds)),
                status=VideoJobStatus.COMPLETED,
                stage="COMPLETED (REUSED)",
                progress=100,
                video_path=existing.get("video_path"),
                subtitle_path=existing.get("subtitle_path"),
                provenance_chunks=target.chunk_ids,
                source_content_ids=target.source_content_ids,
                page_start=target.page_start,
                page_end=target.page_end,
                completed_at=existing.get("generated_at", datetime.now(timezone.utc).isoformat()),
            )
            _save_video_artifact(artifact)
            return artifact

    artifact = VideoArtifact(
        job_id=jid,
        student_id=student_id,
        source_id=source_id,
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        duration_seconds=float(target.target_seconds),
        status=VideoJobStatus.QUEUED,
        stage="QUEUED",
        progress=5,
        provenance_chunks=target.chunk_ids,
        source_content_ids=target.source_content_ids,
        page_start=target.page_start,
        page_end=target.page_end,
    )
    _save_video_artifact(artifact)

    sem = job_manager.get_semaphore()
    acquired_sem = False
    await sem.acquire()
    acquired_sem = True

    try:
        # 1. Video Planning (LLM reasoning)
        artifact.status = VideoJobStatus.PLANNING
        artifact.stage = "Generating Video Plan"
        artifact.progress = 20
        _save_video_artifact(artifact)
        logger.info("%s Generating structured VideoPlan...", log_prefix)

        plan: VideoPlan = await asyncio.to_thread(
            plan_video_for_target,
            target=target,
            student_id=student_id,
            source_id=source_id,
        )

        # Validate VideoPlan
        validate_video_plan(plan)

        # 2. Narration & Audio Synthesis (TTS)
        artifact.status = VideoJobStatus.GENERATING_AUDIO
        artifact.stage = "Synthesizing Narration Audio"
        artifact.progress = 40
        _save_video_artifact(artifact)
        logger.info("%s Synthesizing voiceover audio...", log_prefix)

        script = extract_narration_script(plan)
        audio_path = settings.audio_dir / f"{jid}.wav"

        # Determine TTS provider: use mock only if explicitly requested or running under automated pytest fixture
        if mock_tts is True:
            tts = get_tts_provider("mock")
        elif mock_tts is False:
            tts = get_tts_provider()
        elif getattr(settings, "tts_provider", "") in ("mock", "test") or os.environ.get("PYTEST_CURRENT_TEST"):
            tts = get_tts_provider("mock")
        else:
            tts = get_tts_provider()

        await tts.generate_audio(
            text=script.full_text,
            output_path=audio_path,
            target_seconds=float(plan.duration_seconds),
        )
        artifact.audio_path = str(audio_path)

        # Validate narration audio exists and has valid audio stream
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError(f"Narration audio file is missing or 0 bytes: {audio_path}")
        audio_probe = probe_media(audio_path)
        a_streams = [s for s in audio_probe.get("streams", []) if s.get("codec_type") == "audio"]
        if not a_streams:
            raise RuntimeError(f"Narration audio {audio_path} contains no valid audio stream")
        a_dur = float(audio_probe.get("format", {}).get("duration", 0) or 0)
        if a_dur <= 0:
            raise RuntimeError(f"Narration audio {audio_path} has invalid duration ({a_dur}s)")

        # Inspect generated audio duration and sync visual scenes if audio took slightly longer
        try:
            actual_audio_dur = a_dur
            if actual_audio_dur > float(plan.duration_seconds):
                logger.info(
                    "%s Audio duration (%.2fs) exceeds planned visual duration (%ds); scaling visual scenes...",
                    log_prefix, actual_audio_dur, plan.duration_seconds
                )
                ratio = actual_audio_dur / float(plan.duration_seconds)
                for s in plan.scenes:
                    s.duration_seconds = round(s.duration_seconds * ratio, 2)
                plan.duration_seconds = int(actual_audio_dur)
        except Exception as exc:
            logger.debug("%s Could not scale visual scenes to audio duration: %s", log_prefix, exc)

        # 3. Whisper Alignment & Subtitle Generation
        artifact.status = VideoJobStatus.ALIGNING
        artifact.stage = "Aligning Subtitles via Whisper"
        artifact.progress = 60
        _save_video_artifact(artifact)
        logger.info("%s Generating Whisper word-level alignment & subtitles...", log_prefix)

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
        logger.info("%s Rendering Manim animation scenes...", log_prefix)

        raw_video_path = settings.renders_dir / f"{jid}_visual.mp4"
        await asyncio.to_thread(render_video_plan, plan, raw_video_path)

        # Validate rendered visual stream exists and has valid duration
        if not raw_video_path.exists() or raw_video_path.stat().st_size == 0:
            raise RuntimeError(f"Rendered visual video file missing or 0 bytes: {raw_video_path}")
        raw_probe = probe_media(raw_video_path)
        v_streams = [s for s in raw_probe.get("streams", []) if s.get("codec_type") == "video"]
        if not v_streams:
            raise RuntimeError(f"Rendered visual video {raw_video_path} contains no video stream")
        v_dur = float(raw_probe.get("format", {}).get("duration", 0) or 0)
        if v_dur <= 0:
            raise RuntimeError(f"Rendered visual video {raw_video_path} has invalid duration ({v_dur}s)")

        # 5. Final Audio/Video Composition
        artifact.status = VideoJobStatus.COMPOSITING
        artifact.stage = "Compositing Final MP4"
        artifact.progress = 90
        _save_video_artifact(artifact)
        logger.info("%s Multiplexing audio and visual tracks via FFmpeg...", log_prefix)

        final_mp4_path = settings.renders_dir / f"{jid}.mp4"
        await composite_remedial_video(
            video_mp4=raw_video_path,
            audio_wav=audio_path,
            output_mp4=final_mp4_path,
            subtitles_srt=srt_path,
        )

        # Strictly validate final composited artifact integrity
        final_validation = validate_video_artifact(final_mp4_path, expect_audio=True)
        logger.info(
            "%s Final artifact validated: size=%d bytes, duration=%.2fs, v_codec=%s, a_codec=%s",
            log_prefix,
            final_validation["size"],
            final_validation["duration"],
            final_validation["video_codec"],
            final_validation["audio_codec"],
        )

        # 6. Store in canonical structured video artifact store
        store_video_artifacts(
            video_id=jid,
            student_id=student_id,
            source_id=source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            plan=plan,
            final_mp4=final_mp4_path,
            audio_path=audio_path,
            srt_path=srt_path,
            alignment_data=align_meta,
            actual_seconds=float(plan.duration_seconds),
            tts_provider=getattr(settings, "tts_provider", "edge_tts"),
            model=getattr(settings, "ollama_model", "llama3.2:3b"),
        )

        # 7. Upsert validated Layer B video scenes into Qdrant for timecode Q&A
        try:
            from ...db.vector_store import upsert_layer_b_scenes
            cumulative_time = 0.0
            layer_b_chunks = []
            for s_idx, scene in enumerate(plan.scenes):
                dur = float(scene.duration_seconds or 5.0)
                t_start = round(cumulative_time, 2)
                t_end = round(cumulative_time + dur, 2)
                cumulative_time = t_end

                chunk_ids = scene.source_chunk_ids or plan.source_chunk_ids or target.chunk_ids or []
                pg_start = scene.page_start or plan.page_start or target.page_start
                pg_end = scene.page_end or plan.page_end or target.page_end

                layer_b_chunk = LayerBVideoSceneChunk(
                    scene_id=scene.scene_id or f"scene_{s_idx + 1}",
                    video_id=jid,
                    user_id=student_id,
                    source_id=source_id,
                    source_version="v1",
                    concept_id=target.concept_id,
                    scene_type=scene.scene_type,
                    title=scene.title or f"Scene {s_idx + 1}",
                    narration_text=scene.narration or "",
                    timestamp_start=t_start,
                    timestamp_end=t_end,
                    source_chunk_ids=chunk_ids,
                    page_start=pg_start,
                    page_end=pg_end,
                    approval_status="approved",
                    grounding_status="verified_grounded",
                )
                layer_b_chunks.append(layer_b_chunk)

            upserted_scenes_count = upsert_layer_b_scenes(layer_b_chunks)
            logger.info("%s Upserted %d Layer B scene chunks into Qdrant", log_prefix, upserted_scenes_count)
        except Exception as vec_exc:
            logger.warning("%s Failed to sync Layer B scene chunks to Qdrant: %s", log_prefix, vec_exc)

        artifact.video_path = str(final_mp4_path)
        artifact.status = VideoJobStatus.COMPLETED
        artifact.stage = "COMPLETED"
        artifact.progress = 100
        artifact.completed_at = datetime.now(timezone.utc).isoformat()
        _save_video_artifact(artifact)
        logger.info("%s Video generation complete: %s", log_prefix, final_mp4_path)
        return artifact

    except Exception as exc:
        logger.error("%s Job failed: %s", log_prefix, exc, exc_info=True)
        artifact.status = VideoJobStatus.FAILED
        artifact.stage = "FAILED"
        artifact.error = str(exc)
        _save_video_artifact(artifact)
        return artifact
    finally:
        if acquired_sem:
            sem.release()
