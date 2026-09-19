"""High-level orchestration pipeline for Step 3 Video Generation.

Coordinates script generation, neural voiceover synthesis, visual card composition,
and audio-video multiplexing into a single cohesive, observable workflow.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ...core.config import settings
from ...services.assessment.providers import LLMProvider
from ...services.assessment.schemas import VideoTarget
from .audio_synthesizer import synthesize_script_audio
from .muxer import concatenate_video_clips, generate_webvtt_subtitles, mux_audio_and_video, probe_media_duration
from .schemas import VideoRenderJob, VideoScript
from .script_generator import generate_video_script
from .visual_renderer import render_scene_to_video_clip

logger = logging.getLogger(__name__)

# Base output directory
VIDEOS_DIR = Path(settings.runtime_dir) / "videos"


def _get_videos_index_path() -> Path:
    p = VIDEOS_DIR / "videos_index.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("{}", encoding="utf-8")
    return p


def load_videos_index() -> Dict[str, dict]:
    """Load the master index of rendered videos."""
    idx_path = _get_videos_index_path()
    try:
        return json.loads(idx_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_videos_index(index: Dict[str, dict]) -> None:
    """Save updates to the master video index atomically using a temporary file."""
    idx_path = _get_videos_index_path()
    temp_path = idx_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    temp_path.replace(idx_path)


def register_completed_video(job: VideoRenderJob, script: VideoScript) -> None:
    """Register a completed video in the master video index."""
    idx = load_videos_index()
    idx[job.video_id] = {
        "video_id": job.video_id,
        "job_id": job.job_id,
        "student_id": job.student_id,
        "source_id": job.source_id,
        "concept_id": job.concept_id,
        "concept_name": job.concept_name,
        "difficulty": script.difficulty,
        "target_seconds": script.target_total_seconds,
        "actual_duration_seconds": job.duration_seconds,
        "video_file_path": job.video_file_path,
        "subtitles_file_path": job.subtitles_file_path,
        "completed_at": job.completed_at,
    }
    save_videos_index(idx)


async def execute_video_generation_pipeline(
    target: VideoTarget,
    student_id: str,
    source_id: str,
    job_id: Optional[str] = None,
    video_id: Optional[str] = None,
    mock_mode: bool = False,
    provider: Optional[LLMProvider] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> VideoRenderJob:
    """Execute the end-to-end video generation pipeline asynchronously.

    Steps:
    1. Generate grounded VideoScript
    2. Synthesize audio voiceover tracks
    3. Render visual 1080p clips
    4. Mux audio + visual + subtitles into final MP4
    5. Register in videos index
    """
    if not job_id:
        job_id = f"JOB_VGEN_{uuid.uuid4().hex[:10]}"

    if not video_id:
        video_id = f"VID_{uuid.uuid4().hex[:12]}"

    job = VideoRenderJob(
        job_id=job_id,
        video_id=video_id,
        student_id=student_id,
        source_id=source_id,
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        status="pending",
        progress_percent=0,
        current_stage="Initializing video workspace",
    )

    def _update_progress(percent: int, stage: str):
        job.progress_percent = percent
        job.current_stage = stage
        if progress_callback:
            try:
                progress_callback(percent, stage)
            except Exception:
                pass

    video_workspace = VIDEOS_DIR / job.video_id
    video_workspace.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Script Generation (0% -> 20%)
        _update_progress(10, f"Generating grounded lesson script for '{target.concept_name}'")
        job.status = "generating_script"

        # Run script generator (CPU/network bound)
        loop = asyncio.get_running_loop()
        script: VideoScript = await loop.run_in_executor(
            None,
            generate_video_script,
            target,
            student_id,
            source_id,
            provider,
        )
        # Match script video_id to job video_id
        script.video_id = job.video_id

        # Save script JSON
        script_path = video_workspace / "script.json"
        script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        _update_progress(25, "Script generated and validated")

        # Step 2: Audio Synthesis (25% -> 50%)
        job.status = "synthesizing_voiceover"
        _update_progress(30, "Synthesizing neural voiceover narration")

        master_audio_path, scene_audio_paths, measured_durations = await synthesize_script_audio(
            script=script,
            output_dir=video_workspace,
            mock_mode=mock_mode,
        )
        _update_progress(50, f"Synthesized {len(scene_audio_paths)} audio tracks ({sum(measured_durations):.1f}s)")

        # Step 3: Visual Scene Rendering (50% -> 80%)
        job.status = "rendering_visuals"
        _update_progress(55, "Rendering 1080p visual scenes")

        scene_video_clips: List[Path] = []
        total_duration = sum(scene.duration_seconds for scene in script.scenes)
        accumulated_time = 0.0

        for idx, scene in enumerate(script.scenes, start=1):
            clip_path = video_workspace / f"scene_{idx}_clip.mp4"
            start_ratio = accumulated_time / max(1.0, total_duration)
            end_ratio = (accumulated_time + scene.duration_seconds) / max(1.0, total_duration)

            # Render clip
            await loop.run_in_executor(
                None,
                render_scene_to_video_clip,
                scene,
                scene.duration_seconds,
                clip_path,
                target.concept_name,
                target.difficulty,
                idx,
                len(script.scenes),
                source_id,
                start_ratio,
                end_ratio,
            )

            scene_video_clips.append(clip_path)
            accumulated_time += scene.duration_seconds
            progress_pct = 55 + int(25 * (idx / len(script.scenes)))
            _update_progress(progress_pct, f"Rendered scene {idx}/{len(script.scenes)}")

        # Step 4: Video Stitching & Audio-Video Muxing (80% -> 95%)
        job.status = "muxing_media"
        _update_progress(82, "Concatenating scene clips")

        raw_video_path = video_workspace / "raw_video.mp4"
        await loop.run_in_executor(
            None,
            concatenate_video_clips,
            scene_video_clips,
            raw_video_path,
        )

        _update_progress(88, "Muxing audio, video, and generating subtitles")
        final_mp4_path = video_workspace / "final_video.mp4"
        await loop.run_in_executor(
            None,
            mux_audio_and_video,
            raw_video_path,
            master_audio_path,
            final_mp4_path,
        )

        subtitles_path = video_workspace / "subtitles.vtt"
        generate_webvtt_subtitles(script, measured_durations, subtitles_path)

        # Step 5: Finalization & Registration (100%)
        job.status = "completed"
        job.progress_percent = 100
        job.current_stage = "Remediation video ready"
        job.video_file_path = str(final_mp4_path)
        job.subtitles_file_path = str(subtitles_path)
        probed_dur = probe_media_duration(final_mp4_path)
        if probed_dur <= 0.0:
            probed_dur = probe_media_duration(master_audio_path)
        job.duration_seconds = round(probed_dur if probed_dur > 0.0 else accumulated_time, 2)
        job.completed_at = datetime.now(timezone.utc).isoformat()

        # Save job status
        job_meta_path = video_workspace / "job.json"
        job_meta_path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

        # Register in master index
        register_completed_video(job, script)
        _update_progress(100, f"Remediation video completed ({job.duration_seconds}s)")

        logger.info(
            f"[pipeline] Successfully rendered video {job.video_id} for concept '{target.concept_name}' "
            f"({job.duration_seconds}s) at {final_mp4_path}"
        )
        return job

    except Exception as err:
        logger.error(f"[pipeline] Video generation failed for job {job_id}: {err}", exc_info=True)
        job.status = "failed"
        job.error_message = str(err)
        job.current_stage = f"Failed: {str(err)}"
        job_meta_path = video_workspace / "job.json"
        job_meta_path.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        raise
