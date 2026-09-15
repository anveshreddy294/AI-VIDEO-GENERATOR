"""Summary template: animated bullet-point list with key takeaways."""
from __future__ import annotations

from typing import Any

from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    TEXT_COLOR,
    ACCENT1,
    ACCENT2,
    event_rt,
    event_hold,
)


class SummaryTemplate:
    ALLOWED_EVENTS = {"place_title", "place_point", "hold"}
    SLOTS = {}

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 10.0))
        title_text = plan.get("title", "Summary")
        points = plan.get("summary_points", [
            "Objects at rest remain at rest",
            "Objects in motion remain in motion",
            "An external force is required for change",
        ])
        # Cap at 4 points for layout
        points = points[:4]

        rt_title = event_rt(timeline, "e0", 0.8)
        hold_title = event_hold(timeline, "e0", 0.3)
        rt_per_point = event_rt(timeline, "e1", 0.7)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=44, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.4)',
            "",
        ]

        # Build point mobjects
        for i, pt in enumerate(points):
            bullet = "\u2022"
            lines += [
                f'        pt_{i} = Text("{bullet} {_esc(pt)}", font_size=28, color="{TEXT_COLOR}")',
                f'        pt_{i}.set_opacity(0)',
            ]

        # Arrange them vertically
        if points:
            first = "pt_0"
            lines += [f'        all_pts = VGroup({", ".join(f"pt_{i}" for i in range(len(points)))})']
            lines += [f'        all_pts.arrange(DOWN, aligned_edge=LEFT, buff=0.35)']
            lines += [f'        all_pts.next_to(title, DOWN, buff=0.5).shift(LEFT*0.5)']

        lines += [""]

        elapsed = 0.0

        lines += [f'        self.play(Write(title), run_time={rt_title:.3f})']
        elapsed += rt_title
        if hold_title > 0.05:
            lines += [f'        self.wait({hold_title:.3f})']
            elapsed += hold_title

        for i in range(len(points)):
            eid = f"e{i+1}"
            rt_pt = event_rt(timeline, eid, rt_per_point)
            hold_pt = event_hold(timeline, eid, 0.3)
            lines += [
                f'        pt_{i}.set_opacity(1)',
                f'        self.play(FadeIn(pt_{i}, shift=RIGHT*0.3), run_time={rt_pt:.3f})',
            ]
            elapsed += rt_pt
            if hold_pt > 0.05:
                lines += [f'        self.wait({hold_pt:.3f})']
                elapsed += hold_pt

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
