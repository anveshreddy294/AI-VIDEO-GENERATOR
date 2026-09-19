from ..storage import atomic_json, validate_id, serialized
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
import logging
from pathlib import Path
from typing import Any

from ...core.config import settings
from ..schemas import KnowledgeGraph
from .planner import classify_difficulty
from .schemas import AssessmentSession, StudentLearningProfile, VideoTarget, VideoTargetMatrix

logger = logging.getLogger(__name__)

# Passing score threshold (percentage 0-100)
PASS_THRESHOLD = settings.assessment_pass_threshold

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
    submission_result: Any | None = None,
    include_historical: bool = False,
) -> VideoTargetMatrix:
    """Scan updated scores and build the authoritative Video Target Matrix for Step 3.

    Enforces strict current-session scoping:
    1. Only concepts demonstrated as weak/incorrect in THIS current session receive video targets.
    2. Concepts that passed (score >= pass_threshold) are filtered out.
    3. Older weak concepts from past sessions NOT tested in this session are excluded from `videos`
       (optionally placed in `historical_review_videos` if explicitly requested).
    4. Concepts on the Anti-Loop Kill Switch (>3 failed attempts) are routed to human intervention.
    5. Exact chunk provenance is recovered deterministically via Qdrant, falling back to ContentUnits.
    """
    from ...db.vector_store import retrieve_exact_chunks
    from ..registry import load_content_units

    videos: list[VideoTarget] = []
    historical_review_videos: list[VideoTarget] = []

    # Map session questions and submission results
    questions_by_concept: dict[str, list[Any]] = {}
    question_by_id: dict[str, Any] = {}
    results_by_qid: dict[str, Any] = {}

    if session and session.questions:
        for q in session.questions:
            question_by_id[q.question_id] = q
            questions_by_concept.setdefault(q.concept_id, []).append(q)

    if submission_result and hasattr(submission_result, "results") and submission_result.results:
        for r in submission_result.results:
            results_by_qid[r.question_id] = r

    # Determine tested concepts in this session
    session_concept_ids: set[str] = set(questions_by_concept.keys()) if session else set()

    # Identify concepts failed in THIS session
    failed_concepts_in_session: set[str] = set()
    concept_session_scores: dict[str, float] = {}

    if session:
        for cid, q_list in questions_by_concept.items():
            c_results = [results_by_qid[q.question_id] for q in q_list if q.question_id in results_by_qid]
            if c_results:
                correct_count = sum(1 for r in c_results if r.correct)
                score_pct = (correct_count / len(c_results)) * 100.0
            else:
                # If no submission result provided, check profile latest score
                score_pct = profile.concept_masteries.get(cid).last_score if cid in profile.concept_masteries else 0.0

            concept_session_scores[cid] = round(score_pct, 1)
            if score_pct < pass_threshold:
                failed_concepts_in_session.add(cid)
    else:
        # Fallback if no session object: evaluate profile masteries directly
        for cid, m in profile.concept_masteries.items():
            if m.status not in ("MASTERED", "REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK") and m.last_score < pass_threshold:
                failed_concepts_in_session.add(cid)
                concept_session_scores[cid] = round(m.last_score, 1)

    # 1. Build current-session video targets for failed concepts not on kill switch
    for concept_id in sorted(failed_concepts_in_session):
        mastery = profile.concept_masteries.get(concept_id)
        if mastery and mastery.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK"):
            continue

        concept = kg.concepts.get(concept_id)
        if not concept:
            continue

        difficulty = classify_difficulty(concept)
        duration = DURATION_BY_DIFFICULTY.get(difficulty, 30)
        c_score = concept_session_scores.get(concept_id, 0.0)

        # Select the primary failed question for this concept in this session
        q_list = questions_by_concept.get(concept_id, [])
        failed_q = None
        matched_result = None
        for q in q_list:
            r = results_by_qid.get(q.question_id)
            if r and not r.correct:
                failed_q = q
                matched_result = r
                break
        if not failed_q and q_list:
            failed_q = q_list[0]
            matched_result = results_by_qid.get(failed_q.question_id)

        # Extract question details
        q_id = failed_q.question_id if failed_q else ""
        q_stem = failed_q.stem if failed_q else ""
        sel_idx = matched_result.selected_index if matched_result else -1
        corr_idx = failed_q.correct_index if failed_q else (matched_result.correct_index if matched_result else -1)
        q_expl = failed_q.explanation if failed_q else ""

        # Formulate deterministic misconception description
        misconception = ""
        if failed_q and failed_q.options:
            if 0 <= sel_idx < len(failed_q.options):
                chosen_text = failed_q.options[sel_idx].text
                correct_text = failed_q.options[corr_idx].text if 0 <= corr_idx < len(failed_q.options) else ""
                misconception = (
                    f"Learner incorrectly selected: '{chosen_text}' instead of authoritative answer: '{correct_text}'. "
                    f"Key distinction: {q_expl}"
                )
            elif sel_idx == -1:
                misconception = f"Question was left unanswered. Core concept explanation: {q_expl}"
        if not misconception and q_expl:
            misconception = f"Conceptual gap: {q_expl}"

        # Prerequisite and gap analysis
        prereqs = list(concept.prerequisite_concept_ids or [])
        prereq_gaps = [pid for pid in prereqs if pid in failed_concepts_in_session]

        # Provenance fields
        chunk_ids = list(failed_q.chunk_ids) if failed_q and failed_q.chunk_ids else []
        source_content_ids = list(failed_q.content_ids) if failed_q and failed_q.content_ids else list(concept.source_content_ids or [])
        page_start = failed_q.page_start if failed_q else None
        page_end = failed_q.page_end if failed_q else None
        t_start = failed_q.timestamp_start if failed_q else None
        t_end = failed_q.timestamp_end if failed_q else None

        # Authoritative Evidence Resolution: Qdrant exact scroll -> ContentUnits fallback
        authoritative_evidence: list[str] = []
        source_id = session.source_id if session else profile.source_id

        # 1. Deterministic Qdrant match
        qdrant_chunks = retrieve_exact_chunks(
            source_id=source_id,
            chunk_ids=chunk_ids,
            concept_ids=[concept_id],
            limit=5,
        )
        for qc in qdrant_chunks:
            txt = qc.get("text")
            if txt and txt not in authoritative_evidence:
                authoritative_evidence.append(txt)

        # 2. Controlled fallback: Load ContentUnits from registry
        if not authoritative_evidence and source_id:
            all_cus = load_content_units(source_id) or []
            cu_map = {cu.content_id: cu for cu in all_cus}
            for cid_cu in source_content_ids:
                if cid_cu in cu_map and cu_map[cid_cu].text:
                    authoritative_evidence.append(cu_map[cid_cu].text)
            if not authoritative_evidence:
                # Search by concept name in text if direct CU IDs not found
                for cu in all_cus:
                    if concept.name.lower() in cu.text.lower() and cu.text not in authoritative_evidence:
                        authoritative_evidence.append(cu.text)
                        if len(authoritative_evidence) >= 2:
                            break

        # 3. Final guarantee: KnowledgeGraph definition
        if not authoritative_evidence and concept.definition:
            authoritative_evidence.append(concept.definition)

        directive = f"Generate a {duration}-second AI video explaining {concept.name}"
        video_objective = (
            f"Remediate conceptual gap in '{concept.name}' ({difficulty}): "
            f"address failed question '{q_stem[:80]}...' using authoritative source evidence."
        )

        videos.append(
            VideoTarget(
                session_id=session.session_id if session else "",
                student_id=profile.student_id,
                source_id=source_id,
                concept_id=concept.concept_id,
                concept_name=concept.name,
                definition=concept.definition or "",
                difficulty=difficulty,
                assessment_score=c_score,
                score=c_score,
                status="NEEDS_VIDEO",
                target_seconds=duration,
                video_objective=video_objective,
                directive=directive,
                question_id=q_id,
                question_stem=q_stem,
                selected_index=sel_idx,
                correct_index=corr_idx,
                explanation=q_expl,
                misconception=misconception,
                prerequisite_concept_ids=prereqs,
                prerequisite_gaps=prereq_gaps,
                chunk_ids=chunk_ids,
                source_content_ids=source_content_ids,
                page_start=page_start,
                page_end=page_end,
                timestamp_start=t_start,
                timestamp_end=t_end,
                authoritative_evidence=authoritative_evidence,
                scope="current_session",
            )
        )

    # 2. If historical review is explicitly enabled, isolate older weak concepts
    if include_historical:
        for cid, mastery in profile.concept_masteries.items():
            if cid in session_concept_ids:
                continue
            if mastery.status in ("MASTERED", "REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK"):
                continue
            if mastery.last_score >= pass_threshold:
                continue

            concept = kg.concepts.get(cid)
            if not concept:
                continue

            difficulty = classify_difficulty(concept)
            duration = DURATION_BY_DIFFICULTY.get(difficulty, 30)
            directive = f"Generate a {duration}-second historical review video explaining {concept.name}"

            historical_review_videos.append(
                VideoTarget(
                    session_id="",
                    student_id=profile.student_id,
                    source_id=profile.source_id,
                    concept_id=concept.concept_id,
                    concept_name=concept.name,
                    definition=concept.definition or "",
                    difficulty=difficulty,
                    assessment_score=round(mastery.last_score, 1),
                    score=round(mastery.last_score, 1),
                    status="NEEDS_VIDEO",
                    target_seconds=duration,
                    video_objective=f"Historical review: reinforce prior weak concept '{concept.name}'.",
                    directive=directive,
                    prerequisite_concept_ids=list(concept.prerequisite_concept_ids or []),
                    source_content_ids=list(concept.source_content_ids or []),
                    scope="historical_review",
                )
            )

    # Order videos: foundational first, then intermediate, then advanced
    difficulty_order = {"foundational": 0, "intermediate": 1, "advanced": 2}
    videos.sort(key=lambda v: (difficulty_order.get(v.difficulty, 1), v.concept_name))
    historical_review_videos.sort(key=lambda v: (difficulty_order.get(v.difficulty, 1), v.concept_name))

    # Identify kill-switch concepts requiring human intervention
    human_intervention_concepts = [
        m.concept_name or cid
        for cid, m in profile.concept_masteries.items()
        if m.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK")
    ]
    human_intervention_concept_ids = [
        cid
        for cid, m in profile.concept_masteries.items()
        if m.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK")
    ]
    has_kill_switch = bool(human_intervention_concepts)

    directives = [v.directive for v in videos]

    if not videos and not has_kill_switch:
        decision = "ALL_MASTERED"
        summary = "All assessed concepts in this assessment have been successfully mastered. No AI videos needed."
    elif not videos and has_kill_switch:
        decision = "HUMAN_INTERVENTION"
        summary = f"Persistent knowledge gaps require human instructor intervention for: {', '.join(human_intervention_concepts)}."
    elif videos and has_kill_switch:
        decision = "GENERATE_VIDEOS"
        notice = f"Notice: Persistent knowledge gaps require human instructor intervention for: {', '.join(human_intervention_concepts)}."
        summary = f"{', and '.join(directives)}. {notice}" if directives else notice
    else:
        decision = "GENERATE_VIDEOS"
        summary = ", and ".join(directives) + "." if directives else "Generate AI remedial videos."

    return VideoTargetMatrix(
        session_id=session.session_id if session else "",
        student_id=profile.student_id,
        source_id=profile.source_id,
        source_filename=source_filename,
        overall_score=round(profile.overall_score, 1),
        decision=decision,
        summary=summary,
        videos=videos,
        historical_review_videos=historical_review_videos,
        human_intervention_concepts=human_intervention_concepts,
        human_intervention_concept_ids=human_intervention_concept_ids,
    )


def save_video_matrix(matrix: VideoTargetMatrix) -> Path:
    """Save the Video Target Matrix to runtime disk for Step 3 ingestion."""
    from ...core.config import BASE_DIR, settings
    out_dir = getattr(settings, "video_targets_dir", BASE_DIR / "storage" / "runtime" / "video_targets")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_student = validate_id(matrix.student_id)
    safe_source = validate_id(matrix.source_id)
    out_file = out_dir / f"{safe_student}_{safe_source}.json"
    atomic_json(out_file, matrix.model_dump())
    return out_file


def load_video_matrix(student_id: str, source_id: str) -> VideoTargetMatrix | None:
    """Load an existing Video Target Matrix from runtime disk with legacy fallback."""
    from ...core.config import BASE_DIR, settings
    safe_student = validate_id(student_id)
    safe_source = validate_id(source_id)
    target_dir = getattr(settings, "video_targets_dir", BASE_DIR / "storage" / "runtime" / "video_targets")
    path = target_dir / f"{safe_student}_{safe_source}.json"
    if not path.exists():
        legacy_path = BASE_DIR / "storage" / "video_targets" / f"{safe_student}_{safe_source}.json"
        if legacy_path.exists():
            path = legacy_path

    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VideoTargetMatrix.model_validate(data)
    except Exception as exc:
        logger.warning("[video_target] Failed to load matrix at %s: %s", path, exc)
        return None
