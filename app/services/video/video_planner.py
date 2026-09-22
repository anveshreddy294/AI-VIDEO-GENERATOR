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
Ground ALL scene titles, descriptions, and narration strictly in the SOURCE EVIDENCE and CONCEPT.
Do not mention physics, forces, or unrelated concepts unless they explicitly appear in the source.

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
1. Explain the concept simply and accurately based ONLY on the source evidence.
2. Address the likely knowledge gap based on the student's score.
3. Structure scenes logically: Introduction/Title -> Definitional Core -> Structural/Process Workflow -> Practical Application -> Key Takeaways Summary.
4. Allocate scene durations so their sum equals approximately {duration} seconds.
5. Provide clear, natural spoken narration for each scene.

Respond with STRICT JSON only matching this schema:
{{
  "concept_id": "{concept_id}",
  "concept_name": "{concept_name}",
  "duration_seconds": {duration},
  "learning_objective": "<1-sentence learning objective grounded strictly in the source>",
  "key_points": ["<key takeaway 1 from source>", "<key takeaway 2 from source>", "<key takeaway 3 from source>"],
  "scenes": [
    {{
      "scene_type": "TITLE",
      "title": "{concept_name}",
      "subtitle": "<topic subtitle grounded in source>",
      "duration_seconds": 5.0
    }},
    {{
      "scene_type": "EXPLANATION",
      "title": "Understanding {concept_name}",
      "text": "<concise explanation extracted directly from source evidence>",
      "duration_seconds": 12.0
    }},
    {{
      "scene_type": "DIAGRAM",
      "diagram_type": "concept_flow",
      "title": "Structural Workflow",
      "label": "Process & Architecture",
      "summary_points": ["<stage 1>", "<stage 2>", "<stage 3>"],
      "duration_seconds": 16.0
    }},
    {{
      "scene_type": "SUMMARY",
      "title": "Key Takeaways",
      "summary_points": ["<point 1 from source>", "<point 2 from source>", "<point 3 from source>"],
      "duration_seconds": 12.0
    }}
  ],
  "narration": [
    {{
      "scene_index": 0,
      "text": "<spoken introduction welcoming student to concept>",
      "target_seconds": 5.0
    }},
    {{
      "scene_index": 1,
      "text": "<spoken explanation of core definition strictly from source>",
      "target_seconds": 12.0
    }},
    {{
      "scene_index": 2,
      "text": "<spoken walkthrough of the structural workflow and relationships>",
      "target_seconds": 16.0
    }},
    {{
      "scene_index": 3,
      "text": "<spoken summary recap of key takeaways>",
      "target_seconds": 12.0
    }}
  ]
}}

Allowed scene types:
TITLE, TEXT, EXPLANATION, EQUATION, DIAGRAM, ARROW, HIGHLIGHT, TRANSFORM, EXAMPLE, SUMMARY

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


def normalize_and_repair_video_plan(plan: VideoPlan, target_seconds: float) -> VideoPlan:
    """Normalize and auto-repair a VideoPlan before strict validation.

    Guarantees:
    1. Pro-rates scene durations so their sum matches target_seconds within tolerance.
    2. Synchronizes narration segment indices and target_seconds to scene durations.
    3. Trims and budgets narration words so effective WPM never exceeds speech rate limits (<= 160 WPM).
    4. Guarantees safe scene types and fallback text fields.
    """
    target_dur = max(5.0, float(target_seconds or plan.target_seconds or plan.duration_seconds or 45.0))
    plan.target_seconds = int(target_dur)
    plan.duration_seconds = int(target_dur)

    if not plan.scenes:
        plan.scenes = [
            ScenePlan(
                scene_index=0,
                scene_type=SceneType.TITLE,
                title=plan.concept_name,
                duration_seconds=target_dur,
            )
        ]

    # Pro-rate scene durations proportionally
    raw_total = sum(max(0.5, float(s.duration_seconds or 0.0)) for s in plan.scenes)
    if raw_total <= 0:
        raw_total = float(len(plan.scenes))
        for s in plan.scenes:
            s.duration_seconds = 1.0

    scale_factor = target_dur / raw_total
    allocated = 0.0
    for idx, s in enumerate(plan.scenes):
        s.scene_index = idx
        if not s.title and not s.text and not s.label:
            s.title = plan.concept_name
        if idx == len(plan.scenes) - 1:
            s.duration_seconds = max(1.0, round(target_dur - allocated, 1))
        else:
            raw_dur = max(0.5, float(s.duration_seconds or 5.0))
            scaled = max(1.0, round(raw_dur * scale_factor, 1))
            s.duration_seconds = scaled
            allocated += scaled

    total_scenes_dur = sum(s.duration_seconds for s in plan.scenes)
    diff = round(target_dur - total_scenes_dur, 1)
    if diff != 0:
        plan.scenes[-1].duration_seconds = max(1.0, round(plan.scenes[-1].duration_seconds + diff, 1))

    # Synchronize and speech-budget narration segments
    max_idx = len(plan.scenes) - 1
    narr_by_idx: dict[int, str] = {}
    for seg in plan.narration:
        s_idx = max(0, min(int(seg.scene_index), max_idx))
        if s_idx in narr_by_idx:
            narr_by_idx[s_idx] += " " + seg.text.strip()
        else:
            narr_by_idx[s_idx] = seg.text.strip()

    new_narr: list[NarrationSegment] = []
    for idx, scene in enumerate(plan.scenes):
        text = narr_by_idx.get(idx, "")
        if not text or not text.strip():
            if scene.scene_type == SceneType.TITLE:
                text = f"Welcome to this focused study module on {plan.concept_name}."
            elif scene.scene_type == SceneType.SUMMARY:
                text = f"In summary, remember these core principles of {plan.concept_name} for your diagnostic review."
            else:
                text = scene.text or scene.title or f"Let's explore key aspects of {plan.concept_name}."

        # Budget words to strictly adhere to maximum speech rates (wpm=140 target, guarantees < 240 WPM limit)
        budgeted_text = shorten_narration_to_budget(text, scene.duration_seconds, wpm=140)
        if not budgeted_text or not budgeted_text.strip():
            budgeted_text = f"Reviewing {plan.concept_name}."

        new_narr.append(
            NarrationSegment(
                scene_index=idx,
                text=budgeted_text,
                target_seconds=scene.duration_seconds,
            )
        )

    plan.narration = new_narr
    return plan


def _synthesize_grounded_fallback_plan(
    target: VideoTarget,
    evidence_chunks: list[dict[str, Any]],
) -> VideoPlan:
    """Deterministic fallback synthesis dynamically grounded in the source text (30s to 600s).

    Eliminates hardcoded physics assumptions for non-physics domains while preserving
    physics formulas when genuine physical mechanics concepts are provided.
    """
    dur = float(target.target_seconds or (30 if target.difficulty == "foundational" else (60 if target.difficulty == "advanced" else 45)))

    # Extract clean sentences from evidence chunks
    all_sentences: list[str] = []
    for c in evidence_chunks:
        raw_text = c.get("text", "") if isinstance(c, dict) else str(c)
        clean_text = re.sub(r"\[IMAGE:[^\]]*\]", "", raw_text)
        clean_text = re.sub(r"```[a-zA-Z]*", "", clean_text).replace("```", "")
        clean_text = clean_text.replace("\n", " ").strip()
        for sent in re.split(r"(?<=[.?!])\s+", clean_text):
            sent = sent.strip()
            if len(sent) > 15 and not sent.startswith("#"):
                all_sentences.append(sent)

    if not all_sentences:
        clean_snippet = target.directive.replace("\n", " ").strip()
        if clean_snippet:
            all_sentences.append(clean_snippet[:250])
        all_sentences.append(f"{target.concept_name} is a foundational concept in this course material.")
        all_sentences.append(f"Understanding the core components of {target.concept_name} enables rigorous analysis.")

    first_chunk_text = evidence_chunks[0].get("text", "") if evidence_chunks else target.directive
    clean_snippet = all_sentences[0] if all_sentences else first_chunk_text[:300].replace("\n", " ").strip()
    chunk_ids = target.chunk_ids or [c.get("chunk_id", "") for c in evidence_chunks if c.get("chunk_id")]

    # Domain detection: physics vs general concept
    name_lower = target.concept_name.lower()
    corpus_lower = (name_lower + " " + " ".join(all_sentences[:4])).lower()
    is_physics = any(
        kw in corpus_lower
        for kw in (
            "newton", "second law", "first law", "third law",
            "net force", "applied force", "friction", "kinematics",
            "momentum", "gravity", "gravitational",
        )
    )

    if is_physics:
        eq = "F = ma" if "force" in name_lower or "second law" in name_lower else (
            "p = mv" if "momentum" in name_lower else (
                "v = d / t" if "speed" in name_lower or "velocity" in name_lower else (
                    "E = mc^2" if "energy" in name_lower or "mass" in name_lower else f"Concept: {target.concept_name}"
                )
            )
        )
    else:
        eq = None

    # Multi-tier pedagogical scene allocation based on target duration
    if dur <= 50:
        weights = [0.12, 0.28, 0.28, 0.18, 0.14]
        if is_physics:
            scene_configs = [
                (SceneType.TITLE, target.concept_name, "Core Pedagogical Concept Review", None, None, "force_box", "Mass (m)", "Force (F)", "Acceleration (a)"),
                (SceneType.EXPLANATION, f"Understanding {target.concept_name}", None, clean_snippet[:120], None, None, None, None, None),
                (SceneType.EQUATION if " = " in eq else SceneType.DIAGRAM, f"Governing Principle: {target.concept_name}", None, None, eq if " = " in eq else None, "force_box", "Mass (m)", "Force (F)", "Acceleration (a)"),
                (SceneType.EXAMPLE, f"Concrete Example: {target.concept_name}", "Real-World Application", f"Observing {target.concept_name} in action demonstrates direct proportional response.", None, None, None, None, None),
                (SceneType.SUMMARY, "Key Takeaways", None, None, None, None, None, None, None),
            ]
            narration_templates = [
                f"Welcome to this remedial lesson on {target.concept_name}. Let's break down the fundamental physics and governing principles.",
                f"Here is the authoritative definition from the course materials: {clean_snippet[:100]}. Notice how each element relates to the physical state of the system.",
                f"The governing relation {eq} quantifies this exact interaction, demonstrating how changes in applied force cause direct acceleration.",
                f"In everyday physical scenarios, observing these laws in action makes the theoretical concepts immediate and intuitive.",
                f"To achieve full mastery, remember the core equation and always review prerequisite definitions before your next assessment.",
            ]
        else:
            s2_text = all_sentences[1][:150] if len(all_sentences) > 1 else clean_snippet[:120]
            scene_configs = [
                (SceneType.TITLE, target.concept_name, "Core Conceptual Architecture", None, None, None, None, None, None),
                (SceneType.EXPLANATION, f"Understanding {target.concept_name}", None, clean_snippet[:140], None, None, None, None, None),
                (SceneType.DIAGRAM, f"{target.concept_name} Structural Flow", "Process & Architecture", None, None, "concept_flow", None, None, None),
                (SceneType.EXAMPLE, f"Practical Context: {target.concept_name}", "Applied Workflow", s2_text, None, None, None, None, None),
                (SceneType.SUMMARY, "Key Takeaways & Review Checklist", None, None, None, None, None, None, None),
            ]
            narration_templates = [
                f"Welcome to this focused study module on {target.concept_name}. In this video, we explore the core structure and essential principles established in your materials.",
                f"Let's review the verified definition from your curriculum: {clean_snippet[:110]}. Notice the exact terminology used to define this concept.",
                f"Examining this structural workflow reveals how each component interacts within the broader {target.concept_name} system.",
                f"In real-world applications: {s2_text[:110]}. Applying these methods ensures consistent, reliable results.",
                f"In summary, review these essential takeaways, reinforce your understanding of prerequisite concepts, and apply them with confidence.",
            ]
    elif dur <= 110:
        weights = [0.10, 0.22, 0.22, 0.20, 0.14, 0.12]
        if is_physics:
            scene_configs = [
                (SceneType.TITLE, target.concept_name, "Deep Dive Conceptual Lesson", None, None, None, None, None, None),
                (SceneType.EXPLANATION, f"Foundation & Definition of {target.concept_name}", None, clean_snippet[:150], None, None, None, None, None),
                (SceneType.EQUATION, f"Mathematical Law: {eq}", None, None, eq if " = " in eq else "F = ma", None, None, None, None),
                (SceneType.DIAGRAM, "Force & State Interaction", "Vector Simulation", None, None, "force_box", "Mass (m)", "Force (F)", "Acceleration (a)"),
                (SceneType.EXAMPLE, "Practical Real-World Demonstration", "Applied Scenario", f"Applying {target.concept_name} to accelerating bodies and systems.", None, None, None, None, None),
                (SceneType.SUMMARY, "Mastery Summary & Review Checklist", None, None, None, None, None, None, None),
            ]
            narration_templates = [
                f"Welcome to this focused study module on {target.concept_name}. In this video, we will walk through the core definitions, mathematical formulation, and physical demonstrations.",
                f"Let's review the fundamental definition established in your textbook: {clean_snippet[:130]}. Understanding the exact terminology is essential for tackling diagnostic problems.",
                f"Next, examine the governing equation {eq}. In this relationship, each variable plays an indispensable role in determining how the system responds to external influences.",
                f"Look at the dynamic visual model on screen. When an external net force acts upon a massive body, it induces an acceleration directly proportional to the applied force vector.",
                f"Consider a concrete example: increasing applied force produces greater acceleration, whereas heavier mass requires proportionally more force to move.",
                f"In summary, remember the relationship {eq}, keep units consistent, and connect every equation back to physical intuition to solidify your mastery.",
            ]
        else:
            s2_text = all_sentences[1][:150] if len(all_sentences) > 1 else clean_snippet[:130]
            s3_text = all_sentences[2][:150] if len(all_sentences) > 2 else "Systematic execution requires evaluating prerequisite constraints."
            scene_configs = [
                (SceneType.TITLE, target.concept_name, "Deep Dive Conceptual Lesson", None, None, None, None, None, None),
                (SceneType.EXPLANATION, f"Definition & Core Architecture: {target.concept_name}", None, clean_snippet[:160], None, None, None, None, None),
                (SceneType.DIAGRAM, f"{target.concept_name} Structural Framework", "Component Architecture", None, None, "concept_flow", None, None, None),
                (SceneType.EXAMPLE, f"Operational Workflow: {target.concept_name}", "Applied Context", s2_text, None, None, None, None, None),
                (SceneType.EXPLANATION, "Key Insights & Implementation Details", None, s3_text, None, None, None, None, None),
                (SceneType.SUMMARY, "Mastery Summary & Review Checklist", None, None, None, None, None, None, None),
            ]
            narration_templates = [
                f"Welcome to this in-depth study session on {target.concept_name}. We will examine the core definitions, architectural principles, and concrete applications from your course materials.",
                f"First, consider the authoritative curriculum definition: {clean_snippet[:120]}. This foundational statement outlines the primary purpose and scope of the concept.",
                f"Examine the architectural workflow on screen. Notice how inputs and structural dependencies map directly into the core processing stages of {target.concept_name}.",
                f"In practical application: {s2_text[:120]}. Connecting theoretical concepts to tangible operations deepens intuition and diagnostic accuracy.",
                f"Furthermore: {s3_text[:120]}. Keeping these structural relationships clear prevents frequent conceptual pitfalls.",
                f"In conclusion, master these foundational rules, review key terminology, and apply these principles during your diagnostic assessments.",
            ]
    elif dur <= 230:
        weights = [0.08, 0.18, 0.18, 0.18, 0.16, 0.12, 0.10]
        s2_text = all_sentences[1][:150] if len(all_sentences) > 1 else clean_snippet[:130]
        s3_text = all_sentences[2][:150] if len(all_sentences) > 2 else "Component interactions determine overall system behavior."
        scene_configs = [
            (SceneType.TITLE, target.concept_name, "Comprehensive Academic Tutorial", None, None, None, None, None, None),
            (SceneType.EXPLANATION, f"Conceptual Foundations of {target.concept_name}", None, clean_snippet[:160], None, None, None, None, None),
            (SceneType.DIAGRAM, f"{target.concept_name} Structural Dynamics", "System Architecture", None, None, "concept_flow", None, None, None),
            (SceneType.EXPLANATION, "Detailed Methodological Analysis", None, s2_text, None, None, None, None, None),
            (SceneType.EXAMPLE, "Case Study & Real-World Application", "Applied Analysis", s3_text, None, None, None, None, None),
            (SceneType.EXPLANATION, "Common Pitfalls & Diagnostic Checks", None, f"Carefully verify foundational constraints when analyzing {target.concept_name}.", None, None, None, None, None),
            (SceneType.SUMMARY, "Formula & Concept Reference Guide", None, None, None, None, None, None, None),
        ]
        narration_templates = [
            f"Welcome to this comprehensive tutorial on {target.concept_name}. Over the next few minutes, we will explore the foundational principles, structural dynamics, and practical implementations.",
            f"Let us examine the authoritative definition presented in your verified materials: {clean_snippet[:130]}. This forms the basis for solving complex multi-step problems.",
            f"Observe the dynamic system model on screen. Notice how core data flow and relational components operate together within {target.concept_name}.",
            f"Digging deeper into the methodological breakdown: {s2_text[:130]}. Each component serves a vital role in maintaining structural integrity.",
            f"Consider practical applications: {s3_text[:130]}. Observing these dynamics in realistic environments clarifies how abstract rules produce measurable outcomes.",
            f"A common student mistake is overlooking subtle prerequisite relationships. Remember to distinguish between initial constraints and operational states.",
            f"To conclude, review these key takeaways: master the core definitions, verify system constraints, and practice diagnosing questions with confidence.",
        ]
    else:
        weights = [0.08, 0.14, 0.14, 0.16, 0.16, 0.14, 0.10, 0.08]
        s2_text = all_sentences[1][:150] if len(all_sentences) > 1 else clean_snippet[:140]
        s3_text = all_sentences[2][:150] if len(all_sentences) > 2 else "Analyzing foundational constraints enables predictable behavior."
        scene_configs = [
            (SceneType.TITLE, target.concept_name, "In-Depth Masterclass Lecture", None, None, None, None, None, None),
            (SceneType.EXPLANATION, f"Core Architecture & Context of {target.concept_name}", None, clean_snippet[:170], None, None, None, None, None),
            (SceneType.DIAGRAM, f"{target.concept_name} Comprehensive Flow", "Architecture & Workflow", None, None, "concept_flow", None, None, None),
            (SceneType.EXPLANATION, "Operational Analysis & In-Depth Walkthrough", None, s2_text, None, None, None, None, None),
            (SceneType.EXAMPLE, "Real-World Case Studies & Industry Applications", "Applied Context", s3_text, None, None, None, None, None),
            (SceneType.EXPLANATION, "Diagnostic Nuances & Edge Case Handling", None, f"Handling boundary conditions and edge cases in {target.concept_name}.", None, None, None, None, None),
            (SceneType.EXPLANATION, "Synthesis & Integration with Prerequisite Topics", None, "Connecting this topic to surrounding curriculum elements.", None, None, None, None, None),
            (SceneType.SUMMARY, "Complete Reference Checklist & Review Guide", None, None, None, None, None, None, None),
        ]
        narration_templates = [
            f"Welcome to this in-depth masterclass on {target.concept_name}. In this extended lecture, we will deeply investigate the conceptual origins, architectural structures, and concrete applications.",
            f"Let us examine the authoritative definitions presented in your curriculum: {clean_snippet[:140]}. Understanding this formal statement provides the clarity needed for mastery.",
            f"Look closely at the structural workflow on screen. Tracing each relationship from left to right demonstrates how components coordinate within {target.concept_name}.",
            f"Expanding our analysis to operational implementation: {s2_text[:140]}. Notice how each parameter directly influences final outcomes.",
            f"In practical engineering and analysis: {s3_text[:140]}. Seeing these principles applied in industry scenarios highlights their universal utility.",
            f"A frequent pitfall is conflating related terminology. Pay careful attention to distinct boundary conditions to avoid common diagnostic traps.",
            f"Connecting these concepts back to prerequisite foundations ensures lasting retention and solidifies your mastery across related topics.",
            f"In conclusion, review the core checklist, practice explaining the structural interactions, and proceed to the diagnostic review with confidence.",
        ]

    durations = [max(1.0, round(dur * w, 1)) for w in weights]
    diff = round(dur - sum(durations), 1)
    durations[-1] = max(1.0, round(durations[-1] + diff, 1))

    scenes: list[ScenePlan] = []
    narration: list[NarrationSegment] = []

    for idx, (cfg, seg_dur, narr_text) in enumerate(zip(scene_configs, durations, narration_templates)):
        stype, title, sub, text, eq_val, diag_type, obj_lbl, f_lbl, a_lbl = cfg
        summary_pts = [
            f"Mastery: {target.concept_name}",
            f"Key Concept: {all_sentences[0][:50] if all_sentences else target.concept_name}",
            "Review definitions to ensure complete understanding",
        ] if stype == SceneType.SUMMARY else []

        scenes.append(
            ScenePlan(
                scene_index=idx,
                scene_type=stype,
                title=title,
                subtitle=sub,
                text=text,
                equation=eq_val,
                label=sub or title,
                diagram_type=diag_type,
                object_label=obj_lbl,
                force_label=f_lbl,
                acceleration_label=a_lbl,
                summary_points=summary_pts,
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
        learning_objective=f"Master the core principles and structure of {target.concept_name}",
        key_points=[f"Understanding {target.concept_name}", "Analyzing structural relations", "Practical applications"],
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
            cids = payload.get("concept_ids", [])
            if target.concept_id in cids or any(target.concept_name.lower() in str(c).lower() for c in cids):
                evidence.append(payload)
        if not evidence and raw_chunks:
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

    dur = float(target.target_seconds or (30 if target.difficulty == "foundational" else (60 if target.difficulty == "advanced" else 45)))

    prompt = _VIDEO_PLAN_PROMPT.format(
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        definition=evidence[0].get("text", "")[:300] if evidence else target.directive,
        source_chunks=chunk_texts,
        duration=int(dur),
        score=int(target.score),
    )

    chunk_ids = target.chunk_ids or [c.get("chunk_id", "") for c in evidence if c.get("chunk_id")]
    try:
        raw = active_provider.generate_content(prompt)
        data = _parse_json(raw)

        # Parse scenes
        raw_scenes = data.get("scenes", [])
        scenes: list[ScenePlan] = []
        for i, s in enumerate(raw_scenes):
            raw_stype = str(s.get("scene_type", "EXPLANATION")).upper()
            try:
                stype = SceneType(raw_stype)
            except Exception:
                stype = SceneType.EXPLANATION
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
        # Normalize and auto-repair plan (scales durations to target_seconds and budgets narration rate)
        plan = normalize_and_repair_video_plan(plan, dur)
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
        fallback_plan = normalize_and_repair_video_plan(fallback_plan, dur)
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
