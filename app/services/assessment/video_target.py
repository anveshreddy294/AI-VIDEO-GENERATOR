"""Step 6 — Video Generation Blueprint: Video Target Matrix Builder.

Goal: Tell Step 3 (AI Video Generation Engine) exactly which parts need AI videos.
Execution:
1. Scans the newly updated scores in StudentLearningProfile.
2. Filters out everything the student passed (score >= pass_threshold).
3. Filters out everything that hit the Anti-Loop Kill Switch (REQUIRES_HUMAN_FALLBACK).
4. Isolates the specific concepts the student failed.
5. Scales target video duration by conceptual depth:
   - Foundational: 30 seconds
   - Intermediate: 45 seconds
   - Advanced: 60 seconds
6. Generates the Video Target Matrix handoff JSON object with explicit directives:
   e.g. "Generate a 30-second AI video explaining Concept B, and a 45-second AI video explaining Concept C."
7. Persists the matrix and terminates Step 2, handing off to Step 3.
"""

import json
from pathlib import Path
from typing import Any

from ...core.config import settings
from ..schemas import KnowledgeGraph
from .planner import classify_difficulty
from .schemas import AssessmentSession, StudentLearningProfile, VideoTarget, VideoTargetMatrix

# Passing score threshold (percentage 0-100)
PASS_THRESHOLD = 70.0

# Duration scaling rule by difficulty tier
DURATION_BY_DIFFICULTY = {
    "foundational": 30,
    "intermediate": 45,
    "advanced": 60,
}


def build_video_target_matrix(
    profile: StudentLearningProfile,
    kg: KnowledgeGraph,
    source_filename: str = "",
    pass_threshold: float = PASS_THRESHOLD,
    session: AssessmentSession | None = None,
) -> VideoTargetMatrix:
    """Scan updated scores and build the Video Target Matrix for Step 3."""
    videos: list[VideoTarget] = []
    directives: list[str] = []

    # 1. Isolate failed concepts that have NOT hit the kill switch
    for concept_id, mastery in profile.concept_masteries.items():
        # Filter out kill-switch concepts
        if mastery.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK"):
            continue

        # Filter out passed concepts (score >= threshold or MASTERED)
        if mastery.status == "MASTERED" or mastery.last_score >= pass_threshold:
            continue

        # Student failed this concept
        concept = kg.concepts.get(concept_id)
        if not concept:
            continue

        difficulty = classify_difficulty(concept)
        duration = DURATION_BY_DIFFICULTY.get(difficulty, 30)
        directive = f"Generate a {duration}-second AI video explaining {concept.name}"
        directives.append(directive)

        # Extract provenance from session questions if available
        concept_chunk_ids: list[str] = []
        page_start: int | None = None
        page_end: int | None = None
        if session:
            for q in session.questions:
                if q.concept_id == concept_id:
                    concept_chunk_ids.extend(q.chunk_ids)
                    if q.page_start is not None:
                        page_start = q.page_start if page_start is None else min(page_start, q.page_start)
                    if q.page_end is not None:
                        page_end = q.page_end if page_end is None else max(page_end, q.page_end)
        concept_chunk_ids = list(dict.fromkeys(concept_chunk_ids))

        videos.append(
            VideoTarget(
                concept_id=concept.concept_id,
                concept_name=concept.name,
                definition=concept.definition or "",
                difficulty=difficulty,
                score=round(mastery.last_score, 1),
                status="NEEDS_VIDEO",
                target_seconds=duration,
                directive=directive,
                chunk_ids=concept_chunk_ids,
                source_content_ids=list(concept.source_content_ids),
                page_start=page_start,
                page_end=page_end,
            )
        )

    # Order videos: foundational first, then intermediate, then advanced
    difficulty_order = {"foundational": 0, "intermediate": 1, "advanced": 2}
    videos.sort(key=lambda v: (difficulty_order.get(v.difficulty, 1), v.concept_name))

    # Determine verdict and high-level summary
    has_kill_switch = any(
        m.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK")
        for m in profile.concept_masteries.values()
    )

    if not videos and not has_kill_switch and profile.total_sessions > 0:
        decision = "ALL_MASTERED"
        summary = "All assessed concepts have been successfully mastered. No AI videos needed."
    elif not videos and has_kill_switch:
        decision = "HUMAN_INTERVENTION"
        summary = "Persistent knowledge gaps require human instructor intervention."
    else:
        decision = "GENERATE_VIDEOS"
        summary = ", and ".join(directives) + "." if directives else "Generate AI remedial videos."
        if has_kill_switch:
            summary += " Note: One or more concepts hit the anti-loop kill switch and require human instructor intervention."

    return VideoTargetMatrix(
        student_id=profile.student_id,
        source_id=profile.source_id,
        source_filename=source_filename,
        overall_score=round(profile.overall_score, 1),
        decision=decision,
        summary=summary,
        videos=videos,
    )


def save_video_matrix(matrix: VideoTargetMatrix) -> Path:
    """Save the Video Target Matrix to disk for Step 3 ingestion."""
    from ...core.config import BASE_DIR
    out_dir = BASE_DIR / "storage" / "video_targets"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_student = matrix.student_id.replace("/", "_")
    safe_source = matrix.source_id.replace("/", "_")
    out_file = out_dir / f"{safe_student}_{safe_source}.json"
    out_file.write_text(
        json.dumps(matrix.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    return out_file


def load_video_matrix(student_id: str, source_id: str) -> VideoTargetMatrix | None:
    """Load an existing Video Target Matrix from disk."""
    from ...core.config import BASE_DIR
    safe_student = student_id.replace("/", "_")
    safe_source = source_id.replace("/", "_")
    path = BASE_DIR / "storage" / "video_targets" / f"{safe_student}_{safe_source}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VideoTargetMatrix.model_validate(data)
    except Exception as exc:
        print(f"[video_target] Failed to load matrix at {path}: {exc}")
        return None
