"""Freeform template: the LLM authors a complete Manim scene directly.

Used when no deterministic concept template fits the topic (e.g., abstract
chemistry, biology, novel physics scenarios). Selected by the planner via
``concept_template: "freeform"``. The generated script must:

- expose ``class GeneratedScene(Scene)`` with a ``construct`` method
- import ``from manim import *`` and ``import numpy as np``
- last as close as possible to ``timeline['audio_duration']`` (we pad with a
  trailing ``self.wait`` if the LLM under-runs).

Strict guardrails block VoiceoverScene / external audio embeds, ensure dark
background, and inject our standard fade-out tail.
"""
from __future__ import annotations

import re
from typing import Any

from modules.config import NVIDIA_PLANNER_MODEL, get_logger
from modules.llm.nvidia_client import NvidiaClient
from modules.manim.code_sanitize import has_latex_mobjects, strip_latex_mobjects

logger = get_logger(__name__)

FREEFORM_SYSTEM = """You are an expert Manim Community Edition (v0.18+) animator.
You write COMPLETE, runnable Python files for short educational physics/science scenes.

HARD RULES:
- Output ONE Python file, NO markdown fences, NO commentary.
- Top of file: `from manim import *` then `import numpy as np`.
- Define exactly: `class GeneratedScene(Scene):` with `construct(self)`.
- First line of construct: `self.camera.background_color = "#0f1117"`.
- Do NOT import or subclass VoiceoverScene. Do NOT use add_sound, SVGMobject, ImageMobject, or external files.
- Only Manim built-ins: Text, Arrow, Line, Rectangle, Circle, Dot, VGroup, Axes, NumberPlane, ParametricFunction, ValueTracker, always_redraw, Create, Write, FadeIn, FadeOut, Transform, GrowArrow, MoveAlongPath, ReplacementTransform, AnimationGroup, LaggedStart.
- NEVER use MathTex or Tex (LaTeX is not available). Use Text() for equations, e.g. Text("W = F × d").
- Keep total animation time CLOSE TO the requested audio duration (use self.wait(...) to pad).
- SAFE AREA: keep all mobjects within x in [-6.6, 6.6] and y in [-3.6, 3.6]. Title band at y≈3.2; captions at y≈-3.2.
- Title: one line, to_edge(UP, buff=0.35), use scale_to_fit_width(12.0) if long.
- Body text: use Text(..., width=5.0) for wrapping or scale_to_fit_width before placing.
- Use .next_to or .arrange with buff>=0.4. Never stack overlapping labels.
- Prefer LaggedStart(..., lag_ratio=0.15) and rate_func=smooth for reveals.
- Use color hexes: title "#e0e6f0", body "#c8d3e6", accents "#4f8ef7" / "#41d4a8" / "#ff7a59".
- End with: `self.play(FadeOut(*self.mobjects), run_time=0.40)`.
- Never use .get_edge(); use .get_left/right/top/bottom().
"""

FREEFORM_PROMPT = """Generate a single Manim scene for the following plan.

SCENE TITLE: {title}
LEARNING GOAL: {learning_goal}
ANCHOR EXAMPLE / SCENARIO: {anchor_example}
TARGET AUDIO DURATION: {audio_duration:.2f} seconds (animation total must be <= this; pad with self.wait)
NARRATION (the visuals must mirror this script):
\"\"\"
{narration}
\"\"\"

ANCHOR PHRASES — visually emphasize when each is spoken (estimate timing by phrase order):
{anchor_phrases}

{learner_context}

DESIGN GUIDELINES:
- Build a UNIQUE visual specific to this scene's anchor example — do NOT reuse the same diagram across scenes.
- Show 1-3 distinct visual stages tied to the narration beats.
- For abstract concepts, use diagrams, arrows, transitions, or labeled symbols — not just text.
- Equations: use Text() with Unicode symbols (×, Δ, θ) — never MathTex/Tex.
- Prefer FadeIn/Write for entrances, Transform for evolutions, FadeOut between stages.

Return ONLY the complete Python file.
"""


class FreeformTemplate:
    """Lets the LLM author the Manim scene for arbitrary topics."""

    ALLOWED_EVENTS = {
        "place_title", "highlight", "show", "explain", "transform",
        "compare", "summarize", "hold", "label", "equation", "diagram",
    }
    SLOTS = {}

    @staticmethod
    def compile(plan: dict[str, Any], timeline: dict[str, Any]) -> str:
        scene_id = plan.get("scene_id", 0)
        title = plan.get("title", f"Scene {scene_id}")
        learning_goal = plan.get("learning_goal", "")
        anchor_example = plan.get("anchor_example", "")
        narration = plan.get("narration", "")
        audio_duration = float(timeline.get("audio_duration", 9.0))
        learner_context = plan.get("_learner_context", "")

        anchor_phrases = [
            ev.get("anchor_phrase", "")
            for ev in plan.get("events", [])
            if ev.get("anchor_phrase")
        ]
        phrase_block = "\n".join(f'  - "{p}"' for p in anchor_phrases) or "  (none)"

        prompt = FREEFORM_PROMPT.format(
            title=title,
            learning_goal=learning_goal,
            anchor_example=anchor_example,
            audio_duration=audio_duration,
            narration=narration.strip(),
            anchor_phrases=phrase_block,
            learner_context=learner_context or "",
        )

        try:
            client = NvidiaClient()
            text = client.chat(
                NVIDIA_PLANNER_MODEL,
                [
                    {"role": "system", "content": FREEFORM_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.55,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.warning("Freeform LLM authoring failed for scene %s: %s", scene_id, exc)
            return _stub_scene(title, learning_goal, audio_duration)

        code = _strip_fences(text).strip()
        code = _sanitize(code)
        if has_latex_mobjects(code):
            code = strip_latex_mobjects(code)
        if "class GeneratedScene" not in code or "def construct" not in code:
            logger.warning("Freeform output invalid for scene %s; using stub", scene_id)
            return _stub_scene(title, learning_goal, audio_duration)
        return code


def _strip_fences(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    return text


_BANNED_PATTERNS = (
    r"from\s+manim_voiceover",
    r"VoiceoverScene",
    r"add_sound\s*\(",
    r"SVGMobject\s*\(",
    r"ImageMobject\s*\(",
)

# Static replacement string — never embed the raw regex pattern in the
# replacement arg of re.sub(). In Python 3.12+ unrecognised backslash
# sequences like \s and \( in the replacement string raise re.error.
_SANITIZE_REPLACEMENT = "# [sanitized]"


def _sanitize(code: str) -> str:
    for pat in _BANNED_PATTERNS:
        try:
            code = re.sub(pat, _SANITIZE_REPLACEMENT, code)
        except re.error as exc:
            logger.warning("Sanitize pattern %r failed: %s — skipping", pat, exc)
    if "from manim import" not in code:
        code = "from manim import *\nimport numpy as np\n\n" + code
    if "import numpy" not in code:
        code = code.replace("from manim import *", "from manim import *\nimport numpy as np", 1)
    return code


def _stub_scene(title: str, goal: str, audio_dur: float) -> str:
    pad = max(0.5, audio_dur - 2.0)
    return f"""from manim import *
import numpy as np


class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "#0f1117"
        title = Text({title!r}, font_size=44, weight=BOLD, color="#e0e6f0")
        title.to_edge(UP, buff=0.5)
        goal = Text({goal!r}, font_size=26, color="#c8d3e6")
        goal.next_to(title, DOWN, buff=0.6)
        self.play(Write(title), run_time=0.9)
        self.play(FadeIn(goal, shift=UP*0.2), run_time=0.8)
        self.wait({pad:.2f})
        self.play(FadeOut(*self.mobjects), run_time=0.40)
"""
