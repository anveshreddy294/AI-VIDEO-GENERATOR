"""Step 5C Domain Models — Deterministic Learning Action, Roadmap & Reason Codes.

Defines the explicit domain models for personalized roadmap representation,
action types, and machine-readable decision codes without LLM synthesis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from .models import DomainInvariantViolation, MasteryState


class LearningActionType(str, Enum):
    """Constrained, deterministic learning action types."""

    ASSESS = "ASSESS"
    LEARN = "LEARN"
    REMEDIATE = "REMEDIATE"
    REASSESS = "REASSESS"
    REVIEW = "REVIEW"
    CONTINUE = "CONTINUE"
    NEEDS_SUPPORT = "NEEDS_SUPPORT"
    COMPLETE = "COMPLETE"


class ReasonCode(str, Enum):
    """Machine-readable reason codes explaining deterministic action selection."""

    REASSESSMENT_PENDING = "REASSESSMENT_PENDING"
    ACTIVE_REMEDIATION = "ACTIVE_REMEDIATION"
    WEAK_CONCEPT_REQUIRES_REMEDIATION = "WEAK_CONCEPT_REQUIRES_REMEDIATION"
    ACTIVE_LEARNING_PENDING_ASSESSMENT = "ACTIVE_LEARNING_PENDING_ASSESSMENT"
    NEXT_GROUNDED_CONCEPT = "NEXT_GROUNDED_CONCEPT"
    PREREQUISITE_NOT_MASTERED = "PREREQUISITE_NOT_MASTERED"
    MANUAL_SUPPORT_REQUIRED = "MANUAL_SUPPORT_REQUIRED"
    ALL_CONCEPTS_MASTERED = "ALL_CONCEPTS_MASTERED"


class NextLearningAction(BaseModel):
    """Deterministic next pedagogical action for a learner on a grounded concept."""

    user_id: str
    source_id: str
    session_id: str | None = None

    concept_id: str | None = None
    action_type: LearningActionType
    reason_code: ReasonCode
    priority: int = Field(default=10, ge=1, le=100)

    mastery_state: MasteryState | None = None
    mastery_score: float | None = None
    lifetime_accuracy: float | None = None

    dependency_status: str = Field(default="NONE")  # "SATISFIED", "UNSATISFIED", "NONE"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except Exception as err:
            if isinstance(err, DomainInvariantViolation):
                raise
            from pydantic import ValidationError
            if isinstance(err, ValidationError):
                first_msg = err.errors()[0].get("msg", str(err)) if err.errors() else str(err)
                raise DomainInvariantViolation(first_msg) from err
            raise

    @field_validator("user_id", "source_id")
    @classmethod
    def _validate_non_empty_identity(cls, v: str, info: Any) -> str:
        if not v or not v.strip():
            raise DomainInvariantViolation(f"Field '{info.field_name}' cannot be empty.")
        return v.strip()

    @model_validator(mode="after")
    def _validate_action_concept_coherence(self) -> "NextLearningAction":
        """Validate concept_id existence relative to action_type."""
        if self.action_type == LearningActionType.COMPLETE:
            # When curriculum is complete, concept_id is legitimately None
            return self
        if not self.concept_id or not self.concept_id.strip():
            raise DomainInvariantViolation(
                f"concept_id cannot be empty when action_type is '{self.action_type.value}'"
            )
        self.concept_id = self.concept_id.strip()
        return self


class LearningRoadmap(BaseModel):
    """Structured, deterministic learning roadmap partitioning all grounded concepts."""

    user_id: str
    source_id: str
    session_id: str | None = None

    mastered_concepts: list[str] = Field(default_factory=list)
    current_concept: str | None = None
    weak_concepts: list[str] = Field(default_factory=list)
    remediating_concepts: list[str] = Field(default_factory=list)
    reassessing_concepts: list[str] = Field(default_factory=list)
    unassessed_concepts: list[str] = Field(default_factory=list)
    blocked_concepts: list[str] = Field(default_factory=list)
    needs_support_concepts: list[str] = Field(default_factory=list)

    completed: bool = Field(default=False)
    next_action: NextLearningAction

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except Exception as err:
            if isinstance(err, DomainInvariantViolation):
                raise
            from pydantic import ValidationError
            if isinstance(err, ValidationError):
                first_msg = err.errors()[0].get("msg", str(err)) if err.errors() else str(err)
                raise DomainInvariantViolation(first_msg) from err
            raise

    @field_validator("user_id", "source_id")
    @classmethod
    def _validate_non_empty_ids(cls, v: str, info: Any) -> str:
        if not v or not v.strip():
            raise DomainInvariantViolation(f"Field '{info.field_name}' cannot be empty.")
        return v.strip()

    @model_validator(mode="after")
    def _validate_completion_invariant(self) -> "LearningRoadmap":
        """Enforce strict completion semantics: completed iff ALL required concepts are mastered."""
        if self.completed:
            if (
                self.weak_concepts
                or self.remediating_concepts
                or self.reassessing_concepts
                or self.unassessed_concepts
                or self.blocked_concepts
                or self.needs_support_concepts
            ):
                raise DomainInvariantViolation(
                    "Roadmap cannot be marked completed=True while unmastered, weak, blocked, "
                    "or NEEDS_SUPPORT concepts remain."
                )
            if self.next_action.action_type != LearningActionType.COMPLETE:
                raise DomainInvariantViolation(
                    "Completed roadmap must specify next_action.action_type == COMPLETE."
                )
        return self
