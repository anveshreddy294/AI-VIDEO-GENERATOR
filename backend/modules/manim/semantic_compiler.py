"""Semantic compiler: dispatches plan + timeline → Manim scene code.

This is the production compiler. It:
  1. Looks up the correct concept template from TEMPLATES registry
  2. Proactively overrides generic/freeform templates with chemistry templates
     when the topic, semantic_tags, or visualizable_elements indicate a
     chemistry domain.
  3. Passes the semantic plan and timed event timeline to template.compile()
  4. Validates the generated code has no raw geometry primitives
  5. Writes the final scene_N.py file

Fallback hierarchy (per scene):
  chemistry template → explain template → intro → stub (on exception)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.config import PATHS, RenderWorkspace, get_logger
from modules.manim.code_sanitize import (
    has_latex_mobjects, strip_latex_mobjects, strip_latex_in_text_literals,
)
from modules.templates import TEMPLATES

logger = get_logger(__name__)

# These are the primitive geometry calls that should NOT appear in
# semantically compiled output — presence means a template bug.
_GEOMETRY_PRIMITIVES = (
    "Line(LEFT",
    "Line(RIGHT",
    "Arrow(LEFT",
    "Arrow(RIGHT",
    "Circle(radius=",
    "Square(side_length=",
    'Rectangle(width=',
)

# Templates the LLM planner may assign that are considered "generic" —
# the chemistry router is consulted to upgrade these when the topic is
# a chemistry domain. "freeform" is always last-resort.
_GENERIC_TEMPLATE_IDS = frozenset({
    "freeform", "intro", "concept_card", "diagram",
    "comparison", "equation", "timeline",
})


def _resolve_template(plan: dict[str, Any]) -> tuple[type, str, str]:
    """Determine the best template class for this plan.

    Returns (template_cls, resolved_id, source_tag).
    """
    template_id = plan.get("concept_template", "intro")
    if template_id == "freeform":
        return TEMPLATES["concept_card"], "concept_card", "fallback_explain"
    scene_id = plan.get("scene_id", "?")
    template_cls = TEMPLATES.get(template_id)

    from modules.templates.chemistry import CHEMISTRY_TEMPLATE_IDS
    if template_id in CHEMISTRY_TEMPLATE_IDS and template_cls is not None:
        logger.info(
            "[TEMPLATE] scene=%s requested=%s resolved=%s source=registered_chemistry",
            scene_id,
            template_id,
            template_id,
        )
        return template_cls, template_id, "registered_chemistry"

    if template_id in _GENERIC_TEMPLATE_IDS or template_cls is None:
        try:
            from modules.planning.chemistry_router import route_chemistry_template
            chem_id = route_chemistry_template(
                topic=plan.get("title", ""),
                scene_role=plan.get("scene_role", ""),
                semantic_tags=plan.get("semantic_tags", []),
                visualizable_elements=plan.get("visualizable_elements", []),
            )
            if chem_id:
                chem_cls = TEMPLATES.get(chem_id)
                if chem_cls:
                    logger.info(
                        "[TEMPLATE] scene=%s requested=%s resolved=%s "
                        "source=router_upgrade topic=%r",
                        scene_id,
                        template_id,
                        chem_id,
                        plan.get("title", ""),
                    )
                    return chem_cls, chem_id, "router_upgrade"
        except Exception as exc:
            logger.debug("Chemistry router error for scene %s: %s", scene_id, exc)

    if template_cls is not None:
        logger.info(
            "[TEMPLATE] scene=%s requested=%s resolved=%s source=registered",
            scene_id,
            template_id,
            template_id,
        )
        return template_cls, template_id, "registered"

    logger.warning(
        "[TEMPLATE][FALLBACK] scene=%s requested=%s resolved=intro "
        "source=fallback_intro reason=unknown_template",
        scene_id,
        template_id,
    )
    return TEMPLATES["intro"], "intro", "fallback_intro"


def _manim_output_dir(workspace: RenderWorkspace | None) -> Path:
    return workspace.manim_dir if workspace is not None else PATHS["manim"]


def semantic_compile(
    plan: dict[str, Any],
    sync_result: dict[str, Any],
    workspace: RenderWorkspace | None = None,
) -> tuple[Path, str]:
    """Compile a Manim scene file from a semantic plan + timed timeline.

    Returns (file_path, scene_code) — the file is written to disk.
    """
    scene_id = plan["scene_id"]
    template_id = plan.get("concept_template", "intro")
    logger.info("Compiling scene %d with template '%s'", scene_id, template_id)

    template_cls, resolved_id, source = _resolve_template(plan)
    if resolved_id in ("freeform", "intro") and source == "fallback_intro":
        logger.warning(
            "[TEMPLATE][FALLBACK] scene=%s using generic template %s",
            scene_id,
            resolved_id,
        )

    timeline = sync_result.get("timeline", {
        "audio_duration": sync_result.get("audio_duration", 8.0),
        "events": [],
    })
    if "audio_duration" not in timeline:
        timeline["audio_duration"] = sync_result.get("audio_duration", 8.0)

    code = template_cls.compile(plan, timeline)
    code = _post_process(code, scene_id)
    mode = "template_fallback" if source.startswith("fallback_") else "semantic"
    code = f"# AICARLS_COMPILE_MODE: {mode}\n" + code
    from modules.manim.code_guard import validate_scene_code
    validate_scene_code(code)

    out_path = _manim_output_dir(workspace) / f"scene_{scene_id}.py"
    out_path.write_text(code, encoding="utf-8")
    logger.info(
        "Semantic Manim code written: %s (%d lines) template=%s",
        out_path,
        code.count("\n"),
        resolved_id,
    )
    return out_path, code


def semantic_compile_all(
    plans: list[dict[str, Any]],
    timelines: list[dict[str, Any]],
    workspace: RenderWorkspace | None = None,
    force_regenerate: bool = True,
    allow_fallback: bool = True,
) -> list[tuple[Path, str]]:
    """Compile all scenes, isolating failures so one bad scene can't kill the video."""
    if force_regenerate:
        logger.info(
            "[SESSION] semantic_compile_all force_regenerate=True workspace=%s",
            workspace.root if workspace else PATHS["manim"],
        )

    timeline_map = {t["scene_id"]: t for t in timelines}
    results: list[tuple[Path, str]] = []
    failed_scenes: list[int] = []

    for plan in plans:
        sid = plan["scene_id"]
        sync = timeline_map.get(sid, {"scene_id": sid, "audio_duration": 8.0, "timeline": {}})
        try:
            if not allow_fallback and (_resolve_template(plan)[2].startswith("fallback_")
                                       or _resolve_template(plan)[1] == "freeform"):
                raise ValueError(f"Unknown semantic template for scene {sid}")
            results.append(semantic_compile(plan, sync, workspace=workspace))
        except Exception as exc:
            if not allow_fallback:
                raise
            logger.error(
                "[TEMPLATE][STUB] scene=%s reason=%s: %s",
                sid,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            failed_scenes.append(sid)
            stub_code = _compile_stub_fallback(plan, sync)
            stub_path = _manim_output_dir(workspace) / f"scene_{sid}.py"
            try:
                stub_path.write_text(stub_code, encoding="utf-8")
            except Exception as write_exc:
                logger.error("Could not write stub for scene %d: %s", sid, write_exc)
            results.append((stub_path, stub_code))

    if failed_scenes:
        logger.warning(
            "semantic_compile_all: %d/%d scenes failed and used stubs: %s",
            len(failed_scenes), len(plans), failed_scenes,
        )

    return results


def _compile_stub_fallback(plan: dict[str, Any], sync_result: dict[str, Any]) -> str:
    """Minimal valid Manim scene used when a template raises during compile."""
    title = plan.get("title", f"Scene {plan.get('scene_id', '?')}")
    goal = plan.get("learning_goal", "")
    audio_dur = float(
        sync_result.get("audio_duration")
        or sync_result.get("timeline", {}).get("audio_duration")
        or 8.0
    )
    pad = max(0.5, audio_dur - 2.5)
    title_safe = title[:60]
    goal_safe = goal[:80] if goal else ""
    return f'''# AICARLS_COMPILE_MODE: stub
from manim import *
import numpy as np


class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "#0f1117"
        title = Text({title_safe!r}, font_size=40, weight=BOLD, color="#e0e6f0")
        title.to_edge(UP, buff=0.5)
        self.play(Write(title), run_time=0.9)
        {"goal = Text(" + repr(goal_safe) + ", font_size=24, color='#c8d3e6')" if goal_safe else ""}
        {"goal.next_to(title, DOWN, buff=0.6)" if goal_safe else ""}
        {"self.play(FadeIn(goal, shift=UP*0.2), run_time=0.7)" if goal_safe else ""}
        self.wait({pad:.2f})
        self.play(FadeOut(*self.mobjects), run_time=0.40)
'''


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def _post_process(code: str, scene_id: int) -> str:
    """Ensure the generated code is well-formed and warn on any issues."""
    if "from manim import *" not in code:
        code = "from manim import *\nimport numpy as np\n\n" + code

    if "import numpy as np" not in code:
        code = code.replace("from manim import *", "from manim import *\nimport numpy as np", 1)

    if "class GeneratedScene" not in code:
        logger.error("Scene %d: compiled code missing GeneratedScene class!", scene_id)

    _warn_primitives(code, scene_id)
    code = _sanitize_manim_antipatterns(code, scene_id)
    if has_latex_mobjects(code):
        logger.warning(
            "Scene %d: replacing MathTex/Tex with Text (LaTeX may be unavailable)",
            scene_id,
        )
        code = strip_latex_mobjects(code)
    else:
        code = strip_latex_in_text_literals(code)
    return code


def _sanitize_manim_antipatterns(code: str, scene_id: int) -> str:
    """Fix known Manim CE incompatibilities in generated scene code."""
    if "ArrowTip(" in code:
        logger.warning(
            "Scene %d: removing invalid ArrowTip() calls (use Arrow or Arc.add_tip instead)",
            scene_id,
        )
        lines_out: list[str] = []
        for line in code.splitlines():
            if "ArrowTip(" in line and "=" in line:
                continue
            line = line.replace("disp_tip, ", "").replace(", disp_tip", "")
            line = line.replace("torque_arc_tip, ", "").replace(", torque_arc_tip", "")
            lines_out.append(line)
        code = "\n".join(lines_out)
    return code


def _warn_primitives(code: str, scene_id: int) -> None:
    """Log a warning if bare geometry primitives appear in semantic output."""
    for prim in _GEOMETRY_PRIMITIVES:
        lines = code.splitlines()
        for lineno, line in enumerate(lines, 1):
            if prim in line and "def _" not in line and "#" not in line.lstrip()[:1]:
                logger.debug(
                    "Scene %d line %d: primitive '%s' found in semantic output — "
                    "this is expected inside template setup code",
                    scene_id, lineno, prim,
                )
                break
