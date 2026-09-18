"""Test suite for Step 2 Assessment Result Contract and Dashboard Scoring.

Verifies:
A. 3 questions: 3 correct -> 100.0%
B. 3 questions: 2 correct -> 66.7%
C. 3 questions: 1 correct -> 33.3%
D. 3 questions: 0 correct -> 0.0%
E. Unanswered question handled according to grading contract (selected_index=-1, marked incorrect).
F. Frontend-visible result fields correspond exactly to backend response schema (AssessmentSubmitResponse).
G. Multi-session independence: profile_summary.overall_score is distinct from current assessment percentage.
"""

import sys
from pathlib import Path
from uuid import uuid4

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app
from app.services.assessment.schemas import (
    AssessmentOption,
    AssessmentSession,
    AssessmentSubmitResponse,
    ConceptSnapshot,
    Question,
)
from app.services.assessment.session_store import save_session

client = TestClient(app)


def _create_test_session(session_id: str, student_id: str, source_id: str) -> AssessmentSession:
    """Create a test session with exactly 3 questions for 3 distinct concepts."""
    q1 = Question(
        question_id=f"Q1_{session_id}",
        concept_id="CONCEPT_FORCE",
        concept_name="Force",
        stem="What is force in classical mechanics?",
        options=[
            AssessmentOption(index=0, text="An interaction that changes motion"),
            AssessmentOption(index=1, text="A scalar quantity with no direction"),
            AssessmentOption(index=2, text="Energy stored in a vacuum"),
            AssessmentOption(index=3, text="Resistance to acceleration"),
        ],
        correct_index=0,
        explanation="Force is an interaction that changes motion.",
        chunk_ids=["CHUNK_001"],
        content_ids=["CU_001"],
        page_start=1,
        page_end=1,
        source_id=source_id,
        difficulty="foundational",
    )
    q2 = Question(
        question_id=f"Q2_{session_id}",
        concept_id="CONCEPT_MASS",
        concept_name="Mass",
        stem="What is mass a measure of?",
        options=[
            AssessmentOption(index=0, text="Gravitational force exclusively"),
            AssessmentOption(index=1, text="Inertia of an object"),
            AssessmentOption(index=2, text="Volume occupied by an object"),
            AssessmentOption(index=3, text="Velocity rate of change"),
        ],
        correct_index=1,
        explanation="Mass is a measure of an object's inertia.",
        chunk_ids=["CHUNK_002"],
        content_ids=["CU_002"],
        page_start=2,
        page_end=2,
        source_id=source_id,
        difficulty="foundational",
    )
    q3 = Question(
        question_id=f"Q3_{session_id}",
        concept_id="CONCEPT_ACCEL",
        concept_name="Acceleration",
        stem="What is acceleration defined as?",
        options=[
            AssessmentOption(index=0, text="Rate of change of position"),
            AssessmentOption(index=1, text="Total distance divided by time"),
            AssessmentOption(index=2, text="Rate of change of velocity"),
            AssessmentOption(index=3, text="Force multiplied by mass"),
        ],
        correct_index=2,
        explanation="Acceleration is the rate of change of velocity.",
        chunk_ids=["CHUNK_003"],
        content_ids=["CU_003"],
        page_start=3,
        page_end=3,
        source_id=source_id,
        difficulty="intermediate",
    )

    snapshot = {
        "CONCEPT_FORCE": ConceptSnapshot(
            concept_id="CONCEPT_FORCE",
            concept_name="Force",
            definition="An interaction that changes motion.",
            difficulty="foundational",
            source_id=source_id,
        ),
        "CONCEPT_MASS": ConceptSnapshot(
            concept_id="CONCEPT_MASS",
            concept_name="Mass",
            definition="Inertia of an object.",
            difficulty="foundational",
            source_id=source_id,
        ),
        "CONCEPT_ACCEL": ConceptSnapshot(
            concept_id="CONCEPT_ACCEL",
            concept_name="Acceleration",
            definition="Rate of change of velocity.",
            prerequisite_concept_ids=["CONCEPT_FORCE", "CONCEPT_MASS"],
            difficulty="intermediate",
            source_id=source_id,
        ),
    }

    session = AssessmentSession(
        session_id=session_id,
        student_id=student_id,
        source_id=source_id,
        status="READY",
        questions=[q1, q2, q3],
        concept_queue=["CONCEPT_FORCE", "CONCEPT_MASS", "CONCEPT_ACCEL"],
        concept_snapshot=snapshot,
    )
    save_session(session)
    return session


def cleanup_fixtures(session_ids: list[str], student_ids: list[str], source_id: str):
    """Clean up disk files created during tests."""
    for sess_id in session_ids:
        (Path("storage/assessment_sessions") / f"{sess_id}.json").unlink(missing_ok=True)
    for stu_id in student_ids:
        (Path("storage/learning_profiles") / f"{stu_id}_{source_id}.json").unlink(missing_ok=True)
        (Path("storage/video_targets") / f"{stu_id}_{source_id}.json").unlink(missing_ok=True)


def run_tests():
    print("=================================================================")
    print("   TESTING STEP 2 ASSESSMENT SCORING & DASHBOARD CONTRACT        ")
    print("=================================================================")

    source_id = "SRC_CONTRACT_TEST"
    created_sessions = []
    created_students = []

    try:
        # -------------------------------------------------------------
        # Test A: 3 questions, 3 correct -> 100.0%
        # -------------------------------------------------------------
        print("\n--- Test A: 3 questions: 3 correct -> 100.0% ---")
        sess_a_id = f"SESS_CONTRACT_A_{uuid4().hex[:6]}"
        stu_a_id = f"STU_CONTRACT_A_{uuid4().hex[:6]}"
        created_sessions.append(sess_a_id)
        created_students.append(stu_a_id)
        session_a = _create_test_session(sess_a_id, stu_a_id, source_id)

        payload_a = {
            "session_id": sess_a_id,
            "answers": [
                {"question_id": session_a.questions[0].question_id, "selected_index": 0},  # correct
                {"question_id": session_a.questions[1].question_id, "selected_index": 1},  # correct
                {"question_id": session_a.questions[2].question_id, "selected_index": 2},  # correct
            ],
        }
        resp_a = client.post("/assessment/submit", json=payload_a)
        assert resp_a.status_code == 200, f"Submit A failed: {resp_a.text}"
        data_a = resp_a.json()

        assert data_a["score"] == 3, f"Expected score=3, got {data_a['score']}"
        assert data_a["total"] == 3, f"Expected total=3, got {data_a['total']}"
        assert data_a["percentage"] == 100.0, f"Expected percentage=100.0, got {data_a['percentage']}"
        print(f"   [PASS] 3/3 correct: score={data_a['score']}/{data_a['total']}, percentage={data_a['percentage']}%")

        # -------------------------------------------------------------
        # Test B: 3 questions: 2 correct -> 66.7%
        # -------------------------------------------------------------
        print("\n--- Test B: 3 questions: 2 correct -> 66.7% ---")
        sess_b_id = f"SESS_CONTRACT_B_{uuid4().hex[:6]}"
        stu_b_id = f"STU_CONTRACT_B_{uuid4().hex[:6]}"
        created_sessions.append(sess_b_id)
        created_students.append(stu_b_id)
        session_b = _create_test_session(sess_b_id, stu_b_id, source_id)

        payload_b = {
            "session_id": sess_b_id,
            "answers": [
                {"question_id": session_b.questions[0].question_id, "selected_index": 0},  # correct
                {"question_id": session_b.questions[1].question_id, "selected_index": 1},  # correct
                {"question_id": session_b.questions[2].question_id, "selected_index": 0},  # wrong (correct is 2)
            ],
        }
        resp_b = client.post("/assessment/submit", json=payload_b)
        assert resp_b.status_code == 200, f"Submit B failed: {resp_b.text}"
        data_b = resp_b.json()

        assert data_b["score"] == 2, f"Expected score=2, got {data_b['score']}"
        assert data_b["total"] == 3, f"Expected total=3, got {data_b['total']}"
        assert data_b["percentage"] == 66.7, f"Expected percentage=66.7, got {data_b['percentage']}"
        print(f"   [PASS] 2/3 correct: score={data_b['score']}/{data_b['total']}, percentage={data_b['percentage']}%")

        # -------------------------------------------------------------
        # Test C: 3 questions: 1 correct -> 33.3%
        # -------------------------------------------------------------
        print("\n--- Test C: 3 questions: 1 correct -> 33.3% ---")
        sess_c_id = f"SESS_CONTRACT_C_{uuid4().hex[:6]}"
        stu_c_id = f"STU_CONTRACT_C_{uuid4().hex[:6]}"
        created_sessions.append(sess_c_id)
        created_students.append(stu_c_id)
        session_c = _create_test_session(sess_c_id, stu_c_id, source_id)

        payload_c = {
            "session_id": sess_c_id,
            "answers": [
                {"question_id": session_c.questions[0].question_id, "selected_index": 0},  # correct
                {"question_id": session_c.questions[1].question_id, "selected_index": 0},  # wrong (correct is 1)
                {"question_id": session_c.questions[2].question_id, "selected_index": 0},  # wrong (correct is 2)
            ],
        }
        resp_c = client.post("/assessment/submit", json=payload_c)
        assert resp_c.status_code == 200, f"Submit C failed: {resp_c.text}"
        data_c = resp_c.json()

        assert data_c["score"] == 1, f"Expected score=1, got {data_c['score']}"
        assert data_c["total"] == 3, f"Expected total=3, got {data_c['total']}"
        assert data_c["percentage"] == 33.3, f"Expected percentage=33.3, got {data_c['percentage']}"
        print(f"   [PASS] 1/3 correct: score={data_c['score']}/{data_c['total']}, percentage={data_c['percentage']}%")

        # -------------------------------------------------------------
        # Test D: 3 questions: 0 correct -> 0.0%
        # -------------------------------------------------------------
        print("\n--- Test D: 3 questions: 0 correct -> 0.0% ---")
        sess_d_id = f"SESS_CONTRACT_D_{uuid4().hex[:6]}"
        stu_d_id = f"STU_CONTRACT_D_{uuid4().hex[:6]}"
        created_sessions.append(sess_d_id)
        created_students.append(stu_d_id)
        session_d = _create_test_session(sess_d_id, stu_d_id, source_id)

        payload_d = {
            "session_id": sess_d_id,
            "answers": [
                {"question_id": session_d.questions[0].question_id, "selected_index": 3},  # wrong (correct is 0)
                {"question_id": session_d.questions[1].question_id, "selected_index": 3},  # wrong (correct is 1)
                {"question_id": session_d.questions[2].question_id, "selected_index": 3},  # wrong (correct is 2)
            ],
        }
        resp_d = client.post("/assessment/submit", json=payload_d)
        assert resp_d.status_code == 200, f"Submit D failed: {resp_d.text}"
        data_d = resp_d.json()

        assert data_d["score"] == 0, f"Expected score=0, got {data_d['score']}"
        assert data_d["total"] == 3, f"Expected total=3, got {data_d['total']}"
        assert data_d["percentage"] == 0.0, f"Expected percentage=0.0, got {data_d['percentage']}"
        print(f"   [PASS] 0/3 correct: score={data_d['score']}/{data_d['total']}, percentage={data_d['percentage']}%")

        # -------------------------------------------------------------
        # Test E: Unanswered question handled according to grading contract
        # -------------------------------------------------------------
        print("\n--- Test E: Unanswered question handled according to grading contract ---")
        sess_e_id = f"SESS_CONTRACT_E_{uuid4().hex[:6]}"
        stu_e_id = f"STU_CONTRACT_E_{uuid4().hex[:6]}"
        created_sessions.append(sess_e_id)
        created_students.append(stu_e_id)
        session_e = _create_test_session(sess_e_id, stu_e_id, source_id)

        # Question 1 is answered correctly; Question 2 is wrong; Question 3 is omitted entirely (unanswered)
        payload_e = {
            "session_id": sess_e_id,
            "answers": [
                {"question_id": session_e.questions[0].question_id, "selected_index": 0},  # correct
                {"question_id": session_e.questions[1].question_id, "selected_index": 0},  # wrong
                # Q3 omitted
            ],
        }
        resp_e = client.post("/assessment/submit", json=payload_e)
        assert resp_e.status_code == 200, f"Submit E failed: {resp_e.text}"
        data_e = resp_e.json()

        assert data_e["score"] == 1, f"Expected score=1, got {data_e['score']}"
        assert data_e["total"] == 3, f"Expected total=3, got {data_e['total']}"
        assert data_e["percentage"] == 33.3, f"Expected percentage=33.3, got {data_e['percentage']}"

        # Check results array for Q3
        q3_result = [r for r in data_e["results"] if r["question_id"] == session_e.questions[2].question_id][0]
        assert q3_result["selected_index"] == -1, f"Expected selected_index=-1 for unanswered question, got {q3_result['selected_index']}"
        assert q3_result["correct"] is False, "Unanswered question must be graded incorrect"
        print("   [PASS] Unanswered question correctly scored as incorrect with selected_index=-1.")

        # -------------------------------------------------------------
        # Test F: Frontend-visible result fields correspond exactly to backend schema
        # -------------------------------------------------------------
        print("\n--- Test F: Frontend-visible result fields correspond exactly to backend schema ---")
        # Validate data_b against Pydantic model
        validated_response = AssessmentSubmitResponse.model_validate(data_b)
        assert validated_response.status == "SUBMITTED"
        assert validated_response.score == 2
        assert validated_response.total == 3
        assert validated_response.percentage == 66.7

        # Required fields in backend response consumed by dashboard displayResults
        assert "percentage" in data_b, "Field 'percentage' required for Assessment Score display"
        assert "score" in data_b, "Field 'score' required for fraction display"
        assert "total" in data_b, "Field 'total' required for fraction display"
        assert "profile_summary" in data_b, "Field 'profile_summary' required for profile metrics"
        assert "overall_score" in data_b["profile_summary"], "profile_summary.overall_score required"
        assert "strong_concepts" in data_b["profile_summary"], "profile_summary.strong_concepts required"
        assert "weak_concepts" in data_b["profile_summary"], "profile_summary.weak_concepts required"
        assert "prerequisite_gaps" in data_b, "Field 'prerequisite_gaps' required"
        assert "video_target_matrix" in data_b, "Field 'video_target_matrix' required"

        print("   [PASS] Response matches AssessmentSubmitResponse schema and all frontend-visible fields.")

        # -------------------------------------------------------------
        # Test G: Multi-session profile overall_score independence from percentage
        # -------------------------------------------------------------
        print("\n--- Test G: Multi-session profile overall_score independence from percentage ---")
        stu_g_id = f"STU_CONTRACT_G_{uuid4().hex[:6]}"
        created_students.append(stu_g_id)

        # Session 1: Student gets 3/3 (100.0%)
        sess_g1_id = f"SESS_CONTRACT_G1_{uuid4().hex[:6]}"
        created_sessions.append(sess_g1_id)
        session_g1 = _create_test_session(sess_g1_id, stu_g_id, source_id)
        resp_g1 = client.post("/assessment/submit", json={
            "session_id": sess_g1_id,
            "answers": [
                {"question_id": session_g1.questions[0].question_id, "selected_index": 0},
                {"question_id": session_g1.questions[1].question_id, "selected_index": 1},
                {"question_id": session_g1.questions[2].question_id, "selected_index": 2},
            ],
        })
        data_g1 = resp_g1.json()
        assert data_g1["percentage"] == 100.0
        assert data_g1["profile_summary"]["overall_score"] == 100.0

        # Session 2: Same student takes a second assessment and gets 1/3 (33.3%)
        sess_g2_id = f"SESS_CONTRACT_G2_{uuid4().hex[:6]}"
        created_sessions.append(sess_g2_id)
        session_g2 = _create_test_session(sess_g2_id, stu_g_id, source_id)
        resp_g2 = client.post("/assessment/submit", json={
            "session_id": sess_g2_id,
            "answers": [
                {"question_id": session_g2.questions[0].question_id, "selected_index": 0},  # correct
                {"question_id": session_g2.questions[1].question_id, "selected_index": 0},  # wrong
                {"question_id": session_g2.questions[2].question_id, "selected_index": 0},  # wrong
            ],
        })
        data_g2 = resp_g2.json()

        # THIS submission percentage is 33.3%
        assert data_g2["percentage"] == 33.3, f"Expected submission percentage=33.3, got {data_g2['percentage']}"
        # Historical profile overall_score is (100.0 + 33.333...) / 2 = 66.7%
        assert data_g2["profile_summary"]["overall_score"] == 66.7, f"Expected historical overall_score=66.7, got {data_g2['profile_summary']['overall_score']}"

        # Crucial verification: percentage != overall_score
        assert data_g2["percentage"] != data_g2["profile_summary"]["overall_score"], (
            f"Conflation detected: submission percentage ({data_g2['percentage']}) and "
            f"profile overall_score ({data_g2['profile_summary']['overall_score']}) must be distinct!"
        )
        print(f"   [PASS] Independence Verified: Submission Score = {data_g2['percentage']}%, "
              f"Historical Profile Score = {data_g2['profile_summary']['overall_score']}%.")

        print("\n=================================================================")
        print("   ALL STEP 2 SCORING CONTRACT TESTS PASSED PERFECTLY!          ")
        print("=================================================================")

    finally:
        cleanup_fixtures(created_sessions, created_students, source_id)


if __name__ == "__main__":
    run_tests()
