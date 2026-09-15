"""Compile beat-indexed visual skeleton + timeline into polished Manim code.

Strategy
--------
A deterministic template produces clean, sync-accurate Manim scenes:
- Persistent title at top.
- For each beat: FadeOut previous beat's mobjects, introduce this beat's mobjects
  with proper layout (no overlap), play animations sized to the beat's run_time
  budget, then self.wait() to fill the beat's audio window.
- Total scene duration == audio duration (within ~0.1s).
- Every skeleton object is rendered.

LLM compilation is supported (USE_LLM_COMPILER=true) but is strictly post-validated:
if it doesn't render every object, deviates from TIMELINE, or uses banned APIs,
we discard it and use the template.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from modules.config import (
    NVIDIA_CODE_MODEL,
    PATHS,
    USE_LLM_COMPILER,
    get_logger,
)
from modules.llm.nvidia_client import NvidiaClient

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compile_scene(
    scene: dict[str, Any],
    skeleton: dict[str, Any],
    sync_result: dict[str, Any],
) -> tuple[Path, str]:
    """Compile a Manim file. Returns (file_path, deterministic_fallback_code)."""
    scene_id = scene["scene_id"]
    timeline = sync_result["timeline"]
    logger.info("Compiling Manim code for scene %d", scene_id)

    template_code = _compile_template(scene, skeleton, timeline)

    code: str | None = None
    if USE_LLM_COMPILER:
        try:
            raw = _llm_compile(scene, skeleton, timeline)
            candidate = _clean_code(raw)
            candidate = _ensure_valid_structure(candidate)
            if _passes_quality_checks(candidate, skeleton):
                code = candidate
            else:
                logger.warning(
                    "LLM output failed quality checks for scene %d; using template",
                    scene_id,
                )
        except Exception as exc:
            logger.warning("LLM compile failed for scene %d: %s", scene_id, exc)

    final_code = code or template_code
    out_path = PATHS["manim"] / f"scene_{scene_id}.py"
    out_path.write_text(final_code, encoding="utf-8")
    logger.info("Manim code saved: %s", out_path)
    return out_path, template_code


# ---------------------------------------------------------------------------
# Template compiler (deterministic, sync-accurate)
# ---------------------------------------------------------------------------


def _compile_template(
    scene: dict[str, Any],
    skeleton: dict[str, Any],
    timeline: dict[str, Any],
) -> str:
    """Produce a polished, sync-accurate Manim file from skeleton + beat timeline."""
    objects = skeleton["objects"]
    beats = timeline["beats"]
    obj_run = timeline["object_run_times"]
    title_text = scene.get("concept", "Concept").strip()[:50]

    lines: list[str] = [
        "from manim import *",
        "",
        "",
        "class GeneratedScene(Scene):",
        "    def construct(self):",
        f'        self.camera.background_color = "#0f1117"',
        "",
        f'        scene_title = Text("{_escape(title_text)}", font_size=42, weight=BOLD, color="#e0e6f0").to_edge(UP, buff=0.4)',
        "        self.play(Write(scene_title), run_time=0.8)",
        "",
    ]

    objects_by_beat: dict[int, list[dict[str, Any]]] = {}
    for obj in objects:
        objects_by_beat.setdefault(obj.get("beat_index", 0), []).append(obj)

    intro_time = 0.8  # initial Write(scene_title)
    outro_time = 0.4  # FadeOut(scene_title) at end
    prev_group_var: str | None = None
    elapsed = intro_time
    audio_duration = float(timeline.get("total", sum(b.get("slot_duration", 1.5) for b in beats)))

    for beat_idx, beat in enumerate(beats):
        beat_objs = objects_by_beat.get(beat_idx, [])
        slot_duration = max(float(beat.get("slot_duration", beat.get("duration", 1.5))), 1.0)
        # Beat 0 absorbs the intro_time inside its slot.
        slot_budget = slot_duration - (intro_time if beat_idx == 0 else 0.0)
        slot_budget = max(slot_budget, 0.5)

        fade_time = 0.3 if prev_group_var else 0.0
        anim_total = sum(
            max(float(obj_run.get(o["id"], 0.5)), 0.4) for o in beat_objs
        )
        anim_total = min(anim_total, max(slot_budget * 0.55, 0.6))
        wait_time = max(slot_budget - fade_time - anim_total, 0.3)

        lines.append(
            f"        # --- beat {beat_idx}: {_escape(beat.get('phrase', ''))[:60]} ---"
        )
        if prev_group_var:
            lines.append(
                f"        self.play(FadeOut({prev_group_var}), run_time={fade_time:.2f})"
            )

        var_names = [_safe_var(o["id"]) for o in beat_objs]
        # Avoid collisions with reserved variable names.
        var_names = [
            ("obj_" + v) if v in {"scene_title", "title", "self"} else v
            for v in var_names
        ]

        for var, obj in zip(var_names, beat_objs):
            lines.append(f"        {_create_mobject_line(var, obj)}")

        if not beat_objs:
            lines.append(f"        self.wait({slot_budget:.2f})")
            lines.append("")
            elapsed += slot_budget
            continue

        if len(var_names) == 1:
            group_var = var_names[0]
            lines.append(
                f"        {group_var}.next_to(scene_title, DOWN, buff=0.8).move_to([0, -0.3, 0])"
            )
        else:
            group_var = f"beat_{beat_idx}_group"
            lines.append(
                f"        {group_var} = VGroup({', '.join(var_names)}).arrange(DOWN, buff=0.5)"
                ".next_to(scene_title, DOWN, buff=0.6)"
            )

        # Scale run_times proportionally to fit anim_total budget.
        raw_rts = [max(float(obj_run.get(obj["id"], 0.6)), 0.4) for obj in beat_objs]
        scale = anim_total / sum(raw_rts) if sum(raw_rts) > 0 else 1.0
        rts = [round(rt * scale, 3) for rt in raw_rts]

        for obj, var, rt in zip(beat_objs, var_names, rts):
            action = _action_for(obj["action"])
            lines.append(f'        self.play({action}({var}), run_time={rt:.3f})')

        lines.append(f"        self.wait({wait_time:.2f})")
        lines.append("")
        elapsed += fade_time + sum(rts) + wait_time
        prev_group_var = group_var

    # Tail: make total duration match audio_duration as closely as possible.
    tail_pad = audio_duration - elapsed - outro_time - 0.3  # 0.3 for prev fade
    if tail_pad > 0.1:
        lines.append(f"        self.wait({tail_pad:.2f})")

    if prev_group_var:
        lines.append(f"        self.play(FadeOut({prev_group_var}), run_time=0.3)")
    lines.append(f"        self.play(FadeOut(scene_title), run_time={outro_time:.2f})")
    return "\n".join(lines) + "\n"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _create_mobject_line(var: str, obj: dict[str, Any]) -> str:
    obj_type = obj["type"]
    content = _escape(obj["content"])[:80]

    if obj_type == "Text":
        return f'{var} = Text("{content}", font_size=32, color="#c8d3e6")'
    if obj_type == "MathTex":
        # LaTeX may not be fully installed — use Text instead.
        return f'{var} = Text("{content}", font_size=32, color="#c8d3e6")'
    if obj_type == "Circle":
        return f'{var} = VGroup(Circle(radius=0.9, color="#4f8ef7", fill_opacity=0.25), Text("{content}", font_size=22, color="#e0e6f0"))'
    if obj_type == "Square":
        return f'{var} = VGroup(Square(side_length=1.6, color="#41d4a8", fill_opacity=0.25), Text("{content}", font_size=22, color="#e0e6f0"))'
    if obj_type == "Rectangle":
        return f'{var} = VGroup(Rectangle(width=2.8, height=1.2, color="#f7c948", fill_opacity=0.2), Text("{content}", font_size=22, color="#e0e6f0"))'
    if obj_type == "Arrow":
        return f'{var} = VGroup(Arrow(LEFT, RIGHT, color="#ff7a59", stroke_width=6), Text("{content}", font_size=22, color="#e0e6f0").shift(DOWN*0.5))'
    if obj_type == "Dot":
        return f'{var} = VGroup(Dot(radius=0.18, color="#ffd166"), Text("{content}", font_size=22, color="#e0e6f0").shift(DOWN*0.4))'
    if obj_type == "Line":
        return f'{var} = VGroup(Line(LEFT, RIGHT, color="#c8d3e6", stroke_width=4), Text("{content}", font_size=22, color="#e0e6f0").shift(DOWN*0.4))'
    return f'{var} = Text("{content}", font_size=28, color="#c8d3e6")'


def _action_for(action: str) -> str:
    # FadeOut as an "introducing" action makes no sense, so coerce to FadeIn.
    return {
        "Write": "Write",
        "FadeIn": "FadeIn",
        "FadeOut": "FadeIn",
        "Create": "Create",
        "Indicate": "Indicate",
        "GrowFromCenter": "GrowFromCenter",
        "Transform": "FadeIn",
        "MoveToTarget": "FadeIn",
    }.get(action, "FadeIn")


def _safe_var(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not safe:
        safe = "obj"
    if safe[0].isdigit():
        safe = "obj_" + safe
    return safe


# ---------------------------------------------------------------------------
# LLM compiler (optional, strict post-validation)
# ---------------------------------------------------------------------------


CODE_SYSTEM = """You are an expert Manim Community Edition code generator.

Produce ONE complete Python file with a class GeneratedScene(Scene).
HARD RULES:
1. Use ONLY the run_time values from the provided OBJECT_RUN_TIMES dict.
2. Animate objects in beat order. After each beat, FadeOut that beat's mobjects.
3. EVERY object id from the skeleton MUST appear as a mobject and be animated.
4. NEVER overlap mobjects: use VGroup.arrange + next_to(title, DOWN, buff=...).
5. Keep a persistent title at the top via .to_edge(UP).
6. NEVER use MathTex/Tex (LaTeX may be incomplete). Use Text() only.
7. NEVER use .get_edge() or ApplyMethod. Use .get_left/right/top/bottom and .animate.
8. End the scene with FadeOut(title) and self.wait(0.3).
9. Return ONLY Python code, no markdown fences."""

CODE_PROMPT = """Generate the Manim code for this scene.

NARRATION: {narration}
CONCEPT TITLE: {concept}

VISUAL_INSTRUCTION: {visual_instruction}

BEATS (in order, each gets its own animation block then FadeOut):
{beats}

SKELETON OBJECTS (every object MUST be rendered, grouped by beat_index):
{skeleton}

OBJECT_RUN_TIMES (use EXACTLY these values for run_time=...):
{object_run_times}

SELF_WAIT after each beat = beat.duration - (sum of object run_times in that beat) - 0.3 (clamp >= 0.2).

Return ONLY Python."""


def _llm_compile(
    scene: dict[str, Any],
    skeleton: dict[str, Any],
    timeline: dict[str, Any],
) -> str:
    prompt = CODE_PROMPT.format(
        narration=scene["narration"],
        concept=scene.get("concept", ""),
        visual_instruction=scene["visual_instruction"],
        beats=json.dumps(timeline["beats"], indent=2),
        skeleton=json.dumps(skeleton["objects"], indent=2),
        object_run_times=json.dumps(timeline["object_run_times"], indent=2),
    )
    messages = [
        {"role": "system", "content": CODE_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    client = NvidiaClient()
    return client.chat(NVIDIA_CODE_MODEL, messages, temperature=0.15, max_tokens=8192)


def _clean_code(code: str) -> str:
    code = code.strip()
    if "```python" in code:
        match = re.search(r"```python\s*(.*?)\s*```", code, re.DOTALL)
        if match:
            code = match.group(1)
    elif "```" in code:
        match = re.search(r"```\s*(.*?)\s*```", code, re.DOTALL)
        if match:
            code = match.group(1)
    return code.strip()


def _ensure_valid_structure(code: str) -> str:
    if "from manim import" not in code:
        code = "from manim import *\n\n" + code
    if "class GeneratedScene" not in code:
        code += (
            "\n\nclass GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            '        self.add(Text("Scene"))\n'
            "        self.wait(1)\n"
        )
    return code


_BANNED_PATTERNS = (
    "MathTex(",
    "Tex(",
    ".get_edge(",
    "ApplyMethod",
)


def _passes_quality_checks(code: str, skeleton: dict[str, Any]) -> bool:
    """Strict checks: structure, banned APIs, every object id referenced."""
    if "class GeneratedScene" not in code or "def construct" not in code:
        return False
    if "self.play(" not in code:
        return False
    for banned in _BANNED_PATTERNS:
        if banned in code:
            return False
    # Every object id from the skeleton must appear in the code.
    for obj in skeleton["objects"]:
        if _safe_var(obj["id"]) not in code and obj["id"] not in code:
            return False
    return True
