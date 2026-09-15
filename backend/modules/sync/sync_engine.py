"""Synchronization engine: audio + WhisperX alignment → event timeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.config import PATHS, RenderWorkspace, get_logger
from modules.sync.timeline_builder import build_event_timeline
from modules.sync.whisper_align import align
from modules.tts.piper_tts import get_audio_duration

logger = get_logger(__name__)


def synchronize_scene(
    plan: dict[str, Any],
    wav_path: Path,
    workspace: RenderWorkspace | None = None,
) -> dict[str, Any]:
    """Build a timed event timeline for one scene."""
    scene_id = plan["scene_id"]
    narration = plan.get("narration", "")
    events = plan.get("events", [])
    logger.info("Synchronizing scene %d (%d events)", scene_id, len(events))

    audio_duration = get_audio_duration(wav_path)
    word_timestamps = align(wav_path, narration)
    timeline = build_event_timeline(events, word_timestamps, audio_duration)

    result: dict[str, Any] = {
        "scene_id": scene_id,
        "audio_duration": audio_duration,
        "word_timestamps": word_timestamps,
        "timeline": timeline,
    }

    timelines_root = (
        workspace.timelines_dir if workspace is not None else PATHS["timelines"]
    )
    out_path = timelines_root / f"scene_{scene_id}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Timeline saved: %s (audio=%.2fs, %d events)",
        out_path, audio_duration, len(timeline["events"]),
    )
    return result


def synchronize_all(
    plans: list[dict[str, Any]],
    audio_paths: dict[int, Path],
    workspace: RenderWorkspace | None = None,
) -> list[dict[str, Any]]:
    """Build timelines for all scenes and write master timeline."""
    timelines = [
        synchronize_scene(plan, audio_paths[plan["scene_id"]], workspace=workspace)
        for plan in plans
    ]

    timelines_root = (
        workspace.timelines_dir if workspace is not None else PATHS["timelines"]
    )
    master_path = timelines_root / "master_timeline.json"
    master_path.write_text(json.dumps(timelines, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Master timeline saved: %s", master_path)
    return timelines
