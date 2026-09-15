"""Acceleration template.

Visual sequence:
  1. Title + ground + object at left
  2. Velocity indicator appears above object
  3. Object moves with progressively increasing step sizes (equal time intervals)
  4. Displacement markers (tick lines) appear below to show increasing gaps
  5. Acceleration label appears
"""
from __future__ import annotations

from typing import Any

from modules.assets.mechanics import get_code
from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    ACCENT1,
    ACCENT2,
    VEL_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    asset_instance,
)


class AccelerationTemplate:
    ALLOWED_EVENTS = {"place", "introduce_velocity", "accelerate", "show_labels", "hold"}
    SLOTS = {
        "object": ["block", "car", "hockey_puck"],
        "surface": ["ground"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 10.0))
        title_text = plan.get("title", "Acceleration")

        obj_asset = _aid(plan, "object", "block")
        obj_var = asset_instance(plan, "object") or "obj_a"
        obj_params = _aparams(plan, "object")

        surf_var = asset_instance(plan, "surface") or "ground_a"
        surf_params = _aparams(plan, "surface")
        surf_params.setdefault("texture", "ground")
        surf_params.setdefault("extent", 8.0)

        surf_y = -2.2
        obj_y_offset = {"block": 0.45, "car": 0.28, "hockey_puck": 0.18}
        obj_y = surf_y + obj_y_offset.get(obj_asset, 0.45)
        obj_x_start = -3.2

        _evs = plan.get("events", [])
        rt_place = event_rt_type(timeline, _evs, "place", "e0", 0.7)
        rt_vel = event_rt_type(timeline, _evs, "introduce_velocity", "e1", 0.6)
        rt_accel = event_rt_type(timeline, _evs, "accelerate", "e2", 2.4)
        rt_labels = event_rt_type(timeline, _evs, "show_labels", "e3", 0.8)
        hold_after = event_hold(timeline, "e3", 0.5)

        steps = 5
        total_dist = 5.5
        weights = [i + 1 for i in range(steps)]
        ws = sum(weights)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        surf_code = get_code("ground", surf_var, surf_params)
        lines += [_indent(surf_code)]
        lines += [f'        {surf_var}.move_to(np.array([0, {surf_y:.2f}, 0]))']

        obj_code = get_code(obj_asset, obj_var, obj_params)
        lines += [_indent(obj_code)]
        lines += [f'        {obj_var}.move_to(np.array([{obj_x_start:.2f}, {obj_y:.2f}, 0]))']

        # Velocity arrow above object
        lines += [
            f'        vel_arrow = Arrow(ORIGIN, RIGHT*0.6, color="{VEL_COLOR}", stroke_width=4, buff=0)',
            f'        vel_arrow.next_to({obj_var}, UP, buff=0.15)',
            f'        vel_arrow.set_opacity(0)',
        ]

        # Displacement tick marks (created at fixed x positions, revealed later)
        tick_positions = []
        cursor_x = obj_x_start
        for i, w in enumerate(weights):
            step_dist = total_dist * w / ws
            cursor_x += step_dist
            tick_positions.append(round(cursor_x, 3))

        for i, tx in enumerate(tick_positions):
            lines += [
                f'        tick_{i} = Line(UP*0.15, DOWN*0.15, color="{ACCENT1}", stroke_width=3)',
                f'        tick_{i}.move_to(np.array([{tx}, {surf_y:.2f}, 0]))',
                f'        tick_{i}.set_opacity(0)',
            ]

        # Acceleration label
        lines += [
            f'        accel_label = Text("Increasing displacement → Acceleration", font_size=22, color="{ACCENT2}")',
            f'        accel_label.to_edge(DOWN, buff=0.5)',
            f'        accel_label.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        # e0: place scene
        lines += [
            f'        self.play(Write(title), FadeIn({surf_var}, {obj_var}), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # e1: velocity indicator appears
        lines += [
            f'        vel_arrow.set_opacity(1)',
            f'        vel_arrow.next_to({obj_var}, UP, buff=0.15)',
            f'        self.play(GrowArrow(vel_arrow), run_time={rt_vel:.3f})',
        ]
        elapsed += rt_vel

        # e2: accelerate — progressive steps with growing velocity arrow
        for i, w in enumerate(weights):
            dist = round(total_dist * w / ws, 3)
            rt = round(rt_accel * w / ws, 3)
            new_vlen = round(0.6 + i * 0.28, 3)
            lines += [
                f'        new_vel_{i} = Arrow(ORIGIN, RIGHT*{new_vlen}, color="{VEL_COLOR}", stroke_width=4, buff=0)',
                f'        new_vel_{i}.next_to({obj_var}, UP, buff=0.15)',
                f'        new_vel_{i}.shift(RIGHT*{dist/2:.3f})',
                f'        self.play(',
                f'            {obj_var}.animate.shift(RIGHT*{dist}),',
                f'            Transform(vel_arrow, new_vel_{i}),',
                f'            FadeIn(tick_{i}),',
                f'            run_time={rt}',
                f'        )',
            ]
        elapsed += rt_accel

        # e3: show displacement label
        lines += [
            f'        accel_label.set_opacity(1)',
            f'        self.play(FadeIn(accel_label), run_time={rt_labels:.3f})',
        ]
        elapsed += rt_labels
        if hold_after > 0.05:
            lines += [f'        self.wait({hold_after:.3f})']
            elapsed += hold_after

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
