"""Gravitation template.

Visual sequence:
  1. Title + two masses placed in space (dark background, star field)
  2. Gravitational force arrows grow between both masses (mutual attraction)
  3. Labels appear: F = G·m₁·m₂/r²
  4. Distance label 'r' shown between centers
  5. Masses slowly accelerate toward each other (attraction demonstrated)
  6. Equation highlight fades in at bottom
"""
from __future__ import annotations

import math
from typing import Any

from modules.assets.mechanics import get_code
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
    asset_instance,
)

MASS1_COLOR = "#4f8ef7"
MASS2_COLOR = "#41d4a8"
GRAVITY_COLOR = "#ff7a59"
DISTANCE_COLOR = "#f7c948"
EQ_COLOR = "#c8d3e6"


class GravitationTemplate:
    ALLOWED_EVENTS = {
        "place", "show_forces", "label_distance",
        "show_equation", "attract", "hold"
    }
    SLOTS = {
        "mass1": ["planet", "sphere"],
        "mass2": ["planet", "sphere"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 12.0))
        title_text = plan.get("title", "Gravitation")

        m1_label = plan.get("mass1_label", "m₁")
        m2_label = plan.get("mass2_label", "m₂")
        m1_x = -2.8
        m2_x = 2.8
        obj_y = 0.0
        arrow_len = 1.2
        attract_shift = 0.8

        rt_place = event_rt(timeline, "e0", 0.8)
        rt_forces = event_rt(timeline, "e1", 0.8)
        hold_forces = event_hold(timeline, "e1", 0.4)
        rt_distance = event_rt(timeline, "e2", 0.6)
        hold_dist = event_hold(timeline, "e2", 0.3)
        rt_equation = event_rt(timeline, "e3", 0.7)
        hold_eq = event_hold(timeline, "e3", 0.5)
        rt_attract = event_rt(timeline, "e4", 1.6)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Star field — small dots scattered in background
            f'        import random',
            f'        random.seed(42)',
            f'        stars = VGroup(*[',
            f'            Dot(radius=0.025, color=WHITE, fill_opacity=random.uniform(0.2, 0.7))',
            f'            .move_to(np.array([random.uniform(-6.5, 6.5), random.uniform(-3.5, 3.5), 0]))',
            f'            for _ in range(60)',
            f'        ])',
            "",
            # Mass 1 (left)
            f'        mass1 = Circle(radius=0.55, color="{MASS1_COLOR}", fill_opacity=0.85)',
            f'        mass1.move_to(np.array([{m1_x:.2f}, {obj_y:.2f}, 0]))',
            f'        m1_label = Text("{_esc(m1_label)}", font_size=22, color=WHITE, weight=BOLD)',
            f'        m1_label.move_to(mass1.get_center())',
            f'        mass1_grp = VGroup(mass1, m1_label)',
            "",
            # Mass 2 (right)
            f'        mass2 = Circle(radius=0.42, color="{MASS2_COLOR}", fill_opacity=0.85)',
            f'        mass2.move_to(np.array([{m2_x:.2f}, {obj_y:.2f}, 0]))',
            f'        m2_label = Text("{_esc(m2_label)}", font_size=22, color=WHITE, weight=BOLD)',
            f'        m2_label.move_to(mass2.get_center())',
            f'        mass2_grp = VGroup(mass2, m2_label)',
            "",
            # Gravitational force arrows — each pointing toward the other
            f'        force1 = Arrow(',
            f'            np.array([{m1_x + 0.55:.2f}, {obj_y:.2f}, 0]),',
            f'            np.array([{m1_x + 0.55 + arrow_len:.2f}, {obj_y:.2f}, 0]),',
            f'            color="{GRAVITY_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        force1_label = Text("F", font_size=20, color="{GRAVITY_COLOR}", slant=ITALIC)',
            f'        force1_label.next_to(force1, UP, buff=0.08)',
            f'        force1_grp = VGroup(force1, force1_label)',
            f'        force1_grp.set_opacity(0)',
            "",
            f'        force2 = Arrow(',
            f'            np.array([{m2_x - 0.42:.2f}, {obj_y:.2f}, 0]),',
            f'            np.array([{m2_x - 0.42 - arrow_len:.2f}, {obj_y:.2f}, 0]),',
            f'            color="{GRAVITY_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        force2_label = Text("F", font_size=20, color="{GRAVITY_COLOR}", slant=ITALIC)',
            f'        force2_label.next_to(force2, UP, buff=0.08)',
            f'        force2_grp = VGroup(force2, force2_label)',
            f'        force2_grp.set_opacity(0)',
            "",
            # Distance brace
            f'        dist_line = DashedLine(',
            f'            np.array([{m1_x:.2f}, {obj_y - 0.9:.2f}, 0]),',
            f'            np.array([{m2_x:.2f}, {obj_y - 0.9:.2f}, 0]),',
            f'            color="{DISTANCE_COLOR}", stroke_width=2',
            f'        )',
            f'        dist_label = Text("r", font_size=22, color="{DISTANCE_COLOR}", slant=ITALIC)',
            f'        dist_label.move_to(np.array([0, {obj_y - 1.2:.2f}, 0]))',
            f'        dist_grp = VGroup(dist_line, dist_label)',
            f'        dist_grp.set_opacity(0)',
            "",
            # Equation
            f'        eq_box = RoundedRectangle(corner_radius=0.18, width=5.2, height=0.9,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        eq_text = Text("F = G \u00b7 m\u2081m\u2082 / r\u00b2", font_size=28, color="{EQ_COLOR}", weight=BOLD)',
            f'        eq_box.to_edge(DOWN, buff=0.5)',
            f'        eq_text.move_to(eq_box.get_center())',
            f'        eq_grp = VGroup(eq_box, eq_text)',
            f'        eq_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(stars, mass1_grp, mass2_grp), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Mutual force arrows
        lines += [
            f'        force1_grp.set_opacity(1)',
            f'        force2_grp.set_opacity(1)',
            f'        self.play(',
            f'            GrowArrow(force1), FadeIn(force1_label),',
            f'            GrowArrow(force2), FadeIn(force2_label),',
            f'            run_time={rt_forces:.3f}',
            f'        )',
        ]
        elapsed += rt_forces
        if hold_forces > 0.05:
            lines += [f'        self.wait({hold_forces:.3f})  # let viewer absorb mutual attraction']
            elapsed += hold_forces

        # Distance label
        lines += [
            f'        dist_grp.set_opacity(1)',
            f'        self.play(Create(dist_line), FadeIn(dist_label), run_time={rt_distance:.3f})',
        ]
        elapsed += rt_distance
        if hold_dist > 0.05:
            lines += [f'        self.wait({hold_dist:.3f})']
            elapsed += hold_dist

        # Equation reveal
        lines += [
            f'        eq_grp.set_opacity(1)',
            f'        self.play(FadeIn(eq_box), Write(eq_text), run_time={rt_equation:.3f})',
        ]
        elapsed += rt_equation
        if hold_eq > 0.05:
            lines += [f'        self.wait({hold_eq:.3f})  # pause on equation']
            elapsed += hold_eq

        # Masses attract — shift toward each other
        lines += [
            f'        self.play(',
            f'            mass1_grp.animate.shift(RIGHT*{attract_shift:.2f}),',
            f'            mass2_grp.animate.shift(LEFT*{attract_shift:.2f}),',
            f'            force1_grp.animate.shift(RIGHT*{attract_shift:.2f}),',
            f'            force2_grp.animate.shift(LEFT*{attract_shift:.2f}),',
            f'            FadeOut(dist_grp),',
            f'            run_time={rt_attract:.3f}',
            f'        )',
        ]
        elapsed += rt_attract

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)


def _aid(plan: dict, role: str, default: str) -> str:
    for a in plan.get("assets", []):
        if a["role"] == role:
            return a.get("asset_id", default)
    return default


def _aparams(plan: dict, role: str) -> dict:
    for a in plan.get("assets", []):
        if a["role"] == role:
            return dict(a.get("params", {}))
    return {}


def _indent(code: str, spaces: int = 8) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else "" for line in code.splitlines())


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")