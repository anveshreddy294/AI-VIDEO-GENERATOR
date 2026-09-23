"""Step 5B Assessment Attempt Domain Models and Invariants.

Defines the explicit AssessmentAttempt entity and AssessmentType enum.
Server-side grading determines is_correct; client input is never trusted for outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from .models import DomainInvariantViolation


class AssessmentType(str, Enum):
    """Constrained assessment classification types."""

    DIAGNOSTIC = "DIAGNOSTIC"
    REASSESSMENT = "REASSESSMENT"


class AssessmentAttempt(BaseModel):
    """Domain entity representing a single evaluated assessment question attempt."""

    attempt_id: str
    user_id: str
    source_id: str
    session_id: str | None = None
    concept_id: str
    question_id: str
    assessment_type: AssessmentType

    selected_answer: int = Field(ge=0, le=10)
    correct_answer: int = Field(ge=0, le=10)
    is_correct: bool

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    submitted_at: datetime = Field(
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

    @field_validator("attempt_id", "user_id", "source_id", "concept_id", "question_id")
    @classmethod
    def _validate_non_empty(cls, v: str, info: Any) -> str:
        if not v or not v.strip():
            raise DomainInvariantViolation(
                f"Field '{info.field_name}' cannot be empty or whitespace only."
            )
        return v.strip()

    @model_validator(mode="after")
    def _enforce_attempt_invariants(self) -> "AssessmentAttempt":
        """Validate server-side grading consistency."""
        expected_correct = (self.selected_answer == self.correct_answer)
        if self.is_correct != expected_correct:
            raise DomainInvariantViolation(
                f"Inconsistent grading: is_correct is {self.is_correct}, "
                f"but selected_answer ({self.selected_answer}) == correct_answer ({self.correct_answer}) is {expected_correct}."
            )
        return self
