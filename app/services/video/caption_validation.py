"""Independently validate generated scene WebVTT against measured media timing.

This intentionally accepts our one-cue-per-scene format, not arbitrary WebVTT.
It does not claim word alignment or speech recognition accuracy.
"""
from __future__ import annotations

import html
import math
import re
from pathlib import Path

from .scene_schema import SceneTimelineEntry, VideoPlan

TIMESTAMP_TOLERANCE_SECONDS = .002  # millisecond serialization/rounding only
MAX_CAPTION_BYTES = 1024 * 1024
_TIME = r"(\d{2,}):([0-5]\d):([0-5]\d)\.(\d{3})"
_CUE = re.compile(rf"^{_TIME} --> {_TIME}$")


class CaptionValidationError(ValueError):
    def __init__(self, code: str = "VIDEO_CAPTIONS_INVALID") -> None:
        super().__init__(code)


def caption_text(text: str) -> str:
    """Contain markup and cue delimiters without changing spoken content."""
    return html.escape(" ".join(text.split()).replace("-->", "→"), quote=False)


def _seconds(parts) -> float:
    hours, minutes, seconds, milliseconds = map(int, parts)
    return hours*3600 + minutes*60 + seconds + milliseconds/1000


def validate_scene_captions(path: Path, plan: VideoPlan,
                           timeline: list[SceneTimelineEntry], final_duration: float) -> None:
    """Read the saved file, reject invalid cues and inconsistent scene metadata."""
    fail = CaptionValidationError
    tolerance = TIMESTAMP_TOLERANCE_SECONDS
    if not math.isfinite(final_duration) or final_duration <= 0 or not timeline:
        raise fail()
    if len(timeline) != len(plan.scenes):
        raise fail()
    try:
        if path.stat().st_size > MAX_CAPTION_BYTES:
            raise fail()
        raw = path.read_bytes()
        if len(raw) > MAX_CAPTION_BYTES:
            raise fail()
        document = raw.decode("utf-8-sig").replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        raise fail() from None
    blocks = re.split(r"\n\s*\n", document.strip())
    if not blocks or blocks[0] != "WEBVTT" or len(blocks)-1 != len(timeline):
        raise fail()
    cursor = previous_cue_end = 0.0
    scene_ids = set()
    for index, (block, entry, scene) in enumerate(zip(blocks[1:], timeline, plan.scenes)):
        values = (entry.start_seconds, entry.end_seconds, entry.duration_seconds)
        if (not all(math.isfinite(v) for v in values) or entry.scene_id in scene_ids
                or entry.scene_id != scene.scene_id or entry.scene_index != index or scene.scene_index != index
                or entry.start_seconds < 0 or entry.end_seconds <= entry.start_seconds
                or entry.duration_seconds <= 0 or abs(entry.start_seconds-cursor) > tolerance
                or abs(entry.end_seconds-entry.start_seconds-entry.duration_seconds) > tolerance
                or entry.end_seconds > final_duration+tolerance):
            raise fail()
        scene_ids.add(entry.scene_id)
        lines = block.splitlines()
        if len(lines) != 2 or (match := _CUE.fullmatch(lines[0])) is None:
            raise fail()
        start, end = _seconds(match.groups()[:4]), _seconds(match.groups()[4:])
        expected = caption_text(" ".join(s.text for s in plan.narration if s.scene_index == index))
        if (not expected or lines[1] != expected or end <= start or start < previous_cue_end
                or end > final_duration+tolerance or abs(start-entry.start_seconds) > tolerance
                or abs(end-entry.end_seconds) > tolerance):
            raise fail()
        cursor, previous_cue_end = entry.end_seconds, end
    if abs(cursor-final_duration) > tolerance:
        raise fail()
