"""Friction template.

Visual sequence:
  1. Title + rough ground (hatching texture) + object
  2. Applied force arrow (right side) grows
  3. Friction arrow (left, opposing) grows — labeled 'f'
  4. Object moves slowly (friction slowing it)
  5. Net force label appears showing F_net = F - f
"""
from __future__ import annotations

from typing import Any

from modules.assets.mechanics import get_code
from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    FORCE_COLOR,
    ACCENT1,
    ACCENT2,
    event_rt,
    event_rt_type,
    event_hold,
    asset_instance,
)

FRICTION_COLOR = "#f7c948"


class FrictionTemplate:
    ALLOWED_EVENTS = {"place", "apply_force", "introduce_friction", "slow_slide", "net_force", "hold"}
    SLOTS = {
        "object": ["block", "car"],
        "surface": ["ground"],
        "applied_force": ["arrow_force"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 10.0))
        title_text = plan.get("title", "Friction")

        obj_asset = _aid(plan, "object", "block")
        obj_var = asset_instance(plan, "object") or "obj_a"
        obj_params = _aparams(plan, "object")
        obj_params.setdefault("color", "#f7c948")

        surf_var = asset_instance(plan, "surface") or "ground_a"
        surf_params = _aparams(plan, "surface")
        surf_params.setdefault("texture", "rough")
        surf_params.setdefault("extent", 7.5)

        force_var = asset_instance(plan, "applied_force") or "force_a"
        force_params = _aparams(plan, "applied_force")
        force_params.setdefault("label", "F")
        force_params.setdefault("direction", "RIGHT")
        force_params.setdefault("color", FORCE_COLOR)

        surf_y = -2.2
        obj_y_offset = {"block": 0.45, "car": 0.28}
        obj_y = surf_y + obj_y_offset.get(obj_asset, 0.45)
        obj_x = -1.2

        _evs = plan.get("events", [])
        rt_place = event_rt_type(timeline, _evs, "place", "e0", 0.7)
        rt_force = event_rt_type(timeline, _evs, "apply_force", "e1", 0.75)
        rt_friction = event_rt_type(timeline, _evs, "introduce_friction", "e2", 0.75)
        hold_balance = event_hold(timeline, "e2", 0.0)
        rt_slide = event_rt_type(timeline, _evs, "slow_slide", "e3", 1.6)
        rt_net = event_rt_type(timeline, _evs, "net_force", "e4", 0.7)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # Surface with rough texture lines
        surf_code = get_code("ground", surf_var, surf_params)
        lines += [_indent(surf_code)]
        lines += [f'        {surf_var}.move_to(np.array([0, {surf_y:.2f}, 0]))']

        # Rough texture marks (small diagonal lines below ground)
        lines += [
            f'        rough_marks = VGroup(*[',
            f'            Line(',
            f'                np.array([-3.2 + i*0.55, {surf_y - 0.05:.2f}, 0]),',
            f'                np.array([-3.2 + i*0.55 + 0.25, {surf_y - 0.28:.2f}, 0]),',
            f'                color="#c09060", stroke_width=2',
            f'            ) for i in range(13)',
            f'        ])',
        ]

        obj_code = get_code(obj_asset, obj_var, obj_params)
        lines += [_indent(obj_code)]
        lines += [f'        {obj_var}.move_to(np.array([{obj_x:.2f}, {obj_y:.2f}, 0]))']

        # Applied force arrow (right)
        force_code = get_code("arrow_force", force_var, force_params)
        lines += [_indent(force_code)]
        lines += [f'        {force_var}.next_to({obj_var}, LEFT, buff=0.15)']

        # Friction arrow (opposing, right side)
        lines += [
            f'        friction_arrow = Arrow(ORIGIN, LEFT*1.4, color="{FRICTION_COLOR}", stroke_width=5, buff=0)',
            f'        friction_label = Text("f", font_size=22, color="{FRICTION_COLOR}", slant=ITALIC)',
            f'        friction_label.next_to(friction_arrow, UP, buff=0.06)',
            f'        friction_grp = VGroup(friction_arrow, friction_label)',
            f'        friction_grp.next_to({obj_var}, RIGHT, buff=0.15)',
        ]

        # Net force label
        lines += [
            f'        net_label = Text("F_net = F \u2212 f", font_size=26, color="{ACCENT2}")',
            f'        net_label.to_edge(DOWN, buff=0.6)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn({surf_var}, rough_marks, {obj_var}), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Apply force (GrowArrow adds it to scene)
        force_label_anim = f', FadeIn({force_var}_label)' if force_params.get("label") else ''
        lines += [
            f'        {force_var}.next_to({obj_var}, LEFT, buff=0.15)',
            f'        self.play(GrowArrow({force_var}_arrow){force_label_anim}, run_time={rt_force:.3f})',
        ]
        elapsed += rt_force

        # Friction appears (GrowArrow adds it to scene)
        lines += [
            f'        friction_grp.next_to({obj_var}, RIGHT, buff=0.15)',
            f'        self.play(GrowArrow(friction_arrow), FadeIn(friction_label), run_time={rt_friction:.3f})',
        ]
        elapsed += rt_friction
        if hold_balance > 0.05:
            lines += [f'        self.wait({hold_balance:.3f})  # balanced forces momentarily']
            elapsed += hold_balance

        # Slow slide (friction wins partially)
        slide_dist = 1.6
        lines += [
            f'        self.play(',
            f'            {obj_var}.animate.shift(RIGHT*{slide_dist}),',
            f'            {force_var}.animate.shift(RIGHT*{slide_dist}),',
            f'            friction_grp.animate.shift(RIGHT*{slide_dist}),',
            f'            run_time={rt_slide:.3f}',
            f'        )',
        ]
        elapsed += rt_slide

        # Net force label
        lines += [
            f'        self.play(FadeIn(net_label), run_time={rt_net:.3f})',
        ]
        elapsed += rt_net

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
