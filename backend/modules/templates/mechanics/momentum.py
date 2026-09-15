"""Momentum template.

Visual sequence:
  1. Title + two objects side by side on ground
  2. Momentum labels appear: p = m·v for each object
  3. Velocity arrows shown (both moving toward each other or one stationary)
  4. Objects collide — brief contact flash
  5. Post-collision velocity arrows update
  6. Conservation statement: p_before = p_after
"""
from __future__ import annotations

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
    VEL_COLOR,
    event_rt,
    event_hold,
    asset_instance,
)

OBJ1_COLOR = "#4f8ef7"
OBJ2_COLOR = "#41d4a8"
MOMENTUM_COLOR = "#f7c948"
IMPACT_COLOR = "#ff7a59"
CONSERVATION_COLOR = "#e0e6f0"


class MomentumTemplate:
    ALLOWED_EVENTS = {
        "place", "show_momentum", "approach",
        "collide", "post_collision", "conservation", "hold"
    }
    SLOTS = {
        "object1": ["block", "car"],
        "object2": ["block", "car"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 12.0))
        title_text = plan.get("title", "Momentum")

        obj1_asset = _aid(plan, "object1", "block")
        obj1_var = asset_instance(plan, "object1") or "obj1_a"
        obj1_params = _aparams(plan, "object1")
        obj1_params.setdefault("color", OBJ1_COLOR)

        obj2_asset = _aid(plan, "object2", "block")
        obj2_var = asset_instance(plan, "object2") or "obj2_a"
        obj2_params = _aparams(plan, "object2")
        obj2_params.setdefault("color", OBJ2_COLOR)

        m1_label = plan.get("mass1_label", "2 kg")
        m2_label = plan.get("mass2_label", "1 kg")
        v1_label = plan.get("vel1_label", "v₁")
        v2_label = plan.get("vel2_label", "v₂")

        surf_y = -2.2
        obj1_x = -3.0
        obj2_x = 2.5
        obj_y = surf_y + 0.45
        approach_shift = 1.3   # how far obj1 moves right before collision

        rt_place = event_rt(timeline, "e0", 0.8)
        rt_momentum = event_rt(timeline, "e1", 0.75)
        hold_momentum = event_hold(timeline, "e1", 0.5)
        rt_approach = event_rt(timeline, "e2", 1.2)
        rt_collide = event_rt(timeline, "e3", 0.35)
        rt_post = event_rt(timeline, "e4", 0.8)
        hold_post = event_hold(timeline, "e4", 0.4)
        rt_conservation = event_rt(timeline, "e5", 0.7)
        hold_cons = event_hold(timeline, "e5", 0.6)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Ground surface
            f'        ground = Line(LEFT*5.5, RIGHT*5.5, color="#909090", stroke_width=4)',
            f'        ground.move_to(np.array([0, {surf_y:.2f}, 0]))',
            "",
        ]

        # Object 1 (left, moving right)
        obj1_code = get_code(obj1_asset, obj1_var, obj1_params)
        lines += [_indent(obj1_code)]
        lines += [f'        {obj1_var}.move_to(np.array([{obj1_x:.2f}, {obj_y:.2f}, 0]))']

        # Object 2 (right, stationary or moving left)
        obj2_code = get_code(obj2_asset, obj2_var, obj2_params)
        lines += [_indent(obj2_code)]
        lines += [
            f'        {obj2_var}.move_to(np.array([{obj2_x:.2f}, {obj_y:.2f}, 0]))',
            "",
        ]

        # Mass labels above each object
        lines += [
            f'        mass1_tag = Text("{_esc(m1_label)}", font_size=18, color="{OBJ1_COLOR}")',
            f'        mass1_tag.next_to({obj1_var}, UP, buff=0.12)',
            f'        mass2_tag = Text("{_esc(m2_label)}", font_size=18, color="{OBJ2_COLOR}")',
            f'        mass2_tag.next_to({obj2_var}, UP, buff=0.12)',
            "",
            # Velocity arrows
            f'        vel1_arrow = Arrow(ORIGIN, RIGHT*1.3, color="{VEL_COLOR}", stroke_width=5, buff=0)',
            f'        vel1_arrow.next_to({obj1_var}, LEFT, buff=0.12)',
            f'        vel1_lbl = Text("{_esc(v1_label)}", font_size=20, color="{VEL_COLOR}")',
            f'        vel1_lbl.next_to(vel1_arrow, UP, buff=0.06)',
            f'        vel1_grp = VGroup(vel1_arrow, vel1_lbl)',
            f'        vel1_grp.set_opacity(0)',
            "",
            f'        vel2_arrow = Arrow(ORIGIN, LEFT*0.5, color="{ACCENT2}", stroke_width=4, buff=0)',
            f'        vel2_arrow.next_to({obj2_var}, RIGHT, buff=0.12)',
            f'        vel2_lbl = Text("{_esc(v2_label)}", font_size=20, color="{ACCENT2}")',
            f'        vel2_lbl.next_to(vel2_arrow, UP, buff=0.06)',
            f'        vel2_grp = VGroup(vel2_arrow, vel2_lbl)',
            f'        vel2_grp.set_opacity(0)',
            "",
            # Momentum labels (p = m*v)
            f'        mom1_lbl = Text("p\u2081 = m\u2081v\u2081", font_size=22, color="{MOMENTUM_COLOR}")',
            f'        mom1_lbl.next_to({obj1_var}, DOWN, buff=0.25)',
            f'        mom2_lbl = Text("p\u2082 = m\u2082v\u2082", font_size=22, color="{MOMENTUM_COLOR}")',
            f'        mom2_lbl.next_to({obj2_var}, DOWN, buff=0.25)',
            f'        mom1_lbl.set_opacity(0)',
            f'        mom2_lbl.set_opacity(0)',
            "",
            # Impact flash
            f'        impact = Circle(radius=0.35, color="{IMPACT_COLOR}", fill_opacity=0.0, stroke_width=3)',
            f'        impact.move_to(np.array([{(obj1_x + approach_shift + obj2_x)/2:.2f}, {obj_y:.2f}, 0]))',
            f'        impact.set_opacity(0)',
            "",
            # Post-collision velocity arrows
            f'        post_vel1 = Arrow(ORIGIN, LEFT*0.6, color="{VEL_COLOR}", stroke_width=4, buff=0)',
            f'        post_vel1.move_to(np.array([{obj1_x + approach_shift - 1.0:.2f}, {obj_y + 0.7:.2f}, 0]))',
            f'        post_vel2 = Arrow(ORIGIN, RIGHT*1.6, color="{ACCENT2}", stroke_width=5, buff=0)',
            f'        post_vel2.move_to(np.array([{obj2_x + 0.8:.2f}, {obj_y + 0.7:.2f}, 0]))',
            f'        post_grp = VGroup(post_vel1, post_vel2)',
            f'        post_grp.set_opacity(0)',
            "",
            # Conservation box
            f'        cons_box = RoundedRectangle(corner_radius=0.18, width=5.8, height=0.85,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        cons_text = Text("p_before = p_after", font_size=28, color="{CONSERVATION_COLOR}", weight=BOLD)',
            f'        cons_box.to_edge(DOWN, buff=0.45)',
            f'        cons_text.move_to(cons_box.get_center())',
            f'        cons_grp = VGroup(cons_box, cons_text)',
            f'        cons_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(ground, {obj1_var}, {obj2_var}, mass1_tag, mass2_tag), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Momentum labels + velocity arrows
        lines += [
            f'        vel1_grp.set_opacity(1)',
            f'        vel2_grp.set_opacity(1)',
            f'        mom1_lbl.set_opacity(1)',
            f'        mom2_lbl.set_opacity(1)',
            f'        self.play(',
            f'            GrowArrow(vel1_arrow), FadeIn(vel1_lbl),',
            f'            GrowArrow(vel2_arrow), FadeIn(vel2_lbl),',
            f'            FadeIn(mom1_lbl, mom2_lbl),',
            f'            run_time={rt_momentum:.3f}',
            f'        )',
        ]
        elapsed += rt_momentum
        if hold_momentum > 0.05:
            lines += [f'        self.wait({hold_momentum:.3f})  # viewer reads momentum labels']
            elapsed += hold_momentum

        # Objects approach
        lines += [
            f'        self.play(',
            f'            {obj1_var}.animate.shift(RIGHT*{approach_shift:.2f}),',
            f'            vel1_grp.animate.shift(RIGHT*{approach_shift:.2f}),',
            f'            mom1_lbl.animate.shift(RIGHT*{approach_shift:.2f}),',
            f'            mass1_tag.animate.shift(RIGHT*{approach_shift:.2f}),',
            f'            run_time={rt_approach:.3f},',
            f'            rate_func=rate_functions.linear',
            f'        )',
        ]
        elapsed += rt_approach

        # Collision flash
        lines += [
            f'        impact.set_opacity(1)',
            f'        self.play(',
            f'            impact.animate.scale(2.5).set_opacity(0),',
            f'            FadeOut(vel1_grp, vel2_grp, mom1_lbl, mom2_lbl),',
            f'            run_time={rt_collide:.3f}',
            f'        )',
        ]
        elapsed += rt_collide

        # Post-collision arrows
        lines += [
            f'        post_grp.set_opacity(1)',
            f'        self.play(',
            f'            GrowArrow(post_vel1), GrowArrow(post_vel2),',
            f'            run_time={rt_post:.3f}',
            f'        )',
        ]
        elapsed += rt_post
        if hold_post > 0.05:
            lines += [f'        self.wait({hold_post:.3f})  # viewer observes direction changes']
            elapsed += hold_post

        # Conservation statement
        lines += [
            f'        cons_grp.set_opacity(1)',
            f'        self.play(FadeIn(cons_box), Write(cons_text), run_time={rt_conservation:.3f})',
        ]
        elapsed += rt_conservation
        if hold_cons > 0.05:
            lines += [f'        self.wait({hold_cons:.3f})']
            elapsed += hold_cons

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