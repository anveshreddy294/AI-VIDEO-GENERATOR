"""Phase 2A Step 2 Hardening: Robust Question Backfilling Tests.

Verifies:
A. test_question_backfill_after_validation_failure
B. test_question_backfill_after_duplicate
C. test_question_backfill_does_not_repeat_concepts
D. test_question_backfill_excludes_kill_switch
E. test_question_backfill_exhaustion
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

from app.main import app
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.schemas import (
    AssessmentOption,
    ConceptMastery,
    Question,
    StudentLearningProfile,
)

client = TestClient(app)


def _make_valid_question(concept_id: str, concept_name: str, source_id: str = "SRC_BACKFILL_TEST", stem: str | None = None) -> Question:
    """Helper to create a structurally valid Question."""
    return Question(
        concept_id=concept_id,
        concept_name=concept_name,
        stem=stem or f"Authoritative test question regarding {concept_name} fundamentals.",
        options=[
            AssessmentOption(index=0, text=f"Correct description of {concept_name}"),
            AssessmentOption(index=1, text=f"Plausible misconception A for {concept_name}"),
            AssessmentOption(index=2, text=f"Plausible misconception B for {concept_name}"),
            AssessmentOption(index=3, text=f"Plausible misconception C for {concept_name}"),
        ],
        correct_index=0,
        explanation=f"Based on authoritative definition of {concept_name}.",
        chunk_ids=["CHUNK_001"],
        content_ids=["CU_001"],
        page_start=1,
        page_end=2,
        source_id=source_id,
        difficulty="intermediate",
    )


def _build_step1_payload(concept_ids: list[str], source_id: str = "SRC_BACKFILL_TEST") -> dict:
    """Build a Step 1 JSON payload with specified concepts."""
    return {
        "status": "READY",
        "source_id": source_id,
        "asset_id": "AST_TEST",
        "filename": "physics_test.pdf",
        "modality": "pdf",
        "topic_blueprint": {
            "topic_name": "Backfill Test Physics",
            "key_concepts": [cid.replace("CONCEPT_", "").title() for cid in concept_ids],
            "difficulty_level": "intermediate",
        },
        "knowledge_graph": {
            "concepts": {
                cid: {
                    "concept_id": cid,
                    "name": cid.replace("CONCEPT_", "").title(),
                    "definition": f"Definition of {cid}",
                    "prerequisite_concept_ids": [],
                    "source_content_ids": ["CU_001"],
                }
                for cid in concept_ids
            }
        },
        "chunks": [
            {
                "chunk_id": "CHUNK_001",
                "text": "Authoritative study text regarding physics concepts and definitions.",
                "page_start": 1,
                "page_end": 2,
                "concept_ids": concept_ids,
                "content_ids": ["CU_001"],
                "source_id": source_id,
            }
        ],
    }


def test_question_backfill_after_validation_failure():
    """A. Request 3 questions. Force first candidate to fail validation.
    Ensure reserve candidate is attempted and final session reaches 3 valid questions.
    """
    print("\n--- Running Test A: test_question_backfill_after_validation_failure ---")
    source_id = "SRC_BACKFILL_A"
    student_id = "STU_BACKFILL_A"
    concepts = ["CONCEPT_ALPHA", "CONCEPT_BETA", "CONCEPT_GAMMA", "CONCEPT_DELTA"]
    step1_payload = _build_step1_payload(concepts, source_id=source_id)

    def mock_generate(concept, source_id, provided_chunks, max_retries):
        if concept.concept_id == "CONCEPT_ALPHA":
            # Return structurally invalid question (e.g. only 2 options)
            q = _make_valid_question(concept.concept_id, concept.name, source_id)
            q.options = q.options[:2]  # Truncate to fail validate_question
            return q
        return _make_valid_question(concept.concept_id, concept.name, source_id)

    with patch("app.api.assessment.generate_question", side_effect=mock_generate):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 3,
                "step1_output": step1_payload,
            },
        )
        assert resp.status_code == 200, f"Expected 200, got: {resp.text}"
        data = resp.json()
        assert data["question_count"] == 3, f"Expected 3 questions, got {data['question_count']}"
        assert data["requested_questions"] == 3
        assert data["shortfall"] == 0

        tested_concept_ids = [q["concept_id"] for q in data["questions"]]
        assert "CONCEPT_ALPHA" not in tested_concept_ids, "Failed candidate must not be accepted"
        assert "CONCEPT_ALPHA" in data["failed_concepts"], "Failed candidate must be in failed_concepts"
        assert len(tested_concept_ids) == 3
        print(f"   [PASS] Backfilled successfully! Tested concepts: {tested_concept_ids}")


def test_question_backfill_after_duplicate():
    """B. Make one generated question duplicate an existing question.
    Ensure another concept is used from the reserve queue.
    """
    print("\n--- Running Test B: test_question_backfill_after_duplicate ---")
    source_id = "SRC_BACKFILL_B"
    student_id = "STU_BACKFILL_B"
    concepts = ["CONCEPT_ONE", "CONCEPT_TWO", "CONCEPT_THREE", "CONCEPT_FOUR"]
    step1_payload = _build_step1_payload(concepts, source_id=source_id)

    duplicate_stem = "Duplicate stem testing identical text overlap for questions."

    def mock_generate(concept, source_id, provided_chunks, max_retries):
        if concept.concept_id == "CONCEPT_TWO":
            # Return duplicate stem of CONCEPT_ONE
            return _make_valid_question(concept.concept_id, concept.name, source_id, stem=duplicate_stem)
        if concept.concept_id == "CONCEPT_ONE":
            return _make_valid_question(concept.concept_id, concept.name, source_id, stem=duplicate_stem)
        return _make_valid_question(concept.concept_id, concept.name, source_id)

    with patch("app.api.assessment.generate_question", side_effect=mock_generate):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 3,
                "step1_output": step1_payload,
            },
        )
        assert resp.status_code == 200, f"Expected 200, got: {resp.text}"
        data = resp.json()
        assert data["question_count"] == 3, f"Expected 3 questions, got {data['question_count']}"

        tested_concept_ids = [q["concept_id"] for q in data["questions"]]
        # Exactly one of the duplicate pair was evaluated first and accepted; the second was rejected
        assert ("CONCEPT_ONE" in tested_concept_ids) ^ ("CONCEPT_TWO" in tested_concept_ids), (
            "Exactly one of the duplicate pair must be accepted and the other rejected"
        )
        assert ("CONCEPT_ONE" in data["failed_concepts"]) or ("CONCEPT_TWO" in data["failed_concepts"]), (
            "The duplicate concept must be tracked in failed_concepts"
        )
        assert "CONCEPT_FOUR" in tested_concept_ids, "Reserve concept CONCEPT_FOUR must be backfilled"
        print(f"   [PASS] Duplicate rejected and reserve backfilled! Tested: {tested_concept_ids}")


def test_question_backfill_does_not_repeat_concepts():
    """C. Ensure every accepted question has a unique concept_id."""
    print("\n--- Running Test C: test_question_backfill_does_not_repeat_concepts ---")
    source_id = "SRC_BACKFILL_C"
    student_id = "STU_BACKFILL_C"
    concepts = ["CONCEPT_K1", "CONCEPT_K2", "CONCEPT_K3", "CONCEPT_K4"]
    step1_payload = _build_step1_payload(concepts, source_id=source_id)

    def mock_gen(concept, source_id, provided_chunks=None, max_retries=None):
        return _make_valid_question(concept.concept_id, concept.name, source_id)

    with patch("app.api.assessment.generate_question", side_effect=mock_gen):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 4,
                "step1_output": step1_payload,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        concept_ids = [q["concept_id"] for q in data["questions"]]
        assert len(concept_ids) == len(set(concept_ids)), f"Duplicate concepts detected in session: {concept_ids}"
        print(f"   [PASS] All {len(concept_ids)} accepted questions have strictly unique concepts: {concept_ids}")


def test_question_backfill_excludes_kill_switch():
    """D. Profile contains REQUIRES_HUMAN_FALLBACK concept.
    Ensure it is never selected as a reserve candidate or primary candidate.
    """
    print("\n--- Running Test D: test_question_backfill_excludes_kill_switch ---")
    source_id = "SRC_BACKFILL_D"
    student_id = "STU_BACKFILL_D"
    concepts = ["CONCEPT_SAFE_1", "CONCEPT_FAILING", "CONCEPT_KILL_SWITCH", "CONCEPT_SAFE_2", "CONCEPT_SAFE_3"]
    step1_payload = _build_step1_payload(concepts, source_id=source_id)

    # Pre-seed profile with CONCEPT_KILL_SWITCH as REQUIRES_HUMAN_FALLBACK
    profile = get_or_create_profile(student_id, source_id)
    profile.concept_masteries["CONCEPT_KILL_SWITCH"] = ConceptMastery(
        concept_id="CONCEPT_KILL_SWITCH",
        concept_name="Kill Switch Concept",
        status="REQUIRES_HUMAN_FALLBACK",
        iteration_count=4,
    )
    save_profile(profile)

    def mock_generate(concept, source_id, provided_chunks, max_retries):
        # Force CONCEPT_FAILING to fail so backfill is triggered
        if concept.concept_id == "CONCEPT_FAILING":
            return None
        return _make_valid_question(concept.concept_id, concept.name, source_id)

    with patch("app.api.assessment.generate_question", side_effect=mock_generate):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 3,
                "step1_output": step1_payload,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        tested_concept_ids = [q["concept_id"] for q in data["questions"]]

        assert "CONCEPT_KILL_SWITCH" not in tested_concept_ids, "Kill-switch concept MUST NOT be in accepted questions"
        assert "CONCEPT_KILL_SWITCH" not in data.get("failed_concepts", []), "Kill switch concept should not even be evaluated as candidate"
        assert len(tested_concept_ids) == 3, f"Expected 3 questions, got {len(tested_concept_ids)}"
        print(f"   [PASS] Kill-switch concept strictly excluded! Tested: {tested_concept_ids}")


def test_question_backfill_exhaustion():
    """E. Request 10 questions but only 3 valid candidates exist.
    Ensure exactly 3 valid questions are returned, shortfall is reported,
    and no fake/invalid questions are inserted.
    """
    print("\n--- Running Test E: test_question_backfill_exhaustion ---")
    source_id = "SRC_BACKFILL_E"
    student_id = "STU_BACKFILL_E"
    concepts = ["CONCEPT_X", "CONCEPT_Y", "CONCEPT_Z"]
    step1_payload = _build_step1_payload(concepts, source_id=source_id)

    def mock_gen(concept, source_id, provided_chunks=None, max_retries=None):
        return _make_valid_question(concept.concept_id, concept.name, source_id)

    with patch("app.api.assessment.generate_question", side_effect=mock_gen):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 10,
                "step1_output": step1_payload,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_count"] == 3, f"Expected 3 questions, got {data['question_count']}"
        assert data["requested_questions"] == 10
        assert data["generated_questions"] == 3
        assert data["shortfall"] == 7

        # Verify all 3 questions are real valid questions for the 3 concepts
        concept_ids = [q["concept_id"] for q in data["questions"]]
        assert set(concept_ids) == {"CONCEPT_X", "CONCEPT_Y", "CONCEPT_Z"}
        print(f"   [PASS] Candidate exhaustion handled accurately: requested=10, generated=3, shortfall=7")


if __name__ == "__main__":
    print("=================================================================")
    print("  TESTING STEP 2 HARDENING: ROBUST QUESTION BACKFILLING (PHASE 2A)")
    print("=================================================================")
    test_question_backfill_after_validation_failure()
    test_question_backfill_after_duplicate()
    test_question_backfill_does_not_repeat_concepts()
    test_question_backfill_excludes_kill_switch()
    test_question_backfill_exhaustion()
    print("\n=================================================================")
    print("   ALL PHASE 2A ROBUST QUESTION BACKFILLING TESTS PASSED!       ")
    print("=================================================================")
