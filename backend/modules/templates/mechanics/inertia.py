"""Inertia template.

Visual sequence:
  1. Title at top
  2. Surface (ground/ice) at bottom of frame
  3. Object (puck/block/car) placed on surface — STATIONARY
  4. Emphasis wait: object motionless while narration says "remains at rest"
  5. Force arrow appears from the side
  6. Impact pulse on object
  7. Object accelerates with progressively increasing displacements
"""
from __future__ import annotations

from typing import Any

from modules.assets.mechanics import get_code
from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    TEXT_COLOR,
    FORCE_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    event_hold_type,
    event_start,
    asset_param,
    asset_instance,
)


class InertiaTemplate:
    ALLOWED_EVENTS = {"place", "hold", "introduce", "impact_pulse", "accelerate"}
    SLOTS = {
        "stationary_object": ["block", "hockey_puck", "car"],
        "surface": ["ground"],
        "external_force": ["arrow_force"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 10.0))
        title_text = plan.get("title", "Inertia")

        # --- resolve asset params from plan ---
        obj_asset = _asset_id(plan, "stationary_object", "hockey_puck")
        obj_var = asset_instance(plan, "stationary_object") or "obj_a"
        obj_params = _asset_params(plan, "stationary_object")

        surf_var = asset_instance(plan, "surface") or "ground_a"
        surf_params = _asset_params(plan, "surface")
        surf_params.setdefault("texture", "ice")
        surf_params.setdefault("extent", 7.0)

        force_var = asset_instance(plan, "external_force") or "force_a"
        force_params = _asset_params(plan, "external_force")
        force_params.setdefault("label", "F")
        force_params.setdefault("direction", "RIGHT")
        force_dir = force_params["direction"].upper()
        force_dir_neg = "LEFT" if force_dir == "RIGHT" else "RIGHT"

        # --- timing (type-based lookup so order in semantic plan doesn't matter) ---
        _evs = plan.get("events", [])
        rt_place = event_rt_type(timeline, _evs, "place", "e0", 0.70)
        hold_still = max(event_hold_type(timeline, _evs, "hold", 1.20), 0.80)
        rt_introduce = event_rt_type(timeline, _evs, "introduce", "e2", 0.75)
        rt_impact = event_rt_type(timeline, _evs, "impact_pulse", "e3", 0.55)
        rt_accel = event_rt_type(timeline, _evs, "accelerate", "e4", 1.80)

        # --- object setup y-position (sits ON ground) ---
        surf_y = -2.2  # ground y
        puck_y = surf_y + 0.18  # ellipse sits on line
        obj_y_offset = {"block": 0.45, "car": 0.28, "hockey_puck": 0.18}
        obj_y = surf_y + obj_y_offset.get(obj_asset, 0.25)

        obj_x = -2.5 if force_dir == "RIGHT" else 2.5

        lines: list[str] = [_HEADER]

        # ── Title ──
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # ── Surface ──
        surf_code = get_code("ground", surf_var, surf_params)
        lines += [_indent(surf_code)]
        lines += [f'        {surf_var}.move_to(np.array([0, {surf_y:.2f}, 0]))']

        # ── Stationary object ──
        obj_code = get_code(obj_asset, obj_var, obj_params)
        lines += [_indent(obj_code)]
        lines += [f'        {obj_var}.move_to(np.array([{obj_x:.2f}, {obj_y:.2f}, 0]))']

        # ── Force arrow (defined here, added to scene later via GrowArrow) ──
        force_code = get_code("arrow_force", force_var, force_params)
        lines += [_indent(force_code)]
        lines += [f'        {force_var}.next_to({obj_var}, {force_dir_neg}, buff=0.15)']

        lines += [""]

        # ── Animation sequence ──
        elapsed = 0.0

        # e0: place title + ground + object
        lines += [
            f'        self.play(',
            f'            Write(title),',
            f'            FadeIn({surf_var}),',
            f'            FadeIn({obj_var}),',
            f'            run_time={rt_place:.3f}',
            f'        )',
        ]
        elapsed += rt_place

        # e1: hold — object motionless, stillness emphasis
        lines += [f'        self.wait({hold_still:.3f})  # stillness emphasis — object at rest']
        elapsed += hold_still

        # e2: introduce force arrow (GrowArrow adds it to scene)
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
        hold_intro = event_hold(timeline, "e2", 0.0)
        if hold_intro > 0.05:
            lines += [f'        self.wait({hold_intro:.3f})']
            elapsed += hold_intro

        # e3: impact pulse
        ht = round(rt_impact * 0.5, 3)
        lines += [
            f'        self.play({obj_var}.animate.scale(1.18), run_time={ht})',
            f'        self.play({obj_var}.animate.scale(1/1.18), run_time={ht})',
            f'        self.play(FadeOut({force_var}), run_time=0.20)',
        ]
        elapsed += rt_impact + 0.20

        # e4: accelerate — progressive displacement
        steps = 4
        total_dist = 3.8
        weights = [i + 1 for i in range(steps)]
        ws = sum(weights)
        for i, w in enumerate(weights):
            dist = round(total_dist * w / ws, 3)
            rt = round(rt_accel * w / ws, 3)
            lines += [f'        self.play({obj_var}.animate.shift({force_dir}*{dist}), run_time={rt})']
        elapsed += rt_accel

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _asset_id(plan: dict, role: str, default: str) -> str:
    for a in plan.get("assets", []):
        if a["role"] == role:
            return a.get("asset_id", default)
    return default


def _asset_params(plan: dict, role: str) -> dict:
    for a in plan.get("assets", []):
        if a["role"] == role:
            return dict(a.get("params", {}))
    return {}


def _indent(code: str, spaces: int = 8) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else "" for line in code.splitlines())


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
