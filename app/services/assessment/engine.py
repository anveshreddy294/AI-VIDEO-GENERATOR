"""Step 6 — Mastery Engine & Anti-Looping.

Grades submissions, tracks concept mastery with anti-looping protection,
detects prerequisite gaps, and enforces the kill switch.
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
    """Grade a student's submission against the backend answer key.

    Implements:
    - Timestamp validation (expires_at check)
    - Answer grading
    - False mastery protection (correct_attempts >= 2 for MASTERED)
    - Prerequisite gap detection
    - Kill switch (iteration_count > 3 → REQUIRES_FALLBACK)
    """
    # 1. Validate session hasn't expired
    if session.expires_at:
        expires = datetime.fromisoformat(session.expires_at)
        if datetime.now(timezone.utc) > expires:
            raise ValueError("Assessment has expired. Please start a new assessment.")

    # Build answer lookup
    answer_map = {q.question_id: q for q in session.questions}
    submission_map = {a.question_id: a for a in submission.answers}

    results: list[QuestionResult] = []
    concept_scores: dict[str, list[bool]] = {}  # concept_id → [correct?, ...]

    for question in session.questions:
        sub = submission_map.get(question.question_id)
        if sub is None:
            # Question not answered — treat as wrong
            selected = -1
            correct = False
        else:
            selected = sub.selected_index
            correct = selected == question.correct_index

        result = QuestionResult(
            question_id=question.question_id,
            concept_id=question.concept_id,
            correct=correct,
            selected_index=selected,
            correct_index=question.correct_index,
        )
        results.append(result)
        concept_scores.setdefault(question.concept_id, []).append(correct)

    # 2. Calculate overall score
    score = sum(1 for r in results if r.correct)
    total = len(results)
    percentage = (score / total * 100) if total > 0 else 0.0

    # 3. Update concept masteries with anti-looping protection
    now = datetime.now(timezone.utc).isoformat()
    for concept_id, correct_list in concept_scores.items():
        if concept_id not in profile.concept_masteries:
            concept = kg.concepts.get(concept_id)
            profile.concept_masteries[concept_id] = ConceptMastery(
                concept_id=concept_id,
                concept_name=concept.name if concept else "",
            )

        mastery = profile.concept_masteries[concept_id]
        mastery.attempts += 1
        mastery.last_attempt_at = now

        all_correct = all(correct_list)
        any_correct = any(correct_list)

        if all_correct:
            mastery.correct_attempts += 1
            mastery.consecutive_correct += 1
        else:
            mastery.consecutive_correct = 0
            mastery.iteration_count += 1

        # Determine status with anti-looping protection
        if mastery.correct_attempts >= 2 and mastery.consecutive_correct >= 1:
            mastery.status = "MASTERED"
        elif mastery.iteration_count > 3:
            mastery.status = "REQUIRES_FALLBACK"
        elif any_correct or mastery.correct_attempts >= 1:
            mastery.status = "LEARNING"
        else:
            mastery.status = "LEARNING"  # attempted but all wrong

    # 4. Prerequisite gap detection
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
                    gap_desc = (
                        f"Prerequisite gap: Failed '{concept.name}' (child) AND "
                        f"'{kg.concepts[prereq_id].name if prereq_id in kg.concepts else prereq_id}' (parent)"
                    )
                    prerequisite_gaps.append(gap_desc)

                    # Mark parent as weak too
                    if prereq_id in profile.concept_masteries:
                        profile.concept_masteries[prereq_id].status = "LEARNING"

    # 5. Update profile aggregates
    profile.total_sessions += 1
    profile.overall_score = (
        (profile.overall_score * (profile.total_sessions - 1) + percentage)
        / profile.total_sessions
    )

    # Recompute strong/weak concepts
    profile.strong_concepts = [
        m.concept_name for m in profile.concept_masteries.values()
        if m.status == "MASTERED" and m.concept_name
    ]
    profile.weak_concepts = [
        m.concept_name for m in profile.concept_masteries.values()
        if m.status in ("LEARNING", "REQUIRES_FALLBACK") and m.concept_name
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
    )
