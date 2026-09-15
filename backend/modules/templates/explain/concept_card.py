"""Concept card chalkboard explanation template."""
from __future__ import annotations

from typing import Any

from modules.templates.explain._base import (
    EXPLAIN_ALLOWED_EVENTS,
    audio_duration,
    build_timing_waits,
    cards_literal,
    esc,
    event_rt,
    merge_content,
    wrap_explain_scene,
)

CONTENT_SCHEMA = """{
  "main_title": "<scene title>",
  "cards": [
    {"title": "<short label>", "content": "<1-2 sentence explanation>", "color": "#7BA7C2"},
    {"title": "...", "content": "...", "color": "#7AC2A0"}
  ]
}
Provide 2-4 cards. Colors: #7BA7C2 (blue), #7AC2A0 (green), #E8D87A (yellow), #E8A0A0 (pink)."""


class ConceptCardTemplate:
    ALLOWED_EVENTS = EXPLAIN_ALLOWED_EVENTS
    CONTENT_SCHEMA = CONTENT_SCHEMA
    SLOTS = {}

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        content = merge_content(plan, "concept_card")
        main_title = esc(str(content.get("main_title", plan.get("title", "Concept"))))
        cards_json = cards_literal(content.get("cards", []))
        dur = audio_duration(timeline)

        # Compute wait before title reveal based on e0 start time.
        waits = build_timing_waits(timeline, ["e0", "e1"], [0.3, 1.5])
        pre_title_wait = f"{waits[0]}\n        " if waits[0] else ""
        pre_cards_wait = f"{waits[1]}\n        " if waits[1] else ""

        body = f"""{pre_title_wait}self.build_scene(
            main_title="{main_title}",
            cards={cards_json},
            audio_duration={dur:.3f},
        )"""
        return wrap_explain_scene("concept_card", "ConceptCardScene", body)
