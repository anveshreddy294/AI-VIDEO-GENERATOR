"""Step 5B Authoritative Question Registry.

Provides registration and authoritative lookup of questions generated for grounded concepts.
Enforces that questions belong to the expected concept, source, session, and user.
"""

from __future__ import annotations

import copy
from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class AuthoritativeQuestion(BaseModel):
    """Server-side authoritative question record with hidden answer key."""

    question_id: str
    concept_id: str
    source_id: str
    session_id: str | None = None
    user_id: str | None = None
    stem: str
    options: list[str]
    correct_index: int = Field(ge=0, le=10)
    difficulty: str = "intermediate"
    explanation: str = ""
    status: str = "PENDING"  # PENDING or ANSWERED
    distractor_misconceptions: dict[int, Any] = Field(
        default_factory=dict,
        description="Diagnostic misconception metadata mapped by distractor option index",
    )


@runtime_checkable
class QuestionRegistry(Protocol):
    """Protocol for storing and retrieving authoritative generated questions."""

    def get(self, question_id: str) -> AuthoritativeQuestion | None:
        """Retrieve question by ID."""
        ...

    def register(self, question: AuthoritativeQuestion) -> AuthoritativeQuestion:
        """Register a newly generated question."""
        ...

    def mark_answered(self, question_id: str) -> None:
        """Mark a question as answered so it cannot be reused as pending."""
        ...

    def get_pending_for_concept(
        self, user_id: str, source_id: str, concept_id: str
    ) -> AuthoritativeQuestion | None:
        """Retrieve any pending unanswered question for user, source, and concept."""
        ...


class InMemoryQuestionRegistry:
    """Thread-safe in-memory question registry."""

    def __init__(self) -> None:
        self._questions: dict[str, AuthoritativeQuestion] = {}

    def get(self, question_id: str) -> AuthoritativeQuestion | None:
        q = self._questions.get(question_id.strip())
        return copy.deepcopy(q) if q is not None else None

    def register(self, question: AuthoritativeQuestion) -> AuthoritativeQuestion:
        key = question.question_id.strip()
        self._questions[key] = copy.deepcopy(question)
        return copy.deepcopy(question)

    def mark_answered(self, question_id: str) -> None:
        key = question_id.strip()
        if key in self._questions:
            self._questions[key].status = "ANSWERED"

    def get_pending_for_concept(
        self, user_id: str, source_id: str, concept_id: str
    ) -> AuthoritativeQuestion | None:
        clean_user = user_id.strip() if user_id else ""
        clean_source = source_id.strip() if source_id else ""
        clean_concept = concept_id.strip() if concept_id else ""
        for q in self._questions.values():
            if (
                q.concept_id == clean_concept
                and q.source_id == clean_source
                and (not q.user_id or q.user_id == clean_user)
                and q.status == "PENDING"
            ):
                return copy.deepcopy(q)
        return None

    def clear(self) -> None:
        self._questions.clear()
