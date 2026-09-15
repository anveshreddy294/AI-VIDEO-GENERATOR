"""Covalent Bonding / Lewis Structures template.

Visual sequence:
  1. Title + two isolated atoms appear (with valence electron dots)
  2. Atoms slide toward each other
  3. Shared electron pair(s) appear between atoms — bond line(s) drawn
  4. Lone pairs appear on each atom
  5. Formal-charge badges appear (if non-zero)
  6. Bond type label (single / double / triple) + bond length annotation
  7. Molecular formula fades in below
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
    BOND_COLOR,
    ELECTRON_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    element_color,
    _aid,
    _aparams,
    _indent,
    _esc,
)

LONE_PAIR_COLOR = "#c8d3e6"
BOND_LABEL_COLOR = "#f7c948"


class CovalentBondingTemplate:
    ALLOWED_EVENTS = {
        "place", "approach", "form_bond",
        "lone_pairs", "formal_charges",
        "bond_label", "show_formula", "hold",
    }
    SLOTS = {
        "atom_a": ["H", "C", "N", "O", "F", "Cl", "generic"],
        "atom_b": ["H", "C", "N", "O", "F", "Cl", "generic"],
    }
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Covalent Bond in H₂O'>",
  "atom_a": "H|C|N|O|F|Cl|generic",
  "atom_b": "H|C|N|O|F|Cl|generic",
  "bond_order": 1,
  "formula": "<molecule formula, e.g. 'H₂O'>",
  "bond_label": "<bond type label, e.g. 'Single Covalent Bond'>",
  "show_lone_pairs": true
}
"""

    # (symbol, radius, valence_electrons, color)
    _ATOM_DATA: dict[str, tuple[float, int]] = {
        "H":  (0.26, 1),
        "C":  (0.34, 4),
        "N":  (0.32, 5),
        "O":  (0.30, 6),
        "F":  (0.28, 7),
        "Cl": (0.38, 7),
        "S":  (0.36, 6),
        "P":  (0.36, 5),
        "generic": (0.32, 4),
    }

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 12.0))
        title_text = plan.get("title", "Covalent Bonding")

        params = plan.get("params", {})
        sym_a     = params.get("atom_a", "H")
        sym_b     = params.get("atom_b", "Cl")
        n_bonds   = int(params.get("bonds", 1))          # 1=single, 2=double, 3=triple
        formula   = params.get("formula",  f"{sym_a}{sym_b}")
        bond_len_pm = params.get("bond_length_pm", "")   # optional annotation

        data_a = CovalentBondingTemplate._ATOM_DATA.get(sym_a,
                  CovalentBondingTemplate._ATOM_DATA["generic"])
        data_b = CovalentBondingTemplate._ATOM_DATA.get(sym_b,
                  CovalentBondingTemplate._ATOM_DATA["generic"])

        ra, va = data_a  # radius, valence electrons
        rb, vb = data_b
        col_a = element_color(sym_a)
        col_b = element_color(sym_b)

        # Lone pairs = (valence - shared_electrons) / 2
        shared = n_bonds * 2
        lp_a = max(0, (va - shared) // 2)
        lp_b = max(0, (vb - shared) // 2)

        # Starting positions (atoms separated, then they converge)
        bond_gap = 0.12
        final_cx = 0.0
        final_ax = -(ra + rb / 2 + bond_gap + n_bonds * 0.08)
        final_bx =  (ra + rb / 2 + bond_gap + n_bonds * 0.08)
        start_ax = final_ax - 1.8
        start_bx = final_bx + 1.8
        ay = 0.0

        _evs = plan.get("events", [])
        rt_place   = event_rt_type(timeline, _evs, "place",          "e0", 0.7)
        rt_approach= event_rt_type(timeline, _evs, "approach",       "e1", 0.9)
        rt_bond    = event_rt_type(timeline, _evs, "form_bond",      "e2", 0.75)
        hold_bond  = event_hold(timeline, "e2", 0.4)
        rt_lone    = event_rt_type(timeline, _evs, "lone_pairs",     "e3", 0.65)
        hold_lone  = event_hold(timeline, "e3", 0.35)
        rt_fcharge = event_rt_type(timeline, _evs, "formal_charges", "e4", 0.5)
        rt_blabel  = event_rt_type(timeline, _evs, "bond_label",     "e5", 0.6)
        hold_blbl  = event_hold(timeline, "e5", 0.4)
        rt_formula = event_rt_type(timeline, _evs, "show_formula",   "e6", 0.6)
        hold_form  = event_hold(timeline, "e6", 0.5)

        lines: list[str] = [_HEADER]

        # ── Title ──────────────────────────────────────────────────
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=36, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # ── Atom A (starts left, moves right) ──────────────────────
        lines += [
            f'        atom_a = Circle(radius={ra:.3f}, color="{col_a}",'
            f' fill_color="{col_a}", fill_opacity=0.80, stroke_width=2)',
            f'        atom_a.move_to(np.array([{start_ax:.3f}, {ay:.3f}, 0]))',
            f'        sym_a = Text("{_esc(sym_a)}", font_size=22, weight=BOLD, color="{TITLE_COLOR}")',
            f'        sym_a.move_to(atom_a.get_center())',
            f'        grp_a = VGroup(atom_a, sym_a)',
            "",
        ]

        # ── Atom B (starts right, moves left) ──────────────────────
        lines += [
            f'        atom_b = Circle(radius={rb:.3f}, color="{col_b}",'
            f' fill_color="{col_b}", fill_opacity=0.80, stroke_width=2)',
            f'        atom_b.move_to(np.array([{start_bx:.3f}, {ay:.3f}, 0]))',
            f'        sym_b = Text("{_esc(sym_b)}", font_size=22, weight=BOLD, color="{TITLE_COLOR}")',
            f'        sym_b.move_to(atom_b.get_center())',
            f'        grp_b = VGroup(atom_b, sym_b)',
            "",
        ]

        # ── Valence dot markers (initial isolated state) ───────────
        # Draw dots around each atom at cardinal & diagonal positions
        def dot_positions(atom_x: float, r: float, n_dots: int) -> list[tuple[float, float]]:
            positions = []
            angle_step = 2 * math.pi / max(n_dots, 1)
            for i in range(n_dots):
                angle = math.pi / 4 + i * angle_step  # start at 45°
                positions.append((atom_x + (r + 0.14) * math.cos(angle),
                                  ay     + (r + 0.14) * math.sin(angle)))
            return positions

        # Initial dots on atom A
        dot_a_pos = dot_positions(start_ax, ra, va)
        for i, (dx, dy) in enumerate(dot_a_pos):
            lines += [
                f'        dot_a_{i} = Dot(radius=0.07, color="{ELECTRON_COLOR}")',
                f'        dot_a_{i}.move_to(np.array([{dx:.3f}, {dy:.3f}, 0]))',
            ]
        a_dot_grp = ", ".join(f'dot_a_{i}' for i in range(va))
        lines += [f'        dots_a = VGroup({a_dot_grp})' if va else '        dots_a = VGroup()', ""]

        # Initial dots on atom B
        dot_b_pos = dot_positions(start_bx, rb, vb)
        for i, (dx, dy) in enumerate(dot_b_pos):
            lines += [
                f'        dot_b_{i} = Dot(radius=0.07, color="{ELECTRON_COLOR}")',
                f'        dot_b_{i}.move_to(np.array([{dx:.3f}, {dy:.3f}, 0]))',
            ]
        b_dot_grp = ", ".join(f'dot_b_{i}' for i in range(vb))
        lines += [f'        dots_b = VGroup({b_dot_grp})' if vb else '        dots_b = VGroup()', ""]

        # ── Bond lines (appear after approach) ─────────────────────
        bond_spacing = 0.13
        for bi in range(n_bonds):
            offset = (bi - (n_bonds - 1) / 2) * bond_spacing
            lines += [
                f'        bond_{bi} = Line(',
                f'            np.array([{final_ax + ra:.3f}, {ay + offset:.3f}, 0]),',
                f'            np.array([{final_bx - rb:.3f}, {ay + offset:.3f}, 0]),',
                f'            color="{BOND_COLOR}", stroke_width=4',
                f'        )',
                f'        bond_{bi}.set_opacity(0)',
            ]
        lines.append("")

        # Shared electron pair dots (center of bond)
        bond_cx = (final_ax + ra + final_bx - rb) / 2
        for bi in range(n_bonds):
            offset = (bi - (n_bonds - 1) / 2) * bond_spacing
            lines += [
                f'        shared_e_{bi}_l = Dot(radius=0.065, color="{ELECTRON_COLOR}")',
                f'        shared_e_{bi}_l.move_to(np.array([{bond_cx - 0.12:.3f}, {ay + offset:.3f}, 0]))',
                f'        shared_e_{bi}_r = Dot(radius=0.065, color="{ELECTRON_COLOR}")',
                f'        shared_e_{bi}_r.move_to(np.array([{bond_cx + 0.12:.3f}, {ay + offset:.3f}, 0]))',
                f'        shared_e_{bi}_l.set_opacity(0)',
                f'        shared_e_{bi}_r.set_opacity(0)',
            ]
        lines.append("")

        # ── Lone pairs ─────────────────────────────────────────────
        # Atom A lone pairs (left side, stacked above/below)
        lp_offsets_a = [(0, (i - (lp_a - 1)/2) * 0.22) for i in range(lp_a)]
        for i, (ox, oy) in enumerate(lp_offsets_a):
            lx1 = final_ax - ra - 0.18 - 0.09
            lx2 = final_ax - ra - 0.18 + 0.09
            lines += [
                f'        lp_a_{i}_l = Dot(radius=0.065, color="{LONE_PAIR_COLOR}")',
                f'        lp_a_{i}_l.move_to(np.array([{lx1:.3f}, {ay + oy:.3f}, 0]))',
                f'        lp_a_{i}_r = Dot(radius=0.065, color="{LONE_PAIR_COLOR}")',
                f'        lp_a_{i}_r.move_to(np.array([{lx2:.3f}, {ay + oy:.3f}, 0]))',
                f'        lp_a_{i}_l.set_opacity(0)',
                f'        lp_a_{i}_r.set_opacity(0)',
            ]
        lines.append("")

        # Atom B lone pairs (right side)
        lp_offsets_b = [(0, (i - (lp_b - 1)/2) * 0.22) for i in range(lp_b)]
        for i, (ox, oy) in enumerate(lp_offsets_b):
            rx1 = final_bx + rb + 0.18 - 0.09
            rx2 = final_bx + rb + 0.18 + 0.09
            lines += [
                f'        lp_b_{i}_l = Dot(radius=0.065, color="{LONE_PAIR_COLOR}")',
                f'        lp_b_{i}_l.move_to(np.array([{rx1:.3f}, {ay + oy:.3f}, 0]))',
                f'        lp_b_{i}_r = Dot(radius=0.065, color="{LONE_PAIR_COLOR}")',
                f'        lp_b_{i}_r.move_to(np.array([{rx2:.3f}, {ay + oy:.3f}, 0]))',
                f'        lp_b_{i}_l.set_opacity(0)',
                f'        lp_b_{i}_r.set_opacity(0)',
            ]
        lines.append("")

        # ── Bond type label ────────────────────────────────────────
        bond_names = {1: "Single Bond", 2: "Double Bond", 3: "Triple Bond"}
        bond_name  = bond_names.get(n_bonds, "Bond")
        bond_annotation = f"{bond_name}"
        if bond_len_pm:
            bond_annotation += f"  ({bond_len_pm} pm)"
        lines += [
            f'        bond_lbl = Text("{_esc(bond_annotation)}", font_size=22, color="{BOND_LABEL_COLOR}")',
            f'        bond_lbl.next_to(atom_a, DOWN, buff=0.65)',
            f'        bond_lbl.set_opacity(0)',
            "",
        ]

        # ── Molecular formula ──────────────────────────────────────
        lines += [
            f'        formula_text = Text("{_esc(formula)}", font_size=30, weight=BOLD, color="{ACCENT2}")',
            f'        formula_text.to_edge(DOWN, buff=0.5)',
            f'        formula_text.set_opacity(0)',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        lines += [f'        self.play(Write(title), run_time={rt_place:.3f})']
        elapsed += rt_place

        # Place atoms with valence dots
        lines += [
            f'        self.play(FadeIn(grp_a, dots_a, grp_b, dots_b), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # Approach: atoms slide toward each other, dots fade
        lines += [
            f'        self.play(',
            f'            grp_a.animate.move_to(np.array([{final_ax:.3f}, {ay:.3f}, 0])),',
            f'            sym_a.animate.move_to(np.array([{final_ax:.3f}, {ay:.3f}, 0])),',
            f'            grp_b.animate.move_to(np.array([{final_bx:.3f}, {ay:.3f}, 0])),',
            f'            sym_b.animate.move_to(np.array([{final_bx:.3f}, {ay:.3f}, 0])),',
            f'            FadeOut(dots_a, dots_b),',
            f'            run_time={rt_approach:.3f}',
            f'        )',
        ]
        elapsed += rt_approach

        # Form bond
        bond_creates = ", ".join(f'Create(bond_{bi})' for bi in range(n_bonds))
        shared_fades = ", ".join(
            f'FadeIn(shared_e_{bi}_l, shared_e_{bi}_r)'
            for bi in range(n_bonds)
        )
        bond_opacities = "\n".join(f'        bond_{bi}.set_opacity(1)' for bi in range(n_bonds))
        shared_opacities = "\n".join(
            f'        shared_e_{bi}_l.set_opacity(1)\n        shared_e_{bi}_r.set_opacity(1)'
            for bi in range(n_bonds)
        )
        lines += [
            bond_opacities,
            shared_opacities,
            f'        self.play({bond_creates}, {shared_fades}, run_time={rt_bond:.3f})',
        ]
        elapsed += rt_bond
        if hold_bond > 0.05:
            lines += [f'        self.wait({hold_bond:.3f})']
            elapsed += hold_bond

        # Lone pairs
        all_lp_anims = []
        for i in range(lp_a):
            lines += [
                f'        lp_a_{i}_l.set_opacity(1)',
                f'        lp_a_{i}_r.set_opacity(1)',
            ]
            all_lp_anims += [f'FadeIn(lp_a_{i}_l, lp_a_{i}_r)']
        for i in range(lp_b):
            lines += [
                f'        lp_b_{i}_l.set_opacity(1)',
                f'        lp_b_{i}_r.set_opacity(1)',
            ]
            all_lp_anims += [f'FadeIn(lp_b_{i}_l, lp_b_{i}_r)']
        if all_lp_anims:
            lines += [f'        self.play({", ".join(all_lp_anims)}, run_time={rt_lone:.3f})']
        elapsed += rt_lone
        if hold_lone > 0.05:
            lines += [f'        self.wait({hold_lone:.3f})']
            elapsed += hold_lone

        # Bond label
        lines += [
            f'        bond_lbl.set_opacity(1)',
            f'        self.play(FadeIn(bond_lbl), run_time={rt_blabel:.3f})',
        ]
        elapsed += rt_blabel
        if hold_blbl > 0.05:
            lines += [f'        self.wait({hold_blbl:.3f})']
            elapsed += hold_blbl

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