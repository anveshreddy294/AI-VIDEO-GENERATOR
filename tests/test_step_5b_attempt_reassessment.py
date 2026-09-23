"""Unit, isolation, and integration tests for Step 5B: Assessment Attempt Integration + Reassessment Loop."""

import pytest
from app.services.mastery import (
    AssessmentAttempt,
    AssessmentAttemptRepository,
    AssessmentAttemptResult,
    AssessmentAttemptService,
    AssessmentServiceError,
    AssessmentSubmissionRequest,
    AssessmentType,
    AuthoritativeQuestion,
    DomainInvariantViolation,
    GroundingIntegrityError,
    InMemoryAssessmentAttemptRepository,
    InMemoryMasteryRepository,
    InMemoryQuestionRegistry,
    InvalidStateTransitionError,
    MasteryConfig,
    MasteryRecord,
    MasteryRepository,
    MasteryState,
    MasteryStateMachine,
    QuestionRegistry,
    ReassessmentService,
    UnknownQuestionError,
)
from app.services.schemas import ConceptNode


@pytest.fixture
def repos():
    return {
        "attempt_repo": InMemoryAssessmentAttemptRepository(),
        "mastery_repo": InMemoryMasteryRepository(),
        "question_reg": InMemoryQuestionRegistry(),
        "state_machine": MasteryStateMachine(
            MasteryConfig(mastery_threshold=80.0, weak_threshold=60.0, max_remediation_attempts=3)
        ),
    }


@pytest.fixture
def attempt_service(repos) -> AssessmentAttemptService:
    return AssessmentAttemptService(
        attempt_repo=repos["attempt_repo"],
        mastery_repo=repos["mastery_repo"],
        question_registry=repos["question_reg"],
        state_machine=repos["state_machine"],
    )


@pytest.fixture
def reassessment_service(repos) -> ReassessmentService:
    return ReassessmentService(
        mastery_repo=repos["mastery_repo"],
        question_registry=repos["question_reg"],
    )


def _register_dummy_question(
    qreg: QuestionRegistry,
    question_id: str = "Q_01",
    concept_id: str = "CONCEPT_NEWTON",
    source_id: str = "SRC_01",
    user_id: str | None = None,
    session_id: str | None = None,
    correct_index: int = 2,
    stem: str = "What is Newton's First Law?",
) -> AuthoritativeQuestion:
    q = AuthoritativeQuestion(
        question_id=question_id,
        concept_id=concept_id,
        source_id=source_id,
        user_id=user_id,
        session_id=session_id,
        stem=stem,
        options=["Option A", "Option B", "Option C (Correct)", "Option D"],
        correct_index=correct_index,
        difficulty="intermediate",
        explanation="Newton's First Law states inertia.",
    )
    qreg.register(q)
    return q


def test_01_diagnostic_incorrect_transitions_to_weak(attempt_service: AssessmentAttemptService, repos):
    """Test 1: Incorrect diagnostic answer graded server-side transitions concept to WEAK."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_01", correct_index=2)

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=1,  # Incorrect (correct is 2)
        assessment_type=AssessmentType.DIAGNOSTIC,
    )
    result = attempt_service.submit_attempt(req)

    assert result.attempt.is_correct is False
    assert result.attempt.correct_answer == 2
    assert result.attempt.selected_answer == 1
    assert result.mastery.mastery_state == MasteryState.WEAK
    assert result.mastery.attempt_count == 1
    assert result.mastery.incorrect_count == 1
    assert result.mastery.correct_count == 0
    assert result.mastery.mastery_score == 0.0


def test_02_diagnostic_correct_updates_mastery(attempt_service: AssessmentAttemptService, repos):
    """Test 2: Correct diagnostic answer transitions to MASTERED when threshold met."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_01", correct_index=2)

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=2,  # Correct
        assessment_type=AssessmentType.DIAGNOSTIC,
    )
    result = attempt_service.submit_attempt(req)

    assert result.attempt.is_correct is True
    assert result.mastery.mastery_state == MasteryState.MASTERED
    assert result.mastery.attempt_count == 1
    assert result.mastery.correct_count == 1
    assert result.mastery.mastery_score == 100.0


def test_03_authoritative_server_side_grading(attempt_service: AssessmentAttemptService, repos):
    """Test 3: Server evaluates is_correct deterministically based on AuthoritativeQuestion."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_01", correct_index=3)

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=3,
    )
    result = attempt_service.submit_attempt(req)
    assert result.attempt.is_correct is True
    assert result.attempt.correct_answer == 3


def test_04_unknown_question_rejected(attempt_service: AssessmentAttemptService):
    """Test 4: Attempt referencing unknown question_id raises UnknownQuestionError."""
    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_NON_EXISTENT",
        selected_answer=0,
    )
    with pytest.raises(UnknownQuestionError):
        attempt_service.submit_attempt(req)


def test_05_question_concept_mismatch_rejected(attempt_service: AssessmentAttemptService, repos):
    """Test 5: Submitting answer for a question belonging to another concept raises GroundingIntegrityError."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_01")

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_DIFFERENT",  # Mismatch!
        question_id="Q_01",
        selected_answer=2,
    )
    with pytest.raises(GroundingIntegrityError) as exc_info:
        attempt_service.submit_attempt(req)
    assert "belongs to concept" in str(exc_info.value)


def test_06_cross_user_submission_rejected(attempt_service: AssessmentAttemptService, repos):
    """Test 6: Submitting answer for a user-bound question from another user raises GroundingIntegrityError."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_01", user_id="user_alpha")

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_beta",  # Unauthorized foreign user!
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=2,
    )
    with pytest.raises(GroundingIntegrityError) as exc_info:
        attempt_service.submit_attempt(req)
    assert "Cross-user violation" in str(exc_info.value)


def test_07_cross_source_submission_rejected(attempt_service: AssessmentAttemptService, repos):
    """Test 7: Submitting answer for a question bound to another source raises GroundingIntegrityError."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_SOURCE_A")

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_1",
        source_id="SRC_SOURCE_B",  # Mismatch source!
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=2,
    )
    with pytest.raises(GroundingIntegrityError) as exc_info:
        attempt_service.submit_attempt(req)
    assert "Cross-source violation" in str(exc_info.value)


def test_08_cross_session_submission_rejected(attempt_service: AssessmentAttemptService, repos):
    """Test 8: Submitting answer for a session-bound question from another session raises GroundingIntegrityError."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_01", session_id="SESS_AAA")

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_01",
        user_id="user_1",
        source_id="SRC_01",
        session_id="SESS_BBB",  # Mismatched session!
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=2,
    )
    with pytest.raises(GroundingIntegrityError) as exc_info:
        attempt_service.submit_attempt(req)
    assert "Cross-session violation" in str(exc_info.value)


def test_09_duplicate_attempt_is_idempotent(attempt_service: AssessmentAttemptService, repos):
    """Test 9: Resubmitting identical attempt_id returns cached result without double-counting."""
    _register_dummy_question(repos["question_reg"], "Q_01", "CONCEPT_NEWTON", "SRC_01", correct_index=2)

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_IDEMPOTENT_01",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=2,
    )
    res1 = attempt_service.submit_attempt(req)
    assert res1.is_duplicate is False
    assert res1.mastery.attempt_count == 1
    assert res1.mastery.correct_count == 1

    # Second submission with same attempt_id
    res2 = attempt_service.submit_attempt(req)
    assert res2.is_duplicate is True
    assert res2.mastery.attempt_count == 1
    assert res2.mastery.correct_count == 1
    assert res2.attempt.attempt_id == "ATT_IDEMPOTENT_01"


def test_10_reassessment_cannot_begin_before_remediation(reassessment_service: ReassessmentService, repos):
    """Test 10: Reassessment generation is blocked if concept has not completed remediation."""
    # Concept in WEAK state (not yet remediated)
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].transition_to(mastery, MasteryState.WEAK)
    repos["mastery_repo"].save(mastery)

    with pytest.raises(AssessmentServiceError) as exc_info:
        reassessment_service.generate_reassessment_question(
            user_id="user_1",
            source_id="SRC_01",
            concept_id="CONCEPT_NEWTON",
        )
    assert "must be in REASSESSING state" in str(exc_info.value)


def test_11_reassessment_uses_same_concept_and_grounded_evidence(
    reassessment_service: ReassessmentService, repos
):
    """Test 11: Reassessment generation uses the exact same grounded concept and source chunks."""
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].transition_to(mastery, MasteryState.WEAK)
    repos["state_machine"].assign_remediation(mastery)  # REMEDIATING
    repos["state_machine"].confirm_remediation(mastery)  # REASSESSING
    repos["mastery_repo"].save(mastery)

    dummy_concept = ConceptNode(
        concept_id="CONCEPT_NEWTON",
        name="Newton's Second Law",
        definition="F = ma where force equals mass times acceleration.",
    )
    dummy_chunks = [{
        "chunk_id": "CHUNK_01",
        "text": "Newton's Second Law: Force equals mass multiplied by acceleration (F = m * a). Unit of force is Newton.",
    }]

    new_q = reassessment_service.generate_reassessment_question(
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        provided_concept=dummy_concept,
        provided_chunks=dummy_chunks,
    )

    assert new_q.concept_id == "CONCEPT_NEWTON"
    assert new_q.source_id == "SRC_01"
    assert len(new_q.options) == 4
    # Check registered in authoritative registry
    auth_q = repos["question_reg"].get(new_q.question_id)
    assert auth_q is not None
    assert auth_q.concept_id == "CONCEPT_NEWTON"


def test_12_reassessment_question_differs_from_diagnostic(
    reassessment_service: ReassessmentService, repos
):
    """Test 12: Reassessment question has different question_id and stem from diagnostic."""
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].transition_to(mastery, MasteryState.WEAK)
    repos["state_machine"].assign_remediation(mastery)
    repos["state_machine"].confirm_remediation(mastery)
    repos["mastery_repo"].save(mastery)

    prev_q = _register_dummy_question(
        repos["question_reg"],
        question_id="Q_DIAGNOSTIC_PREV",
        concept_id="CONCEPT_NEWTON",
        source_id="SRC_01",
        stem="What is the definition of Newton's Second Law?",
    )

    dummy_concept = ConceptNode(
        concept_id="CONCEPT_NEWTON",
        name="Newton's Second Law",
        definition="F = ma where force equals mass times acceleration.",
    )
    dummy_chunks = [{
        "chunk_id": "CHUNK_01",
        "text": "Newton's Second Law: Force equals mass times acceleration. Applications include calculating rocket thrust and car braking force.",
    }]

    new_q = reassessment_service.generate_reassessment_question(
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        previous_question_id="Q_DIAGNOSTIC_PREV",
        provided_concept=dummy_concept,
        provided_chunks=dummy_chunks,
    )

    assert new_q.question_id != "Q_DIAGNOSTIC_PREV"
    assert new_q.stem.strip().lower() != prev_q.stem.strip().lower()


def test_13_successful_reassessment_transitions_to_mastered(attempt_service: AssessmentAttemptService, repos):
    """Test 13: Passing reassessments reaches threshold with minimum required evidence and transitions to MASTERED."""
    # Setup: Student answered 3 correct and 1 incorrect on diagnostic (score = 75.0% < 80.0% threshold -> WEAK)
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_D1", is_correct=True)
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_D2", is_correct=True)
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_D3", is_correct=True)
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_D4", is_correct=False)
    assert mastery.mastery_state == MasteryState.WEAK
    assert mastery.mastery_score == 75.0

    # Remediation assigned and confirmed -> REASSESSING
    repos["state_machine"].assign_remediation(mastery)
    repos["state_machine"].confirm_remediation(mastery)
    repos["mastery_repo"].save(mastery)

    _register_dummy_question(repos["question_reg"], "Q_REASSESS_01", "CONCEPT_NEWTON", "SRC_01", correct_index=1)
    _register_dummy_question(repos["question_reg"], "Q_REASSESS_02", "CONCEPT_NEWTON", "SRC_01", correct_index=2)

    # First reassessment attempt (1/1 = 100%, but min_reassessment_attempts_for_mastery = 2) -> remains REASSESSING
    req1 = AssessmentSubmissionRequest(
        attempt_id="ATT_R1",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_REASSESS_01",
        selected_answer=1,  # Correct!
        assessment_type=AssessmentType.REASSESSMENT,
    )
    res1 = attempt_service.submit_attempt(req1)
    assert res1.attempt.is_correct is True
    assert res1.mastery.reassessment_attempt_count == 1
    assert res1.mastery.reassessment_correct_count == 1
    assert res1.mastery.mastery_score == 100.0
    assert res1.mastery.mastery_state == MasteryState.REASSESSING

    # Second reassessment attempt (2/2 = 100%, meets min_attempts=2 and threshold=80.0%) -> transitions to MASTERED!
    req2 = AssessmentSubmissionRequest(
        attempt_id="ATT_R2",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_REASSESS_02",
        selected_answer=2,  # Correct!
        assessment_type=AssessmentType.REASSESSMENT,
    )
    res2 = attempt_service.submit_attempt(req2)
    assert res2.attempt.is_correct is True
    assert res2.mastery.reassessment_attempt_count == 2
    assert res2.mastery.reassessment_correct_count == 2
    assert res2.mastery.mastery_score == 100.0
    assert res2.mastery.lifetime_accuracy == round((5 / 6) * 100.0, 2)  # 5 correct out of 6 total attempts = 83.33%
    assert res2.mastery.mastery_state == MasteryState.MASTERED


def test_14_third_unsuccessful_remediation_cycle_reaches_needs_support(
    attempt_service: AssessmentAttemptService, repos
):
    """Test 14: After third unsuccessful reassessment, concept transitions to NEEDS_SUPPORT."""
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_01", is_correct=False)  # WEAK
    repos["mastery_repo"].save(mastery)

    # Cycle 1
    repos["state_machine"].assign_remediation(mastery)  # remediation_count = 1
    repos["state_machine"].confirm_remediation(mastery) # REASSESSING
    repos["mastery_repo"].save(mastery)
    _register_dummy_question(repos["question_reg"], "Q_CYCLE_1", "CONCEPT_NEWTON", "SRC_01", correct_index=1)
    res1 = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_C1", user_id="user_1", source_id="SRC_01", concept_id="CONCEPT_NEWTON",
        question_id="Q_CYCLE_1", selected_answer=0, assessment_type=AssessmentType.REASSESSMENT
    ))
    assert res1.mastery.mastery_state == MasteryState.WEAK

    # Cycle 2
    repos["state_machine"].assign_remediation(res1.mastery)  # remediation_count = 2
    repos["state_machine"].confirm_remediation(res1.mastery) # REASSESSING
    repos["mastery_repo"].save(res1.mastery)
    _register_dummy_question(repos["question_reg"], "Q_CYCLE_2", "CONCEPT_NEWTON", "SRC_01", correct_index=1)
    res2 = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_C2", user_id="user_1", source_id="SRC_01", concept_id="CONCEPT_NEWTON",
        question_id="Q_CYCLE_2", selected_answer=0, assessment_type=AssessmentType.REASSESSMENT
    ))
    assert res2.mastery.mastery_state == MasteryState.WEAK

    # Cycle 3 (Third and final retry limit)
    repos["state_machine"].assign_remediation(res2.mastery)  # remediation_count = 3
    repos["state_machine"].confirm_remediation(res2.mastery) # REASSESSING
    repos["mastery_repo"].save(res2.mastery)
    _register_dummy_question(repos["question_reg"], "Q_CYCLE_3", "CONCEPT_NEWTON", "SRC_01", correct_index=1)
    res3 = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_C3", user_id="user_1", source_id="SRC_01", concept_id="CONCEPT_NEWTON",
        question_id="Q_CYCLE_3", selected_answer=0, assessment_type=AssessmentType.REASSESSMENT
    ))
    # 3rd failure with remediation_count == 3 transitions to NEEDS_SUPPORT!
    assert res3.mastery.mastery_state == MasteryState.NEEDS_SUPPORT
    assert res3.mastery.remediation_attempt_count == 3


def test_15_fourth_remediation_attempt_strictly_blocked(repos):
    """Test 15: Attempting a 4th remediation is strictly blocked with InvalidStateTransitionError."""
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].transition_to(mastery, MasteryState.WEAK)
    mastery.remediation_attempt_count = 3
    mastery.mastery_state = MasteryState.NEEDS_SUPPORT

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        repos["state_machine"].assign_remediation(mastery)
    assert "Maximum remediation attempts (3) exceeded" in str(exc_info.value)
    assert mastery.remediation_attempt_count == 3


def test_16_mastered_cannot_regress_via_arbitrary_transition(repos):
    """Test 16: MASTERED state is protected against direct manual regression."""
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_01", is_correct=True)
    assert mastery.mastery_state == MasteryState.MASTERED

    # Arbitrary transition to WEAK is blocked
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        repos["state_machine"].transition_to(mastery, MasteryState.WEAK)
    assert "A MASTERED concept cannot regress via arbitrary direct transition" in str(exc_info.value)

    # Arbitrary transition to LEARNING is blocked
    with pytest.raises(InvalidStateTransitionError):
        repos["state_machine"].transition_to(mastery, MasteryState.LEARNING)


def test_17_validated_reevaluation_can_intentionally_update_mastered(repos):
    """Test 17: A validated assessment attempt can intentionally reevaluate and regress MASTERED."""
    mastery = repos["state_machine"].create_initial_record("user_1", "SRC_01", "CONCEPT_NEWTON")
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_01", is_correct=True)
    assert mastery.mastery_state == MasteryState.MASTERED

    # Learner fails subsequent validated assessment attempt
    repos["state_machine"].record_assessment_attempt(mastery, "ATT_02", is_correct=False)
    assert mastery.mastery_state == MasteryState.WEAK
    assert mastery.mastery_score == 50.0


def test_18_repository_failure_guarantees_atomicity(repos):
    """Test 18: If mastery save fails, attempt is rolled back to prevent partial mutation."""
    class FailingMasteryRepo(InMemoryMasteryRepository):
        def save(self, record: MasteryRecord) -> MasteryRecord:
            raise RuntimeError("Database connection timed out during mastery write!")

    failing_mastery_repo = FailingMasteryRepo()
    attempt_repo = repos["attempt_repo"]
    qreg = repos["question_reg"]
    _register_dummy_question(qreg, "Q_01", "CONCEPT_NEWTON", "SRC_01", correct_index=2)

    svc = AssessmentAttemptService(
        attempt_repo=attempt_repo,
        mastery_repo=failing_mastery_repo,
        question_registry=qreg,
    )

    req = AssessmentSubmissionRequest(
        attempt_id="ATT_ATOMIC_FAIL",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_01",
        selected_answer=2,
    )

    with pytest.raises(AssessmentServiceError) as exc_info:
        svc.submit_attempt(req)
    assert "rolled back attempt" in str(exc_info.value)

    # Verify attempt was NOT saved
    assert attempt_repo.exists("ATT_ATOMIC_FAIL") is False
    assert attempt_repo.get("ATT_ATOMIC_FAIL") is None


def test_19_realistic_default_mastery_threshold_lifecycle(attempt_service: AssessmentAttemptService, repos):
    """Test 19: Proves default 80% threshold and decoupled reassessment evidence prevents premature mastery and starvation."""
    # Ensure default config is active (mastery_threshold=80.0, weak_threshold=60.0, min_reassessment_attempts_for_mastery=2)
    assert repos["state_machine"].config.mastery_threshold == 80.0
    assert repos["state_machine"].config.weak_threshold == 60.0
    assert repos["state_machine"].config.min_reassessment_attempts_for_mastery == 2

    for i in range(1, 6):
        _register_dummy_question(repos["question_reg"], f"Q_LIFECYCLE_{i}", "CONCEPT_NEWTON", "SRC_01", correct_index=2)

    # Attempt 1: incorrect diagnostic -> score = 0% -> WEAK
    res1 = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REALISTIC_1",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_LIFECYCLE_1",
        selected_answer=0,  # Incorrect
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert res1.attempt.is_correct is False
    assert res1.mastery.attempt_count == 1
    assert res1.mastery.correct_count == 0
    assert res1.mastery.mastery_score == 0.0
    assert res1.mastery.lifetime_accuracy == 0.0
    assert res1.mastery.mastery_state == MasteryState.WEAK

    # Remediation 1
    repos["state_machine"].assign_remediation(res1.mastery)
    repos["state_machine"].confirm_remediation(res1.mastery)
    repos["mastery_repo"].save(res1.mastery)

    # Attempt 2: correct reassessment 1 -> score = 100% on reassessment, lifetime accuracy = 50.0%
    # But only 1 reassessment attempt < min_reassessment_attempts_for_mastery (2) -> NOT MASTERED YET
    res2 = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REALISTIC_2",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_LIFECYCLE_2",
        selected_answer=2,  # Correct
        assessment_type=AssessmentType.REASSESSMENT,
    ))
    assert res2.attempt.is_correct is True
    assert res2.mastery.attempt_count == 2
    assert res2.mastery.correct_count == 1
    assert res2.mastery.lifetime_accuracy == 50.0
    assert res2.mastery.reassessment_attempt_count == 1
    assert res2.mastery.reassessment_correct_count == 1
    assert res2.mastery.mastery_score == 100.0
    # CRITICAL: With only 1 reassessment attempt, state is NOT MASTERED; remains in REASSESSING
    assert res2.mastery.mastery_state != MasteryState.MASTERED
    assert res2.mastery.mastery_state == MasteryState.REASSESSING

    # Attempt 3: correct reassessment 2 -> 2/2 = 100% on reassessment, meets min evidence (2 >= 2) -> MASTERED!
    res3 = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_REALISTIC_3",
        user_id="user_1",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_LIFECYCLE_3",
        selected_answer=2,  # Correct
        assessment_type=AssessmentType.REASSESSMENT,
    ))
    assert res3.attempt.is_correct is True
    assert res3.mastery.attempt_count == 3
    assert res3.mastery.correct_count == 2
    assert res3.mastery.lifetime_accuracy == 66.67
    assert res3.mastery.reassessment_attempt_count == 2
    assert res3.mastery.reassessment_correct_count == 2
    assert res3.mastery.mastery_score == 100.0
    assert res3.mastery.mastery_state == MasteryState.MASTERED


def test_20_liveness_guarantee_post_diagnostic_failure(attempt_service: AssessmentAttemptService, repos):
    """Test 20: Specifically proves that initial diagnostic failure does NOT permanently starve the learner."""
    # Under old cumulative formula: 0/1 (diag) + 3/3 (reassess) = 3/4 = 75% < 80% -> starvation / NEEDS_SUPPORT bug.
    # Under decoupled formula: post-remediation evidence evaluates reassessments and reaches MASTERED within <= 3 cycles.
    _register_dummy_question(repos["question_reg"], "Q_DIAG", "CONCEPT_NEWTON", "SRC_01", correct_index=1)
    _register_dummy_question(repos["question_reg"], "Q_RE1", "CONCEPT_NEWTON", "SRC_01", correct_index=2)
    _register_dummy_question(repos["question_reg"], "Q_RE2", "CONCEPT_NEWTON", "SRC_01", correct_index=3)

    # Diagnostic failed
    d_res = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_DIAG_FAIL",
        user_id="user_live",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_DIAG",
        selected_answer=0,
        assessment_type=AssessmentType.DIAGNOSTIC,
    ))
    assert d_res.mastery.mastery_state == MasteryState.WEAK
    assert d_res.mastery.lifetime_accuracy == 0.0

    # Remediation Cycle 1
    repos["state_machine"].assign_remediation(d_res.mastery)
    repos["state_machine"].confirm_remediation(d_res.mastery)
    repos["mastery_repo"].save(d_res.mastery)

    # Reassessment 1 (Correct)
    r1_res = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_RE1_PASS",
        user_id="user_live",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_RE1",
        selected_answer=2,
        assessment_type=AssessmentType.REASSESSMENT,
    ))
    assert r1_res.mastery.reassessment_attempt_count == 1
    assert r1_res.mastery.mastery_score == 100.0
    assert r1_res.mastery.mastery_state == MasteryState.REASSESSING  # waiting for 2nd evidence point

    # Reassessment 2 (Correct) -> 2/2 reassessments = 100.0% >= 80.0% -> MASTERED!
    r2_res = attempt_service.submit_attempt(AssessmentSubmissionRequest(
        attempt_id="ATT_RE2_PASS",
        user_id="user_live",
        source_id="SRC_01",
        concept_id="CONCEPT_NEWTON",
        question_id="Q_RE2",
        selected_answer=3,
        assessment_type=AssessmentType.REASSESSMENT,
    ))
    assert r2_res.mastery.mastery_state == MasteryState.MASTERED
    assert r2_res.mastery.reassessment_attempt_count == 2
    assert r2_res.mastery.reassessment_correct_count == 2
    assert r2_res.mastery.mastery_score == 100.0
    assert r2_res.mastery.lifetime_accuracy == 66.67  # 2/3 lifetime accuracy preserved
    assert r2_res.mastery.remediation_attempt_count == 1  # Achieved in Cycle 1 <= 3!

