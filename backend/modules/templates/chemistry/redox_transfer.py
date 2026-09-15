"""Redox (Electron Transfer) template.

Semantic tags : redox, oxidation, reduction, electron-transfer,
                oxidizing-agent, reducing-agent, OIL-RIG,
                half-reactions, electrochemistry
Visualizable  : electron transfer between species, oxidation state change,
                half-reaction arrows, OIL-RIG mnemonic, charge notation

Visual sequence:
  1. Title + reaction equation (e.g. Mg + O₂ → MgO)
  2. Two atom/ion circles appear: Reducing agent (loses e⁻) on left,
     Oxidising agent (gains e⁻) on right
  3. Electron dots (Dot objects) appear near the reducing agent
  4. Transfer animation: electrons MoveAlongPath from left atom to right atom
     (curved arc above the two species, matching narration anchor phrase)
  5. Oxidation state labels update: left shows +n, right shows -n
  6. Half-reaction equations appear for oxidation (above) and reduction (below)
  7. OIL-RIG mnemonic box fades in:
       "OIL — Oxidation Is Loss (of electrons)"
       "RIG — Reduction Is Gain (of electrons)"
  8. Summary: "Species that loses electrons = reducing agent (gets oxidised)"

Electrons are represented as Dot objects. Transfer uses ArcBetweenPoints curved paths
so the motion is physically suggestive of electron cloud movement.
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
    ELECTRON_COLOR,
    IONIC_COLOR,
    ENERGY_COLOR,
    event_rt_type,
    event_hold,
    _esc,
)

OXIDISED_COLOR  = "#ff7a59"   # orange-red  — species being oxidised (loses e⁻)
REDUCED_COLOR   = "#41d4a8"   # teal        — species being reduced (gains e⁻)
ELECTRON_TFER   = "#f7c948"   # gold        — electrons in flight
OX_STATE_COLOR  = "#ff5c8a"   # pink-red    — oxidation state labels
OIL_COLOR       = "#ff7a59"   # OIL box colour
RIG_COLOR       = "#41d4a8"   # RIG box colour
HALF_RXN_COLOR  = "#c8d3e6"   # half-reaction text


class RedoxTransferTemplate:
    ALLOWED_EVENTS = {
        "place", "show_species", "show_electrons",
        "transfer", "update_charges", "half_reactions",
        "oil_rig", "summary", "hold",
    }
    SLOTS = {}
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Oxidation and Reduction'>",
  "reaction_equation": "<overall equation, e.g. 'Mg + O₂ → 2MgO'>",
  "reducing_agent": {
    "symbol": "<e.g. 'Mg'>",
    "initial_charge": 0,
    "final_charge": 2,
    "electrons_lost": 2
  },
  "oxidising_agent": {
    "symbol": "<e.g. 'O₂'>",
    "initial_charge": 0,
    "final_charge": -2,
    "electrons_gained": 2
  },
  "half_reaction_oxidation": "<e.g. 'Mg → Mg²⁺ + 2e⁻'>",
  "half_reaction_reduction": "<e.g. 'O₂ + 4e⁻ → 2O²⁻'>",
  "show_oil_rig": true,
  "n_electrons": <integer number of electron dots to animate, 1-4 recommended>
}
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur   = float(timeline.get("audio_duration", 18.0))
        title_text  = plan.get("title", "Oxidation and Reduction")

        content = plan.get("content") or {}
        if not isinstance(content, dict):
            content = {}
        params  = plan.get("params", {})

        def _get(key, default):
            return content.get(key) or params.get(key, default)

        rxn_eq = _get("reaction_equation", "Mg + O₂ → 2MgO")

        red_agent  = _get("reducing_agent",  {})
        ox_agent   = _get("oxidising_agent", {})
        if not isinstance(red_agent, dict):
            red_agent = {}
        if not isinstance(ox_agent, dict):
            ox_agent = {}

        red_sym       = red_agent.get("symbol", "Mg")
        red_init_chg  = int(red_agent.get("initial_charge", 0))
        red_fin_chg   = int(red_agent.get("final_charge", 2))
        e_lost        = int(red_agent.get("electrons_lost", 2))

        ox_sym        = ox_agent.get("symbol", "O₂")
        ox_init_chg   = int(ox_agent.get("initial_charge", 0))
        ox_fin_chg    = int(ox_agent.get("final_charge", -2))
        e_gained      = int(ox_agent.get("electrons_gained", 2))

        half_ox  = _get("half_reaction_oxidation",
                         f"{red_sym} → {red_sym}{_charge_sup(red_fin_chg)} + {e_lost}e⁻")
        half_red = _get("half_reaction_reduction",
                         f"{ox_sym} + {e_gained}e⁻ → {ox_sym}{_charge_sup(ox_fin_chg)}")

        show_oil = _get("show_oil_rig", True)
        n_elec   = min(int(_get("n_electrons", e_lost)), 4)

        # Layout
        left_x,  left_y  = -3.2,  0.1
        right_x, right_y =  3.2,  0.1
        arc_peak_y       =  2.0

        _evs = plan.get("events", [])
        rt_place    = event_rt_type(timeline, _evs, "place",           "e0", 0.60)
        rt_species  = event_rt_type(timeline, _evs, "show_species",    "e1", 0.80)
        hold_sp     = event_hold(timeline, "e1", 0.35)
        rt_elec_ap  = event_rt_type(timeline, _evs, "show_electrons",  "e2", 0.65)
        hold_ea     = event_hold(timeline, "e2", 0.30)
        rt_transfer = event_rt_type(timeline, _evs, "transfer",        "e3", 1.40)
        hold_tr     = event_hold(timeline, "e3", 0.45)
        rt_charges  = event_rt_type(timeline, _evs, "update_charges",  "e4", 0.65)
        hold_ch     = event_hold(timeline, "e4", 0.40)
        rt_half     = event_rt_type(timeline, _evs, "half_reactions",  "e5", 0.80)
        hold_hf     = event_hold(timeline, "e5", 0.45)
        rt_oil      = event_rt_type(timeline, _evs, "oil_rig",         "e6", 0.70)
        hold_oil    = event_hold(timeline, "e6", 0.50)
        rt_summary  = event_rt_type(timeline, _evs, "summary",         "e7", 0.65)
        hold_sum    = event_hold(timeline, "e7", 0.50)

        lines: list[str] = [_HEADER]

        # ── Title + equation ───────────────────────────────────────
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=34, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.28)',
            f'        rxn_eq = Text("{_esc(rxn_eq)}", font_size=22, color="{TEXT_COLOR}")',
            f'        rxn_eq.to_edge(UP, buff=0.72)',
            f'        rxn_eq.set_opacity(0)',
            "",
        ]

        # ── Reducing agent (left) ──────────────────────────────────
        left_init_lbl = _charge_str(red_init_chg)
        left_fin_lbl  = _charge_str(red_fin_chg)
        lines += [
            f'        # Reducing agent',
            f'        red_circle = Circle(radius=0.52, color="{OXIDISED_COLOR}",',
            f'            fill_color="{OXIDISED_COLOR}", fill_opacity=0.22, stroke_width=2.5)',
            f'        red_circle.move_to(np.array([{left_x:.3f}, {left_y:.3f}, 0]))',
            f'        red_sym_txt = Text("{_esc(red_sym)}", font_size=28, weight=BOLD, color="{TITLE_COLOR}")',
            f'        red_sym_txt.move_to(red_circle.get_center())',
            f'        red_charge_txt = Text("{_esc(left_init_lbl)}", font_size=18, color="{OX_STATE_COLOR}")',
            f'        red_charge_txt.next_to(red_circle, UP, buff=0.10)',
            f'        red_lbl = Text("Reducing Agent", font_size=15, color="{OXIDISED_COLOR}")',
            f'        red_lbl.next_to(red_circle, DOWN, buff=0.30)',
            f'        red_ox_lbl = Text("(gets oxidised)", font_size=13, color="{OXIDISED_COLOR}")',
            f'        red_ox_lbl.next_to(red_lbl, DOWN, buff=0.06)',
            f'        red_grp = VGroup(red_circle, red_sym_txt, red_charge_txt, red_lbl, red_ox_lbl)',
            f'        red_grp.set_opacity(0)',
            "",
        ]

        # ── Oxidising agent (right) ────────────────────────────────
        right_init_lbl = _charge_str(ox_init_chg)
        right_fin_lbl  = _charge_str(ox_fin_chg)
        lines += [
            f'        # Oxidising agent',
            f'        ox_circle = Circle(radius=0.52, color="{REDUCED_COLOR}",',
            f'            fill_color="{REDUCED_COLOR}", fill_opacity=0.22, stroke_width=2.5)',
            f'        ox_circle.move_to(np.array([{right_x:.3f}, {right_y:.3f}, 0]))',
            f'        ox_sym_txt = Text("{_esc(ox_sym)}", font_size=28, weight=BOLD, color="{TITLE_COLOR}")',
            f'        ox_sym_txt.move_to(ox_circle.get_center())',
            f'        ox_charge_txt = Text("{_esc(right_init_lbl)}", font_size=18, color="{OX_STATE_COLOR}")',
            f'        ox_charge_txt.next_to(ox_circle, UP, buff=0.10)',
            f'        ox_lbl = Text("Oxidising Agent", font_size=15, color="{REDUCED_COLOR}")',
            f'        ox_lbl.next_to(ox_circle, DOWN, buff=0.30)',
            f'        ox_red_lbl = Text("(gets reduced)", font_size=13, color="{REDUCED_COLOR}")',
            f'        ox_red_lbl.next_to(ox_lbl, DOWN, buff=0.06)',
            f'        ox_grp = VGroup(ox_circle, ox_sym_txt, ox_charge_txt, ox_lbl, ox_red_lbl)',
            f'        ox_grp.set_opacity(0)',
            "",
        ]

        # ── Electron dots near reducing agent ──────────────────────
        e_start_positions = []
        e_end_positions   = []
        for ei in range(n_elec):
            angle = math.pi / 2 + (ei - n_elec / 2 + 0.5) * 0.45
            sx = left_x + 0.55 * math.cos(angle)
            sy = left_y + 0.55 * math.sin(angle)
            ex = right_x - 0.6 + ei * 0.25
            ey = right_y + 0.55
            e_start_positions.append((sx, sy))
            e_end_positions.append((ex, ey))
            lines += [
                f'        elec_{ei} = Dot(radius=0.095, color="{ELECTRON_TFER}", fill_opacity=0.95)',
                f'        elec_{ei}.move_to(np.array([{sx:.4f}, {sy:.4f}, 0]))',
                f'        elec_lbl_{ei} = Text("e⁻", font_size=13, color="{ELECTRON_TFER}")',
                f'        elec_lbl_{ei}.move_to(elec_{ei}.get_center() + UP * 0.18)',
                f'        elec_unit_{ei} = VGroup(elec_{ei}, elec_lbl_{ei})',
                f'        elec_unit_{ei}.set_opacity(0)',
            ]
        lines.append("")

        # ── Arc paths for transfer ─────────────────────────────────
        mid_x = (left_x + right_x) / 2
        for ei, ((sx, sy), (ex, ey)) in enumerate(zip(e_start_positions, e_end_positions)):
            # Curved arc going up and over
            lines += [
                f'        transfer_arc_{ei} = ArcBetweenPoints(',
                f'            np.array([{sx:.4f}, {sy:.4f}, 0]),',
                f'            np.array([{ex:.4f}, {ey:.4f}, 0]),',
                f'            angle=-PI * 0.55',
                f'        )',
                f'        transfer_arc_{ei}.set_stroke(color="{ELECTRON_TFER}", width=1.5, opacity=0.45)',
            ]
        lines.append("")

        # Arrow label above arc
        lines += [
            f'        transfer_lbl = Text("{n_elec}e⁻", font_size=20, weight=BOLD, color="{ELECTRON_TFER}")',
            f'        transfer_lbl.move_to(np.array([{mid_x:.3f}, {left_y + 1.9:.3f}, 0]))',
            f'        transfer_lbl.set_opacity(0)',
            f'        transfer_arrow_disp = Arrow(',
            f'            np.array([{left_x + 0.7:.3f}, {left_y + 1.5:.3f}, 0]),',
            f'            np.array([{right_x - 0.7:.3f}, {right_y + 1.5:.3f}, 0]),',
            f'            buff=0, color="{ELECTRON_TFER}", stroke_width=2',
            f'        )',
            f'        transfer_arrow_disp.set_opacity(0)',
            "",
        ]

        # ── Charge update labels ───────────────────────────────────
        lines += [
            f'        # Updated charge labels post-transfer',
            f'        new_red_charge = Text("{_esc(left_fin_lbl)}", font_size=20, weight=BOLD,',
            f'            color="{OX_STATE_COLOR}")',
            f'        new_red_charge.next_to(red_circle, UP, buff=0.10)',
            f'        new_red_charge.set_opacity(0)',
            f'        new_ox_charge = Text("{_esc(right_fin_lbl)}", font_size=20, weight=BOLD,',
            f'            color="{REDUCED_COLOR}")',
            f'        new_ox_charge.next_to(ox_circle, UP, buff=0.10)',
            f'        new_ox_charge.set_opacity(0)',
            "",
        ]

        # ── Half reactions ─────────────────────────────────────────
        lines += [
            f'        half_ox_box = RoundedRectangle(corner_radius=0.12, width=5.8, height=0.60,',
            f'            color="{OXIDISED_COLOR}", fill_opacity=0.07, stroke_width=1.2)',
            f'        half_ox_box.move_to(np.array([{mid_x:.3f}, -1.55, 0]))',
            f'        half_ox_txt = Text("Oxidation: {_esc(half_ox)}", font_size=18, color="{OXIDISED_COLOR}")',
            f'        half_ox_txt.move_to(half_ox_box.get_center())',
            f'        half_red_box = RoundedRectangle(corner_radius=0.12, width=5.8, height=0.60,',
            f'            color="{REDUCED_COLOR}", fill_opacity=0.07, stroke_width=1.2)',
            f'        half_red_box.move_to(np.array([{mid_x:.3f}, -2.25, 0]))',
            f'        half_red_txt = Text("Reduction: {_esc(half_red)}", font_size=18, color="{REDUCED_COLOR}")',
            f'        half_red_txt.move_to(half_red_box.get_center())',
            f'        half_grp = VGroup(half_ox_box, half_ox_txt, half_red_box, half_red_txt)',
            f'        half_grp.set_opacity(0)',
            "",
        ]

        # ── OIL-RIG mnemonic box ───────────────────────────────────
        if show_oil:
            lines += [
                f'        oil_rig_box = RoundedRectangle(corner_radius=0.18, width=6.5, height=1.25,',
                f'            color="{ACCENT3}", fill_opacity=0.07, stroke_width=1.5)',
                f'        oil_rig_box.to_edge(RIGHT, buff=0.3).shift(UP * 0.5)',
                f'        oil_txt = Text("OIL — Oxidation Is Loss (of electrons)",',
                f'            font_size=16, color="{OIL_COLOR}")',
                f'        oil_txt.move_to(oil_rig_box.get_center() + UP * 0.28)',
                f'        rig_txt = Text("RIG — Reduction Is Gain (of electrons)",',
                f'            font_size=16, color="{RIG_COLOR}")',
                f'        rig_txt.move_to(oil_rig_box.get_center() + DOWN * 0.28)',
                f'        oilrig_grp = VGroup(oil_rig_box, oil_txt, rig_txt)',
                f'        oilrig_grp.set_opacity(0)',
                "",
            ]

        # ── Summary ────────────────────────────────────────────────
        lines += [
            f'        summary_txt = Text(',
            f'            "Species losing electrons = reducing agent (gets oxidised)",',
            f'            font_size=18, color="{ACCENT2}"',
            f'        )',
            f'        summary_txt.to_edge(DOWN, buff=0.32)',
            f'        summary_txt.set_opacity(0)',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        # e0: title + equation
        lines += [
            f'        self.play(Write(title), run_time={rt_place:.3f})',
            f'        rxn_eq.set_opacity(1)',
            f'        self.play(FadeIn(rxn_eq), run_time={rt_place * 0.5:.3f})',
        ]
        elapsed += rt_place

        # e1: species appear
        lines += [
            f'        red_grp.set_opacity(1)',
            f'        ox_grp.set_opacity(1)',
            f'        self.play(FadeIn(red_grp), FadeIn(ox_grp), run_time={rt_species:.3f})',
        ]
        elapsed += rt_species
        if hold_sp > 0.05:
            lines += [f'        self.wait({hold_sp:.3f})']
            elapsed += hold_sp

        # e2: electrons appear near reducing agent
        elec_fade_anims = ", ".join(f'FadeIn(elec_unit_{ei})' for ei in range(n_elec))
        lines += [
            f'        for _e in [{", ".join(f"elec_unit_{ei}" for ei in range(n_elec))}]:',
            f'            _e.set_opacity(1)',
            f'        self.play({elec_fade_anims}, run_time={rt_elec_ap:.3f})',
        ]
        elapsed += rt_elec_ap
        if hold_ea > 0.05:
            lines += [f'        self.wait({hold_ea:.3f})']
            elapsed += hold_ea

        # e3: electron transfer along arcs
        arc_create = ", ".join(f'Create(transfer_arc_{ei})' for ei in range(n_elec))
        move_anims = ", ".join(f'MoveAlongPath(elec_unit_{ei}, transfer_arc_{ei})' for ei in range(n_elec))
        lines += [
            f'        # Show arc trails, then move electrons',
            f'        self.play(',
            f'            FadeIn(transfer_lbl, shift=UP*0.2),',
            f'            GrowArrow(transfer_arrow_disp),',
            f'            {arc_create},',
            f'            run_time={rt_transfer * 0.35:.3f}',
            f'        )',
            f'        self.play(',
            f'            {move_anims},',
            f'            run_time={rt_transfer * 0.65:.3f}',
            f'        )',
            f'        self.play(',
            f'            FadeOut(transfer_lbl, transfer_arrow_disp,',
            *[f'                transfer_arc_{ei},' for ei in range(n_elec)],
            *[f'                elec_unit_{ei},' for ei in range(n_elec)],
            f'            ),',
            f'            run_time=0.30',
            f'        )',
        ]
        elapsed += rt_transfer
        if hold_tr > 0.05:
            lines += [f'        self.wait({hold_tr:.3f})']
            elapsed += hold_tr

        # e4: charge labels update
        lines += [
            f'        new_red_charge.set_opacity(1)',
            f'        new_ox_charge.set_opacity(1)',
            f'        self.play(',
            f'            ReplacementTransform(red_charge_txt, new_red_charge),',
            f'            ReplacementTransform(ox_charge_txt, new_ox_charge),',
            f'            run_time={rt_charges:.3f}',
            f'        )',
        ]
        elapsed += rt_charges
        if hold_ch > 0.05:
            lines += [f'        self.wait({hold_ch:.3f})']
            elapsed += hold_ch

        # e5: half reactions
        lines += [
            f'        half_grp.set_opacity(1)',
            f'        self.play(',
            f'            FadeIn(half_ox_box), Write(half_ox_txt),',
            f'            run_time={rt_half * 0.5:.3f}',
            f'        )',
            f'        self.play(',
            f'            FadeIn(half_red_box), Write(half_red_txt),',
            f'            run_time={rt_half * 0.5:.3f}',
            f'        )',
        ]
        elapsed += rt_half
        if hold_hf > 0.05:
            lines += [f'        self.wait({hold_hf:.3f})']
            elapsed += hold_hf

        # e6: OIL-RIG
        if show_oil:
            lines += [
                f'        oilrig_grp.set_opacity(1)',
                f'        self.play(',
                f'            FadeIn(oil_rig_box),',
                f'            Write(oil_txt),',
                f'            Write(rig_txt),',
                f'            run_time={rt_oil:.3f}',
                f'        )',
            ]
            elapsed += rt_oil
            if hold_oil > 0.05:
                lines += [f'        self.wait({hold_oil:.3f})']
                elapsed += hold_oil

        # e7: summary
        lines += [
            f'        summary_txt.set_opacity(1)',
            f'        self.play(Write(summary_txt), run_time={rt_summary:.3f})',
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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _charge_sup(charge: int) -> str:
    """Return superscript-style charge string: 2 → '²⁺', -2 → '²⁻', 0 → ''."""
    if charge == 0:
        return ""
    mag = abs(charge)
    sign = "⁺" if charge > 0 else "⁻"
    digits = {1:"¹", 2:"²", 3:"³", 4:"⁴", 5:"⁵"}
    return f"{digits.get(mag, str(mag))}{sign}"


def _charge_str(charge: int) -> str:
    """Human-readable oxidation state: 0 → '0', 2 → '+2', -2 → '-2'."""
    if charge == 0:
        return "0"
    return f"+{charge}" if charge > 0 else str(charge)