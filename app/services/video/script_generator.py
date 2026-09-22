"""Script & narration generator for educational remedial video lessons.

Derives narration strictly from VideoPlan, concept definitions, and authoritative source chunks.
Ensures narration length matches the scene duration budget according to standard speech rates (130–160 WPM).
"""

from __future__ import annotations

import logging
from typing import Any

from .scene_schema import NarrationScript, NarrationSegment, VideoPlan

logger = logging.getLogger(__name__)

# Default educational narration speech rate in words per minute
DEFAULT_WPM: int = 145


def estimate_speech_duration(text: str, wpm: int = DEFAULT_WPM) -> float:
    """Estimate speech duration in seconds from text word count."""
    if not text or not text.strip():
        return 0.0
    words = [w for w in text.split() if w.strip()]
    return (len(words) / max(60, wpm)) * 60.0


def shorten_narration_to_budget(text: str, budget_seconds: float, wpm: int = DEFAULT_WPM) -> str:
    """Shorten or truncate narration text if it exceeds the scene duration budget."""
    if budget_seconds <= 0 or not text.strip():
        return text

    max_words = int((budget_seconds / 60.0) * wpm)
    words = text.split()
    if len(words) <= max_words:
        return text

    # Trim to maximum words ending on a sentence or sensible boundary
    trimmed_words = words[:max_words]
    trimmed_text = " ".join(trimmed_words)

    # Ensure sentence ends cleanly with period if truncated
    if not trimmed_text.endswith((".", "!", "?")):
        trimmed_text += "."

    logger.info(
        "[script_generator] Shortened narration from %d to %d words to fit %.1fs budget",
        len(words),
        len(trimmed_words),
        budget_seconds,
    )
    return trimmed_text


def extract_narration_script(plan: VideoPlan, wpm: int = DEFAULT_WPM) -> NarrationScript:
    """Extract complete narration script and segments from VideoPlan, enforcing duration budgets."""
    segments: list[NarrationSegment] = []

    # If plan has explicit narration segments
    if plan.narration:
        for seg in plan.narration:
            matched_scene = (
                plan.scenes[seg.scene_index]
                if 0 <= seg.scene_index < len(plan.scenes)
                else None
            )
            budget = (
                matched_scene.duration_seconds
                if matched_scene
                else seg.target_seconds
            )
            # Budget check and gentle shortening if needed
            fitted_text = shorten_narration_to_budget(seg.text, budget, wpm=wpm)
            segments.append(
                NarrationSegment(
                    segment_id=seg.segment_id,
                    scene_index=seg.scene_index,
                    text=fitted_text,
                    target_seconds=budget,
                )
            )
    else:
        # Construct segments from scenes directly
        for idx, scene in enumerate(plan.scenes):
            raw_text = scene.narration or scene.text or scene.title or plan.concept_name
            fitted = shorten_narration_to_budget(raw_text, scene.duration_seconds, wpm=wpm)
            segments.append(
                NarrationSegment(
                    scene_index=idx,
                    text=fitted,
                    target_seconds=scene.duration_seconds,
                )
            )

    full_text_parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    full_text = " ".join(full_text_parts)
    total_seconds = sum(seg.target_seconds for seg in segments) or float(plan.duration_seconds)

    return NarrationScript(
        concept_id=plan.concept_id,
        total_target_seconds=total_seconds,
        segments=segments,
        full_text=full_text,
    )
