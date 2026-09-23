"""Step 5A Domain Models — Deterministic Mastery Entity and Invariants.

Defines the core domain entity representing a student's mastery of a single
grounded concept, along with state enumeration, configuration, and strict
domain invariant enforcement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator


class DomainInvariantViolation(ValueError):
    """Raised when an operation violates core domain invariants."""


class InvalidStateTransitionError(ValueError):
    """Raised when an invalid state transition is requested."""


class MasteryState(str, Enum):
    """Explicit lifecycle states for concept mastery tracking."""

    UNASSESSED = "UNASSESSED"
    LEARNING = "LEARNING"
    WEAK = "WEAK"
    REMEDIATING = "REMEDIATING"
    REASSESSING = "REASSESSING"
    MASTERED = "MASTERED"
    NEEDS_SUPPORT = "NEEDS_SUPPORT"


class MasteryConfig(BaseModel):
    """Deterministic configuration parameters for mastery scoring and bounded remediation."""

    mastery_threshold: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Minimum score percentage required to achieve MASTERED state.",
    )
    weak_threshold: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Score percentage below which a concept is marked WEAK.",
    )
    min_remediation_attempts: int = Field(
        default=1,
        description="Minimum remediation attempts required before reassessment.",
    )
    max_remediation_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum allowed remediation attempts before escalating to NEEDS_SUPPORT.",
    )
    min_reassessment_attempts_for_mastery: int = Field(
        default=2,
        ge=1,
        description="Minimum valid reassessment attempts required to demonstrate mastery after remediation.",
    )


class MasteryRecord(BaseModel):
    """Domain model representing mastery of ONE grounded concept by ONE user.

    Strictly references an existing grounded concept ID without duplicating
    source concept definitions.
    """

    user_id: str
    source_id: str
    session_id: str | None = None
    concept_id: str

    attempt_count: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)
    incorrect_count: int = Field(default=0, ge=0)

    reassessment_attempt_count: int = Field(default=0, ge=0)
    reassessment_correct_count: int = Field(default=0, ge=0)
    lifetime_accuracy: float = Field(default=0.0, ge=0.0, le=100.0)

    mastery_score: float = Field(default=0.0, ge=0.0, le=100.0)
    mastery_state: MasteryState = Field(default=MasteryState.UNASSESSED)

    remediation_attempt_count: int = Field(default=0, ge=0)
    processed_attempt_ids: list[str] = Field(default_factory=list)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_assessed_at: datetime | None = None
    last_remediation_at: datetime | None = None

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except Exception as err:
            if isinstance(err, DomainInvariantViolation):
                raise
            # Unwrap DomainInvariantViolation from Pydantic ValidationError
            from pydantic import ValidationError
            if isinstance(err, ValidationError):
                first_msg = err.errors()[0].get("msg", str(err)) if err.errors() else str(err)
                raise DomainInvariantViolation(first_msg) from err
            raise

    @field_validator("user_id", "source_id", "concept_id")
    @classmethod
    def _validate_non_empty_strings(cls, v: str, info: Any) -> str:
        if not v or not v.strip():
            raise DomainInvariantViolation(
                f"Field '{info.field_name}' cannot be empty or whitespace only."
            )
        return v.strip()

    @model_validator(mode="after")
    def _enforce_domain_invariants(self) -> "MasteryRecord":
        """Validate relational invariants across attempt counts and scores."""
        if self.correct_count > self.attempt_count:
            raise DomainInvariantViolation(
                f"correct_count ({self.correct_count}) cannot exceed attempt_count ({self.attempt_count})"
            )
        if self.incorrect_count > self.attempt_count:
            raise DomainInvariantViolation(
                f"incorrect_count ({self.incorrect_count}) cannot exceed attempt_count ({self.attempt_count})"
            )
        if self.correct_count + self.incorrect_count != self.attempt_count:
            raise DomainInvariantViolation(
                f"correct_count ({self.correct_count}) + incorrect_count ({self.incorrect_count}) "
                f"must equal attempt_count ({self.attempt_count})"
            )
        if self.reassessment_correct_count > self.reassessment_attempt_count:
            raise DomainInvariantViolation(
                f"reassessment_correct_count ({self.reassessment_correct_count}) cannot exceed reassessment_attempt_count ({self.reassessment_attempt_count})"
            )
        if self.reassessment_attempt_count > self.attempt_count:
            raise DomainInvariantViolation(
                f"reassessment_attempt_count ({self.reassessment_attempt_count}) cannot exceed total attempt_count ({self.attempt_count})"
            )
        if not (0.0 <= self.mastery_score <= 100.0):
            raise DomainInvariantViolation(
                f"mastery_score ({self.mastery_score}) must be in range [0.0, 100.0]"
            )
        if not (0.0 <= self.lifetime_accuracy <= 100.0):
            raise DomainInvariantViolation(
                f"lifetime_accuracy ({self.lifetime_accuracy}) must be in range [0.0, 100.0]"
            )
        if self.remediation_attempt_count < 0:
            raise DomainInvariantViolation(
                f"remediation_attempt_count ({self.remediation_attempt_count}) cannot be negative"
            )
        return self

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)
