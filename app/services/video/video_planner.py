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
    """Deterministic fallback synthesis if LLM is offline or output is invalid."""
    dur = float(target.target_seconds or (30 if target.difficulty == "foundational" else (60 if target.difficulty == "advanced" else 45)))
    
    # Proportional durations across 5 pedagogical scenes (Section 9)
    weights = [0.12, 0.28, 0.28, 0.18, 0.14]
    durations = [max(1.0, round(dur * w, 1)) for w in weights]
    diff = round(dur - sum(durations), 1)
    durations[-1] = max(1.0, round(durations[-1] + diff, 1))

    first_chunk_text = evidence_chunks[0].get("text", "") if evidence_chunks else target.directive
    clean_snippet = first_chunk_text[:180].replace("\n", " ")

    # Detect equation if present
    eq = "F = ma" if "force" in target.concept_name.lower() or "second law" in target.concept_name.lower() else (
        "p = mv" if "momentum" in target.concept_name.lower() else f"Concept: {target.concept_name}"
    )

    chunk_ids = target.chunk_ids or [c.get("chunk_id", "") for c in evidence_chunks if c.get("chunk_id")]

    scenes = [
        ScenePlan(
            scene_index=0,
            scene_type=SceneType.TITLE,
            title=target.concept_name,
            subtitle="Core Pedagogical Concept Review",
            duration_seconds=durations[0],
            source_chunk_ids=chunk_ids,
            page_start=target.page_start,
            page_end=target.page_end,
        ),
        ScenePlan(
            scene_index=1,
            scene_type=SceneType.EXPLANATION,
            title=f"Understanding {target.concept_name}",
            text=clean_snippet,
            label=f"Core Concept: {target.concept_name}",
            duration_seconds=durations[1],
            source_chunk_ids=chunk_ids,
            page_start=target.page_start,
            page_end=target.page_end,
        ),
        ScenePlan(
            scene_index=2,
            scene_type=SceneType.EQUATION if " = " in eq else SceneType.DIAGRAM,
            title=f"Governing Principle: {target.concept_name}",
            equation=eq if " = " in eq else None,
            diagram_type="force_box" if " = " not in eq else None,
            object_label="Object / State",
            force_label="Applied Force",
            acceleration_label="Resulting Change",
            label=f"Governing Relation: {eq}",
            duration_seconds=durations[2],
            source_chunk_ids=chunk_ids,
            page_start=target.page_start,
            page_end=target.page_end,
        ),
        ScenePlan(
            scene_index=3,
            scene_type=SceneType.EXAMPLE,
            title=f"Concrete Example: {target.concept_name}",
            text=f"Consider a physical scenario governed by {target.concept_name}, demonstrating direct proportional response.",
            label="Real-World Application",
            duration_seconds=durations[3],
            source_chunk_ids=chunk_ids,
            page_start=target.page_start,
            page_end=target.page_end,
        ),
        ScenePlan(
            scene_index=4,
            scene_type=SceneType.SUMMARY,
            title="Key Takeaways",
            summary_points=[
                f"Core foundation: {target.concept_name}",
                "Key relationship observed directly in study material",
                "Review foundational prerequisites to solidify understanding",
            ],
            duration_seconds=durations[4],
            source_chunk_ids=chunk_ids,
            page_start=target.page_start,
            page_end=target.page_end,
        ),
    ]

    narration = [
        NarrationSegment(
            scene_index=0,
            text=f"Welcome to this remedial lesson on {target.concept_name}.",
            target_seconds=durations[0],
        ),
        NarrationSegment(
            scene_index=1,
            text=f"Let's focus on the authoritative definition: {clean_snippet[:90]}.",
            target_seconds=durations[1],
        ),
        NarrationSegment(
            scene_index=2,
            text=f"Notice how the governing relation {eq} describes the system behavior.",
            target_seconds=durations[2],
        ),
        NarrationSegment(
            scene_index=3,
            text=f"In practice, observing these principles clarifies the underlying physical laws.",
            target_seconds=durations[3],
        ),
        NarrationSegment(
            scene_index=4,
            text=f"Remember these core takeaways to master {target.concept_name}.",
            target_seconds=durations[4],
        ),
    ]

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
