"""Rutherford Gold Foil Experiment template.

Semantic tags : atomic-structure, rutherford-model, nuclear-model, alpha-scattering
Visualizable  : gold foil experiment, alpha particle scattering, nucleus discovery,
                plum pudding model refutation, deflection angles

Visual sequence:
  1. Title + brief label: "Rutherford, 1909"
  2. Radioactive source emits alpha particles (stream of dots moving right)
  3. Gold foil appears as vertical band in the centre
  4. Three scattering paths animate simultaneously:
       a. Most particles pass straight through (no deflection)
       b. A few deflect at small angles
       c. Very few bounce almost straight back (~180°)
  5. Nucleus dot materialises at the foil centre, labeled "Nucleus"
  6. Observation summary text builds line by line:
       "Most pass through → atom is mostly empty space"
       "Some deflect  → concentrated positive charge"
       "Few bounce back → dense nucleus at centre"
  7. Old plum-pudding model (diffuse sphere) fades in left, gets X'd out
  8. Nuclear model diagram fades in right with tiny nucleus dot and orbit ring

All paths use ArcBetweenPoints so particle trajectories are curved (physically accurate).
event.start values from sync engine are consumed for beat-precise synchronisation.
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
    ENERGY_COLOR,
    event_rt,
    event_rt_type,
    event_hold,
    event_start,
    _esc,
)

ALPHA_COLOR     = "#f7c948"   # gold — alpha particles
FOIL_COLOR      = "#b8860b"   # dark gold — gold foil
STRAIGHT_COLOR  = "#4fc3f7"   # sky blue — undeflected beam
DEFLECT_COLOR   = "#41d4a8"   # teal — small deflection
BOUNCE_COLOR    = "#ff5c8a"   # pink-red — large deflection / back-scatter
NUCLEUS_DOT_CLR = "#ff7a59"   # orange-red — nucleus
PLUM_COLOR      = "#7c5cbf"   # purple — plum pudding model
WRONG_COLOR     = "#ff3c3c"   # red X


class RutherfordGoldFoilTemplate:
    ALLOWED_EVENTS = {
        "place", "emit_alpha", "show_foil",
        "scatter_paths", "show_nucleus",
        "observations", "old_model", "new_model", "hold",
    }
    SLOTS = {}
    CONTENT_SCHEMA = """{
  "title": "<scene title, e.g. 'Rutherford Gold Foil Experiment'>",
  "year": "1909",
  "show_plum_pudding_contrast": true,
  "alpha_source_label": "<label for source, e.g. 'α source (Ra)'>",
  "foil_label": "Gold foil (0.00004 cm thick)",
  "detector_label": "ZnS fluorescent screen",
  "observation_lines": [
    "Most α-particles pass straight through",
    "Some deflect at small angles",
    "Very few bounce back (>90°)"
  ],
  "conclusion": "Atom has a tiny, dense, positively-charged nucleus"
}
All fields are optional; defaults are provided.
"""

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        audio_dur  = float(timeline.get("audio_duration", 18.0))
        title_text = plan.get("title", "Rutherford Gold Foil Experiment")

        params = plan.get("params", {})
        year_label    = params.get("year",          "1909")
        src_label     = params.get("alpha_source_label", "α source")
        foil_label    = params.get("foil_label",    "Gold foil")
        det_label     = params.get("detector_label","ZnS screen")
        show_contrast = params.get("show_plum_pudding_contrast", True)
        obs_lines     = params.get("observation_lines", [
            "Most pass through → mostly empty space",
            "Some deflect → positive charge concentrated",
            "Few bounce back → dense nucleus exists",
        ])
        conclusion    = params.get("conclusion",
            "Atom has a tiny, dense, positively-charged nucleus")

        _evs = plan.get("events", [])

        rt_place    = event_rt_type(timeline, _evs, "place",         "e0", 0.65)
        rt_emit     = event_rt_type(timeline, _evs, "emit_alpha",    "e1", 1.0)
        hold_emit   = event_hold(timeline, "e1", 0.3)
        rt_foil     = event_rt_type(timeline, _evs, "show_foil",     "e2", 0.6)
        hold_foil   = event_hold(timeline, "e2", 0.25)
        rt_scatter  = event_rt_type(timeline, _evs, "scatter_paths", "e3", 2.0)
        hold_scat   = event_hold(timeline, "e3", 0.5)
        rt_nucleus  = event_rt_type(timeline, _evs, "show_nucleus",  "e4", 0.7)
        hold_nuc    = event_hold(timeline, "e4", 0.4)
        rt_obs      = event_rt_type(timeline, _evs, "observations",  "e5", 1.0)
        hold_obs    = event_hold(timeline, "e5", 0.5)
        rt_old      = event_rt_type(timeline, _evs, "old_model",     "e6", 0.7)
        hold_old    = event_hold(timeline, "e6", 0.4)
        rt_new      = event_rt_type(timeline, _evs, "new_model",     "e7", 0.7)
        hold_new    = event_hold(timeline, "e7", 0.5)

        # Layout constants
        src_x  = -5.0
        foil_x =  0.0
        det_x  =  4.8
        beam_y =  0.2    # central beam y-axis

        lines: list[str] = [_HEADER]

        # ── Title ──────────────────────────────────────────────────
        lines += [
            f'        title = Text("{_esc(title_text)}", font_size=34, weight=BOLD, color="{TITLE_COLOR}")',
            f'        title.to_edge(UP, buff=0.28)',
            f'        year_lbl = Text("{_esc(year_label)}", font_size=18, color="{LABEL_COLOR}")',
            f'        year_lbl.next_to(title, RIGHT, buff=0.3)',
            "",
        ]

        # ── Radioactive source ──────────────────────────────────────
        lines += [
            f'        source_box = RoundedRectangle(corner_radius=0.12, width=0.9, height=0.6,',
            f'            color="{ALPHA_COLOR}", fill_color="{ALPHA_COLOR}", fill_opacity=0.25,',
            f'            stroke_width=2)',
            f'        source_box.move_to(np.array([{src_x:.2f}, {beam_y:.2f}, 0]))',
            f'        source_lbl = Text("{_esc(src_label)}", font_size=15, color="{ALPHA_COLOR}")',
            f'        source_lbl.next_to(source_box, DOWN, buff=0.12)',
            f'        source_grp = VGroup(source_box, source_lbl)',
            f'        source_grp.set_opacity(0)',
            "",
        ]

        # ── Gold foil ──────────────────────────────────────────────
        lines += [
            f'        foil_rect = Rectangle(width=0.18, height=3.2,',
            f'            color="{FOIL_COLOR}", fill_color="{FOIL_COLOR}", fill_opacity=0.85,',
            f'            stroke_width=2)',
            f'        foil_rect.move_to(np.array([{foil_x:.2f}, {beam_y:.2f}, 0]))',
            f'        foil_lbl = Text("{_esc(foil_label)}", font_size=14, color="{ALPHA_COLOR}")',
            f'        foil_lbl.next_to(foil_rect, UP, buff=0.18)',
            f'        foil_grp = VGroup(foil_rect, foil_lbl)',
            f'        foil_grp.set_opacity(0)',
            "",
        ]

        # ── Detector arc ───────────────────────────────────────────
        lines += [
            f'        detector_arc = Arc(radius=3.8, start_angle=-PI*0.65, angle=PI*1.3,',
            f'            color="{LABEL_COLOR}", stroke_width=2, stroke_opacity=0.5)',
            f'        detector_arc.move_to(np.array([{foil_x:.2f}, {beam_y:.2f}, 0]))',
            f'        det_lbl = Text("{_esc(det_label)}", font_size=13, color="{LABEL_COLOR}")',
            f'        det_lbl.move_to(np.array([{det_x:.2f}, {beam_y + 2.3:.2f}, 0]))',
            f'        detector_grp = VGroup(detector_arc, det_lbl)',
            f'        detector_grp.set_opacity(0)',
            "",
        ]

        # ── Alpha particle stream (initial incoming beam) ───────────
        n_stream = 5
        stream_ys = [beam_y + (i - n_stream // 2) * 0.28 for i in range(n_stream)]
        for i, sy in enumerate(stream_ys):
            lines += [
                f'        alpha_{i} = Dot(radius=0.09, color="{ALPHA_COLOR}", fill_opacity=0.9)',
                f'        alpha_{i}.move_to(np.array([{src_x + 0.55:.3f}, {sy:.3f}, 0]))',
                f'        alpha_{i}.set_opacity(0)',
            ]
        alpha_vars = ", ".join(f"alpha_{i}" for i in range(n_stream))
        lines += [
            f'        alpha_stream = VGroup({alpha_vars})',
            "",
        ]

        # ── Scattering paths ───────────────────────────────────────
        # Path A: straight through (3 particles)
        for i in range(3):
            sy = beam_y + (i - 1) * 0.4
            lines += [
                f'        p_straight_{i} = Dot(radius=0.09, color="{STRAIGHT_COLOR}", fill_opacity=0.9)',
                f'        p_straight_{i}.move_to(np.array([{src_x + 0.6:.3f}, {sy:.3f}, 0]))',
                f'        path_straight_{i} = Line(',
                f'            np.array([{src_x + 0.6:.3f}, {sy:.3f}, 0]),',
                f'            np.array([{det_x:.3f}, {sy:.3f}, 0])',
                f'        )',
                f'        path_straight_{i}.set_stroke(color="{STRAIGHT_COLOR}", width=1.2, opacity=0.4)',
            ]

        # Path B: small deflection upward (1 particle)
        def_start_y = beam_y + 0.55
        def_end_y   = beam_y + 1.6
        lines += [
            f'        p_deflect = Dot(radius=0.10, color="{DEFLECT_COLOR}", fill_opacity=0.9)',
            f'        p_deflect.move_to(np.array([{src_x + 0.6:.3f}, {def_start_y:.3f}, 0]))',
            f'        path_deflect = ArcBetweenPoints(',
            f'            np.array([{src_x + 0.6:.3f}, {def_start_y:.3f}, 0]),',
            f'            np.array([{det_x:.3f}, {def_end_y:.3f}, 0]),',
            f'            angle=-PI/6',
            f'        )',
            f'        path_deflect.set_stroke(color="{DEFLECT_COLOR}", width=1.5, opacity=0.5)',
        ]

        # Path C: large back-scatter (1 particle)
        back_start_y = beam_y - 0.2
        lines += [
            f'        p_bounce = Dot(radius=0.11, color="{BOUNCE_COLOR}", fill_opacity=0.9)',
            f'        p_bounce.move_to(np.array([{src_x + 0.6:.3f}, {back_start_y:.3f}, 0]))',
            f'        # Bounce path: goes toward foil then arcs sharply back',
            f'        path_bounce_in = Line(',
            f'            np.array([{src_x + 0.6:.3f}, {back_start_y:.3f}, 0]),',
            f'            np.array([{foil_x - 0.25:.3f}, {back_start_y:.3f}, 0])',
            f'        )',
            f'        path_bounce_out = ArcBetweenPoints(',
            f'            np.array([{foil_x - 0.25:.3f}, {back_start_y:.3f}, 0]),',
            f'            np.array([{src_x + 1.0:.3f}, {back_start_y + 0.55:.3f}, 0]),',
            f'            angle=PI*0.75',
            f'        )',
            f'        path_bounce_in.set_stroke(color="{BOUNCE_COLOR}", width=2, opacity=0.5)',
            f'        path_bounce_out.set_stroke(color="{BOUNCE_COLOR}", width=2, opacity=0.5)',
            "",
        ]

        # Path labels
        lines += [
            f'        lbl_straight = Text("Most: pass straight through", font_size=15, color="{STRAIGHT_COLOR}")',
            f'        lbl_straight.move_to(np.array([2.0, {beam_y + 1.45:.3f}, 0]))',
            f'        lbl_straight.set_opacity(0)',
            f'        lbl_deflect = Text("Some: small deflection", font_size=15, color="{DEFLECT_COLOR}")',
            f'        lbl_deflect.move_to(np.array([2.6, {def_end_y + 0.32:.3f}, 0]))',
            f'        lbl_deflect.set_opacity(0)',
            f'        lbl_bounce = Text("Very few: bounce back!", font_size=15, weight=BOLD, color="{BOUNCE_COLOR}")',
            f'        lbl_bounce.move_to(np.array([-1.8, {back_start_y - 0.9:.3f}, 0]))',
            f'        lbl_bounce.set_opacity(0)',
            "",
        ]

        # ── Nucleus dot at foil centre ─────────────────────────────
        lines += [
            f'        nucleus_dot = Dot(radius=0.14, color="{NUCLEUS_DOT_CLR}", fill_opacity=1.0)',
            f'        nucleus_dot.move_to(np.array([{foil_x:.2f}, {beam_y:.2f}, 0]))',
            f'        nucleus_ring = Circle(radius=0.28, color="{NUCLEUS_DOT_CLR}",',
            f'            stroke_width=2, stroke_opacity=0.5, fill_opacity=0)',
            f'        nucleus_ring.move_to(nucleus_dot.get_center())',
            f'        nucleus_nametag = Text("Nucleus", font_size=16, color="{NUCLEUS_DOT_CLR}")',
            f'        nucleus_nametag.next_to(nucleus_dot, RIGHT, buff=0.3)',
            f'        nucleus_grp = VGroup(nucleus_dot, nucleus_ring, nucleus_nametag)',
            f'        nucleus_grp.set_opacity(0)',
            "",
        ]

        # ── Observations box ───────────────────────────────────────
        obs_y_start = -1.05
        for i, line_text in enumerate(obs_lines[:3]):
            oy = obs_y_start - i * 0.42
            lines += [
                f'        obs_{i} = Text("{_esc(line_text)}", font_size=17, color="{ACCENT2}")',
                f'        obs_{i}.to_edge(LEFT, buff=0.4)',
                f'        obs_{i}.move_to(np.array([obs_{i}.get_center()[0], {oy:.3f}, 0]))',
                f'        obs_{i}.set_opacity(0)',
            ]
        lines += [""]

        # Conclusion
        lines += [
            f'        conclusion_txt = Text("{_esc(conclusion)}", font_size=18, weight=BOLD, color="{ACCENT3}")',
            f'        conclusion_txt.to_edge(DOWN, buff=0.35)',
            f'        conclusion_txt.set_opacity(0)',
            "",
        ]

        # ── Old model (plum pudding) ───────────────────────────────
        if show_contrast:
            lines += [
                f'        plum_sphere = Circle(radius=0.55, color="{PLUM_COLOR}",',
                f'            fill_color="{PLUM_COLOR}", fill_opacity=0.22, stroke_width=2)',
                f'        plum_sphere.move_to(np.array([-4.0, -2.4, 0]))',
                f'        for _pi in range(5):',
                f'            _px = np.random.uniform(-0.35, 0.35)',
                f'            _py = np.random.uniform(-0.35, 0.35)',
                f'            _pdot = Dot(radius=0.07, color="{ELECTRON_COLOR}", fill_opacity=0.7)',
                f'            _pdot.move_to(plum_sphere.get_center() + np.array([_px, _py, 0]))',
                f'            plum_sphere.add(_pdot)',
                f'        plum_lbl = Text("Thomson Model\\n(Plum Pudding)", font_size=14, color="{PLUM_COLOR}")',
                f'        plum_lbl.next_to(plum_sphere, DOWN, buff=0.12)',
                f'        plum_wrong_x = Cross(plum_sphere, color="{WRONG_COLOR}", stroke_width=3)',
                f'        plum_grp = VGroup(plum_sphere, plum_lbl)',
                f'        plum_grp.set_opacity(0)',
                f'        plum_wrong_x.set_opacity(0)',
                "",
            ]

        # ── New nuclear model sketch ───────────────────────────────
        nuc_cx, nuc_cy = 3.5, -2.4
        lines += [
            f'        new_nucleus = Dot(radius=0.12, color="{NUCLEUS_DOT_CLR}", fill_opacity=1.0)',
            f'        new_nucleus.move_to(np.array([{nuc_cx:.2f}, {nuc_cy:.2f}, 0]))',
            f'        new_orbit = Circle(radius=0.55, color="{ACCENT1}",',
            f'            stroke_width=1.5, stroke_opacity=0.6, fill_opacity=0)',
            f'        new_orbit.move_to(np.array([{nuc_cx:.2f}, {nuc_cy:.2f}, 0]))',
            f'        new_electron = Dot(radius=0.08, color="{ELECTRON_COLOR}", fill_opacity=0.9)',
            f'        new_electron.move_to(np.array([{nuc_cx + 0.55:.2f}, {nuc_cy:.2f}, 0]))',
            f'        new_model_lbl = Text("Nuclear Model\\n(Rutherford)", font_size=14, color="{ACCENT1}")',
            f'        new_model_lbl.next_to(new_orbit, DOWN, buff=0.12)',
            f'        new_model_grp = VGroup(new_nucleus, new_orbit, new_electron, new_model_lbl)',
            f'        new_model_grp.set_opacity(0)',
            "",
        ]

        # ── Animation sequence ─────────────────────────────────────
        elapsed = 0.0

        # e0: title
        lines += [
            f'        self.play(Write(title), FadeIn(year_lbl), run_time={rt_place:.3f})',
        ]
        elapsed += rt_place

        # e1: source appears, alpha stream materialises
        lines += [
            f'        source_grp.set_opacity(1)',
            f'        detector_grp.set_opacity(1)',
            f'        self.play(FadeIn(source_grp, detector_grp), run_time={rt_emit * 0.4:.3f})',
            f'        alpha_stream.set_opacity(1)',
            f'        self.play(',
            f'            *[FadeIn(alpha_{i}) for i in range({n_stream})],',
            f'            run_time={rt_emit * 0.6:.3f}',
            f'        )',
        ]
        elapsed += rt_emit
        if hold_emit > 0.05:
            lines += [f'        self.wait({hold_emit:.3f})']
            elapsed += hold_emit

        # e2: foil appears
        lines += [
            f'        foil_grp.set_opacity(1)',
            f'        self.play(FadeIn(foil_grp), run_time={rt_foil:.3f})',
            f'        self.play(FadeOut(alpha_stream), run_time=0.2)',
        ]
        elapsed += rt_foil
        if hold_foil > 0.05:
            lines += [f'        self.wait({hold_foil:.3f})']
            elapsed += hold_foil

        # e3: scatter all three path types simultaneously
        straight_rt = rt_scatter * 0.55
        lines += [
            f'        # Show paths first (dashed trail), then animate particles',
            f'        self.play(',
            f'            *[Create(path_straight_{i}) for i in range(3)],',
            f'            Create(path_deflect),',
            f'            Create(path_bounce_in),',
            f'            run_time={rt_scatter * 0.35:.3f}',
            f'        )',
            f'        self.play(',
            f'            *[p_straight_{i}.animate.move_to(np.array([{det_x:.3f}, {beam_y + (i-1)*0.4:.3f}, 0])) for i in range(3)],',
            f'            MoveAlongPath(p_deflect, path_deflect),',
            f'            MoveAlongPath(p_bounce, path_bounce_in),',
            f'            run_time={straight_rt:.3f}',
            f'        )',
            f'        self.play(',
            f'            MoveAlongPath(p_bounce, path_bounce_out),',
            f'            Create(path_bounce_out),',
            f'            FadeIn(lbl_straight),',
            f'            run_time={rt_scatter * 0.35:.3f}',
            f'        )',
            f'        lbl_deflect.set_opacity(1)',
            f'        lbl_bounce.set_opacity(1)',
            f'        self.play(FadeIn(lbl_deflect, lbl_bounce), run_time=0.4)',
        ]
        elapsed += rt_scatter
        if hold_scat > 0.05:
            lines += [f'        self.wait({hold_scat:.3f})']
            elapsed += hold_scat

        # e4: nucleus materialises
        lines += [
            f'        nucleus_grp.set_opacity(1)',
            f'        self.play(FadeIn(nucleus_grp, scale=0.5), run_time={rt_nucleus:.3f})',
        ]
        elapsed += rt_nucleus
        if hold_nuc > 0.05:
            lines += [f'        self.wait({hold_nuc:.3f})']
            elapsed += hold_nuc

        # e5: observations appear line by line
        obs_rt_each = rt_obs / max(len(obs_lines[:3]), 1)
        for i in range(len(obs_lines[:3])):
            lines += [
                f'        obs_{i}.set_opacity(1)',
                f'        self.play(FadeIn(obs_{i}), run_time={obs_rt_each:.3f})',
            ]
        elapsed += rt_obs
        if hold_obs > 0.05:
            lines += [f'        self.wait({hold_obs:.3f})']
            elapsed += hold_obs

        # e6: old model with X
        if show_contrast:
            lines += [
                f'        plum_grp.set_opacity(1)',
                f'        self.play(FadeIn(plum_grp), run_time={rt_old * 0.6:.3f})',
                f'        plum_wrong_x.set_opacity(1)',
                f'        self.play(Create(plum_wrong_x), run_time={rt_old * 0.4:.3f})',
            ]
            elapsed += rt_old
            if hold_old > 0.05:
                lines += [f'        self.wait({hold_old:.3f})']
                elapsed += hold_old

        # e7: new nuclear model
        lines += [
            f'        new_model_grp.set_opacity(1)',
            f'        self.play(FadeIn(new_model_grp), run_time={rt_new * 0.5:.3f})',
            f'        conclusion_txt.set_opacity(1)',
            f'        self.play(Write(conclusion_txt), run_time={rt_new * 0.5:.3f})',
        ]
        elapsed += rt_new
        if hold_new > 0.05:
            lines += [f'        self.wait({hold_new:.3f})']
            elapsed += hold_new

        tail = audio_dur - elapsed - 0.40
        if tail > 0.05:
            lines += [f'        self.wait({tail:.3f})']

        lines += ["", _FOOTER]
        return "\n".join(lines)