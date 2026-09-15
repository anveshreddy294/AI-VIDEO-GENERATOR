"""Extract and persist narration scripts per scene."""

from __future__ import annotations

from typing import Any

from modules.config import PATHS, get_logger

logger = get_logger(__name__)


def extract_narration(scenes: list[dict[str, Any]]) -> dict[int, str]:
    """Extract narration text keyed by scene_id and write .txt files."""
    narrations: dict[int, str] = {}
    for scene in scenes:
        scene_id = scene["scene_id"]
        text = scene["narration"].strip()
        narrations[scene_id] = text
        txt_path = PATHS["audio"] / f"scene_{scene_id}.txt"
        txt_path.write_text(text, encoding="utf-8")
        logger.info("Narration saved: %s (%d chars)", txt_path, len(text))
    return narrations
