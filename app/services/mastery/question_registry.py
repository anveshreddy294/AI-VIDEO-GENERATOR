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


@runtime_checkable
class QuestionRegistry(Protocol):
    """Protocol for storing and retrieving authoritative generated questions."""

    def get(self, question_id: str) -> AuthoritativeQuestion | None:
        """Retrieve question by ID."""
        ...

    def register(self, question: AuthoritativeQuestion) -> AuthoritativeQuestion:
        """Register a newly generated question."""
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

    def clear(self) -> None:
        self._questions.clear()
