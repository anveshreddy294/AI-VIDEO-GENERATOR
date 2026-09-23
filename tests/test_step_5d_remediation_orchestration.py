"""Unit and isolation tests for Step 5D: Personalized Remediation Orchestration.

Verifies:
1. Orchestrator initiation from NextLearningAction(REMEDIATE)
2. Direct orchestrator invocation with user_id, source_id, concept_id
3. Duplicate active job prevention (concurrent PENDING/RUNNING reuse)
4. Completed job idempotency key lookup and instant reuse
5. Strict artifact validation before advancing mastery to REASSESSING
6. Mastery state transition to REASSESSING on valid MP4
7. Remediation attempt counter increment on educational progression
8. Infrastructure failure classification on FFmpeg error
9. Infrastructure failure classification on TTS/timeout failure
10. Attempt budget preservation: rollback attempt counter on infrastructure failure
11. State preservation: rollback to WEAK on infrastructure failure so learner can retry
12. Max remediation attempts kill-switch: rejection when attempt_count >= 3
13. Rejection of REMEDIATE on MASTERED concept
14. Rejection of REMEDIATE on NEEDS_SUPPORT concept
15. Grounded VideoTarget creation (concept definition, misconception, question context, chunk provenance)
16. Multi-tenant and source isolation (no cross-user, cross-source job pollution)
"""

from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from unittest.mock import patch
import asyncio

import pytest


def async_test(coro):
    """Run an async test function synchronously using asyncio.run."""
    @wraps(coro)
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper

from app.services.assessment.schemas import VideoTarget
from app.services.mastery import (
    AssessmentAttempt,
    AssessmentType,
    AuthoritativeQuestion,
    ConceptDependencyProvider,
    DomainInvariantViolation,
    InMemoryAssessmentAttemptRepository,
    InMemoryMasteryRepository,
    InMemoryQuestionRegistry,
    InMemoryRemediationJobRepository,
    InvalidStateTransitionError,
    LearningActionType,
    MasteryConfig,
    MasteryRecord,
    MasteryState,
    MasteryStateMachine,
    NextLearningAction,
    ReasonCode,
    RemediationJob,
    RemediationJobStatus,
    RemediationOrchestrator,
)
from app.services.schemas import ConceptNode, KnowledgeGraph
from app.services.video.scene_schema import VideoArtifact, VideoJobStatus


@pytest.fixture
def mastery_repo() -> InMemoryMasteryRepository:
    return InMemoryMasteryRepository()


@pytest.fixture
def remediation_repo() -> InMemoryRemediationJobRepository:
    return InMemoryRemediationJobRepository()


@pytest.fixture
def attempt_repo() -> InMemoryAssessmentAttemptRepository:
    return InMemoryAssessmentAttemptRepository()


@pytest.fixture
def question_registry() -> InMemoryQuestionRegistry:
    return InMemoryQuestionRegistry()


@pytest.fixture
def state_machine() -> MasteryStateMachine:
    return MasteryStateMachine(MasteryConfig(max_remediation_attempts=3))


@pytest.fixture
def sample_kg() -> KnowledgeGraph:
    return KnowledgeGraph(
        concepts={
            "C_A": ConceptNode(
                concept_id="C_A",
                name="Mass and Force",
                definition="Fundamental definitions of mass and force.",
                prerequisite_concept_ids=[],
                difficulty="foundational",
            ),
            "C_B": ConceptNode(
                concept_id="C_B",
                name="Newton's Second Law",
                definition="F = ma relating net force, mass, and acceleration.",
                prerequisite_concept_ids=["C_A"],
                difficulty="intermediate",
            ),
        }
    )


@pytest.fixture
def dependency_provider(sample_kg: KnowledgeGraph) -> ConceptDependencyProvider:
    return ConceptDependencyProvider.from_knowledge_graph(sample_kg)


def create_fake_video_engine(video_file_path: Path, fail_with: Exception | None = None, is_failed_status: bool = False):
    """Factory creating a mock video engine function returning VideoArtifact."""

    async def fake_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        if fail_with:
            raise fail_with
        if is_failed_status:
            return VideoArtifact(
                job_id=job_id or "JOB_1",
                student_id=target.student_id,
                source_id=target.source_id,
                concept_id=target.concept_id,
                concept_name=target.concept_name,
                status=VideoJobStatus.FAILED,
                error="FFmpeg exit code 1: internal rendering failure",
            )
        return VideoArtifact(
            job_id=job_id or "JOB_1",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=float(target.target_seconds),
            status=VideoJobStatus.COMPLETED,
            video_path=str(video_file_path),
        )

    return fake_engine


# 1. Orchestrator initiation from NextLearningAction(REMEDIATE)
@async_test
async def test_orchestrator_initiation_from_next_learning_action(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "valid_remediation.mp4"
    video_file.write_bytes(b"mock mp4 content")

    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    action = NextLearningAction(
        action_type=LearningActionType.REMEDIATE,
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        concept_name="Mass and Force",
        reason_code=ReasonCode.WEAK_CONCEPT_REQUIRES_REMEDIATION,
        explanation="Learner requires visual remediation.",
    )

    fake_engine = create_fake_video_engine(video_file)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job = await orchestrator.execute_remediation(action)

    assert job.status == RemediationJobStatus.READY
    assert job.concept_id == "C_A"
    assert job.attempt_number == 1
    assert job.video_path == str(video_file)

    updated_rec = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated_rec.mastery_state == MasteryState.REASSESSING
    assert updated_rec.remediation_attempt_count == 1


# 2. Direct orchestrator invocation with user_id, source_id, concept_id
@async_test
async def test_direct_orchestrator_invocation(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "direct_call.mp4"
    video_file.write_bytes(b"data")

    rec = MasteryRecord(
        user_id="user_direct",
        source_id="src_direct",
        concept_id="C_B",
        mastery_state=MasteryState.WEAK,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(video_file)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 45.0}):
        job = await orchestrator.execute_remediation(
            action_or_user_id="user_direct",
            source_id="src_direct",
            concept_id="C_B",
        )

    assert job.status == RemediationJobStatus.READY
    assert job.user_id == "user_direct"
    assert job.concept_id == "C_B"


# 3. Duplicate active job prevention (concurrent PENDING/RUNNING reuse)
@async_test
async def test_duplicate_active_job_prevention(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
):
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.REMEDIATING,
        remediation_attempt_count=1,
    )
    mastery_repo.save(rec)

    # Seed an active RUNNING job in repo
    active_job = RemediationJob(
        remediation_job_id="REM_EXISTING_RUNNING",
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        status=RemediationJobStatus.RUNNING,
        attempt_number=1,
        idempotency_key="user_1:src_1:C_A:1",
    )
    remediation_repo.save(active_job)

    # Video engine that would fail if called
    engine_called = False

    async def fail_if_called(target: VideoTarget, **kwargs):
        nonlocal engine_called
        engine_called = True
        raise AssertionError("Video engine should NOT have been called!")

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fail_if_called,
    )

    job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")
    assert not engine_called
    assert job.remediation_job_id == "REM_EXISTING_RUNNING"
    assert job.status == RemediationJobStatus.RUNNING


# 4. Completed job idempotency key lookup and instant reuse
@async_test
async def test_completed_job_idempotent_reuse(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "already_done.mp4"
    video_file.write_bytes(b"existing video content")

    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.REMEDIATING,
        remediation_attempt_count=1,
    )
    mastery_repo.save(rec)

    completed_job = RemediationJob(
        remediation_job_id="REM_COMPLETED",
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        status=RemediationJobStatus.READY,
        attempt_number=1,
        idempotency_key="user_1:src_1:C_A:1",
        video_path=str(video_file),
    )
    remediation_repo.save(completed_job)

    engine_called = False

    async def engine_should_not_run(target, **kwargs):
        nonlocal engine_called
        engine_called = True
        raise RuntimeError("Should not run")

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=engine_should_not_run,
    )

    job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")
    assert not engine_called
    assert job.remediation_job_id == "REM_COMPLETED"
    assert job.status == RemediationJobStatus.READY


# 5. Strict artifact validation before advancing mastery to REASSESSING (missing file)
@async_test
async def test_strict_artifact_validation_missing_file(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    non_existent = tmp_path / "ghost.mp4"

    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(non_existent)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")
    assert job.status == RemediationJobStatus.FAILED
    assert job.is_infrastructure_failure is True

    # Mastery must NOT be advanced to REASSESSING!
    updated_rec = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated_rec.mastery_state != MasteryState.REASSESSING


# 6. Strict artifact validation on zero-byte file
@async_test
async def test_strict_artifact_validation_zero_byte_file(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    zero_byte_file = tmp_path / "zero.mp4"
    zero_byte_file.write_bytes(b"")

    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(zero_byte_file)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")
    assert job.status == RemediationJobStatus.FAILED
    assert job.is_infrastructure_failure is True

    updated_rec = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated_rec.mastery_state != MasteryState.REASSESSING


# 7. Mastery state transition to REASSESSING on valid MP4
@async_test
async def test_mastery_state_transition_on_valid_video(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "valid.mp4"
    video_file.write_bytes(b"valid content")

    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(video_file)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")

    assert job.status == RemediationJobStatus.READY
    updated_rec = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated_rec.mastery_state == MasteryState.REASSESSING


# 8. Remediation attempt counter increment on educational progression
@async_test
async def test_remediation_attempt_counter_increment(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "valid2.mp4"
    video_file.write_bytes(b"valid")

    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=1,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(video_file)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")

    assert job.attempt_number == 2
    updated = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated.remediation_attempt_count == 2
    assert updated.mastery_state == MasteryState.REASSESSING


# 9. Infrastructure failure classification on FFmpeg error
@async_test
async def test_infrastructure_failure_classification_ffmpeg_error(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(tmp_path / "dummy.mp4", is_failed_status=True)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")
    assert job.status == RemediationJobStatus.FAILED
    assert job.is_infrastructure_failure is True
    assert "FFmpeg exit code 1" in (job.failure_message or "")


# 10. Infrastructure failure classification on TTS/timeout failure
@async_test
async def test_infrastructure_failure_classification_tts_timeout(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(
        tmp_path / "dummy.mp4",
        fail_with=TimeoutError("Edge TTS service timed out after 30 seconds"),
    )
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")
    assert job.status == RemediationJobStatus.FAILED
    assert job.is_infrastructure_failure is True
    assert "timed out" in (job.failure_message or "")


# 11. Attempt budget preservation: rollback attempt counter on infrastructure failure
@async_test
async def test_attempt_budget_preservation_on_infrastructure_failure(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    # Learner enters with remediation_attempt_count = 1
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=1,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(
        tmp_path / "dummy.mp4",
        fail_with=RuntimeError("GPU OOM during Manim render"),
    )
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    job = await orchestrator.execute_remediation("user_1", "src_1", "C_A")
    assert job.status == RemediationJobStatus.FAILED
    assert job.is_infrastructure_failure is True

    # Critical: learner's attempt count must STILL be 1 (NOT 2)
    updated = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated.remediation_attempt_count == 1


# 12. State preservation: rollback to WEAK on infrastructure failure so learner can retry
@async_test
async def test_state_preservation_on_infrastructure_failure(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(
        tmp_path / "dummy.mp4",
        fail_with=OSError("Disk full"),
    )
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    await orchestrator.execute_remediation("user_1", "src_1", "C_A")

    # State must be WEAK so the learner can retry
    updated = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated.mastery_state == MasteryState.WEAK


# 13. Max remediation attempts kill-switch: rejection when attempt_count >= 3
@async_test
async def test_max_remediation_attempts_kill_switch(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    # Learner has exhausted 3 remediation attempts
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=3,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(tmp_path / "video.mp4")
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with pytest.raises(InvalidStateTransitionError, match="Maximum remediation attempts"):
        await orchestrator.execute_remediation("user_1", "src_1", "C_A")

    updated = mastery_repo.get("user_1", "src_1", "C_A")
    assert updated.mastery_state == MasteryState.NEEDS_SUPPORT


# 14. Rejection of REMEDIATE on MASTERED concept
@async_test
async def test_rejection_of_remediate_on_mastered_concept(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.MASTERED,
        mastery_score=100.0,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(tmp_path / "video.mp4")
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with pytest.raises(InvalidStateTransitionError, match="MASTERED"):
        await orchestrator.execute_remediation("user_1", "src_1", "C_A")


# 15. Rejection of REMEDIATE on NEEDS_SUPPORT concept
@async_test
async def test_rejection_of_remediate_on_needs_support_concept(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_A",
        mastery_state=MasteryState.NEEDS_SUPPORT,
        remediation_attempt_count=3,
    )
    mastery_repo.save(rec)

    fake_engine = create_fake_video_engine(tmp_path / "video.mp4")
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with pytest.raises(InvalidStateTransitionError, match="NEEDS_SUPPORT"):
        await orchestrator.execute_remediation("user_1", "src_1", "C_A")


# 16. Grounded VideoTarget creation (concept definition, misconception, question context)
@async_test
async def test_grounded_video_target_creation(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    attempt_repo: InMemoryAssessmentAttemptRepository,
    question_registry: InMemoryQuestionRegistry,
    sample_kg: KnowledgeGraph,
    dependency_provider: ConceptDependencyProvider,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "grounded.mp4"
    video_file.write_bytes(b"vid")

    # Seed authoritative question
    q = AuthoritativeQuestion(
        question_id="Q_101",
        concept_id="C_B",
        source_id="src_1",
        stem="What is Newton's Second Law formula?",
        options=["F = m/a", "F = ma", "F = m + a", "F = a/m"],
        correct_index=1,
        explanation="F = ma relates force directly to mass and acceleration.",
    )
    question_registry.register(q)

    # Seed failed attempt
    att = AssessmentAttempt(
        attempt_id="ATT_101",
        user_id="user_1",
        source_id="src_1",
        concept_id="C_B",
        question_id="Q_101",
        selected_answer=0,  # Incorrect!
        correct_answer=1,
        is_correct=False,
        assessment_type=AssessmentType.DIAGNOSTIC,
    )
    attempt_repo.save(att)

    rec = MasteryRecord(
        user_id="user_1",
        source_id="src_1",
        concept_id="C_B",
        mastery_state=MasteryState.WEAK,
    )
    mastery_repo.save(rec)

    captured_target: VideoTarget | None = None

    async def capturing_engine(target: VideoTarget, **kwargs):
        nonlocal captured_target
        captured_target = target
        return VideoArtifact(
            job_id="JOB_CAPTURED",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            duration_seconds=float(target.target_seconds),
            status=VideoJobStatus.COMPLETED,
            video_path=str(video_file),
        )

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        attempt_repo=attempt_repo,
        question_registry=question_registry,
        state_machine=state_machine,
        video_engine_fn=capturing_engine,
        knowledge_graph=sample_kg,
        dependency_provider=dependency_provider,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 45.0}):
        await orchestrator.execute_remediation("user_1", "src_1", "C_B")

    assert captured_target is not None
    assert captured_target.concept_id == "C_B"
    assert captured_target.concept_name == "Newton's Second Law"
    assert captured_target.question_id == "Q_101"
    assert captured_target.selected_index == 0
    assert captured_target.correct_index == 1
    assert "F = ma relates force" in captured_target.explanation
    assert "selected option 0 instead of correct option 1" in captured_target.misconception
    assert "C_A" in captured_target.prerequisite_concept_ids


# 17. Multi-tenant and source isolation (no cross-user, cross-source pollution)
@async_test
async def test_multi_tenant_and_source_isolation(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_u1 = tmp_path / "u1.mp4"
    video_u1.write_bytes(b"u1")
    video_u2 = tmp_path / "u2.mp4"
    video_u2.write_bytes(b"u2")

    # Two different users with identical concept
    rec1 = MasteryRecord(user_id="user_A", source_id="src_1", concept_id="C_A", mastery_state=MasteryState.WEAK)
    rec2 = MasteryRecord(user_id="user_B", source_id="src_1", concept_id="C_A", mastery_state=MasteryState.WEAK)
    mastery_repo.save(rec1)
    mastery_repo.save(rec2)

    fake_engine = create_fake_video_engine(video_u1)
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=fake_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job_a = await orchestrator.execute_remediation("user_A", "src_1", "C_A")

    # user_A's job should be READY
    assert job_a.user_id == "user_A"
    assert job_a.status == RemediationJobStatus.READY

    # user_B's record must still be in WEAK (unaffected by user_A)
    rec_b = mastery_repo.get("user_B", "src_1", "C_A")
    assert rec_b.mastery_state == MasteryState.WEAK
    assert rec_b.remediation_attempt_count == 0

    # user_B's jobs in repo must be empty
    jobs_b = remediation_repo.list_for_concept("user_B", "src_1", "C_A")
    assert len(jobs_b) == 0


# 18. Real Concurrency Test with asyncio.gather (Simultaneous Calls)
@async_test
async def test_real_concurrency_simultaneous_calls(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "concurrent.mp4"
    video_file.write_bytes(b"concurrent bytes")

    rec = MasteryRecord(
        user_id="user_conc",
        source_id="src_conc",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    call_count = 0

    async def slow_video_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # Simulate non-zero rendering time
        return VideoArtifact(
            job_id=job_id or "JOB_CONC",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=float(target.target_seconds),
            status=VideoJobStatus.COMPLETED,
            video_path=str(video_file),
        )

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=slow_video_engine,
    )

    action = NextLearningAction(
        action_type=LearningActionType.REMEDIATE,
        user_id="user_conc",
        source_id="src_conc",
        concept_id="C_A",
        reason_code=ReasonCode.WEAK_CONCEPT_REQUIRES_REMEDIATION,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job1, job2 = await asyncio.gather(
            orchestrator.execute_remediation(action, wait_for_completion=True),
            orchestrator.execute_remediation(action, wait_for_completion=True),
        )

    # 1. Exactly one logical RemediationJob
    all_jobs = remediation_repo.list_for_concept("user_conc", "src_conc", "C_A")
    assert len(all_jobs) == 1

    # 2. Both callers receive the exact same job ID
    assert job1.remediation_job_id == job2.remediation_job_id
    assert job1.status == RemediationJobStatus.READY
    assert job2.status == RemediationJobStatus.READY

    # 3. Exactly one video engine invocation
    assert call_count == 1

    # 4. Exactly one educational attempt increment
    updated_rec = mastery_repo.get("user_conc", "src_conc", "C_A")
    assert updated_rec.remediation_attempt_count == 1
    assert updated_rec.mastery_state == MasteryState.REASSESSING


# 19. Active job reuse while RUNNING (Non-waiting caller)
@async_test
async def test_active_job_reuse_while_running(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_file = tmp_path / "active_reuse.mp4"
    video_file.write_bytes(b"content")

    rec = MasteryRecord(
        user_id="user_active",
        source_id="src_active",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    engine_started = asyncio.Event()
    engine_finish = asyncio.Event()
    engine_calls = 0

    async def controlled_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        nonlocal engine_calls
        engine_calls += 1
        engine_started.set()
        await engine_finish.wait()
        return VideoArtifact(
            job_id=job_id or "JOB_ACT",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=float(target.target_seconds),
            status=VideoJobStatus.COMPLETED,
            video_path=str(video_file),
        )

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=controlled_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        # Start Task 1 in background
        task1 = asyncio.create_task(
            orchestrator.execute_remediation("user_active", "src_active", "C_A", wait_for_completion=False)
        )
        await engine_started.wait()

        # Task 2 arrives while Task 1 is actively RUNNING
        job2 = await orchestrator.execute_remediation("user_active", "src_active", "C_A", wait_for_completion=False)

        # Release Task 1
        engine_finish.set()
        job1 = await task1

    assert job1.remediation_job_id == job2.remediation_job_id
    assert job2.status == RemediationJobStatus.RUNNING
    assert job1.status == RemediationJobStatus.READY
    assert engine_calls == 1
    assert len(remediation_repo.list_for_concept("user_active", "src_active", "C_A")) == 1


# 20. New Educational Cycle: Cycle 1 Job != Cycle 2 Job
@async_test
async def test_new_educational_cycle_creates_distinct_job(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video1 = tmp_path / "vid1.mp4"
    video1.write_bytes(b"vid1")
    video2 = tmp_path / "vid2.mp4"
    video2.write_bytes(b"vid2")

    rec = MasteryRecord(
        user_id="user_cycle",
        source_id="src_cycle",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    call_num = 0

    async def cycle_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        nonlocal call_num
        call_num += 1
        vpath = video1 if call_num == 1 else video2
        return VideoArtifact(
            job_id=job_id or f"JOB_CYCLE_{call_num}",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=float(target.target_seconds),
            status=VideoJobStatus.COMPLETED,
            video_path=str(vpath),
        )

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=cycle_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        # === Educational Cycle 1 ===
        job_c1 = await orchestrator.execute_remediation("user_cycle", "src_cycle", "C_A")
        assert job_c1.attempt_number == 1
        assert job_c1.status == RemediationJobStatus.READY

        # Duplicate call inside Cycle 1 reuses Cycle 1 job
        dup_c1 = await orchestrator.execute_remediation("user_cycle", "src_cycle", "C_A")
        assert dup_c1.remediation_job_id == job_c1.remediation_job_id
        assert dup_c1.attempt_number == 1

        # Learner takes reassessment and FAILS -> State machine transitions REASSESSING -> WEAK
        rec_after_c1 = mastery_repo.get("user_cycle", "src_cycle", "C_A")
        assert rec_after_c1.mastery_state == MasteryState.REASSESSING
        assert rec_after_c1.remediation_attempt_count == 1

        # Simulate failed reassessment transitioning state back to WEAK
        state_machine.transition_to(rec_after_c1, MasteryState.WEAK)
        mastery_repo.save(rec_after_c1)

        # === Educational Cycle 2 ===
        job_c2 = await orchestrator.execute_remediation("user_cycle", "src_cycle", "C_A")
        assert job_c2.attempt_number == 2
        assert job_c2.remediation_job_id != job_c1.remediation_job_id

        # Duplicate call inside Cycle 2 reuses Cycle 2 job
        dup_c2 = await orchestrator.execute_remediation("user_cycle", "src_cycle", "C_A")
        assert dup_c2.remediation_job_id == job_c2.remediation_job_id
        assert dup_c2.attempt_number == 2


# 21. Infrastructure Failure + Retry preserves attempt number
@async_test
async def test_infrastructure_failure_and_retry_maintains_attempt_number(
    mastery_repo: InMemoryMasteryRepository,
    remediation_repo: InMemoryRemediationJobRepository,
    state_machine: MasteryStateMachine,
    tmp_path: Path,
):
    video_ok = tmp_path / "ok.mp4"
    video_ok.write_bytes(b"ok")

    rec = MasteryRecord(
        user_id="user_retry",
        source_id="src_retry",
        concept_id="C_A",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)

    should_fail = True

    async def flaky_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        nonlocal should_fail
        if should_fail:
            raise RuntimeError("FFmpeg crashed with exit code 137")
        return VideoArtifact(
            job_id=job_id or "JOB_OK",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=float(target.target_seconds),
            status=VideoJobStatus.COMPLETED,
            video_path=str(video_ok),
        )

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=flaky_engine,
    )

    # 1. Attempt 1 fails due to infrastructure
    job_failed = await orchestrator.execute_remediation("user_retry", "src_retry", "C_A")
    assert job_failed.status == RemediationJobStatus.FAILED
    assert job_failed.is_infrastructure_failure is True
    assert job_failed.attempt_number == 1

    # Check mastery record: attempt counter was restored to 0, state returned to WEAK
    rec_after_fail = mastery_repo.get("user_retry", "src_retry", "C_A")
    assert rec_after_fail.mastery_state == MasteryState.WEAK
    assert rec_after_fail.remediation_attempt_count == 0

    # 2. Learner retries Attempt 1 after infrastructure is restored
    should_fail = False
    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job_retry = await orchestrator.execute_remediation("user_retry", "src_retry", "C_A")

    assert job_retry.status == RemediationJobStatus.READY
    # Crucial: attempt_number is STILL 1, NOT 2!
    assert job_retry.attempt_number == 1

    # Mastery record now has attempt count 1 and is in REASSESSING
    rec_after_retry = mastery_repo.get("user_retry", "src_retry", "C_A")
    assert rec_after_retry.remediation_attempt_count == 1
    assert rec_after_retry.mastery_state == MasteryState.REASSESSING
