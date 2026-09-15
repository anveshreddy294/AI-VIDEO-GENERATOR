"""Chemical Equilibrium template.

Visual sequence:
  1. Title + reaction equation (A + B ⇌ C + D) written on screen
  2. Concentration bar chart appears: reactants tall, products zero
  3. Equilibrium double arrow pulses — system reaches equilibrium
  4. Bars animate to equilibrium concentrations
  5. Keq expression + value badge appear
  6. Perturbation event (optional): stress bar highlight + Le Chatelier label
  7. Bars shift to new equilibrium
  8. Summary: "System opposes the change"
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
    REACTANT_COLOR,
    PRODUCT_COLOR,
    EQUILIBRIUM_COLOR,
    ENERGY_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    _aid,
    _aparams,
    _indent,
    _esc,
)

KEQ_COLOR      = "#f7c948"
STRESS_COLOR   = "#ff5c8a"
BAR_AXIS_COLOR = "#505878"


class ChemicalEquilibriumTemplate:
    ALLOWED_EVENTS = {
        "place", "show_bars", "reach_equilibrium",
        "show_keq", "perturbation", "shift",
        "summary", "hold",
    }
    SLOTS = {}  # reaction species from plan params
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Le Chatelier's Principle'>",
  "reactants": ["<species A>", "<species B>"],
  "products": ["<species C>", "<species D>"],
  "reaction_label": "<equation string, e.g. 'N₂ + 3H₂ ⇌ 2NH₃'>",
  "perturbation": "increase_reactants|increase_products|increase_pressure|increase_temperature|none",
  "keq_label": "<equilibrium constant expression, e.g. 'Kc = [NH₃]²/[N₂][H₂]³'>"
}
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 15.0))
        title_text = plan.get("title", "Chemical Equilibrium")

        params = plan.get("params", {})
        reactants  = params.get("reactants",  ["A", "B"])
        products   = params.get("products",   ["C", "D"])
        keq_expr   = params.get("keq_expr",   "[C][D] / [A][B]")
        keq_value  = params.get("keq_value",  "1.8 × 10⁻⁵")

        # Equilibrium concentrations (0–1 normalized bar heights)
        react_eq   = params.get("react_eq",   [0.55, 0.55])
        prod_eq    = params.get("prod_eq",    [0.40, 0.40])

        # Perturbation (optional)
        perturb    = params.get("perturbation", "increase [A]")
        do_perturb = params.get("do_perturbation", True)
        react_new  = params.get("react_new",   [0.45, 0.45])
        prod_new   = params.get("prod_new",    [0.55, 0.55])

        all_species   = reactants + products
        n_species     = len(all_species)
        bar_colors    = [REACTANT_COLOR] * len(reactants) + [PRODUCT_COLOR] * len(products)
        bar_init      = [0.95] * len(reactants) + [0.02] * len(products)
        bar_eq_vals   = react_eq + prod_eq
        bar_new_vals  = react_new + prod_new

        # Layout
        bar_w    = 0.55
        bar_gap  = 0.20
        bar_maxh = 2.8
        chart_x0 = -((n_species - 1) * (bar_w + bar_gap)) / 2
        axis_y   = -1.8

        _evs = plan.get("events", [])
        rt_place   = event_rt_type(timeline, _evs, "place",             "e0", 0.7)
        rt_bars    = event_rt_type(timeline, _evs, "show_bars",         "e1", 0.9)
        hold_bars  = event_hold(timeline, "e1", 0.35)
        rt_equil   = event_rt_type(timeline, _evs, "reach_equilibrium", "e2", 1.4)
        hold_equil = event_hold(timeline, "e2", 0.5)
        rt_keq     = event_rt_type(timeline, _evs, "show_keq",          "e3", 0.7)
        hold_keq   = event_hold(timeline, "e3", 0.4)
        rt_perturb = event_rt_type(timeline, _evs, "perturbation",      "e4", 0.7)
        hold_pert  = event_hold(timeline, "e4", 0.4)
        rt_shift   = event_rt_type(timeline, _evs, "shift",             "e5", 1.0)
        hold_shift = event_hold(timeline, "e5", 0.4)
        rt_summary = event_rt_type(timeline, _evs, "summary",           "e6", 0.65)
        hold_sum   = event_hold(timeline, "e6", 0.5)

        lines: list[str] = [_HEADER]

        # Title
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=36, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.3)',
            "",
        ]

        # Reaction equation
        react_str = " + ".join(reactants)
        prod_str  = " + ".join(products)
        equation  = f"{react_str}  \u21cc  {prod_str}"
        lines += [
            f'        equation = Text("{_esc(equation)}", font_size=28, color="{TEXT_COLOR}")',
            f'        equation.to_edge(UP, buff=0.72)',
            f'        equation.set_opacity(0)',
            "",
        ]

        # Equilibrium arrow annotation
        lines += [
            f'        eq_arrow = DoubleArrow(LEFT*0.5, RIGHT*0.5,'
            f' color="{EQUILIBRIUM_COLOR}", stroke_width=3, buff=0)',
            f'        eq_arrow.move_to(np.array([0.0, 1.05, 0]))',
            f'        eq_arrow.set_opacity(0)',
            "",
        ]

        # Chart axis
        axis_len = (n_species + 0.5) * (bar_w + bar_gap)
        lines += [
            f'        axis = Line(',
            f'            np.array([{chart_x0 - bar_w:.3f}, {axis_y:.3f}, 0]),',
            f'            np.array([{chart_x0 + axis_len:.3f}, {axis_y:.3f}, 0]),',
            f'            color="{BAR_AXIS_COLOR}", stroke_width=2',
            f'        )',
            f'        conc_lbl = Text("[conc]", font_size=16, color="{LABEL_COLOR}")',
            f'        conc_lbl.next_to(axis, LEFT, buff=0.08)',
            "",
        ]

        # Bars
        for i, (sp, col, h_init) in enumerate(zip(all_species, bar_colors, bar_init)):
            bx = chart_x0 + i * (bar_w + bar_gap)
            bh = h_init * bar_maxh
            by = axis_y + bh / 2
            lines += [
                f'        bar_{i} = Rectangle(width={bar_w:.3f}, height={bh:.3f},'
                f' color="{col}", fill_color="{col}", fill_opacity=0.80, stroke_width=1)',
                f'        bar_{i}.move_to(np.array([{bx:.3f}, {by:.3f}, 0]))',
                f'        bar_{i}_lbl = Text("{_esc(sp)}", font_size=18, color="{TITLE_COLOR}")',
                f'        bar_{i}_lbl.move_to(np.array([{bx:.3f}, {axis_y - 0.28:.3f}, 0]))',
                f'        bar_{i}_grp = VGroup(bar_{i}, bar_{i}_lbl)',
            ]
        bar_vars = ", ".join(f'bar_{i}_grp' for i in range(n_species))
        lines += [
            f'        bars_grp = VGroup({bar_vars})',
            f'        bars_grp.set_opacity(0)',
            "",
        ]

        # Keq box
        lines += [
            f'        keq_box = RoundedRectangle(corner_radius=0.15, width=4.6, height=1.05,'
            f' color="{KEQ_COLOR}", fill_opacity=0.08, stroke_width=1.5)',
            f'        keq_box.to_edge(RIGHT, buff=0.25).shift(UP*0.5)',
            f'        keq_expr_text = Text("K_eq = {_esc(keq_expr)}", font_size=20, color="{TITLE_COLOR}")',
            f'        keq_val_text = Text("= {_esc(keq_value)}", font_size=20, weight=BOLD, color="{KEQ_COLOR}")',
            f'        keq_expr_text.move_to(keq_box.get_center() + UP*0.22)',
            f'        keq_val_text.move_to(keq_box.get_center() + DOWN*0.22)',
            f'        keq_grp = VGroup(keq_box, keq_expr_text, keq_val_text)',
            f'        keq_grp.set_opacity(0)',
            "",
        ]

        # Perturbation label
        if do_perturb:
            lines += [
                f'        perturb_lbl = Text("Stress: {_esc(perturb)}", font_size=20, color="{STRESS_COLOR}")',
                f'        perturb_lbl.to_edge(LEFT, buff=0.3).shift(DOWN*0.2)',
                f'        perturb_lbl.set_opacity(0)',
                f'        lechatlbl = Text("Le Chatelier\'s Principle:", font_size=18, color="{ACCENT3}")',
                f'        lechatlbl.next_to(perturb_lbl, UP, buff=0.1)',
                f'        lechatlbl.set_opacity(0)',
                "",
            ]

        # Summary
        lines += [
            f'        summary = Text("System opposes the change → new equilibrium", font_size=19, color="{ACCENT2}")',
            f'        summary.to_edge(DOWN, buff=0.35)',
            f'        summary.set_opacity(0)',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        lines += [
            f'        self.play(Write(title), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        lines += [
            f'        equation.set_opacity(1)',
            f'        self.play(Write(equation), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        lines += [
            f'        bars_grp.set_opacity(1)',
            f'        self.play(FadeIn(axis, conc_lbl, bars_grp), run_time={rt_bars:.3f})',
        ]
        elapsed += rt_bars
        if hold_bars > 0.05:
            lines += [f'        self.wait({hold_bars:.3f})']
            elapsed += hold_bars

        # Animate bars to equilibrium
        eq_anims = []
        for i, (bx_frac, h_eq) in enumerate(zip(
            [chart_x0 + i * (bar_w + bar_gap) for i in range(n_species)],
            bar_eq_vals
        )):
            new_h = h_eq * bar_maxh
            new_by = axis_y + new_h / 2
            eq_anims.append(
                f'            bar_{i}.animate.become(Rectangle(width={bar_w:.3f},'
                f' height={new_h:.3f}, color="{bar_colors[i]}",'
                f' fill_color="{bar_colors[i]}", fill_opacity=0.80, stroke_width=1))'
                f'.move_to(np.array([{bx_frac:.3f}, {new_by:.3f}, 0]))'
            )
        lines += [
            f'        eq_arrow.set_opacity(1)',
            f'        self.play(',
            f'            FadeIn(eq_arrow),',
            *[a + ',' for a in eq_anims],
            f'            run_time={rt_equil:.3f}',
            f'        )',
        ]
        elapsed += rt_equil
        if hold_equil > 0.05:
            lines += [f'        self.wait({hold_equil:.3f})']
            elapsed += hold_equil

        # Keq
        lines += [
            f'        keq_grp.set_opacity(1)',
            f'        self.play(FadeIn(keq_box), Write(keq_expr_text), Write(keq_val_text), run_time={rt_keq:.3f})',
        ]
        elapsed += rt_keq
        if hold_keq > 0.05:
            lines += [f'        self.wait({hold_keq:.3f})']
            elapsed += hold_keq

        # Perturbation
        if do_perturb:
            lines += [
                f'        lechatlbl.set_opacity(1)',
                f'        perturb_lbl.set_opacity(1)',
                f'        self.play(FadeIn(lechatlbl, perturb_lbl), run_time={rt_perturb:.3f})',
            ]
            elapsed += rt_perturb
            if hold_pert > 0.05:
                lines += [f'        self.wait({hold_pert:.3f})']
                elapsed += hold_pert

            # Shift to new equilibrium
            shift_anims = []
            for i, (bx_frac, h_new) in enumerate(zip(
                [chart_x0 + i * (bar_w + bar_gap) for i in range(n_species)],
                bar_new_vals
            )):
                new_h = h_new * bar_maxh
                new_by = axis_y + new_h / 2
                shift_anims.append(
                    f'            bar_{i}.animate.become(Rectangle(width={bar_w:.3f},'
                    f' height={new_h:.3f}, color="{bar_colors[i]}",'
                    f' fill_color="{bar_colors[i]}", fill_opacity=0.80, stroke_width=1))'
                    f'.move_to(np.array([{bx_frac:.3f}, {new_by:.3f}, 0]))'
                )
            lines += [
                f'        self.play(',
                *[a + ',' for a in shift_anims],
                f'            run_time={rt_shift:.3f}',
                f'        )',
            ]
            elapsed += rt_shift
            if hold_shift > 0.05:
                lines += [f'        self.wait({hold_shift:.3f})']
                elapsed += hold_shift

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