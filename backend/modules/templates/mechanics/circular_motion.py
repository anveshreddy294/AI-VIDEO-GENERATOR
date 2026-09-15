"""Circular Motion template.

Visual sequence:
  1. Title + circular path (dashed) drawn on screen
  2. Object (ball/dot) placed on the path at 3 o'clock position
  3. Velocity arrow (tangent, upward) appears — showing tangential direction
  4. Centripetal acceleration arrow points inward toward center — labeled a_c
  5. Object begins orbiting the circle (continuous arc animation)
  6. At 90° intervals: velocity arrow updates to remain tangential
  7. Centripetal force label: F_c = mv²/r
  8. "Always perpendicular to velocity" annotation
"""
from __future__ import annotations

import math
from typing import Any

from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    TEXT_COLOR,
    ACCENT1,
    ACCENT2,
    FORCE_COLOR,
    VEL_COLOR,
    event_rt,
    event_hold,
)

ORBIT_COLOR = "#4f4f6f"
CENTRIPETAL_COLOR = "#ff7a59"
TANGENT_COLOR = "#4fc3f7"
BALL_COLOR = "#41d4a8"
EQ_COLOR = "#e0e6f0"
CENTER_COLOR = "#f7c948"


class CircularMotionTemplate:
    ALLOWED_EVENTS = {
        "place", "show_velocity", "show_centripetal",
        "orbit", "freeze_at_top", "show_equation", "annotate", "hold"
    }
    SLOTS = {}  # uses built-in circle path visuals

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 13.0))
        title_text = plan.get("title", "Circular Motion")

        radius = 1.9
        cx, cy = -0.5, -0.1    # circle center
        # Starting position: 3 o'clock (right of center)
        start_angle = 0.0
        ball_x = cx + radius
        ball_y = cy
        arrow_len = 1.1
        centripetal_len = 1.0

        rt_place = event_rt(timeline, "e0", 0.9)
        rt_velocity = event_rt(timeline, "e1", 0.7)
        hold_vel = event_hold(timeline, "e1", 0.4)
        rt_centripetal = event_rt(timeline, "e2", 0.7)
        hold_cent = event_hold(timeline, "e2", 0.45)
        rt_orbit = event_rt(timeline, "e3", 2.2)
        rt_freeze = event_rt(timeline, "e4", 0.5)
        hold_freeze = event_hold(timeline, "e4", 0.5)
        rt_equation = event_rt(timeline, "e5", 0.7)
        hold_eq = event_hold(timeline, "e5", 0.4)
        rt_annotate = event_rt(timeline, "e6", 0.65)
        hold_ann = event_hold(timeline, "e6", 0.5)

        # At top of circle (12 o'clock): ball is at (cx, cy + radius)
        top_x = cx
        top_y = cy + radius

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Circular path (dashed)
            f'        orbit_path = Circle(radius={radius:.2f}, color="{ORBIT_COLOR}", stroke_width=2.5)',
            f'        orbit_path.move_to(np.array([{cx:.2f}, {cy:.2f}, 0]))',
            f'        orbit_path.set_style(stroke_opacity=0.6)',
            "",
            # Center dot + cross marker
            f'        center_dot = Dot(radius=0.07, color="{CENTER_COLOR}")',
            f'        center_dot.move_to(np.array([{cx:.2f}, {cy:.2f}, 0]))',
            f'        center_cross_h = Line(',
            f'            np.array([{cx - 0.18:.2f}, {cy:.2f}, 0]),',
            f'            np.array([{cx + 0.18:.2f}, {cy:.2f}, 0]),',
            f'            color="{CENTER_COLOR}", stroke_width=2',
            f'        )',
            f'        center_cross_v = Line(',
            f'            np.array([{cx:.2f}, {cy - 0.18:.2f}, 0]),',
            f'            np.array([{cx:.2f}, {cy + 0.18:.2f}, 0]),',
            f'            color="{CENTER_COLOR}", stroke_width=2',
            f'        )',
            f'        center_grp = VGroup(center_dot, center_cross_h, center_cross_v)',
            "",
            # Ball (object on the path)
            f'        ball = Dot(radius=0.17, color="{BALL_COLOR}", fill_opacity=0.95)',
            f'        ball.move_to(np.array([{ball_x:.2f}, {ball_y:.2f}, 0]))',
            "",
            # Tangential velocity arrow (upward at 3 o'clock)
            f'        vel_arrow = Arrow(',
            f'            np.array([{ball_x:.2f}, {ball_y:.2f}, 0]),',
            f'            np.array([{ball_x:.2f}, {ball_y + arrow_len:.2f}, 0]),',
            f'            color="{TANGENT_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        vel_lbl = Text("v", font_size=22, color="{TANGENT_COLOR}", slant=ITALIC)',
            f'        vel_lbl.next_to(vel_arrow, RIGHT, buff=0.1)',
            f'        vel_grp = VGroup(vel_arrow, vel_lbl)',
            f'        vel_grp.set_opacity(0)',
            "",
            # Centripetal arrow (inward: pointing from ball toward center)
            f'        cent_arrow = Arrow(',
            f'            np.array([{ball_x:.2f}, {ball_y:.2f}, 0]),',
            f'            np.array([{cx + (ball_x - cx) * (1 - centripetal_len/radius):.2f}, {ball_y:.2f}, 0]),',
            f'            color="{CENTRIPETAL_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        cent_lbl = Text("a\u2c7c", font_size=20, color="{CENTRIPETAL_COLOR}")',
            f'        cent_lbl.next_to(cent_arrow, DOWN, buff=0.1)',
            f'        cent_grp = VGroup(cent_arrow, cent_lbl)',
            f'        cent_grp.set_opacity(0)',
            "",
            # Orbit path for animation (full circle for MoveAlongPath)
            f'        full_orbit = Circle(radius={radius:.2f})',
            f'        full_orbit.move_to(np.array([{cx:.2f}, {cy:.2f}, 0]))',
            f'        full_orbit.set_opacity(0)',
            "",
            # Top-of-circle state: velocity arrow pointing right (tangent at top)
            f'        top_vel = Arrow(',
            f'            np.array([{top_x:.2f}, {top_y:.2f}, 0]),',
            f'            np.array([{top_x + arrow_len:.2f}, {top_y:.2f}, 0]),',
            f'            color="{TANGENT_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        top_cent = Arrow(',
            f'            np.array([{top_x:.2f}, {top_y:.2f}, 0]),',
            f'            np.array([{top_x:.2f}, {cy + (top_y - cy) * (1 - centripetal_len/radius):.2f}, 0]),',
            f'            color="{CENTRIPETAL_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        top_ball = Dot(radius=0.17, color="{BALL_COLOR}", fill_opacity=0.95)',
            f'        top_ball.move_to(np.array([{top_x:.2f}, {top_y:.2f}, 0]))',
            f'        frozen_grp = VGroup(top_ball, top_vel, top_cent)',
            f'        frozen_grp.set_opacity(0)',
            "",
            # Equation box
            f'        eq_box = RoundedRectangle(corner_radius=0.18, width=4.4, height=0.85,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        eq_text = Text("F\u2c7c = mv\u00b2/r", font_size=26, color="{EQ_COLOR}", weight=BOLD)',
            f'        eq_box.to_edge(RIGHT, buff=0.3).shift(UP*1.5)',
            f'        eq_text.move_to(eq_box.get_center())',
            f'        eq_grp = VGroup(eq_box, eq_text)',
            f'        eq_grp.set_opacity(0)',
            "",
            # Annotation
            f'        ann_text = Text("v \u22a5 a\u2c7c always", font_size=21, color="{TEXT_COLOR}")',
            f'        ann_text.to_edge(RIGHT, buff=0.25).shift(DOWN*0.1)',
            f'        ann_text.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), Create(orbit_path), FadeIn(center_grp, ball), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Velocity arrow (tangential)
        lines += [
            f'        vel_grp.set_opacity(1)',
            f'        self.play(GrowArrow(vel_arrow), FadeIn(vel_lbl), run_time={rt_velocity:.3f})',
        ]
        elapsed += rt_velocity
        if hold_vel > 0.05:
            lines += [f'        self.wait({hold_vel:.3f})  # viewer sees tangential direction']
            elapsed += hold_vel

        # Centripetal arrow (inward)
        lines += [
            f'        cent_grp.set_opacity(1)',
            f'        self.play(GrowArrow(cent_arrow), FadeIn(cent_lbl), run_time={rt_centripetal:.3f})',
        ]
        elapsed += rt_centripetal
        if hold_cent > 0.05:
            lines += [f'        self.wait({hold_cent:.3f})  # both arrows visible, perpendicularity clear']
            elapsed += hold_cent

        # Object orbits — moves along circle
        lines += [
            f'        self.play(',
            f'            MoveAlongPath(ball, full_orbit),',
            f'            MoveAlongPath(vel_arrow, full_orbit),',
            f'            MoveAlongPath(cent_arrow, full_orbit),',
            f'            FadeOut(vel_lbl, cent_lbl),',
            f'            run_time={rt_orbit:.3f},',
            f'            rate_func=rate_functions.linear',
            f'        )',
        ]
        elapsed += rt_orbit

        # Freeze at top — show perpendicularity clearly
        lines += [
            f'        frozen_grp.set_opacity(1)',
            f'        self.play(',
            f'            FadeOut(ball, vel_arrow, cent_arrow),',
            f'            FadeIn(top_ball, top_vel, top_cent),',
            f'            run_time={rt_freeze:.3f}',
            f'        )',
        ]
        elapsed += rt_freeze
        if hold_freeze > 0.05:
            lines += [f'        self.wait({hold_freeze:.3f})  # viewer sees right-angle at top']
            elapsed += hold_freeze

        # Equation
        lines += [
            f'        eq_grp.set_opacity(1)',
            f'        self.play(FadeIn(eq_box), Write(eq_text), run_time={rt_equation:.3f})',
        ]
        elapsed += rt_equation
        if hold_eq > 0.05:
            lines += [f'        self.wait({hold_eq:.3f})']
            elapsed += hold_eq

        # Perpendicular annotation
        lines += [
            f'        ann_text.set_opacity(1)',
            f'        self.play(FadeIn(ann_text, shift=LEFT*0.2), run_time={rt_annotate:.3f})',
        ]
        elapsed += rt_annotate
        if hold_ann > 0.05:
            lines += [f'        self.wait({hold_ann:.3f})']
            elapsed += hold_ann

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")