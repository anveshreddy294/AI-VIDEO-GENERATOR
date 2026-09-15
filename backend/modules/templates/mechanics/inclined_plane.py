"""Inclined plane template.

Visual sequence:
  1. Title + inclined plane + object on slope
  2. Weight arrow (straight down) appears
  3. Normal force arrow (perpendicular to plane) appears
  4. Component parallel to slope (sliding force) appears
  5. Optional friction force (opposing slide) appears
  6. Object begins to slide down
"""
from __future__ import annotations

import math
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
    event_hold,
    asset_instance,
)

NORMAL_COLOR = "#41d4a8"
WEIGHT_COLOR = "#ff7a59"
COMPONENT_COLOR = "#f7c948"


class InclinedPlaneTemplate:
    ALLOWED_EVENTS = {"place", "show_weight", "show_normal", "show_component", "show_friction", "slide", "hold"}
    SLOTS = {
        "object": ["block"],
        "inclined_plane": ["inclined_plane"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 10.0))
        title_text = plan.get("title", "Inclined Plane")

        obj_asset = _aid(plan, "object", "block")
        obj_var = asset_instance(plan, "object") or "obj_a"
        obj_params = _aparams(plan, "object")

        plane_var = asset_instance(plan, "inclined_plane") or "plane_a"
        plane_params = _aparams(plan, "inclined_plane")
        plane_params.setdefault("angle", 30)
        angle_deg = float(plane_params["angle"])
        angle_rad = math.radians(angle_deg)
        plane_params.setdefault("width", 4.5)
        plane_w = float(plane_params["width"])

        plane_code = get_code("inclined_plane", plane_var, plane_params)

        rt_place = event_rt(timeline, "e0", 0.7)
        rt_weight = event_rt(timeline, "e1", 0.7)
        rt_normal = event_rt(timeline, "e2", 0.7)
        rt_component = event_rt(timeline, "e3", 0.7)
        hold_forces = event_hold(timeline, "e3", 0.5)
        rt_slide = event_rt(timeline, "e4", 1.5)

        # Place plane with its base at bottom-left
        plane_origin_x = -3.5
        plane_origin_y = -2.2

        # Object sits on the slope at 40% along the base
        obj_t = 0.4
        obj_x = plane_origin_x + plane_w * obj_t * math.cos(angle_rad)
        obj_y = plane_origin_y + plane_w * obj_t * math.sin(angle_rad) + 0.5

        arrow_len = 1.4

        # Weight arrow: straight down
        weight_x = obj_x
        weight_y = obj_y

        # Normal force: perpendicular to slope (angle_rad + pi/2 from x-axis)
        normal_dx = -math.sin(angle_rad) * arrow_len
        normal_dy = math.cos(angle_rad) * arrow_len

        # Parallel component: along slope (downhill)
        comp_dx = math.cos(angle_rad) * arrow_len * math.sin(angle_rad) * -1
        comp_dy = -math.sin(angle_rad) * arrow_len * math.sin(angle_rad)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        lines += [_indent(plane_code)]
        lines += [f'        {plane_var}.move_to(np.array([{plane_origin_x:.2f}, {plane_origin_y:.2f}, 0]))']

        obj_code = get_code(obj_asset, obj_var, obj_params)
        lines += [_indent(obj_code)]
        lines += [f'        {obj_var}.move_to(np.array([{obj_x:.2f}, {obj_y:.2f}, 0]))']
        lines += [f'        {obj_var}.rotate({angle_rad:.4f})  # align with slope']

        # Force arrows
        lines += [
            f'        weight_arrow = Arrow(',
            f'            np.array([{weight_x:.2f}, {weight_y:.2f}, 0]),',
            f'            np.array([{weight_x:.2f}, {weight_y - arrow_len:.2f}, 0]),',
            f'            color="{WEIGHT_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        weight_label = Text("mg", font_size=20, color="{WEIGHT_COLOR}")',
            f'        weight_label.next_to(weight_arrow, RIGHT, buff=0.1)',
            f'        weight_grp = VGroup(weight_arrow, weight_label)',
            f'        weight_grp.set_opacity(0)',
            "",
            f'        normal_arrow = Arrow(',
            f'            np.array([{obj_x:.2f}, {obj_y:.2f}, 0]),',
            f'            np.array([{obj_x+normal_dx:.2f}, {obj_y+normal_dy:.2f}, 0]),',
            f'            color="{NORMAL_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        normal_label = Text("N", font_size=20, color="{NORMAL_COLOR}")',
            f'        normal_label.next_to(normal_arrow, LEFT, buff=0.1)',
            f'        normal_grp = VGroup(normal_arrow, normal_label)',
            f'        normal_grp.set_opacity(0)',
            "",
            f'        comp_arrow = Arrow(',
            f'            np.array([{obj_x:.2f}, {obj_y:.2f}, 0]),',
            f'            np.array([{obj_x+comp_dx:.2f}, {obj_y+comp_dy:.2f}, 0]),',
            f'            color="{COMPONENT_COLOR}", stroke_width=4, buff=0',
            f'        )',
            f'        comp_label = Text("mg sin\u03b8", font_size=18, color="{COMPONENT_COLOR}")',
            f'        comp_label.next_to(comp_arrow, DOWN, buff=0.12)',
            f'        comp_grp = VGroup(comp_arrow, comp_label)',
            f'        comp_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn({plane_var}, {obj_var}), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        lines += [
            f'        weight_grp.set_opacity(1)',
            f'        self.play(GrowArrow(weight_arrow), FadeIn(weight_label), run_time={rt_weight:.3f})',
        ]
        elapsed += rt_weight

        lines += [
            f'        normal_grp.set_opacity(1)',
            f'        self.play(GrowArrow(normal_arrow), FadeIn(normal_label), run_time={rt_normal:.3f})',
        ]
        elapsed += rt_normal

        lines += [
            f'        comp_grp.set_opacity(1)',
            f'        self.play(GrowArrow(comp_arrow), FadeIn(comp_label), run_time={rt_component:.3f})',
        ]
        elapsed += rt_component
        if hold_forces > 0.05:
            lines += [f'        self.wait({hold_forces:.3f})  # let learner see all force components']
            elapsed += hold_forces

        # Slide down slope
        slide_dx = math.cos(angle_rad) * 2.5
        slide_dy = math.sin(angle_rad) * 2.5
        lines += [
            f'        self.play(',
            f'            {obj_var}.animate.shift(RIGHT*{slide_dx:.3f}+DOWN*{slide_dy:.3f}),',
            f'            FadeOut(weight_grp, normal_grp, comp_grp),',
            f'            run_time={rt_slide:.3f}',
            f'        )',
        ]
        elapsed += rt_slide

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
