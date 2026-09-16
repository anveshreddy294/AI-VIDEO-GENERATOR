"""Step 2 API — Student Knowledge Profiling endpoints.

POST /assessment/start      → Plan + Generate + Dispatch quiz
POST /assessment/submit     → Grade + Mastery + Profile update
GET  /assessment/profile/{student_id}/{source_id} → Retrieve learning profile
GET  /assessment/status/{session_id}               → Check session status
"""

import traceback
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from ..services.registry import get_source_record, load_knowledge_graph
from ..services.assessment.schemas import (
    AssessmentSession,
    StudentSubmission,
    StudentLearningProfile,
)
from ..services.assessment.planner import plan_assessment
from ..services.assessment.generator import generate_question
from ..services.assessment.validator import validate_question, is_duplicate
from ..services.assessment.engine import grade_submission
from ..services.assessment.profile import get_or_create_profile, save_profile
from ..services.assessment.session_store import save_session, load_session

router = APIRouter(prefix="/assessment", tags=["Step 2 — Assessment"])

# Config
MAX_QUESTIONS = 10
ASSESSMENT_TTL_HOURS = 24
MAX_RETRIES_PER_QUESTION = 2


@router.post("/start")
def start_assessment(student_id: str, source_id: str):
    """Step 1-5: Initialize, Plan, Generate, Validate, Dispatch a quiz.

    Flow:
    1. Lock Check: verify source status == READY
    2. Load KnowledgeGraph from registry
    3. Load or create StudentLearningProfile
    4. Plan concept queue with prerequisite pairing
    5. Sequentially generate grounded questions (one per concept)
    6. Validate each question (structure + dedup)
    7. Dispatch the validated quiz (strip correct answers)
    """
    # Step 1: Lock Check
    record = get_source_record(source_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
    if record.status != "READY":
        raise HTTPException(
            status_code=423,
            detail=f"Source '{source_id}' is not ready (status: {record.status}). "
                   "Wait for ingestion to complete.",
        )

    # Step 2: Load KnowledgeGraph
    kg = load_knowledge_graph(source_id)
    if not kg or not kg.concepts:
        raise HTTPException(
            status_code=422,
            detail=f"Source '{source_id}' has no extracted concepts. "
                   "The knowledge graph is empty.",
        )

    # Step 3: Load or create StudentLearningProfile
    profile = get_or_create_profile(student_id, source_id)

    # Step 4: Plan concept queue
    concept_queue = plan_assessment(kg, profile, max_questions=MAX_QUESTIONS)
    if not concept_queue:
        raise HTTPException(
            status_code=422,
            detail="No concepts available for assessment.",
        )

    # Step 5: Create session
    session = AssessmentSession(
        student_id=student_id,
        source_id=source_id,
        status="GENERATING",
        concept_queue=[c.concept_id for c in concept_queue],
    )

    # Set expiry
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ASSESSMENT_TTL_HOURS)
    session.expires_at = expires_at.isoformat()

    # Step 5-6: Sequential grounded generation + validation
    questions = []
    failed_concepts: list[str] = []

    for concept in concept_queue:
        question = generate_question(
            concept, source_id, max_retries=MAX_RETRIES_PER_QUESTION
        )

        if question is None:
            failed_concepts.append(concept.concept_id)
            continue

        # Validate structure
        is_valid, error = validate_question(question)
        if not is_valid:
            print(f"[assessment] Question for '{concept.name}' failed validation: {error}")
            failed_concepts.append(concept.concept_id)
            continue

        # Check duplicate
        if is_duplicate(question, questions):
            print(f"[assessment] Question for '{concept.name}' is duplicate, skipping")
            failed_concepts.append(concept.concept_id)
            continue

        questions.append(question)

    if not questions:
        session.status = "FAILED"
        save_session(session)
        raise HTTPException(
            status_code=422,
            detail="Could not generate any valid questions. "
                   "The source material may not have enough content in Qdrant.",
        )

    # Step 7: Dispatch — strip correct answers for frontend
    session.questions = questions
    session.status = "READY"
    save_session(session)

    # Build safe response (no correct_answer exposed)
    safe_questions = []
    for q in questions:
        safe_questions.append({
            "question_id": q.question_id,
            "concept_name": q.concept_name,
            "stem": q.stem,
            "options": [{"index": opt.index, "text": opt.text} for opt in q.options],
            "difficulty": q.difficulty,
        })

    return {
        "status": "READY",
        "session_id": session.session_id,
        "student_id": student_id,
        "source_id": source_id,
        "expires_at": session.expires_at,
        "question_count": len(questions),
        "questions": safe_questions,
        "concepts_tested": list({q.concept_name for q in questions}),
        "failed_concepts": failed_concepts,
    }


@router.post("/submit")
def submit_assessment(submission: StudentSubmission):
    """Step 6: Grade submission, update mastery, detect prerequisite gaps."""
    # Load session
    session = load_session(submission.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{submission.session_id}' not found.")

    if session.status == "SUBMITTED":
        raise HTTPException(status_code=409, detail="This assessment has already been submitted.")

    if session.status != "READY":
        raise HTTPException(status_code=400, detail=f"Session is in '{session.status}' state, not ready for submission.")

    # Load KnowledgeGraph
    kg = load_knowledge_graph(session.source_id)
    if not kg:
        raise HTTPException(status_code=500, detail="Knowledge graph not found for source.")

    # Load profile
    profile = get_or_create_profile(session.student_id, session.source_id)

    try:
        # Grade
        result = grade_submission(submission, session, kg, profile)
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except Exception as exc:
        print(f"[assessment] Grading failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Grading failed: {exc}") from exc

    # Update session status
    session.status = "SUBMITTED"
    session.submitted_at = datetime.now(timezone.utc).isoformat()
    save_session(session)

    # Save updated profile
    save_profile(profile)

    return {
        "status": "SUBMITTED",
        "session_id": result.session_id,
        "score": result.score,
        "total": result.total,
        "percentage": round(result.percentage, 1),
        "results": [
            {
                "question_id": r.question_id,
                "concept_id": r.concept_id,
                "correct": r.correct,
            }
            for r in result.results
        ],
        "prerequisite_gaps": result.prerequisite_gaps,
        "profile_summary": {
            "overall_score": round(profile.overall_score, 1),
            "strong_concepts": profile.strong_concepts,
            "weak_concepts": profile.weak_concepts,
        },
    }


@router.get("/profile/{student_id}/{source_id}")
def get_profile(student_id: str, source_id: str):
    """Step 7: Retrieve the student's learning profile."""
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
        "prerequisite_gaps": profile.prerequisite_gaps,
        "concept_masteries": {
            cid: {
                "concept_name": m.concept_name,
                "attempts": m.attempts,
                "correct_attempts": m.correct_attempts,
                "status": m.status,
                "iteration_count": m.iteration_count,
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
