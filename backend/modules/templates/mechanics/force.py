"""Force template.

Visual sequence:
  1. Title + ground + object (block/car) in center
  2. Force arrow grows from the side toward the object
  3. Object pushed in force direction (constant velocity slide)
  4. Optional second force from opposite direction → object stops
  5. Net force label appears
"""
from __future__ import annotations

from typing import Any

from modules.assets.mechanics import get_code
from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    FORCE_COLOR,
    ACCENT2,
    event_rt,
    event_rt_type,
    event_hold,
    asset_instance,
)


class ForceTemplate:
    ALLOWED_EVENTS = {"place", "introduce", "apply_force", "slide", "net_force", "hold"}
    SLOTS = {
        "object": ["block", "car", "hockey_puck"],
        "surface": ["ground"],
        "primary_force": ["arrow_force"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 10.0))
        title_text = plan.get("title", "Force")

        obj_asset = _aid(plan, "object", "block")
        obj_var = asset_instance(plan, "object") or "obj_a"
        obj_params = _aparams(plan, "object")

        surf_var = asset_instance(plan, "surface") or "ground_a"
        surf_params = _aparams(plan, "surface")
        surf_params.setdefault("texture", "ground")
        surf_params.setdefault("extent", 7.0)

        force_var = asset_instance(plan, "primary_force") or "force_a"
        force_params = _aparams(plan, "primary_force")
        force_params.setdefault("label", "F")
        force_params.setdefault("direction", "RIGHT")
        force_dir = force_params["direction"].upper()
        force_dir_neg = "LEFT" if force_dir == "RIGHT" else "RIGHT"

        surf_y = -2.2
        obj_y_offset = {"block": 0.45, "car": 0.28, "hockey_puck": 0.18}
        obj_y = surf_y + obj_y_offset.get(obj_asset, 0.45)
        obj_x = -1.0

        _evs = plan.get("events", [])
        rt_place = event_rt_type(timeline, _evs, "place", "e0", 0.7)
        rt_introduce = event_rt_type(timeline, _evs, "introduce", "e1", 0.75)
        hold_force = event_hold(timeline, "e1", 0.0)
        rt_apply = event_rt_type(timeline, _evs, "apply_force", "e2", 0.65)
        rt_slide = event_rt_type(timeline, _evs, "slide", "e3", 1.4)
        rt_label = event_rt_type(timeline, _evs, "net_force", "e4", 0.7)

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
        lines += [f'        {obj_var}.move_to(np.array([{obj_x:.2f}, {obj_y:.2f}, 0]))']

        force_code = get_code("arrow_force", force_var, force_params)
        lines += [_indent(force_code)]
        lines += [f'        {force_var}.next_to({obj_var}, {force_dir_neg}, buff=0.15)']

        # Net force label (will appear after slide)
        lines += [
            f'        net_label = Text("Net Force \u2192 Acceleration", font_size=24, color="{ACCENT2}")',
            f'        net_label.to_edge(DOWN, buff=0.6)',
            "",
        ]

        elapsed = 0.0

        # e0: place scene
        lines += [
            f'        self.play(Write(title), FadeIn({surf_var}, {obj_var}), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # e1: introduce force arrow (GrowArrow adds it to scene)
        force_label_anim = f'FadeIn({force_var}_label)' if force_params.get("label") else ''
        if force_label_anim:
            lines += [
                f'        {force_var}.next_to({obj_var}, {force_dir_neg}, buff=0.15)',
                f'        self.play(GrowArrow({force_var}_arrow), {force_label_anim}, run_time={rt_introduce:.3f})',
            ]
        else:
            lines += [
                f'        {force_var}.next_to({obj_var}, {force_dir_neg}, buff=0.15)',
                f'        self.play(GrowArrow({force_var}_arrow), run_time={rt_introduce:.3f})',
            ]
        elapsed += rt_introduce
        if hold_force > 0.05:
            lines += [f'        self.wait({hold_force:.3f})']
            elapsed += hold_force

        # e2: apply force — force arrow and object move together
        initial_push = 1.2
        lines += [
            f'        self.play(',
            f'            {force_var}.animate.shift({force_dir}*{initial_push:.2f}),',
            f'            {obj_var}.animate.shift({force_dir}*{initial_push:.2f}),',
            f'            run_time={rt_apply:.3f}',
            f'        )',
        ]
        elapsed += rt_apply

        # e3: object keeps sliding, force arrow fades (force no longer applied)
        remaining_dist = 2.5
        lines += [
            f'        self.play(',
            f'            {obj_var}.animate.shift({force_dir}*{remaining_dist:.2f}),',
            f'            FadeOut({force_var}),',
            f'            run_time={rt_slide:.3f}',
            f'        )',
        ]
        elapsed += rt_slide

        # e4: net force label
        lines += [
            f'        self.play(FadeIn(net_label), run_time={rt_label:.3f})',
        ]
        elapsed += rt_label
        hold_end = event_hold(timeline, "e4", 0.5)
        if hold_end > 0.05:
            lines += [f'        self.wait({hold_end:.3f})']
            elapsed += hold_end

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
