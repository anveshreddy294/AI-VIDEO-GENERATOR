"""Side-by-side comparison chalkboard template."""
from __future__ import annotations

from typing import Any

from modules.templates.explain._base import (
    EXPLAIN_ALLOWED_EVENTS,
    audio_duration,
    build_timing_waits,
    esc,
    merge_content,
    wrap_explain_scene,
)

CONTENT_SCHEMA = """{
  "left_title": "<label for left panel>",
  "left_content": "<2-3 sentences>",
  "right_title": "<label for right panel>",
  "right_content": "<2-3 sentences contrasting the left>"
}"""


class ComparisonTemplate:
    ALLOWED_EVENTS = EXPLAIN_ALLOWED_EVENTS
    CONTENT_SCHEMA = CONTENT_SCHEMA
    SLOTS = {}

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        content = merge_content(plan, "comparison")
        dur = audio_duration(timeline)

        waits = build_timing_waits(timeline, ["e0", "e1"], [0.3, 1.5])
        pre_title_wait = f"{waits[0]}\n        " if waits[0] else ""

        body = f"""{pre_title_wait}self.build_scene(
            left_title="{esc(str(content.get('left_title', 'A')))}",
            left_content="{esc(str(content.get('left_content', '')))}",
            right_title="{esc(str(content.get('right_title', 'B')))}",
            right_content="{esc(str(content.get('right_content', '')))}",
            audio_duration={dur:.3f},
        )"""
        return wrap_explain_scene("comparison_scene", "ComparisonScene", body)
