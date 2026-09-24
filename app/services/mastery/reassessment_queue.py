"""Server-side Reassessment Queue and Session Management.

Manages multi-tenant reassessment question batches:
- Keyed by (user_id, source_id, concept_id, cycle)
- Exposes exactly ONE active question at a time
- Coordinates async prefetching without duplicate generation races
- Supports state-machine invalidation when mastery transitions out of REASSESSING
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from .api_schemas import SafeOption
from .question_registry import AuthoritativeQuestion

logger = logging.getLogger(__name__)


@dataclass
class ReassessmentSession:
    """Server-side session for a single reassessment cycle on a concept."""

    user_id: str
    source_id: str
    concept_id: str
    cycle: int
    questions: list[AuthoritativeQuestion] = field(default_factory=list)
    current_index: int = 0
    status: str = "READY"  # GENERATING, READY, COMPLETED, INVALIDATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_task: asyncio.Task[Any] | None = None
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_invalidated(self) -> bool:
        return self.status == "INVALIDATED"

    def get_current_question(self) -> AuthoritativeQuestion | None:
        """Return active AuthoritativeQuestion if available."""
        if self.status != "READY":
            return None
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def get_current_tuple(self) -> tuple[AuthoritativeQuestion, int, int] | None:
        """Return (active_question, question_number, total_questions) if available."""
        q = self.get_current_question()
        if q:
            return q, self.current_index + 1, len(self.questions)
        return None

    def advance(self, answered_question_id: str) -> None:
        """Advance index after an authoritative answer has been graded."""
        if 0 <= self.current_index < len(self.questions):
            if self.questions[self.current_index].question_id == answered_question_id.strip():
                self.current_index += 1
                if self.current_index >= len(self.questions):
                    self.status = "COMPLETED"

    def invalidate(self) -> None:
        """Invalidate all remaining uncompleted questions in this session."""
        self.status = "INVALIDATED"
        if not self.ready_event.is_set():
            self.ready_event.set()


class ReassessmentQueue:
    """Thread-safe server-side registry of reassessment sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ReassessmentSession] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, user_id: str, source_id: str, concept_id: str, cycle: int | None = None) -> str:
        clean_u = user_id.strip()
        clean_s = source_id.strip()
        clean_c = concept_id.strip()
        if cycle is not None:
            return f"{clean_u}:{clean_s}:{clean_c}:{cycle}"
        return f"{clean_u}:{clean_s}:{clean_c}"

    def get_session(
        self, user_id: str, source_id: str, concept_id: str, cycle: int | None = None
    ) -> ReassessmentSession | None:
        """Find session for user, source, concept. If cycle is None, return most recent active session."""
        if cycle is not None:
            key = self._make_key(user_id, source_id, concept_id, cycle)
            return self._sessions.get(key)

        prefix = f"{user_id.strip()}:{source_id.strip()}:{concept_id.strip()}:"
        matching = [s for k, s in self._sessions.items() if k.startswith(prefix)]
        if matching:
            # Sort by cycle descending
            matching.sort(key=lambda s: s.cycle, reverse=True)
            return matching[0]
        return None

    def register_batch(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        cycle: int,
        questions: list[AuthoritativeQuestion],
    ) -> ReassessmentSession:
        """Create and register a new batch session."""
        session = ReassessmentSession(
            user_id=user_id.strip(),
            source_id=source_id.strip(),
            concept_id=concept_id.strip(),
            cycle=cycle,
            questions=questions,
            current_index=0,
            status="READY",
        )
        self.register_session(session)
        return session

    def register_session(self, session: ReassessmentSession) -> None:
        key = self._make_key(session.user_id, session.source_id, session.concept_id, session.cycle)
        self._sessions[key] = session
        session.ready_event.set()

    def advance(self, user_id: str, source_id: str, concept_id: str, answered_question_id: str) -> None:
        """Advance current index in the active session."""
        sess = self.get_session(user_id, source_id, concept_id)
        if sess:
            sess.advance(answered_question_id)

    def invalidate_concept(
        self, user_id: str, source_id: str, concept_id: str
    ) -> int:
        """Invalidate all sessions and remaining questions for concept."""
        return self.invalidate_for_concept(user_id, source_id, concept_id)

    def invalidate_for_concept(
        self, user_id: str, source_id: str, concept_id: str
    ) -> int:
        """Invalidate all sessions and remaining questions for concept."""
        prefix = f"{user_id.strip()}:{source_id.strip()}:{concept_id.strip()}:"
        count = 0
        for k, sess in list(self._sessions.items()):
            if k.startswith(prefix):
                sess.invalidate()
                count += 1
        return count

    def is_stale_or_invalidated(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        question_id: str,
        cycle: int | None = None,
    ) -> bool:
        """Return True if session or question was invalidated or belongs to old cycle."""
        session = self.get_session(user_id, source_id, concept_id, cycle)
        if session is None:
            # If no session registered in queue, question may be an initial diagnostic or standalone
            return False
        if session.status == "INVALIDATED":
            return True
        return False

    def clear(self) -> None:
        self._sessions.clear()
