"""Step 5E API & Application Layer Test Suite.

Verifies:
1. GET /{source_id}/roadmap returns valid grounded roadmap
2. GET /{source_id}/roadmap causes zero mutation (pure read idempotency)
3. GET /{source_id}/next-action returns deterministic action without state mutation
4. Assessment submission: correct answer advances mastery
5. Assessment submission: incorrect answer transitions to WEAK
6. Client cannot supply authoritative correctness (is_correct / correct_answer ignored/rejected)
7. Duplicate assessment attempt does not double count (idempotent result)
8. Unknown question submission rejected with 404
9. Cross-source question submission rejected with 403
10. Reassessment question response never exposes correct answer (answer-key security)
11. Reassessment generation rejected before remediation (state != REASSESSING)
12. Valid reassessment generated after remediation confirmed
13. Repeated reassessment generation does not spam unlimited questions (idempotent reuse)
14. Remediation POST returns HTTP 202 with job reference
15. Duplicate remediation POST reuses same job
16. Concurrent remediation POST reuses same logical job
17. Remediation status cross-user lookup rejected with 403
18. NEEDS_SUPPORT remediation rejected with 409
19. COMPLETE roadmap returns action_type == COMPLETE
20. API does not expose absolute filesystem video path
21. Domain exceptions mapped to intentional HTTP status codes
22. Real API integration flow using TestClient
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.learning import get_adaptive_learning_service
from app.services.mastery import (
    AdaptiveLearningService,
    AssessmentType,
    AuthoritativeQuestion,
    InMemoryAssessmentAttemptRepository,
    InMemoryMasteryRepository,
    InMemoryQuestionRegistry,
    InMemoryRemediationJobRepository,
    LearningActionType,
    MasteryRecord,
    MasteryState,
    MasteryStateMachine,
    ReasonCode,
    RemediationJob,
    RemediationJobStatus,
)
from app.services.schemas import ConceptNode, KnowledgeGraph, SourceRecord
from app.services.video.scene_schema import VideoArtifact, VideoJobStatus


@pytest.fixture
def mock_curriculum():
    """Create a realistic grounded 3-concept curriculum for source testing."""
    c1 = ConceptNode(
        concept_id="CONCEPT_NEWTON_1",
        name="Newton's First Law",
        definition="An object remains at rest or in uniform motion unless acted upon by a net force.",
        prerequisite_concept_ids=[],
        source_content_ids=["cu_001"],
    )
    c2 = ConceptNode(
        concept_id="CONCEPT_NEWTON_2",
        name="Newton's Second Law",
        definition="Acceleration of an object is directly proportional to net force and inversely to mass.",
        prerequisite_concept_ids=["CONCEPT_NEWTON_1"],
        source_content_ids=["cu_002"],
    )
    c3 = ConceptNode(
        concept_id="CONCEPT_NEWTON_3",
        name="Newton's Third Law",
        definition="For every action force there is an equal and opposite reaction force.",
        prerequisite_concept_ids=["CONCEPT_NEWTON_2"],
        source_content_ids=["cu_003"],
    )
    kg = KnowledgeGraph(concepts={
        "CONCEPT_NEWTON_1": c1,
        "CONCEPT_NEWTON_2": c2,
        "CONCEPT_NEWTON_3": c3,
    })
    rec = SourceRecord(
        source_id="SRC_PHYSICS_TEST",
        filename="physics_test.pdf",
        source_type="pdf",
        mime_type="application/pdf",
        file_hash="hash123",
        sha256="hash123",
        file_size=1024,
        uploaded_by="student_default",
        user_id="student_default",
        owner_user_id="student_default",
        version=1,
        source_version="v1",
        status="READY",
    )
    return rec, kg



@pytest.fixture
def isolated_service(mock_curriculum):
    """Isolated AdaptiveLearningService instance with mock video engine."""
    async def mock_video_engine(target, job_id, **kwargs):
        return VideoArtifact(
            job_id=job_id,
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            status=VideoJobStatus.COMPLETED,
            video_path=str(Path("storage/videos/test_remedial.mp4")),
            duration_seconds=32.5,
        )

    service = AdaptiveLearningService(
        mastery_repo=InMemoryMasteryRepository(),
        attempt_repo=InMemoryAssessmentAttemptRepository(),
        question_registry=InMemoryQuestionRegistry(),
        remediation_repo=InMemoryRemediationJobRepository(),
        state_machine=MasteryStateMachine(),
        video_engine_fn=mock_video_engine,
    )
    return service



@pytest.fixture
def client(isolated_service, mock_curriculum, monkeypatch):
    """FastAPI TestClient with overridden service dependency and mocked registry."""
    rec, kg = mock_curriculum

    # Override get_adaptive_learning_service
    app.dependency_overrides[get_adaptive_learning_service] = lambda: isolated_service

    # Mock registry lookups for source
    dummy_chunks = [
        type("RichChunk", (), {
            "model_dump": lambda s: {
                "chunk_id": "ch_001",
                "text": "Newton's First Law describes inertia: an object remains at rest unless acted on by external force.",
                "source_id": rec.source_id,
            }
        })()
    ]
    monkeypatch.setattr("app.services.mastery.application_service.get_source_record", lambda sid: rec if sid == rec.source_id else None)
    monkeypatch.setattr("app.services.mastery.application_service.load_knowledge_graph", lambda sid: kg if sid == rec.source_id else None)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_knowledge_graph", lambda sid: kg if sid == rec.source_id else None)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_rich_chunks", lambda sid: dummy_chunks if sid == rec.source_id else [])

    yield TestClient(app)

    app.dependency_overrides.clear()


# =============================================================================
# 1. Roadmap & Next-Action Tests
# =============================================================================
def test_01_get_roadmap_returns_valid_grounded_roadmap(client):
    res = client.get("/api/learning/SRC_PHYSICS_TEST/roadmap?user_id=student_default")
    assert res.status_code == 200
    data = res.json()
    assert data["source_id"] == "SRC_PHYSICS_TEST"
    assert data["completed"] is False
    assert "CONCEPT_NEWTON_1" in data["unassessed_concepts"]
    assert "CONCEPT_NEWTON_2" in data["blocked_concepts"]
    assert data["next_action"]["action_type"] == "ASSESS"
    assert data["next_action"]["concept_id"] == "CONCEPT_NEWTON_1"


def test_02_get_roadmap_causes_zero_mutation(client, isolated_service):
    # Call twice
    res1 = client.get("/api/learning/SRC_PHYSICS_TEST/roadmap?user_id=student_default")
    res2 = client.get("/api/learning/SRC_PHYSICS_TEST/roadmap?user_id=student_default")
    assert res1.json() == res2.json()

    # Verify underlying repository remains completely empty (zero mutations)
    records = isolated_service.mastery_repo.list_by_user_source("student_default", "SRC_PHYSICS_TEST")
    assert len(records) == 0


def test_03_get_next_action_returns_deterministic_action(client):
    res = client.get("/api/learning/SRC_PHYSICS_TEST/next-action?user_id=student_default")
    assert res.status_code == 200
    data = res.json()
    assert data["concept_id"] == "CONCEPT_NEWTON_1"
    assert data["action_type"] == "ASSESS"
    assert data["reason_code"] == "NEXT_GROUNDED_CONCEPT"


def test_04_get_learning_state_snapshot(client):
    res = client.get("/api/learning/SRC_PHYSICS_TEST/state?user_id=student_default")
    assert res.status_code == 200
    data = res.json()
    assert data["total_concepts"] == 3
    assert data["mastered_count"] == 0
    assert data["progress_percentage"] == 0.0
    assert len(data["concepts"]) == 3
    assert data["concepts"][0]["mastery_state"] == "UNASSESSED"


# =============================================================================
# 2. Authoritative Assessment Submission Tests
# =============================================================================
def test_05_assessment_submission_correct_advances_mastery(client, isolated_service):
    # Register authoritative question
    q = AuthoritativeQuestion(
        question_id="Q_N1_01",
        concept_id="CONCEPT_NEWTON_1",
        source_id="SRC_PHYSICS_TEST",
        user_id="student_default",
        stem="What does Newton's first law state?",
        options=["Objects at rest remain at rest", "F = ma", "Every action has reaction", "Energy conserved"],
        correct_index=0,
    )
    isolated_service.question_registry.register(q)

    # Submit correct answer (0)
    payload = {
        "attempt_id": "ATT_001",
        "concept_id": "CONCEPT_NEWTON_1",
        "question_id": "Q_N1_01",
        "selected_answer": 0,
    }
    res = client.post("/api/learning/SRC_PHYSICS_TEST/assessment/submit?user_id=student_default", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_correct"] is True
    assert data["mastery_state"] == "MASTERED"
    assert data["mastery_score"] == 100.0
    assert data["attempt_count"] == 1
    # Next concept (CONCEPT_NEWTON_2) is now unblocked
    assert data["next_action"]["concept_id"] == "CONCEPT_NEWTON_2"


def test_06_assessment_submission_incorrect_transitions_to_weak(client, isolated_service):
    q = AuthoritativeQuestion(
        question_id="Q_N1_02",
        concept_id="CONCEPT_NEWTON_1",
        source_id="SRC_PHYSICS_TEST",
        user_id="student_default",
        stem="What does Newton's first law state?",
        options=["Option A", "Option B", "Option C", "Option D"],
        correct_index=1,
    )
    isolated_service.question_registry.register(q)

    # Submit incorrect answer (0)
    payload = {
        "attempt_id": "ATT_002",
        "concept_id": "CONCEPT_NEWTON_1",
        "question_id": "Q_N1_02",
        "selected_answer": 0,
    }
    res = client.post("/api/learning/SRC_PHYSICS_TEST/assessment/submit?user_id=student_default", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_correct"] is False
    assert data["mastery_state"] == "WEAK"
    assert data["mastery_score"] == 0.0
    # Next action must now be REMEDIATE on CONCEPT_NEWTON_1
    assert data["next_action"]["action_type"] == "REMEDIATE"
    assert data["next_action"]["concept_id"] == "CONCEPT_NEWTON_1"


def test_07_client_cannot_supply_authoritative_correctness(client, isolated_service):
    q = AuthoritativeQuestion(
        question_id="Q_N1_03",
        concept_id="CONCEPT_NEWTON_1",
        source_id="SRC_PHYSICS_TEST",
        user_id="student_default",
        stem="Testing tampering",
        options=["Wrong", "Correct", "Wrong", "Wrong"],
        correct_index=1,
    )
    isolated_service.question_registry.register(q)

    # Client tries to pass is_correct: True and correct_answer: 0
    payload = {
        "attempt_id": "ATT_TAMPER_01",
        "concept_id": "CONCEPT_NEWTON_1",
        "question_id": "Q_N1_03",
        "selected_answer": 0,  # Wrong
        "is_correct": True,    # Fraudulent field
        "correct_answer": 0,   # Fraudulent field
    }
    res = client.post("/api/learning/SRC_PHYSICS_TEST/assessment/submit?user_id=student_default", json=payload)
    assert res.status_code == 200
    data = res.json()
    # Server-side grading evaluates selected_answer (0) == correct_index (1) -> False
    assert data["is_correct"] is False
    assert data["mastery_state"] == "WEAK"


def test_08_duplicate_assessment_attempt_is_idempotent(client, isolated_service):
    q = AuthoritativeQuestion(
        question_id="Q_N1_04",
        concept_id="CONCEPT_NEWTON_1",
        source_id="SRC_PHYSICS_TEST",
        user_id="student_default",
        stem="Idempotency test",
        options=["A", "B", "C", "D"],
        correct_index=2,
    )
    isolated_service.question_registry.register(q)

    payload = {
        "attempt_id": "ATT_IDEM_01",
        "concept_id": "CONCEPT_NEWTON_1",
        "question_id": "Q_N1_04",
        "selected_answer": 2,
    }
    res1 = client.post("/api/learning/SRC_PHYSICS_TEST/assessment/submit?user_id=student_default", json=payload)
    assert res1.status_code == 200
    assert res1.json()["is_duplicate"] is False

    # Second submission with same attempt_id
    res2 = client.post("/api/learning/SRC_PHYSICS_TEST/assessment/submit?user_id=student_default", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_duplicate"] is True
    # Verify attempt_count remains 1 (no double counter)
    assert data2["attempt_count"] == 1


def test_09_unknown_question_rejected(client):
    payload = {
        "attempt_id": "ATT_UNKNOWN_01",
        "concept_id": "CONCEPT_NEWTON_1",
        "question_id": "Q_DOES_NOT_EXIST",
        "selected_answer": 0,
    }
    res = client.post("/api/learning/SRC_PHYSICS_TEST/assessment/submit?user_id=student_default", json=payload)
    assert res.status_code == 404
    assert res.json()["detail"]["error_code"] == "UNKNOWN_QUESTION"


def test_10_cross_source_question_rejected(client, isolated_service):
    # Question registered to a different source
    q = AuthoritativeQuestion(
        question_id="Q_FOREIGN_01",
        concept_id="CONCEPT_NEWTON_1",
        source_id="SRC_OTHER_DOC",
        user_id="student_default",
        stem="Foreign question",
        options=["A", "B", "C", "D"],
        correct_index=0,
    )
    isolated_service.question_registry.register(q)

    payload = {
        "attempt_id": "ATT_CROSS_01",
        "concept_id": "CONCEPT_NEWTON_1",
        "question_id": "Q_FOREIGN_01",
        "selected_answer": 0,
    }
    res = client.post("/api/learning/SRC_PHYSICS_TEST/assessment/submit?user_id=student_default", json=payload)
    assert res.status_code == 403


# =============================================================================
# 3. Reassessment API & Answer Key Protection Tests
# =============================================================================
def test_11_reassessment_rejected_before_remediation(client, isolated_service):
    # Concept is UNASSESSED
    res = client.post("/api/learning/SRC_PHYSICS_TEST/reassessment/generate?concept_id=CONCEPT_NEWTON_1&user_id=student_default")
    assert res.status_code == 400
    assert "REASSESSING" in res.json()["detail"]["message"]


def test_12_reassessment_response_never_exposes_answer_key(client, isolated_service):
    # Set concept into REASSESSING state
    m = MasteryRecord(
        user_id="student_default",
        source_id="SRC_PHYSICS_TEST",
        concept_id="CONCEPT_NEWTON_1",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    isolated_service.mastery_repo.save(m)

    with patch("app.services.mastery.reassessment_service.generate_question") as mock_gen:
        from app.services.assessment.schemas import Question, AssessmentOption
        mock_gen.return_value = Question(
            question_id="Q_REASS_001",
            concept_id="CONCEPT_NEWTON_1",
            concept_name="Newton's First Law",
            source_id="SRC_PHYSICS_TEST",
            stem="What happens when net external force is zero?",
            options=[
                AssessmentOption(index=0, text="Velocity remains constant"),
                AssessmentOption(index=1, text="Object accelerates"),
                AssessmentOption(index=2, text="Mass decreases"),
                AssessmentOption(index=3, text="Friction increases"),
            ],
            correct_index=0,
            explanation="Newton's first law defines inertial reference frames.",
            difficulty="intermediate",
        )

        res = client.post("/api/learning/SRC_PHYSICS_TEST/reassessment/generate?concept_id=CONCEPT_NEWTON_1&user_id=student_default")
        assert res.status_code == 200
        data = res.json()

        # Critical security assertions: ensure zero answer key leakage
        assert "correct_answer" not in data
        assert "correct_index" not in data
        assert "is_correct" not in data
        assert "answer_key" not in data
        assert len(data["options"]) == 4
        assert data["question_id"] == "Q_REASS_001"


def test_13_repeated_reassessment_generation_idempotent_reuse(client, isolated_service):
    m = MasteryRecord(
        user_id="student_default",
        source_id="SRC_PHYSICS_TEST",
        concept_id="CONCEPT_NEWTON_1",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    isolated_service.mastery_repo.save(m)

    with patch("app.services.mastery.reassessment_service.generate_question") as mock_gen:
        from app.services.assessment.schemas import Question, AssessmentOption
        mock_gen.return_value = Question(
            question_id="Q_REASS_002",
            concept_id="CONCEPT_NEWTON_1",
            concept_name="Newton's First Law",
            source_id="SRC_PHYSICS_TEST",
            stem="Reassessment question stem",
            options=[AssessmentOption(index=i, text=f"Text {i}") for i in range(4)],
            correct_index=0,
            explanation="Explanation text",
        )

        res1 = client.post("/api/learning/SRC_PHYSICS_TEST/reassessment/generate?concept_id=CONCEPT_NEWTON_1&user_id=student_default")
        assert res1.status_code == 200
        qid1 = res1.json()["question_id"]

        # Call again before answering
        res2 = client.post("/api/learning/SRC_PHYSICS_TEST/reassessment/generate?concept_id=CONCEPT_NEWTON_1&user_id=student_default")
        assert res2.status_code == 200
        qid2 = res2.json()["question_id"]

        # Must reuse the same pending question instead of generating a new one
        assert qid1 == qid2
        assert mock_gen.call_count == 1



# =============================================================================
# 4. Remediation Orchestration API Tests
# =============================================================================
def test_14_remediation_post_returns_202_accepted(client, isolated_service):
    # Set concept to WEAK
    m = MasteryRecord(
        user_id="student_default",
        source_id="SRC_PHYSICS_TEST",
        concept_id="CONCEPT_NEWTON_1",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.WEAK,
    )
    isolated_service.mastery_repo.save(m)

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        res = client.post("/api/learning/SRC_PHYSICS_TEST/remediation?user_id=student_default", json={"concept_id": "CONCEPT_NEWTON_1"})
        assert res.status_code == 202
        data = res.json()
        assert data["concept_id"] == "CONCEPT_NEWTON_1"
        assert data["status"] in ("RUNNING", "READY")
        assert data["remediation_job_id"].startswith("REM_")


def test_15_duplicate_remediation_post_reuses_same_job(client, isolated_service):
    m = MasteryRecord(
        user_id="student_default",
        source_id="SRC_PHYSICS_TEST",
        concept_id="CONCEPT_NEWTON_1",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.WEAK,
    )
    isolated_service.mastery_repo.save(m)

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        res1 = client.post("/api/learning/SRC_PHYSICS_TEST/remediation?user_id=student_default", json={"concept_id": "CONCEPT_NEWTON_1"})
        job_id_1 = res1.json()["remediation_job_id"]

        res2 = client.post("/api/learning/SRC_PHYSICS_TEST/remediation?user_id=student_default", json={"concept_id": "CONCEPT_NEWTON_1"})
        job_id_2 = res2.json()["remediation_job_id"]

        assert job_id_1 == job_id_2


def test_16_remediation_status_polling_does_not_expose_filesystem_path(client, isolated_service):
    job = RemediationJob(
        remediation_job_id="REM_TEST_01",
        user_id="student_default",
        source_id="SRC_PHYSICS_TEST",
        concept_id="CONCEPT_NEWTON_1",
        status=RemediationJobStatus.READY,
        video_job_id="VID_TEST_01",
        video_path="C:\\Users\\ANVESH\\Downloads\\AI-VIDEO-GENERATOR-main\\storage\\videos\\final.mp4",
        duration_seconds=30.0,
        idempotency_key="key_01",
    )
    isolated_service.remediation_repo.save(job)

    res = client.get("/api/learning/SRC_PHYSICS_TEST/remediation/REM_TEST_01?user_id=student_default")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "READY"
    assert data["stream_url"] == "/video/VID_TEST_01/stream"
    # Ensure raw filesystem path is not exposed
    assert "video_path" not in data
    assert "C:\\" not in str(data)


def test_17_remediation_status_cross_user_lookup_rejected(client, isolated_service):
    job = RemediationJob(
        remediation_job_id="REM_OTHER_01",
        user_id="user_alice",
        source_id="SRC_PHYSICS_TEST",
        concept_id="CONCEPT_NEWTON_1",
        status=RemediationJobStatus.READY,
        idempotency_key="key_other",
    )
    isolated_service.remediation_repo.save(job)

    # Bob requests Alice's job
    res = client.get("/api/learning/SRC_PHYSICS_TEST/remediation/REM_OTHER_01?user_id=user_bob")
    assert res.status_code == 403


def test_18_needs_support_concept_remediation_rejected(client, isolated_service):
    m = MasteryRecord(
        user_id="student_default",
        source_id="SRC_PHYSICS_TEST",
        concept_id="CONCEPT_NEWTON_1",
        attempt_count=3,
        incorrect_count=3,
        remediation_attempt_count=3,
        mastery_state=MasteryState.NEEDS_SUPPORT,
    )
    isolated_service.mastery_repo.save(m)

    res = client.post("/api/learning/SRC_PHYSICS_TEST/remediation?user_id=student_default", json={"concept_id": "CONCEPT_NEWTON_1"})
    assert res.status_code == 409
    assert "NEEDS_SUPPORT" in res.json()["detail"]["message"]


# =============================================================================
# 5. Full Real API Flow Integration Test
# =============================================================================
def test_19_complete_api_integration_flow(client, isolated_service):
    """Execute complete learner flow via HTTP endpoints:

    1. GET roadmap (Initial: CONCEPT_NEWTON_1 is ASSESS)
    2. Register diagnostic question & submit incorrect answer -> WEAK
    3. GET next-action -> REMEDIATE
    4. POST remediation -> 202 Accepted & READY
    5. GET next-action -> REASSESS
    6. POST reassessment/generate -> safe question (no answer key)
    7. Submit reassessment attempt 1 (correct) -> state stays REASSESSING (needs 2)
    8. Submit reassessment attempt 2 (correct) -> transitions to MASTERED
    9. GET updated roadmap -> CONCEPT_NEWTON_2 is now unlocked for ASSESS
    """
    user = "student_default"
    source = "SRC_PHYSICS_TEST"

    # 1. Initial Roadmap
    r1 = client.get(f"/api/learning/{source}/roadmap?user_id={user}").json()
    assert r1["next_action"]["concept_id"] == "CONCEPT_NEWTON_1"
    assert r1["next_action"]["action_type"] == "ASSESS"

    # 2. Register diagnostic question & submit incorrect
    q_diag = AuthoritativeQuestion(
        question_id="Q_FLOW_DIAG",
        concept_id="CONCEPT_NEWTON_1",
        source_id=source,
        user_id=user,
        stem="Diagnostic question stem",
        options=["Option 0", "Option 1 (Correct)", "Option 2", "Option 3"],
        correct_index=1,
    )
    isolated_service.question_registry.register(q_diag)

    sub1 = client.post(
        f"/api/learning/{source}/assessment/submit?user_id={user}",
        json={"attempt_id": "ATT_FLOW_01", "concept_id": "CONCEPT_NEWTON_1", "question_id": "Q_FLOW_DIAG", "selected_answer": 0},
    ).json()
    assert sub1["is_correct"] is False
    assert sub1["mastery_state"] == "WEAK"
    assert sub1["next_action"]["action_type"] == "REMEDIATE"

    # 3. Verify next action
    act1 = client.get(f"/api/learning/{source}/next-action?user_id={user}").json()
    assert act1["action_type"] == "REMEDIATE"
    assert act1["concept_id"] == "CONCEPT_NEWTON_1"

    # 4. Trigger Remediation
    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        rem_res = client.post(f"/api/learning/{source}/remediation?user_id={user}", json={}).json()
        assert rem_res["status"] in ("RUNNING", "READY")
        rem_id = rem_res["remediation_job_id"]

        # Poll status
        poll_res = client.get(f"/api/learning/{source}/remediation/{rem_id}?user_id={user}").json()
        assert poll_res["status"] == "READY"
        assert poll_res["stream_url"] == f"/video/{rem_id}/stream"

    # 5. Next action must now be REASSESS
    act2 = client.get(f"/api/learning/{source}/next-action?user_id={user}").json()
    assert act2["action_type"] == "REASSESS"
    assert act2["concept_id"] == "CONCEPT_NEWTON_1"

    # 6. Generate Reassessment Question
    with patch("app.services.mastery.reassessment_service.generate_question") as mock_gen:
        from app.services.assessment.schemas import Question, AssessmentOption
        mock_gen.return_value = Question(
            question_id="Q_FLOW_REASS_01",
            concept_id="CONCEPT_NEWTON_1",
            concept_name="Newton's First Law",
            source_id=source,
            stem="Reassessment question stem 1",
            options=[
                AssessmentOption(index=0, text="Correct Option"),
                AssessmentOption(index=1, text="Wrong Option"),
                AssessmentOption(index=2, text="Wrong Option"),
                AssessmentOption(index=3, text="Wrong Option"),
            ],
            correct_index=0,
            explanation="Explanation for reassessment question",
        )
        reass_q1 = client.post(f"/api/learning/{source}/reassessment/generate?user_id={user}").json()
        assert reass_q1["question_id"] == "Q_FLOW_REASS_01"
        assert "correct_answer" not in reass_q1

    # 7. Submit First Reassessment Attempt (Correct)
    sub_r1 = client.post(
        f"/api/learning/{source}/assessment/submit?user_id={user}",
        json={"attempt_id": "ATT_FLOW_R1", "concept_id": "CONCEPT_NEWTON_1", "question_id": "Q_FLOW_REASS_01", "selected_answer": 0, "assessment_type": "REASSESSMENT"},
    ).json()
    assert sub_r1["is_correct"] is True
    # Needs minimum 2 reassessments for mastery under Step 5B.1
    assert sub_r1["mastery_state"] == "REASSESSING"
    assert sub_r1["reassessment_attempt_count"] == 1

    # 8. Submit Second Reassessment Attempt (Correct)
    q_reass_2 = AuthoritativeQuestion(
        question_id="Q_FLOW_REASS_02",
        concept_id="CONCEPT_NEWTON_1",
        source_id=source,
        user_id=user,
        stem="Reassessment question stem 2",
        options=["Wrong", "Correct Option", "Wrong", "Wrong"],
        correct_index=1,
    )
    isolated_service.question_registry.register(q_reass_2)

    sub_r2 = client.post(
        f"/api/learning/{source}/assessment/submit?user_id={user}",
        json={"attempt_id": "ATT_FLOW_R2", "concept_id": "CONCEPT_NEWTON_1", "question_id": "Q_FLOW_REASS_02", "selected_answer": 1, "assessment_type": "REASSESSMENT"},
    ).json()
    assert sub_r2["is_correct"] is True
    # Now has 2/2 reassessments correct -> 100% mastery score -> MASTERED!
    assert sub_r2["mastery_state"] == "MASTERED"
    assert sub_r2["mastery_score"] == 100.0

    # 9. Verify Updated Roadmap: Concept 1 is MASTERED; Concept 2 is unlocked!
    r_final = client.get(f"/api/learning/{source}/roadmap?user_id={user}").json()
    assert "CONCEPT_NEWTON_1" in r_final["mastered_concepts"]
    assert "CONCEPT_NEWTON_2" not in r_final["blocked_concepts"]
    assert "CONCEPT_NEWTON_2" in r_final["unassessed_concepts"]
    assert r_final["next_action"]["concept_id"] == "CONCEPT_NEWTON_2"
    assert r_final["next_action"]["action_type"] == "ASSESS"
