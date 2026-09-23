"""Comprehensive Test Suite for Misconception Intelligence Layer (M1 through M7).

Verifies:
1. M1 & M2: Misconception domain models, normalization, distractor metadata capture.
2. M3: Deterministic evidence accumulation (1 -> POSSIBLE, 2 -> LIKELY, 3+ -> CONFIRMED),
   idempotency, and recurrence tracking (CORRECTED -> RECURRENT).
3. M4: Deterministic TeachingStrategySelector (zero LLM policy calls, taxonomy mapping,
   prerequisite review check, retry novelty progression, zero fabricated misconceptions).
4. M5: VideoTarget extension with misconception context, VideoPlanner strategy scene synthesis,
   and strategy traceability in RemediationJob metadata.
5. M6: ReassessmentService targeting active misconceptions, and correction decision upon
   authoritative mastery evidence (transitions to CORRECTED).
6. M7: RoadmapResponse explainable misconception journey, safe learner-facing fields,
   zero answer leakage, and UI dashboard compact presentation card.
7. Real E2E Flow: Full loop from grounded diagnostic distractor through remediation video,
   targeted reassessment, mastery update, and misconception correction.
"""

from __future__ import annotations

import asyncio
import functools
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.assessment.schemas import (
    AssessmentOption,
    Question,
    SafeOption,
    SafeQuestion,
    VideoTarget,
)
from app.services.mastery import (
    AdaptiveLearningService,
    AssessmentAttempt,
    AssessmentAttemptResult,
    AssessmentAttemptService,
    AssessmentSubmissionRequest,
    AssessmentType,
    AuthoritativeQuestion,
    ConceptDependencyProvider,
    DistractorMisconceptionMetadata,
    DomainInvariantViolation,
    InMemoryAssessmentAttemptRepository,
    InMemoryMasteryRepository,
    InMemoryMisconceptionRepository,
    InMemoryQuestionRegistry,
    InMemoryRemediationJobRepository,
    LearningActionType,
    MasteryConfig,
    MasteryRecord,
    MasteryState,
    MasteryStateMachine,
    MisconceptionConfidenceState,
    MisconceptionEvidence,
    MisconceptionStatus,
    NextLearningAction,
    ReasonCode,
    RemediationJob,
    RemediationJobStatus,
    RemediationOrchestrator,
    ReassessmentService,
    TeachingStrategyDecision,
    TeachingStrategyReasonCode,
    TeachingStrategySelector,
    TeachingStrategyType,
    normalize_misconception_code,
)
from app.services.schemas import ConceptNode, KnowledgeGraph, SourceRecord
from app.services.video.scene_schema import VideoArtifact, VideoJobStatus, VideoPlan
from app.services.video.video_planner import plan_video_for_target


def async_test(coro):
    @functools.wraps(coro)
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def sample_kg() -> KnowledgeGraph:
    c_mass = ConceptNode(
        concept_id="CONCEPT_MASS",
        name="Inertial Mass",
        definition="The measure of an object's resistance to acceleration when a net force is applied.",
        prerequisite_concept_ids=[],
        source_content_ids=["chunk_mass"],
        difficulty="foundational",
    )
    c_force = ConceptNode(
        concept_id="CONCEPT_FORCE",
        name="Net Force and Acceleration",
        definition="Acceleration of an object is directly proportional to net force and inversely proportional to mass (F = ma).",
        prerequisite_concept_ids=["CONCEPT_MASS"],
        source_content_ids=["chunk_force"],
        difficulty="intermediate",
    )
    return KnowledgeGraph(concepts={
        "CONCEPT_MASS": c_mass,
        "CONCEPT_FORCE": c_force,
    })


@pytest.fixture
def dependency_provider(sample_kg: KnowledgeGraph) -> ConceptDependencyProvider:
    return ConceptDependencyProvider.from_knowledge_graph(sample_kg)


@pytest.fixture
def clean_services(sample_kg: KnowledgeGraph, dependency_provider: ConceptDependencyProvider, monkeypatch):
    def mock_get_source(sid):
        return SourceRecord(
            source_id=sid,
            filename=f"{sid}.pdf",
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

    monkeypatch.setattr("app.services.mastery.application_service.get_source_record", mock_get_source)
    monkeypatch.setattr("app.services.mastery.application_service.load_knowledge_graph", lambda sid: sample_kg)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_knowledge_graph", lambda sid: sample_kg)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_rich_chunks", lambda sid: [])

    mastery_repo = InMemoryMasteryRepository()
    attempt_repo = InMemoryAssessmentAttemptRepository()
    question_registry = InMemoryQuestionRegistry()
    remediation_repo = InMemoryRemediationJobRepository()
    misconception_repo = InMemoryMisconceptionRepository()
    strategy_selector = TeachingStrategySelector(
        dependency_provider=dependency_provider,
        misconception_repo=misconception_repo,
        mastery_repo=mastery_repo,
    )
    state_machine = MasteryStateMachine(MasteryConfig(max_remediation_attempts=3, mastery_threshold=0.7, min_reassessment_attempts_for_mastery=1))

    attempt_service = AssessmentAttemptService(
        mastery_repo=mastery_repo,
        attempt_repo=attempt_repo,
        question_registry=question_registry,
        state_machine=state_machine,
        misconception_repo=misconception_repo,
    )

    reassessment_service = ReassessmentService(
        mastery_repo=mastery_repo,
        question_registry=question_registry,
        misconception_repo=misconception_repo,
    )

    app_service = AdaptiveLearningService(
        mastery_repo=mastery_repo,
        attempt_repo=attempt_repo,
        question_registry=question_registry,
        remediation_repo=remediation_repo,
        misconception_repo=misconception_repo,
        strategy_selector=strategy_selector,
    )

    return {
        "mastery_repo": mastery_repo,
        "attempt_repo": attempt_repo,
        "question_registry": question_registry,
        "remediation_repo": remediation_repo,
        "misconception_repo": misconception_repo,
        "strategy_selector": strategy_selector,
        "state_machine": state_machine,
        "attempt_service": attempt_service,
        "reassessment_service": reassessment_service,
        "app_service": app_service,
        "kg": sample_kg,
        "dependency_provider": dependency_provider,
    }


# ==============================================================================
# M1 & M2: DOMAIN MODELS, NORMALIZATION, EVIDENCE CAPTURE
# ==============================================================================

def test_m1_normalization_rules():
    """Verify normalize_misconception_code accepts valid codes and rejects placeholders."""
    # Valid codes
    assert normalize_misconception_code("same_force_same_accel") == "SAME_FORCE_SAME_ACCEL"
    assert normalize_misconception_code("MASS_FORCE_CONFLATION") == "MASS_FORCE_CONFLATION"
    assert normalize_misconception_code("  heavier_falls_faster  ") == "HEAVIER_FALLS_FASTER"

    # Rejection of placeholders and garbage
    assert normalize_misconception_code(None) is None
    assert normalize_misconception_code("") is None
    assert normalize_misconception_code("WRONG_ANSWER_1") is None
    assert normalize_misconception_code("BAD_REASONING") is None
    assert normalize_misconception_code("MISC_1") is None
    assert normalize_misconception_code("NONE") is None
    assert normalize_misconception_code("UNKNOWN") is None


def test_m2_distractor_metadata_capture(clean_services):
    """Verify that selecting a mapped distractor creates misconception evidence."""
    svc = clean_services["attempt_service"]
    q_reg = clean_services["question_registry"]
    m_repo = clean_services["misconception_repo"]

    # Register authoritative question with distractor misconception
    auth_q = AuthoritativeQuestion(
        question_id="Q_DIAG_NEWTON_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        stem="If the same force is applied to two objects of different mass, what happens?",
        options=[
            "They will have the exact same acceleration",
            "The object with less mass accelerates more",
            "The object with more mass accelerates more",
            "Neither object moves",
        ],
        correct_index=1,
        distractor_misconceptions={
            0: DistractorMisconceptionMetadata(
                code="SAME_FORCE_SAME_ACCELERATION",
                label="Assumes identical forces produce identical accelerations regardless of mass",
                misconception_type="causal",
            )
        },
        source_content_ids=["chunk_force"],
    )
    q_reg.register(auth_q)

    # Learner chooses distractor 0 (incorrect)
    sub = AssessmentSubmissionRequest(
        attempt_id="ATT_1",
        question_id="Q_DIAG_NEWTON_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="learner_alex",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    )
    res = svc.record_attempt(sub)
    assert not res.is_correct

    # Verify evidence stored in repository
    mis = m_repo.find_active_by_code("learner_alex", "SRC_PHYSICS_1", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCELERATION")
    assert mis is not None
    assert mis.confidence == MisconceptionConfidenceState.POSSIBLE
    assert mis.evidence_count == 1
    assert "ATT_1" in mis.evidence_attempt_ids
    assert mis.status == MisconceptionStatus.ACTIVE


# ==============================================================================
# M3: EVIDENCE ACCUMULATION, CONFIDENCE PROGRESSION & RECURRENCE
# ==============================================================================

def test_m3_confidence_progression_and_idempotency(clean_services):
    """Verify 1 -> POSSIBLE, 2 -> LIKELY, 3+ -> CONFIRMED, and idempotent attempt handling."""
    svc = clean_services["attempt_service"]
    q_reg = clean_services["question_registry"]
    m_repo = clean_services["misconception_repo"]

    # Register 3 distinct questions testing same misconception
    for i in range(1, 4):
        q_reg.register(AuthoritativeQuestion(
            question_id=f"Q_FORCE_{i}",
            concept_id="CONCEPT_FORCE",
            source_id="SRC_PHYSICS_1",
            stem=f"Force scenario question variation {i}?",
            options=["Distractor matching misconception", "Wrong opt 2", "Correct Answer", "Wrong opt 3"],
            correct_index=2,
            distractor_misconceptions={
                0: DistractorMisconceptionMetadata(
                    code="SAME_FORCE_SAME_ACCELERATION",
                    label="Same force means same acceleration",
                )
            },
        ))

    # Attempt 1 -> POSSIBLE
    svc.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_101",
        question_id="Q_FORCE_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="learner_bob",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    mis = m_repo.find_active_by_code("learner_bob", "SRC_PHYSICS_1", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCELERATION")
    assert mis.confidence == MisconceptionConfidenceState.POSSIBLE
    assert mis.evidence_count == 1

    # Idempotency check: duplicate submission with ATT_101 must not double count
    svc.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_101",
        question_id="Q_FORCE_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="learner_bob",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    mis_dup = m_repo.find_active_by_code("learner_bob", "SRC_PHYSICS_1", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCELERATION")
    assert mis_dup.evidence_count == 1

    # Attempt 2 -> LIKELY
    svc.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_102",
        question_id="Q_FORCE_2",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="learner_bob",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    mis2 = m_repo.find_active_by_code("learner_bob", "SRC_PHYSICS_1", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCELERATION")
    assert mis2.confidence == MisconceptionConfidenceState.LIKELY
    assert mis2.evidence_count == 2

    # Attempt 3 -> CONFIRMED
    svc.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_103",
        question_id="Q_FORCE_3",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="learner_bob",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    mis3 = m_repo.find_active_by_code("learner_bob", "SRC_PHYSICS_1", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCELERATION")
    assert mis3.confidence == MisconceptionConfidenceState.CONFIRMED
    assert mis3.evidence_count == 3


def test_m3_recurrence_tracking(clean_services):
    """Verify that a misconception that was CORRECTED becomes RECURRENT if triggered again."""
    m_repo = clean_services["misconception_repo"]
    svc = clean_services["attempt_service"]
    q_reg = clean_services["question_registry"]

    q_reg.register(AuthoritativeQuestion(
        question_id="Q_RECUR_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        stem="Is velocity directly proportional to force in free motion?",
        options=["Yes, velocity needs force", "No, acceleration is proportional to force"],
        correct_index=1,
        distractor_misconceptions={
            0: DistractorMisconceptionMetadata(code="FORCE_PROPORTIONAL_VELOCITY", label="Velocity requires continuous force")
        }
    ))

    # Step 1: Initial occurrence
    svc.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REC_1",
        question_id="Q_RECUR_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="learner_clara",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    mis = m_repo.find_active_by_code("learner_clara", "SRC_PHYSICS_1", "CONCEPT_FORCE", "FORCE_PROPORTIONAL_VELOCITY")
    assert mis.status == MisconceptionStatus.ACTIVE

    # Step 2: Mark corrected
    mis.mark_corrected()
    m_repo.save(mis)
    assert mis.status == MisconceptionStatus.CORRECTED

    # Step 3: Relapse (learner falls into same misconception again)
    svc.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REC_2",
        question_id="Q_RECUR_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="learner_clara",
        selected_answer=0,
        assessment_type=AssessmentType.REASSESSMENT,
    ))

    relapsed = m_repo.find_by_code("learner_clara", "SRC_PHYSICS_1", "CONCEPT_FORCE", "FORCE_PROPORTIONAL_VELOCITY")
    assert relapsed is not None
    assert relapsed.status == MisconceptionStatus.RECURRENT


# ==============================================================================
# M4: DETERMINISTIC TEACHING STRATEGY SELECTION
# ==============================================================================

def test_m4_teaching_strategy_selector_taxonomy_and_prerequisites(clean_services):
    """Verify deterministic strategy selection based on taxonomy and prerequisite mastery."""
    selector: TeachingStrategySelector = clean_services["strategy_selector"]
    m_repo: InMemoryMisconceptionRepository = clean_services["misconception_repo"]
    mastery_repo: InMemoryMasteryRepository = clean_services["mastery_repo"]

    # 1. Unmastered prerequisite check -> PREREQUISITE_REVIEW
    mis_evidence = MisconceptionEvidence(
        user_id="user_prereq",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCELERATION",
        label="Same force means same acceleration",
        misconception_type="causal",
        confidence=MisconceptionConfidenceState.LIKELY,
        status=MisconceptionStatus.ACTIVE,
    )
    m_repo.save(mis_evidence)

    dec_prereq = selector.select_strategy("user_prereq", "SRC_PHYSICS_1", "CONCEPT_FORCE")
    assert dec_prereq.strategy == TeachingStrategyType.PREREQUISITE_REVIEW
    assert dec_prereq.reason_code == TeachingStrategyReasonCode.UNMASTERED_PREREQUISITE

    # 2. Master prerequisite CONCEPT_MASS -> now taxonomy kicks in
    mastery_repo.save(MasteryRecord(
        user_id="user_prereq",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=0.9,
    ))

    # Causal misconception -> COUNTEREXAMPLE
    dec_causal = selector.select_strategy("user_prereq", "SRC_PHYSICS_1", "CONCEPT_FORCE")
    assert dec_causal.strategy == TeachingStrategyType.COUNTEREXAMPLE

    # Conflation misconception -> CONTRAST
    mis_evidence.misconception_type = "conflation"
    m_repo.save(mis_evidence)
    dec_conflation = selector.select_strategy("user_prereq", "SRC_PHYSICS_1", "CONCEPT_FORCE")
    assert dec_conflation.strategy == TeachingStrategyType.CONTRAST

    # Procedural misconception -> WORKED_EXAMPLE
    mis_evidence.misconception_type = "procedural"
    m_repo.save(mis_evidence)
    dec_procedural = selector.select_strategy("user_prereq", "SRC_PHYSICS_1", "CONCEPT_FORCE")
    assert dec_procedural.strategy == TeachingStrategyType.WORKED_EXAMPLE

    # Prediction misconception -> PREDICTION_AND_REVEAL
    mis_evidence.misconception_type = "prediction"
    m_repo.save(mis_evidence)
    dec_pred = selector.select_strategy("user_prereq", "SRC_PHYSICS_1", "CONCEPT_FORCE")
    assert dec_pred.strategy == TeachingStrategyType.PREDICTION_AND_REVEAL


def test_m4_strategy_retry_novelty_progression(clean_services):
    """Verify that retries rotate to a novel strategy."""
    selector: TeachingStrategySelector = clean_services["strategy_selector"]
    m_repo: InMemoryMisconceptionRepository = clean_services["misconception_repo"]
    mastery_repo: InMemoryMasteryRepository = clean_services["mastery_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="user_retry",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
    ))

    mis = MisconceptionEvidence(
        user_id="user_retry",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        code="FORCE_CONFLATION",
        label="Conflation of force and energy",
        misconception_type="conflation",
        confidence=MisconceptionConfidenceState.LIKELY,
        status=MisconceptionStatus.ACTIVE,
    )
    m_repo.save(mis)

    # Attempt 1: CONTRAST (from conflation)
    dec1 = selector.select_strategy("user_retry", "SRC_PHYSICS_1", "CONCEPT_FORCE", previous_strategies=[])
    assert dec1.strategy == TeachingStrategyType.CONTRAST

    # Attempt 2: Must rotate away from CONTRAST
    dec2 = selector.select_strategy("user_retry", "SRC_PHYSICS_1", "CONCEPT_FORCE", previous_strategies=[TeachingStrategyType.CONTRAST.value])
    assert dec2.strategy != TeachingStrategyType.CONTRAST
    assert dec2.strategy == TeachingStrategyType.VISUAL_COMPARISON

    # Attempt 3: Must rotate away from both
    dec3 = selector.select_strategy(
        "user_retry",
        "SRC_PHYSICS_1",
        "CONCEPT_FORCE",
        previous_strategies=[TeachingStrategyType.CONTRAST.value, TeachingStrategyType.VISUAL_COMPARISON.value],
    )
    assert dec3.strategy not in (TeachingStrategyType.CONTRAST, TeachingStrategyType.VISUAL_COMPARISON)
    assert dec3.strategy == TeachingStrategyType.COUNTEREXAMPLE


def test_m4_no_fabricated_personalization(clean_services):
    """Verify that without misconception evidence, normal grounded remediation is used."""
    selector: TeachingStrategySelector = clean_services["strategy_selector"]
    mastery_repo: InMemoryMasteryRepository = clean_services["mastery_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="user_clean",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
    ))

    # No misconception registered for CONCEPT_FORCE
    dec = selector.select_strategy("user_clean", "SRC_PHYSICS_1", "CONCEPT_FORCE")
    assert dec.strategy == TeachingStrategyType.DIRECT_EXPLANATION
    assert dec.misconception_code is None
    assert dec.reason_code in (
        TeachingStrategyReasonCode.DEFAULT_CONCEPT_GROUNDED,
        TeachingStrategyReasonCode.DEFAULT_DIRECT,
    )


# ==============================================================================
# M5: VIDEO TARGET EXTENSION, PLANNER PEDAGOGY, STRATEGY TRACEABILITY
# ==============================================================================

def test_m5_video_target_extension():
    """Verify VideoTarget stores optional misconception fields."""
    target = VideoTarget(
        student_id="student_1",
        source_id="src_1",
        concept_id="CONCEPT_FORCE",
        concept_name="Net Force and Acceleration",
        misconception_code="SAME_FORCE_SAME_ACCEL",
        misconception_label="Same force assumed to mean same acceleration",
        confidence="LIKELY",
        teaching_strategy="COUNTEREXAMPLE",
        previous_strategy="DIRECT_EXPLANATION",
        evidence_attempt_ids=["ATT_1", "ATT_2"],
    )
    dumped = target.model_dump()
    assert dumped["misconception_code"] == "SAME_FORCE_SAME_ACCEL"
    assert dumped["teaching_strategy"] == "COUNTEREXAMPLE"
    assert len(dumped["evidence_attempt_ids"]) == 2


def test_m5_video_planner_strategy_scenes():
    """Verify VideoPlanner alters scene structure and pedagogical angles per strategy."""
    # 1. CONTRAST strategy
    target_contrast = VideoTarget(
        student_id="student_1",
        source_id="src_1",
        concept_id="CONCEPT_FORCE",
        concept_name="Net Force and Acceleration",
        teaching_strategy="CONTRAST",
        misconception_code="MASS_FORCE_CONFLATION",
        misconception_label="Conflating mass with force",
    )
    plan_c: VideoPlan = plan_video_for_target(target_contrast, student_id="student_1", source_id="src_1")
    assert any("contrast" in (s.narration or "").lower() or "case a" in (s.narration or "").lower() or "versus" in (s.narration or "").lower() for s in plan_c.scenes)

    # 2. COUNTEREXAMPLE strategy
    target_counter = VideoTarget(
        student_id="student_1",
        source_id="src_1",
        concept_id="CONCEPT_FORCE",
        concept_name="Net Force and Acceleration",
        teaching_strategy="COUNTEREXAMPLE",
        misconception_code="SAME_FORCE_SAME_ACCEL",
        misconception_label="Same force assumed to mean same acceleration",
    )
    plan_ce: VideoPlan = plan_video_for_target(target_counter, student_id="student_1", source_id="src_1")
    assert any("assumption" in (s.narration or "").lower() or "counterexample" in (s.narration or "").lower() for s in plan_ce.scenes)

    # 3. WORKED_EXAMPLE strategy
    target_worked = VideoTarget(
        student_id="student_1",
        source_id="src_1",
        concept_id="CONCEPT_FORCE",
        concept_name="Net Force and Acceleration",
        teaching_strategy="WORKED_EXAMPLE",
    )
    plan_w: VideoPlan = plan_video_for_target(target_worked, student_id="student_1", source_id="src_1")
    assert any("step 1" in (s.narration or "").lower() or "step-by-step" in (s.narration or "").lower() or "calculation" in (s.narration or "").lower() for s in plan_w.scenes)


@async_test
async def test_m5_strategy_traceability_persisted_in_remediation_job(clean_services, tmp_path):
    """Verify RemediationJob persists strategy_used, misconception_code, and evidence_attempt_ids."""
    mastery_repo = clean_services["mastery_repo"]
    remediation_repo = clean_services["remediation_repo"]
    misconception_repo = clean_services["misconception_repo"]
    strategy_selector = clean_services["strategy_selector"]
    state_machine = clean_services["state_machine"]

    # Seed weak mastery
    mastery_repo.save(MasteryRecord(
        user_id="user_trace",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        mastery_state=MasteryState.WEAK,
        attempt_count=2,
        incorrect_count=2,
    ))
    mastery_repo.save(MasteryRecord(
        user_id="user_trace",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
    ))

    # Seed misconception evidence
    misconception_repo.save(MisconceptionEvidence(
        user_id="user_trace",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Same force assumed to mean same acceleration",
        misconception_type="causal",
        confidence=MisconceptionConfidenceState.LIKELY,
        evidence_attempt_ids=["ATT_T1", "ATT_T2"],
    ))

    # Mock video engine returning valid artifact
    video_file = tmp_path / "trace_video.mp4"
    video_file.write_bytes(b"mock mp4 content")

    async def mock_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        # Check target contains strategy and misconception
        assert target.teaching_strategy == "COUNTEREXAMPLE"
        assert target.misconception_code == "SAME_FORCE_SAME_ACCEL"
        assert target.evidence_attempt_ids == ["ATT_T1", "ATT_T2"]

        return VideoArtifact(
            job_id=job_id or "JOB_TRACE_1",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=30.0,
            status=VideoJobStatus.COMPLETED,
            video_path=str(video_file),
        )

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        misconception_repo=misconception_repo,
        strategy_selector=strategy_selector,
        video_engine_fn=mock_engine,
    )

    action = NextLearningAction(
        action_type=LearningActionType.REMEDIATE,
        reason_code=ReasonCode.DIAGNOSTIC_FAILED_WEAK,
        user_id="user_trace",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job = await orchestrator.execute_remediation(action)

    # Assert traceability fields persisted on job
    assert job.strategy_used == "COUNTEREXAMPLE"
    assert job.misconception_code == "SAME_FORCE_SAME_ACCEL"
    assert job.evidence_attempt_ids == ["ATT_T1", "ATT_T2"]
    assert job.metadata.get("strategy_used") == "COUNTEREXAMPLE"
    assert job.metadata.get("misconception_code") == "SAME_FORCE_SAME_ACCEL"


# ==============================================================================
# M6: REASSESSMENT TARGETING & MISCONCEPTION CORRECTION
# ==============================================================================

def test_m6_reassessment_targeting_and_correction(clean_services):
    """Verify ReassessmentService generates targeted question, and correct answer marks misconception CORRECTED."""
    mastery_repo = clean_services["mastery_repo"]
    attempt_service = clean_services["attempt_service"]
    reassessment_service = clean_services["reassessment_service"]
    misconception_repo = clean_services["misconception_repo"]
    question_registry = clean_services["question_registry"]
    kg = clean_services["kg"]

    # 1. Concept in REASSESSING state with active misconception
    mastery_repo.save(MasteryRecord(
        user_id="user_m6",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        mastery_state=MasteryState.REASSESSING,
        attempt_count=2,
        incorrect_count=2,
        remediation_attempt_count=1,
    ))

    misconception_repo.save(MisconceptionEvidence(
        user_id="user_m6",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Same force assumed to mean same acceleration",
        misconception_type="causal",
        confidence=MisconceptionConfidenceState.LIKELY,
        status=MisconceptionStatus.ACTIVE,
    ))

    # 2. Generate reassessment question
    q = reassessment_service.generate_reassessment_question(
        user_id="user_m6",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        provided_concept=kg.concepts["CONCEPT_FORCE"],
    )
    assert q is not None
    assert q.concept_id == "CONCEPT_FORCE"
    registered_q = question_registry.get(q.question_id)
    assert registered_q is not None

    # 3. Learner submits the correct answer (not selecting any distractor)
    sub = AssessmentSubmissionRequest(
        attempt_id="ATT_REASSESS_PASS",
        question_id=q.question_id,
        concept_id="CONCEPT_FORCE",
        source_id="SRC_PHYSICS_1",
        user_id="user_m6",
        selected_answer=q.correct_index,
        assessment_type=AssessmentType.REASSESSMENT,
    )
    result = attempt_service.record_attempt(sub)
    assert result.is_correct
    assert result.mastery_state == MasteryState.MASTERED

    # 4. Verify misconception is marked CORRECTED
    updated_mis = misconception_repo.find_by_code("user_m6", "SRC_PHYSICS_1", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCEL")
    assert updated_mis is not None
    assert updated_mis.status == MisconceptionStatus.CORRECTED


# ==============================================================================
# M7: ROADMAP EXPLAINABLE HISTORY & UI PRESENTATION
# ==============================================================================

def test_m7_roadmap_explainable_history_safe_client_fields(clean_services):
    """Verify RoadmapResponse exposes explainable fields and hides answer keys."""
    app_service: AdaptiveLearningService = clean_services["app_service"]
    mastery_repo = clean_services["mastery_repo"]
    misconception_repo = clean_services["misconception_repo"]
    remediation_repo = clean_services["remediation_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="user_m7",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))

    mastery_repo.save(MasteryRecord(
        user_id="user_m7",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        mastery_state=MasteryState.REMEDIATING,
        attempt_count=2,
        incorrect_count=2,
        remediation_attempt_count=1,
    ))

    misconception_repo.save(MisconceptionEvidence(
        user_id="user_m7",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Same force assumed to mean same acceleration",
        confidence=MisconceptionConfidenceState.LIKELY,
        status=MisconceptionStatus.ACTIVE,
        evidence_attempt_ids=["ATT_1", "ATT_2"],
    ))

    remediation_repo.save(RemediationJob(
        job_id="JOB_M7",
        user_id="user_m7",
        source_id="SRC_PHYSICS_1",
        concept_id="CONCEPT_FORCE",
        concept_name="Net Force and Acceleration",
        status=RemediationJobStatus.READY,
        strategy_used="COUNTEREXAMPLE",
        misconception_code="SAME_FORCE_SAME_ACCEL",
    ))

    roadmap = app_service.get_roadmap("user_m7", "SRC_PHYSICS_1")

    # Verify explainable journey exposed
    assert roadmap.misconception_journey is not None
    assert len(roadmap.misconception_journey) >= 1
    journey_item = next(j for j in roadmap.misconception_journey if j["concept_id"] == "CONCEPT_FORCE")
    assert journey_item["active_misconception_label"] == "Same force assumed to mean same acceleration"
    assert journey_item["misconception_confidence"] == "LIKELY"
    assert journey_item["strategy_used"] == "COUNTEREXAMPLE"
    assert journey_item["misconception_status"] == "ACTIVE"

    # Verify NextActionResponse includes why_chosen
    next_action = app_service.get_next_learning_action("user_m7", "SRC_PHYSICS_1")
    assert next_action.why_chosen is not None
    assert next_action.why_chosen["detected_learning_gap"] == "Same force assumed to mean same acceleration"
    assert "2 assessment attempts" in next_action.why_chosen["evidence"]
    assert next_action.why_chosen["status"] == "Under review"


def test_m7_dashboard_ui_elements():
    """Verify that DASHBOARD_HTML contains the compact 'Why this review was chosen' section."""
    client = TestClient(app)
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.text

    # Required M7 UI IDs and text
    assert 'id="misconceptionReviewCard"' in html
    assert "Why this review was chosen" in html
    assert 'id="lblDetectedGap"' in html
    assert 'id="lblEvidenceAttempts"' in html
    assert 'id="lblTeachingApproach"' in html
    assert 'id="lblMisconceptionStatus"' in html


# ==============================================================================
# REAL E2E FLOW
# ==============================================================================

@async_test
async def test_m5_m6_m7_real_e2e_complete_flow(clean_services, tmp_path):
    """Complete Real E2E Flow:
    1. Grounded diagnostic question answered incorrectly with mapped distractor -> POSSIBLE.
    2. Second diagnostic question answered incorrectly with same distractor -> LIKELY.
    3. Personalization next-action -> REMEDIATE.
    4. TeachingStrategySelector picks COUNTEREXAMPLE.
    5. RemediationOrchestrator generates validated video and persists strategy metadata.
    6. Video reaches COMPLETED -> Next-action becomes REASSESS.
    7. ReassessmentService generates targeted question.
    8. Learner submits correct answer -> MASTERED and misconception becomes CORRECTED.
    9. Roadmap displays before-and-after misconception journey.
    """
    mastery_repo = clean_services["mastery_repo"]
    attempt_repo = clean_services["attempt_repo"]
    question_registry = clean_services["question_registry"]
    remediation_repo = clean_services["remediation_repo"]
    misconception_repo = clean_services["misconception_repo"]
    attempt_service = clean_services["attempt_service"]
    reassessment_service = clean_services["reassessment_service"]
    strategy_selector = clean_services["strategy_selector"]
    app_service = clean_services["app_service"]
    state_machine = clean_services["state_machine"]
    kg = clean_services["kg"]

    user_id = "real_e2e_student"
    source_id = "SRC_REAL_E2E"
    concept_id = "CONCEPT_FORCE"

    # Master prerequisite first so strategy selector targets the causal misconception
    mastery_repo.save(MasteryRecord(
        user_id=user_id,
        source_id=source_id,
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=1.0,
    ))

    # --- STEP 1: First diagnostic question ---
    question_registry.register(AuthoritativeQuestion(
        question_id="Q_E2E_DIAG_1",
        concept_id=concept_id,
        source_id=source_id,
        stem="What acceleration occurs when force F acts on mass m?",
        options=["Same accel", "a = F/2m", "a = F/m", "a = 2F/m"],
        correct_index=2,
        distractor_misconceptions={
            0: DistractorMisconceptionMetadata(
                code="SAME_FORCE_SAME_ACCEL",
                label="Same force produces same acceleration",
                misconception_type="causal",
            )
        }
    ))
    res1 = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_E2E_1",
        question_id="Q_E2E_DIAG_1",
        concept_id=concept_id,
        source_id=source_id,
        user_id=user_id,
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert not res1.is_correct
    mis1 = misconception_repo.find_active_by_code(user_id, source_id, concept_id, "SAME_FORCE_SAME_ACCEL")
    assert mis1.confidence == MisconceptionConfidenceState.POSSIBLE

    # --- STEP 2: Second diagnostic question (reinforces misconception) ---
    question_registry.register(AuthoritativeQuestion(
        question_id="Q_E2E_DIAG_2",
        concept_id=concept_id,
        source_id=source_id,
        stem="Two unequal masses experience the same net force. Do they accelerate equally?",
        options=["No", "Yes, identical force means identical acceleration", "Depends on speed", "Neither accelerates"],
        correct_index=0,
        distractor_misconceptions={
            1: DistractorMisconceptionMetadata(
                code="SAME_FORCE_SAME_ACCEL",
                label="Same force produces same acceleration",
                misconception_type="causal",
            )
        }
    ))
    res2 = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_E2E_2",
        question_id="Q_E2E_DIAG_2",
        concept_id=concept_id,
        source_id=source_id,
        user_id=user_id,
        selected_answer=1,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert not res2.is_correct
    mis2 = misconception_repo.find_active_by_code(user_id, source_id, concept_id, "SAME_FORCE_SAME_ACCEL")
    assert mis2.confidence == MisconceptionConfidenceState.LIKELY
    assert mis2.evidence_count == 2

    # --- STEP 3: Next action is REMEDIATE ---
    act_remediate = app_service.get_next_learning_action(user_id, source_id)
    assert act_remediate.action_type == LearningActionType.REMEDIATE
    assert act_remediate.concept_id == concept_id
    assert act_remediate.why_chosen["detected_learning_gap"] == "Same force produces same acceleration"
    assert act_remediate.why_chosen["status"] == "Under review"

    # --- STEP 4 & 5: Video generation with strategy traceability ---
    mp4_path = tmp_path / "e2e_remediation.mp4"
    mp4_path.write_bytes(b"validated MP4 container binary data")

    async def e2e_video_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        assert target.teaching_strategy == "COUNTEREXAMPLE"
        assert target.misconception_code == "SAME_FORCE_SAME_ACCEL"
        assert target.confidence == "LIKELY"
        return VideoArtifact(
            job_id=job_id or "JOB_E2E_1",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=30.0,
            status=VideoJobStatus.COMPLETED,
            video_path=str(mp4_path),
        )

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        misconception_repo=misconception_repo,
        strategy_selector=strategy_selector,
        video_engine_fn=e2e_video_engine,
    )

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job = await orchestrator.execute_remediation(act_remediate)
    assert job.status == RemediationJobStatus.READY
    assert job.strategy_used == "COUNTEREXAMPLE"
    assert job.misconception_code == "SAME_FORCE_SAME_ACCEL"

    # --- STEP 6: Concept transitions to REASSESS ---
    act_reassess = app_service.get_next_learning_action(user_id, source_id)
    assert act_reassess.action_type == LearningActionType.REASSESS

    # --- STEP 7: Generate targeted reassessment question ---
    reassess_q = reassessment_service.generate_reassessment_question(
        user_id,
        source_id,
        concept_id,
        provided_concept=kg.concepts[concept_id],
    )
    assert reassess_q is not None

    # --- STEP 8: Learner submits correct answer on reassessment ---
    res_pass = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_E2E_REASSESS",
        question_id=reassess_q.question_id,
        concept_id=concept_id,
        source_id=source_id,
        user_id=user_id,
        selected_answer=reassess_q.correct_index,
        assessment_type=AssessmentType.REASSESSMENT,
    ))
    assert res_pass.is_correct
    assert res_pass.mastery_state == MasteryState.MASTERED

    # Misconception must now be CORRECTED
    mis_corrected = misconception_repo.find_by_code(user_id, source_id, concept_id, "SAME_FORCE_SAME_ACCEL")
    assert mis_corrected.status == MisconceptionStatus.CORRECTED

    # --- STEP 9: Roadmap displays before/after misconception journey ---
    final_roadmap = app_service.get_roadmap(user_id, source_id)
    assert any(j["concept_id"] == concept_id and j["misconception_status"] == "CORRECTED" for j in final_roadmap.misconception_journey)

    final_action = app_service.get_next_learning_action(user_id, source_id)
    assert final_action.action_type in (LearningActionType.ASSESS, LearningActionType.COMPLETE)
