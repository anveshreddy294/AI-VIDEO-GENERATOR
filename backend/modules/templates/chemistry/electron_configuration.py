"""Electron Configuration template.

Semantic tags : electron-configuration, shell-filling, 2n-squared-rule,
                K-L-M-shells, aufbau-principle, valence-electrons
Visualizable  : K L M electron shell diagram, shell capacity table,
                electron distribution per shell, valence shell highlight

Visual sequence:
  1. Title appears
  2. Shell capacity table (K=2, L=8, M=18) materialises on the left using 2n² rule
  3. Atom nucleus (symbol badge) appears at centre
  4. K shell (n=1) ring draws; electrons fill one by one (up to 2)
  5. L shell (n=2) ring draws; electrons fill one by one (up to 8)
  6. M shell (n=3) ring draws; remaining electrons fill
  7. Valence shell highlighted with glow + arrow label "valence electrons = X"
  8. Config string (e.g. "2, 8, 1") appears at bottom
  9. Group/period annotation (optional): "Group IA, Period 3"

All electron Dots are placed at evenly-spaced angles along the shell circle.
Shell rings use DashedVMobject for visual consistency with other chemistry templates.
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
    NUCLEUS_COLOR,
    NEUTRON_COLOR,
    ELECTRON_COLOR,
    SHELL_COLOR,
    event_rt_type,
    event_hold,
    _esc,
)

SHELL_NAMES     = {1: "K", 2: "L", 3: "M", 4: "N"}
SHELL_CAPACITY  = {1: 2, 2: 8, 3: 18, 4: 32}   # 2n²
VALENCE_GLO_CLR = "#f7c948"   # gold glow for valence shell
CAPACITY_CLR    = "#4f8ef7"   # blue for capacity numbers in table
TABLE_CLR       = "#2a3550"   # table background


class ElectronConfigurationTemplate:
    ALLOWED_EVENTS = {
        "place", "shell_table", "draw_nucleus",
        "fill_k", "fill_l", "fill_m", "fill_n",
        "highlight_valence", "show_config",
        "group_period", "hold",
    }
    SLOTS = {
        "atom": ["hydrogen", "helium", "carbon", "nitrogen",
                 "oxygen", "sodium", "magnesium", "chlorine",
                 "calcium", "generic"],
    }
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Electron Configuration of Sodium'>",
  "atom": "hydrogen|helium|carbon|nitrogen|oxygen|sodium|magnesium|chlorine|calcium|generic",
  "symbol": "<element symbol, e.g. 'Na'>",
  "atomic_number": <integer>,
  "shells": [<electrons per shell, e.g. 2, 8, 1>],
  "config_string": "<display string, e.g. '2, 8, 1'>",
  "show_group_period": true,
  "group_label": "<e.g. 'Group IA'>",
  "period_label": "<e.g. 'Period 3'>",
  "show_2n_rule": true
}
shells must sum to atomic_number. Maximum 4 shells supported.
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur   = float(timeline.get("audio_duration", 20.0))
        title_text  = plan.get("title", "Electron Configuration")

        content = plan.get("content") or {}
        if not isinstance(content, dict):
            content = {}
        params  = plan.get("params", {})

        def _get(key, default):
            return content.get(key) or params.get(key, default)

        symbol      = _get("symbol", "Na")
        atomic_z    = int(_get("atomic_number", 11))
        shells_raw  = _get("shells", None)
        config_str  = _get("config_string", "")
        show_gp     = _get("show_group_period", False)
        group_lbl   = _get("group_label", "")
        period_lbl  = _get("period_label", "")
        show_2n     = _get("show_2n_rule", True)

        # Derive shell filling from atomic number if not provided
        if shells_raw is None or not isinstance(shells_raw, list):
            remaining = atomic_z
            capacities = [2, 8, 18, 32]
            shells_raw = []
            for cap in capacities:
                placed = min(remaining, cap)
                shells_raw.append(placed)
                remaining -= placed
                if remaining <= 0:
                    break

        shells = [int(x) for x in shells_raw]
        n_shells = min(len(shells), 4)

        # Auto-generate config string if not given
        if not config_str:
            config_str = ", ".join(str(x) for x in shells)

        # Valence count
        valence_count = shells[-1] if shells else 0

        # Atom layout
        cx, cy    = 0.5, 0.0
        nuc_r     = 0.30
        shell_gap = 0.75
        shell_radii = [nuc_r + shell_gap * (i + 1) for i in range(n_shells)]

        # Table layout
        table_x = -3.8
        table_y_start = 1.0

        _evs = plan.get("events", [])
        rt_place    = event_rt_type(timeline, _evs, "place",            "e0", 0.60)
        rt_table    = event_rt_type(timeline, _evs, "shell_table",      "e1", 0.80)
        hold_table  = event_hold(timeline, "e1", 0.35)
        rt_nuc      = event_rt_type(timeline, _evs, "draw_nucleus",     "e2", 0.65)
        hold_nuc    = event_hold(timeline, "e2", 0.25)
        rt_k        = event_rt_type(timeline, _evs, "fill_k",           "e3", 0.90)
        hold_k      = event_hold(timeline, "e3", 0.30)
        rt_l        = event_rt_type(timeline, _evs, "fill_l",           "e4", 1.10)
        hold_l      = event_hold(timeline, "e4", 0.30)
        rt_m        = event_rt_type(timeline, _evs, "fill_m",           "e5", 1.10)
        hold_m      = event_hold(timeline, "e5", 0.30)
        rt_n        = event_rt_type(timeline, _evs, "fill_n",           "e6", 1.10)
        rt_valence  = event_rt_type(timeline, _evs, "highlight_valence","e7", 0.70)
        hold_val    = event_hold(timeline, "e7", 0.45)
        rt_config   = event_rt_type(timeline, _evs, "show_config",      "e8", 0.60)
        hold_cfg    = event_hold(timeline, "e8", 0.45)
        rt_gp       = event_rt_type(timeline, _evs, "group_period",     "e9", 0.55)
        hold_gp     = event_hold(timeline, "e9", 0.40)

        lines: list[str] = [_HEADER]

        # ── Title ──────────────────────────────────────────────────
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=34, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.28)',
            "",
        ]

        # ── 2n² Shell Capacity Table ───────────────────────────────
        if show_2n:
            header_y = table_y_start
            lines += [
                f'        tbl_hdr = Text("Shell  n  Capacity (2n²)", font_size=17,',
                f'            color="{ACCENT2}", weight=BOLD)',
                f'        tbl_hdr.move_to(np.array([{table_x:.3f}, {header_y:.3f}, 0]))',
                f'        tbl_hdr.set_opacity(0)',
            ]
            row_spacing = 0.45
            table_row_vars = []
            for ni in range(1, n_shells + 1):
                row_y = header_y - ni * row_spacing
                shell_name = SHELL_NAMES.get(ni, f"n={ni}")
                cap = SHELL_CAPACITY.get(ni, 2 * ni * ni)
                filled = shells[ni - 1] if ni <= len(shells) else 0
                row_txt = f'{shell_name}      {ni}       {cap}   [{filled} filled]'
                rv = f'tbl_row_{ni}'
                lines += [
                    f'        {rv} = Text("{_esc(row_txt)}", font_size=15, color="{LABEL_COLOR}")',
                    f'        {rv}.move_to(np.array([{table_x:.3f}, {row_y:.3f}, 0]))',
                    f'        {rv}.set_opacity(0)',
                ]
                table_row_vars.append(rv)
            tbl_sep_y = header_y - (n_shells + 1) * row_spacing
            lines += [
                f'        tbl_rule_2n = Text("Formula: 2n²", font_size=15, color="{CAPACITY_CLR}")',
                f'        tbl_rule_2n.move_to(np.array([{table_x:.3f}, {tbl_sep_y:.3f}, 0]))',
                f'        tbl_rule_2n.set_opacity(0)',
                f'        tbl_grp = VGroup(tbl_hdr, {", ".join(table_row_vars)}, tbl_rule_2n)',
                "",
            ]

        # ── Nucleus ────────────────────────────────────────────────
        lines += [
            f'        nucleus_circle = Circle(radius={nuc_r:.3f}, color="{NUCLEUS_COLOR}",',
            f'            fill_color="{NUCLEUS_COLOR}", fill_opacity=0.30, stroke_width=2)',
            f'        nucleus_circle.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
            f'        nucleus_sym = Text("{_esc(symbol)}", font_size=24, weight=BOLD, color="{ACCENT3}")',
            f'        nucleus_sym.move_to(nucleus_circle.get_center())',
            f'        nucleus_z = Text("{atomic_z}", font_size=14, color="{LABEL_COLOR}")',
            f'        nucleus_z.next_to(nucleus_circle, UP, buff=0.06)',
            f'        nucleus_grp = VGroup(nucleus_circle, nucleus_sym, nucleus_z)',
            f'        nucleus_grp.set_opacity(0)',
            "",
        ]

        # ── Shells + electrons ─────────────────────────────────────
        shell_fill_event_ids = ["e3", "e4", "e5", "e6"]
        shell_fill_rts = [rt_k, rt_l, rt_m, rt_n]
        shell_fill_holds = [hold_k, hold_l, hold_m, 0.0]

        for si in range(n_shells):
            r = shell_radii[si]
            shell_name = SHELL_NAMES.get(si + 1, f"n={si+1}")
            lines += [
                f'        # ── Shell {si+1} ({shell_name}) ──',
                f'        orbit_{si} = DashedVMobject(',
                f'            Circle(radius={r:.4f}, color="{ACCENT1}",',
                f'                stroke_width=1.5, stroke_opacity=0.55),',
                f'            num_dashes=48',
                f'        )',
                f'        orbit_{si}.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
                f'        orbit_{si}.set_opacity(0)',
                f'        orbit_lbl_{si} = Text("{shell_name}", font_size=16, color="{LABEL_COLOR}")',
                f'        orbit_lbl_{si}.move_to(np.array([{cx:.3f}, {cy + r + 0.22:.4f}, 0]))',
                f'        orbit_lbl_{si}.set_opacity(0)',
            ]
            n_e_on_shell = shells[si] if si < len(shells) else 0
            # Cap visual dots to avoid overcrowding (M shell: show max 10 with dots + number)
            display_count = min(n_e_on_shell, 10)
            for ei in range(display_count):
                angle = 2 * math.pi * ei / max(display_count, 1)
                ex = cx + r * math.cos(angle)
                ey = cy + r * math.sin(angle)
                lines += [
                    f'        elec_{si}_{ei} = Dot(radius=0.082, color="{ELECTRON_COLOR}", fill_opacity=0.95)',
                    f'        elec_{si}_{ei}.move_to(np.array([{ex:.4f}, {ey:.4f}, 0]))',
                    f'        elec_{si}_{ei}.set_opacity(0)',
                ]
            # If M/N shell has more than 10, add a count label
            if n_e_on_shell > 10:
                lx = cx + r + 0.3
                lines += [
                    f'        elec_overflow_{si} = Text("+{n_e_on_shell - 10} more",',
                    f'            font_size=13, color="{ELECTRON_COLOR}")',
                    f'        elec_overflow_{si}.move_to(np.array([{lx:.3f}, {cy:.3f}, 0]))',
                    f'        elec_overflow_{si}.set_opacity(0)',
                ]
            lines.append("")

        # ── Valence shell highlight ────────────────────────────────
        val_si = n_shells - 1
        val_r  = shell_radii[val_si]
        lines += [
            f'        valence_glow = Circle(radius={val_r:.4f}, color="{VALENCE_GLO_CLR}",',
            f'            stroke_width=3.0, stroke_opacity=0)',
            f'        valence_glow.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
            f'        val_arrow = Arrow(',
            f'            np.array([{cx + val_r + 0.9:.3f}, {cy + 0.5:.3f}, 0]),',
            f'            np.array([{cx + val_r + 0.15:.3f}, {cy + val_r * 0.7:.3f}, 0]),',
            f'            buff=0.05, color="{VALENCE_GLO_CLR}", stroke_width=2',
            f'        )',
            f'        val_lbl = Text("valence electrons = {valence_count}",',
            f'            font_size=17, color="{VALENCE_GLO_CLR}")',
            f'        val_lbl.move_to(np.array([{cx + val_r + 1.5:.3f}, {cy + 0.65:.3f}, 0]))',
            f'        valence_highlight = VGroup(valence_glow, val_arrow, val_lbl)',
            f'        valence_highlight.set_opacity(0)',
            "",
        ]

        # ── Config string ──────────────────────────────────────────
        lines += [
            f'        config_txt = Text("Electron configuration: {_esc(config_str)}",',
            f'            font_size=21, color="{ACCENT3}")',
            f'        config_txt.to_edge(DOWN, buff=0.55)',
            f'        config_txt.set_opacity(0)',
            "",
        ]

        # ── Group/Period annotation ────────────────────────────────
        if show_gp and (group_lbl or period_lbl):
            gp_str = f"{group_lbl}  •  {period_lbl}".strip(" •")
            lines += [
                f'        gp_txt = Text("{_esc(gp_str)}", font_size=17, color="{ACCENT2}")',
                f'        gp_txt.to_edge(DOWN, buff=0.28)',
                f'        gp_txt.set_opacity(0)',
                "",
            ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        # e0: title
        lines += [f'        self.play(Write(title), run_time={rt_place:.3f})']
        elapsed += rt_place

        # e1: shell capacity table
        if show_2n:
            lines += [
                f'        tbl_grp.set_opacity(1)',
                f'        self.play(',
                f'            FadeIn(tbl_hdr),',
                *[f'            FadeIn({rv}),' for rv in table_row_vars],
                f'            FadeIn(tbl_rule_2n),',
                f'            run_time={rt_table:.3f}',
                f'        )',
            ]
            elapsed += rt_table
            if hold_table > 0.05:
                lines += [f'        self.wait({hold_table:.3f})']
                elapsed += hold_table

        # e2: nucleus
        lines += [
            f'        nucleus_grp.set_opacity(1)',
            f'        self.play(FadeIn(nucleus_grp, scale=0.5), run_time={rt_nuc:.3f})',
        ]
        elapsed += rt_nuc
        if hold_nuc > 0.05:
            lines += [f'        self.wait({hold_nuc:.3f})']
            elapsed += hold_nuc

        # e3–e6: fill each shell
        fill_event_rts = [rt_k, rt_l, rt_m, rt_n]
        fill_event_holds = [hold_k, hold_l, hold_m, 0.0]

        for si in range(n_shells):
            n_e_here = shells[si] if si < len(shells) else 0
            display_count = min(n_e_here, 10)
            fill_rt = fill_event_rts[si] if si < len(fill_event_rts) else 1.0
            fill_hold = fill_event_holds[si] if si < len(fill_event_holds) else 0.3
            rt_per_e = fill_rt / max(display_count, 1) * 0.7

            # Shell ring first
            lines += [
                f'        orbit_{si}.set_opacity(1)',
                f'        orbit_lbl_{si}.set_opacity(1)',
                f'        self.play(Create(orbit_{si}), FadeIn(orbit_lbl_{si}), run_time={fill_rt * 0.28:.3f})',
            ]
            # Then electrons one by one
            for ei in range(display_count):
                lines += [
                    f'        elec_{si}_{ei}.set_opacity(1)',
                    f'        self.play(FadeIn(elec_{si}_{ei}, scale=0.3), run_time={rt_per_e:.3f})',
                ]
            if n_e_here > 10:
                lines += [
                    f'        elec_overflow_{si}.set_opacity(1)',
                    f'        self.play(FadeIn(elec_overflow_{si}), run_time=0.3)',
                ]
            elapsed += fill_rt
            if fill_hold > 0.05:
                lines += [f'        self.wait({fill_hold:.3f})']
                elapsed += fill_hold

        # e7: valence highlight
        lines += [
            f'        valence_highlight.set_opacity(1)',
            f'        self.play(',
            f'            valence_glow.animate.set_stroke(opacity=0.85),',
            f'            GrowArrow(val_arrow),',
            f'            FadeIn(val_lbl),',
            f'            run_time={rt_valence:.3f}',
            f'        )',
        ]
        elapsed += rt_valence
        if hold_val > 0.05:
            lines += [f'        self.wait({hold_val:.3f})']
            elapsed += hold_val

        # e8: config string
        lines += [
            f'        config_txt.set_opacity(1)',
            f'        self.play(Write(config_txt), run_time={rt_config:.3f})',
        ]
        elapsed += rt_config
        if hold_cfg > 0.05:
            lines += [f'        self.wait({hold_cfg:.3f})']
            elapsed += hold_cfg

        # e9: group/period
        if show_gp and (group_lbl or period_lbl):
            lines += [
                f'        gp_txt.set_opacity(1)',
                f'        self.play(FadeIn(gp_txt), run_time={rt_gp:.3f})',
            ]
            elapsed += rt_gp
            if hold_gp > 0.05:
                lines += [f'        self.wait({hold_gp:.3f})']
                elapsed += hold_gp

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)