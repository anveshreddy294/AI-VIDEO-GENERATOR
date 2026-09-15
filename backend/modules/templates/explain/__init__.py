"""Chalkboard explanation templates for conceptual scenes."""
from modules.templates.explain.comparison import ComparisonTemplate
from modules.templates.explain.concept_card import ConceptCardTemplate
from modules.templates.explain.diagram import DiagramTemplate
from modules.templates.explain.equation import EquationTemplate
from modules.templates.explain.timeline import TimelineTemplate

EXPLAIN_TEMPLATE_IDS = [
    "concept_card",
    "comparison",
    "equation",
    "timeline",
    "diagram",
]

__all__ = [
    "ConceptCardTemplate",
    "ComparisonTemplate",
    "EquationTemplate",
    "TimelineTemplate",
    "DiagramTemplate",
    "EXPLAIN_TEMPLATE_IDS",
]
