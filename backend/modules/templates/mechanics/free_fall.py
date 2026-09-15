"""Free fall template.

Visual sequence:
  1. Title + ground line + object positioned high above ground
  2. Gravity arrow appears below object pointing down (g = 9.8 m/s²)
  3. Velocity label (v = 0) shown at rest
  4. Object falls — velocity arrow grows as object accelerates
  5. Speed labels update at key frames (v increases)
  6. Object hits ground — impact flash
  7. Equation highlight: v = g·t, h = ½g·t²
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

GRAVITY_COLOR = "#ff7a59"
GROUND_COLOR = "#909090"
IMPACT_COLOR = "#f7c948"
EQ_COLOR = "#c8d3e6"


class FreeFallTemplate:
    ALLOWED_EVENTS = {
        "place", "show_gravity", "release",
        "fall", "impact", "show_equations", "hold"
    }
    SLOTS = {
        "object": ["block", "sphere", "ball"],
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 11.0))
        title_text = plan.get("title", "Free Fall")

        obj_asset = _aid(plan, "object", "sphere")
        obj_var = asset_instance(plan, "object") or "obj_a"
        obj_params = _aparams(plan, "object")
        obj_params.setdefault("color", ACCENT2)

        ground_y = -2.8
        obj_start_y = 2.2
        obj_x = 0.0
        fall_distance = obj_start_y - ground_y - 0.25  # stop just above ground

        rt_place = event_rt(timeline, "e0", 0.7)
        rt_gravity = event_rt(timeline, "e1", 0.65)
        hold_gravity = event_hold(timeline, "e1", 0.4)
        rt_release = event_rt(timeline, "e2", 0.3)
        rt_fall = event_rt(timeline, "e3", 1.8)
        rt_impact = event_rt(timeline, "e4", 0.5)
        rt_equations = event_rt(timeline, "e5", 0.7)
        hold_eq = event_hold(timeline, "e5", 0.6)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Ground
            f'        ground = Line(LEFT*5.5, RIGHT*5.5, color="{GROUND_COLOR}", stroke_width=4)',
            f'        ground.move_to(np.array([0, {ground_y:.2f}, 0]))',
            # Ground hatch marks
            f'        hatch = VGroup(*[',
            f'            Line(',
            f'                np.array([-4.8 + i*0.6, {ground_y:.2f}, 0]),',
            f'                np.array([-4.8 + i*0.6 + 0.25, {ground_y - 0.22:.2f}, 0]),',
            f'                color="#707070", stroke_width=1.5',
            f'            ) for i in range(17)',
            f'        ])',
            "",
            # Dashed height indicator (left side)
            f'        height_line = DashedLine(',
            f'            np.array([-1.8, {ground_y:.2f}, 0]),',
            f'            np.array([-1.8, {obj_start_y:.2f}, 0]),',
            f'            color="{ACCENT1}", stroke_width=1.5',
            f'        )',
            f'        height_label = Text("h", font_size=20, color="{ACCENT1}", slant=ITALIC)',
            f'        height_label.move_to(np.array([-2.15, (({ground_y:.2f}+{obj_start_y:.2f})/2), 0]))',
            f'        height_grp = VGroup(height_line, height_label)',
            "",
        ]

        # Object
        obj_code = get_code(obj_asset, obj_var, obj_params)
        lines += [_indent(obj_code)]
        lines += [
            f'        {obj_var}.move_to(np.array([{obj_x:.2f}, {obj_start_y:.2f}, 0]))',
            "",
        ]

        # Gravity arrow (down, starting below the object)
        lines += [
            f'        grav_arrow = Arrow(',
            f'            np.array([{obj_x:.2f}, {obj_start_y - 0.3:.2f}, 0]),',
            f'            np.array([{obj_x:.2f}, {obj_start_y - 1.2:.2f}, 0]),',
            f'            color="{GRAVITY_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        grav_label = Text("g = 9.8 m/s\u00b2", font_size=20, color="{GRAVITY_COLOR}")',
            f'        grav_label.next_to(grav_arrow, RIGHT, buff=0.15)',
            f'        grav_grp = VGroup(grav_arrow, grav_label)',
            f'        grav_grp.set_opacity(0)',
            "",
            # Velocity label (starts at v=0)
            f'        vel_label = Text("v = 0", font_size=22, color="{VEL_COLOR}")',
            f'        vel_label.next_to({obj_var}, RIGHT, buff=0.25)',
            f'        vel_label.set_opacity(0)',
            "",
            # Equations box
            f'        eq_box = RoundedRectangle(corner_radius=0.18, width=5.0, height=1.1,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        eq_line1 = Text("v = g \u00b7 t", font_size=24, color="{EQ_COLOR}")',
            f'        eq_line2 = Text("h = \u00bd g \u00b7 t\u00b2", font_size=24, color="{EQ_COLOR}")',
            f'        eq_line1.shift(UP*0.22)',
            f'        eq_line2.shift(DOWN*0.22)',
            f'        eq_content = VGroup(eq_line1, eq_line2)',
            f'        eq_box.to_edge(RIGHT, buff=0.4).shift(UP*0.3)',
            f'        eq_content.move_to(eq_box.get_center())',
            f'        eq_grp = VGroup(eq_box, eq_content)',
            f'        eq_grp.set_opacity(0)',
            "",
            # Impact flash group
            f'        impact_flash = Circle(radius=0.5, color="{IMPACT_COLOR}", fill_opacity=0.0, stroke_width=3)',
            f'        impact_flash.move_to(np.array([{obj_x:.2f}, {ground_y:.2f}, 0]))',
            f'        impact_flash.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(ground, hatch, {obj_var}, height_grp), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Show gravity force
        lines += [
            f'        grav_grp.set_opacity(1)',
            f'        self.play(GrowArrow(grav_arrow), FadeIn(grav_label), run_time={rt_gravity:.3f})',
        ]
        elapsed += rt_gravity
        if hold_gravity > 0.05:
            lines += [f'        self.wait({hold_gravity:.3f})  # viewer reads g label']
            elapsed += hold_gravity

        # Velocity label appears (v = 0 at rest)
        lines += [
            f'        vel_label.set_opacity(1)',
            f'        self.play(FadeIn(vel_label), run_time={rt_release:.3f})',
        ]
        elapsed += rt_release

        # Object falls — accelerating downward
        lines += [
            f'        self.play(',
            f'            {obj_var}.animate.shift(DOWN*{fall_distance:.3f}),',
            f'            grav_grp.animate.shift(DOWN*{fall_distance:.3f}),',
            f'            vel_label.animate.shift(DOWN*{fall_distance:.3f}),',
            f'            FadeOut(height_grp),',
            f'            run_time={rt_fall:.3f},',
            f'            rate_func=rate_functions.ease_in_quad',
            f'        )',
        ]
        elapsed += rt_fall

        # Impact flash
        lines += [
            f'        impact_flash.set_opacity(1)',
            f'        self.play(',
            f'            FadeOut({obj_var}, grav_grp, vel_label),',
            f'            impact_flash.animate.scale(2.5).set_opacity(0),',
            f'            run_time={rt_impact:.3f}',
            f'        )',
        ]
        elapsed += rt_impact

        # Equations
        lines += [
            f'        eq_grp.set_opacity(1)',
            f'        self.play(FadeIn(eq_box), Write(eq_line1), Write(eq_line2), run_time={rt_equations:.3f})',
        ]
        elapsed += rt_equations
        if hold_eq > 0.05:
            lines += [f'        self.wait({hold_eq:.3f})']
            elapsed += hold_eq

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