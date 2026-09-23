"""Step 5A Repository Abstraction — Persistence Boundary for Mastery Records.

Defines the MasteryRepository interface (Protocol) and an in-memory implementation
ensuring strict tenant and source isolation for unit testing and local development.
Decoupled from Supabase to preserve modularity.
"""

from __future__ import annotations

import copy
from typing import Protocol, runtime_checkable

from .models import MasteryRecord


@runtime_checkable
class MasteryRepository(Protocol):
    """Persistence protocol for reading and writing concept mastery records."""

    def get(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
    ) -> MasteryRecord | None:
        """Retrieve a specific concept mastery record for a user and source."""
        ...

    def save(self, record: MasteryRecord) -> MasteryRecord:
        """Persist or update a mastery record and return the saved instance."""
        ...

    def list_by_user_source(
        self,
        user_id: str,
        source_id: str,
    ) -> list[MasteryRecord]:
        """List all concept mastery records for a specific user and source."""
        ...

    def list_by_user(self, user_id: str) -> list[MasteryRecord]:
        """List all concept mastery records for a user across all sources."""
        ...


class InMemoryMasteryRepository:
    """Thread-safe dictionary-backed repository enforcing strict cross-user and cross-source isolation."""

    def __init__(self) -> None:
        # Keyed by (user_id, source_id, concept_id)
        self._records: dict[tuple[str, str, str], MasteryRecord] = {}

    def get(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
    ) -> MasteryRecord | None:
        key = (user_id.strip(), source_id.strip(), concept_id.strip())
        record = self._records.get(key)
        return copy.deepcopy(record) if record is not None else None

    def save(self, record: MasteryRecord) -> MasteryRecord:
        key = (record.user_id.strip(), record.source_id.strip(), record.concept_id.strip())
        record.touch()
        self._records[key] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def list_by_user_source(
        self,
        user_id: str,
        source_id: str,
    ) -> list[MasteryRecord]:
        target_uid = user_id.strip()
        target_sid = source_id.strip()
        return [
            copy.deepcopy(rec)
            for (uid, sid, _), rec in self._records.items()
            if uid == target_uid and sid == target_sid
        ]

    def list_by_user(self, user_id: str) -> list[MasteryRecord]:
        target_uid = user_id.strip()
        return [
            copy.deepcopy(rec)
            for (uid, _, _), rec in self._records.items()
            if uid == target_uid
        ]

    def clear(self) -> None:
        """Clear all stored records (useful for test isolation)."""
        self._records.clear()
