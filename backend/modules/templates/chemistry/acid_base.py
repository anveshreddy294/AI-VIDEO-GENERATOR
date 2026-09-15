"""Acid-Base Chemistry / pH template.

Visual sequence:
  1. Title + pH scale (0–14) drawn horizontally with color gradient
  2. Needle/marker placed at starting pH
  3. Acid or base molecule shown; proton transfer animation
  4. H⁺ / OH⁻ concentration bars appear
  5. pH calculation text: pH = -log[H⁺]
  6. Marker slides to new pH value
  7. Strong vs. Weak label + dissociation degree annotation
  8. Conjugate acid-base pair labels (optional)
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
    ACID_COLOR,
    BASE_COLOR,
    ELECTRON_COLOR,
    ENERGY_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    _esc,
)

PROTON_COLOR   = "#ff7a59"
PH_LOW_COLOR   = "#ff3c3c"    # pH 0 (strongly acidic)
PH_MID_COLOR   = "#41d4a8"    # pH 7 (neutral)
PH_HIGH_COLOR  = "#4f8ef7"    # pH 14 (strongly basic)
NEEDLE_COLOR   = "#f7c948"
WATER_COLOR    = "#4fc3f7"
WEAK_COLOR     = "#f7c948"
STRONG_COLOR   = "#ff5c8a"


class AcidBaseTemplate:
    ALLOWED_EVENTS = {
        "place", "draw_scale", "show_molecule",
        "proton_transfer", "concentration_bars",
        "ph_calculation", "slide_needle",
        "strong_weak_label", "conjugate_pair", "hold",
    }
    SLOTS = {}  # acid/base info from plan params
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Strong vs Weak Acids'>",
  "acid_formula": "<acid formula, e.g. 'HCl'>",
  "base_formula": "<base formula, e.g. 'NaOH'>",
  "acid_type": "strong|weak",
  "base_type": "strong|weak",
  "ph_value": <number between 0 and 14>,
  "reaction_equation": "<neutralisation equation, e.g. 'HCl + NaOH → NaCl + H₂O'>",
  "show_ph_scale": true
}
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 14.0))
        title_text = plan.get("title", "Acid-Base Chemistry")

        params       = plan.get("params", {})
        acid_name    = params.get("acid",        "HCl")
        base_name    = params.get("base",        "NaOH")
        is_acid      = params.get("is_acid",     True)      # True=show acid, False=show base
        ph_initial   = float(params.get("ph_initial", 7.0))
        ph_final     = float(params.get("ph_final",   1.0))
        is_strong    = params.get("is_strong",   True)
        conc_h       = params.get("conc_h",      "1.0")     # [H+] mol/L string
        ph_formula   = params.get("ph_formula",  f"pH = -log({conc_h}) = {ph_final:.1f}")
        conjugate_acid  = params.get("conjugate_acid",  "Cl⁻")
        conjugate_base  = params.get("conjugate_base",  "H₂O")
        show_conjugate  = params.get("show_conjugate",  False)

        # Scale layout
        scale_y   = 0.5
        scale_x0  = -4.0
        scale_x1  =  4.0
        scale_len = scale_x1 - scale_x0
        tick_h    = 0.18

        def ph_to_x(ph: float) -> float:
            return scale_x0 + (ph / 14.0) * scale_len

        _evs = plan.get("events", [])
        rt_place    = event_rt_type(timeline, _evs, "place",             "e0", 0.6)
        rt_scale    = event_rt_type(timeline, _evs, "draw_scale",        "e1", 1.0)
        hold_scale  = event_hold(timeline, "e1", 0.35)
        rt_mol      = event_rt_type(timeline, _evs, "show_molecule",     "e2", 0.7)
        hold_mol    = event_hold(timeline, "e2", 0.3)
        rt_transfer = event_rt_type(timeline, _evs, "proton_transfer",   "e3", 0.9)
        hold_trans  = event_hold(timeline, "e3", 0.4)
        rt_conc     = event_rt_type(timeline, _evs, "concentration_bars","e4", 0.7)
        hold_conc   = event_hold(timeline, "e4", 0.3)
        rt_phcalc   = event_rt_type(timeline, _evs, "ph_calculation",    "e5", 0.7)
        hold_phcalc = event_hold(timeline, "e5", 0.4)
        rt_needle   = event_rt_type(timeline, _evs, "slide_needle",      "e6", 1.0)
        hold_needle = event_hold(timeline, "e6", 0.5)
        rt_swlbl    = event_rt_type(timeline, _evs, "strong_weak_label", "e7", 0.6)
        hold_swlbl  = event_hold(timeline, "e7", 0.4)
        rt_conj     = event_rt_type(timeline, _evs, "conjugate_pair",    "e8", 0.6)
        hold_conj   = event_hold(timeline, "e8", 0.4)

        lines: list[str] = [_HEADER]

        # Title
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=36, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # ── pH Scale ───────────────────────────────────────────────
        # Background gradient rectangle (approximated with 3 colored sections)
        seg_len = scale_len / 3
        lines += [
            f'        # pH scale background (acidic | neutral | basic)',
            f'        scale_acid = Rectangle(width={seg_len:.3f}, height=0.30,'
            f' color="{PH_LOW_COLOR}", fill_color="{PH_LOW_COLOR}", fill_opacity=0.70,'
            f' stroke_width=0)',
            f'        scale_acid.move_to(np.array([{scale_x0 + seg_len/2:.3f}, {scale_y:.3f}, 0]))',
            f'        scale_neut = Rectangle(width={seg_len:.3f}, height=0.30,'
            f' color="{PH_MID_COLOR}", fill_color="{PH_MID_COLOR}", fill_opacity=0.70,'
            f' stroke_width=0)',
            f'        scale_neut.move_to(np.array([{scale_x0 + seg_len*1.5:.3f}, {scale_y:.3f}, 0]))',
            f'        scale_base = Rectangle(width={seg_len:.3f}, height=0.30,'
            f' color="{PH_HIGH_COLOR}", fill_color="{PH_HIGH_COLOR}", fill_opacity=0.70,'
            f' stroke_width=0)',
            f'        scale_base.move_to(np.array([{scale_x0 + seg_len*2.5:.3f}, {scale_y:.3f}, 0]))',
            f'        scale_grp = VGroup(scale_acid, scale_neut, scale_base)',
            f'        scale_grp.set_opacity(0)',
            "",
        ]

        # Tick marks + labels for pH 0, 1, 3, 7, 11, 13, 14
        tick_phs = [0, 1, 3, 7, 11, 13, 14]
        for ph in tick_phs:
            tx = ph_to_x(ph)
            lines += [
                f'        tick_{ph} = Line(UP*{tick_h:.2f}, DOWN*{tick_h:.2f},'
                f' color="{LABEL_COLOR}", stroke_width=1.5)',
                f'        tick_{ph}.move_to(np.array([{tx:.3f}, {scale_y:.3f}, 0]))',
                f'        tick_lbl_{ph} = Text("{ph}", font_size=14, color="{LABEL_COLOR}")',
                f'        tick_lbl_{ph}.move_to(np.array([{tx:.3f}, {scale_y - 0.38:.3f}, 0]))',
            ]
        tick_vars = " + ".join(
            [f'tick_{ph}' for ph in tick_phs] + [f'tick_lbl_{ph}' for ph in tick_phs]
        )
        lines += [
            f'        ticks_grp = VGroup({", ".join(f"tick_{ph}" for ph in tick_phs)},'
            f' {", ".join(f"tick_lbl_{ph}" for ph in tick_phs)})',
            f'        ticks_grp.set_opacity(0)',
            "",
        ]

        # "Acidic" / "Neutral" / "Basic" labels above scale
        lines += [
            f'        acidic_lbl = Text("Acidic", font_size=16, color="{PH_LOW_COLOR}")',
            f'        acidic_lbl.move_to(np.array([{scale_x0 + seg_len/2:.3f}, {scale_y + 0.45:.3f}, 0]))',
            f'        neutral_lbl = Text("Neutral", font_size=16, color="{PH_MID_COLOR}")',
            f'        neutral_lbl.move_to(np.array([{scale_x0 + seg_len*1.5:.3f}, {scale_y + 0.45:.3f}, 0]))',
            f'        basic_lbl = Text("Basic", font_size=16, color="{PH_HIGH_COLOR}")',
            f'        basic_lbl.move_to(np.array([{scale_x0 + seg_len*2.5:.3f}, {scale_y + 0.45:.3f}, 0]))',
            f'        region_lbls = VGroup(acidic_lbl, neutral_lbl, basic_lbl)',
            f'        region_lbls.set_opacity(0)',
            "",
        ]

        # Needle at initial pH
        init_nx = ph_to_x(ph_initial)
        final_nx = ph_to_x(ph_final)
        lines += [
            f'        needle = Triangle(fill_color="{NEEDLE_COLOR}", fill_opacity=0.9,'
            f' stroke_width=0)',
            f'        needle.scale(0.12)',
            f'        needle.move_to(np.array([{init_nx:.3f}, {scale_y - 0.28:.3f}, 0]))',
            f'        needle.set_opacity(0)',
            "",
        ]

        # ── Molecule display ───────────────────────────────────────
        mol_sym = acid_name if is_acid else base_name
        mol_col = ACID_COLOR if is_acid else BASE_COLOR
        mx, my  = -1.5, -0.8
        lines += [
            f'        mol_circle = Circle(radius=0.35, color="{mol_col}",'
            f' fill_color="{mol_col}", fill_opacity=0.75, stroke_width=2)',
            f'        mol_circle.move_to(np.array([{mx:.3f}, {my:.3f}, 0]))',
            f'        mol_text = Text("{_esc(mol_sym)}", font_size=22, weight=BOLD, color="{TITLE_COLOR}")',
            f'        mol_text.move_to(mol_circle.get_center())',
            f'        mol_grp = VGroup(mol_circle, mol_text)',
            f'        mol_grp.set_opacity(0)',
            "",
        ]

        # Water molecule (for proton transfer)
        wx, wy = 1.5, -0.8
        lines += [
            f'        water_circle = Circle(radius=0.28, color="{WATER_COLOR}",'
            f' fill_color="{WATER_COLOR}", fill_opacity=0.75, stroke_width=2)',
            f'        water_circle.move_to(np.array([{wx:.3f}, {wy:.3f}, 0]))',
            f'        water_text = Text("H₂O", font_size=18, weight=BOLD, color="{TITLE_COLOR}")',
            f'        water_text.move_to(water_circle.get_center())',
            f'        water_grp = VGroup(water_circle, water_text)',
            f'        water_grp.set_opacity(0)',
            "",
        ]

        # Proton (H⁺) that transfers
        lines += [
            f'        proton = Dot(radius=0.12, color="{PROTON_COLOR}", fill_opacity=0.95)',
            f'        proton.move_to(np.array([{mx + 0.38:.3f}, {my:.3f}, 0]))',
            f'        proton_lbl = Text("H\u207a", font_size=14, weight=BOLD, color="{TITLE_COLOR}")',
            f'        proton_lbl.move_to(proton.get_center())',
            f'        proton_grp = VGroup(proton, proton_lbl)',
            f'        proton_grp.set_opacity(0)',
            "",
        ]

        # Transfer arc path
        mid_x = (mx + wx) / 2
        lines += [
            f'        transfer_arc = ArcBetweenPoints(',
            f'            np.array([{mx + 0.38:.3f}, {my:.3f}, 0]),',
            f'            np.array([{wx - 0.30:.3f}, {wy:.3f}, 0]),',
            f'            angle=-PI/3',
            f'        )',
            f'        transfer_arc.set_stroke(color="{PROTON_COLOR}", width=2, opacity=0.6)',
            "",
        ]

        # Concentration bars: [H+] and [OH-]
        bar_y0     = -2.0
        bar_maxh_c = 1.5
        bar_w_c    = 0.5
        hconc_frac = 1.0 - (ph_final / 14.0)
        ohconc_frac = ph_final / 14.0
        lines += [
            f'        # Concentration bars',
            f'        bar_h = Rectangle(width={bar_w_c:.3f},'
            f' height={hconc_frac * bar_maxh_c:.3f},'
            f' color="{ACID_COLOR}", fill_color="{ACID_COLOR}", fill_opacity=0.80,'
            f' stroke_width=1)',
            f'        bar_h.move_to(np.array([-1.0, {bar_y0 + hconc_frac * bar_maxh_c / 2:.3f}, 0]))',
            f'        bar_h_lbl = Text("[H\u207a]", font_size=16, color="{ACID_COLOR}")',
            f'        bar_h_lbl.move_to(np.array([-1.0, {bar_y0 - 0.22:.3f}, 0]))',
            f'        bar_oh = Rectangle(width={bar_w_c:.3f},'
            f' height={ohconc_frac * bar_maxh_c:.3f},'
            f' color="{BASE_COLOR}", fill_color="{BASE_COLOR}", fill_opacity=0.80,'
            f' stroke_width=1)',
            f'        bar_oh.move_to(np.array([1.0, {bar_y0 + ohconc_frac * bar_maxh_c / 2:.3f}, 0]))',
            f'        bar_oh_lbl = Text("[OH\u207b]", font_size=16, color="{BASE_COLOR}")',
            f'        bar_oh_lbl.move_to(np.array([1.0, {bar_y0 - 0.22:.3f}, 0]))',
            f'        conc_bars = VGroup(bar_h, bar_h_lbl, bar_oh, bar_oh_lbl)',
            f'        conc_bars.set_opacity(0)',
            "",
        ]

        # pH formula text
        lines += [
            f'        ph_formula_text = Text("{_esc(ph_formula)}", font_size=22, color="{ACCENT3}")',
            f'        ph_formula_text.to_edge(DOWN, buff=0.75)',
            f'        ph_formula_text.set_opacity(0)',
            "",
        ]

        # Strong/weak label
        sw_col  = STRONG_COLOR if is_strong else WEAK_COLOR
        sw_text = ("Strong Acid — 100% dissociation" if is_strong and is_acid
                   else "Weak Acid — partial dissociation" if not is_strong and is_acid
                   else "Strong Base — 100% dissociation" if is_strong
                   else "Weak Base — partial dissociation")
        lines += [
            f'        sw_lbl = Text("{_esc(sw_text)}", font_size=18, color="{sw_col}")',
            f'        sw_lbl.to_edge(DOWN, buff=0.40)',
            f'        sw_lbl.set_opacity(0)',
            "",
        ]

        # Conjugate pair
        if show_conjugate:
            lines += [
                f'        conj_text = Text("Conjugate pair: {_esc(mol_sym)} / {_esc(conjugate_acid)}",'
                f' font_size=17, color="{ACCENT2}")',
                f'        conj_text.to_edge(DOWN, buff=0.15)',
                f'        conj_text.set_opacity(0)',
                "",
            ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        lines += [f'        self.play(Write(title), run_time={rt_place:.3f})']
        elapsed += rt_place

        # Draw pH scale
        lines += [
            f'        scale_grp.set_opacity(1)',
            f'        ticks_grp.set_opacity(1)',
            f'        region_lbls.set_opacity(1)',
            f'        self.play(FadeIn(scale_grp, ticks_grp, region_lbls), run_time={rt_scale:.3f})',
        ]
        elapsed += rt_scale
        if hold_scale > 0.05:
            lines += [f'        self.wait({hold_scale:.3f})']
            elapsed += hold_scale

        # Place needle at initial pH
        lines += [
            f'        needle.set_opacity(1)',
            f'        self.play(FadeIn(needle), run_time=0.4)',
        ]

        # Show molecule
        lines += [
            f'        mol_grp.set_opacity(1)',
            f'        water_grp.set_opacity(1)',
            f'        self.play(FadeIn(mol_grp, water_grp), run_time={rt_mol:.3f})',
        ]
        elapsed += rt_mol
        if hold_mol > 0.05:
            lines += [f'        self.wait({hold_mol:.3f})']
            elapsed += hold_mol

        # Proton transfer
        lines += [
            f'        proton_grp.set_opacity(1)',
            f'        self.play(',
            f'            FadeIn(proton_grp),',
            f'            Create(transfer_arc),',
            f'            run_time=0.3',
            f'        )',
            f'        self.play(',
            f'            MoveAlongPath(proton_grp, transfer_arc),',
            f'            run_time={rt_transfer:.3f}',
            f'        )',
            f'        self.play(FadeOut(proton_grp, transfer_arc), run_time=0.25)',
        ]
        elapsed += rt_transfer
        if hold_trans > 0.05:
            lines += [f'        self.wait({hold_trans:.3f})']
            elapsed += hold_trans

        # Concentration bars
        lines += [
            f'        conc_bars.set_opacity(1)',
            f'        self.play(',
            f'            FadeOut(mol_grp, water_grp),',
            f'            FadeIn(conc_bars),',
            f'            run_time={rt_conc:.3f}',
            f'        )',
        ]
        elapsed += rt_conc
        if hold_conc > 0.05:
            lines += [f'        self.wait({hold_conc:.3f})']
            elapsed += hold_conc

        # pH calculation
        lines += [
            f'        ph_formula_text.set_opacity(1)',
            f'        self.play(Write(ph_formula_text), run_time={rt_phcalc:.3f})',
        ]
        elapsed += rt_phcalc
        if hold_phcalc > 0.05:
            lines += [f'        self.wait({hold_phcalc:.3f})']
            elapsed += hold_phcalc

        # Slide needle to final pH
        lines += [
            f'        self.play(',
            f'            needle.animate.move_to(np.array([{final_nx:.3f}, {scale_y - 0.28:.3f}, 0])),',
            f'            run_time={rt_needle:.3f}',
            f'        )',
        ]
        elapsed += rt_needle
        if hold_needle > 0.05:
            lines += [f'        self.wait({hold_needle:.3f})']
            elapsed += hold_needle

        # Strong / weak label
        lines += [
            f'        sw_lbl.set_opacity(1)',
            f'        self.play(FadeIn(sw_lbl), run_time={rt_swlbl:.3f})',
        ]
        elapsed += rt_swlbl
        if hold_swlbl > 0.05:
            lines += [f'        self.wait({hold_swlbl:.3f})']
            elapsed += hold_swlbl

        # Conjugate pair
        if show_conjugate:
            lines += [
                f'        conj_text.set_opacity(1)',
                f'        self.play(Write(conj_text), run_time={rt_conj:.3f})',
            ]
            elapsed += rt_conj
            if hold_conj > 0.05:
                lines += [f'        self.wait({hold_conj:.3f})']
                elapsed += hold_conj

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)