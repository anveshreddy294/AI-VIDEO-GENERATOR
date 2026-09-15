"""Torque template.

Visual sequence:
  1. Title + horizontal lever (rigid rod) with pivot point at center
  2. Force arrow applied at one end (downward) with label F
  3. Moment arm 'r' shown (dashed line from pivot to force point)
  4. Curved torque arc drawn — rotational tendency visualized
  5. Lever rotates — angular consequence of torque shown
  6. Torque equation τ = r × F highlighted
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
    event_rt,
    event_hold,
)

LEVER_COLOR = "#c8d3e6"
PIVOT_COLOR = "#f7c948"
TORQUE_ARC_COLOR = "#41d4a8"
ARM_COLOR = "#4f8ef7"
EQ_COLOR = "#e0e6f0"
FORCE_APPLY_COLOR = "#ff7a59"


class TorqueTemplate:
    ALLOWED_EVENTS = {
        "place", "apply_force", "show_arm",
        "show_arc", "rotate_lever", "show_equation", "hold"
    }
    SLOTS = {}  # uses built-in rod + pivot visuals

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 12.0))
        title_text = plan.get("title", "Torque")

        pivot_x = 0.0
        pivot_y = 0.3
        lever_half = 3.2
        force_x = lever_half      # force applied at right end
        force_len = 1.4
        arm_label = plan.get("arm_label", "r")
        force_label = plan.get("force_label", "F")
        rotate_angle = math.radians(-18)  # lever tilts clockwise

        rt_place = event_rt(timeline, "e0", 0.8)
        rt_force = event_rt(timeline, "e1", 0.7)
        hold_force = event_hold(timeline, "e1", 0.4)
        rt_arm = event_rt(timeline, "e2", 0.65)
        hold_arm = event_hold(timeline, "e2", 0.35)
        rt_arc = event_rt(timeline, "e3", 0.65)
        hold_arc = event_hold(timeline, "e3", 0.4)
        rt_rotate = event_rt(timeline, "e4", 1.0)
        rt_equation = event_rt(timeline, "e5", 0.7)
        hold_eq = event_hold(timeline, "e5", 0.6)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Lever (horizontal rod)
            f'        lever = Line(',
            f'            np.array([{pivot_x - lever_half:.2f}, {pivot_y:.2f}, 0]),',
            f'            np.array([{pivot_x + lever_half:.2f}, {pivot_y:.2f}, 0]),',
            f'            color="{LEVER_COLOR}", stroke_width=8',
            f'        )',
            "",
            # Pivot triangle
            f'        pivot_tri = Triangle(color="{PIVOT_COLOR}", fill_opacity=0.9)',
            f'        pivot_tri.scale(0.32)',
            f'        pivot_tri.flip()',
            f'        pivot_tri.move_to(np.array([{pivot_x:.2f}, {pivot_y - 0.42:.2f}, 0]))',
            f'        pivot_dot = Dot(radius=0.1, color="{PIVOT_COLOR}")',
            f'        pivot_dot.move_to(np.array([{pivot_x:.2f}, {pivot_y:.2f}, 0]))',
            f'        pivot_grp = VGroup(pivot_tri, pivot_dot)',
            "",
            # Full lever assembly (rod + pivot) for rotation
            f'        lever_assy = VGroup(lever, pivot_dot)',
            "",
        ]

        # Force arrow (applied downward at right end of lever)
        lines += [
            f'        force_arrow = Arrow(',
            f'            np.array([{pivot_x + force_x:.2f}, {pivot_y + 0.05:.2f}, 0]),',
            f'            np.array([{pivot_x + force_x:.2f}, {pivot_y + 0.05 - force_len:.2f}, 0]),',
            f'            color="{FORCE_APPLY_COLOR}", stroke_width=6, buff=0',
            f'        )',
            f'        force_lbl = Text("{_esc(force_label)}", font_size=26, color="{FORCE_APPLY_COLOR}", weight=BOLD)',
            f'        force_lbl.next_to(force_arrow, RIGHT, buff=0.15)',
            f'        force_grp = VGroup(force_arrow, force_lbl)',
            f'        force_grp.set_opacity(0)',
            "",
            # Moment arm (dashed line from pivot to force application point)
            f'        arm_line = DashedLine(',
            f'            np.array([{pivot_x:.2f}, {pivot_y:.2f}, 0]),',
            f'            np.array([{pivot_x + force_x:.2f}, {pivot_y:.2f}, 0]),',
            f'            color="{ARM_COLOR}", stroke_width=2.5',
            f'        )',
            f'        arm_lbl = Text("{_esc(arm_label)}", font_size=22, color="{ARM_COLOR}", slant=ITALIC)',
            f'        arm_lbl.move_to(np.array([{pivot_x + force_x / 2:.2f}, {pivot_y + 0.35:.2f}, 0]))',
            f'        arm_grp = VGroup(arm_line, arm_lbl)',
            f'        arm_grp.set_opacity(0)',
            "",
            # Rotational arc (curved arrow showing torque direction)
            f'        torque_arc = Arc(',
            f'            radius=0.9,',
            f'            start_angle=0,',
            f'            angle=-PI/3,',
            f'            color="{TORQUE_ARC_COLOR}",',
            f'            stroke_width=4',
            f'        )',
            f'        torque_arc.move_arc_center_to(np.array([{pivot_x:.2f}, {pivot_y:.2f}, 0]))',
            f'        torque_arc.add_tip(tip_length=0.22, tip_color="{TORQUE_ARC_COLOR}")',
            f'        tau_lbl = Text("\u03c4", font_size=28, color="{TORQUE_ARC_COLOR}", weight=BOLD)',
            f'        tau_lbl.move_to(np.array([{pivot_x + 1.15:.2f}, {pivot_y - 0.65:.2f}, 0]))',
            f'        arc_grp = VGroup(torque_arc, tau_lbl)',
            f'        arc_grp.set_opacity(0)',
            "",
            # Equation
            f'        eq_box = RoundedRectangle(corner_radius=0.18, width=4.2, height=0.85,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        eq_text = Text("\u03c4 = r \u00d7 F", font_size=28, color="{EQ_COLOR}", weight=BOLD)',
            f'        eq_box.to_edge(DOWN, buff=0.5)',
            f'        eq_text.move_to(eq_box.get_center())',
            f'        eq_grp = VGroup(eq_box, eq_text)',
            f'        eq_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(lever, pivot_grp), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Apply force arrow
        lines += [
            f'        force_grp.set_opacity(1)',
            f'        self.play(GrowArrow(force_arrow), FadeIn(force_lbl), run_time={rt_force:.3f})',
        ]
        elapsed += rt_force
        if hold_force > 0.05:
            lines += [f'        self.wait({hold_force:.3f})  # force visible before arm shown']
            elapsed += hold_force

        # Show moment arm
        lines += [
            f'        arm_grp.set_opacity(1)',
            f'        self.play(Create(arm_line), FadeIn(arm_lbl), run_time={rt_arm:.3f})',
        ]
        elapsed += rt_arm
        if hold_arm > 0.05:
            lines += [f'        self.wait({hold_arm:.3f})']
            elapsed += hold_arm

        # Rotational arc
        lines += [
            f'        arc_grp.set_opacity(1)',
            f'        self.play(Create(torque_arc), FadeIn(torque_arc_tip, tau_lbl), run_time={rt_arc:.3f})',
        ]
        elapsed += rt_arc
        if hold_arc > 0.05:
            lines += [f'        self.wait({hold_arc:.3f})  # let viewer read torque direction']
            elapsed += hold_arc

        # Lever rotates about pivot
        lines += [
            f'        self.play(',
            f'            Rotate(lever, angle={rotate_angle:.4f}, about_point=np.array([{pivot_x:.2f}, {pivot_y:.2f}, 0])),',
            f'            FadeOut(arm_grp, arc_grp),',
            f'            run_time={rt_rotate:.3f},',
            f'            rate_func=rate_functions.ease_in_out_quad',
            f'        )',
        ]
        elapsed += rt_rotate

        # Equation
        lines += [
            f'        eq_grp.set_opacity(1)',
            f'        self.play(FadeIn(eq_box), Write(eq_text), run_time={rt_equation:.3f})',
        ]
        elapsed += rt_equation
        if hold_eq > 0.05:
            lines += [f'        self.wait({hold_eq:.3f})']
            elapsed += hold_eq

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")