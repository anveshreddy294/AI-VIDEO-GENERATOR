"""Intro template: title card with concept text and key term highlight."""
from __future__ import annotations

from typing import Any

from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    TEXT_COLOR,
    ACCENT1,
    event_rt,
    event_hold,
)


class IntroTemplate:
    """Text-only intro scene: large title, subtitle, highlighted key term."""

    ALLOWED_EVENTS = {"place_title", "place_subtitle", "highlight_term", "hold"}
    SLOTS = {}  # no physics assets

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        title_text = plan.get("title", plan.get("anchor_example", "Concept"))
        subtitle = plan.get("subtitle", "")
        key_term = plan.get("key_term", "")
        audio_dur = float(timeline.get("audio_duration", 8.0))

        rt_title = event_rt(timeline, "e0", 0.8)
        hold_title = event_hold(timeline, "e0", 0.4)
        rt_sub = event_rt(timeline, "e1", 0.7)
        hold_sub = event_hold(timeline, "e1", 0.3)
        rt_term = event_rt(timeline, "e2", 0.6)
        hold_term = event_hold(timeline, "e2", 0.5)

        lines: list[str] = [_HEADER]

        # Objects
        lines.append(f'        title = Text("{_esc(title_text)}", font_size=52, weight=BOLD, color="{TITLE_COLOR}")')
        lines.append(f'        title.to_edge(UP, buff=0.8)')

        if subtitle:
            lines.append(f'        subtitle = Text("{_esc(subtitle)}", font_size=30, color="{TEXT_COLOR}")')
            lines.append(f'        subtitle.next_to(title, DOWN, buff=0.5)')

        if key_term:
            lines.append(f'        key_term_box = RoundedRectangle(corner_radius=0.2, width=4.5, height=1.0,'
                         f' color="{ACCENT1}", fill_opacity=0.12, stroke_width=2)')
            lines.append(f'        key_term_text = Text("{_esc(key_term)}", font_size=36, color="{ACCENT1}", weight=BOLD)')
            lines.append(f'        key_term_box.move_to(ORIGIN + DOWN*0.4)')
            lines.append(f'        key_term_text.move_to(key_term_box.get_center())')

        lines.append("")

        # Animations
        elapsed = 0.0

        lines.append(f'        self.play(Write(title), run_time={rt_title:.3f})')
        elapsed += rt_title
        if hold_title > 0.05:
            lines.append(f'        self.wait({hold_title:.3f})')
            elapsed += hold_title

        if subtitle:
            lines.append(f'        self.play(FadeIn(subtitle, shift=UP*0.2), run_time={rt_sub:.3f})')
            elapsed += rt_sub
            if hold_sub > 0.05:
                lines.append(f'        self.wait({hold_sub:.3f})')
                elapsed += hold_sub

        if key_term:
            lines.append(f'        self.play(FadeIn(key_term_box), Write(key_term_text), run_time={rt_term:.3f})')
            elapsed += rt_term
            if hold_term > 0.05:
                lines.append(f'        self.wait({hold_term:.3f})')
                elapsed += hold_term

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines.append(f'        self.wait({tail:.3f})')

        lines.append("")
        lines.append(_FOOTER)
        return "\n".join(lines)


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
