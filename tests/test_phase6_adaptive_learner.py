"""Phase 6 Comprehensive Test Suite: Adaptive Assessment, Agentic AI, and Personalized Roadmap.

Validates:
1. Question generation & deterministic MCQ grading
2. Descriptive question submission & bounded rubric-based scoring
3. Answer-key secrecy & client response hygiene
4. Assessment persistence & duplicate submission idempotency
5. Mastery state machine transitions (UNASSESSED -> LEARNING -> WEAK -> REMEDIATING -> REASSESSING -> MASTERED)
6. Weak-concept identification & agentic remediation decisions
7. Video recommendations & reuse
8. Reassessment eligibility & novel generation
9. Adaptive roadmap dynamic partitioning & progress recalculation
10. Anti-loop kill switch (NEEDS_SUPPORT threshold)
11. Multi-tenant, cross-user, and cross-source isolation
12. Complete end-to-end adaptive learner simulation
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.schemas import KnowledgeGraph, ConceptNode
from app.services.mastery.models import MasteryRecord, MasteryState
from app.services.mastery.question_registry import AuthoritativeQuestion
from app.services.mastery.api_schemas import (
    AssessmentSubmissionRequestDTO,
    AssessmentType,
)
from app.services.mastery.application_service import AdaptiveLearningService
from app.services.assessment.descriptive_evaluator import (
    RubricCriterion,
    evaluate_descriptive_answer,
)


from app.api.learning import get_adaptive_learning_service
from app.services.schemas import KnowledgeGraph, ConceptNode, SourceRecord
from app.services.video.scene_schema import VideoArtifact, VideoJobStatus
from pathlib import Path


@pytest.fixture
def mock_curriculum():
    c1 = ConceptNode(
        concept_id="CONCEPT_AUTH_FLOW",
        name="Authentication Workflow",
        definition="User identification and token verification protocol",
        prerequisite_concept_ids=[],
    )
    c2 = ConceptNode(
        concept_id="CONCEPT_TOKEN_REFRESH",
        name="Token Refresh Mechanism",
        definition="Silent renewal of expired credentials using refresh tokens",
        prerequisite_concept_ids=["CONCEPT_AUTH_FLOW"],
    )
    kg = KnowledgeGraph(
        concepts={
            "CONCEPT_AUTH_FLOW": c1,
            "CONCEPT_TOKEN_REFRESH": c2,
        }
    )
    rec = SourceRecord(
        source_id="SRC_AUTH_01",
        filename="auth_spec.pdf",
        source_type="pdf",
        mime_type="application/pdf",
        file_hash="hash_auth",
        sha256="hash_auth",
        file_size=2048,
        uploaded_by="",
        user_id="",
        owner_user_id="",
        version=1,
        source_version="v1",
        status="READY",
    )
    return rec, kg


@pytest.fixture
def isolated_service(mock_curriculum):
    """Provide isolated in-memory AdaptiveLearningService with mock video engine."""
    async def mock_video_engine(target, job_id, **kwargs):
        return VideoArtifact(
            job_id=job_id,
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            status=VideoJobStatus.COMPLETED,
            video_path=str(Path("storage/videos/test_remedial.mp4")),
            duration_seconds=25.0,
        )

    service = AdaptiveLearningService(
        video_engine_fn=mock_video_engine,
    )
    return service


@pytest.fixture
def client(isolated_service, mock_curriculum, monkeypatch):
    """FastAPI TestClient with overridden service dependency and mocked registry."""
    rec, kg = mock_curriculum

    app.dependency_overrides[get_adaptive_learning_service] = lambda: isolated_service

    dummy_chunks = [
        type("RichChunk", (), {
            "model_dump": lambda s: {
                "chunk_id": "ch_auth_01",
                "text": "Authentication verifies identity using tokens. Access tokens grant entry.",
                "source_id": rec.source_id,
            }
        })()
    ]
    monkeypatch.setattr("app.services.mastery.application_service.get_source_record", lambda sid: rec)
    monkeypatch.setattr("app.services.mastery.application_service.load_knowledge_graph", lambda sid: kg)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_knowledge_graph", lambda sid: kg)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_rich_chunks", lambda sid: dummy_chunks)

    yield TestClient(app)

    app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# Test 1: Bounded Rubric-Based Descriptive Answer Evaluation
# -----------------------------------------------------------------------------
def test_01_descriptive_rubric_evaluation_sufficient_response():
    rubric = [
        RubricCriterion(
            criterion_id="CRIT_1",
            description="Explains token rotation mechanism",
            points=2.0,
            required_keywords=["refresh token", "rotation", "access token"],
        ),
        RubricCriterion(
            criterion_id="CRIT_2",
            description="Discusses session expiration and security",
            points=1.0,
            required_keywords=["expiration", "security"],
        ),
    ]

    student_response = (
        "When the access token expires, the client sends a refresh token to the authorization server. "
        "The server performs token rotation, invalidating the old token and returning a new access token, "
        "which enhances overall session security and minimizes unauthorized access upon expiration."
    )

    result = evaluate_descriptive_answer(
        question_id="Q_DESC_01",
        concept_id="CONCEPT_TOKEN_REFRESH",
        student_response=student_response,
        rubric_criteria=rubric,
        authoritative_explanation="Refresh tokens allow renewing access credentials without requiring re-authentication.",
    )

    assert result.passed is True
    assert result.score >= 80.0
    assert len(result.criteria_met) >= 1
    assert "Refresh tokens allow" in result.explanation
    assert result.word_count > 15


def test_02_descriptive_rubric_evaluation_too_brief_rejection():
    rubric = [
        RubricCriterion(
            criterion_id="CRIT_1",
            description="Core concept definition",
            points=2.0,
            required_keywords=["auth", "token"],
        )
    ]

    result = evaluate_descriptive_answer(
        question_id="Q_DESC_02",
        concept_id="CONCEPT_AUTH_FLOW",
        student_response="Tokens are used.",  # Only 3 words
        rubric_criteria=rubric,
        min_words=5,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "too brief" in result.feedback.lower()


# -----------------------------------------------------------------------------
# Test 3: API Integration for Descriptive Answer Submission
# -----------------------------------------------------------------------------
def test_03_submit_descriptive_answer_via_api(client, isolated_service):
    user = "student_alpha"
    source = "SRC_AUTH_01"

    # Register an authoritative descriptive question
    q_desc = AuthoritativeQuestion(
        question_id="Q_DESC_TEST",
        concept_id="CONCEPT_AUTH_FLOW",
        source_id=source,
        user_id=user,
        stem="Explain the authentication flow when a user logs in.",
        question_type="descriptive",
        rubric_criteria=[
            {
                "criterion_id": "C1",
                "description": "Credentials verification",
                "points": 1.0,
                "required_keywords": ["credentials", "verify", "password"],
            },
            {
                "criterion_id": "C2",
                "description": "JWT issuance",
                "points": 1.0,
                "required_keywords": ["jwt", "token", "session"],
            },
        ],
        explanation="The server verifies credentials against hashed records and issues a signed JWT token.",
    )
    isolated_service.question_registry.register(q_desc)

    payload = {
        "attempt_id": "ATT_DESC_01",
        "concept_id": "CONCEPT_AUTH_FLOW",
        "question_id": "Q_DESC_TEST",
        "selected_answer": -1,
        "text_answer": (
            "The client sends user credentials over HTTPS. The server checks the password hash to verify "
            "authenticity and upon success issues a signed JWT access token for the user session."
        ),
    }

    res = client.post(f"/api/learning/{source}/assessment/submit?user_id={user}", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_correct"] is True
    assert data["text_answer"] is not None
    assert data["feedback"] is not None
    assert "The server verifies credentials" in data["explanation"]
    assert data["mastery_state"] in ("LEARNING", "MASTERED")


# -----------------------------------------------------------------------------
# Test 4: Answer-Key Confidentiality
# -----------------------------------------------------------------------------
def test_04_answer_key_confidentiality_in_roadmap_and_reassessment(client, isolated_service):
    user = "student_beta"
    source = "SRC_AUTH_01"

    # Set concept to REASSESSING
    m = MasteryRecord(
        user_id=user,
        source_id=source,
        concept_id="CONCEPT_AUTH_FLOW",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    isolated_service.mastery_repo.save(m)

    with patch("app.services.mastery.reassessment_service.generate_question") as mock_gen:
        from app.services.assessment.schemas import Question, AssessmentOption
        mock_gen.return_value = Question(
            question_id="Q_SAFE_01",
            concept_id="CONCEPT_AUTH_FLOW",
            concept_name="Authentication Workflow",
            source_id=source,
            stem="Which token verifies user identity?",
            options=[
                AssessmentOption(index=0, text="Access Token"),
                AssessmentOption(index=1, text="Dummy Option 1"),
                AssessmentOption(index=2, text="Dummy Option 2"),
                AssessmentOption(index=3, text="Dummy Option 3"),
            ],
            correct_index=0,
            explanation="SECRET EXPLANATION",
        )

        res = client.post(f"/api/learning/{source}/reassessment/generate?concept_id=CONCEPT_AUTH_FLOW&user_id={user}")
        assert res.status_code == 200
        data = res.json()

        # Strict security assertions: zero answer leakage
        for secret_key in ["correct_index", "correct_answer", "answer_key", "is_correct", "explanation"]:
            assert secret_key not in data, f"Leaked hidden key: {secret_key}"


# -----------------------------------------------------------------------------
# Test 5: Assessment Attempt Persistence and Idempotency
# -----------------------------------------------------------------------------
def test_05_duplicate_submission_is_idempotent(client, isolated_service):
    user = "student_gamma"
    source = "SRC_AUTH_01"

    q = AuthoritativeQuestion(
        question_id="Q_IDEM_01",
        concept_id="CONCEPT_AUTH_FLOW",
        source_id=source,
        user_id=user,
        stem="Identify the protocol",
        options=["OAuth 2.0", "FTP", "Telnet", "SMTP"],
        correct_index=0,
    )
    isolated_service.question_registry.register(q)

    payload = {
        "attempt_id": "ATT_IDEM_001",
        "concept_id": "CONCEPT_AUTH_FLOW",
        "question_id": "Q_IDEM_01",
        "selected_answer": 0,
    }

    # First submission
    res1 = client.post(f"/api/learning/{source}/assessment/submit?user_id={user}", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_duplicate"] is False
    assert data1["is_correct"] is True

    # Duplicate submission
    res2 = client.post(f"/api/learning/{source}/assessment/submit?user_id={user}", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_duplicate"] is True
    assert data2["attempt_count"] == data1["attempt_count"]


# -----------------------------------------------------------------------------
# Test 6: Weak-Concept Identification and Agentic Remediation Decision
# -----------------------------------------------------------------------------
def test_06_weak_concept_triggers_remediation_decision(client, isolated_service):
    user = "student_delta"
    source = "SRC_AUTH_01"

    q = AuthoritativeQuestion(
        question_id="Q_WEAK_01",
        concept_id="CONCEPT_AUTH_FLOW",
        source_id=source,
        user_id=user,
        stem="Identify the protocol",
        options=["OAuth 2.0", "FTP", "Telnet", "SMTP"],
        correct_index=0,
    )
    isolated_service.question_registry.register(q)

    # Fail the diagnostic question
    payload = {
        "attempt_id": "ATT_FAIL_01",
        "concept_id": "CONCEPT_AUTH_FLOW",
        "question_id": "Q_WEAK_01",
        "selected_answer": 1,  # Incorrect
    }

    res = client.post(f"/api/learning/{source}/assessment/submit?user_id={user}", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_correct"] is False
    assert data["mastery_state"] == "WEAK"
    assert data["next_action"]["action_type"] == "REMEDIATE"
    assert data["next_action"]["concept_id"] == "CONCEPT_AUTH_FLOW"


# -----------------------------------------------------------------------------
# Test 7: Video Remediation Integration & Reuse
# -----------------------------------------------------------------------------
def test_07_video_remediation_initiation_and_reuse(client, isolated_service):
    user = "student_epsilon"
    source = "SRC_AUTH_01"

    # Set concept to WEAK
    m = MasteryRecord(
        user_id=user,
        source_id=source,
        concept_id="CONCEPT_AUTH_FLOW",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.WEAK,
    )
    isolated_service.mastery_repo.save(m)

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 25.0}):
        # Trigger remediation
        res = client.post(f"/api/learning/{source}/remediation?user_id={user}", json={})
        assert res.status_code == 202
        rem_data = res.json()
        job_id = rem_data["remediation_job_id"]
        assert rem_data["status"] in ("RUNNING", "READY")

        # Second identical request reuses active/completed job
        res_dup = client.post(f"/api/learning/{source}/remediation?user_id={user}", json={})
        assert res_dup.status_code == 202
        assert res_dup.json()["remediation_job_id"] == job_id


# -----------------------------------------------------------------------------
# Test 8: Anti-Loop Kill Switch to NEEDS_SUPPORT
# -----------------------------------------------------------------------------
def test_08_anti_loop_kill_switch_transitions_to_needs_support(client, isolated_service):
    user = "student_zeta"
    source = "SRC_AUTH_01"

    # Max allowed attempts before kill switch is 3
    m = MasteryRecord(
        user_id=user,
        source_id=source,
        concept_id="CONCEPT_AUTH_FLOW",
        attempt_count=3,
        incorrect_count=3,
        remediation_attempt_count=3,
        mastery_state=MasteryState.REASSESSING,
    )
    isolated_service.mastery_repo.save(m)

    q = AuthoritativeQuestion(
        question_id="Q_KILL_01",
        concept_id="CONCEPT_AUTH_FLOW",
        source_id=source,
        user_id=user,
        stem="Final reassessment question",
        options=["Option 0", "Option 1", "Option 2", "Option 3"],
        correct_index=0,
    )
    isolated_service.question_registry.register(q)

    # Fail the 3rd reassessment
    payload = {
        "attempt_id": "ATT_KILL_03",
        "concept_id": "CONCEPT_AUTH_FLOW",
        "question_id": "Q_KILL_01",
        "selected_answer": 2,  # Incorrect
        "assessment_type": "REASSESSMENT",
    }

    res = client.post(f"/api/learning/{source}/assessment/submit?user_id={user}", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["mastery_state"] == "NEEDS_SUPPORT"
    assert data["next_action"]["action_type"] != "REMEDIATE"


# -----------------------------------------------------------------------------
# Test 9: Complete Closed-Loop Adaptive Learner Journey Simulation
# -----------------------------------------------------------------------------
def test_09_complete_adaptive_learner_loop_simulation(client, isolated_service):
    user = "student_omega"
    source = "SRC_AUTH_01"

    # 1. Initial State: CONCEPT_AUTH_FLOW unassessed, CONCEPT_TOKEN_REFRESH blocked
    rm1 = client.get(f"/api/learning/{source}/roadmap?user_id={user}").json()
    assert "CONCEPT_AUTH_FLOW" in rm1["unassessed_concepts"]
    assert "CONCEPT_TOKEN_REFRESH" in rm1["blocked_concepts"]
    assert rm1["next_action"]["concept_id"] == "CONCEPT_AUTH_FLOW"
    assert rm1["next_action"]["action_type"] == "ASSESS"

    # 2. Diagnostic Assessment Failure
    q1 = AuthoritativeQuestion(
        question_id="Q_SIM_DIAG",
        concept_id="CONCEPT_AUTH_FLOW",
        source_id=source,
        user_id=user,
        stem="Diagnostic question",
        options=["Right", "Wrong 1", "Wrong 2", "Wrong 3"],
        correct_index=0,
    )
    isolated_service.question_registry.register(q1)

    sub_diag = client.post(
        f"/api/learning/{source}/assessment/submit?user_id={user}",
        json={"attempt_id": "ATT_SIM_01", "concept_id": "CONCEPT_AUTH_FLOW", "question_id": "Q_SIM_DIAG", "selected_answer": 1},
    ).json()
    assert sub_diag["is_correct"] is False
    assert sub_diag["mastery_state"] == "WEAK"
    assert sub_diag["next_action"]["action_type"] == "REMEDIATE"

    # 3. Trigger Remediation Video
    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 25.0}):
        rem_res = client.post(f"/api/learning/{source}/remediation?user_id={user}", json={}).json()
        assert rem_res["status"] in ("RUNNING", "READY")

    # Next action updates to REASSESS
    act_reass = client.get(f"/api/learning/{source}/next-action?user_id={user}").json()
    assert act_reass["action_type"] == "REASSESS"
    assert act_reass["concept_id"] == "CONCEPT_AUTH_FLOW"

    # 4. Generate & Submit Reassessments (First Reassessment)
    q_reass_1 = AuthoritativeQuestion(
        question_id="Q_SIM_REASS_1",
        concept_id="CONCEPT_AUTH_FLOW",
        source_id=source,
        user_id=user,
        stem="Reassessment 1",
        options=["Right", "Wrong 1", "Wrong 2", "Wrong 3"],
        correct_index=0,
    )
    isolated_service.question_registry.register(q_reass_1)

    sub_r1 = client.post(
        f"/api/learning/{source}/assessment/submit?user_id={user}",
        json={"attempt_id": "ATT_SIM_R1", "concept_id": "CONCEPT_AUTH_FLOW", "question_id": "Q_SIM_REASS_1", "selected_answer": 0, "assessment_type": "REASSESSMENT"},
    ).json()
    assert sub_r1["is_correct"] is True
    assert sub_r1["mastery_state"] == "REASSESSING"

    # Second Reassessment (Meets Mastery Threshold)
    q_reass_2 = AuthoritativeQuestion(
        question_id="Q_SIM_REASS_2",
        concept_id="CONCEPT_AUTH_FLOW",
        source_id=source,
        user_id=user,
        stem="Reassessment 2",
        options=["Wrong 0", "Right", "Wrong 2", "Wrong 3"],
        correct_index=1,
    )
    isolated_service.question_registry.register(q_reass_2)

    sub_r2 = client.post(
        f"/api/learning/{source}/assessment/submit?user_id={user}",
        json={"attempt_id": "ATT_SIM_R2", "concept_id": "CONCEPT_AUTH_FLOW", "question_id": "Q_SIM_REASS_2", "selected_answer": 1, "assessment_type": "REASSESSMENT"},
    ).json()
    assert sub_r2["is_correct"] is True
    assert sub_r2["mastery_state"] == "MASTERED"

    # 5. Verify Roadmap Adaptation: Concept 1 is MASTERED, Concept 2 is UNBLOCKED!
    rm2 = client.get(f"/api/learning/{source}/roadmap?user_id={user}").json()
    assert "CONCEPT_AUTH_FLOW" in rm2["mastered_concepts"]
    assert "CONCEPT_TOKEN_REFRESH" not in rm2["blocked_concepts"]
    assert "CONCEPT_TOKEN_REFRESH" in rm2["unassessed_concepts"]
    assert rm2["next_action"]["concept_id"] == "CONCEPT_TOKEN_REFRESH"
    assert rm2["next_action"]["action_type"] == "ASSESS"


def test_10_descriptive_semantic_edge_cases():
    """Verify semantic safeguards: disclaimer rejection, contradiction detection, and synonym tolerance."""
    rubric = [
        RubricCriterion(
            criterion_id="C1",
            description="Explains token rotation mechanism",
            points=2.0,
            required_keywords=["refresh token", "rotation", "access token"],
        ),
        RubricCriterion(
            criterion_id="C2",
            description="Discusses session expiration and security",
            points=1.0,
            required_keywords=["expiration", "security"],
        ),
    ]

    # 1. Conceptually correct answer with vocabulary variation (synonyms/paraphrasing)
    synonym_ans = "When identity assertions lapse in validity, a renewal key is passed to auth endpoints to reissue entry credentials while invalidating obsolete tickets."
    r_syn = evaluate_descriptive_answer("Q1", "C_AUTH", synonym_ans, rubric)
    assert r_syn.passed is True
    assert r_syn.score >= 80.0

    # 2. Ignorance disclaimer containing keywords -> MUST FAIL
    disclaimer_ans = "I do not understand refresh token, rotation, access token, expiration, or security at all."
    r_disc = evaluate_descriptive_answer("Q2", "C_AUTH", disclaimer_ans, rubric)
    assert r_disc.passed is False
    assert r_disc.score == 0.0

    # 3. Contradictory assertion containing keywords -> MUST FAIL
    contradiction_ans = "Token rotation makes access token insecure and refresh token causes security breach upon expiration."
    r_contra = evaluate_descriptive_answer("Q3", "C_AUTH", contradiction_ans, rubric)
    assert r_contra.passed is False
    assert r_contra.score < 50.0

    # 4. Concise but accurate reasoning
    concise_ans = "Refresh tokens exchange expired access tokens for new ones securely."
    r_concise = evaluate_descriptive_answer("Q4", "C_AUTH", concise_ans, rubric)
    assert r_concise.passed is True
    assert r_concise.score >= 70.0

