"""Durable focused sessions; verified repositories and immutable exact source scope."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Literal, TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import Field, JsonValue, TypeAdapter, ValidationError

from ..core.supabase import (
    SupabaseAuthenticationError,
    SupabaseConflict,
    SupabaseResponseError,
    SupabaseUnavailable,
)
from .knowledge_models import Contract, Identifier, ConceptView, KnowledgeMap
from .knowledge_service import KnowledgeService
from .repositories.knowledge_repository import KnowledgeRepository, KnowledgeError
from .security.source_scope import SourceScope

SESSION_LIST_LIMIT = 50
MAX_SESSION_CONCEPTS = 64
if TYPE_CHECKING:
    from .qa.canonical_answer import CanonicalQARequest
State = Literal["ACTIVE", "COMPLETED", "ABANDONED"]
Action = Literal["create", "selection", "resume", "complete", "abandon"]


class SessionSelection(Contract):
    topic_id: Identifier
    subtopic_id: Identifier | None = None


class CreateLearningSession(SessionSelection):
    session_id: UUID = Field(default_factory=uuid4)
    source_id: Identifier
    source_version: Annotated[int, Field(ge=1, le=2**31 - 1)]


class LearningSession(SourceScope):
    session_id: UUID
    topic_id: Identifier
    subtopic_id: Identifier | None
    selected_concept_ids: Annotated[
        list[Identifier], Field(min_length=1, max_length=MAX_SESSION_CONCEPTS)
    ]
    state: State
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime


class SessionView(Contract):
    session: LearningSession
    topic_title: str
    subtopic_title: str | None
    concepts: list[ConceptView]


class SessionQARequest(Contract):
    session_id: UUID
    question: Annotated[str, Field(min_length=1, max_length=4000)]
    source_id: Identifier | None = None
    source_version: Annotated[int, Field(ge=1, le=2**31 - 1)] | None = None
    topic_id: Identifier | None = None
    subtopic_id: Identifier | None = None
    concept_ids: (
        Annotated[list[Identifier], Field(min_length=1, max_length=64)] | None
    ) = None


class SessionStorageUnavailable(RuntimeError):
    """Safe explicit condition, including an approved-but-not-deployed session schema."""


class LearningSessionRepository:
    """Caller JWT Data API SELECT; all mutations use the bounded ownership-checking RPC."""

    def __init__(self, context: KnowledgeRepository) -> None:
        self.context = context

    def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, JsonValue] | None = None,
    ) -> JsonValue:
        try:
            return self.context.runtime.user_request(
                method, path, token=self.context._token, params=params, body=body
            )
        except SupabaseConflict:
            raise KnowledgeError("CONFLICT") from None
        except SupabaseAuthenticationError:
            raise KnowledgeError("NOT_FOUND") from None
        except (SupabaseResponseError, SupabaseUnavailable):
            raise SessionStorageUnavailable("SESSION_STORAGE_UNAVAILABLE") from None

    def _decode(self, value: JsonValue) -> LearningSession:
        try:
            row = LearningSession.model_validate_json(json.dumps(value))
        except ValidationError:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
        if row.user_id != self.context.user.user_id:
            raise KnowledgeError("NOT_FOUND")
        return row

    def list(self) -> list[LearningSession]:
        value = self._request(
            "GET",
            "/rest/v1/learning_sessions",
            params={
                "select": "*",
                "user_id": "eq." + str(self.context.user.user_id),
                "order": "last_active_at.desc,session_id",
                "limit": str(SESSION_LIST_LIMIT),
            },
        )
        if not isinstance(value, list):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return [self._decode(row) for row in value]

    def get(self, session_id: UUID) -> LearningSession:
        value = self._request(
            "GET",
            "/rest/v1/learning_sessions",
            params={
                "select": "*",
                "user_id": "eq." + str(self.context.user.user_id),
                "session_id": "eq." + str(session_id),
                "limit": "1",
            },
        )
        if not isinstance(value, list):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        if not value:
            raise KnowledgeError("NOT_FOUND")
        row = self._decode(value[0])
        if row.session_id != session_id:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return row

    def mutate(
        self,
        action: Action,
        session_id: UUID,
        *,
        scope: SourceScope | None = None,
        selection: SessionSelection | None = None,
        concepts: list[str] | None = None,
    ) -> LearningSession:
        body: dict[str, JsonValue] = {
            "p_action": action,
            "p_session_id": str(session_id),
        }
        if scope is not None and selection is not None and concepts is not None:
            body.update(
                p_source_id=scope.source_id,
                p_source_version=scope.source_version,
                p_topic_id=selection.topic_id,
                p_subtopic_id=selection.subtopic_id,
                p_concept_ids=concepts,
            )
        row = self._decode(
            self._request(
                "POST", "/rest/v1/rpc/visualai_mutate_learning_session", body=body
            )
        )
        if (
            row.session_id != session_id
            or scope is not None
            and (row.source_id, row.source_version)
            != (scope.source_id, scope.source_version)
        ):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        if selection is not None and (
            row.topic_id,
            row.subtopic_id,
            row.selected_concept_ids,
        ) != (selection.topic_id, selection.subtopic_id, concepts):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return row


class LearningSessionService:
    """Resolve one canonical map per operation; never query vectors or local session files."""

    def __init__(
        self,
        context: KnowledgeRepository,
        repository: LearningSessionRepository | None = None,
    ) -> None:
        self.context = context
        self.repository = repository or LearningSessionRepository(context)

    def _selection(
        self, scope: SourceScope, selection: SessionSelection
    ) -> tuple[KnowledgeMap, list[ConceptView], str, str | None]:
        mapping = KnowledgeService(self.context).get_knowledge_map(scope)
        if mapping.knowledge_state != "READY":
            raise KnowledgeError("NOT_READY")
        topic = next(
            (t for t in mapping.topics if t.topic_id == selection.topic_id), None
        )
        if topic is None:
            raise KnowledgeError("NOT_FOUND")
        subs = [
            s
            for s in topic.subtopics
            if selection.subtopic_id is None or s.subtopic_id == selection.subtopic_id
        ]
        if not subs:
            raise KnowledgeError("NOT_FOUND")
        concepts = [c for s in subs for c in s.concepts]
        if not concepts:
            raise KnowledgeError("NOT_READY")
        if len(concepts) > MAX_SESSION_CONCEPTS:
            raise KnowledgeError("PAYLOAD_TOO_LARGE")
        return (
            mapping,
            concepts,
            topic.title,
            subs[0].title if selection.subtopic_id else None,
        )

    def create(self, request: CreateLearningSession) -> LearningSession:
        scope = self.context.scope(request.source_id, request.source_version)
        selection = SessionSelection(
            topic_id=request.topic_id, subtopic_id=request.subtopic_id
        )
        _, concepts, _, _ = self._selection(scope, selection)
        return self.repository.mutate(
            "create",
            request.session_id,
            scope=scope,
            selection=selection,
            concepts=sorted(c.concept_id for c in concepts),
        )

    def get(self, session_id: UUID) -> SessionView:
        row = self.repository.get(session_id)
        _, concepts, title, subtitle = self._selection(
            self.context.scope(row.source_id, row.source_version),
            SessionSelection(topic_id=row.topic_id, subtopic_id=row.subtopic_id),
        )
        if sorted(c.concept_id for c in concepts) != row.selected_concept_ids:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return SessionView(
            session=row, topic_title=title, subtopic_title=subtitle, concepts=concepts
        )

    def transition(
        self, session_id: UUID, action: Literal["resume", "complete", "abandon"]
    ) -> LearningSession:
        row = self.repository.get(session_id)
        target = {"resume": "ACTIVE", "complete": "COMPLETED", "abandon": "ABANDONED"}[
            action
        ]
        if row.state != "ACTIVE" and row.state != target:
            raise KnowledgeError("CONFLICT")
        if row.state != "ACTIVE" and action == "resume":
            raise KnowledgeError("CONFLICT")
        result = self.repository.mutate(action, session_id)
        if result.state != target or (
            result.source_id,
            result.source_version,
            result.topic_id,
            result.subtopic_id,
            result.selected_concept_ids,
        ) != (
            row.source_id,
            row.source_version,
            row.topic_id,
            row.subtopic_id,
            row.selected_concept_ids,
        ):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return result

    def change_selection(
        self, session_id: UUID, selection: SessionSelection
    ) -> LearningSession:
        row = self.repository.get(session_id)
        if row.state != "ACTIVE":
            raise KnowledgeError("CONFLICT")
        scope = self.context.scope(row.source_id, row.source_version)
        _, concepts, _, _ = self._selection(scope, selection)
        return self.repository.mutate(
            "selection",
            session_id,
            scope=scope,
            selection=selection,
            concepts=sorted(c.concept_id for c in concepts),
        )

    def qa_request(self, request: SessionQARequest) -> CanonicalQARequest:
        """Stored exact selection is authoritative; optional concept narrowing cannot broaden it."""
        from .qa.canonical_answer import CanonicalQARequest

        row = self.repository.get(request.session_id)
        if row.state != "ACTIVE":
            raise KnowledgeError("CONFLICT")
        for field in ("source_id", "source_version", "topic_id", "subtopic_id"):
            if field in request.model_fields_set and getattr(request, field) != getattr(
                row, field
            ):
                raise KnowledgeError("INVALID_SCOPE")
        concepts = (
            request.concept_ids
            if request.concept_ids is not None
            else row.selected_concept_ids
        )
        if not set(concepts) <= set(row.selected_concept_ids):
            raise KnowledgeError("INVALID_SCOPE")
        # RetrievalService independently revalidates canonical selector associations.
        return CanonicalQARequest(
            source_id=row.source_id,
            source_version=row.source_version,
            question=request.question,
            topic_id=row.topic_id,
            subtopic_id=row.subtopic_id,
            concept_ids=concepts,
        )
