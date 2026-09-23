"""Step 5A State Machine — Deterministic Mastery Transitions & Learning Lifecycle.

Governs state transitions for concept mastery according to strictly enforced
deterministic rules, bounded remediation retry limits, and idempotency protection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Set

from .models import (
    DomainInvariantViolation,
    InvalidStateTransitionError,
    MasteryConfig,
    MasteryRecord,
    MasteryState,
)

# Explicitly allowed state transitions: CurrentState -> Set[NextState]
ALLOWED_TRANSITIONS: Mapping[MasteryState, Set[MasteryState]] = {
    MasteryState.UNASSESSED: {
        MasteryState.LEARNING,
        MasteryState.WEAK,
        MasteryState.MASTERED,
    },
    MasteryState.LEARNING: {
        MasteryState.WEAK,
        MasteryState.MASTERED,
    },
    MasteryState.WEAK: {
        MasteryState.REMEDIATING,
        MasteryState.NEEDS_SUPPORT,
        MasteryState.LEARNING,
        MasteryState.MASTERED,
    },
    MasteryState.REMEDIATING: {
        MasteryState.REASSESSING,
        MasteryState.NEEDS_SUPPORT,
    },
    MasteryState.REASSESSING: {
        MasteryState.MASTERED,
        MasteryState.WEAK,
        MasteryState.NEEDS_SUPPORT,
    },
    MasteryState.MASTERED: {
        # Protected state: cannot accidentally revert to REMEDIATING or REASSESSING.
        # Regressing to WEAK or LEARNING requires an explicit reassessment/diagnostic failure.
        MasteryState.WEAK,
        MasteryState.LEARNING,
    },
    MasteryState.NEEDS_SUPPORT: {
        # Protected escalation state: requires explicit instructor/support reset.
        MasteryState.LEARNING,
        MasteryState.UNASSESSED,
    },
}


class MasteryStateMachine:
    """Deterministic state machine governing learning progression and mastery states."""

    def __init__(self, config: MasteryConfig | None = None) -> None:
        self.config = config or MasteryConfig()

    def create_initial_record(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        session_id: str | None = None,
    ) -> MasteryRecord:
        """Create a new grounded concept mastery record in UNASSESSED state."""
        return MasteryRecord(
            user_id=user_id,
            source_id=source_id,
            concept_id=concept_id,
            session_id=session_id,
            attempt_count=0,
            correct_count=0,
            incorrect_count=0,
            reassessment_attempt_count=0,
            reassessment_correct_count=0,
            lifetime_accuracy=0.0,
            mastery_score=0.0,
            mastery_state=MasteryState.UNASSESSED,
            remediation_attempt_count=0,
            processed_attempt_ids=[],
        )

    def transition_to(
        self,
        record: MasteryRecord,
        target_state: MasteryState,
        is_validated_reevaluation: bool = False,
    ) -> MasteryRecord:
        """Validate and apply a direct state transition."""
        if record.mastery_state == target_state:
            return record

        # Protection: MASTERED cannot regress via direct manual transition call
        if record.mastery_state == MasteryState.MASTERED:
            if target_state in (MasteryState.WEAK, MasteryState.LEARNING) and not is_validated_reevaluation:
                raise InvalidStateTransitionError(
                    "A MASTERED concept cannot regress via arbitrary direct transition; "
                    "regression must originate from a validated assessment/reevaluation workflow."
                )

        allowed = ALLOWED_TRANSITIONS.get(record.mastery_state, set())
        if target_state not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid transition: cannot transition from {record.mastery_state.value} to {target_state.value}"
            )

        record.mastery_state = target_state
        record.touch()
        return record

    def start_assessment(
        self,
        record: MasteryRecord,
        session_id: str | None = None,
    ) -> MasteryRecord:
        """Begin an assessment session on this concept."""
        if session_id:
            record.session_id = session_id

        if record.mastery_state == MasteryState.UNASSESSED:
            return self.transition_to(record, MasteryState.LEARNING)
        return record

    def assign_remediation(
        self,
        record: MasteryRecord,
        session_id: str | None = None,
    ) -> MasteryRecord:
        """Assign or generate remediation for a weak concept with strict retry bounding."""
        if session_id:
            record.session_id = session_id

        # Disallow assigning remediation to mastered concepts
        if record.mastery_state == MasteryState.MASTERED:
            raise InvalidStateTransitionError(
                "Cannot assign remediation to a concept in MASTERED state."
            )

        # Check bounded remediation retry limit: at most max_remediation_attempts allowed
        if record.remediation_attempt_count >= self.config.max_remediation_attempts or record.mastery_state == MasteryState.NEEDS_SUPPORT:
            if record.mastery_state != MasteryState.NEEDS_SUPPORT:
                self.transition_to(record, MasteryState.NEEDS_SUPPORT)
            raise InvalidStateTransitionError(
                f"Maximum remediation attempts ({self.config.max_remediation_attempts}) exceeded; concept requires human support."
            )

        record.remediation_attempt_count += 1
        record.last_remediation_at = datetime.now(timezone.utc)
        record.touch()

        return self.transition_to(record, MasteryState.REMEDIATING)

    def confirm_remediation(
        self,
        record: MasteryRecord,
        session_id: str | None = None,
    ) -> MasteryRecord:
        """Trusted service boundary: confirms completed remediation and prepares for reassessment."""
        if session_id:
            record.session_id = session_id
        if record.mastery_state != MasteryState.REMEDIATING:
            raise InvalidStateTransitionError(
                f"Cannot confirm remediation from state {record.mastery_state.value}; must be REMEDIATING."
            )
        return self.start_reassessment(record, session_id=session_id)

    def start_reassessment(
        self,
        record: MasteryRecord,
        session_id: str | None = None,
    ) -> MasteryRecord:
        """Initiate post-remediation reassessment."""
        if session_id:
            record.session_id = session_id

        if record.mastery_state != MasteryState.REMEDIATING:
            raise InvalidStateTransitionError(
                f"Cannot start reassessment from state {record.mastery_state.value}; must be REMEDIATING."
            )

        return self.transition_to(record, MasteryState.REASSESSING)

    def record_assessment_attempt(
        self,
        record: MasteryRecord,
        attempt_id: str,
        is_correct: bool,
        session_id: str | None = None,
        assessment_type: Any | None = None,
    ) -> MasteryRecord:
        """Record a validated assessment attempt with idempotency and score updates."""
        if not attempt_id or not attempt_id.strip():
            raise DomainInvariantViolation("attempt_id cannot be empty")

        clean_attempt_id = attempt_id.strip()

        # Idempotency guard: duplicate submissions are no-ops
        if clean_attempt_id in record.processed_attempt_ids:
            return record

        if session_id:
            record.session_id = session_id

        # Update lifetime attempt counters
        record.attempt_count += 1
        if is_correct:
            record.correct_count += 1
        else:
            record.incorrect_count += 1

        record.lifetime_accuracy = round(
            (record.correct_count / record.attempt_count) * 100.0, 2
        )

        # Distinguish reassessment attempts from initial diagnostic/learning attempts
        is_reassessment = (
            (assessment_type is not None and getattr(assessment_type, "value", str(assessment_type)) == "REASSESSMENT")
            or record.mastery_state == MasteryState.REASSESSING
        )

        if is_reassessment:
            record.reassessment_attempt_count += 1
            if is_correct:
                record.reassessment_correct_count += 1
            record.mastery_score = round(
                (record.reassessment_correct_count / record.reassessment_attempt_count) * 100.0, 2
            )
        else:
            record.mastery_score = record.lifetime_accuracy

        record.last_assessed_at = datetime.now(timezone.utc)
        record.processed_attempt_ids.append(clean_attempt_id)
        record.touch()

        # Determine target state based on current state and thresholds
        if record.mastery_state == MasteryState.REASSESSING:
            if is_correct:
                if (
                    record.reassessment_attempt_count >= self.config.min_reassessment_attempts_for_mastery
                    and record.mastery_score >= self.config.mastery_threshold
                ):
                    return self.transition_to(record, MasteryState.MASTERED)
                else:
                    # Check if retry limit reached without reaching mastery
                    if record.remediation_attempt_count >= self.config.max_remediation_attempts:
                        return self.transition_to(record, MasteryState.NEEDS_SUPPORT)
                    # Stay in REASSESSING to collect remaining required evidence
                    return record
            else:
                # Reassessment failed: check if remediation attempts are exhausted
                if record.remediation_attempt_count >= self.config.max_remediation_attempts:
                    return self.transition_to(record, MasteryState.NEEDS_SUPPORT)
                return self.transition_to(record, MasteryState.WEAK)

        # In UNASSESSED or LEARNING:
        if record.mastery_state in (MasteryState.UNASSESSED, MasteryState.LEARNING):
            if is_correct and record.mastery_score >= self.config.mastery_threshold:
                return self.transition_to(record, MasteryState.MASTERED)
            return self.transition_to(record, MasteryState.WEAK)

        # In WEAK:
        if record.mastery_state == MasteryState.WEAK:
            if is_reassessment:
                if (
                    is_correct
                    and record.reassessment_attempt_count >= self.config.min_reassessment_attempts_for_mastery
                    and record.mastery_score >= self.config.mastery_threshold
                ):
                    return self.transition_to(record, MasteryState.MASTERED)
            else:
                if is_correct and record.mastery_score >= self.config.mastery_threshold:
                    return self.transition_to(record, MasteryState.MASTERED)
            # Stays WEAK

        # In MASTERED: regression check via validated reevaluation
        if record.mastery_state == MasteryState.MASTERED:
            if not is_correct or record.mastery_score < self.config.mastery_threshold:
                return self.transition_to(
                    record,
                    MasteryState.WEAK,
                    is_validated_reevaluation=True,
                )

        return record
