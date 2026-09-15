"""Molecular Geometry / VSEPR template.

Visual sequence:
  1. Title + central atom appears
  2. Bonded atoms grow outward from center at correct angles
  3. Bond angle arcs appear with degree labels
  4. Lone pairs shown as lobe shapes (if any)
  5. Geometry name label (e.g., "Bent", "Tetrahedral") fades in
  6. VSEPR notation (AX₂E₁) and dipole moment arrow (if polar)
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
    ORBITAL_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    element_color,
    _aid,
    _aparams,
    _indent,
    _esc,
)

ANGLE_COLOR   = "#f7c948"
LONE_COLOR    = "#7c5cbf"
DIPOLE_COLOR  = "#ff5c8a"


# Geometry definitions: name -> (bond_angles_deg, lone_pairs, vsepr_notation, is_polar)
_GEOMETRIES: dict[str, dict] = {
    "linear": {
        "angles_deg":   [180.0],
        "bond_angles":  ["180°"],
        "lone_pairs":   0,
        "vsepr":        "AX₂",
        "is_polar":     False,
        "description":  "Linear",
        "n_bonds":      2,
    },
    "bent": {
        "angles_deg":   [104.5],
        "bond_angles":  ["104.5°"],
        "lone_pairs":   2,
        "vsepr":        "AX₂E₂",
        "is_polar":     True,
        "description":  "Bent",
        "n_bonds":      2,
    },
    "trigonal_planar": {
        "angles_deg":   [120.0, 120.0, 120.0],
        "bond_angles":  ["120°"],
        "lone_pairs":   0,
        "vsepr":        "AX₃",
        "is_polar":     False,
        "description":  "Trigonal Planar",
        "n_bonds":      3,
    },
    "trigonal_pyramidal": {
        "angles_deg":   [107.0, 107.0, 107.0],
        "bond_angles":  ["107°"],
        "lone_pairs":   1,
        "vsepr":        "AX₃E₁",
        "is_polar":     True,
        "description":  "Trigonal Pyramidal",
        "n_bonds":      3,
    },
    "tetrahedral": {
        "angles_deg":   [109.5, 109.5, 109.5, 109.5],
        "bond_angles":  ["109.5°"],
        "lone_pairs":   0,
        "vsepr":        "AX₄",
        "is_polar":     False,
        "description":  "Tetrahedral",
        "n_bonds":      4,
    },
    "t_shaped": {
        "angles_deg":   [90.0, 90.0, 180.0],
        "bond_angles":  ["90°", "180°"],
        "lone_pairs":   2,
        "vsepr":        "AX₃E₂",
        "is_polar":     True,
        "description":  "T-Shaped",
        "n_bonds":      3,
    },
    "seesaw": {
        "angles_deg":   [102.0, 173.0, 102.0, 173.0],
        "bond_angles":  ["102°", "173°"],
        "lone_pairs":   1,
        "vsepr":        "AX₄E₁",
        "is_polar":     True,
        "description":  "See-Saw",
        "n_bonds":      4,
    },
}

# Bond direction vectors for common geometries (2D projection)
_BOND_DIRECTIONS: dict[str, list[tuple[float, float]]] = {
    "linear":             [(1.0, 0.0), (-1.0, 0.0)],
    "bent":               [(math.cos(math.radians(52.25)),  math.sin(math.radians(52.25))),
                           (math.cos(math.radians(127.75)), math.sin(math.radians(127.75)))],
    "trigonal_planar":    [(1.0, 0.0),
                           (math.cos(math.radians(120)), math.sin(math.radians(120))),
                           (math.cos(math.radians(240)), math.sin(math.radians(240)))],
    "trigonal_pyramidal": [(1.0, 0.0),
                           (math.cos(math.radians(120)), math.sin(math.radians(120))),
                           (math.cos(math.radians(240)), math.sin(math.radians(240)))],
    "tetrahedral":        [(1.0, 0.4), (-1.0, 0.4),
                           (0.6, -1.0), (-0.6, -1.0)],
    "t_shaped":           [(0.0, 1.0), (1.0, 0.0), (-1.0, 0.0)],
    "seesaw":             [(0.0, 1.0), (0.0, -1.0),
                           (1.0, 0.25), (-1.0, 0.25)],
}


class MolecularGeometryTemplate:
    ALLOWED_EVENTS = {
        "place", "draw_bonds", "show_angles",
        "lone_pairs", "label_geometry",
        "vsepr_notation", "dipole", "hold",
    }
    SLOTS = {
        "central_atom": ["C", "N", "O", "S", "P", "Cl", "generic"],
        "ligand":       ["H", "F", "Cl", "O", "generic"],
    }
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'VSEPR: Tetrahedral Shape of CH₄'>",
  "central_atom": "C|N|O|S|P|Cl|generic",
  "ligand": "H|F|Cl|O|generic",
  "geometry": "linear|bent|trigonal_planar|tetrahedral|trigonal_pyramidal|octahedral",
  "bond_angle": "<bond angle string, e.g. '109.5°'>",
  "formula": "<molecular formula, e.g. 'CH₄'>",
  "lone_pairs": <integer 0-3>
}
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 13.0))
        title_text = plan.get("title", "Molecular Geometry")

        params   = plan.get("params", {})
        geometry = params.get("geometry", "tetrahedral")
        sym_c    = params.get("central", "C")
        sym_l    = params.get("ligand",  "H")
        molecule = params.get("molecule", f"{sym_c}{sym_l}₄")

        geo = _GEOMETRIES.get(geometry, _GEOMETRIES["tetrahedral"])
        dirs = _BOND_DIRECTIONS.get(geometry, _BOND_DIRECTIONS["tetrahedral"])
        n_bonds   = geo["n_bonds"]
        n_lp      = geo["lone_pairs"]
        bond_len  = 1.05

        col_c = element_color(sym_c)
        col_l = element_color(sym_l)
        rad_c = 0.32
        rad_l = 0.20

        cx, cy = 0.0, 0.1

        _evs = plan.get("events", [])
        rt_place  = event_rt_type(timeline, _evs, "place",          "e0", 0.6)
        rt_bonds  = event_rt_type(timeline, _evs, "draw_bonds",     "e1", 1.0)
        hold_bonds= event_hold(timeline, "e1", 0.3)
        rt_angles = event_rt_type(timeline, _evs, "show_angles",    "e2", 0.7)
        hold_ang  = event_hold(timeline, "e2", 0.4)
        rt_lone   = event_rt_type(timeline, _evs, "lone_pairs",     "e3", 0.6)
        hold_lone = event_hold(timeline, "e3", 0.3)
        rt_geolbl = event_rt_type(timeline, _evs, "label_geometry", "e4", 0.65)
        hold_geo  = event_hold(timeline, "e4", 0.4)
        rt_vsepr  = event_rt_type(timeline, _evs, "vsepr_notation", "e5", 0.6)
        rt_dipole = event_rt_type(timeline, _evs, "dipole",         "e6", 0.6)
        hold_dip  = event_hold(timeline, "e6", 0.5)

        lines: list[str] = [_HEADER]

        # Title
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=36, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # Molecule label
        lines += [
            f'        mol_lbl = Text("{_esc(molecule)}", font_size=22, color="{LABEL_COLOR}")',
            f'        mol_lbl.to_edge(UP, buff=0.72)',
            "",
        ]

        # Central atom
        lines += [
            f'        central = Circle(radius={rad_c:.3f}, color="{col_c}",'
            f' fill_color="{col_c}", fill_opacity=0.85, stroke_width=2)',
            f'        central.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
            f'        central_sym = Text("{_esc(sym_c)}", font_size=22, weight=BOLD, color="{TITLE_COLOR}")',
            f'        central_sym.move_to(central.get_center())',
            f'        central_grp = VGroup(central, central_sym)',
            "",
        ]

        # Bond lines + ligand atoms
        norm_dirs = []
        for dx, dy in dirs[:n_bonds]:
            mag = math.hypot(dx, dy)
            norm_dirs.append((dx / mag, dy / mag))

        for bi, (dx, dy) in enumerate(norm_dirs):
            bx_end = cx + dx * bond_len
            by_end = cy + dy * bond_len
            lx = cx + dx * (bond_len + 0.05)
            ly = cy + dy * (bond_len + 0.05)
            lines += [
                f'        bond_{bi} = Line(',
                f'            np.array([{cx:.3f}, {cy:.3f}, 0]),',
                f'            np.array([{bx_end:.3f}, {by_end:.3f}, 0]),',
                f'            color="{BOND_COLOR}", stroke_width=4',
                f'        )',
                f'        bond_{bi}.set_opacity(0)',
                f'        lig_{bi} = Circle(radius={rad_l:.3f}, color="{col_l}",'
                f' fill_color="{col_l}", fill_opacity=0.80, stroke_width=1.5)',
                f'        lig_{bi}.move_to(np.array([{lx:.3f}, {ly:.3f}, 0]))',
                f'        lig_{bi}_sym = Text("{_esc(sym_l)}", font_size=16, weight=BOLD, color="{TITLE_COLOR}")',
                f'        lig_{bi}_sym.move_to(lig_{bi}.get_center())',
                f'        lig_{bi}_grp = VGroup(lig_{bi}, lig_{bi}_sym)',
                f'        lig_{bi}_grp.set_opacity(0)',
            ]
        lines.append("")

        # Bond angle arcs (between first two bonds)
        if len(norm_dirs) >= 2:
            a1 = math.atan2(norm_dirs[0][1], norm_dirs[0][0])
            a2 = math.atan2(norm_dirs[1][1], norm_dirs[1][0])
            arc_r = 0.40
            lines += [
                f'        angle_arc = Arc(radius={arc_r:.3f}, start_angle={a1:.4f},'
                f' angle={a2 - a1:.4f}, color="{ANGLE_COLOR}", stroke_width=2)',
                f'        angle_arc.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
                f'        angle_lbl = Text("{geo["bond_angles"][0]}", font_size=18, color="{ANGLE_COLOR}")',
            ]
            mid_angle = (a1 + a2) / 2
            lbl_x = cx + (arc_r + 0.22) * math.cos(mid_angle)
            lbl_y = cy + (arc_r + 0.22) * math.sin(mid_angle)
            lines += [
                f'        angle_lbl.move_to(np.array([{lbl_x:.3f}, {lbl_y:.3f}, 0]))',
                f'        angle_grp = VGroup(angle_arc, angle_lbl)',
                f'        angle_grp.set_opacity(0)',
                "",
            ]

        # Lone pair lobes (ellipses pointing away from bonded region)
        if n_lp > 0:
            # Place lone pairs opposite to the centroid of bond directions
            sum_dx = sum(d[0] for d in norm_dirs)
            sum_dy = sum(d[1] for d in norm_dirs)
            avg_mag = math.hypot(sum_dx, sum_dy) or 1.0
            lp_dx = -sum_dx / avg_mag
            lp_dy = -sum_dy / avg_mag
            for lpi in range(n_lp):
                spread = (lpi - (n_lp - 1) / 2) * 0.32
                perp_dx = -lp_dy
                perp_dy =  lp_dx
                lpx = cx + lp_dx * (rad_c + 0.32) + perp_dx * spread
                lpy = cy + lp_dy * (rad_c + 0.32) + perp_dy * spread
                lines += [
                    f'        lp_{lpi} = Ellipse(width=0.32, height=0.18, color="{LONE_COLOR}",'
                    f' fill_color="{LONE_COLOR}", fill_opacity=0.55, stroke_width=1)',
                    f'        lp_{lpi}.move_to(np.array([{lpx:.3f}, {lpy:.3f}, 0]))',
                    f'        lp_{lpi}.set_opacity(0)',
                ]
            lp_vars = ", ".join(f'lp_{lpi}' for lpi in range(n_lp))
            lines += [f'        lone_pairs_grp = VGroup({lp_vars})', ""]

        # Geometry label
        lines += [
            f'        geo_lbl = Text("{_esc(geo["description"])}", font_size=28, weight=BOLD, color="{ACCENT2}")',
            f'        geo_lbl.to_edge(DOWN, buff=0.8)',
            f'        geo_lbl.set_opacity(0)',
            "",
        ]

        # VSEPR notation
        lines += [
            f'        vsepr_lbl = Text("VSEPR: {_esc(geo["vsepr"])}", font_size=21, color="{ACCENT3}")',
            f'        vsepr_lbl.to_edge(DOWN, buff=0.42)',
            f'        vsepr_lbl.set_opacity(0)',
            "",
        ]

        # Dipole arrow (if polar)
        if geo["is_polar"]:
            # Net dipole points from positive to negative (rough: toward ligands)
            dip_dx = sum(d[0] for d in norm_dirs)
            dip_dy = sum(d[1] for d in norm_dirs)
            dip_mag = math.hypot(dip_dx, dip_dy) or 1.0
            dip_dx /= dip_mag
            dip_dy /= dip_mag
            dip_len = 0.7
            lines += [
                f'        dipole_arrow = Arrow(',
                f'            np.array([{cx:.3f}, {cy:.3f}, 0]),',
                f'            np.array([{cx + dip_dx*dip_len:.3f}, {cy + dip_dy*dip_len:.3f}, 0]),',
                f'            color="{DIPOLE_COLOR}", stroke_width=4, buff=0',
                f'        )',
                f'        dipole_lbl = Text("\u03bc \u2260 0  (polar)", font_size=18, color="{DIPOLE_COLOR}")',
                f'        dipole_lbl.next_to(dipole_arrow, RIGHT, buff=0.1)',
                f'        dipole_grp = VGroup(dipole_arrow, dipole_lbl)',
                f'        dipole_grp.set_opacity(0)',
                "",
            ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), FadeIn(mol_lbl), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        lines += [f'        self.play(FadeIn(central_grp), run_time={rt_place:.3f})']
        elapsed += rt_place

        # Draw bonds one by one
        bond_rt = rt_bonds / max(n_bonds, 1)
        for bi in range(n_bonds):
            lines += [
                f'        bond_{bi}.set_opacity(1)',
                f'        lig_{bi}_grp.set_opacity(1)',
                f'        self.play(Create(bond_{bi}), FadeIn(lig_{bi}_grp), run_time={bond_rt:.3f})',
            ]
        elapsed += rt_bonds
        if hold_bonds > 0.05:
            lines += [f'        self.wait({hold_bonds:.3f})']
            elapsed += hold_bonds

        # Angle arcs
        if len(norm_dirs) >= 2:
            lines += [
                f'        angle_grp.set_opacity(1)',
                f'        self.play(Create(angle_arc), FadeIn(angle_lbl), run_time={rt_angles:.3f})',
            ]
        elapsed += rt_angles
        if hold_ang > 0.05:
            lines += [f'        self.wait({hold_ang:.3f})']
            elapsed += hold_ang

        # Lone pairs
        if n_lp > 0:
            lines += [
                f'        lone_pairs_grp.set_opacity(1)',
                f'        self.play(FadeIn(lone_pairs_grp), run_time={rt_lone:.3f})',
            ]
        elapsed += rt_lone
        if hold_lone > 0.05 and n_lp > 0:
            lines += [f'        self.wait({hold_lone:.3f})']
            elapsed += hold_lone

        # Geometry label
        lines += [
            f'        geo_lbl.set_opacity(1)',
            f'        self.play(Write(geo_lbl), run_time={rt_geolbl:.3f})',
        ]
        elapsed += rt_geolbl
        if hold_geo > 0.05:
            lines += [f'        self.wait({hold_geo:.3f})']
            elapsed += hold_geo

        # VSEPR notation
        lines += [
            f'        vsepr_lbl.set_opacity(1)',
            f'        self.play(FadeIn(vsepr_lbl), run_time={rt_vsepr:.3f})',
        ]
        elapsed += rt_vsepr

        # Dipole
        if geo["is_polar"]:
            lines += [
                f'        dipole_grp.set_opacity(1)',
                f'        self.play(GrowArrow(dipole_arrow), FadeIn(dipole_lbl), run_time={rt_dipole:.3f})',
            ]
            elapsed += rt_dipole
            if hold_dip > 0.05:
                lines += [f'        self.wait({hold_dip:.3f})']
                elapsed += hold_dip

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)