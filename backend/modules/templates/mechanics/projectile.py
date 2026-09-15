"""Projectile motion template.

Visual sequence:
  1. Title + ground + launch point (cannon/dot)
  2. Parabolic arc drawn
  3. Velocity components shown at launch: v_x (horizontal) and v_y (vertical)
  4. Object (dot) travels along arc
  5. At apex: v_y = 0, only v_x remains
  6. Landing with impact dot
"""
from __future__ import annotations

from typing import Any

from modules.templates.mechanics._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    FORCE_COLOR,
    ACCENT1,
    ACCENT2,
    VEL_COLOR,
    event_rt,
    event_hold,
)


class ProjectileTemplate:
    ALLOWED_EVENTS = {"place", "draw_arc", "show_components", "travel", "apex", "land", "hold"}
    SLOTS = {}  # uses built-in visuals

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur = float(timeline.get("audio_duration", 10.0))
        title_text = plan.get("title", "Projectile Motion")

        rt_place = event_rt(timeline, "e0", 0.7)
        rt_arc = event_rt(timeline, "e1", 1.2)
        rt_components = event_rt(timeline, "e2", 0.8)
        hold_comp = event_hold(timeline, "e2", 0.4)
        rt_travel = event_rt(timeline, "e3", 1.8)
        rt_apex = event_rt(timeline, "e4", 0.6)
        hold_apex = event_hold(timeline, "e4", 0.5)
        rt_land = event_rt(timeline, "e5", 0.5)

        lines: list[str] = [_HEADER]

        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=38, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
            # Ground
            f'        ground = Line(LEFT*4.5, RIGHT*4.5, color="#909090", stroke_width=4)',
            f'        ground.move_to(DOWN*2.5)',
            # Launch point
            f'        launch_dot = Dot(radius=0.12, color="{ACCENT2}").move_to(np.array([-4.0, -2.5, 0]))',
            # Parabolic arc (ParametricFunction)
            f'        arc = ParametricFunction(',
            f'            lambda t: np.array([-4.0 + t*4.5, -2.5 + 4.5*t - 2.2*(t**2), 0]),',
            f'            t_range=[0, 1.9], color="{ACCENT1}", stroke_width=3',
            f'        )',
            # Projectile dot (travels along arc)
            f'        proj = Dot(radius=0.14, color="{ACCENT2}").move_to(np.array([-4.0, -2.5, 0]))',
            "",
        ]

        # Velocity components at launch
        lines += [
            f'        vx_arrow = Arrow(ORIGIN, RIGHT*1.2, color="{VEL_COLOR}", stroke_width=4, buff=0)',
            f'        vy_arrow = Arrow(ORIGIN, UP*1.5, color="{FORCE_COLOR}", stroke_width=4, buff=0)',
            f'        vx_arrow.move_to(np.array([-4.0, -2.5, 0]))',
            f'        vy_arrow.move_to(np.array([-4.0, -2.5, 0]))',
            f'        vx_label = Text("v\\u2093", font_size=18, color="{VEL_COLOR}").next_to(vx_arrow, DOWN, buff=0.1)',
            f'        vy_label = Text("v\\u1D67", font_size=18, color="{FORCE_COLOR}").next_to(vy_arrow, RIGHT, buff=0.1)',
            f'        comp_grp = VGroup(vx_arrow, vy_arrow, vx_label, vy_label)',
            f'        comp_grp.set_opacity(0)',
            "",
            # Apex indicator
            f'        apex_dot = Dot(radius=0.1, color="{ACCENT2}")',
            f'        apex_dot.move_to(np.array([-4.0 + 1.9*4.5/2, -2.5 + 4.5*(1.9/2) - 2.2*(1.9/2)**2, 0]))',
            f'        apex_label = Text("v\\u1D67 = 0", font_size=20, color="{FORCE_COLOR}")',
            f'        apex_label.next_to(apex_dot, UP, buff=0.15)',
            f'        apex_grp = VGroup(apex_dot, apex_label)',
            f'        apex_grp.set_opacity(0)',
            "",
        ]

        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(ground, launch_dot), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        lines += [f'        self.play(Create(arc), run_time={rt_arc:.3f})']
        elapsed += rt_arc

        lines += [
            f'        comp_grp.set_opacity(1)',
            f'        self.play(FadeIn(comp_grp, shift=RIGHT*0.1), run_time={rt_components:.3f})',
        ]
        elapsed += rt_components
        if hold_comp > 0.05:
            lines += [f'        self.wait({hold_comp:.3f})']
            elapsed += hold_comp

        # Projectile travels along arc
        lines += [
            f'        self.play(FadeOut(comp_grp), run_time=0.25)',
            f'        self.play(FadeIn(proj), run_time=0.20)',
            f'        self.play(',
            f'            MoveAlongPath(proj, arc),',
            f'            run_time={rt_travel:.3f}',
            f'        )',
        ]
        elapsed += 0.45 + rt_travel

        # Apex pause
        lines += [
            f'        apex_grp.set_opacity(1)',
            f'        self.play(FadeIn(apex_grp), run_time={rt_apex:.3f})',
        ]
        elapsed += rt_apex
        if hold_apex > 0.05:
            lines += [f'        self.wait({hold_apex:.3f})']
            elapsed += hold_apex

        lines += [f'        self.play(FadeOut(apex_grp), run_time={rt_land:.3f})']
        elapsed += rt_land

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
