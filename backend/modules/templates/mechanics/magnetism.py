"""Magnetism template.

Visual sequence:
  1. Title + two bar magnets placed facing each other (N–S poles visible)
  2. Opposite poles (N facing S) — attraction arrows grow between them
  3. Magnets pull toward each other (approach animation)
  4. Configuration resets — same poles face each other (N–N)
  5. Repulsion arrows grow outward
  6. Magnets push apart
  7. Magnetic field lines arc between poles (optional)
  8. Label: "Like poles repel, Unlike poles attract"
"""
from __future__ import annotations

from typing import Any

from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    TEXT_COLOR,
    ACCENT1,
    ACCENT2,
    event_rt,
    event_hold,
)

NORTH_COLOR = "#ff5252"
SOUTH_COLOR = "#4f8ef7"
ATTRACT_COLOR = "#41d4a8"
REPEL_COLOR = "#ff7a59"
FIELD_COLOR = "#f7c948"
EQ_COLOR = "#c8d3e6"
MAGNET_BODY = "#8b6914"


class MagnetismTemplate:
    ALLOWED_EVENTS = {
        "place", "attract_arrows", "attract_move",
        "reset", "repel_arrows", "repel_move",
        "field_lines", "show_rule", "hold"
    }
    SLOTS = {}  # uses built-in magnet visuals

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 13.0))
        title_text = plan.get("title", "Magnetism")

        magnet_w = 1.4
        magnet_h = 0.65
        pole_w = 0.48
        gap = 1.6          # initial gap between facing pole faces
        left_cx = -(gap / 2 + magnet_w / 2)   # center x of left magnet
        right_cx = gap / 2 + magnet_w / 2      # center x of right magnet
        mag_y = 0.5
        attract_shift = 0.55
        repel_shift = 0.7

        rt_place = event_rt(timeline, "e0", 0.8)
        rt_attract = event_rt(timeline, "e1", 0.7)
        hold_attract = event_hold(timeline, "e1", 0.4)
        rt_attract_move = event_rt(timeline, "e2", 0.9)
        rt_reset = event_rt(timeline, "e3", 0.5)
        rt_repel = event_rt(timeline, "e4", 0.7)
        hold_repel = event_hold(timeline, "e4", 0.35)
        rt_repel_move = event_rt(timeline, "e5", 0.9)
        rt_field = event_rt(timeline, "e6", 0.7)
        rt_rule = event_rt(timeline, "e7", 0.7)
        hold_rule = event_hold(timeline, "e7", 0.6)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        def magnet_code(var: str, cx: float, north_on_right: bool) -> list[str]:
            """Emit code for a bar magnet: body + north pole + south pole."""
            body_color = MAGNET_BODY
            n_x = cx + (magnet_w / 2 - pole_w / 2) * (1 if north_on_right else -1)
            s_x = cx + (magnet_w / 2 - pole_w / 2) * (-1 if north_on_right else 1)
            return [
                f'        {var}_body = Rectangle(width={magnet_w:.2f}, height={magnet_h:.2f},'
                f' color="{body_color}", fill_color="{body_color}", fill_opacity=0.85)',
                f'        {var}_body.move_to(np.array([{cx:.2f}, {mag_y:.2f}, 0]))',
                f'        {var}_north = Rectangle(width={pole_w:.2f}, height={magnet_h:.2f},'
                f' color="{NORTH_COLOR}", fill_color="{NORTH_COLOR}", fill_opacity=0.9)',
                f'        {var}_north.move_to(np.array([{n_x:.2f}, {mag_y:.2f}, 0]))',
                f'        {var}_north_lbl = Text("N", font_size=20, color=WHITE, weight=BOLD)',
                f'        {var}_north_lbl.move_to({var}_north.get_center())',
                f'        {var}_south = Rectangle(width={pole_w:.2f}, height={magnet_h:.2f},'
                f' color="{SOUTH_COLOR}", fill_color="{SOUTH_COLOR}", fill_opacity=0.9)',
                f'        {var}_south.move_to(np.array([{s_x:.2f}, {mag_y:.2f}, 0]))',
                f'        {var}_south_lbl = Text("S", font_size=20, color=WHITE, weight=BOLD)',
                f'        {var}_south_lbl.move_to({var}_south.get_center())',
                f'        {var} = VGroup({var}_body, {var}_north, {var}_south,'
                f' {var}_north_lbl, {var}_south_lbl)',
            ]

        # Left magnet: N on right face (facing gap), S on left
        lines += magnet_code("mag_l", left_cx, north_on_right=True)
        lines += [""]
        # Right magnet: S on left face (facing gap), N on right  → attraction setup
        lines += magnet_code("mag_r", right_cx, north_on_right=True)
        lines += [""]

        # Attraction arrows (pointing inward between the gap)
        gap_center_x = 0.0
        lines += [
            f'        attr_arr_l = Arrow(',
            f'            np.array([{left_cx + magnet_w/2 + 0.15:.2f}, {mag_y:.2f}, 0]),',
            f'            np.array([{gap_center_x - 0.15:.2f}, {mag_y:.2f}, 0]),',
            f'            color="{ATTRACT_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        attr_arr_r = Arrow(',
            f'            np.array([{right_cx - magnet_w/2 - 0.15:.2f}, {mag_y:.2f}, 0]),',
            f'            np.array([{gap_center_x + 0.15:.2f}, {mag_y:.2f}, 0]),',
            f'            color="{ATTRACT_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        attr_lbl = Text("Attraction", font_size=22, color="{ATTRACT_COLOR}")',
            f'        attr_lbl.move_to(np.array([0, {mag_y - 1.1:.2f}, 0]))',
            f'        attr_grp = VGroup(attr_arr_l, attr_arr_r, attr_lbl)',
            f'        attr_grp.set_opacity(0)',
            "",
            # Repulsion arrows (pointing outward)
            f'        rep_arr_l = Arrow(',
            f'            np.array([{left_cx:.2f}, {mag_y:.2f}, 0]),',
            f'            np.array([{left_cx - 1.3:.2f}, {mag_y:.2f}, 0]),',
            f'            color="{REPEL_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        rep_arr_r = Arrow(',
            f'            np.array([{right_cx:.2f}, {mag_y:.2f}, 0]),',
            f'            np.array([{right_cx + 1.3:.2f}, {mag_y:.2f}, 0]),',
            f'            color="{REPEL_COLOR}", stroke_width=5, buff=0',
            f'        )',
            f'        rep_lbl = Text("Repulsion", font_size=22, color="{REPEL_COLOR}")',
            f'        rep_lbl.move_to(np.array([0, {mag_y - 1.1:.2f}, 0]))',
            f'        rep_grp = VGroup(rep_arr_l, rep_arr_r, rep_lbl)',
            f'        rep_grp.set_opacity(0)',
            "",
            # Field line arcs between poles (decorative)
            f'        field_arcs = VGroup(*[',
            f'            Arc(radius=0.3 + i*0.22, start_angle=PI*0.15, angle=PI*0.7,',
            f'                color="{FIELD_COLOR}", stroke_width=1.5, stroke_opacity=0.6)',
            f'            .move_arc_center_to(np.array([0, {mag_y:.2f}, 0]))',
            f'            for i in range(4)',
            f'        ])',
            f'        field_arcs.set_opacity(0)',
            "",
            # Rule label
            f'        rule_box = RoundedRectangle(corner_radius=0.18, width=6.8, height=0.85,',
            f'            color="{ACCENT1}", fill_opacity=0.10, stroke_width=1.5)',
            f'        rule_text = Text("Like poles repel \u2022 Unlike poles attract",',
            f'            font_size=22, color="{EQ_COLOR}", weight=BOLD)',
            f'        rule_box.to_edge(DOWN, buff=0.45)',
            f'        rule_text.move_to(rule_box.get_center())',
            f'        rule_grp = VGroup(rule_box, rule_text)',
            f'        rule_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(mag_l, mag_r), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Attraction arrows
        lines += [
            f'        attr_grp.set_opacity(1)',
            f'        self.play(',
            f'            GrowArrow(attr_arr_l), GrowArrow(attr_arr_r), FadeIn(attr_lbl),',
            f'            run_time={rt_attract:.3f}',
            f'        )',
        ]
        elapsed += rt_attract
        if hold_attract > 0.05:
            lines += [f'        self.wait({hold_attract:.3f})  # viewer reads attraction']
            elapsed += hold_attract

        # Magnets attract (move inward)
        lines += [
            f'        self.play(',
            f'            mag_l.animate.shift(RIGHT*{attract_shift:.2f}),',
            f'            mag_r.animate.shift(LEFT*{attract_shift:.2f}),',
            f'            FadeOut(attr_grp),',
            f'            run_time={rt_attract_move:.3f},',
            f'            rate_func=rate_functions.ease_in_quad',
            f'        )',
        ]
        elapsed += rt_attract_move

        # Reset positions
        lines += [
            f'        self.play(',
            f'            mag_l.animate.shift(LEFT*{attract_shift:.2f}),',
            f'            mag_r.animate.shift(RIGHT*{attract_shift:.2f}),',
            f'            run_time={rt_reset:.3f}',
            f'        )',
        ]
        elapsed += rt_reset

        # Repulsion setup: flip right magnet so N faces left (N-N configuration)
        lines += [
            f'        self.play(',
            f'            mag_r.animate.flip(axis=RIGHT),',
            f'            run_time=0.45',
            f'        )',
        ]
        elapsed += 0.45

        # Repulsion arrows
        lines += [
            f'        rep_grp.set_opacity(1)',
            f'        self.play(',
            f'            GrowArrow(rep_arr_l), GrowArrow(rep_arr_r), FadeIn(rep_lbl),',
            f'            run_time={rt_repel:.3f}',
            f'        )',
        ]
        elapsed += rt_repel
        if hold_repel > 0.05:
            lines += [f'        self.wait({hold_repel:.3f})  # viewer reads repulsion']
            elapsed += hold_repel

        # Magnets repel (move outward)
        lines += [
            f'        self.play(',
            f'            mag_l.animate.shift(LEFT*{repel_shift:.2f}),',
            f'            mag_r.animate.shift(RIGHT*{repel_shift:.2f}),',
            f'            FadeOut(rep_grp),',
            f'            run_time={rt_repel_move:.3f},',
            f'            rate_func=rate_functions.ease_out_quad',
            f'        )',
        ]
        elapsed += rt_repel_move

        # Field lines
        lines += [
            f'        field_arcs.set_opacity(1)',
            f'        self.play(Create(field_arcs), run_time={rt_field:.3f})',
        ]
        elapsed += rt_field

        # Rule
        lines += [
            f'        rule_grp.set_opacity(1)',
            f'        self.play(FadeIn(rule_box), Write(rule_text), run_time={rt_rule:.3f})',
        ]
        elapsed += rt_rule
        if hold_rule > 0.05:
            lines += [f'        self.wait({hold_rule:.3f})']
            elapsed += hold_rule

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")