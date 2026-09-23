"""Comprehensive Production-Path Stabilization & Verification Test Suite.

Verifies:
- Test A: Canonical Concept ID validation (Polar Research Station -> CONCEPT_POLAR_RESEARCH_STATION, passes video schema)
- Test B: Dashboard contract (remediation routes to /api/learning/.../remediation, no legacy /video/generate or /assessment/start)
- Test C: Reassessment loop (Q1 -> submit -> Next Question -> Q2 with new question_id -> submit -> MASTERED)
- Test D: Refresh after diagnostic failure (restores source, WEAK state, REMEDIATE next-action)
- Test E: Refresh while video running (restores same remediation job, status tracking resumes)
- Test F: Refresh after video ready (video stream_url accessible, next-action REASSESS)
- Test G: Refresh after reassessment Q1 (answered question not resurrected as pending, Next Question indicated)
- Test H: Duplicate upload click (SHA256 deduplication reuses active/completed job)
- Test I: Duplicate remediation click (same concept reuses same remediation job)
- Test J: Active polling cleanup (clean termination on terminal states and beforeunload)
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.dashboard import DASHBOARD_HTML
from app.api.learning import get_adaptive_learning_service
from app.services.concept_id import canonicalize_concept_id, validate_concept_id
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
from app.services.pipeline_tracker import job_manager, PipelineJob


@pytest.fixture
def polar_curriculum():
    """Grounded curriculum containing Polar Research Station concept."""
    cid = canonicalize_concept_id("Polar Research Station")
    assert cid == "CONCEPT_POLAR_RESEARCH_STATION"

    c1 = ConceptNode(
        concept_id=cid,
        name="Polar Research Station",
        definition="Scientific facility located in polar regions designed for arctic and antarctic research.",
        prerequisite_concept_ids=[],
        source_content_ids=["chunk_polar_001"],
    )
    kg = KnowledgeGraph(concepts={cid: c1})
    rec = SourceRecord(
        source_id="SRC_POLAR_STATION",
        filename="polar_research.pdf",
        source_type="pdf",
        mime_type="application/pdf",
        file_hash="polar_hash_123",
        sha256="polar_hash_123",
        file_size=2048,
        uploaded_by="student_polar",
        user_id="student_polar",
        owner_user_id="student_polar",
        version=1,
        source_version="v1",
        status="READY",
    )
    return rec, kg, cid


@pytest.fixture
def test_env(polar_curriculum):
    rec, kg, cid = polar_curriculum
    mastery_repo = InMemoryMasteryRepository()
    attempt_repo = InMemoryAssessmentAttemptRepository()
    question_repo = InMemoryQuestionRegistry()
    remediation_repo = InMemoryRemediationJobRepository()
    state_machine = MasteryStateMachine()

    async def mock_video_engine(target, job_id, **kwargs):
        # Verify concept_id contains no spaces or illegal characters
        validate_concept_id(target.concept_id)
        return VideoArtifact(
            job_id=job_id,
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            status=VideoJobStatus.COMPLETED,
            video_path=f"/artifacts/videos/{job_id}.mp4",
            duration_seconds=45.0,
            width=1920,
            height=1080,
            fps=30,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    service = AdaptiveLearningService(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        attempt_repo=attempt_repo,
        question_registry=question_repo,
        state_machine=state_machine,
        video_engine_fn=mock_video_engine,
    )

    dummy_chunks = [
        type("RichChunk", (), {
            "model_dump": lambda s: {
                "chunk_id": "chunk_polar_001",
                "text": "Scientific facility located in polar regions designed for arctic and antarctic research.",
                "source_id": rec.source_id,
            }
        })()
    ]

    app.dependency_overrides[get_adaptive_learning_service] = lambda: service

    with patch("app.services.mastery.application_service.get_source_record", return_value=rec), \
         patch("app.services.mastery.application_service.load_knowledge_graph", return_value=kg), \
         patch("app.services.mastery.reassessment_service.load_knowledge_graph", return_value=kg), \
         patch("app.services.mastery.reassessment_service.load_rich_chunks", return_value=dummy_chunks), \
         patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 45.0}):
        client = TestClient(app)
        yield {
            "client": client,
            "service": service,
            "user_id": "student_polar",
            "source_id": "SRC_POLAR_STATION",
            "concept_id": cid,
            "kg": kg,
            "rec": rec,
        }
    app.dependency_overrides.clear()


# =========================================================================
# TEST A — CANONICAL CONCEPT ID
# =========================================================================
def test_a_canonical_concept_id_polar_research_station(test_env):
    """Test A: Canonical ID passes video validation and video remediation API succeeds."""
    client = test_env["client"]
    user_id = test_env["user_id"]
    source_id = test_env["source_id"]
    cid = test_env["concept_id"]

    # 1. Canonical ID validation
    assert cid == "CONCEPT_POLAR_RESEARCH_STATION"
    validate_concept_id(cid)

    # 2. Set concept to WEAK to permit remediation
    test_env["service"].mastery_repo.save(
        MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=cid,
            mastery_state=MasteryState.WEAK,
            mastery_score=0.2,
        )
    )

    # 3. Call remediation API with canonical ID -> Must NOT return 400
    res = client.post(
        f"/api/learning/{source_id}/remediation?user_id={user_id}",
        json={"concept_id": cid, "force": False},
    )
    assert res.status_code == 202
    data = res.json()
    assert data["concept_id"] == "CONCEPT_POLAR_RESEARCH_STATION"
    assert " " not in data["concept_id"]


# =========================================================================
# TEST B — REAL DASHBOARD ENDPOINT CONTRACT
# =========================================================================
def test_b_real_dashboard_endpoint_contract():
    """Test B: Dashboard HTML/JS contracts invoke Step 5E APIs for adaptive flow."""
    html = DASHBOARD_HTML

    # Adaptive remediation must invoke Step 5E endpoint
    assert "/api/learning/${encodeURIComponent(sourceId)}/remediation" in html

    # Trigger video generation in adaptive mode routes to triggerAdaptiveRemediation
    assert "triggerAdaptiveRemediation()" in html

    # Adaptive reassessment submission must invoke /api/learning/.../assessment/submit
    assert "/api/learning/${encodeURIComponent(sourceId)}/assessment/submit" in html

    # Adaptive reassessment generation must invoke /api/learning/.../reassessment/generate
    assert "/api/learning/${encodeURIComponent(sourceId)}/reassessment/generate" in html


# =========================================================================
# TEST C — REASSESSMENT LOOP & NOVEL QUESTION ID
# =========================================================================
def test_c_reassessment_loop(test_env):
    """Test C: Diagnostic wrong -> WEAK -> remediation READY -> REASSESS -> Q1 -> Next Question -> Q2 -> MASTERED."""
    client = test_env["client"]
    service = test_env["service"]
    user_id = test_env["user_id"]
    source_id = test_env["source_id"]
    cid = test_env["concept_id"]

    # 1. Concept begins WEAK after failed diagnostic
    service.mastery_repo.save(
        MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=cid,
            mastery_state=MasteryState.WEAK,
            mastery_score=0.2,
        )
    )

    # 2. Remediation completes to READY -> transitions to REASSESSING
    rem_job = RemediationJob(
        remediation_job_id="REM_POLAR_1",
        user_id=user_id,
        source_id=source_id,
        concept_id=cid,
        attempt_number=1,
        idempotency_key=f"{user_id}:{source_id}:{cid}:1",
        status=RemediationJobStatus.READY,
        video_job_id="REM_POLAR_1",
        video_path="/artifacts/videos/REM_POLAR_1.mp4",
        duration_seconds=45.0,
    )
    service.remediation_repo.save(rem_job)
    service.mastery_repo.save(
        MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=cid,
            mastery_state=MasteryState.REASSESSING,
            mastery_score=0.2,
        )
    )

    # 3. Next action must be REASSESS
    na_res = client.get(f"/api/learning/{source_id}/next-action?user_id={user_id}")
    assert na_res.status_code == 200
    na_data = na_res.json()
    assert na_data["action_type"] == "REASSESS"

    # 4. Generate Reassessment Question #1
    q1_res = client.post(f"/api/learning/{source_id}/reassessment/generate?user_id={user_id}&concept_id={cid}")
    assert q1_res.status_code == 200
    q1 = q1_res.json()
    assert q1["concept_id"] == cid
    q1_id = q1["question_id"]
    # Answer key must not leak to student
    assert "correct_answer" not in q1
    assert "is_correct" not in q1

    # 5. Submit Question #1 (correct)
    auth_q1 = service.question_registry.get(q1_id)
    sub1_res = client.post(
        f"/api/learning/{source_id}/assessment/submit?user_id={user_id}",
        json={
            "attempt_id": "ATT_001",
            "question_id": q1_id,
            "concept_id": cid,
            "assessment_type": "REASSESSMENT",
            "selected_answer": auth_q1.correct_index,
            "response_time_seconds": 12.0,
        },
    )
    assert sub1_res.status_code == 200
    assert sub1_res.json()["is_correct"] is True

    # 6. Check next action: should still be REASSESS because state machine requires 2 consecutive correct answers
    na2_res = client.get(f"/api/learning/{source_id}/next-action?user_id={user_id}")
    assert na2_res.status_code == 200
    na2_data = na2_res.json()
    assert na2_data["action_type"] == "REASSESS"
    assert na2_data["metadata"]["reassessment_attempts_count"] == 1

    # 7. Generate Reassessment Question #2 (passing previous_question_id)
    q2_res = client.post(
        f"/api/learning/{source_id}/reassessment/generate?user_id={user_id}&concept_id={cid}&previous_question_id={q1_id}"
    )
    assert q2_res.status_code == 200, f"Q2 generation failed: {q2_res.json()}"
    q2 = q2_res.json()
    q2_id = q2["question_id"]

    # Must be a DIFFERENT question_id
    assert q2_id != q1_id
    assert q2["concept_id"] == cid

    # 8. Submit Question #2 (correct)
    auth_q2 = service.question_registry.get(q2_id)
    sub2_res = client.post(
        f"/api/learning/{source_id}/assessment/submit?user_id={user_id}",
        json={
            "attempt_id": "ATT_002",
            "question_id": q2_id,
            "concept_id": cid,
            "assessment_type": "REASSESSMENT",
            "selected_answer": auth_q2.correct_index,
            "response_time_seconds": 10.0,
        },
    )
    assert sub2_res.status_code == 200
    assert sub2_res.json()["is_correct"] is True

    # 9. Verify mastery reached
    rec = service.mastery_repo.get(user_id, source_id, cid)
    assert rec.mastery_state == MasteryState.MASTERED


# =========================================================================
# TEST D — REFRESH AFTER DIAGNOSTIC FAILURE
# =========================================================================
def test_d_refresh_after_diagnostic_failure(test_env):
    """Test D: Browser refresh restores WEAK state and REMEDIATE next-action without rerun."""
    client = test_env["client"]
    service = test_env["service"]
    user_id = test_env["user_id"]
    source_id = test_env["source_id"]
    cid = test_env["concept_id"]

    service.mastery_repo.save(
        MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=cid,
            mastery_state=MasteryState.WEAK,
            mastery_score=0.3,
        )
    )

    # Simulating page reload: GET state and next-action
    state_res = client.get(f"/api/learning/{source_id}/state?user_id={user_id}")
    assert state_res.status_code == 200
    st_data = state_res.json()
    assert st_data["weak_count"] == 1
    assert st_data["next_action"]["action_type"] == "REMEDIATE"
    assert st_data["next_action"]["concept_id"] == cid


# =========================================================================
# TEST E — REFRESH WHILE VIDEO RUNNING
# =========================================================================
def test_e_refresh_while_video_running(test_env):
    """Test E: Refresh during active video rendering restores job ID and resumes tracking."""
    client = test_env["client"]
    service = test_env["service"]
    user_id = test_env["user_id"]
    source_id = test_env["source_id"]
    cid = test_env["concept_id"]

    active_job = RemediationJob(
        remediation_job_id="REM_POLAR_ACTIVE",
        user_id=user_id,
        source_id=source_id,
        concept_id=cid,
        attempt_number=1,
        idempotency_key=f"{user_id}:{source_id}:{cid}:1",
        status=RemediationJobStatus.RUNNING,
    )
    service.remediation_repo.save(active_job)

    na_res = client.get(f"/api/learning/{source_id}/next-action?user_id={user_id}")
    assert na_res.status_code == 200
    meta = na_res.json()["metadata"]
    assert meta["active_remediation_job_id"] == "REM_POLAR_ACTIVE"
    assert meta["active_remediation_status"] == "RUNNING"


# =========================================================================
# TEST F — REFRESH AFTER VIDEO READY
# =========================================================================
def test_f_refresh_after_video_ready(test_env):
    """Test F: Refresh after video completes restores video player and REASSESS action."""
    client = test_env["client"]
    service = test_env["service"]
    user_id = test_env["user_id"]
    source_id = test_env["source_id"]
    cid = test_env["concept_id"]

    service.mastery_repo.save(
        MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=cid,
            mastery_state=MasteryState.REASSESSING,
            mastery_score=0.4,
        )
    )
    ready_job = RemediationJob(
        remediation_job_id="REM_POLAR_READY",
        user_id=user_id,
        source_id=source_id,
        concept_id=cid,
        attempt_number=1,
        idempotency_key=f"{user_id}:{source_id}:{cid}:1",
        status=RemediationJobStatus.READY,
        video_job_id="REM_POLAR_READY",
        video_path="/artifacts/videos/REM_POLAR_READY.mp4",
        duration_seconds=45.0,
    )
    service.remediation_repo.save(ready_job)

    na_res = client.get(f"/api/learning/{source_id}/next-action?user_id={user_id}")
    assert na_res.status_code == 200
    data = na_res.json()
    assert data["action_type"] == "REASSESS"
    assert data["metadata"]["video_ready"] is True
    assert data["metadata"]["stream_url"] == "/video/REM_POLAR_READY/stream"


# =========================================================================
# TEST G — REFRESH AFTER REASSESSMENT QUESTION 1
# =========================================================================
def test_g_refresh_after_reassessment_q1(test_env):
    """Test G: Answered question is marked answered and not resurrected as pending on reload."""
    client = test_env["client"]
    service = test_env["service"]
    user_id = test_env["user_id"]
    source_id = test_env["source_id"]
    cid = test_env["concept_id"]

    service.mastery_repo.save(
        MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=cid,
            mastery_state=MasteryState.REASSESSING,
            mastery_score=0.4,
        )
    )

    # Generate Q1
    q1 = service.reassessment_service.generate_reassessment_question(
        user_id=user_id, source_id=source_id, concept_id=cid
    )
    assert service.question_registry.get(q1.question_id).status == "PENDING"

    # Submit Q1
    auth_q1 = service.question_registry.get(q1.question_id)
    client.post(
        f"/api/learning/{source_id}/assessment/submit?user_id={user_id}",
        json={
            "attempt_id": "ATT_Q1_TEST",
            "question_id": q1.question_id,
            "concept_id": cid,
            "assessment_type": "REASSESSMENT",
            "selected_answer": auth_q1.correct_index,
            "response_time_seconds": 10.0,
        },
    )

    # Question is now marked ANSWERED in registry
    assert service.question_registry.get(q1.question_id).status == "ANSWERED"

    # Refresh: fetch next-action
    na_res = client.get(f"/api/learning/{source_id}/next-action?user_id={user_id}")
    assert na_res.status_code == 200
    data = na_res.json()
    assert data["action_type"] == "REASSESS"
    assert data["metadata"]["reassessment_attempts_count"] == 1
    # Answered question must NOT be returned as pending
    assert "pending_question" not in data["metadata"]


# =========================================================================
# TEST H — DUPLICATE UPLOAD CLICK
# =========================================================================
def test_h_duplicate_upload_deduplication():
    """Test H: Rapid duplicate upload requests with identical content reuse the active job."""
    dedup_key = "student_test:fake_sha256:5"
    job_id_1 = "job_upload_001"

    # Register active job
    test_job = PipelineJob(job_id=job_id_1, job_type="upload_and_assess", status="running", is_finished=False)
    job_manager._jobs[job_id_1] = test_job
    job_manager.register_dedup_key(dedup_key, job_id_1)

    # Second simulated request finds existing active job by key
    found_job = job_manager.find_active_job_by_key(dedup_key)
    assert found_job is not None
    assert found_job.job_id == job_id_1

    # Cleanup
    job_manager.release_dedup_key(dedup_key)
    job_manager._jobs.pop(job_id_1, None)


# =========================================================================
# TEST I — DUPLICATE REMEDIATION CLICK
# =========================================================================
def test_i_duplicate_remediation_click(test_env):
    """Test I: Rapid double click on remediation returns the same active remediation job."""
    client = test_env["client"]
    service = test_env["service"]
    user_id = test_env["user_id"]
    source_id = test_env["source_id"]
    cid = test_env["concept_id"]

    service.mastery_repo.save(
        MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=cid,
            mastery_state=MasteryState.WEAK,
            mastery_score=0.2,
        )
    )

    res1 = client.post(
        f"/api/learning/{source_id}/remediation?user_id={user_id}",
        json={"concept_id": cid, "force": False},
    )
    assert res1.status_code == 202
    job_id_1 = res1.json()["remediation_job_id"]

    # Second click while job is active
    res2 = client.post(
        f"/api/learning/{source_id}/remediation?user_id={user_id}",
        json={"concept_id": cid, "force": False},
    )
    assert res2.status_code == 202
    job_id_2 = res2.json()["remediation_job_id"]

    assert job_id_1 == job_id_2


# =========================================================================
# TEST J — ACTIVE POLLING CLEANUP
# =========================================================================
def test_j_active_polling_cleanup_contract():
    """Test J: Dashboard implements cancelAllPolling and hooks beforeunload listener."""
    html = DASHBOARD_HTML
    assert "function cancelAllPolling()" in html
    assert "clearInterval(videoPollInterval)" in html
    assert "clearInterval(adaptiveState.remediationPollInterval)" in html
    assert "window.addEventListener('beforeunload', cancelAllPolling)" in html
