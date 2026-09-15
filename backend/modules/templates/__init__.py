"""Concept template registry for educational Manim scene generation."""
from __future__ import annotations

from modules.templates.mechanics.intro import IntroTemplate
from modules.templates.mechanics.inertia import InertiaTemplate
from modules.templates.mechanics.force import ForceTemplate
from modules.templates.mechanics.acceleration import AccelerationTemplate
from modules.templates.mechanics.friction import FrictionTemplate
from modules.templates.mechanics.projectile import ProjectileTemplate
from modules.templates.mechanics.inclined_plane import InclinedPlaneTemplate
from modules.templates.mechanics.magnetism import MagnetismTemplate
from modules.templates.mechanics.circular_motion import CircularMotionTemplate
from modules.templates.mechanics.gravitation import GravitationTemplate
from modules.templates.mechanics.momentum import MomentumTemplate
from modules.templates.mechanics.free_fall import FreeFallTemplate
from modules.templates.mechanics.shm import SimpleHarmonicMotionTemplate
from modules.templates.mechanics.torque import TorqueTemplate
from modules.templates.mechanics.work_energy import WorkEnergyTemplate
from modules.templates.mechanics.summary import SummaryTemplate
from modules.templates.freeform import FreeformTemplate
from modules.templates.explain.concept_card import ConceptCardTemplate
from modules.templates.explain.comparison import ComparisonTemplate
from modules.templates.explain.equation import EquationTemplate
from modules.templates.explain.timeline import TimelineTemplate
from modules.templates.explain.diagram import DiagramTemplate
from modules.templates.explain import EXPLAIN_TEMPLATE_IDS
from modules.templates.chemistry import (
    CHEMISTRY_TEMPLATE_IDS,
    CHEMISTRY_TEMPLATES,
)

MECHANICS_TEMPLATE_IDS = [
    "intro",
    "inertia",
    "force",
    "acceleration",
    "friction",
    "projectile",
    "inclined_plane",
    "magnetism",
    "circular_motion",
    "gravitation",
    "momentum",
    "free_fall",
    "shm",
    "torque",
    "work_energy",
    "summary",
]

TEMPLATES: dict[str, type] = {
    # ── Bookends ──────────────────────────────────────────────────────────
    "intro":           IntroTemplate,
    "summary":         SummaryTemplate,
    # ── Mechanics (physics simulation) ───────────────────────────────────
    "inertia":         InertiaTemplate,
    "force":           ForceTemplate,
    "acceleration":    AccelerationTemplate,
    "friction":        FrictionTemplate,
    "projectile":      ProjectileTemplate,
    "inclined_plane":  InclinedPlaneTemplate,
    "magnetism":       MagnetismTemplate,
    "circular_motion": CircularMotionTemplate,
    "gravitation":     GravitationTemplate,
    "momentum":        MomentumTemplate,
    "free_fall":       FreeFallTemplate,
    "shm":             SimpleHarmonicMotionTemplate,
    "torque":          TorqueTemplate,
    "work_energy":     WorkEnergyTemplate,
    # ── Explain (chalkboard explanation) ─────────────────────────────────
    "concept_card":    ConceptCardTemplate,
    "comparison":      ComparisonTemplate,
    "equation":        EquationTemplate,
    "timeline":        TimelineTemplate,
    "diagram":         DiagramTemplate,
    # ── Chemistry ────────────────────────────────────────────────────────
    **CHEMISTRY_TEMPLATES,
    # ── Fallback ─────────────────────────────────────────────────────────
    "freeform":        FreeformTemplate,
}

VALID_TEMPLATE_IDS: list[str] = sorted(TEMPLATES)

__all__ = [
    "TEMPLATES",
    "VALID_TEMPLATE_IDS",
    "MECHANICS_TEMPLATE_IDS",
    "EXPLAIN_TEMPLATE_IDS",
    "CHEMISTRY_TEMPLATE_IDS",
    "CHEMISTRY_TEMPLATES",
]
