"""Narration extraction and formatting for TTS synthesis (re-exported from script_generator)."""

from __future__ import annotations

from .script_generator import (
    DEFAULT_WPM,
    estimate_speech_duration,
    extract_narration_script,
    shorten_narration_to_budget,
)

__all__ = [
    "DEFAULT_WPM",
    "estimate_speech_duration",
    "extract_narration_script",
    "shorten_narration_to_budget",
]
