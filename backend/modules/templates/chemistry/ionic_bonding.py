"""Ionic Bonding template.

Visual sequence:
  1. Title + two neutral atoms (metal left, nonmetal right) with valence dots
  2. Electron transfer: valence electron(s) arc from metal to nonmetal
  3. Ions form: metal shrinks + positive badge, nonmetal grows + negative badge
  4. Electrostatic attraction arrow appears between ions
  5. Lattice snapshot: 2×2 grid of alternating cation/anion dots
  6. Ionic compound formula + lattice energy annotation
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
    IONIC_COLOR,
    ELECTRON_COLOR,
    ENERGY_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    element_color,
    _aid,
    _aparams,
    _indent,
    _esc,
)

CATION_COLOR  = "#ff7a59"   # positive ion
ANION_COLOR   = "#4f8ef7"   # negative ion
ATTRACT_COLOR = "#f7c948"


class IonicBondingTemplate:
    ALLOWED_EVENTS = {
        "place", "transfer", "form_ions",
        "attraction", "lattice", "show_formula", "hold",
    }
    SLOTS = {
        "metal":    ["Na", "K", "Ca", "Mg", "Li", "generic_metal"],
        "nonmetal": ["Cl", "F", "O",  "S",  "Br", "generic_nonmetal"],
    }
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Ionic Bonding in NaCl'>",
  "metal": "Na|K|Ca|Mg|Li|generic_metal",
  "nonmetal": "Cl|F|O|S|Br|generic_nonmetal",
  "formula": "<compound formula, e.g. 'NaCl'>",
  "metal_valence": <integer number of valence electrons in metal>,
  "nonmetal_valence": <integer number of valence electrons in nonmetal>,
  "show_lattice": true
}
"""

    _ATOM_DATA: dict[str, tuple[str, int, float]] = {
        # symbol, valence_electrons, radius
        "Na":             ("Na", 1, 0.32),
        "K":              ("K",  1, 0.38),
        "Ca":             ("Ca", 2, 0.36),
        "Mg":             ("Mg", 2, 0.32),
        "Li":             ("Li", 1, 0.28),
        "Cl":             ("Cl", 7, 0.38),
        "F":              ("F",  7, 0.28),
        "O":              ("O",  6, 0.30),
        "S":              ("S",  6, 0.36),
        "Br":             ("Br", 7, 0.40),
        "generic_metal":    ("M",  1, 0.32),
        "generic_nonmetal": ("X",  7, 0.34),
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 13.0))
        title_text = plan.get("title", "Ionic Bonding")

        params  = plan.get("params", {})
        metal_id    = _aid(plan, "metal",    "Na")
        nonmetal_id = _aid(plan, "nonmetal", "Cl")
        metal_params    = _aparams(plan, "metal")
        nonmetal_params = _aparams(plan, "nonmetal")

        dm = IonicBondingTemplate._ATOM_DATA.get(metal_id,    IonicBondingTemplate._ATOM_DATA["generic_metal"])
        dn = IonicBondingTemplate._ATOM_DATA.get(nonmetal_id, IonicBondingTemplate._ATOM_DATA["generic_nonmetal"])

        sym_m, val_m, rad_m = dm
        sym_n, val_n, rad_n = dn
        col_m = element_color(sym_m)
        col_n = element_color(sym_n)

        # Electrons to transfer = valence of metal (1 or 2)
        n_transfer = val_m
        formula_str = params.get("formula", f"{sym_m}{sym_n}" if n_transfer == 1
                                  else f"{sym_m}{sym_n}₂" if val_n == 6 else f"{sym_m}₂{sym_n}")

        # Positions
        mx, my = -2.0, 0.1
        nx, ny =  2.0, 0.1

        _evs = plan.get("events", [])
        rt_place    = event_rt_type(timeline, _evs, "place",       "e0", 0.7)
        rt_transfer = event_rt_type(timeline, _evs, "transfer",    "e1", 1.1)
        hold_trans  = event_hold(timeline, "e1", 0.35)
        rt_ions     = event_rt_type(timeline, _evs, "form_ions",   "e2", 0.8)
        hold_ions   = event_hold(timeline, "e2", 0.5)
        rt_attract  = event_rt_type(timeline, _evs, "attraction",  "e3", 0.7)
        hold_att    = event_hold(timeline, "e3", 0.45)
        rt_lattice  = event_rt_type(timeline, _evs, "lattice",     "e4", 1.0)
        hold_lat    = event_hold(timeline, "e4", 0.5)
        rt_formula  = event_rt_type(timeline, _evs, "show_formula","e5", 0.6)
        hold_form   = event_hold(timeline, "e5", 0.5)

        lines: list[str] = [_HEADER]

        # Title
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=36, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # ── Metal atom ─────────────────────────────────────────────
        lines += [
            f'        metal_circle = Circle(radius={rad_m:.3f}, color="{col_m}",'
            f' fill_color="{col_m}", fill_opacity=0.80, stroke_width=2)',
            f'        metal_circle.move_to(np.array([{mx:.3f}, {my:.3f}, 0]))',
            f'        metal_sym = Text("{_esc(sym_m)}", font_size=24, weight=BOLD, color="{TITLE_COLOR}")',
            f'        metal_sym.move_to(metal_circle.get_center())',
            f'        metal_grp = VGroup(metal_circle, metal_sym)',
            "",
        ]

        # Valence dots on metal (n_transfer dots on right side)
        for i in range(n_transfer):
            angle = math.pi * (0.1 + 0.3 * i)
            dx = mx + (rad_m + 0.16) * math.cos(angle)
            dy = my + (rad_m + 0.16) * math.sin(angle)
            lines += [
                f'        metal_dot_{i} = Dot(radius=0.08, color="{ELECTRON_COLOR}")',
                f'        metal_dot_{i}.move_to(np.array([{dx:.3f}, {dy:.3f}, 0]))',
            ]
        metal_dots = ", ".join(f'metal_dot_{i}' for i in range(n_transfer))
        lines += [f'        metal_dots = VGroup({metal_dots})' if n_transfer else '        metal_dots = VGroup()', ""]

        # ── Non-metal atom ─────────────────────────────────────────
        lines += [
            f'        nonmetal_circle = Circle(radius={rad_n:.3f}, color="{col_n}",'
            f' fill_color="{col_n}", fill_opacity=0.80, stroke_width=2)',
            f'        nonmetal_circle.move_to(np.array([{nx:.3f}, {ny:.3f}, 0]))',
            f'        nonmetal_sym = Text("{_esc(sym_n)}", font_size=24, weight=BOLD, color="{TITLE_COLOR}")',
            f'        nonmetal_sym.move_to(nonmetal_circle.get_center())',
            f'        nonmetal_grp = VGroup(nonmetal_circle, nonmetal_sym)',
            "",
        ]

        # Lone pair dots on nonmetal (7 - transfer spots, on left side)
        n_nm_dots = val_n
        for i in range(min(n_nm_dots, 6)):
            angle = math.pi + math.pi * 0.25 * (i - (min(n_nm_dots,6)-1)/2)
            dx = nx + (rad_n + 0.16) * math.cos(angle)
            dy = ny + (rad_n + 0.16) * math.sin(angle)
            lines += [
                f'        nm_dot_{i} = Dot(radius=0.08, color="{ELECTRON_COLOR}")',
                f'        nm_dot_{i}.move_to(np.array([{dx:.3f}, {dy:.3f}, 0]))',
            ]
        nm_dots_vars = ", ".join(f'nm_dot_{i}' for i in range(min(n_nm_dots, 6)))
        lines += [f'        nm_dots = VGroup({nm_dots_vars})' if nm_dots_vars else '        nm_dots = VGroup()', ""]

        # ── Transferred electron arcs (CubicBezier from metal to nonmetal) ──
        for i in range(n_transfer):
            ctrl_y = my + 1.5 + i * 0.4
            lines += [
                f'        transfer_path_{i} = CubicBezier(',
                f'            np.array([{mx:.3f}, {my + rad_m:.3f}, 0]),',
                f'            np.array([{mx + 0.6:.3f}, {ctrl_y:.3f}, 0]),',
                f'            np.array([{nx - 0.6:.3f}, {ctrl_y:.3f}, 0]),',
                f'            np.array([{nx:.3f}, {ny + rad_n:.3f}, 0]),',
                f'        )',
                f'        transfer_dot_{i} = Dot(radius=0.08, color="{ELECTRON_COLOR}")',
                f'        transfer_dot_{i}.move_to(np.array([{mx:.3f}, {my + rad_m:.3f}, 0]))',
            ]
        lines.append("")

        # ── Ion badges (appear after transfer) ─────────────────────
        cation_charge = f"+{n_transfer}" if n_transfer > 1 else "+"
        anion_charge  = f"-{n_transfer}" if n_transfer > 1 else "−"
        lines += [
            f'        cation_badge = Text("{_esc(cation_charge)}", font_size=22, weight=BOLD, color="{CATION_COLOR}")',
            f'        cation_badge.next_to(metal_circle, UP+RIGHT, buff=0.0)',
            f'        cation_badge.set_opacity(0)',
            f'        anion_badge = Text("{_esc(anion_charge)}", font_size=22, weight=BOLD, color="{ANION_COLOR}")',
            f'        anion_badge.next_to(nonmetal_circle, UP+RIGHT, buff=0.0)',
            f'        anion_badge.set_opacity(0)',
            "",
        ]

        # ── Attraction arrow ───────────────────────────────────────
        lines += [
            f'        attract_arrow = DoubleArrow(',
            f'            np.array([{mx + rad_m + 0.1:.3f}, {my:.3f}, 0]),',
            f'            np.array([{nx - rad_n - 0.1:.3f}, {ny:.3f}, 0]),',
            f'            color="{ATTRACT_COLOR}", stroke_width=3, buff=0',
            f'        )',
            f'        attract_lbl = Text("electrostatic attraction", font_size=18, color="{ATTRACT_COLOR}")',
            f'        attract_lbl.next_to(attract_arrow, DOWN, buff=0.1)',
            f'        attract_grp = VGroup(attract_arrow, attract_lbl)',
            f'        attract_grp.set_opacity(0)',
            "",
        ]

        # ── Lattice (2×2 grid, bottom half) ────────────────────────
        lattice_cx, lattice_cy = 0.0, -2.0
        lattice_gap = 0.52
        lattice_r   = 0.15
        lines += [f'        # Ionic lattice 2x2 (representative)']
        lattice_vars = []
        for row in range(2):
            for col in range(2):
                is_cation = (row + col) % 2 == 0
                lx = lattice_cx + (col - 0.5) * lattice_gap
                ly = lattice_cy + (row - 0.5) * lattice_gap
                col_c = CATION_COLOR if is_cation else ANION_COLOR
                sym_c = f"+{sym_m}" if is_cation else f"-{sym_n}"
                vn = f'lat_{row}_{col}'
                lines += [
                    f'        {vn}_circ = Circle(radius={lattice_r:.3f}, color="{col_c}",'
                    f' fill_color="{col_c}", fill_opacity=0.75, stroke_width=1.5)',
                    f'        {vn}_circ.move_to(np.array([{lx:.3f}, {ly:.3f}, 0]))',
                    f'        {vn}_lbl = Text("{sym_c}", font_size=10, color="{TITLE_COLOR}")',
                    f'        {vn}_lbl.move_to({vn}_circ.get_center())',
                    f'        {vn} = VGroup({vn}_circ, {vn}_lbl)',
                ]
                lattice_vars.append(vn)
        lat_grp_args = ", ".join(lattice_vars)
        lines += [
            f'        lattice_grp = VGroup({lat_grp_args})',
            f'        lattice_lbl = Text("Ionic Lattice", font_size=18, color="{LABEL_COLOR}")',
            f'        lattice_lbl.next_to(lattice_grp, DOWN, buff=0.15)',
            f'        full_lattice = VGroup(lattice_grp, lattice_lbl)',
            f'        full_lattice.set_opacity(0)',
            "",
        ]

        # ── Formula ────────────────────────────────────────────────
        lines += [
            f'        formula_text = Text("{_esc(formula_str)}", font_size=30, weight=BOLD, color="{ACCENT2}")',
            f'        formula_text.to_edge(DOWN, buff=0.3)',
            f'        formula_text.set_opacity(0)',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        lines += [f'        self.play(Write(title), run_time={rt_place:.3f})']
        elapsed += rt_place

        lines += [
            f'        self.play(FadeIn(metal_grp, metal_dots, nonmetal_grp, nm_dots), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Transfer: dots arc across
        for i in range(n_transfer):
            lines += [
                f'        self.play(',
                f'            MoveAlongPath(transfer_dot_{i}, transfer_path_{i}),',
                f'            FadeOut(metal_dot_{i}),',
                f'            run_time={rt_transfer / max(n_transfer, 1):.3f}',
                f'        )',
                f'        self.play(FadeIn(nm_dot_{min(i, min(n_nm_dots,6)-1)}), FadeOut(transfer_dot_{i}),'
                f' run_time=0.25)',
            ]
        elapsed += rt_transfer
        if hold_trans > 0.05:
            lines += [f'        self.wait({hold_trans:.3f})']
            elapsed += hold_trans

        # Form ions: resize + badges
        new_rm = rad_m * 0.72
        new_rn = rad_n * 1.20
        lines += [
            f'        cation_badge.set_opacity(1)',
            f'        anion_badge.set_opacity(1)',
            f'        self.play(',
            f'            metal_circle.animate.scale({new_rm / rad_m:.3f}),'
            f'            nonmetal_circle.animate.scale({new_rn / rad_n:.3f}),',
            f'            FadeIn(cation_badge, anion_badge),',
            f'            run_time={rt_ions:.3f}',
            f'        )',
        ]
        elapsed += rt_ions
        if hold_ions > 0.05:
            lines += [f'        self.wait({hold_ions:.3f})']
            elapsed += hold_ions

        # Attraction arrow
        lines += [
            f'        attract_grp.set_opacity(1)',
            f'        self.play(GrowArrow(attract_arrow), FadeIn(attract_lbl), run_time={rt_attract:.3f})',
        ]
        elapsed += rt_attract
        if hold_att > 0.05:
            lines += [f'        self.wait({hold_att:.3f})']
            elapsed += hold_att

        # Lattice
        lines += [
            f'        full_lattice.set_opacity(1)',
            f'        self.play(',
            f'            FadeOut(metal_grp, metal_dots, nonmetal_grp, nm_dots,'
            f' cation_badge, anion_badge, attract_grp),',
            f'            FadeIn(full_lattice),',
            f'            run_time={rt_lattice:.3f}',
            f'        )',
        ]
        elapsed += rt_lattice
        if hold_lat > 0.05:
            lines += [f'        self.wait({hold_lat:.3f})']
            elapsed += hold_lat

        # Formula
        lines += [
            f'        formula_text.set_opacity(1)',
            f'        self.play(Write(formula_text), run_time={rt_formula:.3f})',
        ]
        elapsed += rt_formula
        if hold_form > 0.05:
            lines += [f'        self.wait({hold_form:.3f})']
            elapsed += hold_form

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)