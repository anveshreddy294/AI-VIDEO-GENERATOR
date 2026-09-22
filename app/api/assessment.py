"""Step 2 API - Student Knowledge Profiling & Video Target Matrix Bridge.

Endpoints:
- POST /assessment/start               → Ingest Step 1 payload + Plan + Generate + Dispatch safe quiz
- POST /assessment/handoff             → Direct pipeline handoff alias from Step 1
- POST /assessment/submit              → Grade + Anti-Loop Kill Switch + Profile update + Video Target Matrix
- GET  /assessment/profile/{student_id}/{source_id}      → Retrieve student learning profile
- GET  /assessment/status/{session_id}                  → Check assessment session status
- GET  /assessment/video-target/{student_id}/{source_id} → Retrieve Step 3 Video Target Matrix
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Annotated

from fastapi import APIRouter, Body, HTTPException, Query

logger = logging.getLogger(__name__)

from ..core.config import settings
from ..services.storage import validate_id, serialized, commit_assessment, recover_assessment_commits
from ..services.assessment.engine import grade_submission
from ..services.assessment.generator import generate_question
from ..services.assessment.planner import _apply_prerequisite_pairing, classify_difficulty, plan_assessment
from ..services.assessment.profile import get_or_create_profile, save_profile
from ..services.assessment.schemas import (
    AssessmentSession,
    AssessmentStartRequest,
    AssessmentStartResponse,
    AssessmentSubmitResponse,
    ConceptSnapshot,
    ProfileSummary,
    Question,
    QuestionResult,
    SafeOption,
    SafeQuestion,
    StudentSubmission,
    reconstruct_kg_from_snapshot,
)
from ..services.assessment.session_store import load_session, save_session
from ..services.assessment.validator import is_duplicate, validate_grounding, validate_question
from ..services.assessment.video_target import (
    build_video_target_matrix,
    load_video_matrix,
    save_video_matrix,
)
from ..services.registry import get_source_record, load_knowledge_graph, load_rich_chunks
from ..services.schemas import ConceptNode, KnowledgeGraph

router = APIRouter(prefix="/assessment", tags=["Step 2 - Assessment & Profiling"])

# Execution parameters bound directly to central settings
MAX_QUESTIONS = settings.max_questions
ASSESSMENT_TTL_HOURS = settings.assessment_ttl_hours
MAX_RETRIES_PER_QUESTION = settings.max_question_retries


def _call_generate_question(
    concept: ConceptNode,
    source_id: str,
    provided_chunks: list[dict[str, Any]] | None,
    max_retries: int,
    variant_type: str,
) -> Question | None:
    """Invokes generate_question, passing variant_type if supported by function/mock."""
    try:
        return generate_question(
            concept=concept,
            source_id=source_id,
            provided_chunks=provided_chunks,
            max_retries=max_retries,
            variant_type=variant_type,
        )
    except TypeError as e:
        if "variant_type" in str(e):
            return generate_question(
                concept=concept,
                source_id=source_id,
                provided_chunks=provided_chunks,
                max_retries=max_retries,
            )
        raise


@router.post("/start", response_model=AssessmentStartResponse)
def start_assessment(
    payload: Annotated[AssessmentStartRequest | None, Body()] = None,
    student_id: Annotated[str | None, Query()] = None,
    source_id: Annotated[str | None, Query()] = None,
) -> AssessmentStartResponse:
    """Step 1 -> Step 2 Handoff: Ingest, Plan, Ground, Validate, and Dispatch.

    Execution Flow:
    1. Ingesting Step 1 JSON Payload & Session Integrity:
       - Receives Step 1 output (Topic Blueprint, Key Concepts, metadata)
       - Verifies Student ID and Source ID match across payload and session
       - Loads concepts and chunks into temporary working memory
    2. Dynamic Assessment Planning:
       - Balanced Cold Start (foundational, intermediate, advanced)
       - Prerequisite Pairing (foundational queued before dependent concepts)
    3. Grounded Question Generation:
       - Sends text chunk to Ollama with strict negative prompting
       - Provenance tracking (page numbers, chunk IDs, content IDs)
    4. Validation & Safe Quiz Dispatch:
       - Pydantic schema validation (exactly 4 options, non-empty)
       - Strips correct answers and dispatches sanitized quiz to frontend
    """
    # 1. Resolve student_id and source_id
    # Cleanly ignore placeholder values like "string" from Swagger UI templates
    body_student_id = (
        payload.student_id.strip()
        if payload and payload.student_id and payload.student_id.strip() not in ("", "string")
        else None
    )
    body_source_id = (
        payload.source_id.strip()
        if payload and payload.source_id and payload.source_id.strip() not in ("", "string")
        else None
    )

    req_source_id = source_id or body_source_id
    req_student_id = student_id or body_student_id or "student_default"

    if not req_source_id:
        raise HTTPException(
            status_code=400,
            detail="source_id is required either in the JSON body or as a query parameter.",
        )

    # Ingest Step 1 JSON and verify session integrity
    step1_data: dict[str, Any] = {}
    if payload:
        if payload.step1_output and isinstance(payload.step1_output, dict):
            step1_data = payload.step1_output
        else:
            step1_data = payload.model_dump(exclude_none=True)

    # Verify session integrity if Step 1 payload includes source_id / student_id
    payload_source_id = step1_data.get("source_id")
    if (
        payload_source_id
        and payload_source_id not in ("", "string")
        and req_source_id
        and payload_source_id != req_source_id
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Session integrity mismatch: request source_id '{req_source_id}' "
                   f"does not match Step 1 payload source_id '{payload_source_id}'.",
        )

    # 2. Extract or load KnowledgeGraph and concepts into temporary memory
    try:
        validate_id(req_source_id)
        validate_id(req_student_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    in_memory_kg = _extract_knowledge_graph_from_payload(step1_data, req_source_id)
    kg = in_memory_kg or load_knowledge_graph(req_source_id)

    if not in_memory_kg:
        record = get_source_record(req_source_id)
        if not record:
            raise HTTPException(status_code=404, detail="Source not found; ingest material first")
        if record.status != "READY":
            raise HTTPException(status_code=423, detail=f"Source is not ready: {record.status}")

    if not kg or not kg.concepts:
        raise HTTPException(
            status_code=422,
            detail=f"No concepts found for source '{req_source_id}'. The knowledge graph is empty.",
        )

    # Extract key concepts list from Step 1 JSON
    key_concepts = _extract_key_concepts(step1_data)

    # Extract any in-memory chunks provided in Step 1 JSON
    raw_chunks = (
        step1_data.get("chunks")
        or step1_data.get("rich_chunks")
        or load_rich_chunks(req_source_id)
        or None
    )
    if raw_chunks:
        provided_chunks = [
            rc.model_dump() if hasattr(rc, "model_dump") else rc
            for rc in raw_chunks
        ]
    else:
        provided_chunks = None

    # 3. Load or create Student Learning Profile
    profile = get_or_create_profile(req_student_id, req_source_id)

    raw_target = (
        payload.max_questions
        if payload and payload.max_questions is not None
        else settings.max_questions
    )
    target_questions = max(1, min(raw_target, settings.max_questions))

    # Identify kill-switch concepts to strictly exclude from planning & reserve pool
    kill_switch_ids: set[str] = {
        cid for cid, m in profile.concept_masteries.items()
        if m.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK")
    }

    all_available_concepts: list[ConceptNode] = [
        c for c in kg.concepts.values()
        if c and c.concept_id and c.concept_id not in kill_switch_ids
    ]
    if not all_available_concepts:
        raise HTTPException(
            status_code=422,
            detail="No concepts could be scheduled for assessment.",
        )

    # 4. Dynamic Assessment Planning (Cold Start + Prerequisite Pairing)
    concept_queue = plan_assessment(
        kg=kg,
        profile=profile,
        max_questions=target_questions,
        key_concepts=key_concepts,
    )

    # Filter any invalid or kill-switch concepts out of primary queue
    primary_candidates: list[ConceptNode] = [
        c for c in concept_queue
        if c and c.concept_id and c.concept_id not in kill_switch_ids
    ]

    # Build reserve pool from remaining KnowledgeGraph concepts
    primary_ids = {c.concept_id for c in primary_candidates}
    remaining_kg_concepts = [
        c for c in all_available_concepts
        if c.concept_id not in primary_ids
    ]
    # Order reserve pool preserving prerequisite hierarchy
    reserve_candidates = _apply_prerequisite_pairing(remaining_kg_concepts, list(kg.concepts.values()))
    reserve_candidates = [
        c for c in reserve_candidates
        if c.concept_id not in primary_ids
        and c.concept_id not in kill_switch_ids
    ]

    # 4b. Cache compact concept dependency snapshot for self-contained sessions (Phase 2B)
    concept_snapshot: dict[str, ConceptSnapshot] = {}
    for cid, c in kg.concepts.items():
        if not c or not c.concept_id:
            continue
        diff = classify_difficulty(c)
        concept_snapshot[c.concept_id] = ConceptSnapshot(
            concept_id=c.concept_id,
            concept_name=c.name or cid,
            definition=c.definition or "",
            prerequisite_concept_ids=list(c.prerequisite_concept_ids or []),
            source_content_ids=list(c.source_content_ids or []),
            difficulty=diff,
            source_id=req_source_id,
        )

    # 5. Create active session
    session = AssessmentSession(
        student_id=req_student_id,
        source_id=req_source_id,
        status="GENERATING",
        concept_queue=[c.concept_id for c in primary_candidates],
        concept_snapshot=concept_snapshot,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ASSESSMENT_TTL_HOURS)
    session.expires_at = expires_at.isoformat()

    # 6. Multi-Pass Grounded Generation + Validation + Provenance Tracking + Variant Backfill
    questions: list[Question] = []
    failed_concepts: list[str] = []
    concept_question_counts: dict[str, int] = {c.concept_id: 0 for c in all_available_concepts}
    concept_variants_used: dict[str, set[str]] = {c.concept_id: set() for c in all_available_concepts}

    VARIANTS = ["definition", "relationship", "application", "comparison", "misconception"]
    concept_count = len(all_available_concepts)
    max_questions_per_concept = (
        min(len(VARIANTS), target_questions)
        if concept_count <= 1
        else max(2, math.ceil(target_questions / concept_count))
    )

    context_text = " ".join(
        ch.get("text", "") for ch in (provided_chunks or [])
        if not ch.get("source_id") or ch.get("source_id") == req_source_id
    )

    def _try_generate_and_accept(concept: ConceptNode, variant: str) -> bool:
        if len(questions) >= target_questions:
            return False
        if concept_question_counts.get(concept.concept_id, 0) >= max_questions_per_concept:
            return False
        if variant in concept_variants_used.get(concept.concept_id, set()):
            return False

        q = _call_generate_question(
            concept=concept,
            source_id=req_source_id,
            provided_chunks=provided_chunks,
            max_retries=MAX_RETRIES_PER_QUESTION,
            variant_type=variant,
        )

        if q is None:
            failed_concepts.append(concept.concept_id)
            logger.warning(f"[assessment] Candidate rejected: {concept.name} (variant={variant}) reason=generation returned None")
            return False

        # Structural validation + source/provenance check
        is_valid, error = validate_question(q, allowed_source_id=req_source_id)
        if not is_valid:
            failed_concepts.append(concept.concept_id)
            logger.warning(f"[assessment] Candidate rejected: {concept.name} (variant={variant}) reason={error}")
            return False

        # Grounding validation
        grounding_ok, grounding_err = validate_grounding(q, q.evidence_text or context_text)
        if not grounding_ok:
            failed_concepts.append(concept.concept_id)
            logger.warning(f"[assessment] Candidate rejected: {concept.name} (variant={variant}) reason={grounding_err}")
            return False

        # Non-duplication check against existing questions
        if is_duplicate(q, questions):
            failed_concepts.append(concept.concept_id)
            logger.warning(f"[assessment] Candidate rejected: {concept.name} (variant={variant}) reason=duplicate question detected")
            return False

        # ACCEPT
        concept_question_counts[concept.concept_id] = concept_question_counts.get(concept.concept_id, 0) + 1
        concept_variants_used.setdefault(concept.concept_id, set()).add(variant)
        questions.append(q)
        logger.info(f"[assessment] Accepted question {len(questions)}/{target_questions}: {concept.name} (variant={variant})")
        return True

    # Pass 1: Primary candidates (Parallel generation with ThreadPoolExecutor)
    from concurrent.futures import ThreadPoolExecutor

    def _generate_candidate(c_node, v_type):
        try:
            q_res = _call_generate_question(
                concept=c_node,
                source_id=req_source_id,
                provided_chunks=provided_chunks,
                max_retries=MAX_RETRIES_PER_QUESTION,
                variant_type=v_type,
            )
            return (c_node, v_type, q_res)
        except Exception as exc:
            logger.warning("[assessment] Parallel candidate generation failed for %s: %s", c_node.name, exc)
            return (c_node, v_type, None)

    candidates_to_run = primary_candidates[:target_questions]
    if candidates_to_run:
        with ThreadPoolExecutor(max_workers=min(len(candidates_to_run), 2)) as pool:
            futures = [pool.submit(_generate_candidate, c, "definition") for c in candidates_to_run]
            for f in futures:
                if len(questions) >= target_questions:
                    break
                c, variant, q = f.result()
                if q is None:
                    if c.concept_id not in failed_concepts:
                        failed_concepts.append(c.concept_id)
                    logger.warning(f"[assessment] Candidate rejected: {c.name} (variant={variant}) reason=generation returned None")
                    continue

                is_valid, err = validate_question(q, allowed_source_id=req_source_id)
                if not is_valid:
                    if c.concept_id not in failed_concepts:
                        failed_concepts.append(c.concept_id)
                    logger.warning(f"[assessment] Candidate rejected: {c.name} (variant={variant}) reason={err}")
                    continue

                grounding_ok, g_err = validate_grounding(q, q.evidence_text or context_text)
                if not grounding_ok:
                    if c.concept_id not in failed_concepts:
                        failed_concepts.append(c.concept_id)
                    logger.warning(f"[assessment] Candidate rejected: {c.name} (variant={variant}) reason={g_err}")
                    continue

                if is_duplicate(q, questions):
                    if c.concept_id not in failed_concepts:
                        failed_concepts.append(c.concept_id)
                    logger.warning(f"[assessment] Candidate rejected: {c.name} (variant={variant}) reason=duplicate question detected")
                    continue

                concept_question_counts[c.concept_id] = concept_question_counts.get(c.concept_id, 0) + 1
                concept_variants_used.setdefault(c.concept_id, set()).add(variant)
                questions.append(q)
                logger.info(f"[assessment] Accepted parallel question {len(questions)}/{target_questions}: {c.name}")

    # Pass 2: Reserve candidates if target not reached
    if len(questions) < target_questions:
        for c in reserve_candidates:
            if len(questions) >= target_questions:
                break
            logger.info(f"[assessment] Backfilling with reserve concept: {c.name}")
            _try_generate_and_accept(c, "definition")

    # Pass 3: Multi-question backfill with distinct question variants
    if len(questions) < target_questions:
        logger.info(f"[assessment] Initiating multi-question variant backfill: {len(questions)}/{target_questions} accepted")
        remaining_variants = [v for v in VARIANTS if v != "definition"]
        candidate_pool = [c for c in primary_candidates if c.concept_id not in kill_switch_ids] + [
            c for c in reserve_candidates if c.concept_id not in kill_switch_ids
        ]

        max_backfill_attempts = target_questions * 3 + 5
        attempts = 0

        while len(questions) < target_questions and attempts < max_backfill_attempts:
            attempts += 1
            # Concepts eligible for another question
            eligible = [
                c for c in candidate_pool
                if concept_question_counts.get(c.concept_id, 0) < max_questions_per_concept
                and any(v not in concept_variants_used.get(c.concept_id, set()) for v in remaining_variants)
            ]
            if not eligible:
                break

            # Distribute fairly: lowest question count first
            eligible.sort(key=lambda c: (concept_question_counts.get(c.concept_id, 0), c.concept_id))

            progress_made = False
            for c in eligible:
                if len(questions) >= target_questions:
                    break
                unused_variant = next(
                    (v for v in remaining_variants if v not in concept_variants_used.get(c.concept_id, set())),
                    None,
                )
                if not unused_variant:
                    continue

                logger.info(f"[assessment] Backfilling variant '{unused_variant}' for concept: {c.name}")
                accepted = _try_generate_and_accept(c, unused_variant)
                if accepted:
                    progress_made = True
                    break

            if not progress_made:
                break

    # If candidates are exhausted before reaching target_questions
    shortfall = max(0, target_questions - len(questions))
    if shortfall > 0:
        logger.warning(
            f"[assessment] Candidates exhausted: requested={target_questions} "
            f"generated={len(questions)} shortfall={shortfall} "
            f"student='{req_student_id}' source='{req_source_id}'"
        )

    # Zero-question rescue: If no questions could be generated, synthesize questions directly from source context
    if not questions:
        logger.warning("[assessment] Rescuing zero-question session using grounded synthesis")
        from ..services.assessment.generator import _generate_grounded_fallback, search_concept_chunks
        rescue_concepts = [c for c in primary_candidates if c.concept_id not in kill_switch_ids] or [
            c for c in reserve_candidates if c.concept_id not in kill_switch_ids
        ] or list(all_available_concepts.values())

        for idx, c in enumerate(rescue_concepts):
            if len(questions) >= min(target_questions, 3):
                break
            v = VARIANTS[idx % len(VARIANTS)]
            c_chunks = search_concept_chunks(c, req_source_id, limit=3, provided_chunks=provided_chunks)
            if not c_chunks and provided_chunks:
                c_chunks = [ch for ch in provided_chunks if not ch.get("source_id") or ch.get("source_id") == req_source_id][:2]
            if c_chunks:
                rescue_q = _generate_grounded_fallback(
                    concept=c,
                    chunks=c_chunks,
                    chunk_ids=[ch.get("chunk_id", "") for ch in c_chunks if ch.get("chunk_id")],
                    content_ids=[cid for ch in c_chunks for cid in ch.get("content_ids", [])],
                    page_start=c_chunks[0].get("page_start", c_chunks[0].get("page")),
                    page_end=c_chunks[0].get("page_end"),
                    timestamp_start=c_chunks[0].get("timestamp_start"),
                    timestamp_end=c_chunks[0].get("timestamp_end"),
                    source_id=req_source_id,
                    difficulty="intermediate",
                    variant_type=v,
                    fallback_reason="Grounded zero-question rescue",
                )
                if not is_duplicate(rescue_q, questions):
                    questions.append(rescue_q)
                    logger.info(f"[assessment] Accepted rescue grounded question {len(questions)}/{target_questions}: {c.name}")

    if not questions:
        session.status = "FAILED"
        save_session(session)
        raise HTTPException(
            status_code=422,
            detail="Could not generate any valid questions from the source context.",
        )

    # 7. Safe Quiz Dispatch (Answers hidden, provenance retained for tracing)
    session.questions = questions
    session.concept_queue = [q.concept_id for q in questions]
    session.status = "READY"
    save_session(session)

    safe_questions: list[SafeQuestion] = []
    for q in questions:
        safe_q = SafeQuestion(
            question_id=q.question_id,
            concept_id=q.concept_id,
            concept_name=q.concept_name,
            stem=q.stem,
            options=[SafeOption(index=opt.index, text=opt.text) for opt in q.options],
            difficulty=q.difficulty,
            variant_type=q.variant_type,
            page_start=q.page_start,
            page_end=q.page_end,
            chunk_ids=q.chunk_ids,
            timestamp_start=q.timestamp_start,
            timestamp_end=q.timestamp_end,
        )
        safe_questions.append(safe_q)

    return AssessmentStartResponse(
        status="READY",
        session_id=session.session_id,
        student_id=req_student_id,
        source_id=req_source_id,
        expires_at=session.expires_at,
        question_count=len(questions),
        questions=safe_questions,
        concepts_tested=[q.concept_name for q in questions],
        failed_concepts=failed_concepts,
        requested_questions=target_questions,
        generated_questions=len(questions),
        shortfall=shortfall,
    )


@router.post("/handoff", response_model=AssessmentStartResponse)
def handoff_from_step1(payload: AssessmentStartRequest) -> AssessmentStartResponse:
    """Explicit pipeline handoff route: accepts Step 1 JSON and starts Step 2."""
    if not payload or not payload.source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    record = get_source_record(payload.source_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Source '{payload.source_id}' not found in registry.")
    if record.status != "READY":
        raise HTTPException(status_code=423, detail=f"Source '{payload.source_id}' is not ready: {record.status}")
    return start_assessment(payload=payload)


@router.post("/submit", response_model=AssessmentSubmitResponse)
@serialized
def submit_assessment(submission: StudentSubmission) -> AssessmentSubmitResponse:
    """Step 5 & 6: Grade submission, apply Kill Switch, and build Video Target Matrix.

    Execution Flow:
    1. Hidden answer key grading
    2. Student Learning Profile update with scores (e.g. Concept A: 100%, Concept B: 0%)
    3. Anti-Loop Kill Switch: concepts failed >3 times tagged REQUIRES_HUMAN_FALLBACK
    4. Prerequisite Gap Detection
    5. Video Target Matrix Generation: isolates failed concepts with duration scaling (30s/45s/60s)
    6. Persists matrix and terminates Step 2, handing off to Step 3.
    """
    recover_assessment_commits()
    session = load_session(submission.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{submission.session_id}' not found.")

    if session.status == "SUBMITTED":
        answers = {a.question_id: a.selected_index for a in submission.answers}
        if session.submission_response and len(answers) == len(submission.answers) and answers == session.submitted_answers:
            return AssessmentSubmitResponse.model_validate(session.submission_response)
        raise HTTPException(status_code=409, detail="This assessment has already been submitted.")

    if session.status != "READY":
        raise HTTPException(
            status_code=400,
            detail=f"Session is in '{session.status}' state, not ready for submission.",
        )

    # Validate submission answers integrity
    session_q_ids = {q.question_id for q in session.questions}
    submitted_q_ids = set()
    for ans in submission.answers:
        if ans.question_id not in session_q_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid question_id '{ans.question_id}' does not belong to session '{session.session_id}'.",
            )
        if ans.question_id in submitted_q_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate question_id '{ans.question_id}' in submission.",
            )
        submitted_q_ids.add(ans.question_id)

    # Load KnowledgeGraph (attempt normal registry load first)
    kg = load_knowledge_graph(session.source_id)
    if not kg:
        # Fallback 1 (Phase 2B): reconstruct minimal KnowledgeGraph from session concept_snapshot
        try:
            kg = reconstruct_kg_from_snapshot(session, expected_source_id=session.source_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not kg:
        # Fallback 2 (legacy backward compatibility): minimal KG from session questions
        kg = KnowledgeGraph(concepts={
            q.concept_id: ConceptNode(
                concept_id=q.concept_id,
                name=q.concept_name,
                prerequisite_concept_ids=[],
            )
            for q in session.questions
        })

    # Load profile
    profile = get_or_create_profile(session.student_id, session.source_id)

    try:
        result = grade_submission(submission, session, kg, profile)
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[assessment] Grading failed")
        raise HTTPException(status_code=500, detail=f"Grading failed: {exc}") from exc

    # Finalize session
    session.status = "SUBMITTED"
    session.submitted_at = datetime.now(timezone.utc).isoformat()

    # Step 6: Build the Video Target Matrix (Step 2 -> Step 3 Handoff)
    record = get_source_record(session.source_id)
    source_filename = record.filename if record else ""
    video_matrix = build_video_target_matrix(
        profile=profile,
        kg=kg,
        source_filename=source_filename,
        session=session,
        submission_result=result,
    )

    # Concept-level score breakdown (e.g. Concept A: 100%, Concept B: 0%)
    # Disambiguate if two concepts in the session share the same name (#64)
    session_cids = {q.concept_id for q in session.questions}
    names_seen = set()
    has_name_collision = False
    for cid, m in profile.concept_masteries.items():
        if cid in session_cids:
            c_name = m.concept_name or cid
            if c_name in names_seen:
                has_name_collision = True
                break
            names_seen.add(c_name)

    concept_scores = {
        (f"{m.concept_name} ({cid})" if has_name_collision else (m.concept_name or cid)): round(m.last_score, 1)
        for cid, m in profile.concept_masteries.items()
        if cid in session_cids
    }

    profile_summary = ProfileSummary(
        overall_score=round(profile.overall_score, 1),
        strong_concepts=profile.strong_concepts,
        weak_concepts=profile.weak_concepts,
        strong_concept_ids=profile.strong_concept_ids,
        weak_concept_ids=profile.weak_concept_ids,
    )

    response = AssessmentSubmitResponse(
        status="SUBMITTED",
        session_id=result.session_id,
        score=result.score,
        total=result.total,
        percentage=round(result.percentage, 1),
        results=[
            QuestionResult(
                question_id=r.question_id,
                concept_id=r.concept_id,
                correct=r.correct,
                selected_index=r.selected_index,
                correct_index=r.correct_index,
                explanation=r.explanation,
            )
            for r in result.results
        ],
        prerequisite_gaps=result.prerequisite_gaps,
        profile_summary=profile_summary,
        concept_scores=concept_scores,
        video_target_matrix=video_matrix,
    )
    session.submission_response = response.model_dump()
    session.submitted_answers = {a.question_id: a.selected_index for a in submission.answers}
    commit_assessment(session, profile, video_matrix)
    return response


@router.get("/profile/{student_id}/{source_id}")
def get_profile(student_id: str, source_id: str):
    """Retrieve the persistent Student Learning Profile."""
    profile = get_or_create_profile(student_id, source_id)
    if profile.total_sessions == 0:
        return {
            "status": "NO_DATA",
            "message": "No assessment sessions completed yet.",
            "student_id": student_id,
            "source_id": source_id,
        }

    return {
        "status": "OK",
        "student_id": profile.student_id,
        "source_id": profile.source_id,
        "overall_score": round(profile.overall_score, 1),
        "total_sessions": profile.total_sessions,
        "strong_concepts": profile.strong_concepts,
        "weak_concepts": profile.weak_concepts,
        "strong_concept_ids": profile.strong_concept_ids,
        "weak_concept_ids": profile.weak_concept_ids,
        "prerequisite_gaps": profile.prerequisite_gaps,
        "concept_masteries": {
            cid: {
                "concept_name": m.concept_name,
                "attempts": m.attempts,
                "correct_attempts": m.correct_attempts,
                "status": m.status,
                "iteration_count": m.iteration_count,
                "last_score": round(m.last_score, 1),
            }
            for cid, m in profile.concept_masteries.items()
        },
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.get("/status/{session_id}")
def get_session_status(session_id: str):
    """Check the status of an assessment session."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    return {
        "session_id": session.session_id,
        "status": session.status,
        "student_id": session.student_id,
        "source_id": session.source_id,
        "question_count": len(session.questions),
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "submitted_at": session.submitted_at,
    }


@router.get("/video-target/{student_id}/{source_id}")
def get_video_target_matrix_endpoint(student_id: str, source_id: str):
    """Step 3 Consumption Route: Retrieve the strict Video Target Matrix."""
    matrix = load_video_matrix(student_id, source_id)
    if not matrix:
        raise HTTPException(
            status_code=404,
            detail=f"No Video Target Matrix found for student '{student_id}' on source '{source_id}'. "
                   "Complete an assessment submission first.",
        )
    return matrix.model_dump()


def _extract_knowledge_graph_from_payload(
    payload: dict[str, Any], source_id: str
) -> KnowledgeGraph | None:
    """Extract or build a KnowledgeGraph from in-memory Step 1 JSON payload."""
    # Check if knowledge_graph object is present
    kg_data = payload.get("knowledge_graph")
    if isinstance(kg_data, dict) and "concepts" in kg_data:
        try:
            return KnowledgeGraph.model_validate(kg_data)
        except Exception:
            pass

    # Check if topic_blueprint with key_concepts is present
    blueprint = payload.get("topic_blueprint") or {}
    key_concepts = blueprint.get("key_concepts") or payload.get("key_concepts") or []
    if key_concepts and isinstance(key_concepts, list):
        concepts_map = {}
        for item in key_concepts:
            if isinstance(item, str):
                cid = f"CONCEPT_{item.strip().upper().replace(' ', '_')}"
                concepts_map[cid] = ConceptNode(concept_id=cid, name=item)
            elif isinstance(item, dict) and "name" in item:
                cid = item.get("concept_id") or f"CONCEPT_{item['name'].strip().upper().replace(' ', '_')}"
                concepts_map[cid] = ConceptNode(
                    concept_id=cid,
                    name=item["name"],
                    definition=item.get("definition"),
                    prerequisite_concept_ids=item.get("prerequisite_concept_ids", []),
                )
        if concepts_map:
            return KnowledgeGraph(concepts=concepts_map)

    return None


def _extract_key_concepts(payload: dict[str, Any]) -> list[str]:
    """Extract list of key concepts from Step 1 JSON."""
    blueprint = payload.get("topic_blueprint") or {}
    kc = blueprint.get("key_concepts") or payload.get("key_concepts") or []
    result = []
    for item in kc:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and "name" in item:
            result.append(item["name"])
    return result
