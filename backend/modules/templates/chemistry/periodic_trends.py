"""Periodic Trends template.

Visual sequence:
  1. Title + simplified periodic table grid (periods 1-3 or 1-4, groups 1, 2, 13-18)
  2. Trend type label appears (atomic radius / electronegativity / ionization energy)
  3. Arrow overlay shows trend direction across period (left→right)
  4. Arrow overlay shows trend direction down group (top→bottom)
  5. Selected cells highlight to illustrate the trend
  6. Numerical value badges appear on highlighted cells
  7. Summary statement fades in at bottom
"""
from __future__ import annotations

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
    ELECTRON_COLOR,
    ENERGY_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    _aid,
    _aparams,
    _indent,
    _esc,
)

TREND_INCREASE_COLOR = "#41d4a8"   # teal – value increases
TREND_DECREASE_COLOR = "#ff7a59"   # orange – value decreases
CELL_BASE_COLOR      = "#1e2535"
CELL_HIGHLIGHT_COLOR = "#2a3d6e"
CELL_TEXT_COLOR      = "#c8d3e6"


class PeriodicTrendsTemplate:
    ALLOWED_EVENTS = {
        "place", "show_grid", "label_trend",
        "period_arrow", "group_arrow",
        "highlight_cells", "show_values",
        "summary", "hold",
    }
    SLOTS = {}  # trend type comes from plan params
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Atomic Radius Trend'>",
  "trend": "atomic_radius|electronegativity|ionization_energy|electron_affinity",
  "direction": "period|group|both",
  "period_number": <integer 1-4, optional>,
  "group_number": <integer 1-18, optional>,
  "highlight_elements": ["<symbol1>", "<symbol2>"]
}
"""

    # Simplified table: (symbol, period, group_col_index)
    # group_col_index: 0=col1(H/Li/Na/K), 1=col2, 2-7=cols 13-18
    _TABLE = [
        # Period 1
        ("H",  1, 0), ("He", 1, 7),
        # Period 2
        ("Li", 2, 0), ("Be", 2, 1),
        ("B",  2, 2), ("C",  2, 3), ("N",  2, 4),
        ("O",  2, 5), ("F",  2, 6), ("Ne", 2, 7),
        # Period 3
        ("Na", 3, 0), ("Mg", 3, 1),
        ("Al", 3, 2), ("Si", 3, 3), ("P",  3, 4),
        ("S",  3, 5), ("Cl", 3, 6), ("Ar", 3, 7),
    ]

    # Trend data: (symbol -> display_value, period_direction, group_direction, summary)
    _TREND_DATA: dict[str, dict] = {
        "electronegativity": {
            "title":   "Electronegativity",
            "unit":    "(Pauling)",
            "period_dir": "increases →",
            "group_dir":  "decreases ↓",
            "period_color": TREND_INCREASE_COLOR,
            "group_color":  TREND_DECREASE_COLOR,
            "values": {
                "H": "2.2", "Li": "1.0", "Be": "1.6",
                "B": "2.0", "C": "2.6", "N": "3.0",
                "O": "3.4", "F": "4.0", "Na": "0.9",
                "Mg": "1.3", "Al": "1.6", "Si": "1.9",
                "P": "2.2", "S": "2.6", "Cl": "3.2",
            },
            "summary": "Electronegativity increases across a period and decreases down a group.",
        },
        "atomic_radius": {
            "title":   "Atomic Radius",
            "unit":    "(pm)",
            "period_dir": "decreases →",
            "group_dir":  "increases ↓",
            "period_color": TREND_DECREASE_COLOR,
            "group_color":  TREND_INCREASE_COLOR,
            "values": {
                "H": "53", "Li": "167", "Be": "112",
                "B": "87", "C": "67", "N": "56",
                "O": "48", "F": "42", "Na": "190",
                "Mg": "145", "Al": "118", "Si": "111",
                "P": "98", "S": "88", "Cl": "79",
            },
            "summary": "Atomic radius decreases across a period and increases down a group.",
        },
        "ionization_energy": {
            "title":   "Ionization Energy",
            "unit":    "(kJ/mol)",
            "period_dir": "increases →",
            "group_dir":  "decreases ↓",
            "period_color": TREND_INCREASE_COLOR,
            "group_color":  TREND_DECREASE_COLOR,
            "values": {
                "H": "1312", "Li": "520", "Be": "900",
                "B": "801", "C": "1087", "N": "1402",
                "O": "1314", "F": "1681", "Na": "496",
                "Mg": "738", "Al": "578", "Si": "786",
                "P": "1012", "S": "1000", "Cl": "1251",
            },
            "summary": "Ionization energy increases across a period and decreases down a group.",
        },
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 14.0))
        title_text = plan.get("title", "Periodic Trends")

        trend_type = plan.get("params", {}).get("trend", "electronegativity")
        td = PeriodicTrendsTemplate._TREND_DATA.get(
            trend_type, PeriodicTrendsTemplate._TREND_DATA["electronegativity"]
        )

        _evs = plan.get("events", [])
        rt_place   = event_rt_type(timeline, _evs, "place",           "e0", 0.5)
        rt_grid    = event_rt_type(timeline, _evs, "show_grid",       "e1", 1.0)
        hold_grid  = event_hold(timeline, "e1", 0.3)
        rt_ltlbl   = event_rt_type(timeline, _evs, "label_trend",     "e2", 0.6)
        rt_parrow  = event_rt_type(timeline, _evs, "period_arrow",    "e3", 0.7)
        hold_par   = event_hold(timeline, "e3", 0.4)
        rt_garrow  = event_rt_type(timeline, _evs, "group_arrow",     "e4", 0.7)
        hold_gar   = event_hold(timeline, "e4", 0.4)
        rt_hilite  = event_rt_type(timeline, _evs, "highlight_cells", "e5", 0.8)
        rt_vals    = event_rt_type(timeline, _evs, "show_values",     "e6", 0.8)
        hold_vals  = event_hold(timeline, "e6", 0.5)
        rt_summary = event_rt_type(timeline, _evs, "summary",         "e7", 0.7)
        hold_sum   = event_hold(timeline, "e7", 0.6)

        # Grid layout constants
        cell_w = 0.72
        cell_h = 0.58
        grid_left = -3.2
        grid_top  = 1.4

        col_order = [0, 1, 2, 3, 4, 5, 6, 7]  # mapped to x offsets with gap

        def cell_xy(period: int, col_idx: int) -> tuple[float, float]:
            # Gap between col 1-2 and 13-18 group (transition metals skipped)
            gap = 1.5 if col_idx >= 2 else 0.0
            x = grid_left + (col_idx * cell_w) + gap
            y = grid_top  - ((period - 1) * cell_h)
            return x, y

        lines: list[str] = [_HEADER]

        # ── Title ──────────────────────────────────────────────────
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=36, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # ── Trend label ────────────────────────────────────────────
        lines += [
            f'        trend_lbl = Text("{_esc(td["title"])} {_esc(td["unit"])}",'
            f' font_size=24, color="{ACCENT3}", weight=BOLD)',
            f'        trend_lbl.to_edge(UP, buff=0.72)',
            f'        trend_lbl.set_opacity(0)',
            "",
        ]

        # ── Grid cells ─────────────────────────────────────────────
        table = PeriodicTrendsTemplate._TABLE
        for sym, per, col in table:
            x, y = cell_xy(per, col)
            vn = f'cell_{sym}'
            lines += [
                f'        {vn}_rect = RoundedRectangle(corner_radius=0.06,'
                f' width={cell_w-0.06:.2f}, height={cell_h-0.06:.2f},'
                f' color="{CELL_BASE_COLOR}", fill_color="{CELL_BASE_COLOR}",'
                f' fill_opacity=0.85, stroke_color="{ACCENT1}", stroke_width=0.8)',
                f'        {vn}_rect.move_to(np.array([{x:.3f}, {y:.3f}, 0]))',
                f'        {vn}_sym = Text("{sym}", font_size=14, color="{CELL_TEXT_COLOR}")',
                f'        {vn}_sym.move_to(np.array([{x:.3f}, {y:.3f}, 0]))',
                f'        {vn} = VGroup({vn}_rect, {vn}_sym)',
            ]
        lines.append("")

        all_cell_vars = " + ".join(f'cell_{sym}' for sym, _, _ in table)
        lines += [
            f'        table_grp = VGroup({", ".join(f"cell_{sym}" for sym,_,_ in table)})',
            f'        table_grp.set_opacity(0)',
            "",
        ]

        # ── Period arrow (left→right, row 2) ───────────────────────
        per2_cells = [(s, p, c) for s, p, c in table if p == 2]
        if per2_cells:
            lx, ly = cell_xy(2, per2_cells[0][2])
            rx, ry = cell_xy(2, per2_cells[-1][2])
            lines += [
                f'        period_arrow = Arrow(',
                f'            np.array([{lx - cell_w/2:.3f}, {ly - cell_h*0.9:.3f}, 0]),',
                f'            np.array([{rx + cell_w/2:.3f}, {ry - cell_h*0.9:.3f}, 0]),',
                f'            color="{td["period_color"]}", stroke_width=4, buff=0',
                f'        )',
                f'        period_dir_lbl = Text("{_esc(td["period_dir"])}",'
                f' font_size=18, color="{td["period_color"]}")',
                f'        period_dir_lbl.next_to(period_arrow, DOWN, buff=0.08)',
                f'        period_arr_grp = VGroup(period_arrow, period_dir_lbl)',
                f'        period_arr_grp.set_opacity(0)',
                "",
            ]

        # ── Group arrow (top→bottom, col 6=F/Cl) ───────────────────
        group_cells = [(s, p, c) for s, p, c in table if c == 6]
        if group_cells:
            tx, ty = cell_xy(group_cells[0][1],  group_cells[0][2])
            bx, by = cell_xy(group_cells[-1][1], group_cells[-1][2])
            lines += [
                f'        group_arrow = Arrow(',
                f'            np.array([{tx + cell_w*0.7:.3f}, {ty + cell_h/2:.3f}, 0]),',
                f'            np.array([{bx + cell_w*0.7:.3f}, {by - cell_h/2:.3f}, 0]),',
                f'            color="{td["group_color"]}", stroke_width=4, buff=0',
                f'        )',
                f'        group_dir_lbl = Text("{_esc(td["group_dir"])}",'
                f' font_size=18, color="{td["group_color"]}")',
                f'        group_dir_lbl.next_to(group_arrow, RIGHT, buff=0.08)',
                f'        group_arr_grp = VGroup(group_arrow, group_dir_lbl)',
                f'        group_arr_grp.set_opacity(0)',
                "",
            ]

        # ── Highlighted cells (period 2, group halogen col) ────────
        highlight_syms = [s for s, p, c in table if p == 2 or c == 6]
        for sym in highlight_syms:
            lines += [
                f'        cell_{sym}_rect.set_fill(color="{CELL_HIGHLIGHT_COLOR}")',
            ]
        lines.append("")

        # ── Value badges ───────────────────────────────────────────
        for sym, per, col in table:
            val = td["values"].get(sym, "")
            if not val:
                continue
            x, y = cell_xy(per, col)
            lines += [
                f'        val_{sym} = Text("{val}", font_size=11, color="{ACCENT3}")',
                f'        val_{sym}.move_to(np.array([{x:.3f}, {y - 0.13:.3f}, 0]))',
                f'        val_{sym}.set_opacity(0)',
            ]
        lines.append("")

        # ── Summary text ───────────────────────────────────────────
        lines += [
            f'        summary = Text("{_esc(td["summary"])}", font_size=19, color="{ACCENT2}")',
            f'        summary.to_edge(DOWN, buff=0.45)',
            f'        summary.set_opacity(0)',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        lines += [f'        self.play(Write(title), run_time={rt_place:.3f})']
        elapsed += rt_place

        lines += [
            f'        table_grp.set_opacity(1)',
            f'        self.play(FadeIn(table_grp), run_time={rt_grid:.3f})',
        ]
        elapsed += rt_grid
        if hold_grid > 0.05:
            lines += [f'        self.wait({hold_grid:.3f})']
            elapsed += hold_grid

        lines += [
            f'        trend_lbl.set_opacity(1)',
            f'        self.play(FadeIn(trend_lbl), run_time={rt_ltlbl:.3f})',
        ]
        elapsed += rt_ltlbl

        if per2_cells:
            lines += [
                f'        period_arr_grp.set_opacity(1)',
                f'        self.play(GrowArrow(period_arrow), FadeIn(period_dir_lbl), run_time={rt_parrow:.3f})',
            ]
            elapsed += rt_parrow
            if hold_par > 0.05:
                lines += [f'        self.wait({hold_par:.3f})']
                elapsed += hold_par

        if group_cells:
            lines += [
                f'        group_arr_grp.set_opacity(1)',
                f'        self.play(GrowArrow(group_arrow), FadeIn(group_dir_lbl), run_time={rt_garrow:.3f})',
            ]
            elapsed += rt_garrow
            if hold_gar > 0.05:
                lines += [f'        self.wait({hold_gar:.3f})']
                elapsed += hold_gar

        # Highlight cells
        highlight_anims = ", ".join(
            f'cell_{s}_rect.animate.set_fill(color="{CELL_HIGHLIGHT_COLOR}", opacity=0.95)'
            for s in highlight_syms
        )
        if highlight_anims:
            lines += [
                f'        self.play({highlight_anims}, run_time={rt_hilite:.3f})',
            ]
        elapsed += rt_hilite

        # Value badges
        val_syms = [s for s, _, _ in table if td["values"].get(s)]
        if val_syms:
            fade_anims = ", ".join(f'FadeIn(val_{s})' for s in val_syms)
            lines += [f'        self.play({fade_anims}, run_time={rt_vals:.3f})']
        elapsed += rt_vals
        if hold_vals > 0.05:
            lines += [f'        self.wait({hold_vals:.3f})']
            elapsed += hold_vals

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