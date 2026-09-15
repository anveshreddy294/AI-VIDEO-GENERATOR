"""Bohr Orbit Model template.

Semantic tags : atomic-structure, bohr-model, electron-shells, energy-levels,
                quantized-orbits, emission-spectrum, absorption-spectrum
Visualizable  : Bohr atom orbits, electron jumping between shells,
                energy level diagram, photon emission/absorption

Visual sequence:
  1. Title + "Niels Bohr, 1913" label
  2. Nucleus cluster draws at centre (protons + neutrons as Dots)
  3. Quantized orbit rings animate outward one at a time, each labeled (n=1, n=2, …)
  4. Electrons (Dots) placed on each shell and orbit smoothly via MoveAlongPath
  5. Energy-level ladder diagram appears on the right (horizontal lines for n=1…4)
  6. Electron transition: highlight jumps n=1→n=3 (absorption) with upward arrow + hν label
  7. Electron drops back n=3→n=1 (emission) with downward arrow + photon dot flying out
  8. Summary text: "Only specific energy levels are allowed"

Electrons orbit continuously using ValueTracker + UpdateFromAlphaFunc so the animation
looks live. Transitions use MoveAlongPath on the straight vertical jump path.
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
    ENERGY_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    _esc,
    _aparams,
)

PHOTON_COLOR   = "#f7c948"   # gold  — emitted photon
ABSORB_COLOR   = "#ff5c8a"   # pink  — absorption arrow
EMIT_COLOR     = "#41d4a8"   # teal  — emission arrow


class BohrOrbitTemplate:
    ALLOWED_EVENTS = {
        "place", "draw_nucleus", "draw_orbits",
        "populate_electrons", "energy_levels",
        "absorption", "emission", "summary", "hold",
    }
    SLOTS = {
        "atom": ["hydrogen", "helium", "lithium", "sodium", "generic"],
    }
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Bohr Model of the Hydrogen Atom'>",
  "atom": "hydrogen|helium|lithium|sodium|generic",
  "symbol": "<element symbol>",
  "atomic_number": <integer, determines proton count>,
  "n_shells": <number of shells to show, 2–4 recommended>,
  "electrons_per_shell": [<list of integers, one per shell>],
  "show_energy_levels": true,
  "show_transition": true,
  "transition_from": 1,
  "transition_to": 3,
  "transition_type": "absorption|emission"
}
Defaults: hydrogen atom, 2 shells [1, 0], show_transition true, absorption n=1→n=2.
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur   = float(timeline.get("audio_duration", 18.0))
        title_text  = plan.get("title", "Bohr Model of the Atom")

        content = plan.get("content") or {}
        if not isinstance(content, dict):
            content = {}
        params  = plan.get("params", {})

        def _get(key, default):
            return content.get(key) or params.get(key, default)

        symbol       = _get("symbol", "H")
        atomic_z     = int(_get("atomic_number", 1))
        n_shells     = int(_get("n_shells", 3))
        eps          = _get("electrons_per_shell", None)
        show_energy  = _get("show_energy_levels", True)
        show_trans   = _get("show_transition", True)
        trans_from   = int(_get("transition_from", 1))
        trans_to     = int(_get("transition_to", 2))
        trans_type   = _get("transition_type", "absorption")  # "absorption" | "emission"

        # Derive electrons per shell from atomic number if not given
        if eps is None or not isinstance(eps, list):
            _full = [2, 8, 18, 32]
            remaining = atomic_z
            eps = []
            for cap in _full[:n_shells]:
                placed = min(remaining, cap)
                eps.append(placed)
                remaining -= placed
                if remaining <= 0:
                    break
            while len(eps) < n_shells:
                eps.append(0)

        n_shells = min(n_shells, 4)
        eps = eps[:n_shells]

        n_protons  = atomic_z
        n_neutrons = max(0, int(_get("mass_number", atomic_z * 2 - 1)) - atomic_z)
        if n_protons <= 0 and n_neutrons <= 0:
            n_protons = 1

        # Layout — atom left, energy ladder right
        cx, cy      = -2.6, 0.0
        nuc_r       = 0.30
        shell_gap   = 0.58
        shell_radii = [nuc_r + shell_gap * (i + 1) for i in range(n_shells)]
        e_ladder_x  = 3.2

        _evs = plan.get("events", [])
        rt_place   = event_rt_type(timeline, _evs, "place",              "e0", 0.65)
        rt_nuc     = event_rt_type(timeline, _evs, "draw_nucleus",       "e1", 0.8)
        hold_nuc   = event_hold(timeline, "e1", 0.3)
        rt_orbits  = event_rt_type(timeline, _evs, "draw_orbits",        "e2", 1.2)
        hold_orb   = event_hold(timeline, "e2", 0.25)
        rt_elec    = event_rt_type(timeline, _evs, "populate_electrons", "e3", 0.8)
        hold_elec  = event_hold(timeline, "e3", 0.4)
        rt_energy  = event_rt_type(timeline, _evs, "energy_levels",      "e4", 0.8)
        hold_en    = event_hold(timeline, "e4", 0.4)
        rt_absorb  = event_rt_type(timeline, _evs, "absorption",         "e5", 1.0)
        hold_ab    = event_hold(timeline, "e5", 0.4)
        rt_emit    = event_rt_type(timeline, _evs, "emission",           "e6", 1.0)
        hold_em    = event_hold(timeline, "e6", 0.4)
        rt_sum     = event_rt_type(timeline, _evs, "summary",            "e7", 0.65)
        hold_sum   = event_hold(timeline, "e7", 0.5)

        lines: list[str] = [_HEADER]

        lines += [
            '        from modules.manim.style_config import (',
            '            fit_title, fit_in_box, SAFE_W, SAFE_H,',
            '            TITLE_BAND_Y, CAPTION_BAND_Y, CONTENT_CENTER_Y,',
            '        )',
            "",
        ]

        # ── Title ──────────────────────────────────────────────────
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=32, weight=BOLD, color="{TITLE_COLOR}")',
            f'        fit_title(title, SAFE_W - 2.2)',
            f'        title.move_to(np.array([0, TITLE_BAND_Y, 0]))',
            f'        bohr_credit = Text("Niels Bohr, 1913", font_size=14, color="{LABEL_COLOR}")',
            f'        bohr_credit.next_to(title, DOWN, buff=0.12)',
            "",
        ]

        # ── Nucleus cluster ────────────────────────────────────────
        lines += [
            f'        nucleus_bg = Circle(radius={nuc_r:.3f}, color="{NUCLEUS_COLOR}",',
            f'            fill_opacity=0.18, stroke_width=1.5)',
            f'        nucleus_bg.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
        ]
        # Spiral placement for protons+neutrons
        _all_particles = [(True,)] * n_protons + [(False,)] * n_neutrons
        _angle = 0.0
        _r_nuc = 0.0
        for _pi, (is_p,) in enumerate(_all_particles[:14]):
            _px = cx + _r_nuc * math.cos(_angle)
            _py = cy + _r_nuc * math.sin(_angle)
            _col = NUCLEUS_COLOR if is_p else NEUTRON_COLOR
            _vn  = f'nuc_dot_{_pi}'
            lines += [
                f'        {_vn} = Dot(radius=0.085, color="{_col}", fill_opacity=0.92)',
                f'        {_vn}.move_to(np.array([{_px:.4f}, {_py:.4f}, 0]))',
            ]
            _r_nuc += 0.05
            _angle += math.pi * 1.236

        nuc_dots = ", ".join(f'nuc_dot_{i}' for i in range(min(len(_all_particles), 14)))
        if nuc_dots:
            lines += [
                f'        nucleus_grp = VGroup(nucleus_bg, {nuc_dots})',
            ]
        else:
            lines += [
                f'        nuc_placeholder = Dot(radius=0.10, color="{NUCLEUS_COLOR}", fill_opacity=0.9)',
                f'        nuc_placeholder.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
                f'        nucleus_grp = VGroup(nucleus_bg, nuc_placeholder)',
            ]
        lines += [
            f'        nucleus_grp.set_opacity(0)',
            "",
        ]

        # ── Electron shells (DashedVMobject circles) ───────────────
        for i, r in enumerate(shell_radii):
            lines += [
                f'        shell_{i} = DashedVMobject(',
                f'            Circle(radius={r:.4f}, color="{ACCENT1}",',
                f'                stroke_width=1.4, stroke_opacity=0.55),',
                f'            num_dashes=44',
                f'        )',
                f'        shell_{i}.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
                f'        shell_{i}.set_opacity(0)',
                f'        shell_lbl_{i} = Text("n={i+1}", font_size=14, color="{LABEL_COLOR}")',
                f'        shell_lbl_{i}.move_to(np.array([{cx:.3f}, {cy + r + 0.12:.3f}, 0]))',
                f'        shell_lbl_{i}.set_opacity(0)',
            ]
        lines.append("")

        # ── Electrons on shells ────────────────────────────────────
        electron_data: list[list[tuple[float, float, str]]] = []
        for si, (r, n_e) in enumerate(zip(shell_radii, eps)):
            shell_data = []
            for ei in range(max(n_e, 1) if n_e > 0 else 0):
                if n_e == 0:
                    break
                angle = 2 * math.pi * ei / n_e
                ex = cx + r * math.cos(angle)
                ey = cy + r * math.sin(angle)
                vname = f'elec_{si}_{ei}'
                lines += [
                    f'        {vname} = Dot(radius=0.085, color="{ELECTRON_COLOR}", fill_opacity=0.95)',
                    f'        {vname}.move_to(np.array([{ex:.4f}, {ey:.4f}, 0]))',
                    f'        {vname}.set_opacity(0)',
                ]
                shell_data.append((ex, ey, vname))
            electron_data.append(shell_data)
        lines.append("")

        # Element symbol badge
        lines += [
            f'        sym_text = Text("{_esc(symbol)}", font_size=26, weight=BOLD, color="{ACCENT3}")',
            f'        sym_text.move_to(np.array([{cx:.3f}, {cy:.3f}, 0]))',
            f'        sym_text.set_opacity(0)',
            "",
        ]

        # ── Energy level ladder ────────────────────────────────────
        if show_energy:
            e_level_ys = {1: -1.4, 2: -0.55, 3: 0.25, 4: 0.90}
            for ni in range(1, n_shells + 1):
                ely = e_level_ys.get(ni, -1.4 + (ni - 1) * 0.7)
                lines += [
                    f'        elev_{ni} = Line(',
                    f'            np.array([{e_ladder_x - 0.7:.3f}, {ely:.3f}, 0]),',
                    f'            np.array([{e_ladder_x + 0.7:.3f}, {ely:.3f}, 0]),',
                    f'            color="{ACCENT1}", stroke_width=1.8',
                    f'        )',
                    f'        elev_lbl_{ni} = Text("n={ni}", font_size=15, color="{LABEL_COLOR}")',
                    f'        elev_lbl_{ni}.next_to(elev_{ni}, RIGHT, buff=0.12)',
                    f'        elev_grp_{ni} = VGroup(elev_{ni}, elev_lbl_{ni})',
                    f'        elev_grp_{ni}.set_opacity(0)',
                ]
            lines += [
                f'        elev_title = Text("Energy Levels", font_size=17, color="{ACCENT2}")',
                f'        elev_title.move_to(np.array([{e_ladder_x:.3f}, {e_level_ys.get(n_shells, 0.9) + 0.5:.3f}, 0]))',
                f'        elev_title.set_opacity(0)',
                "",
            ]

        # ── Transition objects ─────────────────────────────────────
        if show_energy and show_trans:
            tf_y = e_level_ys.get(trans_from, -1.4)
            tt_y = e_level_ys.get(trans_to, -0.55)
            arrow_col = ABSORB_COLOR if trans_type == "absorption" else EMIT_COLOR
            arrow_dir = "UP" if trans_type == "absorption" else "DOWN"
            hn_lbl = "hν absorbed" if trans_type == "absorption" else "hν emitted"
            lines += [
                f'        trans_arrow = Arrow(',
                f'            np.array([{e_ladder_x - 0.35:.3f}, {tf_y:.3f}, 0]),',
                f'            np.array([{e_ladder_x - 0.35:.3f}, {tt_y:.3f}, 0]),',
                f'            buff=0.02, color="{arrow_col}", stroke_width=3',
                f'        )',
                f'        trans_lbl = Text("{_esc(hn_lbl)}", font_size=15, color="{arrow_col}")',
                f'        trans_lbl.next_to(trans_arrow, LEFT, buff=0.12)',
                f'        photon_dot = Dot(radius=0.10, color="{PHOTON_COLOR}", fill_opacity=0.95)',
                f'        photon_dot.move_to(np.array([{e_ladder_x:.3f}, {tf_y:.3f}, 0]))',
                f'        trans_grp = VGroup(trans_arrow, trans_lbl)',
                f'        trans_grp.set_opacity(0)',
                f'        photon_dot.set_opacity(0)',
                "",
            ]

        # ── Summary text ───────────────────────────────────────────
        lines += [
            f'        summary_txt = Text(',
            f'            "Only specific energy levels are allowed — Bohr\\\'s quantum condition",',
            f'            font_size=16, color="{ACCENT2}"',
            f'        )',
            f'        fit_title(summary_txt, SAFE_W - 0.8)',
            f'        summary_txt.move_to(np.array([0, CAPTION_BAND_Y, 0]))',
            f'        summary_txt.set_opacity(0)',
            "",
        ]

        # ── Fit atom + ladder into safe area ───────────────────────
        shell_names = ", ".join(f"shell_{i}" for i in range(n_shells))
        lbl_names = ", ".join(f"shell_lbl_{i}" for i in range(n_shells))
        elec_names = ", ".join(
            vname for shell_data in electron_data for (_, _, vname) in shell_data
        )
        atom_parts = ["nucleus_grp", "sym_text"]
        if shell_names:
            atom_parts.append(f"VGroup({shell_names})")
        if lbl_names:
            atom_parts.append(f"VGroup({lbl_names})")
        if elec_names:
            atom_parts.append(f"VGroup({elec_names})")
        lines += [
            f'        atom_group = VGroup({", ".join(atom_parts)})',
        ]
        if show_energy:
            elev_names = ", ".join(f"elev_grp_{ni}" for ni in range(1, n_shells + 1))
            lines += [
                f'        ladder_group = VGroup(elev_title, {elev_names})' + (
                    ", trans_grp, photon_dot" if show_trans else ""
                ),
                f'        scene_visual = VGroup(atom_group, ladder_group)',
            ]
        else:
            lines += [
                f'        scene_visual = atom_group',
            ]
        lines += [
            f'        fit_in_box(scene_visual, SAFE_W - 0.5, SAFE_H - 2.2)',
            f'        scene_visual.move_to(np.array([0, CONTENT_CENTER_Y - 0.15, 0]))',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        # e0: title
        lines += [
            f'        self.play(Write(title), FadeIn(bohr_credit), run_time={rt_place:.3f}, rate_func=smooth)',
        ]
        elapsed += rt_place

        # e1: nucleus
        lines += [
            f'        nucleus_grp.set_opacity(1)',
            f'        self.play(FadeIn(nucleus_grp), run_time={rt_nuc:.3f}, rate_func=smooth)',
        ]
        elapsed += rt_nuc
        if hold_nuc > 0.05:
            lines += [f'        self.wait({hold_nuc:.3f})']
            elapsed += hold_nuc

        # e2: shells appear (batched)
        if n_shells > 0:
            for i in range(n_shells):
                lines += [
                    f'        shell_{i}.set_opacity(1)',
                    f'        shell_lbl_{i}.set_opacity(1)',
                ]
            shell_anims = []
            for i in range(n_shells):
                shell_anims.append(f'Create(shell_{i})')
                shell_anims.append(f'FadeIn(shell_lbl_{i})')
            lines += [
                f'        self.play(',
                f'            LaggedStart({", ".join(shell_anims)}, lag_ratio=0.18),',
                f'            run_time={rt_orbits:.3f}, rate_func=smooth',
                f'        )',
            ]
        elapsed += rt_orbits
        if hold_orb > 0.05:
            lines += [f'        self.wait({hold_orb:.3f})']
            elapsed += hold_orb

        # e3: electrons appear + symbol
        elec_anims = []
        for si, shell_data in enumerate(electron_data):
            for (_, _, vname) in shell_data:
                elec_anims.append(f'FadeIn({vname})')
        if elec_anims:
            lines += [
                f'        sym_text.set_opacity(1)',
                f'        self.play(',
                f'            FadeIn(sym_text),',
                f'            LaggedStart({", ".join(elec_anims)}, lag_ratio=0.12),',
                f'            run_time={rt_elec:.3f}, rate_func=smooth',
                f'        )',
            ]
        elapsed += rt_elec
        if hold_elec > 0.05:
            lines += [f'        self.wait({hold_elec:.3f})']
            elapsed += hold_elec

        # Continuous orbit animation using Rotate updater on first shell electrons
        if electron_data and electron_data[0]:
            first_elec_vars = [vname for (_, _, vname) in electron_data[0]]
            r0 = shell_radii[0]
            lines += [
                f'        # Smooth orbital motion for n=1 electron(s)',
                f'        _orbit_tracker = ValueTracker(0)',
                f'        _n1_elecs = [{", ".join(first_elec_vars)}]',
                f'        def _orbit_updater(mob):',
                f'            _alpha = _orbit_tracker.get_value()',
                f'            _base_angle = 2 * PI * _alpha',
                f'            for _k, _em in enumerate(_n1_elecs):',
                f'                _theta = _base_angle + 2 * PI * _k / max(len(_n1_elecs), 1)',
                f'                _em.move_to(nucleus_bg.get_center() + np.array([{r0:.4f} * np.cos(_theta), {r0:.4f} * np.sin(_theta), 0]))',
                f'        for _em in _n1_elecs:',
                f'            _em.add_updater(_orbit_updater)',
                f'        self.play(_orbit_tracker.animate.set_value(1.0), run_time=2.0, rate_func=linear)',
                f'        for _em in _n1_elecs:',
                f'            _em.remove_updater(_orbit_updater)',
                "",
            ]

        # e4: energy level diagram
        if show_energy:
            for ni in range(1, n_shells + 1):
                lines += [f'        elev_grp_{ni}.set_opacity(1)']
            lines += [
                f'        elev_title.set_opacity(1)',
                f'        self.play(FadeIn(elev_title), run_time=0.3, rate_func=smooth)',
            ]
            elev_anims = [f'FadeIn(elev_grp_{ni})' for ni in range(1, n_shells + 1)]
            lines += [
                f'        self.play(',
                f'            LaggedStart({", ".join(elev_anims)}, lag_ratio=0.2),',
                f'            run_time={rt_energy:.3f}, rate_func=smooth',
                f'        )',
            ]
            elapsed += rt_energy
            if hold_en > 0.05:
                lines += [f'        self.wait({hold_en:.3f})']
                elapsed += hold_en

        # e5: absorption transition
        if show_energy and show_trans:
            lines += [
                f'        trans_grp.set_opacity(1)',
                f'        self.play(GrowArrow(trans_arrow), FadeIn(trans_lbl), run_time={rt_absorb:.3f}, rate_func=smooth)',
            ]
            elapsed += rt_absorb
            if hold_ab > 0.05:
                lines += [f'        self.wait({hold_ab:.3f})']
                elapsed += hold_ab

            # e6: emission — photon dot flies out
            tf_y_e = e_level_ys.get(trans_to, -0.55)
            exit_x = e_ladder_x + 1.5
            exit_y = tf_y_e
            lines += [
                f'        photon_dot.move_to(np.array([{e_ladder_x:.3f}, {tf_y_e:.3f}, 0]))',
                f'        photon_dot.set_opacity(1)',
                f'        self.play(',
                f'            FadeOut(trans_grp),',
                f'            FadeIn(photon_dot, scale=0.3),',
                f'            run_time=0.3',
                f'        )',
                f'        self.play(',
                f'            photon_dot.animate.move_to(np.array([{exit_x:.3f}, {exit_y:.3f}, 0])).set_opacity(0),',
                f'            run_time={rt_emit:.3f}',
                f'        )',
            ]
            elapsed += rt_emit
            if hold_em > 0.05:
                lines += [f'        self.wait({hold_em:.3f})']
                elapsed += hold_em

        # e7: summary
        lines += [
            f'        summary_txt.set_opacity(1)',
            f'        self.play(Write(summary_txt), run_time={rt_sum:.3f}, rate_func=smooth)',
        ]
        elapsed += rt_sum
        if hold_sum > 0.05:
            lines += [f'        self.wait({hold_sum:.3f})']
            elapsed += hold_sum

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)