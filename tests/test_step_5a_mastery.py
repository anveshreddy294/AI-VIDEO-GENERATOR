"""Unit and domain tests for Step 5A: Deterministic Mastery Model & State Machine."""

import pytest
from app.services.mastery import (
    DomainInvariantViolation,
    InMemoryMasteryRepository,
    InvalidStateTransitionError,
    MasteryConfig,
    MasteryRecord,
    MasteryRepository,
    MasteryState,
    MasteryStateMachine,
)


@pytest.fixture
def sm() -> MasteryStateMachine:
    return MasteryStateMachine(
        MasteryConfig(mastery_threshold=80.0, weak_threshold=60.0, max_remediation_attempts=3)
    )


@pytest.fixture
def repo() -> InMemoryMasteryRepository:
    return InMemoryMasteryRepository()


def test_01_new_concept_initial_state_is_unassessed(sm: MasteryStateMachine):
    """Test 1: A newly discovered grounded concept initializes in UNASSESSED state."""
    rec = sm.create_initial_record(
        user_id="learner_001",
        source_id="SRC_DOC_A",
        concept_id="CONCEPT_NEWTON_FIRST",
    )
    assert rec.mastery_state == MasteryState.UNASSESSED
    assert rec.attempt_count == 0
    assert rec.correct_count == 0
    assert rec.incorrect_count == 0
    assert rec.mastery_score == 0.0
    assert rec.remediation_attempt_count == 0
    assert rec.processed_attempt_ids == []


def test_02_assessment_started_transitions_to_learning(sm: MasteryStateMachine):
    """Test 2: Starting an assessment on an unassessed concept moves to LEARNING."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    rec = sm.start_assessment(rec, session_id="SESS_01")
    assert rec.mastery_state == MasteryState.LEARNING
    assert rec.session_id == "SESS_01"


def test_03_incorrect_diagnostic_transitions_to_weak(sm: MasteryStateMachine):
    """Test 3: An incorrect diagnostic assessment transitions concept directly to WEAK."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    rec = sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=False)
    assert rec.mastery_state == MasteryState.WEAK
    assert rec.attempt_count == 1
    assert rec.correct_count == 0
    assert rec.incorrect_count == 1
    assert rec.mastery_score == 0.0
    assert "ATT_01" in rec.processed_attempt_ids


def test_04_correct_validated_assessment_updates_counts_and_score(sm: MasteryStateMachine):
    """Test 4: Correct assessment updates counts and deterministic arithmetic score."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    rec = sm.start_assessment(rec)
    rec = sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=True)

    assert rec.attempt_count == 1
    assert rec.correct_count == 1
    assert rec.incorrect_count == 0
    assert rec.mastery_score == 100.0
    assert rec.mastery_state == MasteryState.MASTERED


def test_05_incorrect_validated_assessment_updates_counts(sm: MasteryStateMachine):
    """Test 5: Incorrect assessment increments incorrect_count and attempt_count."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=True)
    sm.record_assessment_attempt(rec, attempt_id="ATT_02", is_correct=False)

    assert rec.attempt_count == 2
    assert rec.correct_count == 1
    assert rec.incorrect_count == 1
    assert rec.mastery_score == 50.0
    assert rec.mastery_state == MasteryState.WEAK


def test_06_mastery_threshold_triggers_mastered(sm: MasteryStateMachine):
    """Test 6: Sufficient validated mastery (score >= threshold) transitions to MASTERED."""
    # 4 correct out of 5 attempts = 80.0% >= 80.0% threshold
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=False)  # score: 0.0 -> WEAK
    sm.record_assessment_attempt(rec, attempt_id="ATT_02", is_correct=True)   # score: 50.0 -> WEAK
    sm.record_assessment_attempt(rec, attempt_id="ATT_03", is_correct=True)   # score: 66.67 -> WEAK
    sm.record_assessment_attempt(rec, attempt_id="ATT_04", is_correct=True)   # score: 75.0 -> WEAK
    sm.record_assessment_attempt(rec, attempt_id="ATT_05", is_correct=True)   # score: 80.0 -> MASTERED

    assert rec.attempt_count == 5
    assert rec.correct_count == 4
    assert rec.incorrect_count == 1
    assert rec.mastery_score == 80.0
    assert rec.mastery_state == MasteryState.MASTERED


def test_07_remediation_assignment_transitions_to_remediating(sm: MasteryStateMachine):
    """Test 7: Assigning remediation moves WEAK concept to REMEDIATING and increments attempt count."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=False)
    assert rec.mastery_state == MasteryState.WEAK

    rec = sm.assign_remediation(rec)
    assert rec.mastery_state == MasteryState.REMEDIATING
    assert rec.remediation_attempt_count == 1
    assert rec.last_remediation_at is not None


def test_08_reassessment_start_transitions_to_reassessing(sm: MasteryStateMachine):
    """Test 8: Initiating reassessment moves REMEDIATING concept to REASSESSING."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=False)
    sm.assign_remediation(rec)
    assert rec.mastery_state == MasteryState.REMEDIATING

    rec = sm.start_reassessment(rec)
    assert rec.mastery_state == MasteryState.REASSESSING


def test_09_retry_limit_exceeded_transitions_to_needs_support(sm: MasteryStateMachine):
    """Test 9: Bounded remediation enforces MAX_REMEDIATION_ATTEMPTS and sets NEEDS_SUPPORT."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=False)  # WEAK

    # Attempt 1
    sm.assign_remediation(rec)  # remediation_attempt_count = 1 -> REMEDIATING
    sm.start_reassessment(rec)   # REASSESSING
    sm.record_assessment_attempt(rec, attempt_id="ATT_02", is_correct=False)  # WEAK

    # Attempt 2
    sm.assign_remediation(rec)  # remediation_attempt_count = 2 -> REMEDIATING
    sm.start_reassessment(rec)   # REASSESSING
    sm.record_assessment_attempt(rec, attempt_id="ATT_03", is_correct=False)  # WEAK

    # Attempt 3 (Max limit)
    sm.assign_remediation(rec)  # remediation_attempt_count = 3 -> REMEDIATING
    sm.start_reassessment(rec)   # REASSESSING
    sm.record_assessment_attempt(rec, attempt_id="ATT_04", is_correct=False)  # Attempts exhausted!

    assert rec.remediation_attempt_count == 3
    assert rec.mastery_state == MasteryState.NEEDS_SUPPORT

    # Further remediation assignment is bounded and cannot loop; a 4th attempt is strictly blocked
    with pytest.raises(InvalidStateTransitionError):
        sm.assign_remediation(rec)
    assert rec.mastery_state == MasteryState.NEEDS_SUPPORT
    assert rec.remediation_attempt_count == 3


def test_10_invalid_transitions_rejected(sm: MasteryStateMachine):
    """Test 10: Invalid transitions are rejected with InvalidStateTransitionError."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    sm.record_assessment_attempt(rec, attempt_id="ATT_01", is_correct=True)
    assert rec.mastery_state == MasteryState.MASTERED

    # MASTERED cannot transition directly to REMEDIATING
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(rec, MasteryState.REMEDIATING)

    with pytest.raises(InvalidStateTransitionError):
        sm.assign_remediation(rec)

    # UNASSESSED cannot transition directly to REASSESSING
    rec2 = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_SECOND")
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(rec2, MasteryState.REASSESSING)


def test_11_duplicate_attempt_is_idempotent(sm: MasteryStateMachine):
    """Test 11: Submitting identical attempt_id does not double-count or mutate state."""
    rec = sm.create_initial_record("learner_001", "SRC_DOC_A", "CONCEPT_NEWTON_FIRST")
    sm.record_assessment_attempt(rec, attempt_id="ATT_UNIQUE_999", is_correct=True)

    assert rec.attempt_count == 1
    assert rec.correct_count == 1
    assert rec.mastery_score == 100.0

    # Resubmit duplicate attempt
    sm.record_assessment_attempt(rec, attempt_id="ATT_UNIQUE_999", is_correct=True)
    sm.record_assessment_attempt(rec, attempt_id="ATT_UNIQUE_999", is_correct=False)

    assert rec.attempt_count == 1
    assert rec.correct_count == 1
    assert rec.incorrect_count == 0
    assert rec.mastery_score == 100.0


def test_12_cross_user_records_remain_independent(repo: InMemoryMasteryRepository, sm: MasteryStateMachine):
    """Test 12: Concept mastery records for different users are completely isolated."""
    rec_user_a = sm.create_initial_record("user_alpha", "SRC_DOC_1", "CONCEPT_X")
    sm.record_assessment_attempt(rec_user_a, attempt_id="ATT_A1", is_correct=True)
    repo.save(rec_user_a)

    rec_user_b = sm.create_initial_record("user_beta", "SRC_DOC_1", "CONCEPT_X")
    sm.record_assessment_attempt(rec_user_b, attempt_id="ATT_B1", is_correct=False)
    repo.save(rec_user_b)

    retrieved_a = repo.get("user_alpha", "SRC_DOC_1", "CONCEPT_X")
    retrieved_b = repo.get("user_beta", "SRC_DOC_1", "CONCEPT_X")

    assert retrieved_a is not None and retrieved_b is not None
    assert retrieved_a.user_id == "user_alpha"
    assert retrieved_a.mastery_state == MasteryState.MASTERED
    assert retrieved_a.correct_count == 1

    assert retrieved_b.user_id == "user_beta"
    assert retrieved_b.mastery_state == MasteryState.WEAK
    assert retrieved_b.correct_count == 0


def test_13_cross_source_records_remain_independent(repo: InMemoryMasteryRepository, sm: MasteryStateMachine):
    """Test 13: Concept mastery records across different sources remain strictly partitioned."""
    rec_src_1 = sm.create_initial_record("user_alpha", "SRC_DOC_1", "CONCEPT_SHARED")
    sm.record_assessment_attempt(rec_src_1, attempt_id="ATT_S1", is_correct=True)
    repo.save(rec_src_1)

    rec_src_2 = sm.create_initial_record("user_alpha", "SRC_DOC_2", "CONCEPT_SHARED")
    sm.record_assessment_attempt(rec_src_2, attempt_id="ATT_S2", is_correct=False)
    repo.save(rec_src_2)

    list_src_1 = repo.list_by_user_source("user_alpha", "SRC_DOC_1")
    list_src_2 = repo.list_by_user_source("user_alpha", "SRC_DOC_2")

    assert len(list_src_1) == 1
    assert list_src_1[0].source_id == "SRC_DOC_1"
    assert list_src_1[0].mastery_state == MasteryState.MASTERED

    assert len(list_src_2) == 1
    assert list_src_2[0].source_id == "SRC_DOC_2"
    assert list_src_2[0].mastery_state == MasteryState.WEAK


def test_14_domain_invariants_cannot_be_violated():
    """Test 14: Relational count invariants and field validations raise DomainInvariantViolation."""
    # Empty user_id
    with pytest.raises(DomainInvariantViolation):
        MasteryRecord(
            user_id="",
            source_id="SRC_1",
            concept_id="CON_1",
            attempt_count=0,
            correct_count=0,
            incorrect_count=0,
        )

    # Empty concept_id
    with pytest.raises(DomainInvariantViolation):
        MasteryRecord(
            user_id="USR_1",
            source_id="SRC_1",
            concept_id="  ",
            attempt_count=0,
            correct_count=0,
            incorrect_count=0,
        )

    # correct_count + incorrect_count != attempt_count
    with pytest.raises(DomainInvariantViolation):
        MasteryRecord(
            user_id="USR_1",
            source_id="SRC_1",
            concept_id="CON_1",
            attempt_count=5,
            correct_count=3,
            incorrect_count=1,  # 3 + 1 != 5
        )

    # correct_count > attempt_count
    with pytest.raises(DomainInvariantViolation):
        MasteryRecord(
            user_id="USR_1",
            source_id="SRC_1",
            concept_id="CON_1",
            attempt_count=2,
            correct_count=3,
            incorrect_count=0,
        )

    # mastery_score out of range
    with pytest.raises(DomainInvariantViolation):
        MasteryRecord(
            user_id="USR_1",
            source_id="SRC_1",
            concept_id="CON_1",
            attempt_count=1,
            correct_count=1,
            incorrect_count=0,
            mastery_score=150.0,
        )
