"""Structured video artifact store for Step 3 remedial lessons.

Manages persistent on-disk organization under:
storage/videos/{student_id}/{source_id}/{concept_id}/
  ├── video_plan.json
  ├── narration.txt
  ├── narration.wav (or narration.mp3)
  ├── alignment.json
  ├── subtitles.srt
  ├── scenes/
  ├── final.mp4
  └── metadata.json

Provides idempotency checks, artifact discovery, and metadata querying.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...core.config import settings
from .scene_schema import VideoArtifact, VideoJobStatus, VideoPlan

logger = logging.getLogger(__name__)


def get_video_dir(student_id: str, source_id: str, concept_id: str) -> Path:
    """Get or create the canonical artifact directory for a concept video."""
    base_dir = Path(getattr(settings, "video_output_dir", settings.renders_dir.parent / "videos"))
    target_dir = base_dir / student_id / source_id / concept_id
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def find_existing_video(
    student_id: str,
    source_id: str,
    concept_id: str,
) -> dict[str, Any] | None:
    """Idempotency check: returns existing metadata if video is already completed."""
    vdir = get_video_dir(student_id, source_id, concept_id)
    meta_file = vdir / "metadata.json"
    mp4_file = vdir / "final.mp4"

    if meta_file.exists() and mp4_file.exists() and mp4_file.stat().st_size > 1024:
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if data.get("status") in ("COMPLETED", VideoJobStatus.COMPLETED.value):
                logger.info(
                    "[artifact_store] Found existing video for %s/%s/%s: %s",
                    student_id,
                    source_id,
                    concept_id,
                    mp4_file,
                )
                return data
        except Exception as exc:
            logger.warning("[artifact_store] Error reading existing metadata: %s", exc)
    return None


def store_video_artifacts(
    video_id: str,
    student_id: str,
    source_id: str,
    concept_id: str,
    concept_name: str,
    plan: VideoPlan,
    final_mp4: Path,
    audio_path: Path | None = None,
    srt_path: Path | None = None,
    alignment_data: dict[str, Any] | None = None,
    actual_seconds: float | None = None,
    tts_provider: str = "edge_tts",
    model: str = "llama3.2:3b",
) -> Path:
    """Store complete artifact bundle in the canonical directory."""
    target_dir = get_video_dir(student_id, source_id, concept_id)

    # 1. video_plan.json
    (target_dir / "video_plan.json").write_text(
        plan.model_dump_json(indent=2), encoding="utf-8"
    )

    # 2. narration.txt
    narration_text = (
        plan.narration_script
        or " ".join(seg.text for seg in plan.narration)
        or f"Review of {concept_name}."
    )
    (target_dir / "narration.txt").write_text(narration_text, encoding="utf-8")

    # 3. narration audio file
    if audio_path and audio_path.exists():
        dest_audio = target_dir / ("narration" + audio_path.suffix)
        if dest_audio != audio_path:
            shutil.copy2(audio_path, dest_audio)

    # 4. subtitles.srt
    if srt_path and srt_path.exists():
        dest_srt = target_dir / "subtitles.srt"
        if dest_srt != srt_path:
            shutil.copy2(srt_path, dest_srt)

    # 5. alignment.json
    align_file = target_dir / "alignment.json"
    if alignment_data:
        align_file.write_text(json.dumps(alignment_data, indent=2), encoding="utf-8")
    else:
        align_file.write_text(json.dumps({"concept_id": concept_id, "aligned": True}, indent=2), encoding="utf-8")

    # 6. final.mp4
    dest_mp4 = target_dir / "final.mp4"
    if dest_mp4 != final_mp4 and final_mp4.exists():
        shutil.copy2(final_mp4, dest_mp4)

    # 7. metadata.json
    metadata = {
        "video_id": video_id,
        "job_id": video_id,
        "student_id": student_id,
        "source_id": source_id,
        "concept_id": concept_id,
        "concept_name": concept_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_seconds": plan.target_seconds or plan.duration_seconds,
        "actual_seconds": actual_seconds or float(plan.duration_seconds),
        "model": model,
        "tts_provider": tts_provider,
        "source_chunk_ids": plan.source_chunk_ids or plan.provenance_chunks,
        "source_content_ids": plan.source_content_ids,
        "page_start": plan.page_start,
        "page_end": plan.page_end,
        "status": "COMPLETED",
        "video_path": str(dest_mp4),
        "subtitle_path": str(target_dir / "subtitles.srt") if srt_path and srt_path.exists() else None,
    }
    meta_file = target_dir / "metadata.json"
    meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    logger.info("[artifact_store] Successfully persisted all video artifacts to %s", target_dir)
    return meta_file


def get_metadata(student_id: str, source_id: str, concept_id: str) -> dict[str, Any] | None:
    """Retrieve metadata.json for a concept video."""
    vdir = get_video_dir(student_id, source_id, concept_id)
    m = vdir / "metadata.json"
    if m.exists():
        return json.loads(m.read_text(encoding="utf-8"))
    return None
