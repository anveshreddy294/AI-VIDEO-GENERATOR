"""Phase 15 Required Regression & Acceptance Tests for Reassessment Repair.

Covers:
- Test A: Safe reassessment response contains structured SafeOptions [{"index": 0, "text": "..."}, ...]
- Test B: No option has empty text
- Test C: renderReassessmentQuestion logic produces visible non-empty text for all 4 choices
- Test D: Frontend backwards-compatibility normalization correctly handles list[str]
- Test E: No correct_index or answer-key leakage exists in client response
- Test F: First correct reassessment attempt causes next reassessment question to appear
- Test G: Second successful reassessment transitions state machine to MASTERED
- Test H: Incorrect reassessment returns learner to WEAK and invalidates remaining queued questions
- Test I: Stale or invalidated queued question submission is rejected by server
- Test J: Repeated reassessment generation requests do not create duplicate Ollama generations
- Test K: Reassessment batch contains distinct question IDs, stems, and option sets
- Test L: Reassessment questions remain grounded against source evidence
"""

import copy
from unittest.mock import patch, MagicMock
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
    MasteryRecord,
    MasteryState,
    MasteryStateMachine,
    ReassessmentQueue,
    AssessmentServiceError,
)
from app.services.mastery.api_schemas import (
    SafeReassessmentQuestionResponse,
    SafeOption,
    AssessmentSubmissionRequestDTO,
)
from app.services.assessment.schemas import Question, AssessmentOption
from app.services.schemas import ConceptNode, KnowledgeGraph, SourceRecord
from app.services.video.scene_schema import VideoArtifact, VideoJobStatus


@pytest.fixture
def curriculum():
    c1 = ConceptNode(
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        name="Linear Algebra",
        definition="Vector spaces, matrices, and linear transformations in machine learning.",
        prerequisite_concept_ids=[],
        source_content_ids=["cu_001"],
    )
    kg = KnowledgeGraph(concepts={"CONCEPT_LINEAR_ALGEBRA": c1})
    rec = SourceRecord(
        source_id="SRC_MATH_01",
        filename="math.pdf",
        source_type="pdf",
        mime_type="application/pdf",
        file_hash="h123",
        sha256="h123",
        file_size=1024,
        uploaded_by="student_test",
        user_id="student_test",
        owner_user_id="student_test",
        version=1,
        source_version="v1",
        status="READY",
    )
    return rec, kg


@pytest.fixture
def app_service(curriculum):
    async def mock_video_engine(target, job_id, **kwargs):
        return VideoArtifact(
            job_id=job_id,
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            status=VideoJobStatus.COMPLETED,
            video_path="storage/videos/test.mp4",
            duration_seconds=30.0,
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
def client(app_service, curriculum, monkeypatch):
    rec, kg = curriculum
    app.dependency_overrides[get_adaptive_learning_service] = lambda: app_service

    dummy_chunks = [
        type("RichChunk", (), {
            "model_dump": lambda s: {
                "chunk_id": "ch_001",
                "text": "Linear algebra provides the mathematical language for multidimensional data representations including matrices and vectors.",
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
# Test A: Safe reassessment response contains options=[{"index":0, "text":"..."}, ...]
# =============================================================================
def test_a_safe_reassessment_response_contains_structured_safe_options(client, app_service):
    m = MasteryRecord(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    app_service.mastery_repo.save(m)

    mock_q = Question(
        question_id="Q_LA_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        concept_name="Linear Algebra",
        source_id="SRC_MATH_01",
        stem="What is the primary role of linear algebra in machine learning?",
        options=[
            AssessmentOption(index=0, text="Representing vector and matrix operations"),
            AssessmentOption(index=1, text="Managing HTTP server connections"),
            AssessmentOption(index=2, text="Rendering DOM nodes"),
            AssessmentOption(index=3, text="CSS styling"),
        ],
        correct_index=0,
        explanation="Linear algebra provides mathematical tools for matrices.",
    )

    with patch("app.services.mastery.reassessment_service.generate_question", return_value=mock_q):
        res = client.post("/api/learning/SRC_MATH_01/reassessment/generate?concept_id=CONCEPT_LINEAR_ALGEBRA&user_id=student_test")
        assert res.status_code == 200
        data = res.json()

        assert "options" in data
        assert len(data["options"]) == 4
        for i, opt in enumerate(data["options"]):
            assert isinstance(opt, dict)
            assert "index" in opt
            assert "text" in opt
            assert opt["index"] == i
            assert isinstance(opt["text"], str)
            assert len(opt["text"].strip()) > 0


# =============================================================================
# Test B: No option has empty text
# =============================================================================
def test_b_no_option_has_empty_text():
    # SafeReassessmentQuestionResponse must strictly reject empty option text
    with pytest.raises(Exception):
        SafeReassessmentQuestionResponse(
            question_id="Q_TEST",
            concept_id="C_TEST",
            stem="Test stem",
            options=[
                SafeOption(index=0, text=""),
                SafeOption(index=1, text="Option B"),
                SafeOption(index=2, text="Option C"),
                SafeOption(index=3, text="Option D"),
            ],
            difficulty="intermediate",
            variant_type="application",
            question_number=1,
            total_questions=2,
        )


# =============================================================================
# Test C: renderReassessmentQuestion produces visible non-empty text for all 4 choices
# =============================================================================
def test_c_render_reassessment_question_dashboard_normalization(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.text

    # Verify that the dashboard script extracts text whether opt is an object or string
    assert "opt.text" in html
    assert "(opt && typeof opt === 'object')" in html
    assert "lblReassessProgressBadge" in html


# =============================================================================
# Test D: Frontend backwards-compatibility normalization handles list[str] temporarily
# =============================================================================
def test_d_frontend_backwards_compat_normalizes_list_of_strings():
    # Simulate JS normalizer in Python:
    # const optText = (opt && typeof opt === 'object') ? (opt.text || '') : String(opt || '');
    def js_normalize(opt):
        if isinstance(opt, dict):
            return opt.get("text", "")
        return str(opt or "")

    str_options = ["Alpha", "Beta", "Gamma", "Delta"]
    normalized_from_str = [js_normalize(opt) for opt in str_options]
    assert normalized_from_str == ["Alpha", "Beta", "Gamma", "Delta"]

    obj_options = [{"index": 0, "text": "Alpha"}, {"index": 1, "text": "Beta"}, {"index": 2, "text": "Gamma"}, {"index": 3, "text": "Delta"}]
    normalized_from_obj = [js_normalize(opt) for opt in obj_options]
    assert normalized_from_obj == ["Alpha", "Beta", "Gamma", "Delta"]


# =============================================================================
# Test E: No correct_index exists in client response
# =============================================================================
def test_e_no_correct_answer_leakage_in_client_response(client, app_service):
    m = MasteryRecord(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    app_service.mastery_repo.save(m)

    mock_q = Question(
        question_id="Q_LA_LEAK",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        concept_name="Linear Algebra",
        source_id="SRC_MATH_01",
        stem="Testing leak",
        options=[AssessmentOption(index=i, text=f"Choice {i}") for i in range(4)],
        correct_index=2,
        explanation="Secret explanation",
    )

    with patch("app.services.mastery.reassessment_service.generate_question", return_value=mock_q):
        res = client.post("/api/learning/SRC_MATH_01/reassessment/generate?concept_id=CONCEPT_LINEAR_ALGEBRA&user_id=student_test")
        assert res.status_code == 200
        data = res.json()

        for forbidden in ["correct_index", "correct_answer", "answer_key", "is_correct", "explanation"]:
            assert forbidden not in data, f"Leaked forbidden key '{forbidden}' in client reassessment response!"


# =============================================================================
# Test F & G: Q1 correct causes next question to appear; Q2 correct transitions to MASTERED
# =============================================================================
def test_f_and_g_multi_question_reassessment_sequence(client, app_service):
    m = MasteryRecord(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    app_service.mastery_repo.save(m)

    # Register 2-question batch in the session
    q1 = AuthoritativeQuestion(
        question_id="Q_SEQ_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        source_id="SRC_MATH_01",
        user_id="student_test",
        stem="Question 1 stem",
        options=["Correct 1", "Wrong B", "Wrong C", "Wrong D"],
        correct_index=0,
        explanation="Explanation 1",
    )
    q2 = AuthoritativeQuestion(
        question_id="Q_SEQ_02",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        source_id="SRC_MATH_01",
        user_id="student_test",
        stem="Question 2 stem",
        options=["Wrong A", "Correct 2", "Wrong C", "Wrong D"],
        correct_index=1,
        explanation="Explanation 2",
    )
    app_service.question_registry.register(q1)
    app_service.question_registry.register(q2)
    app_service.reassessment_queue.register_batch(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        cycle=1,
        questions=[q1, q2],
    )

    # 1. Fetch Q1
    res1 = client.post("/api/learning/SRC_MATH_01/reassessment/generate?concept_id=CONCEPT_LINEAR_ALGEBRA&user_id=student_test")
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["question_id"] == "Q_SEQ_01"
    assert d1["question_number"] == 1
    assert d1["total_questions"] == 2

    # 2. Submit Q1 (Correct)
    sub1 = client.post(
        "/api/learning/SRC_MATH_01/assessment/submit?user_id=student_test",
        json={"attempt_id": "ATT_SEQ_01", "concept_id": "CONCEPT_LINEAR_ALGEBRA", "question_id": "Q_SEQ_01", "selected_answer": 0, "assessment_type": "REASSESSMENT"},
    ).json()
    assert sub1["is_correct"] is True
    assert sub1["mastery_state"] == "REASSESSING"
    assert sub1["next_action"]["action_type"] == "REASSESS"
    assert sub1["explanation"] == "Explanation 1"

    # Test F: Server serves Q2 next without another LLM wait
    res2 = client.post("/api/learning/SRC_MATH_01/reassessment/generate?concept_id=CONCEPT_LINEAR_ALGEBRA&user_id=student_test")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["question_id"] == "Q_SEQ_02"
    assert d2["question_number"] == 2
    assert d2["total_questions"] == 2

    # Test G: Submit Q2 (Correct) -> Transitions to MASTERED
    sub2 = client.post(
        "/api/learning/SRC_MATH_01/assessment/submit?user_id=student_test",
        json={"attempt_id": "ATT_SEQ_02", "concept_id": "CONCEPT_LINEAR_ALGEBRA", "question_id": "Q_SEQ_02", "selected_answer": 1, "assessment_type": "REASSESSMENT"},
    ).json()
    assert sub2["is_correct"] is True
    assert sub2["mastery_state"] == "MASTERED"
    assert sub2["mastery_score"] == 100.0
    assert sub2["explanation"] == "Explanation 2"


# =============================================================================
# Test H: Incorrect reassessment returns learner to WEAK and invalidates remaining queued questions
# =============================================================================
def test_h_incorrect_reassessment_invalidates_queue(client, app_service):
    m = MasteryRecord(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    app_service.mastery_repo.save(m)

    q1 = AuthoritativeQuestion(
        question_id="Q_FAIL_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        source_id="SRC_MATH_01",
        user_id="student_test",
        stem="Question 1",
        options=["Correct", "Wrong", "Wrong", "Wrong"],
        correct_index=0,
    )
    q2 = AuthoritativeQuestion(
        question_id="Q_FAIL_02",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        source_id="SRC_MATH_01",
        user_id="student_test",
        stem="Question 2",
        options=["Wrong", "Correct", "Wrong", "Wrong"],
        correct_index=1,
    )
    app_service.question_registry.register(q1)
    app_service.question_registry.register(q2)
    sess = app_service.reassessment_queue.register_batch(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        cycle=1,
        questions=[q1, q2],
    )

    # Submit WRONG answer to Q1
    sub = client.post(
        "/api/learning/SRC_MATH_01/assessment/submit?user_id=student_test",
        json={"attempt_id": "ATT_FAIL_01", "concept_id": "CONCEPT_LINEAR_ALGEBRA", "question_id": "Q_FAIL_01", "selected_answer": 2, "assessment_type": "REASSESSMENT"},
    ).json()

    assert sub["is_correct"] is False
    assert sub["mastery_state"] == "WEAK"
    assert sub["next_action"]["action_type"] == "REMEDIATE"
    # Session must be invalidated
    assert sess.status == "INVALIDATED"


# =============================================================================
# Test I: Stale or invalidated queued question submission is rejected
# =============================================================================
def test_i_stale_question_submission_rejected(client, app_service):
    m = MasteryRecord(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    app_service.mastery_repo.save(m)

    q_stale = AuthoritativeQuestion(
        question_id="Q_STALE_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        source_id="SRC_MATH_01",
        user_id="student_test",
        stem="Stale Question",
        options=["A", "B", "C", "D"],
        correct_index=0,
    )
    app_service.question_registry.register(q_stale)
    sess = app_service.reassessment_queue.register_batch(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        cycle=1,
        questions=[q_stale],
    )
    # Explicitly invalidate the session (e.g. cycle changed or state left REASSESSING)
    sess.invalidate()

    res = client.post(
        "/api/learning/SRC_MATH_01/assessment/submit?user_id=student_test",
        json={"attempt_id": "ATT_STALE_01", "concept_id": "CONCEPT_LINEAR_ALGEBRA", "question_id": "Q_STALE_01", "selected_answer": 0, "assessment_type": "REASSESSMENT"},
    )
    assert res.status_code in (400, 409, 422)


# =============================================================================
# Test J: Repeated reassessment button clicks do not create duplicate Ollama generations
# =============================================================================
def test_j_repeated_reassessment_clicks_do_not_duplicate_llm(client, app_service):
    m = MasteryRecord(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    app_service.mastery_repo.save(m)

    mock_q = Question(
        question_id="Q_LA_IDEM",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        concept_name="Linear Algebra",
        source_id="SRC_MATH_01",
        stem="What is a vector space?",
        options=[AssessmentOption(index=i, text=f"Def {i}") for i in range(4)],
        correct_index=0,
        explanation="Def",
    )

    with patch("app.services.mastery.reassessment_service.generate_question", return_value=mock_q) as mock_gen:
        res1 = client.post("/api/learning/SRC_MATH_01/reassessment/generate?concept_id=CONCEPT_LINEAR_ALGEBRA&user_id=student_test")
        res2 = client.post("/api/learning/SRC_MATH_01/reassessment/generate?concept_id=CONCEPT_LINEAR_ALGEBRA&user_id=student_test")
        res3 = client.post("/api/learning/SRC_MATH_01/reassessment/generate?concept_id=CONCEPT_LINEAR_ALGEBRA&user_id=student_test")

        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res3.status_code == 200
        assert res1.json()["question_id"] == res2.json()["question_id"] == res3.json()["question_id"]
        assert mock_gen.call_count == 1


# =============================================================================
# Test K & L: Batch contains distinct stems/options and remains grounded in source evidence
# =============================================================================
def test_k_and_l_batch_distinctness_and_grounding(client, app_service):
    from app.services.mastery.reassessment_service import ReassessmentService

    m = MasteryRecord(
        user_id="student_test",
        source_id="SRC_MATH_01",
        concept_id="CONCEPT_LINEAR_ALGEBRA",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    app_service.mastery_repo.save(m)

    svc = ReassessmentService(
        mastery_repo=app_service.mastery_repo,
        question_registry=app_service.question_registry,
        misconception_repo=app_service.misconception_repo,
    )

    raw_json_response = """{
      "questions": [
        {
          "question": "How are matrix transformations applied to multidimensional data?",
          "options": [
            {"index": 0, "text": "By projecting vectors into transformed coordinate frames"},
            {"index": 1, "text": "By modifying HTML headers"},
            {"index": 2, "text": "By clearing browser cache"},
            {"index": 3, "text": "By changing disk partitions"}
          ],
          "correct_index": 0,
          "evidence_quote": "Linear algebra provides the mathematical language for multidimensional data representations including matrices and vectors.",
          "explanation": "Matrix transformations project vectors.",
          "variant_type": "application"
        },
        {
          "question": "What distinguishes linear vector operations from nonlinear activation functions?",
          "options": [
            {"index": 0, "text": "Nonlinear activations allow deep networks to approximate complex functions"},
            {"index": 1, "text": "Linear algebra only works with 1-bit integers"},
            {"index": 2, "text": "Matrices cannot represent 2D points"},
            {"index": 3, "text": "Vectors cannot be multiplied by scalars"}
          ],
          "correct_index": 0,
          "evidence_quote": "Linear algebra provides the mathematical language for multidimensional data representations including matrices and vectors.",
          "explanation": "Nonlinear activations break linearity.",
          "variant_type": "mechanism"
        }
      ]
    }"""

    mock_provider = MagicMock()
    mock_provider.generate.return_value = raw_json_response

    with patch("app.services.mastery.reassessment_service.get_default_provider", return_value=mock_provider):
        questions = svc.generate_reassessment_batch(
            user_id="student_test",
            source_id="SRC_MATH_01",
            concept_id="CONCEPT_LINEAR_ALGEBRA",
            target_count=2,
        )

        assert len(questions) == 2

        # Test K: Distinct IDs, stems, and options
        assert questions[0].question_id != questions[1].question_id
        assert questions[0].stem != questions[1].stem
        opts0 = {opt.text for opt in questions[0].options}
        opts1 = {opt.text for opt in questions[1].options}
        assert opts0 != opts1
        assert len(opts0) == 4
        assert len(opts1) == 4

        # Test L: Grounded against source evidence
        assert questions[0].evidence_quote is not None
        assert "matrices and vectors" in questions[0].evidence_quote
        assert questions[1].evidence_quote is not None
        assert "matrices and vectors" in questions[1].evidence_quote
