"""Equation derivation chalkboard template."""
from __future__ import annotations

from typing import Any

from modules.templates.explain._base import (
    EXPLAIN_ALLOWED_EVENTS,
    audio_duration,
    build_timing_waits,
    esc,
    esc_latex,
    merge_content,
    wrap_explain_scene,
)

CONTENT_SCHEMA = """{
  "title": "<scene title>",
  "equation": "<LaTeX without $ delimiters, e.g. W = F \\cdot d \\cos\\theta>",
  "explanation": "<1-2 sentences explaining each symbol or when to use>"
}"""


class EquationTemplate:
    ALLOWED_EVENTS = EXPLAIN_ALLOWED_EVENTS
    CONTENT_SCHEMA = CONTENT_SCHEMA
    SLOTS = {}

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        content = merge_content(plan, "equation")
        dur = audio_duration(timeline)

        waits = build_timing_waits(timeline, ["e0", "e1"], [0.3, 2.0])
        pre_title_wait = f"{waits[0]}\n        " if waits[0] else ""

        body = f"""{pre_title_wait}self.build_scene(
            title_text="{esc(str(content.get('title', plan.get('title', 'Equation'))))}",
            equation_text="{esc_latex(str(content.get('equation', r'F = ma')))}",
            explanation="{esc(str(content.get('explanation', '')))}",
            audio_duration={dur:.3f},
        )"""
        return wrap_explain_scene("equation_scene", "EquationScene", body)
