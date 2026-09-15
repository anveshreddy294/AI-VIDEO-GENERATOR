"""Simple Harmonic Motion (SHM) template.

Visual sequence:
  1. Title + horizontal spring-mass system (spring on left wall, block on right)
  2. Equilibrium marker (dashed vertical line) shown at rest
  3. Block displaced right — spring stretches, restoring force arrow points left
  4. Block displaced left — spring compresses, restoring force arrow points right
  5. Block oscillates back and forth (sinusoidal motion)
  6. Sinusoidal x(t) curve traced below as the block moves
  7. Period label T = 2π√(m/k) appears
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
    event_rt,
    event_hold,
    asset_instance,
)

SPRING_COLOR = "#4fc3f7"
BLOCK_COLOR = "#f7c948"
RESTORE_COLOR = "#ff7a59"
EQUILIBRIUM_COLOR = "#909090"
WAVE_COLOR = "#41d4a8"
EQ_COLOR = "#c8d3e6"


class SimpleHarmonicMotionTemplate:
    ALLOWED_EVENTS = {
        "place", "mark_equilibrium", "displace_right",
        "displace_left", "oscillate", "trace_wave", "show_period", "hold"
    }
    SLOTS = {
        "object": ["block"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 13.0))
        title_text = plan.get("title", "Simple Harmonic Motion")

        obj_asset = _aid(plan, "object", "block")
        obj_var = asset_instance(plan, "object") or "obj_a"
        obj_params = _aparams(plan, "object")
        obj_params.setdefault("color", BLOCK_COLOR)

        wall_x = -5.0
        spring_rest_x = -1.8   # right end of spring (equilibrium block position)
        block_x = spring_rest_x
        block_y = 0.3
        displace_amt = 1.6

        rt_place = event_rt(timeline, "e0", 0.8)
        rt_equil = event_rt(timeline, "e1", 0.5)
        hold_equil = event_hold(timeline, "e1", 0.3)
        rt_disp_right = event_rt(timeline, "e2", 0.7)
        hold_right = event_hold(timeline, "e2", 0.5)
        rt_disp_left = event_rt(timeline, "e3", 0.9)
        hold_left = event_hold(timeline, "e3", 0.4)
        rt_oscillate = event_rt(timeline, "e4", 2.2)
        rt_wave = event_rt(timeline, "e5", 0.6)
        rt_period = event_rt(timeline, "e6", 0.7)
        hold_period = event_hold(timeline, "e6", 0.5)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Wall
            f'        wall = Rectangle(width=0.35, height=2.8, color="{EQUILIBRIUM_COLOR}", fill_opacity=0.6)',
            f'        wall.move_to(np.array([{wall_x:.2f}, {block_y:.2f}, 0]))',
            f'        wall_hatch = VGroup(*[',
            f'            Line(',
            f'                np.array([{wall_x + 0.175:.2f}, {block_y - 1.1 + i*0.36:.2f}, 0]),',
            f'                np.array([{wall_x + 0.52:.2f}, {block_y - 1.35 + i*0.36:.2f}, 0]),',
            f'                color="#707070", stroke_width=1.5',
            f'            ) for i in range(7)',
            f'        ])',
            "",
            # Spring (zigzag represented as a styled line)
            f'        spring = Line(',
            f'            np.array([{wall_x + 0.175:.2f}, {block_y:.2f}, 0]),',
            f'            np.array([{block_x - 0.45:.2f}, {block_y:.2f}, 0]),',
            f'            color="{SPRING_COLOR}", stroke_width=4',
            f'        )',
            f'        # Zigzag coil decoration over spring',
            f'        n_coils = 8',
            f'        spring_len = {block_x - 0.45 - (wall_x + 0.175):.3f}',
            f'        coil_pts = [',
            f'            np.array([',
            f'                {wall_x + 0.175:.2f} + spring_len * i / n_coils',
            f'                + (spring_len / n_coils / 2 if i % 2 == 0 else 0),',
            f'                {block_y:.2f} + (0.2 if i % 2 == 0 else -0.2),',
            f'                0',
            f'            ])',
            f'            for i in range(n_coils + 1)',
            f'        ]',
            f'        spring_coil = VMobject(color="{SPRING_COLOR}", stroke_width=3)',
            f'        spring_coil.set_points_as_corners(coil_pts)',
            "",
        ]

        # Block
        obj_code = get_code(obj_asset, obj_var, obj_params)
        lines += [_indent(obj_code)]
        lines += [
            f'        {obj_var}.move_to(np.array([{block_x:.2f}, {block_y:.2f}, 0]))',
            "",
        ]

        lines += [
            # Equilibrium dashed line
            f'        equil_line = DashedLine(',
            f'            np.array([{block_x:.2f}, {block_y - 1.2:.2f}, 0]),',
            f'            np.array([{block_x:.2f}, {block_y + 1.2:.2f}, 0]),',
            f'            color="{EQUILIBRIUM_COLOR}", stroke_width=2',
            f'        )',
            f'        equil_label = Text("x = 0", font_size=18, color="{EQUILIBRIUM_COLOR}")',
            f'        equil_label.next_to(equil_line, DOWN, buff=0.1)',
            f'        equil_grp = VGroup(equil_line, equil_label)',
            f'        equil_grp.set_opacity(0)',
            "",
            # Restoring force arrow (shown during displacement)
            f'        restore_arrow = Arrow(ORIGIN, LEFT*1.2, color="{RESTORE_COLOR}", stroke_width=5, buff=0)',
            f'        restore_arrow.move_to(np.array([{block_x + displace_amt + 0.7:.2f}, {block_y:.2f}, 0]))',
            f'        restore_label = Text("F = \u2212kx", font_size=20, color="{RESTORE_COLOR}")',
            f'        restore_label.next_to(restore_arrow, UP, buff=0.08)',
            f'        restore_grp = VGroup(restore_arrow, restore_label)',
            f'        restore_grp.set_opacity(0)',
            "",
            # Sine wave trace (below the system)
            f'        wave_axes_y = -2.0',
            f'        wave_func = ParametricFunction(',
            f'            lambda t: np.array([t * 1.8 - 3.5, {-2.0:.2f} + 0.5 * np.sin(2.5 * t), 0]),',
            f'            t_range=[0, 4.2], color="{WAVE_COLOR}", stroke_width=3',
            f'        )',
            f'        wave_label = Text("x(t)", font_size=18, color="{WAVE_COLOR}")',
            f'        wave_label.move_to(np.array([-4.2, -2.0, 0]))',
            f'        wave_grp = VGroup(wave_func, wave_label)',
            f'        wave_grp.set_opacity(0)',
            "",
            # Period equation box
            f'        period_box = RoundedRectangle(corner_radius=0.18, width=4.8, height=0.85,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        period_text = Text("T = 2\u03c0\u221a(m/k)", font_size=26, color="{EQ_COLOR}", weight=BOLD)',
            f'        period_box.to_edge(RIGHT, buff=0.3).shift(DOWN*0.4)',
            f'        period_text.move_to(period_box.get_center())',
            f'        period_grp = VGroup(period_box, period_text)',
            f'        period_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(wall, wall_hatch, spring_coil, {obj_var}), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Equilibrium marker
        lines += [
            f'        equil_grp.set_opacity(1)',
            f'        self.play(Create(equil_line), FadeIn(equil_label), run_time={rt_equil:.3f})',
        ]
        elapsed += rt_equil
        if hold_equil > 0.05:
            lines += [f'        self.wait({hold_equil:.3f})  # equilibrium established']
            elapsed += hold_equil

        # Displace right — show restoring force pointing left
        lines += [
            f'        restore_grp.set_opacity(1)',
            f'        self.play(',
            f'            {obj_var}.animate.shift(RIGHT*{displace_amt:.2f}),',
            f'            spring_coil.animate.stretch_to_fit_width({displace_amt + 0.3:.2f}).align_to(wall, LEFT).shift(RIGHT*0.175),',
            f'            GrowArrow(restore_arrow), FadeIn(restore_label),',
            f'            run_time={rt_disp_right:.3f}',
            f'        )',
        ]
        elapsed += rt_disp_right
        if hold_right > 0.05:
            lines += [f'        self.wait({hold_right:.3f})  # stretched spring, restoring force visible']
            elapsed += hold_right

        # Displace back past equilibrium to left (compressed spring)
        lines += [
            f'        self.play(',
            f'            {obj_var}.animate.shift(LEFT*{displace_amt * 2:.2f}),',
            f'            restore_grp.animate.shift(LEFT*{displace_amt * 2:.2f}).flip(),',
            f'            spring_coil.animate.stretch_to_fit_width(0.6).align_to(wall, LEFT).shift(RIGHT*0.175),',
            f'            run_time={rt_disp_left:.3f},',
            f'            rate_func=rate_functions.ease_in_out_sine',
            f'        )',
        ]
        elapsed += rt_disp_left
        if hold_left > 0.05:
            lines += [f'        self.wait({hold_left:.3f})  # compressed spring, restoring force reversed']
            elapsed += hold_left

        # Oscillate (return to equilibrium + one more half-cycle)
        lines += [
            f'        self.play(',
            f'            {obj_var}.animate.shift(RIGHT*{displace_amt:.2f}),',
            f'            FadeOut(restore_grp),',
            f'            spring_coil.animate.stretch_to_fit_width({displace_amt + 0.3:.2f} * 0.6).align_to(wall, LEFT).shift(RIGHT*0.175),',
            f'            run_time={rt_oscillate:.3f},',
            f'            rate_func=rate_functions.ease_in_out_sine',
            f'        )',
        ]
        elapsed += rt_oscillate

        # Sine wave trace appears
        lines += [
            f'        wave_grp.set_opacity(1)',
            f'        self.play(Create(wave_func), FadeIn(wave_label), run_time={rt_wave:.3f})',
        ]
        elapsed += rt_wave

        # Period equation
        lines += [
            f'        period_grp.set_opacity(1)',
            f'        self.play(FadeIn(period_box), Write(period_text), run_time={rt_period:.3f})',
        ]
        elapsed += rt_period
        if hold_period > 0.05:
            lines += [f'        self.wait({hold_period:.3f})']
            elapsed += hold_period

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