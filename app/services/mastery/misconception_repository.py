"""Step 5 Misconception Repository Boundary (M2).

Provides persistence protocol and in-memory thread-safe implementation for
MisconceptionEvidence entities, ensuring tenant and source isolation.
"""

from __future__ import annotations

import copy
from typing import Protocol, runtime_checkable

from .misconception_models import MisconceptionEvidence, MisconceptionStatus


@runtime_checkable
class MisconceptionRepository(Protocol):
    """Protocol for persisting and retrieving misconception evidence."""

    def get(self, misconception_id: str) -> MisconceptionEvidence | None:
        """Retrieve evidence by primary key ID."""
        ...

    def save(self, evidence: MisconceptionEvidence) -> MisconceptionEvidence:
        """Save or update evidence record."""
        ...

    def list_for_concept(
        self, user_id: str, source_id: str, concept_id: str
    ) -> list[MisconceptionEvidence]:
        """List all misconceptions observed for a specific user, source, and concept."""
        ...

    def list_for_user_source(
        self, user_id: str, source_id: str
    ) -> list[MisconceptionEvidence]:
        """List all misconceptions observed for a specific user and source."""
        ...

    def find_active_by_code(
        self, user_id: str, source_id: str, concept_id: str, misconception_code: str
    ) -> MisconceptionEvidence | None:
        """Find an active or recurrent misconception with this code."""
        ...

    def find_by_code(
        self, user_id: str, source_id: str, concept_id: str, misconception_code: str
    ) -> MisconceptionEvidence | None:
        """Find any misconception record with this code regardless of status."""
        ...

    def clear(self) -> None:
        """Clear all records (primarily for testing)."""
        ...


class InMemoryMisconceptionRepository:
    """Thread-safe in-memory misconception repository."""

    def __init__(self) -> None:
        self._records: dict[str, MisconceptionEvidence] = {}

    def get(self, misconception_id: str) -> MisconceptionEvidence | None:
        rec = self._records.get(misconception_id.strip())
        return copy.deepcopy(rec) if rec is not None else None

    def save(self, evidence: MisconceptionEvidence) -> MisconceptionEvidence:
        key = evidence.misconception_id.strip()
        self._records[key] = copy.deepcopy(evidence)
        return copy.deepcopy(evidence)

    def list_for_concept(
        self, user_id: str, source_id: str, concept_id: str
    ) -> list[MisconceptionEvidence]:
        uid = user_id.strip()
        sid = source_id.strip()
        cid = concept_id.strip()
        results = [
            copy.deepcopy(r)
            for r in self._records.values()
            if r.user_id == uid and r.source_id == sid and r.concept_id == cid
        ]
        results.sort(key=lambda r: r.last_detected_at, reverse=True)
        return results

    def list_for_user_source(
        self, user_id: str, source_id: str
    ) -> list[MisconceptionEvidence]:
        uid = user_id.strip()
        sid = source_id.strip()
        results = [
            copy.deepcopy(r)
            for r in self._records.values()
            if r.user_id == uid and r.source_id == sid
        ]
        results.sort(key=lambda r: r.last_detected_at, reverse=True)
        return results

    def find_active_by_code(
        self, user_id: str, source_id: str, concept_id: str, misconception_code: str
    ) -> MisconceptionEvidence | None:
        uid = user_id.strip()
        sid = source_id.strip()
        cid = concept_id.strip()
        code = misconception_code.strip().upper()
        for r in self._records.values():
            if (
                r.user_id == uid
                and r.source_id == sid
                and r.concept_id == cid
                and r.misconception_code.upper() == code
                and r.status in (MisconceptionStatus.ACTIVE, MisconceptionStatus.RECURRENT)
            ):
                return copy.deepcopy(r)
        return None

    def find_by_code(
        self, user_id: str, source_id: str, concept_id: str, misconception_code: str
    ) -> MisconceptionEvidence | None:
        uid = user_id.strip()
        sid = source_id.strip()
        cid = concept_id.strip()
        code = misconception_code.strip().upper()
        for r in self._records.values():
            if (
                r.user_id == uid
                and r.source_id == sid
                and r.concept_id == cid
                and r.misconception_code.upper() == code
            ):
                return copy.deepcopy(r)
        return None

    def clear(self) -> None:
        self._records.clear()
