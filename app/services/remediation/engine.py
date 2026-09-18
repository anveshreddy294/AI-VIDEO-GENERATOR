"""Step 4: Remediation Verification & Re-Testing Loop Engine.

Administers targeted 1-2 question verification checks for concepts covered in
remedial video lessons, evaluates responses, transitions concept mastery from
LEARNING to MASTERED, and updates the Video Target Matrix.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from ...core.config import settings
from ...services.assessment.generator import generate_question_for_concept
from ...services.assessment.planner import classify_difficulty
from ...services.assessment.profile import get_or_create_profile, save_profile
from ...services.assessment.providers import get_default_provider
from ...services.assessment.schemas import (
    AnswerSubmission,
    ConceptMastery,
    ConceptSnapshot,
    ProfileSummary,
    Question,
    SafeOption,
    SafeQuestion,
    AssessmentSession,
)
from ...services.assessment.session_store import load_session, save_session
from ...services.assessment.video_target import load_video_matrix, save_video_matrix
from ...services.registry import load_knowledge_graph
from ...services.schemas import ConceptNode, KnowledgeGraph

logger = logging.getLogger(__name__)


def create_remediation_session(
    student_id: str,
    source_id: str,
    concept_id: str,
    count: int = 1,
    mock_mode: bool = False,
) -> Tuple[AssessmentSession, List[SafeQuestion]]:
    """Create a targeted verification re-assessment session for a specific concept.

    Generates fresh questions grounded in source chunks using the 'application'
    or 'misconception' pedagogical variants to verify real comprehension.
    """
    # 1. Load KnowledgeGraph for concept metadata
    kg = load_knowledge_graph(source_id)
    concept_node: Optional[ConceptNode] = None
    if kg and kg.concepts:
        concept_node = kg.concepts.get(concept_id)

    if not concept_node:
        concept_node = ConceptNode(
            concept_id=concept_id,
            name=concept_id.replace("_", " ").title(),
            definition=f"Targeted remediation concept for source {source_id}.",
        )

    # 2. Setup provider (mock or active)
    provider = None
    if not mock_mode:
        try:
            provider = get_default_provider()
        except Exception as e:
            logger.warning("Could not initialize default provider: %s. Using fallback.", e)

    difficulty = classify_difficulty(concept_node) if hasattr(concept_node, "difficulty") else "intermediate"
    questions: List[Question] = []

    # 3. Generate targeted questions (default: 1 focused question)
    variants = ["application", "misconception"]
    for i in range(max(1, count)):
        variant = variants[i % len(variants)]
        try:
            q = generate_question_for_concept(
                concept=concept_node,
                source_id=source_id,
                difficulty=difficulty,
                variant_type=variant,
                llm_provider=provider,
            )
            if q:
                q.question_id = f"Q_REM_{uuid4().hex[:8]}"
                questions.append(q)
            else:
                raise ValueError("Question generation returned None")
        except Exception as e:
            logger.error("Failed to generate verification question for %s: %s", concept_id, e)
            # Deterministic fallback question
            fb_question = Question(
                question_id=f"Q_REM_{uuid4().hex[:8]}",
                concept_id=concept_node.concept_id,
                concept_name=concept_node.name,
                stem=f"Which statement correctly characterizes {concept_node.name} based on the authoritative study material?",
                options=[
                    {"index": 0, "text": concept_node.definition or f"{concept_node.name} is a governing relationship in this domain."},
                    {"index": 1, "text": f"{concept_node.name} operates inversely without regard to governing constraints."},
                    {"index": 2, "text": f"{concept_node.name} has no measurable effect under standard conditions."},
                    {"index": 3, "text": f"{concept_node.name} only applies when external forces are absent."},
                ],
                correct_index=0,
                explanation=f"Based on the core principles of {concept_node.name} presented in the lesson.",
                source_id=source_id,
                difficulty=difficulty,
                variant_type=variant,
            )
            questions.append(fb_question)

    # 4. Build concept snapshot for session
    snapshot = {
        concept_node.concept_id: ConceptSnapshot(
            concept_id=concept_node.concept_id,
            concept_name=concept_node.name,
            definition=concept_node.definition or "",
            prerequisite_concept_ids=list(concept_node.prerequisite_concept_ids or []),
            source_content_ids=list(concept_node.source_content_ids or []),
            difficulty=difficulty,
            source_id=source_id,
        )
    }

    # 5. Create and persist session
    session_id = f"SESS_REM_{uuid4().hex[:12]}"
    session = AssessmentSession(
        session_id=session_id,
        student_id=student_id,
        source_id=source_id,
        questions=questions,
        status="READY",
        concept_snapshot=snapshot,
    )
    save_session(session)

    # 6. Sanitize questions (strip hidden answer key)
    safe_questions: List[SafeQuestion] = []
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
        )
        safe_questions.append(safe_q)

    return session, safe_questions


def evaluate_remediation_submission(
    session_id: str,
    student_id: str,
    concept_id: str,
    answers: List[AnswerSubmission],
) -> Dict[str, Any]:
    """Grade remediation answers, update mastery, and resolve VideoTargetMatrix.

    Returns:
    - passed (bool)
    - score (int)
    - total (int)
    - percentage (float)
    - previous_status (str)
    - new_status (str)
    - message (str)
    - explanations (list of strings)
    - profile_summary (ProfileSummary)
    """
    # 1. Load session
    session = load_session(session_id)
    if not session:
        raise ValueError(f"Remediation session '{session_id}' not found.")

    if not session.questions:
        raise ValueError(f"Remediation session '{session_id}' has no questions.")

    # 2. Grade answers against answer key
    answer_map = {a.question_id: a.selected_index for a in answers}
    score = 0
    total = len(session.questions)
    explanations = []

    for q in session.questions:
        selected = answer_map.get(q.question_id, -1)
        is_correct = (selected == q.correct_index)
        if is_correct:
            score += 1
            explanations.append(f"Correct! {q.explanation}")
        else:
            correct_opt = q.options[q.correct_index].text if 0 <= q.correct_index < len(q.options) else "Unknown"
            explanations.append(f"Incorrect. The correct answer is: '{correct_opt}'. {q.explanation}")

    percentage = (score / total * 100.0) if total > 0 else 0.0
    passed = (percentage >= 70.0)

    # 3. Load StudentLearningProfile
    profile = get_or_create_profile(student_id, session.source_id)
    now = datetime.now(timezone.utc).isoformat()

    if concept_id not in profile.concept_masteries:
        concept_name = session.questions[0].concept_name if session.questions else concept_id
        profile.concept_masteries[concept_id] = ConceptMastery(
            concept_id=concept_id,
            concept_name=concept_name,
        )

    mastery = profile.concept_masteries[concept_id]
    previous_status = mastery.status
    mastery.attempts += 1
    mastery.last_attempt_at = now
    mastery.last_score = percentage

    # 4. State transition & Anti-Loop Kill Switch
    if passed:
        mastery.correct_attempts += 1
        mastery.consecutive_correct += 1
        mastery.status = "MASTERED"

        # Update profile strong/weak lists
        if mastery.concept_name and mastery.concept_name not in profile.strong_concepts:
            profile.strong_concepts.append(mastery.concept_name)
        if concept_id not in profile.strong_concept_ids:
            profile.strong_concept_ids.append(concept_id)

        if mastery.concept_name in profile.weak_concepts:
            profile.weak_concepts.remove(mastery.concept_name)
        if concept_id in profile.weak_concept_ids:
            profile.weak_concept_ids.remove(concept_id)

        # Update VideoTargetMatrix: remove resolved target
        matrix = load_video_matrix(student_id, session.source_id)
        if matrix:
            matrix.videos = [v for v in matrix.videos if v.concept_id != concept_id]
            if len(matrix.videos) == 0:
                if matrix.human_intervention_concepts:
                    matrix.decision = "HUMAN_INTERVENTION"
                    matrix.summary = f"Remaining items require human instructor intervention for: {', '.join(matrix.human_intervention_concepts)}."
                else:
                    matrix.decision = "ALL_MASTERED"
                    matrix.summary = "All assessed concepts in this assessment have been successfully mastered. No AI videos needed."
            else:
                matrix.summary = f"Remaining remediation targets: {len(matrix.videos)} concept(s)."
            save_video_matrix(matrix)

        message = f"Congratulations! You mastered '{mastery.concept_name}'."
    else:
        mastery.consecutive_correct = 0
        mastery.iteration_count += 1

        if mastery.iteration_count > settings.kill_switch_limit:
            mastery.status = "REQUIRES_HUMAN_FALLBACK"
            # Update matrix for instructor intervention
            matrix = load_video_matrix(student_id, session.source_id)
            if matrix:
                matrix.videos = [v for v in matrix.videos if v.concept_id != concept_id]
                if mastery.concept_name and mastery.concept_name not in matrix.human_intervention_concepts:
                    matrix.human_intervention_concepts.append(mastery.concept_name)
                if concept_id not in matrix.human_intervention_concept_ids:
                    matrix.human_intervention_concept_ids.append(concept_id)
                if len(matrix.videos) == 0:
                    matrix.decision = "HUMAN_INTERVENTION"
                    matrix.summary = f"Persistent knowledge gaps require human instructor intervention for: {', '.join(matrix.human_intervention_concepts)}."
                else:
                    matrix.summary = f"Remaining remediation targets: {len(matrix.videos)} concept(s). Notice: Instructor intervention required for {', '.join(matrix.human_intervention_concepts)}."
                save_video_matrix(matrix)
            message = (
                f"Knowledge gap persists for '{mastery.concept_name}' after repeated attempts. "
                "Flagged for human instructor intervention."
            )
        else:
            mastery.status = "LEARNING"
            message = f"Concept '{mastery.concept_name}' not yet mastered. Review the video and try again."

    # 5. Persist profile
    profile.updated_at = now
    save_profile(profile)

    # 6. Build summary
    summary = ProfileSummary(
        overall_score=round(profile.overall_score, 1),
        strong_concepts=profile.strong_concepts,
        weak_concepts=profile.weak_concepts,
        strong_concept_ids=profile.strong_concept_ids,
        weak_concept_ids=profile.weak_concept_ids,
    )

    return {
        "session_id": session_id,
        "student_id": student_id,
        "concept_id": concept_id,
        "concept_name": mastery.concept_name,
        "passed": passed,
        "score": score,
        "total": total,
        "percentage": round(percentage, 1),
        "previous_status": previous_status,
        "new_status": mastery.status,
        "message": message,
        "explanations": explanations,
        "profile_summary": summary.model_dump(),
    }
