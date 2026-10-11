"""Verified-caller, exact-version canonical reads in local or historical storage."""

from __future__ import annotations

import json
from typing import Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from ...core.supabase import (
    AuthenticatedUser,
    SupabaseConflict,
    SupabaseResponseError,
    SupabaseRuntime,
    SupabaseUnavailable,
)
from ..knowledge_models import (
    CanonicalConcept,
    CanonicalKnowledge,
    ConceptEvidence,
    ConceptRelationship,
    KnowledgeReadiness,
    KnowledgeSnapshot,
    ScopedContentUnit,
    SnapshotCommit,
    Subtopic,
    Topic,
    Identifier,
)
from ..schemas import ContentUnit
from ..security.source_scope import SourceScope, vector_version

Code = Literal[
    "NOT_FOUND",
    "NOT_READY",
    "INVALID_SCOPE",
    "PROVIDER_UNAVAILABLE",
    "INVALID_PROVIDER_RESPONSE",
    "PAYLOAD_TOO_LARGE",
    "CONFLICT",
]
READ_PAGE_SIZE = 500
MAX_READ_ROWS = (
    10000  # Exceeds the deployed maximum 8192 associations; bounded per table.
)
MAX_SNAPSHOT_BYTES = 2097152  # Matches the deployed RPC's 2 MiB limit.
ROWS = TypeAdapter(list[dict[str, JsonValue]])
OBJECT = TypeAdapter(dict[str, JsonValue])
IDENTIFIER = TypeAdapter(Identifier)
Record = TypeVar("Record", bound=BaseModel)
METADATA_COLUMNS = (
    "user_id,source_id,source_version,content_id,page_number,page_start,page_end,"
    "slide_number,timestamp_start,timestamp_end,heading_path,chapter,section,sequence_index,"
    "extraction_method,confidence_score,provenance"
)
SELECTS: dict[str, str] = {
    "topics": "user_id,source_id,source_version,topic_id,title,description,sequence,provenance",
    "subtopics": "user_id,source_id,source_version,subtopic_id,topic_id,title,description,sequence,provenance",
    "concepts": "user_id,source_id,source_version,concept_id,subtopic_id,name,definition,sequence,source_content_ids,provenance",
    "concept_relationships": "user_id,source_id,source_version,concept_id,related_concept_id,relationship_type,evidence_content_ids,provenance",
    "content_concepts": "user_id,source_id,source_version,content_id,concept_id,support_kind,char_start,char_end,extraction_confidence,provenance,content:content_units("
    + METADATA_COLUMNS
    + ")",
    "source_versions": "user_id,source_id,source_version:version,version_label:source_version,knowledge_state,schema_version:knowledge_schema_version,operation_id:knowledge_operation_id,payload_hash:knowledge_payload_hash,committed_at:knowledge_committed_at",
    "content_units": ",".join(ContentUnit.model_fields)
    + ",user_id,source_version",
}
ORDERS = {
    "topics": "sequence,topic_id",
    "subtopics": "topic_id,sequence,subtopic_id",
    "concepts": "subtopic_id,sequence,concept_id",
    "concept_relationships": "concept_id,relationship_type,related_concept_id",
    "content_concepts": "concept_id,content_id,support_kind",
    "source_versions": "version",
    "content_units": "sequence_index,content_id",
}


class KnowledgeError(RuntimeError):
    """Stable application category; never carries upstream bodies or documents."""

    def __init__(self, code: Code) -> None:
        self.code = code
        super().__init__(code)


class KnowledgeRepository:
    """Request-scoped repository: reverify supplied identity and retain caller RLS."""

    def __init__(
        self, user: AuthenticatedUser | None, token: str, runtime: SupabaseRuntime
    ) -> None:
        verified = runtime.verify_user(token)
        if user is not None and verified.user_id != user.user_id:
            raise KnowledgeError("NOT_FOUND")
        self.user = verified
        self._token = token
        from .learning_storage import wrap
        self.runtime = wrap(runtime, verified, token)
        self._scopes: set[SourceScope] = set()
        self.database_calls = 0

    def scope(self, source_id: str, version: int) -> SourceScope:
        try:
            return SourceScope(
                user_id=self.user.user_id, source_id=source_id, source_version=version
            )
        except ValidationError:
            raise KnowledgeError("INVALID_SCOPE") from None

    def _check_owner(self, scope: SourceScope) -> None:
        if not isinstance(scope, SourceScope):
            raise KnowledgeError("INVALID_SCOPE")
        if scope.user_id != self.user.user_id:
            raise KnowledgeError("NOT_FOUND")

    def _identifier(self, value: str) -> str:
        try:
            return IDENTIFIER.validate_python(value, strict=True)
        except ValidationError:
            raise KnowledgeError("INVALID_SCOPE") from None

    def _read(
        self, scope: SourceScope, table: str, filters: dict[str, str] | None = None
    ) -> list[dict[str, JsonValue]]:
        self._check_owner(scope)
        rows: list[dict[str, JsonValue]] = []
        params = {
            "select": SELECTS[table],
            "order": ORDERS[table],
            "limit": str(READ_PAGE_SIZE),
            "user_id": "eq." + str(scope.user_id),
            "source_id": "eq." + scope.source_id,
            "version" if table == "source_versions" else "source_version": "eq."
            + str(scope.source_version),
            **(filters or {}),
        }
        try:
            while len(rows) < MAX_READ_ROWS:
                self.database_calls += 1
                page = ROWS.validate_python(
                    self.runtime.user_request(
                        "GET",
                        "/rest/v1/" + table,
                        token=self._token,
                        params=params | {"offset": str(len(rows))},
                    )
                )
                for row in page:
                    if (
                        row.get("user_id"),
                        row.get("source_id"),
                        row.get("source_version"),
                    ) != (str(scope.user_id), scope.source_id, scope.source_version):
                        raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
                rows.extend(page)
                if len(page) < READ_PAGE_SIZE:
                    return rows
            raise KnowledgeError("PAYLOAD_TOO_LARGE")
        except SupabaseUnavailable:
            raise KnowledgeError("PROVIDER_UNAVAILABLE") from None
        except (SupabaseResponseError, ValidationError):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None

    def _decode(self, model: type[Record], row: dict[str, JsonValue]) -> Record:
        try:
            return model.model_validate_json(json.dumps(row))
        except ValidationError:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None

    def get_knowledge_state(self, scope: SourceScope) -> KnowledgeReadiness:
        rows = self._read(scope, "source_versions")
        if not rows:
            raise KnowledgeError("NOT_FOUND")
        if len(rows) != 1:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        state = self._decode(KnowledgeReadiness, rows[0])
        if state.version_label != vector_version(scope.source_version):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        if state.knowledge_state == "READY" and (
            state.schema_version != 1
            or state.operation_id is None
            or state.payload_hash is None
            or state.committed_at is None
        ):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        self._scopes.add(scope)
        return state

    def _ensure_scope(self, scope: SourceScope) -> None:
        self._check_owner(scope)
        if scope not in self._scopes:
            self.get_knowledge_state(scope)

    def _list(
        self,
        model: type[Record],
        scope: SourceScope,
        table: str,
        filters: dict[str, str] | None = None,
    ) -> list[Record]:
        self._ensure_scope(scope)
        return [self._decode(model, row) for row in self._read(scope, table, filters)]

    def list_topics(self, scope: SourceScope) -> list[Topic]:
        return sorted(
            self._list(Topic, scope, "topics"),
            key=lambda row: (row.sequence, row.topic_id),
        )

    def get_topic(self, scope: SourceScope, topic_id: str) -> Topic | None:
        topic_id = self._identifier(topic_id)
        rows = self._list(Topic, scope, "topics", {"topic_id": "eq." + topic_id})
        return rows[0] if rows else None

    def list_subtopics(
        self, scope: SourceScope, topic_id: str | None = None
    ) -> list[Subtopic]:
        if topic_id is not None:
            topic_id = self._identifier(topic_id)
        rows = self._list(
            Subtopic,
            scope,
            "subtopics",
            {"topic_id": "eq." + topic_id} if topic_id else None,
        )
        return sorted(
            rows, key=lambda row: (row.topic_id, row.sequence, row.subtopic_id)
        )

    def get_subtopic(self, scope: SourceScope, subtopic_id: str) -> Subtopic | None:
        subtopic_id = self._identifier(subtopic_id)
        rows = self._list(
            Subtopic, scope, "subtopics", {"subtopic_id": "eq." + subtopic_id}
        )
        return rows[0] if rows else None

    def list_concepts(
        self,
        scope: SourceScope,
        topic_id: str | None = None,
        subtopic_id: str | None = None,
    ) -> list[CanonicalConcept]:
        filters: dict[str, str] = {}
        if topic_id is not None:
            topic_id = self._identifier(topic_id)
        if subtopic_id is not None:
            subtopic_id = self._identifier(subtopic_id)
        if topic_id:
            subtopics = self.list_subtopics(scope, topic_id)
            allowed = {s.subtopic_id for s in subtopics}
            if subtopic_id and subtopic_id not in allowed:
                raise KnowledgeError("NOT_FOUND")
            if not allowed:
                return []
            # IDs originate from validated canonical records, never raw filter expressions.
            filters["subtopic_id"] = "in.(" + ",".join(sorted(allowed)) + ")"
        if subtopic_id:
            filters["subtopic_id"] = "eq." + subtopic_id
        return sorted(
            self._list(CanonicalConcept, scope, "concepts", filters),
            key=lambda row: (
                row.subtopic_id or "",
                row.sequence if row.sequence is not None else -1,
                row.concept_id,
            ),
        )

    def get_concept(
        self, scope: SourceScope, concept_id: str
    ) -> CanonicalConcept | None:
        concept_id = self._identifier(concept_id)
        rows = self._list(
            CanonicalConcept, scope, "concepts", {"concept_id": "eq." + concept_id}
        )
        return rows[0] if rows else None

    def list_concept_evidence(
        self, scope: SourceScope, concept_id: str
    ) -> list[ConceptEvidence]:
        concept_id = self._identifier(concept_id)
        return self._list(
            ConceptEvidence,
            scope,
            "content_concepts",
            {"concept_id": "eq." + concept_id},
        )

    def list_relationships(
        self, scope: SourceScope, concept_id: str | None = None
    ) -> list[ConceptRelationship]:
        if concept_id is not None:
            concept_id = self._identifier(concept_id)
        rows = self._list(ConceptRelationship, scope, "concept_relationships")
        return [
            row
            for row in rows
            if concept_id is None
            or concept_id in (row.concept_id, row.related_concept_id)
        ]

    def list_scoped_content(self, scope: SourceScope) -> list[ScopedContentUnit]:
        """Paged set hydration for understanding without per-unit database calls."""
        self._ensure_scope(scope)
        result: list[ScopedContentUnit] = []
        for row in self._read(scope, 'content_units'):
            content_id=row.get('content_id')
            if not isinstance(content_id,str): raise KnowledgeError('INVALID_PROVIDER_RESPONSE')
            try:
                result.append(ScopedContentUnit(**scope.model_dump(),content_id=content_id,
                    content=ContentUnit.model_validate({k:v for k,v in row.items() if k in ContentUnit.model_fields}),
                    provenance=OBJECT.validate_python(row['provenance'])))
            except (ValidationError,KeyError):
                raise KnowledgeError('INVALID_PROVIDER_RESPONSE') from None
        return result

    def get_scoped_content(
        self, scope: SourceScope, content_id: str
    ) -> ScopedContentUnit:
        content_id = self._identifier(content_id)
        self._ensure_scope(scope)
        rows = self._read(scope, "content_units", {"content_id": "eq." + content_id})
        if len(rows) != 1:
            raise KnowledgeError("NOT_FOUND")
        row = rows[0]
        try:
            return ScopedContentUnit(
                **scope.model_dump(),
                content_id=content_id,
                content=ContentUnit.model_validate(
                    {k: v for k, v in row.items() if k in ContentUnit.model_fields}
                ),
                provenance=OBJECT.validate_python(row["provenance"]),
            )
        except (ValidationError, KeyError):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None

    def get_complete_knowledge_map(self, scope: SourceScope) -> CanonicalKnowledge:
        state = self.get_knowledge_state(scope)
        if state.knowledge_state != "READY":
            return CanonicalKnowledge(
                readiness=state,
                topics=[],
                subtopics=[],
                concepts=[],
                evidence=[],
                relationships=[],
            )
        return CanonicalKnowledge(
            readiness=state,
            topics=self.list_topics(scope),
            subtopics=self.list_subtopics(scope),
            concepts=self.list_concepts(scope),
            evidence=self._list(ConceptEvidence, scope, "content_concepts"),
            relationships=self.list_relationships(scope),
        )

    def commit_snapshot(
        self, scope: SourceScope, operation_id: UUID, snapshot: KnowledgeSnapshot
    ) -> SnapshotCommit:
        """Internal only. The existing server RPC owns validation, hash and idempotency."""
        if not isinstance(operation_id, UUID) or not isinstance(
            snapshot, KnowledgeSnapshot
        ):
            raise KnowledgeError("INVALID_SCOPE")
        self._ensure_scope(scope)
        body = OBJECT.validate_python(
            snapshot.model_dump(mode="json", exclude_none=True)
        )
        if len(json.dumps(body).encode()) > MAX_SNAPSHOT_BYTES:
            raise KnowledgeError("PAYLOAD_TOO_LARGE")
        try:
            self.database_calls += 1
            result = OBJECT.validate_python(
                self.runtime.user_request(
                    "POST",
                    "/rest/v1/rpc/visualai_commit_knowledge_snapshot",
                    token=self._token,
                    body={
                        "p_source_id": scope.source_id,
                        "p_source_version": scope.source_version,
                        "p_operation_id": str(operation_id),
                        "p_payload": body,
                    },
                )
            )
            committed = self._decode(SnapshotCommit, result)
            if (
                committed.source_id,
                committed.source_version,
                committed.operation_id,
            ) != (scope.source_id, scope.source_version, operation_id):
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
            return committed
        except SupabaseConflict:
            raise KnowledgeError("CONFLICT") from None
        except SupabaseUnavailable:
            raise KnowledgeError("PROVIDER_UNAVAILABLE") from None
        except (SupabaseResponseError, ValidationError):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
