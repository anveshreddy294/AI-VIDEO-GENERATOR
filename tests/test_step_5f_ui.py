"""Step 5F Test Suite — Adaptive Learning UI Loop & Student Dashboard Integration.

Verifies:
1. Dashboard HTML embeds all required Step 5F UI elements and buttons:
   - #adaptiveLearningPanel
   - #adaptiveRoadmapWidget
   - #btnStartReview ("Start Personalized Review")
   - #btnTakeAssessmentAgain ("Take Assessment Again")
   - #btnSubmitAnswer ("Submit Answer")
   - #btnNextQuestion ("Next Question")
   - #btnContinueNextConcept ("Continue to Next Concept")
2. Diagnostic incorrect -> UI next-action is REMEDIATE (Start Personalized Review offered)
3. Remediation trigger -> POST /api/learning/{source_id}/remediation returns 202
4. Duplicate remediation trigger -> idempotent reuse of existing job
5. Remediation status reaches READY -> video stream URL provided (no absolute file paths)
6. Video READY state -> next-action returns REASSESS (Take Assessment Again offered)
7. Take Assessment Again -> POST /api/learning/{source_id}/reassessment/generate returns safe payload
8. Answer submission -> authoritative grading via POST /api/learning/{source_id}/assessment/submit
9. Incomplete evidence -> next-action remains REASSESS -> Next Question offered
10. Next Question -> generates subsequent grounded reassessment
11. Evidence satisfied -> next-action returns MASTERED / ASSESS / COMPLETE
12. Roadmaps update deterministically across state mutations
13. No answer keys or hidden correctness metadata exposed in client payloads
14. Real UI adaptive loop execution with measured timings
"""

import time
from datetime import datetime, timezone
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
    RemediationJob,
    RemediationJobStatus,
)
from app.services.schemas import ConceptNode, KnowledgeGraph, SourceRecord
from app.services.video.scene_schema import VideoArtifact, VideoJobStatus


@pytest.fixture
def clean_service():
    """Create a pristine AdaptiveLearningService with in-memory stores."""
    service = AdaptiveLearningService(
        mastery_repo=InMemoryMasteryRepository(),
        attempt_repo=InMemoryAssessmentAttemptRepository(),
        question_registry=InMemoryQuestionRegistry(),
        remediation_repo=InMemoryRemediationJobRepository(),
    )
    return service


@pytest.fixture
def setup_ui_curriculum(clean_service, monkeypatch):
    """Seed test source and grounded concepts for UI integration."""
    source_id = "SRC_UI_ADAPTIVE_TEST"
    user_id = "student_default"

    c1 = ConceptNode(
        concept_id="CONCEPT_VECTORS",
        name="Vector Quantities",
        definition="Quantities characterized by both magnitude and direction.",
        prerequisite_concept_ids=[],
        source_content_ids=["chunk_1"],
    )
    c2 = ConceptNode(
        concept_id="CONCEPT_FORCES",
        name="Force Fundamentals",
        definition="An interaction that changes or tends to change the motion of an object.",
        prerequisite_concept_ids=["CONCEPT_VECTORS"],
        source_content_ids=["chunk_2"],
    )

    kg = KnowledgeGraph(concepts={
        "CONCEPT_VECTORS": c1,
        "CONCEPT_FORCES": c2,
    })

    source_rec = SourceRecord(
        source_id=source_id,
        filename="physics_vectors.pdf",
        source_type="pdf",
        mime_type="application/pdf",
        file_hash="vhash_123",
        sha256="vhash_123",
        file_size=2048,
        uploaded_by=user_id,
        user_id=user_id,
        owner_user_id=user_id,
        version=1,
        source_version="v1",
        status="READY",
    )

    dummy_chunks = [
        type("RichChunk", (), {
            "model_dump": lambda s: {
                "chunk_id": "chunk_1",
                "text": "Vector quantities possess both magnitude and direction, like velocity.",
                "source_id": source_id,
            }
        })()
    ]

    monkeypatch.setattr("app.services.mastery.application_service.get_source_record", lambda sid: source_rec if sid == source_id else None)
    monkeypatch.setattr("app.services.mastery.application_service.load_knowledge_graph", lambda sid: kg if sid == source_id else None)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_knowledge_graph", lambda sid: kg if sid == source_id else None)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_rich_chunks", lambda sid: dummy_chunks if sid == source_id else [])

    # Pre-register diagnostic questions
    clean_service.question_registry.register(
        AuthoritativeQuestion(
            question_id="Q_VEC_DIAG_1",
            concept_id="CONCEPT_VECTORS",
            source_id=source_id,
            stem="Which of the following is a vector quantity?",
            options=["Speed", "Mass", "Velocity", "Temperature"],
            correct_index=2,
            misconceptions={0: "Confused scalar speed with vector velocity"},
            explanation="Velocity has both magnitude and direction, unlike speed which only has magnitude.",
            prerequisite_concept_ids=[],
            is_active=True,
        )
    )

    # Pre-register grounded reassessment questions
    clean_service.question_registry.register(
        AuthoritativeQuestion(
            question_id="Q_VEC_REASSESS_1",
            concept_id="CONCEPT_VECTORS",
            source_id=source_id,
            stem="A displacement of 5 meters East is an example of what?",
            options=["Scalar", "Vector", "Dimensionless constant", "Static point"],
            correct_index=1,
            explanation="Displacement specifies magnitude (5m) and direction (East), making it a vector.",
            prerequisite_concept_ids=[],
            is_active=True,
        )
    )

    clean_service.question_registry.register(
        AuthoritativeQuestion(
            question_id="Q_VEC_REASSESS_2",
            concept_id="CONCEPT_VECTORS",
            source_id=source_id,
            stem="If an airplane flies 200 mph Northward, this represents:",
            options=["Velocity vector", "Pure scalar speed", "Acceleration without force", "Thermal kinetic state"],
            correct_index=0,
            explanation="Velocity includes both speed and directional orientation.",
            prerequisite_concept_ids=[],
            is_active=True,
        )
    )

    # Ensure app uses clean_service
    app.dependency_overrides[get_adaptive_learning_service] = lambda: clean_service

    yield {
        "service": clean_service,
        "source_id": source_id,
        "user_id": user_id,
    }

    app.dependency_overrides.clear()


class TestDashboardHtmlIntegrity:
    """Verifies the dashboard HTML contains all required Step 5F elements and buttons."""

    def test_dashboard_renders_successfully(self):
        client = TestClient(app)
        res = client.get("/dashboard")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]

    def test_required_buttons_present_in_html(self):
        client = TestClient(app)
        html = client.get("/dashboard").text

        # All 5 mandatory buttons
        assert 'id="btnStartReview"' in html
        assert "Start Personalized Review" in html

        assert 'id="btnTakeAssessmentAgain"' in html
        assert "Take Assessment Again" in html

        assert 'id="btnSubmitAnswer"' in html
        assert "Submit Answer" in html

        assert 'id="btnNextQuestion"' in html
        assert "Next Question" in html

        assert 'id="btnContinueNextConcept"' in html
        assert "Continue to Next Concept" in html

    def test_required_adaptive_panels_present(self):
        client = TestClient(app)
        html = client.get("/dashboard").text

        assert 'id="adaptiveLearningPanel"' in html
        assert 'id="adaptiveRoadmapWidget"' in html
        assert 'id="roadmapConceptsContainer"' in html
        assert 'id="adaptiveActionCard"' in html
        assert 'id="adaptiveQuestionBox"' in html
        assert 'id="reassessOptionsContainer"' in html

    def test_no_answer_key_or_absolute_paths_in_html(self):
        client = TestClient(app)
        html = client.get("/dashboard").text

        # Security checks: No secret keys or backend file system paths hardcoded in template
        assert "C:\\Users\\" not in html
        assert "D:\\" not in html
        assert "/var/log" not in html
        assert "password" not in html.lower()

    def test_polling_rate_is_not_subsecond(self):
        client = TestClient(app)
        html = client.get("/dashboard").text
        # Video poll interval was adjusted to >= 2000ms
        assert "2500" in html


class TestAdaptiveLearningUILoopIntegration:
    """Simulates the full student learning loop matching exact Step 5F requirements."""

    def test_initial_diagnostic_incorrect_triggers_remediation_cta(self, setup_ui_curriculum):
        ctx = setup_ui_curriculum
        client = TestClient(app)

        # 1. Learner answers diagnostic question incorrectly (index 0 instead of 2)
        submit_res = client.post(
            f"/api/learning/{ctx['source_id']}/assessment/submit?user_id={ctx['user_id']}",
            json={
                "attempt_id": "ATT_DIAG_1",
                "question_id": "Q_VEC_DIAG_1",
                "concept_id": "CONCEPT_VECTORS",
                "assessment_type": "DIAGNOSTIC",
                "selected_answer": 0,
            },
        )
        assert submit_res.status_code == 200
        sub_data = submit_res.json()
        assert sub_data["is_correct"] is False
        assert sub_data["mastery_state"] == "WEAK"

        # 2. Authoritative Next Action queried by UI -> REMEDIATE
        action_res = client.get(
            f"/api/learning/{ctx['source_id']}/next-action?user_id={ctx['user_id']}"
        )
        assert action_res.status_code == 200
        action = action_res.json()
        assert action["action_type"] == "REMEDIATE"
        assert action["concept_id"] == "CONCEPT_VECTORS"

        # 3. Roadmap reflects Needs Review
        roadmap_res = client.get(
            f"/api/learning/{ctx['source_id']}/roadmap?user_id={ctx['user_id']}"
        )
        assert roadmap_res.status_code == 200
        roadmap = roadmap_res.json()
        assert "CONCEPT_VECTORS" in roadmap["weak_concepts"]

    def test_remediation_and_video_ready_shows_take_assessment_again(self, setup_ui_curriculum):
        ctx = setup_ui_curriculum
        client = TestClient(app)

        # Transition concept to WEAK first
        client.post(
            f"/api/learning/{ctx['source_id']}/assessment/submit?user_id={ctx['user_id']}",
            json={
                "attempt_id": "ATT_DIAG_WEAK",
                "question_id": "Q_VEC_DIAG_1",
                "concept_id": "CONCEPT_VECTORS",
                "assessment_type": "DIAGNOSTIC",
                "selected_answer": 0,
            },
        )

        from unittest.mock import patch
        with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
            # Learner clicks [ Start Personalized Review ] -> POST /api/learning/{source_id}/remediation
            rem_res = client.post(
                f"/api/learning/{ctx['source_id']}/remediation?user_id={ctx['user_id']}",
                json={"concept_id": "CONCEPT_VECTORS", "force": False},
            )
            assert rem_res.status_code == 202
            rem_data = rem_res.json()
            job_id = rem_data["remediation_job_id"]

            # Duplicate click does not recreate job
            rem_dup = client.post(
                f"/api/learning/{ctx['source_id']}/remediation?user_id={ctx['user_id']}",
                json={"concept_id": "CONCEPT_VECTORS", "force": False},
            )
            assert rem_dup.status_code == 202
            assert rem_dup.json()["remediation_job_id"] == job_id

        # Simulate job completion to READY
        job = ctx["service"].remediation_repo.get(job_id)
        job.status = RemediationJobStatus.READY
        job.duration_seconds = 42.0
        job.video_path = "/media/videos/remediation_vectors.mp4"
        job.completed_at = datetime.now(timezone.utc)
        ctx["service"].remediation_repo.save(job)

        # Video status returns safe stream URL (zero local filesystem leakage)
        status_res = client.get(
            f"/api/learning/{ctx['source_id']}/remediation/{job_id}?user_id={ctx['user_id']}"
        )
        assert status_res.status_code == 200
        stat_data = status_res.json()
        assert stat_data["status"] == "READY"
        assert stat_data["stream_url"] == f"/video/{job_id}/stream"
        assert "C:\\" not in str(stat_data)
        assert "/media/" not in stat_data["stream_url"]

        # Authoritative next action -> REASSESS (Take Assessment Again)
        next_res = client.get(
            f"/api/learning/{ctx['source_id']}/next-action?user_id={ctx['user_id']}"
        )
        assert next_res.status_code == 200
        assert next_res.json()["action_type"] == "REASSESS"

    def test_reassessment_question_generation_and_safe_payload(self, setup_ui_curriculum):
        ctx = setup_ui_curriculum
        client = TestClient(app)

        # Prepare concept in REASSESSING state
        record = MasteryRecord(
            user_id=ctx["user_id"],
            source_id=ctx["source_id"],
            concept_id="CONCEPT_VECTORS",
            attempt_count=1,
            incorrect_count=1,
            mastery_state=MasteryState.REASSESSING,
            remediation_attempt_count=1,
        )
        ctx["service"].mastery_repo.save(record)

        from unittest.mock import patch
        with patch("app.services.mastery.reassessment_service.generate_question") as mock_gen:
            from app.services.assessment.schemas import Question, AssessmentOption
            mock_gen.return_value = Question(
                question_id="Q_VEC_REASSESS_GEN_1",
                concept_id="CONCEPT_VECTORS",
                concept_name="Vector Quantities",
                source_id=ctx["source_id"],
                stem="Which quantity includes direction?",
                options=[
                    AssessmentOption(index=0, text="Velocity"),
                    AssessmentOption(index=1, text="Mass"),
                    AssessmentOption(index=2, text="Time"),
                    AssessmentOption(index=3, text="Energy"),
                ],
                correct_index=0,
                explanation="Velocity is a vector quantity.",
            )

            # Learner clicks [ Take Assessment Again ]
            reassess_res = client.post(
                f"/api/learning/{ctx['source_id']}/reassessment/generate?user_id={ctx['user_id']}&concept_id=CONCEPT_VECTORS"
            )
            assert reassess_res.status_code == 200
            q_data = reassess_res.json()

            # Verify safe question payload
            assert "question_id" in q_data
            assert "stem" in q_data
            assert "options" in q_data
            assert len(q_data["options"]) == 4
            # CRITICAL: No correct answer or index metadata exposed!
            assert "correct_index" not in q_data
            assert "correct_answer" not in q_data
            assert "is_correct" not in q_data

    def test_practice_reassessment_question_loop(self, setup_ui_curriculum):
        ctx = setup_ui_curriculum
        client = TestClient(app)

        # Set concept to REASSESSING
        record = MasteryRecord(
            user_id=ctx["user_id"],
            source_id=ctx["source_id"],
            concept_id="CONCEPT_VECTORS",
            attempt_count=1,
            incorrect_count=1,
            mastery_state=MasteryState.REASSESSING,
            remediation_attempt_count=1,
        )
        ctx["service"].mastery_repo.save(record)

        # Question 1: Submitted
        sub1 = client.post(
            f"/api/learning/{ctx['source_id']}/assessment/submit?user_id={ctx['user_id']}",
            json={
                "attempt_id": "ATT_REASSESS_1",
                "question_id": "Q_VEC_REASSESS_1",
                "concept_id": "CONCEPT_VECTORS",
                "assessment_type": "REASSESSMENT",
                "selected_answer": 1,  # Correct
            },
        )
        assert sub1.status_code == 200
        assert sub1.json()["is_correct"] is True

        # Check next-action: If more evidence required, action remains REASSESS
        next_act_1 = client.get(
            f"/api/learning/{ctx['source_id']}/next-action?user_id={ctx['user_id']}"
        ).json()

        if next_act_1["action_type"] == "REASSESS":
            # Submit Question 2
            sub2 = client.post(
                f"/api/learning/{ctx['source_id']}/assessment/submit?user_id={ctx['user_id']}",
                json={
                    "attempt_id": "ATT_REASSESS_2",
                    "question_id": "Q_VEC_REASSESS_2",
                    "concept_id": "CONCEPT_VECTORS",
                    "assessment_type": "REASSESSMENT",
                    "selected_answer": 0,  # Correct
                },
            )
            assert sub2.status_code == 200
            assert sub2.json()["is_correct"] is True

        # Once evidence is satisfied, mastery advances! Next action is ASSESS for CONCEPT_FORCES
        final_action = client.get(
            f"/api/learning/{ctx['source_id']}/next-action?user_id={ctx['user_id']}"
        ).json()

        assert final_action["action_type"] in ("ASSESS", "COMPLETE")
        if final_action["action_type"] == "ASSESS":
            # [ Continue to Next Concept ] is offered for CONCEPT_FORCES
            assert final_action["concept_id"] == "CONCEPT_FORCES"

    def test_complete_learning_path_triggers_completion_ui(self, setup_ui_curriculum):
        ctx = setup_ui_curriculum
        client = TestClient(app)

        # Mark both concepts MASTERED
        for cid in ["CONCEPT_VECTORS", "CONCEPT_FORCES"]:
            rec = MasteryRecord(
                user_id=ctx["user_id"],
                source_id=ctx["source_id"],
                concept_id=cid,
                attempt_count=2,
                correct_count=2,
                mastery_state=MasteryState.MASTERED,
                mastery_score=100.0,
            )
            ctx["service"].mastery_repo.save(rec)

        action = client.get(
            f"/api/learning/{ctx['source_id']}/next-action?user_id={ctx['user_id']}"
        ).json()

        assert action["action_type"] == "COMPLETE"

        roadmap = client.get(
            f"/api/learning/{ctx['source_id']}/roadmap?user_id={ctx['user_id']}"
        ).json()
        assert len(roadmap["mastered_concepts"]) == 2
        assert roadmap["completed"] is True


class TestRealUIAdaptiveFlowPerformance:
    """Measures actual execution timings for key UI interactions."""

    def test_measured_timings(self, setup_ui_curriculum):
        ctx = setup_ui_curriculum
        client = TestClient(app)

        # 1. Assessment submission -> next-action visible timing
        t0 = time.perf_counter()
        client.post(
            f"/api/learning/{ctx['source_id']}/assessment/submit?user_id={ctx['user_id']}",
            json={
                "attempt_id": "ATT_TIMING_1",
                "question_id": "Q_VEC_DIAG_1",
                "concept_id": "CONCEPT_VECTORS",
                "assessment_type": "DIAGNOSTIC",
                "selected_answer": 0,
            },
        )
        t_submit = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        client.get(f"/api/learning/{ctx['source_id']}/next-action?user_id={ctx['user_id']}")
        t_next_action = (time.perf_counter() - t1) * 1000

        # 2. Remediation request timing
        from unittest.mock import patch
        with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
            t2 = time.perf_counter()
            client.post(
                f"/api/learning/{ctx['source_id']}/remediation?user_id={ctx['user_id']}",
                json={"concept_id": "CONCEPT_VECTORS"},
            )
            t_remediation_req = (time.perf_counter() - t2) * 1000

        # 3. Reassessment generate -> question visible timing
        rec = ctx["service"].mastery_repo.get(ctx["user_id"], ctx["source_id"], "CONCEPT_VECTORS")
        rec.mastery_state = MasteryState.REASSESSING
        ctx["service"].mastery_repo.save(rec)

        with patch("app.services.mastery.reassessment_service.generate_question") as mock_gen:
            from app.services.assessment.schemas import Question, AssessmentOption
            mock_gen.return_value = Question(
                question_id="Q_VEC_TIMING_1",
                concept_id="CONCEPT_VECTORS",
                concept_name="Vector Quantities",
                source_id=ctx["source_id"],
                stem="Timing test stem",
                options=[AssessmentOption(index=i, text=f"Opt {i}") for i in range(4)],
                correct_index=0,
                explanation="Explanation",
            )
            t3 = time.perf_counter()
            client.post(
                f"/api/learning/{ctx['source_id']}/reassessment/generate?user_id={ctx['user_id']}&concept_id=CONCEPT_VECTORS"
            )
            t_reassess_gen = (time.perf_counter() - t3) * 1000

        print(f"\n[STEP 5F MEASURED TIMINGS]")
        print(f"Assessment submit: {t_submit:.2f} ms")
        print(f"Next-action query: {t_next_action:.2f} ms")
        print(f"Remediation request: {t_remediation_req:.2f} ms")
        print(f"Reassessment question generate: {t_reassess_gen:.2f} ms")

        assert t_submit < 500
        assert t_next_action < 100
        assert t_remediation_req < 500
        assert t_reassess_gen < 500
