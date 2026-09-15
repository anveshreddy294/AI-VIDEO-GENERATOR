"""Work and Energy template.

Visual sequence:
  1. Title + ground + object (block) at rest on left
  2. Force arrow (horizontal, right) applied to block with label F
  3. Displacement arrow (dashed) grows below the block — labeled d
  4. Block moves rightward (work being done)
  5. Energy bar (KE) appears on right side, growing as block accelerates
  6. W = F·d·cosθ equation appears
  7. Work-energy theorem label: W = ΔKE
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

DISPLACEMENT_COLOR = "#f7c948"
KE_COLOR = "#41d4a8"
EQ_COLOR = "#e0e6f0"
BAR_BG_COLOR = "#1e2a3a"
BAR_FG_COLOR = "#41d4a8"


class WorkEnergyTemplate:
    ALLOWED_EVENTS = {
        "place", "apply_force", "show_displacement",
        "push", "ke_grows", "show_equation", "theorem", "hold"
    }
    SLOTS = {
        "object": ["block", "car"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 12.0))
        title_text = plan.get("title", "Work and Energy")

        obj_asset = _aid(plan, "object", "block")
        obj_var = asset_instance(plan, "object") or "obj_a"
        obj_params = _aparams(plan, "object")
        obj_params.setdefault("color", ACCENT1)

        surf_y = -2.2
        obj_y = surf_y + 0.45
        obj_start_x = -3.5
        push_dist = 4.5

        rt_place = event_rt(timeline, "e0", 0.75)
        rt_force = event_rt(timeline, "e1", 0.65)
        hold_force = event_hold(timeline, "e1", 0.3)
        rt_disp = event_rt(timeline, "e2", 0.55)
        hold_disp = event_hold(timeline, "e2", 0.3)
        rt_push = event_rt(timeline, "e3", 1.8)
        rt_ke = event_rt(timeline, "e4", 0.6)
        rt_eq = event_rt(timeline, "e5", 0.7)
        hold_eq = event_hold(timeline, "e5", 0.4)
        rt_theorem = event_rt(timeline, "e6", 0.65)
        hold_theorem = event_hold(timeline, "e6", 0.5)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Ground
            f'        ground = Line(LEFT*5.5, RIGHT*5.5, color="#909090", stroke_width=4)',
            f'        ground.move_to(np.array([0, {surf_y:.2f}, 0]))',
            "",
        ]

        # Object
        obj_code = get_code(obj_asset, obj_var, obj_params)
        lines += [_indent(obj_code)]
        lines += [
            f'        {obj_var}.move_to(np.array([{obj_start_x:.2f}, {obj_y:.2f}, 0]))',
            "",
        ]

        lines += [
            # Force arrow (horizontal, applied at left face)
            f'        force_arrow = Arrow(',
            f'            np.array([{obj_start_x - 0.9:.2f}, {obj_y:.2f}, 0]),',
            f'            np.array([{obj_start_x - 0.05:.2f}, {obj_y:.2f}, 0]),',
            f'            color="{FORCE_COLOR}", stroke_width=6, buff=0',
            f'        )',
            f'        force_lbl = Text("F", font_size=26, color="{FORCE_COLOR}", weight=BOLD)',
            f'        force_lbl.next_to(force_arrow, UP, buff=0.1)',
            f'        force_grp = VGroup(force_arrow, force_lbl)',
            f'        force_grp.set_opacity(0)',
            "",
            # Displacement arrow (below object) — use Arrow, not ArrowTip (abstract in Manim CE)
            f'        disp_arrow = Arrow(',
            f'            np.array([{obj_start_x:.2f}, {surf_y + 0.1:.2f}, 0]),',
            f'            np.array([{obj_start_x + push_dist:.2f}, {surf_y + 0.1:.2f}, 0]),',
            f'            color="{DISPLACEMENT_COLOR}", stroke_width=3, buff=0,',
            f'            max_tip_length_to_length_ratio=0.12',
            f'        )',
            f'        disp_lbl = Text("d", font_size=20, color="{DISPLACEMENT_COLOR}", slant=ITALIC)',
            f'        disp_lbl.move_to(np.array([{obj_start_x + push_dist/2:.2f}, {surf_y - 0.28:.2f}, 0]))',
            f'        disp_grp = VGroup(disp_arrow, disp_lbl)',
            f'        disp_grp.set_opacity(0)',
            "",
            # KE energy bar (right side, vertical)
            f'        ke_bar_bg = Rectangle(width=0.65, height=2.4,'
            f' color="{BAR_BG_COLOR}", fill_color="{BAR_BG_COLOR}", fill_opacity=1)',
            f'        ke_bar_bg.move_to(np.array([5.0, -0.3, 0]))',
            f'        ke_bar_fg = Rectangle(width=0.65, height=0.1,'
            f' color="{BAR_FG_COLOR}", fill_color="{BAR_FG_COLOR}", fill_opacity=0.85)',
            f'        ke_bar_fg.move_to(ke_bar_bg).align_to(ke_bar_bg, DOWN)',
            f'        ke_bar_lbl = Text("KE", font_size=18, color="{KE_COLOR}")',
            f'        ke_bar_lbl.next_to(ke_bar_bg, UP, buff=0.12)',
            f'        ke_grp = VGroup(ke_bar_bg, ke_bar_fg, ke_bar_lbl)',
            f'        ke_grp.set_opacity(0)',
            "",
            # W = F·d equation
            f'        eq_box = RoundedRectangle(corner_radius=0.18, width=4.0, height=0.85,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        eq_text = Text("W = F \u00b7 d \u00b7 cos\u03b8", font_size=26, color="{EQ_COLOR}", weight=BOLD)',
            f'        eq_box.move_to(np.array([-2.5, 1.7, 0]))',
            f'        eq_text.move_to(eq_box.get_center())',
            f'        eq_grp = VGroup(eq_box, eq_text)',
            f'        eq_grp.set_opacity(0)',
            "",
            # Work-energy theorem
            f'        theorem_box = RoundedRectangle(corner_radius=0.18, width=3.6, height=0.85,',
            f'            color="{KE_COLOR}", fill_opacity=0.10, stroke_width=1.5)',
            f'        theorem_text = Text("W = \u0394KE", font_size=26, color="{KE_COLOR}", weight=BOLD)',
            f'        theorem_box.move_to(np.array([-2.5, 0.6, 0]))',
            f'        theorem_text.move_to(theorem_box.get_center())',
            f'        theorem_grp = VGroup(theorem_box, theorem_text)',
            f'        theorem_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(ground, {obj_var}), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Force arrow
        lines += [
            f'        force_grp.set_opacity(1)',
            f'        self.play(GrowArrow(force_arrow), FadeIn(force_lbl), run_time={rt_force:.3f})',
        ]
        elapsed += rt_force
        if hold_force > 0.05:
            lines += [f'        self.wait({hold_force:.3f})']
            elapsed += hold_force

        # Displacement indicator
        lines += [
            f'        disp_grp.set_opacity(1)',
            f'        self.play(GrowArrow(disp_arrow), FadeIn(disp_lbl), run_time={rt_disp:.3f})',
        ]
        elapsed += rt_disp
        if hold_disp > 0.05:
            lines += [f'        self.wait({hold_disp:.3f})']
            elapsed += hold_disp

        # Block pushed across ground
        lines += [
            f'        ke_grp.set_opacity(1)',
            f'        self.play(',
            f'            {obj_var}.animate.shift(RIGHT*{push_dist:.2f}),',
            f'            force_grp.animate.shift(RIGHT*{push_dist:.2f}),',
            f'            ke_bar_fg.animate.stretch_to_fit_height(2.3).align_to(ke_bar_bg, DOWN),',
            f'            FadeIn(ke_bar_bg, ke_bar_lbl),',
            f'            run_time={rt_push:.3f},',
            f'            rate_func=rate_functions.linear',
            f'        )',
        ]
        elapsed += rt_push

        # KE label blink
        lines += [
            f'        self.play(FadeIn(ke_grp), run_time={rt_ke:.3f})',
        ]
        elapsed += rt_ke

        # W = F·d equation
        lines += [
            f'        eq_grp.set_opacity(1)',
            f'        eq_box.set_fill(opacity=0.10)',
            f'        self.play(FadeIn(eq_box), Write(eq_text), run_time={rt_eq:.3f})',
        ]
        elapsed += rt_eq
        if hold_eq > 0.05:
            lines += [f'        self.wait({hold_eq:.3f})']
            elapsed += hold_eq

        # Work-energy theorem
        lines += [
            f'        theorem_grp.set_opacity(1)',
            f'        theorem_box.set_fill(opacity=0.10)',
            f'        self.play(FadeIn(theorem_box), Write(theorem_text), run_time={rt_theorem:.3f})',
        ]
        elapsed += rt_theorem
        if hold_theorem > 0.05:
            lines += [f'        self.wait({hold_theorem:.3f})']
            elapsed += hold_theorem

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
