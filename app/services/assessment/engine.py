"""Step 5 — Scoring & Mastery Calculation Engine.

Goal: Grade student submissions, pinpoint exact knowledge gaps, and update the
Student Learning Profile with scores (e.g. Concept A: 100%, Concept B: 0%).
Implements:
1. Session expiration and answer key comparison
2. Anti-Loop Kill Switch: If a student has failed the same concept more than 3 times
   historically (iteration_count > 3), tag that concept as REQUIRES_HUMAN_FALLBACK
   so the system halts automated looping on it.
3. Prerequisite Gap Detection: Identifies cases where a student failed a child concept
   and simultaneously failed its foundational prerequisite.
"""

from datetime import datetime, timezone

from ..schemas import ConceptNode, KnowledgeGraph
from .schemas import (
    AssessmentSession,
    ConceptMastery,
    QuestionResult,
    StudentLearningProfile,
    StudentSubmission,
    SubmissionResult,
)


def grade_submission(
    submission: StudentSubmission,
    session: AssessmentSession,
    kg: KnowledgeGraph,
    profile: StudentLearningProfile,
) -> SubmissionResult:
    """Grade a student's submission against the backend hidden answer key.

    Enforces:
    - Session expiration check
    - Hidden answer grading
    - False mastery protection (requires 2+ correct attempts for MASTERED)
    - Anti-Loop Kill Switch (>3 failed attempts -> REQUIRES_HUMAN_FALLBACK)
    - Prerequisite gap detection
    """
    # 1. Validate session expiration
    if session.expires_at:
        expires = datetime.fromisoformat(session.expires_at)
        if datetime.now(timezone.utc) > expires:
            raise ValueError("Assessment session has expired. Please start a new assessment.")

    # 2. Build answer lookup
    submission_map = {a.question_id: a for a in submission.answers}
    results: list[QuestionResult] = []
    concept_scores: dict[str, list[bool]] = {}  # concept_id -> [correct?, ...]

    for question in session.questions:
        sub = submission_map.get(question.question_id)
        if sub is None:
            # Question was left unanswered -> treat as incorrect
            selected = -1
            correct = False
        else:
            selected = sub.selected_index
            correct = (selected == question.correct_index)

        result = QuestionResult(
            question_id=question.question_id,
            concept_id=question.concept_id,
            correct=correct,
            selected_index=selected,
            correct_index=question.correct_index,
        )
        results.append(result)
        concept_scores.setdefault(question.concept_id, []).append(correct)

    # 3. Overall calculation
    score = sum(1 for r in results if r.correct)
    total = len(results)
    percentage = (score / total * 100.0) if total > 0 else 0.0

    # 4. Update Student Learning Profile with Anti-Loop Kill Switch
    now = datetime.now(timezone.utc).isoformat()
    for concept_id, correct_list in concept_scores.items():
        if concept_id not in profile.concept_masteries:
            concept = kg.concepts.get(concept_id)
            profile.concept_masteries[concept_id] = ConceptMastery(
                concept_id=concept_id,
                concept_name=concept.name if concept else concept_id,
            )

        mastery = profile.concept_masteries[concept_id]
        mastery.attempts += 1
        mastery.last_attempt_at = now

        # Update per-concept score on this attempt (0.0 to 100.0)
        curr_score = (sum(correct_list) / len(correct_list) * 100.0) if correct_list else 0.0
        mastery.last_score = curr_score

        all_correct = all(correct_list)
        any_correct = any(correct_list)

        if all_correct:
            mastery.correct_attempts += 1
            mastery.consecutive_correct += 1
        else:
            mastery.consecutive_correct = 0
            mastery.iteration_count += 1

        # Determine status with Anti-Loop Kill Switch
        if mastery.iteration_count > 3:
            # Kill switch triggered: failed more than 3 times historically
            mastery.status = "REQUIRES_HUMAN_FALLBACK"
        elif mastery.correct_attempts >= 2 and mastery.consecutive_correct >= 1:
            mastery.status = "MASTERED"
        elif any_correct or mastery.correct_attempts >= 1:
            mastery.status = "LEARNING"
        else:
            mastery.status = "LEARNING"

    # 5. Prerequisite gap detection
    prerequisite_gaps: list[str] = []
    for concept_id, correct_list in concept_scores.items():
        concept = kg.concepts.get(concept_id)
        if not concept:
            continue

        child_failed = not all(correct_list)
        if child_failed:
            for prereq_id in concept.prerequisite_concept_ids:
                prereq_correct = concept_scores.get(prereq_id)
                if prereq_correct is not None and not all(prereq_correct):
                    parent_name = kg.concepts[prereq_id].name if prereq_id in kg.concepts else prereq_id
                    gap_desc = f"Prerequisite gap: Failed '{concept.name}' (child) AND '{parent_name}' (parent)"
                    prerequisite_gaps.append(gap_desc)
                    if prereq_id in profile.concept_masteries:
                        if profile.concept_masteries[prereq_id].status != "REQUIRES_HUMAN_FALLBACK":
                            profile.concept_masteries[prereq_id].status = "LEARNING"

    # 6. Profile aggregate metrics
    profile.total_sessions += 1
    profile.overall_score = (
        (profile.overall_score * (profile.total_sessions - 1) + percentage)
        / profile.total_sessions
    )

    profile.strong_concepts = [
        m.concept_name for m in profile.concept_masteries.values()
        if m.status == "MASTERED" and m.concept_name
    ]
    profile.weak_concepts = [
        m.concept_name for m in profile.concept_masteries.values()
        if m.status in ("LEARNING", "REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK") and m.concept_name
    ]
    profile.prerequisite_gaps = prerequisite_gaps
    profile.updated_at = now

    return SubmissionResult(
        session_id=session.session_id,
        student_id=session.student_id,
        source_id=session.source_id,
        score=score,
        total=total,
        percentage=percentage,
        results=results,
        prerequisite_gaps=prerequisite_gaps,
        graded_at=now,
    )
