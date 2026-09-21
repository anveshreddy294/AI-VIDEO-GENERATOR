"""Narration extraction and formatting for TTS synthesis."""

from __future__ import annotations

from .scene_schema import NarrationScript, NarrationSegment, VideoPlan


def extract_narration_script(plan: VideoPlan) -> NarrationScript:
    """Extract complete narration script and segments from VideoPlan."""
    segments = plan.narration or []
    full_text_parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    full_text = " ".join(full_text_parts)

    total_seconds = sum(seg.target_seconds for seg in segments) or float(plan.duration_seconds)

    return NarrationScript(
        concept_id=plan.concept_id,
        total_target_seconds=total_seconds,
        segments=segments,
        full_text=full_text,
    )
