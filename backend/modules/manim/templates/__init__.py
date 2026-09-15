"""Manim Scene base classes for chalkboard visuals.

Pipeline templates live in ``modules.templates``; this package only exports
reusable Scene subclasses used by generated code.
"""
from modules.manim.templates.chalkboard_scene import ChalkboardScene
from modules.manim.templates.concept_card import ConceptCardScene
from modules.manim.templates.comparison_scene import ComparisonScene
from modules.manim.templates.equation_scene import EquationScene
from modules.manim.templates.timeline_scene import TimelineScene
from modules.manim.templates.diagram_scene import DiagramScene

__all__ = [
    "ChalkboardScene",
    "ConceptCardScene",
    "ComparisonScene",
    "EquationScene",
    "TimelineScene",
    "DiagramScene",
]
