"""Reaction Energy / Enthalpy / Activation Energy template.

Visual sequence:
  1. Title + blank energy-axis (Y) and reaction-coordinate axis (X)
  2. Reactant energy level drawn + labeled (H_reactants)
  3. Activation energy hump drawn (transition state at peak)
  4. Product energy level drawn + labeled (H_products)
  5. ΔH arrow (exothermic: down; endothermic: up) with value badge
  6. Ea arrow (reactant→peak) with value badge
  7. Transition state label [‡] at peak
  8. Catalyst dashed path (optional, lower Ea hump)
  9. Summary: exo/endo label + spontaneity hint
"""
from __future__ import annotations

import math
from typing import Any

from modules.templates.chemistry._base import (
    _HEADER,
    _FOOTER,
    TITLE_COLOR,
    TEXT_COLOR,
    LABEL_COLOR,
    ACCENT1,
    ACCENT2,
    ACCENT3,
    ENERGY_COLOR,
    REACTANT_COLOR,
    PRODUCT_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    _esc,
)

TS_COLOR        = "#f7c948"    # transition state
EA_COLOR        = "#ff5c8a"    # activation energy arrow
DH_COLOR        = "#41d4a8"    # enthalpy arrow
CATALYST_COLOR  = "#7c5cbf"    # catalyst dashed path
AXIS_COLOR      = "#505878"
LEVEL_COLOR     = "#c8d3e6"


class ReactionEnergyTemplate:
    ALLOWED_EVENTS = {
        "place", "draw_axes", "reactant_level",
        "transition_state", "product_level",
        "delta_h", "activation_energy",
        "ts_label", "catalyst", "summary", "hold",
    }
    SLOTS = {}  # energy values from plan params
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Exothermic Reaction Energy Profile'>",
  "reaction_type": "exothermic|endothermic",
  "reactants_label": "<reactants label, e.g. 'Zn + CuSO₄'>",
  "products_label": "<products label, e.g. 'ZnSO₄ + Cu'>",
  "activation_energy_label": "<Ea label, e.g. 'Ea = 50 kJ/mol'>",
  "delta_h_label": "<ΔH label, e.g. 'ΔH = -218 kJ/mol'>",
  "show_catalyst": false,
  "catalyst_label": "<catalyst name if show_catalyst is true>"
}
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 14.0))
        title_text = plan.get("title", "Reaction Energy Profile")

        params = plan.get("params", {})
        react_label  = params.get("reactant_label",  "Reactants")
        prod_label   = params.get("product_label",   "Products")
        delta_h_val  = params.get("delta_h",         "-92 kJ/mol")
        ea_val       = params.get("ea",              "+184 kJ/mol")
        is_exo       = params.get("is_exothermic",   True)
        show_catalyst= params.get("show_catalyst",   False)
        ea_cat_val   = params.get("ea_catalyst",     "+120 kJ/mol")

        # Layout (all in Manim units)
        ax_x0, ax_y0 = -4.2, -2.5   # axis origin
        ax_xlen = 7.5
        ax_ylen = 5.0

        # Energy levels (in axis y-units, 0 = bottom of y-axis)
        react_y = 1.2                          # reactant energy level
        ts_y    = 3.6                          # transition-state peak
        prod_y  = (0.5 if is_exo else 2.6)    # product level (lower if exo)
        ts_x    = ax_x0 + ax_xlen * 0.45      # x-position of TS peak
        react_x = ax_x0 + ax_xlen * 0.10      # x-midpoint of reactant level
        prod_x  = ax_x0 + ax_xlen * 0.85      # x-midpoint of product level
        level_hw = 0.75                        # half-width of energy level lines

        def y_coord(ey: float) -> float:
            """Energy fraction to scene y-coordinate."""
            return ax_y0 + ey

        react_y_c = y_coord(react_y)
        ts_y_c    = y_coord(ts_y)
        prod_y_c  = y_coord(prod_y)

        _evs = plan.get("events", [])
        rt_place   = event_rt_type(timeline, _evs, "place",             "e0", 0.5)
        rt_axes    = event_rt_type(timeline, _evs, "draw_axes",         "e1", 0.8)
        hold_axes  = event_hold(timeline, "e1", 0.3)
        rt_react   = event_rt_type(timeline, _evs, "reactant_level",    "e2", 0.7)
        hold_react = event_hold(timeline, "e2", 0.3)
        rt_ts      = event_rt_type(timeline, _evs, "transition_state",  "e3", 0.9)
        hold_ts    = event_hold(timeline, "e3", 0.35)
        rt_prod    = event_rt_type(timeline, _evs, "product_level",     "e4", 0.7)
        hold_prod  = event_hold(timeline, "e4", 0.35)
        rt_dh      = event_rt_type(timeline, _evs, "delta_h",           "e5", 0.7)
        hold_dh    = event_hold(timeline, "e5", 0.4)
        rt_ea      = event_rt_type(timeline, _evs, "activation_energy", "e6", 0.7)
        hold_ea    = event_hold(timeline, "e6", 0.4)
        rt_tslbl   = event_rt_type(timeline, _evs, "ts_label",          "e7", 0.5)
        rt_cat     = event_rt_type(timeline, _evs, "catalyst",          "e8", 0.8)
        hold_cat   = event_hold(timeline, "e8", 0.4)
        rt_summary = event_rt_type(timeline, _evs, "summary",           "e9", 0.65)
        hold_sum   = event_hold(timeline, "e9", 0.5)

        lines: list[str] = [_HEADER]

        # Title
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=36, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # ── Axes ───────────────────────────────────────────────────
        lines += [
            f'        # Y-axis (Energy)',
            f'        y_axis = Arrow(',
            f'            np.array([{ax_x0:.3f}, {ax_y0:.3f}, 0]),',
            f'            np.array([{ax_x0:.3f}, {ax_y0 + ax_ylen:.3f}, 0]),',
            f'            color="{AXIS_COLOR}", stroke_width=2, buff=0',
            f'        )',
            f'        y_lbl = Text("Energy (kJ/mol)", font_size=18, color="{LABEL_COLOR}")',
            f'        y_lbl.rotate(PI/2)',
            f'        y_lbl.next_to(y_axis, LEFT, buff=0.1)',
            "",
            f'        # X-axis (Reaction coordinate)',
            f'        x_axis = Arrow(',
            f'            np.array([{ax_x0:.3f}, {ax_y0:.3f}, 0]),',
            f'            np.array([{ax_x0 + ax_xlen:.3f}, {ax_y0:.3f}, 0]),',
            f'            color="{AXIS_COLOR}", stroke_width=2, buff=0',
            f'        )',
            f'        x_lbl = Text("Reaction Coordinate", font_size=18, color="{LABEL_COLOR}")',
            f'        x_lbl.next_to(x_axis, DOWN, buff=0.1)',
            f'        axes_grp = VGroup(y_axis, y_lbl, x_axis, x_lbl)',
            f'        axes_grp.set_opacity(0)',
            "",
        ]

        # ── Energy profile path (smooth Bezier curve) ──────────────
        # Path: reactant level → hump → product level
        # Approximate with CubicBezier segments
        r_start_x = ax_x0 + ax_xlen * 0.02
        r_end_x   = react_x + level_hw
        p_start_x = prod_x  - level_hw
        p_end_x   = ax_x0 + ax_xlen * 0.98

        lines += [
            f'        # Reactant flat section',
            f'        react_flat = Line(',
            f'            np.array([{r_start_x:.3f}, {react_y_c:.3f}, 0]),',
            f'            np.array([{r_end_x:.3f}, {react_y_c:.3f}, 0]),',
            f'            color="{REACTANT_COLOR}", stroke_width=3.5',
            f'        )',
            f'        react_flat.set_opacity(0)',
            "",
            f'        # Hump: reactant rise to TS',
            f'        hump_up = CubicBezier(',
            f'            np.array([{r_end_x:.3f}, {react_y_c:.3f}, 0]),',
            f'            np.array([{r_end_x + 0.6:.3f}, {ts_y_c:.3f}, 0]),',
            f'            np.array([{ts_x - 0.6:.3f}, {ts_y_c:.3f}, 0]),',
            f'            np.array([{ts_x:.3f}, {ts_y_c:.3f}, 0]),',
            f'        )',
            f'        hump_up.set_stroke(color="{LEVEL_COLOR}", width=3)',
            f'        hump_up.set_opacity(0)',
            "",
            f'        # Hump: TS down to products',
            f'        hump_down = CubicBezier(',
            f'            np.array([{ts_x:.3f}, {ts_y_c:.3f}, 0]),',
            f'            np.array([{ts_x + 0.6:.3f}, {ts_y_c:.3f}, 0]),',
            f'            np.array([{p_start_x - 0.6:.3f}, {prod_y_c:.3f}, 0]),',
            f'            np.array([{p_start_x:.3f}, {prod_y_c:.3f}, 0]),',
            f'        )',
            f'        hump_down.set_stroke(color="{LEVEL_COLOR}", width=3)',
            f'        hump_down.set_opacity(0)',
            "",
            f'        # Product flat section',
            f'        prod_flat = Line(',
            f'            np.array([{p_start_x:.3f}, {prod_y_c:.3f}, 0]),',
            f'            np.array([{p_end_x:.3f}, {prod_y_c:.3f}, 0]),',
            f'            color="{PRODUCT_COLOR}", stroke_width=3.5',
            f'        )',
            f'        prod_flat.set_opacity(0)',
            "",
        ]

        # Reactant & product labels
        lines += [
            f'        react_lbl = Text("{_esc(react_label)}", font_size=18, color="{REACTANT_COLOR}")',
            f'        react_lbl.move_to(np.array([{react_x:.3f}, {react_y_c + 0.28:.3f}, 0]))',
            f'        react_lbl.set_opacity(0)',
            f'        prod_lbl = Text("{_esc(prod_label)}", font_size=18, color="{PRODUCT_COLOR}")',
            f'        prod_lbl.move_to(np.array([{prod_x:.3f}, {prod_y_c + 0.28:.3f}, 0]))',
            f'        prod_lbl.set_opacity(0)',
            "",
        ]

        # Transition state label [‡]
        lines += [
            f'        ts_marker = Dot(radius=0.10, color="{TS_COLOR}", fill_opacity=0.9)',
            f'        ts_marker.move_to(np.array([{ts_x:.3f}, {ts_y_c:.3f}, 0]))',
            f'        ts_text = Text("[‡]", font_size=20, weight=BOLD, color="{TS_COLOR}")',
            f'        ts_text.next_to(ts_marker, UP, buff=0.1)',
            f'        ts_grp = VGroup(ts_marker, ts_text)',
            f'        ts_grp.set_opacity(0)',
            "",
        ]

        # ΔH arrow (vertical, between react and prod levels)
        dh_x   = prod_x + level_hw + 0.4
        dh_y_s = react_y_c
        dh_y_e = prod_y_c
        lines += [
            f'        dh_arrow = DoubleArrow(',
            f'            np.array([{dh_x:.3f}, {dh_y_s:.3f}, 0]),',
            f'            np.array([{dh_x:.3f}, {dh_y_e:.3f}, 0]),',
            f'            color="{DH_COLOR}", stroke_width=3, buff=0',
            f'        )',
            f'        dh_lbl = Text("\u0394H = {_esc(delta_h_val)}", font_size=18, color="{DH_COLOR}")',
            f'        dh_lbl.next_to(dh_arrow, RIGHT, buff=0.1)',
            f'        dh_grp = VGroup(dh_arrow, dh_lbl)',
            f'        dh_grp.set_opacity(0)',
            "",
        ]

        # Ea arrow (vertical, reactant→TS)
        ea_x   = ts_x + 0.35
        ea_y_s = react_y_c
        ea_y_e = ts_y_c
        lines += [
            f'        ea_arrow = DoubleArrow(',
            f'            np.array([{ea_x:.3f}, {ea_y_s:.3f}, 0]),',
            f'            np.array([{ea_x:.3f}, {ea_y_e:.3f}, 0]),',
            f'            color="{EA_COLOR}", stroke_width=3, buff=0',
            f'        )',
            f'        ea_lbl = Text("Ea = {_esc(ea_val)}", font_size=18, color="{EA_COLOR}")',
            f'        ea_lbl.next_to(ea_arrow, RIGHT, buff=0.1)',
            f'        ea_grp = VGroup(ea_arrow, ea_lbl)',
            f'        ea_grp.set_opacity(0)',
            "",
        ]

        # Catalyst (lower hump)
        if show_catalyst:
            ts_cat_y   = y_coord(react_y + (ts_y - react_y) * 0.65)  # lower TS
            prod_y_cat = prod_y_c
            lines += [
                f'        # Catalyst dashed path (lower activation energy)',
                f'        cat_hump_up = CubicBezier(',
                f'            np.array([{r_end_x:.3f}, {react_y_c:.3f}, 0]),',
                f'            np.array([{r_end_x + 0.5:.3f}, {ts_cat_y:.3f}, 0]),',
                f'            np.array([{ts_x - 0.5:.3f}, {ts_cat_y:.3f}, 0]),',
                f'            np.array([{ts_x:.3f}, {ts_cat_y:.3f}, 0]),',
                f'        )',
                f'        cat_hump_up.set_stroke(color="{CATALYST_COLOR}", width=2,'
                f' opacity=0.75, dash_array=[0.12, 0.08])',
                f'        cat_hump_down = CubicBezier(',
                f'            np.array([{ts_x:.3f}, {ts_cat_y:.3f}, 0]),',
                f'            np.array([{ts_x + 0.5:.3f}, {ts_cat_y:.3f}, 0]),',
                f'            np.array([{p_start_x - 0.5:.3f}, {prod_y_cat:.3f}, 0]),',
                f'            np.array([{p_start_x:.3f}, {prod_y_cat:.3f}, 0]),',
                f'        )',
                f'        cat_hump_down.set_stroke(color="{CATALYST_COLOR}", width=2,'
                f' opacity=0.75, dash_array=[0.12, 0.08])',
                f'        cat_lbl = Text("+ catalyst (Ea = {_esc(ea_cat_val)})", font_size=16,'
                f' color="{CATALYST_COLOR}")',
                f'        cat_lbl.move_to(np.array([{ts_x:.3f}, {ts_cat_y + 0.28:.3f}, 0]))',
                f'        catalyst_grp = VGroup(cat_hump_up, cat_hump_down, cat_lbl)',
                f'        catalyst_grp.set_opacity(0)',
                "",
            ]

        # Summary
        exo_endo = "Exothermic" if is_exo else "Endothermic"
        summary_str = f"{exo_endo} reaction  |  \u0394H {'< 0' if is_exo else '> 0'}"
        lines += [
            f'        summary = Text("{_esc(summary_str)}", font_size=20, color="{ACCENT2}")',
            f'        summary.to_edge(DOWN, buff=0.35)',
            f'        summary.set_opacity(0)',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        lines += [f'        self.play(Write(title), run_time={rt_place:.3f})']
        elapsed += rt_place

        lines += [
            f'        axes_grp.set_opacity(1)',
            f'        self.play(Create(y_axis), Create(x_axis), FadeIn(y_lbl, x_lbl),'
            f' run_time={rt_axes:.3f})',
        ]
        elapsed += rt_axes
        if hold_axes > 0.05:
            lines += [f'        self.wait({hold_axes:.3f})']
            elapsed += hold_axes

        # Reactant level
        lines += [
            f'        react_flat.set_opacity(1)',
            f'        react_lbl.set_opacity(1)',
            f'        self.play(Create(react_flat), FadeIn(react_lbl), run_time={rt_react:.3f})',
        ]
        elapsed += rt_react
        if hold_react > 0.05:
            lines += [f'        self.wait({hold_react:.3f})']
            elapsed += hold_react

        # Transition state hump
        lines += [
            f'        hump_up.set_opacity(1)',
            f'        hump_down.set_opacity(1)',
            f'        self.play(Create(hump_up), Create(hump_down), run_time={rt_ts:.3f})',
        ]
        elapsed += rt_ts
        if hold_ts > 0.05:
            lines += [f'        self.wait({hold_ts:.3f})']
            elapsed += hold_ts

        # Product level
        lines += [
            f'        prod_flat.set_opacity(1)',
            f'        prod_lbl.set_opacity(1)',
            f'        self.play(Create(prod_flat), FadeIn(prod_lbl), run_time={rt_prod:.3f})',
        ]
        elapsed += rt_prod
        if hold_prod > 0.05:
            lines += [f'        self.wait({hold_prod:.3f})']
            elapsed += hold_prod

        # ΔH arrow
        lines += [
            f'        dh_grp.set_opacity(1)',
            f'        self.play(GrowArrow(dh_arrow), FadeIn(dh_lbl), run_time={rt_dh:.3f})',
        ]
        elapsed += rt_dh
        if hold_dh > 0.05:
            lines += [f'        self.wait({hold_dh:.3f})']
            elapsed += hold_dh

        # Ea arrow
        lines += [
            f'        ea_grp.set_opacity(1)',
            f'        self.play(GrowArrow(ea_arrow), FadeIn(ea_lbl), run_time={rt_ea:.3f})',
        ]
        elapsed += rt_ea
        if hold_ea > 0.05:
            lines += [f'        self.wait({hold_ea:.3f})']
            elapsed += hold_ea

        # TS label
        lines += [
            f'        ts_grp.set_opacity(1)',
            f'        self.play(FadeIn(ts_grp, scale=0.5), run_time={rt_tslbl:.3f})',
        ]
        elapsed += rt_tslbl

        # Catalyst
        if show_catalyst:
            lines += [
                f'        catalyst_grp.set_opacity(1)',
                f'        self.play(',
                f'            Create(cat_hump_up), Create(cat_hump_down), FadeIn(cat_lbl),',
                f'            run_time={rt_cat:.3f}',
                f'        )',
            ]
            elapsed += rt_cat
            if hold_cat > 0.05:
                lines += [f'        self.wait({hold_cat:.3f})']
                elapsed += hold_cat

        # Summary
        lines += [
            f'        summary.set_opacity(1)',
            f'        self.play(Write(summary), run_time={rt_summary:.3f})',
        ]
        elapsed += rt_summary
        if hold_sum > 0.05:
            lines += [f'        self.wait({hold_sum:.3f})']
            elapsed += hold_sum

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)