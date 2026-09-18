"""Tests for Step 2 Hardening Phase 2C: Configuration & Stable Concept IDs.

Tests:
1. test_settings_kill_switch_limit_is_respected
2. test_settings_mastery_threshold_is_respected
3. test_profile_contains_weak_concept_ids
4. test_profile_contains_strong_concept_ids
5. test_old_profile_without_id_fields_loads
6. test_ids_match_knowledge_graph
7. test_no_magic_threshold_override
"""

import json
from app.core.config import settings
from app.services.assessment.engine import grade_submission, rebuild_profile_metrics
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentSession,
    ConceptMastery,
    Question,
    StudentLearningProfile,
    StudentSubmission,
)
from app.services.schemas import ConceptNode, KnowledgeGraph


def _build_test_kg():
    c1 = ConceptNode(
        concept_id="CONCEPT_FORCE",
        name="Force",
        definition="An interaction that changes an object's motion.",
        prerequisite_concept_ids=[],
        source_content_ids=["CU_01"],
    )
    c2 = ConceptNode(
        concept_id="CONCEPT_INERTIA",
        name="Inertia",
        definition="Tendency of an object to resist changes in its motion.",
        prerequisite_concept_ids=["CONCEPT_FORCE"],
        source_content_ids=["CU_02"],
    )
    c3 = ConceptNode(
        concept_id="CONCEPT_ACCELERATION",
        name="Acceleration",
        definition="Rate of change of velocity.",
        prerequisite_concept_ids=["CONCEPT_FORCE"],
        source_content_ids=["CU_03"],
    )
    return KnowledgeGraph(concepts={
        "CONCEPT_FORCE": c1,
        "CONCEPT_INERTIA": c2,
        "CONCEPT_ACCELERATION": c3,
    })


def _build_session_and_submission(concept_id, correct=True):
    kg = _build_test_kg()
    c = kg.concepts[concept_id]
    q = Question(
        question_id=f"Q_{concept_id}",
        concept_id=concept_id,
        concept_name=c.name,
        stem=f"Test question for {c.name}",
        options=[
            {"index": 0, "text": "Correct definition"},
            {"index": 1, "text": "Wrong A"},
            {"index": 2, "text": "Wrong B"},
            {"index": 3, "text": "Wrong C"},
        ],
        correct_index=0,
        explanation="Explanation",
        source_id="SRC_PHYSICS_101",
    )
    session = AssessmentSession(
        session_id=f"SESS_TEST_{concept_id}",
        student_id="STU_2C",
        source_id="SRC_PHYSICS_101",
        questions=[q],
    )
    submission = StudentSubmission(
        session_id=session.session_id,
        answers=[AnswerSubmission(question_id=q.question_id, selected_index=0 if correct else 1)],
    )
    return session, submission, kg


def test_settings_kill_switch_limit_is_respected():
    print("\n--- Running Test 1: test_settings_kill_switch_limit_is_respected ---")
    orig_limit = settings.kill_switch_limit
    try:
        # Set kill switch limit to 1 (more than 1 failure triggers it)
        settings.kill_switch_limit = 1

        profile = StudentLearningProfile(student_id="STU_2C", source_id="SRC_PHYSICS_101")
        session, submission, kg = _build_session_and_submission("CONCEPT_FORCE", correct=False)

        # 1st failure: iteration_count = 1 -> <= 1, remains LEARNING
        grade_submission(submission, session, kg, profile)
        assert profile.concept_masteries["CONCEPT_FORCE"].iteration_count == 1
        assert profile.concept_masteries["CONCEPT_FORCE"].status == "LEARNING"

        # 2nd failure: iteration_count = 2 -> > 1, triggers kill switch
        grade_submission(submission, session, kg, profile)
        assert profile.concept_masteries["CONCEPT_FORCE"].iteration_count == 2
        assert profile.concept_masteries["CONCEPT_FORCE"].status == "REQUIRES_HUMAN_FALLBACK"

        print(f"   [PASS] settings.kill_switch_limit=1 respected: triggered at iteration_count=2.")
    finally:
        settings.kill_switch_limit = orig_limit


def test_settings_mastery_threshold_is_respected():
    print("\n--- Running Test 2: test_settings_mastery_threshold_is_respected ---")
    orig_thresh = settings.mastery_threshold
    try:
        # Increase required mastery threshold to 3 correct attempts
        settings.mastery_threshold = 3

        profile = StudentLearningProfile(student_id="STU_2C", source_id="SRC_PHYSICS_101")
        session, submission, kg = _build_session_and_submission("CONCEPT_INERTIA", correct=True)

        # 1st correct: correct_attempts = 1 -> LEARNING
        grade_submission(submission, session, kg, profile)
        assert profile.concept_masteries["CONCEPT_INERTIA"].correct_attempts == 1
        assert profile.concept_masteries["CONCEPT_INERTIA"].status == "LEARNING"

        # 2nd correct: correct_attempts = 2 -> (under old default 2 this would be MASTERED, but with thresh=3 it must still be LEARNING)
        grade_submission(submission, session, kg, profile)
        assert profile.concept_masteries["CONCEPT_INERTIA"].correct_attempts == 2
        assert profile.concept_masteries["CONCEPT_INERTIA"].status == "LEARNING"

        # 3rd correct: correct_attempts = 3 -> MASTERED
        grade_submission(submission, session, kg, profile)
        assert profile.concept_masteries["CONCEPT_INERTIA"].correct_attempts == 3
        assert profile.concept_masteries["CONCEPT_INERTIA"].status == "MASTERED"

        print(f"   [PASS] settings.mastery_threshold=3 respected: requires exactly 3 correct attempts for MASTERED.")
    finally:
        settings.mastery_threshold = orig_thresh


def test_profile_contains_weak_concept_ids():
    print("\n--- Running Test 3: test_profile_contains_weak_concept_ids ---")
    profile = StudentLearningProfile(student_id="STU_2C", source_id="SRC_PHYSICS_101")
    profile.concept_masteries["CONCEPT_FORCE"] = ConceptMastery(
        concept_id="CONCEPT_FORCE",
        concept_name="Force",
        status="LEARNING",
    )
    profile.concept_masteries["CONCEPT_INERTIA"] = ConceptMastery(
        concept_id="CONCEPT_INERTIA",
        concept_name="Inertia",
        status="REQUIRES_HUMAN_FALLBACK",
    )
    profile.concept_masteries["CONCEPT_ACCELERATION"] = ConceptMastery(
        concept_id="CONCEPT_ACCELERATION",
        concept_name="Acceleration",
        status="MASTERED",
    )

    rebuild_profile_metrics(profile)

    assert "CONCEPT_FORCE" in profile.weak_concept_ids
    assert "CONCEPT_INERTIA" in profile.weak_concept_ids
    assert "CONCEPT_ACCELERATION" not in profile.weak_concept_ids
    assert "Force" in profile.weak_concepts
    assert "Inertia" in profile.weak_concepts

    print(f"   [PASS] weak_concept_ids properly populated: {profile.weak_concept_ids}")


def test_profile_contains_strong_concept_ids():
    print("\n--- Running Test 4: test_profile_contains_strong_concept_ids ---")
    profile = StudentLearningProfile(student_id="STU_2C", source_id="SRC_PHYSICS_101")
    profile.concept_masteries["CONCEPT_ACCELERATION"] = ConceptMastery(
        concept_id="CONCEPT_ACCELERATION",
        concept_name="Acceleration",
        status="MASTERED",
    )
    profile.concept_masteries["CONCEPT_FORCE"] = ConceptMastery(
        concept_id="CONCEPT_FORCE",
        concept_name="Force",
        status="LEARNING",
    )

    rebuild_profile_metrics(profile)

    assert "CONCEPT_ACCELERATION" in profile.strong_concept_ids
    assert "CONCEPT_FORCE" not in profile.strong_concept_ids
    assert "Acceleration" in profile.strong_concepts

    print(f"   [PASS] strong_concept_ids properly populated: {profile.strong_concept_ids}")


def test_old_profile_without_id_fields_loads():
    print("\n--- Running Test 5: test_old_profile_without_id_fields_loads ---")
    legacy_json = {
        "student_id": "STU_LEGACY_01",
        "source_id": "SRC_LEGACY_PHYSICS",
        "overall_score": 75.0,
        "total_sessions": 2,
        "strong_concepts": ["Force"],
        "weak_concepts": ["Inertia"],
        "prerequisite_gaps": [],
        "concept_masteries": {
            "CONCEPT_FORCE": {
                "concept_id": "CONCEPT_FORCE",
                "concept_name": "Force",
                "status": "MASTERED",
                "attempts": 2,
                "correct_attempts": 2,
                "consecutive_correct": 2,
            },
            "CONCEPT_INERTIA": {
                "concept_id": "CONCEPT_INERTIA",
                "concept_name": "Inertia",
                "status": "LEARNING",
                "attempts": 1,
                "correct_attempts": 0,
                "consecutive_correct": 0,
            }
        }
    }

    # Must load successfully without validation error
    profile = StudentLearningProfile.model_validate(legacy_json)
    assert profile.student_id == "STU_LEGACY_01"
    assert profile.strong_concepts == ["Force"]
    assert profile.weak_concepts == ["Inertia"]
    assert "CONCEPT_FORCE" in profile.strong_concept_ids
    assert "CONCEPT_INERTIA" in profile.weak_concept_ids

    # Also test completely minimal legacy JSON without concept_masteries
    minimal_legacy = {
        "student_id": "STU_MINIMAL",
        "source_id": "SRC_MINIMAL",
    }
    p_min = StudentLearningProfile.model_validate(minimal_legacy)
    assert p_min.strong_concept_ids == []
    assert p_min.weak_concept_ids == []

    print("   [PASS] Legacy profile JSON lacking concept ID fields loads cleanly and safely.")


def test_ids_match_knowledge_graph():
    print("\n--- Running Test 6: test_ids_match_knowledge_graph ---")
    kg = _build_test_kg()
    profile = StudentLearningProfile(student_id="STU_2C", source_id="SRC_PHYSICS_101")
    session, submission, kg = _build_session_and_submission("CONCEPT_FORCE", correct=True)

    grade_submission(submission, session, kg, profile)

    # Check that every concept ID in weak/strong exists in KnowledgeGraph
    all_profile_ids = profile.strong_concept_ids + profile.weak_concept_ids
    for cid in all_profile_ids:
        assert cid in kg.concepts, f"Profile ID '{cid}' must match a node in KnowledgeGraph"
        assert cid != kg.concepts[cid].name, f"Profile ID '{cid}' must be the concept_id, not the human name"

    print("   [PASS] All tracked concept IDs strictly match valid KnowledgeGraph concept nodes.")


def test_no_magic_threshold_override():
    print("\n--- Running Test 7: test_no_magic_threshold_override ---")
    orig_limit = settings.kill_switch_limit
    orig_thresh = settings.mastery_threshold

    try:
        # If there are hardcoded overrides (e.g. `if > 3` or `if >= 2`), setting
        # kill_switch_limit=5 and mastery_threshold=4 would be ignored or overridden.
        settings.kill_switch_limit = 5
        settings.mastery_threshold = 4

        profile = StudentLearningProfile(student_id="STU_2C", source_id="SRC_PHYSICS_101")
        session, submission, kg = _build_session_and_submission("CONCEPT_FORCE", correct=False)

        # Fail 4 times: under old hardcoded 3, this would hit kill switch.
        # Under settings.kill_switch_limit=5, it must NOT trigger.
        for i in range(4):
            grade_submission(submission, session, kg, profile)

        assert profile.concept_masteries["CONCEPT_FORCE"].iteration_count == 4
        assert profile.concept_masteries["CONCEPT_FORCE"].status == "LEARNING", (
            f"Expected status LEARNING with 4 failures (limit=5), got {profile.concept_masteries['CONCEPT_FORCE'].status}"
        )

        print("   [PASS] No magic threshold override: engine strictly obeys dynamic settings.")
    finally:
        settings.kill_switch_limit = orig_limit
        settings.mastery_threshold = orig_thresh


def main():
    print("=================================================================")
    print("  TESTING STEP 2 HARDENING: CONFIGURATION & CONCEPT IDS (PHASE 2C)")
    print("=================================================================")

    test_settings_kill_switch_limit_is_respected()
    test_settings_mastery_threshold_is_respected()
    test_profile_contains_weak_concept_ids()
    test_profile_contains_strong_concept_ids()
    test_old_profile_without_id_fields_loads()
    test_ids_match_knowledge_graph()
    test_no_magic_threshold_override()

    print("\n=================================================================")
    print("   ALL PHASE 2C CONFIG & CONCEPT ID TESTS PASSED!                ")
    print("=================================================================")


if __name__ == "__main__":
    main()
