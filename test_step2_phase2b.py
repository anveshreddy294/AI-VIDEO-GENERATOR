"""Phase 2B Step 2 Hardening: Self-Contained AssessmentSession Tests.

Verifies:
A. test_session_contains_concept_dependency_snapshot
B. test_prerequisite_gap_detection_without_registry_kg
C. test_difficulty_preserved_without_registry_kg
D. test_session_snapshot_source_integrity
E. test_backward_compatibility_old_session
"""

import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

from app.main import app
from app.services.assessment.engine import grade_submission
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentOption,
    AssessmentSession,
    ConceptSnapshot,
    Question,
    StudentSubmission,
    reconstruct_kg_from_snapshot,
)
from app.services.assessment.session_store import load_session, save_session
from app.services.schemas import ConceptNode, KnowledgeGraph

client = TestClient(app)


def _make_valid_question(concept_id: str, concept_name: str, source_id: str, difficulty: str = "intermediate") -> Question:
    """Helper to create a valid Question for testing."""
    return Question(
        concept_id=concept_id,
        concept_name=concept_name,
        stem=f"Authoritative question for {concept_name}.",
        options=[
            AssessmentOption(index=0, text=f"Correct description of {concept_name}"),
            AssessmentOption(index=1, text=f"Distractor A for {concept_name}"),
            AssessmentOption(index=2, text=f"Distractor B for {concept_name}"),
            AssessmentOption(index=3, text=f"Distractor C for {concept_name}"),
        ],
        correct_index=0,
        explanation=f"Explanation for {concept_name}.",
        chunk_ids=["CHUNK_001"],
        content_ids=["CU_001"],
        page_start=1,
        page_end=2,
        source_id=source_id,
        difficulty=difficulty,
    )


def test_session_contains_concept_dependency_snapshot():
    """A. Test that start_assessment() stores a compact concept dependency snapshot inside AssessmentSession."""
    print("\n--- Running Test A: test_session_contains_concept_dependency_snapshot ---")
    source_id = "SRC_PHASE2B_A"
    student_id = "STU_PHASE2B_A"

    step1_payload = {
        "status": "READY",
        "source_id": source_id,
        "asset_id": "AST_TEST",
        "filename": "physics.pdf",
        "modality": "pdf",
        "knowledge_graph": {
            "concepts": {
                "CONCEPT_FORCE": {
                    "concept_id": "CONCEPT_FORCE",
                    "name": "Force",
                    "definition": "An interaction that changes motion.",
                    "prerequisite_concept_ids": [],
                    "source_content_ids": ["CU_001"],
                },
                "CONCEPT_ACCEL": {
                    "concept_id": "CONCEPT_ACCEL",
                    "name": "Acceleration",
                    "definition": "Rate of change of velocity.",
                    "prerequisite_concept_ids": ["CONCEPT_FORCE"],
                    "source_content_ids": ["CU_002"],
                },
            }
        },
        "chunks": [
            {
                "chunk_id": "CHUNK_001",
                "text": "Force and acceleration in classical mechanics.",
                "page_start": 1,
                "page_end": 2,
                "concept_ids": ["CONCEPT_FORCE", "CONCEPT_ACCEL"],
                "content_ids": ["CU_001", "CU_002"],
                "source_id": source_id,
            }
        ],
    }

    def mock_gen(concept, source_id, provided_chunks=None, max_retries=None):
        return _make_valid_question(concept.concept_id, concept.name, source_id)

    with patch("app.api.assessment.generate_question", side_effect=mock_gen):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 2,
                "step1_output": step1_payload,
            },
        )
        assert resp.status_code == 200, f"Start failed: {resp.text}"
        data = resp.json()
        session_id = data["session_id"]

        session = load_session(session_id)
        assert session is not None, "Session must exist in store"
        assert hasattr(session, "concept_snapshot"), "Session must have concept_snapshot attribute"
        assert len(session.concept_snapshot) >= 2, "Snapshot must contain concepts from KG"

        snap_force = session.concept_snapshot.get("CONCEPT_FORCE")
        assert snap_force is not None
        assert isinstance(snap_force, ConceptSnapshot)
        assert snap_force.concept_name == "Force"
        assert snap_force.difficulty == "foundational"
        assert snap_force.source_id == source_id

        snap_accel = session.concept_snapshot.get("CONCEPT_ACCEL")
        assert snap_accel is not None
        assert snap_accel.prerequisite_concept_ids == ["CONCEPT_FORCE"]
        assert snap_accel.difficulty == "intermediate"
        print("   [PASS] AssessmentSession contains complete and compact ConceptSnapshot!")


def test_prerequisite_gap_detection_without_registry_kg():
    """B. Verify prerequisite gap detection succeeds even when load_knowledge_graph() returns None."""
    print("\n--- Running Test B: test_prerequisite_gap_detection_without_registry_kg ---")
    source_id = "SRC_PHASE2B_B"
    student_id = "STU_PHASE2B_B"

    # Create session with questions for parent and child concepts
    q_parent = _make_valid_question("CONCEPT_MASS", "Mass", source_id)
    q_child = _make_valid_question("CONCEPT_WEIGHT", "Weight", source_id)

    session = AssessmentSession(
        student_id=student_id,
        source_id=source_id,
        status="READY",
        questions=[q_parent, q_child],
        concept_queue=["CONCEPT_MASS", "CONCEPT_WEIGHT"],
        concept_snapshot={
            "CONCEPT_MASS": ConceptSnapshot(
                concept_id="CONCEPT_MASS",
                concept_name="Mass",
                definition="Measure of inertia.",
                prerequisite_concept_ids=[],
                source_id=source_id,
                difficulty="foundational",
            ),
            "CONCEPT_WEIGHT": ConceptSnapshot(
                concept_id="CONCEPT_WEIGHT",
                concept_name="Weight",
                definition="Force of gravity on mass.",
                prerequisite_concept_ids=["CONCEPT_MASS"],
                source_id=source_id,
                difficulty="intermediate",
            ),
        },
    )
    save_session(session)

    # Student fails BOTH questions (selected_index=1, correct is 0)
    submission_payload = {
        "session_id": session.session_id,
        "answers": [
            {"question_id": q_parent.question_id, "selected_index": 1},
            {"question_id": q_child.question_id, "selected_index": 1},
        ],
    }

    # Simulate missing registry KnowledgeGraph
    with patch("app.api.assessment.load_knowledge_graph", return_value=None):
        resp = client.post("/assessment/submit", json=submission_payload)
        assert resp.status_code == 200, f"Submit failed: {resp.text}"
        data = resp.json()

        assert "prerequisite_gaps" in data
        assert len(data["prerequisite_gaps"]) > 0, "Prerequisite gap must be detected via session snapshot!"
        gap_text = data["prerequisite_gaps"][0]
        assert "Weight" in gap_text and "Mass" in gap_text
        print(f"   [PASS] Prerequisite gap detected without registry KG: {gap_text}")


def test_difficulty_preserved_without_registry_kg():
    """C. Verify video target duration (30/45/60s) strictly preserved without registry KG."""
    print("\n--- Running Test C: test_difficulty_preserved_without_registry_kg ---")
    source_id = "SRC_PHASE2B_C"
    student_id = f"STU_PHASE2B_C_{uuid4().hex[:6]}"

    q_f = _make_valid_question("CONCEPT_F", "Foundational Concept", source_id, difficulty="foundational")
    q_i = _make_valid_question("CONCEPT_I", "Intermediate Concept", source_id, difficulty="intermediate")
    q_a = _make_valid_question("CONCEPT_A", "Advanced Concept", source_id, difficulty="advanced")

    session = AssessmentSession(
        student_id=student_id,
        source_id=source_id,
        status="READY",
        questions=[q_f, q_i, q_a],
        concept_queue=["CONCEPT_F", "CONCEPT_I", "CONCEPT_A"],
        concept_snapshot={
            "CONCEPT_F": ConceptSnapshot(
                concept_id="CONCEPT_F",
                concept_name="Foundational Concept",
                definition="Zero prerequisites",
                prerequisite_concept_ids=[],
                difficulty="foundational",
                source_id=source_id,
            ),
            "CONCEPT_I": ConceptSnapshot(
                concept_id="CONCEPT_I",
                concept_name="Intermediate Concept",
                definition="One prerequisite",
                prerequisite_concept_ids=["CONCEPT_F"],
                difficulty="intermediate",
                source_id=source_id,
            ),
            "CONCEPT_A": ConceptSnapshot(
                concept_id="CONCEPT_A",
                concept_name="Advanced Concept",
                definition="Three prerequisites",
                prerequisite_concept_ids=["CONCEPT_F", "CONCEPT_I", "CONCEPT_EXTRA"],
                difficulty="advanced",
                source_id=source_id,
            ),
        },
    )
    save_session(session)

    # Student fails all 3 questions so all 3 require remedial videos
    submission_payload = {
        "session_id": session.session_id,
        "answers": [
            {"question_id": q_f.question_id, "selected_index": 2},
            {"question_id": q_i.question_id, "selected_index": 2},
            {"question_id": q_a.question_id, "selected_index": 2},
        ],
    }

    with patch("app.api.assessment.load_knowledge_graph", return_value=None):
        resp = client.post("/assessment/submit", json=submission_payload)
        assert resp.status_code == 200
        data = resp.json()

        matrix = data["video_target_matrix"]
        videos = matrix["videos"]
        assert len(videos) == 3, f"Expected 3 video targets, got {len(videos)}"

        video_map = {v["concept_id"]: v for v in videos}
        assert video_map["CONCEPT_F"]["target_seconds"] == 30, "Foundational video must be 30s"
        assert video_map["CONCEPT_I"]["target_seconds"] == 45, "Intermediate video must be 45s"
        assert video_map["CONCEPT_A"]["target_seconds"] == 60, "Advanced video must be 60s"
        print("   [PASS] Durations 30s/45s/60s preserved perfectly via session concept snapshot!")


def test_session_snapshot_source_integrity():
    """D. Ensure attempt to use snapshot for a different source is rejected."""
    print("\n--- Running Test D: test_session_snapshot_source_integrity ---")
    source_a = "SRC_AUTHENTIC_A"
    source_b = "SRC_ALIEN_B"

    session = AssessmentSession(
        student_id="STU_TEST",
        source_id=source_a,
        concept_snapshot={
            "CONCEPT_1": ConceptSnapshot(
                concept_id="CONCEPT_1",
                concept_name="C1",
                source_id=source_a,
            )
        },
    )

    # 1. Direct reconstruct call with mismatched expected_source_id
    try:
        reconstruct_kg_from_snapshot(session, expected_source_id=source_b)
        assert False, "Should have raised ValueError on source_id mismatch"
    except ValueError as exc:
        assert "mismatch" in str(exc)
        print(f"   [PASS] Direct reconstruction mismatch caught: {exc}")

    # 2. Tampered concept snapshot belonging to another source
    tampered_session = AssessmentSession(
        student_id="STU_TEST",
        source_id=source_a,
        status="READY",
        questions=[_make_valid_question("CONCEPT_TAMPERED", "Tampered", source_a)],
        concept_snapshot={
            "CONCEPT_TAMPERED": ConceptSnapshot(
                concept_id="CONCEPT_TAMPERED",
                concept_name="Tampered",
                source_id=source_b,  # Alien source!
            )
        },
    )
    save_session(tampered_session)

    submission_payload = {
        "session_id": tampered_session.session_id,
        "answers": [{"question_id": tampered_session.questions[0].question_id, "selected_index": 0}],
    }

    with patch("app.api.assessment.load_knowledge_graph", return_value=None):
        resp = client.post("/assessment/submit", json=submission_payload)
        assert resp.status_code == 400, f"Expected 400 for cross-source integrity violation, got: {resp.status_code}"
        assert "Cross-source integrity violation" in resp.json()["detail"]
        print(f"   [PASS] API submit correctly rejected cross-source snapshot tampering with 400!")


def test_backward_compatibility_old_session():
    """E. Verify old session without concept_snapshot field deserializes safely and submits without crashing."""
    print("\n--- Running Test E: test_backward_compatibility_old_session ---")
    source_id = "SRC_LEGACY_01"
    student_id = "STU_LEGACY_01"

    old_session_data = {
        "session_id": "SESS_LEGACY_12345678",
        "student_id": student_id,
        "source_id": source_id,
        "questions": [
            _make_valid_question("CONCEPT_LEGACY", "Legacy Concept", source_id).model_dump()
        ],
        "status": "READY",
        "concept_queue": ["CONCEPT_LEGACY"],
        # Notice: NO "concept_snapshot" key here
    }

    # Deserialization test
    session = AssessmentSession.model_validate(old_session_data)
    assert hasattr(session, "concept_snapshot")
    assert session.concept_snapshot == {}, "Default should be empty dict for legacy sessions"
    save_session(session)

    submission_payload = {
        "session_id": session.session_id,
        "answers": [{"question_id": session.questions[0].question_id, "selected_index": 0}],
    }

    # Submit without disk KG -> should use legacy minimal fallback without crashing
    with patch("app.api.assessment.load_knowledge_graph", return_value=None):
        resp = client.post("/assessment/submit", json=submission_payload)
        assert resp.status_code == 200, f"Legacy submission failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "SUBMITTED"
        print("   [PASS] Legacy session without concept_snapshot deserialized and processed safely!")


if __name__ == "__main__":
    print("=================================================================")
    print("  TESTING STEP 2 HARDENING: SELF-CONTAINED SESSIONS (PHASE 2B)   ")
    print("=================================================================")
    test_session_contains_concept_dependency_snapshot()
    test_prerequisite_gap_detection_without_registry_kg()
    test_difficulty_preserved_without_registry_kg()
    test_session_snapshot_source_integrity()
    test_backward_compatibility_old_session()
    print("\n=================================================================")
    print("   ALL PHASE 2B SELF-CONTAINED SESSION TESTS PASSED!             ")
    print("=================================================================")
