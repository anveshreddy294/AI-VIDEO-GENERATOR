# modules/manim/compiler.py

from templates.concept_card import ConceptCardScene
from templates.chalkboard import ChalkboardScene
from templates.equation import EquationScene

TEMPLATE_MAP = {
    "concept_card":  ConceptCardScene,
    "chalkboard":    ChalkboardScene,
    "equation":      EquationScene,
    "diagram":       DiagramScene,
    "comparison":    ComparisonScene,
    "timeline":      TimelineScene,
}

def compile_scene(skeleton_json: dict, timeline_json: dict) -> str:
    """
    Generates final Manim Python file from skeleton + timeline.
    LLM never writes this Python. Templates are pre-written.
    """
    template_name = skeleton_json["template"]
    TemplateClass = TEMPLATE_MAP[template_name]
    
    # Inject timing from sync engine
    content = inject_timing(skeleton_json, timeline_json)
    
    # Generate Python that instantiates the template with content
    scene_code = f"""
from manim import *
from modules.manim.templates.{template_name} import {TemplateClass.__name__}
from modules.manim.style_config import *

class GeneratedScene({TemplateClass.__name__}):
    def construct(self):
        self.build_scene(
            main_title={repr(content['main_title'])},
            cards={repr(content.get('cards', []))}
        )
"""
    return scene_code
