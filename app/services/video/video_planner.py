"""Step 3 Video Planner — Plans structured educational animations via local LLM.

Consumes a VideoTarget (from Step 2 VideoTargetMatrix) and source evidence chunks.
Prompts LLMProvider (Ollama) to produce a structured VideoPlan without writing Python.
Validates the output through scene_validator.py before handoff to Manim.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from ...core.config import settings
from ...core.llm import LLMProvider, get_llm_provider
from ..assessment.schemas import VideoTarget
from ..registry import load_rich_chunks
from .scene_schema import NarrationSegment, ScenePlan, SceneType, VideoPlan
from .scene_validator import validate_video_plan
from .script_generator import shorten_narration_to_budget

logger = logging.getLogger(__name__)

_VIDEO_PLAN_PROMPT = """SYSTEM:
You are an educational animation planner.
You do not write Python.
You do not write Manim code.
You produce a structured scene plan that a deterministic renderer will execute.
Use ONLY the supplied educational source material.
Do not invent facts.

USER:
CONCEPT: {concept_name}
DEFINITION: {definition}
SOURCE EVIDENCE:
{source_chunks}
TARGET DURATION: {duration}
STUDENT SCORE: {score}%

TASK:
Design a short remedial educational animation ({duration} seconds).
The video must:
1. Explain the concept simply.
2. Address the likely knowledge gap based on the student's low score.
3. Use visual representations where appropriate.
4. Build from prerequisite knowledge.
5. End with a concise summary.

Respond with STRICT JSON only matching this schema:
{{
  "concept_id": "{concept_id}",
  "concept_name": "{concept_name}",
  "duration_seconds": {duration},
  "learning_objective": "<1-sentence learning objective>",
  "key_points": ["<point 1>", "<point 2>", "<point 3>"],
  "scenes": [
    {{
      "scene_type": "TITLE",
      "title": "{concept_name}",
      "subtitle": "<subtitle>",
      "duration_seconds": 5.0
    }},
    {{
      "scene_type": "EQUATION",
      "equation": "<formula if applicable, e.g. F = ma>",
      "label": "<description of equation>",
      "duration_seconds": 10.0
    }},
    {{
      "scene_type": "DIAGRAM",
      "diagram_type": "force_box",
      "object_label": "Mass (m)",
      "force_label": "Net Force (F)",
      "acceleration_label": "Acceleration (a)",
      "duration_seconds": 18.0
    }},
    {{
      "scene_type": "SUMMARY",
      "summary_points": ["<key takeaway 1>", "<key takeaway 2>", "<key takeaway 3>"],
      "duration_seconds": 12.0
    }}
  ],
  "narration": [
    {{
      "scene_index": 0,
      "text": "<spoken introduction>",
      "target_seconds": 5.0
    }},
    {{
      "scene_index": 1,
      "text": "<spoken explanation of equation/core principle>",
      "target_seconds": 10.0
    }},
    {{
      "scene_index": 2,
      "text": "<spoken walkthrough of visual diagram and intuition>",
      "target_seconds": 18.0
    }},
    {{
      "scene_index": 3,
      "text": "<spoken summary recap>",
      "target_seconds": 12.0
    }}
  ]
}}

Allowed scene types:
TITLE, TEXT, EQUATION, DIAGRAM, ARROW, HIGHLIGHT, TRANSFORM, EXAMPLE, SUMMARY

Do not produce Python.
Do not produce Manim code.
Do not reference unsupported facts.
Return JSON only.
"""


def _parse_json(raw: str) -> dict[str, Any]:
    without_fences = re.sub(r"```(?:json)?", "", raw).strip()
    # Match outermost json object
    m = re.search(r"(\{.*\})", without_fences, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    return json.loads(without_fences)


def _synthesize_grounded_fallback_plan(
    target: VideoTarget,
    evidence_chunks: list[dict[str, Any]],
) -> VideoPlan:
    """Deterministic fallback synthesis supporting multi-minute educational video plans (30s to 600s)."""
    dur = float(target.target_seconds or (30 if target.difficulty == "foundational" else (60 if target.difficulty == "advanced" else 45)))

    # Detect equation if present
    name_lower = target.concept_name.lower()
    eq = "F = ma" if "force" in name_lower or "second law" in name_lower else (
        "p = mv" if "momentum" in name_lower else (
            "v = d / t" if "speed" in name_lower or "velocity" in name_lower else (
                "E = mc^2" if "energy" in name_lower or "mass" in name_lower else f"Concept: {target.concept_name}"
            )
        )
    )

    first_chunk_text = evidence_chunks[0].get("text", "") if evidence_chunks else target.directive
    clean_snippet = first_chunk_text[:300].replace("\n", " ").strip()
    chunk_ids = target.chunk_ids or [c.get("chunk_id", "") for c in evidence_chunks if c.get("chunk_id")]

    # Multi-tier pedagogical scene allocation based on target duration
    if dur <= 50:
        # Standard compact video (30s - 45s): 5 scenes
        weights = [0.12, 0.28, 0.28, 0.18, 0.14]
        scene_configs = [
            (SceneType.TITLE, target.concept_name, "Core Pedagogical Concept Review", None, None),
            (SceneType.EXPLANATION, f"Understanding {target.concept_name}", None, clean_snippet[:120], None),
            (SceneType.EQUATION if " = " in eq else SceneType.DIAGRAM, f"Governing Principle: {target.concept_name}", None, None, eq if " = " in eq else None),
            (SceneType.EXAMPLE, f"Concrete Example: {target.concept_name}", "Real-World Application", f"Observing {target.concept_name} in action demonstrates direct proportional response.", None),
            (SceneType.SUMMARY, "Key Takeaways", None, None, None),
        ]
        narration_templates = [
            f"Welcome to this remedial lesson on {target.concept_name}. Let's break down the fundamental physics and governing principles.",
            f"Here is the authoritative definition from the course materials: {clean_snippet[:100]}. Notice how each element relates to the physical state of the system.",
            f"The governing relation {eq} quantifies this exact interaction, demonstrating how changes in applied force cause direct acceleration.",
            f"In everyday physical scenarios, observing these laws in action makes the theoretical concepts immediate and intuitive.",
            f"To achieve full mastery, remember the core equation and always review prerequisite definitions before your next assessment.",
        ]
    elif dur <= 110:
        # Medium lesson (~1 minute to 1.5 minutes: 60s - 90s): 6 scenes
        weights = [0.10, 0.22, 0.22, 0.20, 0.14, 0.12]
        scene_configs = [
            (SceneType.TITLE, target.concept_name, "Deep Dive Conceptual Lesson", None, None),
            (SceneType.EXPLANATION, f"Foundation & Definition of {target.concept_name}", None, clean_snippet[:150], None),
            (SceneType.EQUATION, f"Mathematical Law: {eq}", None, None, eq if " = " in eq else "F = ma"),
            (SceneType.DIAGRAM, f"Force & State Interaction", "Vector Simulation", None, None),
            (SceneType.EXAMPLE, f"Practical Real-World Demonstration", "Applied Scenario", f"Applying {target.concept_name} to accelerating vehicles and everyday objects.", None),
            (SceneType.SUMMARY, "Mastery Summary & Review Checklist", None, None, None),
        ]
        narration_templates = [
            f"Welcome to this focused study module on {target.concept_name}. In this video, we will walk through the core definitions, mathematical formulation, and physical demonstrations.",
            f"Let's review the fundamental definition established in your textbook: {clean_snippet[:130]}. Understanding the exact terminology is essential for tackling diagnostic problems.",
            f"Next, examine the governing equation {eq}. In this relationship, each variable plays an indispensable role in determining how the system responds to external influences.",
            f"Look at the dynamic visual model on screen. When an external net force acts upon a massive body, it induces an acceleration directly proportional to the applied force vector.",
            f"Consider a concrete example such as a car accelerating on a highway. Increasing the engine force produces greater acceleration, whereas a heavier mass requires proportionally more force to move.",
            f"In summary, remember the relationship {eq}, keep units consistent, and connect every equation back to physical intuition to solidify your mastery.",
        ]
    elif dur <= 230:
        # Comprehensive lesson (~2 to 3 minutes: 120s - 180s): 7 scenes
        weights = [0.08, 0.18, 0.18, 0.18, 0.16, 0.12, 0.10]
        scene_configs = [
            (SceneType.TITLE, target.concept_name, "Comprehensive Academic Tutorial", None, None),
            (SceneType.EXPLANATION, f"Physical Intuition & Motivation", None, f"Why do objects accelerate or resist motion? {target.concept_name} provides the exact dynamical foundation.", None),
            (SceneType.EXPLANATION, f"Authoritative Definition & Scope", None, clean_snippet[:160], None),
            (SceneType.EQUATION, f"Governing Equation & Parameter Breakdown", None, None, eq if " = " in eq else "F = ma"),
            (SceneType.DIAGRAM, f"Visual Dynamics: Free-Body Analysis", "Force Interaction", None, None),
            (SceneType.EXAMPLE, f"Case Study & Numerical Walkthrough", "Worked Example", f"Analyzing real physical measurements governed by {target.concept_name}.", None),
            (SceneType.SUMMARY, "Formula Reference & Self-Assessment Guide", None, None, None),
        ]
        narration_templates = [
            f"Welcome to this comprehensive tutorial on {target.concept_name}. Over the next few minutes, we will thoroughly explore the underlying principles, governing mathematical formulas, and concrete applications.",
            f"To build strong intuition, consider how objects in the universe behave when forces act upon them. Without an external influence, objects maintain their state; but when an unbalanced force intervenes, acceleration is inevitable.",
            f"Turning to the verified study text: {clean_snippet[:140]}. This formal definition is the cornerstone of classical dynamics and forms the foundation for solving complex multi-step problems.",
            f"The central mathematical formulation is expressed as {eq}. Here, force is a vector quantity that scales directly with acceleration. Notice that doubling the force doubles the acceleration for a fixed mass.",
            f"Observe the dynamic diagram illustrating the force vector acting on the mass block. The direction of the resulting acceleration aligns exactly with the net force vector.",
            f"Let us connect this to a real-world engineering case study. Rocket propulsion, automobile braking, and planetary motion all adhere strictly to these proportional dynamics.",
            f"As we conclude, review these key takeaways: first, remember {eq}; second, ensure vector directions are carefully tracked; and third, practice applying these principles to diagnostic questions.",
        ]
    else:
        # Full masterclass lesson (4 to 10 minutes: 240s - 600s): 8 scenes
        weights = [0.08, 0.14, 0.14, 0.16, 0.16, 0.14, 0.10, 0.08]
        scene_configs = [
            (SceneType.TITLE, target.concept_name, "In-Depth Masterclass Lecture", None, None),
            (SceneType.EXPLANATION, f"Historical Context & Physical Intuition", None, f"Tracing the foundational discoveries that established {target.concept_name} in modern science.", None),
            (SceneType.EXPLANATION, f"Formal Definition & Boundary Conditions", None, clean_snippet[:180], None),
            (SceneType.EQUATION, f"Mathematical Derivation: {eq}", None, None, eq if " = " in eq else "F = ma"),
            (SceneType.DIAGRAM, f"Free-Body Dynamics & Vector Analysis", "Dynamic Simulation", None, None),
            (SceneType.EXAMPLE, f"Real-World Engineering Case Studies", "Applied Physics", f"Practical applications across modern mechanics, automotive safety, and aerospace engineering.", None),
            (SceneType.EXPLANATION, f"Common Misconceptions & Diagnostic Pitfalls", None, "Differentiating between velocity, net force, and acceleration to prevent common exam errors.", None),
            (SceneType.SUMMARY, "Complete Formula Reference & Review", None, None, None),
        ]
        narration_templates = [
            f"Welcome to this in-depth masterclass on {target.concept_name}. In this extended lecture, we will deeply investigate the theoretical origins, mathematical rigor, dynamic simulations, and practical engineering applications.",
            f"Before examining the mathematical laws, let us appreciate the physical motivation. Historically, understanding why and how massive bodies alter their velocity transformed our comprehension of natural phenomena.",
            f"Let us examine the authoritative definitions presented in your course curriculum: {clean_snippet[:150]}. Notice that mass acts as an intrinsic resistance to changes in motion, known universally as inertia.",
            f"The governing physical equation is formalized as {eq}. When working through numerical problems, always verify units: force in Newtons, mass in kilograms, and acceleration in meters per second squared.",
            f"Look closely at the vector simulation on screen. The net force arrow indicates the magnitude and direction of the external interaction, which dictates the instantaneous acceleration of the body.",
            f"Consider practical engineering applications: civil engineers calculate structural load forces, automotive designers calibrate crumple zones, and aeronautical engineers calculate rocket thrust based directly on these relationships.",
            f"A common student pitfall is confusing constant velocity with zero net force. Remember: an object moving at high constant speed experiences zero net force; only changes in velocity require net external forces.",
            f"In conclusion, master the core formula {eq}, visualize the free-body diagram, verify units, and practice diagnosing conceptual questions with confidence.",
        ]

    durations = [max(1.0, round(dur * w, 1)) for w in weights]
    diff = round(dur - sum(durations), 1)
    durations[-1] = max(1.0, round(durations[-1] + diff, 1))

    scenes: list[ScenePlan] = []
    narration: list[NarrationSegment] = []

    for idx, ((stype, title, sub, text, eq_val), seg_dur, narr_text) in enumerate(zip(scene_configs, durations, narration_templates)):
        scenes.append(
            ScenePlan(
                scene_index=idx,
                scene_type=stype,
                title=title,
                subtitle=sub,
                text=text,
                equation=eq_val,
                label=sub or title,
                diagram_type="force_box" if stype == SceneType.DIAGRAM else None,
                object_label="Mass (m)" if stype == SceneType.DIAGRAM else None,
                force_label="Force (F)" if stype == SceneType.DIAGRAM else None,
                acceleration_label="Acceleration (a)" if stype == SceneType.DIAGRAM else None,
                summary_points=[
                    f"Mastery: {target.concept_name}",
                    f"Governing Relation: {eq}",
                    "Apply vector analysis to avoid conceptual pitfalls",
                ] if stype == SceneType.SUMMARY else [],
                duration_seconds=seg_dur,
                source_chunk_ids=chunk_ids,
                page_start=target.page_start,
                page_end=target.page_end,
            )
        )
        fitted_narr = shorten_narration_to_budget(narr_text, seg_dur, wpm=140)
        narration.append(
            NarrationSegment(
                scene_index=idx,
                text=fitted_narr,
                target_seconds=seg_dur,
            )
        )

    return VideoPlan(
        student_id=target.student_id or "STU_DEFAULT",
        source_id=target.source_id or "SRC_DEFAULT",
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        definition=clean_snippet or f"Grounded concept: {target.concept_name}",
        duration_seconds=int(dur),
        target_seconds=int(dur),
        difficulty=target.difficulty,
        learning_objective=f"Master the core principles and relationships of {target.concept_name}",
        key_points=[f"Understanding {target.concept_name}", "Visualizing the system", "Applying governing laws"],
        scenes=scenes,
        narration=narration,
        source_chunk_ids=[cid for cid in chunk_ids if cid],
        provenance_chunks=[cid for cid in chunk_ids if cid],
        source_content_ids=target.source_content_ids or [],
        page_start=target.page_start,
        page_end=target.page_end,
        provenance={
            "chunks": chunk_ids,
            "content_ids": target.source_content_ids or [],
            "pages": [target.page_start, target.page_end] if target.page_start else [],
        },
    )


def plan_video_for_target(
    target: VideoTarget,
    student_id: str | None = None,
    source_id: str | None = None,
    provider: LLMProvider | None = None,
) -> VideoPlan:
    """Generate and validate a VideoPlan for a specific learning gap."""
    active_provider = provider or get_llm_provider()
    student = student_id or target.student_id or "STU_DEFAULT"
    source = source_id or target.source_id or "SRC_DEFAULT"

    # Retrieve source chunks
    evidence: list[dict[str, Any]] = []
    try:
        raw_chunks = load_rich_chunks(source)
        for rc in raw_chunks:
            payload = rc.model_dump() if hasattr(rc, "model_dump") else rc
            # Match concept
            cids = payload.get("concept_ids", [])
            if target.concept_id in cids or any(target.concept_name.lower() in str(c).lower() for c in cids):
                evidence.append(payload)
        if not evidence and raw_chunks:
            # Fall back to first few source chunks if concept-specific tags are sparse
            evidence = [
                (rc.model_dump() if hasattr(rc, "model_dump") else rc)
                for rc in raw_chunks[:4]
            ]
    except Exception as exc:
        logger.warning(f"[video_planner] Could not load rich chunks for {source}: {exc}")

    chunk_texts = "\n---\n".join(
        f"[{c.get('chunk_id', 'CHUNK')}]: {c.get('text', '')[:400]}"
        for c in evidence[:4]
    ) or target.directive

    dur = target.target_seconds or (30 if target.difficulty == "foundational" else (60 if target.difficulty == "advanced" else 45))

    prompt = _VIDEO_PLAN_PROMPT.format(
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        definition=evidence[0].get("text", "")[:300] if evidence else target.directive,
        source_chunks=chunk_texts,
        duration=dur,
        score=int(target.score),
    )

    t0 = time.time()
    chunk_ids = target.chunk_ids or [c.get("chunk_id", "") for c in evidence if c.get("chunk_id")]
    try:
        raw = active_provider.generate_content(prompt)
        data = _parse_json(raw)

        # Parse scenes
        raw_scenes = data.get("scenes", [])
        scenes: list[ScenePlan] = []
        for i, s in enumerate(raw_scenes):
            stype = SceneType(str(s.get("scene_type", "TEXT")).upper())
            scenes.append(
                ScenePlan(
                    scene_index=i,
                    scene_type=stype,
                    duration_seconds=float(s.get("duration_seconds", 5.0)),
                    title=s.get("title"),
                    subtitle=s.get("subtitle"),
                    text=s.get("text"),
                    equation=s.get("equation"),
                    label=s.get("label"),
                    diagram_type=s.get("diagram_type"),
                    object_label=s.get("object_label"),
                    force_label=s.get("force_label"),
                    acceleration_label=s.get("acceleration_label"),
                    summary_points=s.get("summary_points", []),
                    source_chunk_ids=chunk_ids,
                    page_start=target.page_start,
                    page_end=target.page_end,
                )
            )

        # Parse narration
        raw_narration = data.get("narration", [])
        narration: list[NarrationSegment] = [
            NarrationSegment(
                scene_index=int(n.get("scene_index", idx)),
                text=str(n.get("text", "")),
                target_seconds=float(n.get("target_seconds", 5.0)),
            )
            for idx, n in enumerate(raw_narration)
        ]

        plan = VideoPlan(
            student_id=student,
            source_id=source,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            definition=evidence[0].get("text", "")[:300] if evidence else target.directive,
            duration_seconds=int(dur),
            target_seconds=int(dur),
            difficulty=target.difficulty,
            learning_objective=data.get("learning_objective", f"Understand {target.concept_name}"),
            key_points=data.get("key_points", []),
            scenes=scenes,
            narration=narration,
            source_chunk_ids=[cid for cid in chunk_ids if cid],
            provenance_chunks=[cid for cid in chunk_ids if cid],
            source_content_ids=target.source_content_ids or [],
            page_start=target.page_start,
            page_end=target.page_end,
            provenance={
                "chunks": chunk_ids,
                "content_ids": target.source_content_ids or [],
                "pages": [target.page_start, target.page_end] if target.page_start else [],
            },
        )
        validated = validate_video_plan(plan)
        save_video_plan(validated)
        return validated
    except Exception as exc:
        logger.warning(f"[video_planner] LLM generation failed ({exc}); synthesizing grounded fallback VideoPlan")
        fallback_plan = _synthesize_grounded_fallback_plan(target, evidence)
        fallback_plan.student_id = student
        fallback_plan.source_id = source
        fallback_plan.page_start = target.page_start
        fallback_plan.page_end = target.page_end
        fallback_plan.source_content_ids = target.source_content_ids or []
        fallback_plan.source_chunk_ids = [cid for cid in chunk_ids if cid]
        fallback_plan.provenance_chunks = [cid for cid in chunk_ids if cid]
        validated = validate_video_plan(fallback_plan)
        save_video_plan(validated)
        return validated



def save_video_plan(plan: VideoPlan) -> Path:
    """Persist VideoPlan JSON to disk."""
    settings.video_plans_dir.mkdir(parents=True, exist_ok=True)
    out_file = settings.video_plans_dir / f"{plan.plan_id}.json"
    out_file.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return out_file


def load_video_plan(plan_id: str) -> VideoPlan | None:
    """Load persisted VideoPlan from disk."""
    out_file = settings.video_plans_dir / f"{plan_id}.json"
    if not out_file.exists():
        return None
    data = json.loads(out_file.read_text(encoding="utf-8"))
    return VideoPlan.model_validate(data)
