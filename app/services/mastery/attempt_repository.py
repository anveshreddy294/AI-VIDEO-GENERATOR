"""Step 5B Assessment Attempt Repository Abstraction.

Defines AssessmentAttemptRepository Protocol and InMemoryAssessmentAttemptRepository.
"""

from __future__ import annotations

import copy
from typing import Protocol, runtime_checkable

from .attempt_models import AssessmentAttempt


@runtime_checkable
class AssessmentAttemptRepository(Protocol):
    """Persistence protocol for storing and querying assessment attempts."""

    def get(self, attempt_id: str) -> AssessmentAttempt | None:
        """Retrieve attempt by unique attempt_id."""
        ...

    def save(self, attempt: AssessmentAttempt) -> AssessmentAttempt:
        """Persist or update an assessment attempt."""
        ...

    def list_for_concept(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
    ) -> list[AssessmentAttempt]:
        """List all attempts for a given user, source, and concept."""
        ...

    def exists(self, attempt_id: str) -> bool:
        """Check whether attempt_id has already been recorded."""
        ...


class InMemoryAssessmentAttemptRepository:
    """Thread-safe in-memory store for assessment attempts."""

    def __init__(self) -> None:
        self._attempts: dict[str, AssessmentAttempt] = {}

    def get(self, attempt_id: str) -> AssessmentAttempt | None:
        att = self._attempts.get(attempt_id.strip())
        return copy.deepcopy(att) if att is not None else None

    def save(self, attempt: AssessmentAttempt) -> AssessmentAttempt:
        key = attempt.attempt_id.strip()
        self._attempts[key] = copy.deepcopy(attempt)
        return copy.deepcopy(attempt)

    def list_for_concept(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
    ) -> list[AssessmentAttempt]:
        uid = user_id.strip()
        sid = source_id.strip()
        cid = concept_id.strip()
        return [
            copy.deepcopy(att)
            for att in self._attempts.values()
            if att.user_id == uid and att.source_id == sid and att.concept_id == cid
        ]

    def exists(self, attempt_id: str) -> bool:
        return attempt_id.strip() in self._attempts

    def clear(self) -> None:
        self._attempts.clear()
