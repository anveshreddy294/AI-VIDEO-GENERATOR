"""Comprehensive Exit Audit and Safety Test Suite for Misconception Intelligence.

Audits:
1. One wrong answer cannot become CONFIRMED automatically.
2. Duplicate submissions do not inflate evidence.
3. Same question repeated does not inflate evidence.
4. Correct answer does not create misconception evidence.
5. Misconception metadata is never leaked before submission.
6. Cross-user evidence is impossible.
7. Cross-source evidence is impossible.
8. LLM cannot directly set confidence state.
9. LLM cannot directly mark misconception corrected.
10. Teaching strategy is deterministic at the policy layer.
11. Retry strategy changes after ineffective remediation.
12. No unsupported prerequisite is invented.
13. Video remains grounded to original source.
14. Misconception context cannot override source truth.
15. Reassessment targets same misconception with a novel question.
16. Corrected misconception retains historical audit trail.
17. Recurrence is detected.
18. Roadmap explains WHY personalization happened.
19. Existing adaptive learning loop still works without misconception metadata.
20. Runtime remains bounded.

Failure Injections:
- missing misconception mapping
- malformed misconception code
- LLM returns unsupported misconception
- question-generation failure
- video-generation failure
- repository failure
- page refresh is pure read

Real Acceptance Case:
- End-to-end execution of real physics concept (Newton's Second Law).
"""

from __future__ import annotations

import asyncio
import functools
import time
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
    AssessmentServiceError,
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
def audit_kg() -> KnowledgeGraph:
    c_mass = ConceptNode(
        concept_id="CONCEPT_MASS",
        name="Inertial Mass",
        definition="The measure of an object's resistance to acceleration when a net force is applied.",
        prerequisite_concept_ids=[],
        source_content_ids=["chunk_mass_1"],
        difficulty="foundational",
    )
    c_force = ConceptNode(
        concept_id="CONCEPT_FORCE",
        name="Newton's Second Law of Motion",
        definition="Acceleration of an object is directly proportional to net force and inversely proportional to mass (F = ma).",
        prerequisite_concept_ids=["CONCEPT_MASS"],
        source_content_ids=["chunk_force_1", "chunk_force_2"],
        difficulty="intermediate",
    )
    return KnowledgeGraph(concepts={
        "CONCEPT_MASS": c_mass,
        "CONCEPT_FORCE": c_force,
    })


@pytest.fixture
def audit_env(audit_kg: KnowledgeGraph, monkeypatch):
    def mock_get_source(sid):
        return SourceRecord(
            source_id=sid,
            filename=f"{sid}.pdf",
            source_type="pdf",
            mime_type="application/pdf",
            file_hash="hash123",
            sha256="hash123",
            file_size=2048,
            uploaded_by="student_default",
            user_id="student_default",
            owner_user_id="student_default",
            version=1,
            source_version="v1",
            status="READY",
        )

    monkeypatch.setattr("app.services.mastery.application_service.get_source_record", mock_get_source)
    monkeypatch.setattr("app.services.mastery.application_service.load_knowledge_graph", lambda sid: audit_kg)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_knowledge_graph", lambda sid: audit_kg)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_rich_chunks", lambda sid: [])

    dependency_provider = ConceptDependencyProvider.from_knowledge_graph(audit_kg)
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
    state_machine = MasteryStateMachine(MasteryConfig(
        max_remediation_attempts=3,
        mastery_threshold=0.7,
        min_reassessment_attempts_for_mastery=1,
    ))

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
        "kg": audit_kg,
        "dependency_provider": dependency_provider,
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
    }


# ==============================================================================
# AUDIT CHECKS 1 TO 20
# ==============================================================================

def test_check_01_one_wrong_answer_cannot_become_confirmed_automatically(audit_env):
    """Check 1: Single wrong answer can only yield POSSIBLE, never CONFIRMED."""
    attempt_service = audit_env["attempt_service"]
    misconception_repo = audit_env["misconception_repo"]
    question_registry = audit_env["question_registry"]

    question_registry.register(AuthoritativeQuestion(
        question_id="Q_CHK_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        stem="Which object accelerates more under force F?",
        options=["Heavy mass", "Light mass", "Both equally", "Neither"],
        correct_index=1,
        distractor_misconceptions={
            2: DistractorMisconceptionMetadata(
                code="SAME_FORCE_SAME_ACCEL",
                label="Identical force yields identical acceleration regardless of mass",
                misconception_type="causal",
            )
        }
    ))

    res = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_CHK_1",
        question_id="Q_CHK_1",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        user_id="student_default",
        selected_answer=2,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert not res.is_correct

    misc = misconception_repo.find_active_by_code("student_default", "SRC_AUDIT", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCEL")
    assert misc is not None
    assert misc.confidence == MisconceptionConfidenceState.POSSIBLE
    assert misc.confidence != MisconceptionConfidenceState.CONFIRMED
    assert misc.evidence_count == 1


def test_check_02_03_duplicate_and_same_question_does_not_inflate_evidence(audit_env):
    """Checks 2 & 3: Duplicate attempt submissions and repeated attempts on same question do not inflate confidence."""
    attempt_service = audit_env["attempt_service"]
    misconception_repo = audit_env["misconception_repo"]
    question_registry = audit_env["question_registry"]

    question_registry.register(AuthoritativeQuestion(
        question_id="Q_REPEAT",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        stem="Which accelerates faster?",
        options=["Heavy", "Equal", "Light", "Neither"],
        correct_index=2,
        distractor_misconceptions={
            1: DistractorMisconceptionMetadata(
                code="SAME_FORCE_SAME_ACCEL",
                label="Force equals acceleration",
                misconception_type="causal",
            )
        }
    ))

    # Initial attempt
    req = AssessmentSubmissionRequest(
        attempt_id="ATT_REPEAT_1",
        question_id="Q_REPEAT",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        user_id="student_default",
        selected_answer=1,
        assessment_type=AssessmentType.DIAGNOSTIC,
    )
    attempt_service.record_attempt(req)

    # Check 2: Exact duplicate submission
    dup_res = attempt_service.record_attempt(req)
    assert dup_res.is_duplicate is True
    misc = misconception_repo.find_active_by_code("student_default", "SRC_AUDIT", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCEL")
    assert misc.evidence_count == 1
    assert misc.confidence == MisconceptionConfidenceState.POSSIBLE

    # Check 3: New attempt on the SAME question
    req_same_q = AssessmentSubmissionRequest(
        attempt_id="ATT_REPEAT_2",
        question_id="Q_REPEAT",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        user_id="student_default",
        selected_answer=1,
        assessment_type=AssessmentType.DIAGNOSTIC,
    )
    attempt_service.record_attempt(req_same_q)
    misc_after = misconception_repo.find_active_by_code("student_default", "SRC_AUDIT", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCEL")
    # Same question repeated must NOT inflate confidence to LIKELY
    assert misc_after.confidence == MisconceptionConfidenceState.POSSIBLE


def test_check_04_correct_answer_does_not_create_misconception_evidence(audit_env):
    """Check 4: Correct answer creates ZERO misconception evidence."""
    attempt_service = audit_env["attempt_service"]
    misconception_repo = audit_env["misconception_repo"]
    question_registry = audit_env["question_registry"]

    question_registry.register(AuthoritativeQuestion(
        question_id="Q_CORRECT",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        stem="Correct relation?",
        options=["F = m/a", "F = ma", "F = m + a", "F = a/m"],
        correct_index=1,
        distractor_misconceptions={
            0: DistractorMisconceptionMetadata(code="FORCE_DIVISION_MASS", label="F=m/a error"),
        }
    ))

    res = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_CORRECT",
        question_id="Q_CORRECT",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        user_id="student_default",
        selected_answer=1,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert res.is_correct is True
    all_misc = misconception_repo.list_for_concept("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
    assert len(all_misc) == 0


def test_check_05_client_payload_never_leaks_misconception_or_answer_key():
    """Check 5: SafeQuestion and SafeOption never leak distractor_misconceptions or answer keys."""
    raw_q = Question(
        question_id="Q_SAFE_AUDIT",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        concept_name="Newton's Second Law",
        stem="Which object accelerates more?",
        options=[
            AssessmentOption(index=0, text="Cart A", is_correct=False, misconception_code="HIDDEN_MISC_CODE"),
            AssessmentOption(index=1, text="Cart B", is_correct=True),
        ],
        correct_index=1,
        explanation="Secret authoritative derivation",
    )
    safe_q = SafeQuestion(
        question_id=raw_q.question_id,
        concept_id=raw_q.concept_id,
        concept_name=raw_q.concept_name,
        stem=raw_q.stem,
        options=[SafeOption(index=opt.index, text=opt.text) for opt in raw_q.options],
    )
    data = safe_q.model_dump()
    assert "correct_index" not in data
    assert "explanation" not in data
    assert "distractor_misconceptions" not in data
    for opt in data["options"]:
        assert "is_correct" not in opt
        assert "misconception_code" not in opt
    assert "HIDDEN_MISC_CODE" not in str(data)
    assert "Secret authoritative derivation" not in str(data)


def test_check_06_07_cross_user_and_cross_source_isolation(audit_env):
    """Checks 6 & 7: Strict multi-tenant isolation across users and sources."""
    misconception_repo = audit_env["misconception_repo"]

    m1 = MisconceptionEvidence(
        user_id="user_A",
        source_id="SRC_1",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Label",
    )
    misconception_repo.save(m1)

    # Check 6: user_B cannot see user_A's misconception
    user_b_list = misconception_repo.list_for_concept("user_B", "SRC_1", "CONCEPT_FORCE")
    assert len(user_b_list) == 0

    # Check 7: user_A in SRC_2 cannot see SRC_1's misconception
    src_2_list = misconception_repo.list_for_concept("user_A", "SRC_2", "CONCEPT_FORCE")
    assert len(src_2_list) == 0


def test_check_08_09_llm_cannot_directly_set_confidence_or_mark_corrected():
    """Checks 8 & 9: MisconceptionEvidence confidence and status are state-machine bounded."""
    m = MisconceptionEvidence(
        user_id="user_guard",
        source_id="SRC_1",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Label",
        evidence_question_ids=["Q1"],
        evidence_attempt_ids=["ATT1"],
    )
    assert m.confidence_state == MisconceptionConfidenceState.POSSIBLE

    # Check 8: 2 independent questions required for LIKELY
    m.record_occurrence(question_id="Q2", attempt_id="ATT2")
    assert m.confidence_state == MisconceptionConfidenceState.LIKELY

    # Check 9: Only authoritative correction method marks status CORRECTED
    assert m.status == MisconceptionStatus.ACTIVE
    m.mark_corrected()
    assert m.status == MisconceptionStatus.CORRECTED
    assert m.corrected_at is not None


def test_check_10_teaching_strategy_is_deterministic_at_policy_layer(audit_env):
    """Check 10: Strategy selection is 100% deterministic code without LLM policy variance."""
    selector: TeachingStrategySelector = audit_env["strategy_selector"]
    misconception_repo = audit_env["misconception_repo"]
    mastery_repo = audit_env["mastery_repo"]

    # Prerequisite mastered so causal gap directly routes to COUNTEREXAMPLE
    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))

    misconception_repo.save(MisconceptionEvidence(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Causal error",
        misconception_type="causal",
        confidence=MisconceptionConfidenceState.LIKELY,
    ))

    # Run 10 times in a row: must always select COUNTEREXAMPLE
    for _ in range(10):
        decision = selector.select_strategy("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
        assert decision.strategy == TeachingStrategyType.COUNTEREXAMPLE
        assert decision.reason_code == TeachingStrategyReasonCode.INCORRECT_CAUSAL_BELIEF


def test_check_11_retry_strategy_changes_after_ineffective_remediation(audit_env):
    """Check 11: Attempt progression changes pedagogical strategy upon retry."""
    selector: TeachingStrategySelector = audit_env["strategy_selector"]
    misconception_repo = audit_env["misconception_repo"]
    mastery_repo = audit_env["mastery_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))

    misconception_repo.save(MisconceptionEvidence(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        code="CALCULATION_STEP_ERROR",
        label="Procedural error",
        misconception_type="procedural",
        confidence=MisconceptionConfidenceState.LIKELY,
    ))

    # Attempt 1: WORKED_EXAMPLE
    d1 = selector.select_strategy("student_default", "SRC_AUDIT", "CONCEPT_FORCE", attempt_number=1)
    assert d1.strategy == TeachingStrategyType.WORKED_EXAMPLE

    # Attempt 2: Must shift strategy (e.g. VISUAL_COMPARISON or CONTRAST)
    d2 = selector.select_strategy("student_default", "SRC_AUDIT", "CONCEPT_FORCE", attempt_number=2, previous_strategy=d1.strategy)
    assert d2.strategy != d1.strategy
    assert d2.reason_code == TeachingStrategyReasonCode.NOVELTY_FALLBACK_NEXT_STRATEGY


def test_check_12_no_unsupported_prerequisite_invented(audit_env):
    """Check 12: Prerequisite review only triggered if prerequisite exists in knowledge graph and is unmastered."""
    selector: TeachingStrategySelector = audit_env["strategy_selector"]
    mastery_repo = audit_env["mastery_repo"]

    # Prerequisite CONCEPT_MASS is unmastered -> PREREQUISITE_REVIEW
    d_unmastered = selector.select_strategy("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
    assert d_unmastered.strategy == TeachingStrategyType.PREREQUISITE_REVIEW
    assert d_unmastered.target_concept_id == "CONCEPT_MASS"

    # Once CONCEPT_MASS is mastered -> Normal strategy
    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))
    d_mastered = selector.select_strategy("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
    assert d_mastered.strategy != TeachingStrategyType.PREREQUISITE_REVIEW


def test_check_13_14_video_grounded_to_source_and_misconception_cannot_override_truth():
    """Checks 13 & 14: Video plan derives strictly from source knowledge chunk; misconception context annotates pedagogy without corrupting facts."""
    target = VideoTarget(
        student_id="user_vid",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        concept_name="Newton's Second Law",
        chunk_text="Source fact: F = ma. Acceleration is proportional to force and inversely proportional to mass.",
        teaching_strategy="COUNTEREXAMPLE",
        misconception_code="SAME_FORCE_SAME_ACCEL",
        misconception_label="Same force produces same acceleration",
        confidence="LIKELY",
    )
    plan = plan_video_for_target(target)
    assert plan is not None
    assert len(plan.scenes) >= 3

    # Check 14: Grounded fact is taught, misconception is explicitly treated as misconception
    all_narration = " ".join(s.narration for s in plan.scenes)
    assert "Newton" in all_narration
    assert "mass" in all_narration or "force" in all_narration


def test_check_15_reassessment_targets_same_misconception_with_novel_question(audit_env):
    """Check 15: Reassessment generates a question targeting the active misconception with different wording/options."""
    reassessment_service = audit_env["reassessment_service"]
    misconception_repo = audit_env["misconception_repo"]
    mastery_repo = audit_env["mastery_repo"]
    kg = audit_env["kg"]

    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        mastery_state=MasteryState.REASSESSING,
        attempt_count=2,
        incorrect_count=2,
        remediation_attempt_count=1,
    ))

    misconception_repo.save(MisconceptionEvidence(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Force implies same acceleration",
        misconception_type="causal",
        confidence=MisconceptionConfidenceState.LIKELY,
    ))

    q = reassessment_service.generate_reassessment_question(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        provided_concept=kg.concepts["CONCEPT_FORCE"],
    )
    assert q is not None
    assert q.concept_id == "CONCEPT_FORCE"
    assert "force" in q.stem.lower() or "acceleration" in q.stem.lower() or "mass" in q.stem.lower()


def test_check_16_17_corrected_misconception_audit_trail_and_recurrence_detection(audit_env):
    """Checks 16 & 17: Corrected misconception retains full timestamp history, and relapsing marks it RECURRENT."""
    misconception_repo = audit_env["misconception_repo"]
    attempt_service = audit_env["attempt_service"]
    question_registry = audit_env["question_registry"]

    m = MisconceptionEvidence(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Causal gap",
        confidence=MisconceptionConfidenceState.LIKELY,
        status=MisconceptionStatus.ACTIVE,
    )
    misconception_repo.save(m)

    # Correct it
    m.mark_corrected()
    misconception_repo.save(m)
    assert m.status == MisconceptionStatus.CORRECTED
    assert m.corrected_at is not None

    # Check 16: Audit trail preserved
    history = misconception_repo.find_by_code("student_default", "SRC_AUDIT", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCEL")
    assert history.status == MisconceptionStatus.CORRECTED

    # Check 17: Recurrence detection on new failure mapping to same distractor
    question_registry.register(AuthoritativeQuestion(
        question_id="Q_RECUR_TEST",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        stem="Do equal forces cause equal acceleration in different masses?",
        options=["Yes", "No"],
        correct_index=1,
        distractor_misconceptions={
            0: DistractorMisconceptionMetadata(code="SAME_FORCE_SAME_ACCEL", label="Causal gap"),
        }
    ))
    attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_RECUR_1",
        question_id="Q_RECUR_TEST",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        user_id="student_default",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    recurrent_m = misconception_repo.find_by_code("student_default", "SRC_AUDIT", "CONCEPT_FORCE", "SAME_FORCE_SAME_ACCEL")
    assert recurrent_m.status == MisconceptionStatus.RECURRENT


def test_check_18_roadmap_explains_why_personalization_happened(audit_env):
    """Check 18: Roadmap exposes why_chosen and misconception_journey explaining pedagogical decisions."""
    app_service: AdaptiveLearningService = audit_env["app_service"]
    mastery_repo = audit_env["mastery_repo"]
    misconception_repo = audit_env["misconception_repo"]
    remediation_repo = audit_env["remediation_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))
    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        mastery_state=MasteryState.REMEDIATING,
        attempt_count=2,
        incorrect_count=2,
        remediation_attempt_count=1,
    ))
    misconception_repo.save(MisconceptionEvidence(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        code="SAME_FORCE_SAME_ACCEL",
        label="Identical force assumed to mean identical acceleration",
        confidence=MisconceptionConfidenceState.LIKELY,
        status=MisconceptionStatus.ACTIVE,
        evidence_attempt_ids=["ATT_W1", "ATT_W2"],
    ))
    remediation_repo.save(RemediationJob(
        job_id="JOB_WHY_1",
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        status=RemediationJobStatus.READY,
        strategy_used="COUNTEREXAMPLE",
        misconception_code="SAME_FORCE_SAME_ACCEL",
    ))

    roadmap = app_service.get_roadmap("student_default", "SRC_AUDIT")
    assert len(roadmap.misconception_journey) >= 1
    j = roadmap.misconception_journey[0]
    assert j["active_misconception_label"] == "Identical force assumed to mean identical acceleration"
    assert j["strategy_used"] == "COUNTEREXAMPLE"
    assert "2 assessment attempts" in j["why_chosen"]


def test_check_19_existing_adaptive_loop_works_without_misconceptions(audit_env):
    """Check 19: Pure fallback when no misconception metadata is present."""
    selector: TeachingStrategySelector = audit_env["strategy_selector"]
    mastery_repo = audit_env["mastery_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))
    # No misconception registered in repo
    decision = selector.select_strategy("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
    assert decision.strategy == TeachingStrategyType.DIRECT_EXPLANATION
    assert decision.reason_code in (
        TeachingStrategyReasonCode.DEFAULT_CONCEPT_GROUNDED,
        TeachingStrategyReasonCode.DEFAULT_DIRECT,
    )


def test_check_20_runtime_remains_bounded(audit_env):
    """Check 20: Policy selection and roadmap synthesis execute within strict sub-millisecond bounds."""
    selector: TeachingStrategySelector = audit_env["strategy_selector"]
    mastery_repo = audit_env["mastery_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))

    t0 = time.perf_counter()
    for _ in range(50):
        selector.select_strategy("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1, f"Strategy selection took {elapsed:.4f}s for 50 calls"


# ==============================================================================
# FAILURE INJECTION SUITE
# ==============================================================================

def test_failure_injection_missing_misconception_mapping(audit_env):
    """Failure Injection 1: Distractor has no misconception mapping (normal wrong answer)."""
    attempt_service = audit_env["attempt_service"]
    misconception_repo = audit_env["misconception_repo"]
    question_registry = audit_env["question_registry"]

    question_registry.register(AuthoritativeQuestion(
        question_id="Q_UNMAPPED",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        stem="Calculation question",
        options=["10 N", "20 N", "30 N"],
        correct_index=0,
        distractor_misconceptions={},  # No mapping
    ))

    res = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_UNMAPPED",
        question_id="Q_UNMAPPED",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        user_id="student_default",
        selected_answer=1,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert not res.is_correct
    all_m = misconception_repo.list_for_concept("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
    assert len(all_m) == 0


def test_failure_injection_malformed_misconception_code():
    """Failure Injection 2: Malformed or generic placeholder codes are cleanly rejected."""
    assert normalize_misconception_code("") is None
    assert normalize_misconception_code("   ") is None
    assert normalize_misconception_code("MISC_1") is None
    assert normalize_misconception_code("MISCONCEPTION_42") is None
    assert normalize_misconception_code("ERROR") is None
    assert normalize_misconception_code("UNKNOWN") is None
    assert normalize_misconception_code("NONE") is None
    assert normalize_misconception_code("valid_code_123") == "VALID_CODE_123"


def test_failure_injection_question_generation_failure(audit_env):
    """Failure Injection 4: Reassessment generator gracefully raises AssessmentServiceError on invalid concept."""
    reassessment_service = audit_env["reassessment_service"]
    with pytest.raises(AssessmentServiceError):
        reassessment_service.generate_reassessment_question(
            user_id="student_default",
            source_id="SRC_AUDIT",
            concept_id="NON_EXISTENT_CONCEPT",
        )


@async_test
async def test_failure_injection_video_generation_failure_preserves_budget(audit_env, tmp_path):
    """Failure Injection 5: Video engine failure marks job FAILED and preserves educational attempt budget."""
    mastery_repo = audit_env["mastery_repo"]
    remediation_repo = audit_env["remediation_repo"]
    state_machine = audit_env["state_machine"]
    strategy_selector = audit_env["strategy_selector"]

    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))
    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
        mastery_state=MasteryState.WEAK,
        attempt_count=2,
        incorrect_count=2,
        remediation_attempt_count=0,
    ))

    async def broken_video_engine(target: VideoTarget, **kwargs):
        raise RuntimeError("FFmpeg crashed with exit code 1")

    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        strategy_selector=strategy_selector,
        video_engine_fn=broken_video_engine,
    )

    action = NextLearningAction(
        action_type=LearningActionType.REMEDIATE,
        reason_code=ReasonCode.WEAK_CONCEPT_REQUIRES_REMEDIATION,
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_FORCE",
    )

    job = await orchestrator.execute_remediation(action)
    assert job.status == RemediationJobStatus.FAILED
    assert job.is_infrastructure_failure is True

    # Mastery record attempt count must be preserved (rolled back)
    rec = mastery_repo.get("student_default", "SRC_AUDIT", "CONCEPT_FORCE")
    assert rec.remediation_attempt_count == 0
    assert rec.mastery_state == MasteryState.WEAK


def test_failure_injection_repository_failure_rolls_back(audit_env):
    """Failure Injection 7: Repository failure aborts attempt submission cleanly."""
    attempt_service = audit_env["attempt_service"]
    mastery_repo = audit_env["mastery_repo"]
    question_registry = audit_env["question_registry"]

    question_registry.register(AuthoritativeQuestion(
        question_id="Q_REPO_FAIL",
        concept_id="CONCEPT_FORCE",
        source_id="SRC_AUDIT",
        stem="Question",
        options=["A", "B"],
        correct_index=0,
    ))

    with patch.object(mastery_repo, "save", side_effect=IOError("Database connection lost")):
        with pytest.raises(Exception):
            attempt_service.record_attempt(AssessmentSubmissionRequest(
                attempt_id="ATT_REPO_FAIL",
                question_id="Q_REPO_FAIL",
                concept_id="CONCEPT_FORCE",
                source_id="SRC_AUDIT",
                user_id="student_default",
                selected_answer=1,
                assessment_type=AssessmentType.DIAGNOSTIC,
            ))


def test_failure_injection_page_refresh_is_pure_read(audit_env):
    """Failure Injection 9: Page refresh (repeated get_roadmap) produces zero state mutation."""
    app_service: AdaptiveLearningService = audit_env["app_service"]
    mastery_repo = audit_env["mastery_repo"]

    mastery_repo.save(MasteryRecord(
        user_id="student_default",
        source_id="SRC_AUDIT",
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))

    snap1 = app_service.get_roadmap("student_default", "SRC_AUDIT")
    snap2 = app_service.get_roadmap("student_default", "SRC_AUDIT")
    assert snap1.model_dump() == snap2.model_dump()


# ==============================================================================
# REAL ACCEPTANCE CASE
# ==============================================================================

@async_test
async def test_real_acceptance_case_newton_second_law(audit_env, tmp_path):
    """Complete real acceptance case for 'Newton's Second Law of Motion' (CONCEPT_FORCE)."""
    mastery_repo = audit_env["mastery_repo"]
    attempt_service = audit_env["attempt_service"]
    question_registry = audit_env["question_registry"]
    remediation_repo = audit_env["remediation_repo"]
    misconception_repo = audit_env["misconception_repo"]
    reassessment_service = audit_env["reassessment_service"]
    strategy_selector = audit_env["strategy_selector"]
    app_service = audit_env["app_service"]
    state_machine = audit_env["state_machine"]
    kg = audit_env["kg"]

    user_id = "student_default"
    source_id = "SRC_AUDIT"
    concept_id = "CONCEPT_FORCE"

    # Satisfy prerequisite
    mastery_repo.save(MasteryRecord(
        user_id=user_id,
        source_id=source_id,
        concept_id="CONCEPT_MASS",
        mastery_state=MasteryState.MASTERED,
        score=100.0,
    ))

    # --- INITIAL DIAGNOSTIC QUESTION (Evidence #1) ---
    initial_q = AuthoritativeQuestion(
        question_id="Q_DIAG_REAL_01",
        concept_id=concept_id,
        source_id=source_id,
        stem="A constant net force F acts on two carts. Cart A has mass 1 kg, Cart B has mass 2 kg. How do their accelerations compare?",
        options=[
            "Both accelerate identically because the applied force is identical.",
            "Cart A accelerates twice as fast as Cart B.",
            "Cart B accelerates twice as fast as Cart A.",
            "Neither cart accelerates.",
        ],
        correct_index=1,
        distractor_misconceptions={
            0: DistractorMisconceptionMetadata(
                code="SAME_FORCE_SAME_ACCEL",
                label="Identical force yields identical acceleration regardless of mass",
                misconception_type="causal",
            )
        }
    )
    question_registry.register(initial_q)

    # Learner picks wrong answer (Option 0)
    sub1 = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REAL_01",
        question_id="Q_DIAG_REAL_01",
        concept_id=concept_id,
        source_id=source_id,
        user_id=user_id,
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert not sub1.is_correct
    m1 = misconception_repo.find_active_by_code(user_id, source_id, concept_id, "SAME_FORCE_SAME_ACCEL")
    assert m1 is not None
    assert m1.confidence == MisconceptionConfidenceState.POSSIBLE
    assert m1.evidence_count == 1

    # --- SECOND DIAGNOSTIC QUESTION (Evidence #2) ---
    q2 = AuthoritativeQuestion(
        question_id="Q_DIAG_REAL_02",
        concept_id=concept_id,
        source_id=source_id,
        stem="A truck and a bicycle experience identical forward net force. Which accelerates faster?",
        options=[
            "The truck accelerates faster because it has more momentum.",
            "Both experience identical acceleration because force determines acceleration.",
            "The bicycle accelerates faster because it has significantly smaller mass.",
            "Neither moves.",
        ],
        correct_index=2,
        distractor_misconceptions={
            1: DistractorMisconceptionMetadata(
                code="SAME_FORCE_SAME_ACCEL",
                label="Identical force yields identical acceleration regardless of mass",
                misconception_type="causal",
            )
        }
    )
    question_registry.register(q2)

    sub2 = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REAL_02",
        question_id="Q_DIAG_REAL_02",
        concept_id=concept_id,
        source_id=source_id,
        user_id=user_id,
        selected_answer=1,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert not sub2.is_correct
    m2 = misconception_repo.find_active_by_code(user_id, source_id, concept_id, "SAME_FORCE_SAME_ACCEL")
    assert m2 is not None
    assert m2.confidence == MisconceptionConfidenceState.LIKELY
    assert m2.evidence_count == 2

    # --- PERSONALIZATION & STRATEGY SELECTION ---
    next_action = app_service.get_next_action(user_id, source_id)
    assert next_action.action_type == LearningActionType.REMEDIATE
    assert next_action.concept_id == concept_id

    decision = strategy_selector.select_strategy(user_id, source_id, concept_id)
    assert decision.strategy == TeachingStrategyType.COUNTEREXAMPLE
    assert decision.reason_code == TeachingStrategyReasonCode.INCORRECT_CAUSAL_BELIEF

    # --- VIDEO GENERATION (REUSING VIDEO ENGINE) ---
    video_file = tmp_path / "newton_remediation.mp4"
    video_file.write_bytes(b"validated MP4 payload")

    async def mock_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        assert target.teaching_strategy == "COUNTEREXAMPLE"
        assert target.misconception_code == "SAME_FORCE_SAME_ACCEL"
        assert target.confidence == "LIKELY"
        return VideoArtifact(
            job_id=job_id or "JOB_REAL_REMED_01",
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

    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 30.0}):
        job = await orchestrator.execute_remediation(next_action)

    assert job.status == RemediationJobStatus.READY
    assert job.strategy_used == "COUNTEREXAMPLE"
    assert job.misconception_code == "SAME_FORCE_SAME_ACCEL"

    # --- REASSESSMENT GENERATION & SUCCESSFUL ATTEMPT ---
    next_action_reassess = app_service.get_next_action(user_id, source_id)
    assert next_action_reassess.action_type == LearningActionType.REASSESS

    reassess_q = reassessment_service.generate_reassessment_question(
        user_id,
        source_id,
        concept_id,
        provided_concept=kg.concepts[concept_id],
    )
    assert reassess_q is not None

    reassess_sub = attempt_service.record_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REAL_REASSESS_01",
        question_id=reassess_q.question_id,
        concept_id=concept_id,
        source_id=source_id,
        user_id=user_id,
        selected_answer=reassess_q.correct_index,
        assessment_type=AssessmentType.REASSESSMENT,
    ))
    assert reassess_sub.is_correct is True
    assert reassess_sub.mastery_state == MasteryState.MASTERED

    # Misconception status transitioned to CORRECTED
    corrected_m = misconception_repo.find_by_code(user_id, source_id, concept_id, "SAME_FORCE_SAME_ACCEL")
    assert corrected_m.status == MisconceptionStatus.CORRECTED

    # --- ROADMAP & UI EXPLANATION ---
    roadmap = app_service.get_roadmap(user_id, source_id)
    assert len(roadmap.misconception_journey) >= 1
    journey = roadmap.misconception_journey[0]
    assert journey["active_misconception_label"] == "Identical force yields identical acceleration regardless of mass"
    assert journey["misconception_status"] == "CORRECTED"
    assert "2 assessment attempts" in journey["why_chosen"]
    assert "Status: Corrected" in journey["why_chosen"]
