"""Deterministic canonical hierarchy and compatibility projections; no generation."""

from __future__ import annotations

import logging
from collections import defaultdict
from uuid import UUID
from pydantic import ValidationError

from .knowledge_models import (
    CanonicalConcept,
    CanonicalKnowledge,
    ConceptView,
    EvidenceSummary,
    KnowledgeMap,
    KnowledgeSnapshot,
    SnapshotCommit,
    SubtopicView,
    TopicView,
)
from .repositories.knowledge_repository import (
    KnowledgeError,
    KnowledgeRepository,
    MAX_SNAPSHOT_BYTES,
)
from .schemas import ConceptNode, KnowledgeGraph
from .concept_id import ConceptCollisionError
from .security.source_scope import SourceScope

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Validate complete parent/evidence/edge consistency before exposing READY."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate(data: CanonicalKnowledge) -> None:
        topics = {row.topic_id: row for row in data.topics}
        subs = {row.subtopic_id: row for row in data.subtopics}
        concepts = {row.concept_id: row for row in data.concepts}
        invalid = (
            not topics
            or not subs
            or not concepts
            or len(topics) != len(data.topics)
            or len(subs) != len(data.subtopics)
            or len(concepts) != len(data.concepts)
            or len({t.sequence for t in data.topics}) != len(data.topics)
            or len({(s.topic_id, s.sequence) for s in data.subtopics})
            != len(data.subtopics)
            or len({(c.subtopic_id, c.sequence) for c in data.concepts})
            != len(data.concepts)
            or any(s.topic_id not in topics for s in data.subtopics)
            or any(
                c.subtopic_id not in subs or c.sequence is None for c in data.concepts
            )
        )
        if invalid:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        supports: dict[str, set[str]] = defaultdict(set)
        prerequisite_evidence: dict[str, set[str]] = defaultdict(set)
        links: set[tuple[str, str, str]] = set()
        for e in data.evidence:
            key = (e.content_id, e.concept_id, e.support_kind)
            if e.concept_id not in concepts or key in links:
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
            links.add(key)
            supports[e.concept_id].add(e.content_id)
            if e.support_kind == "prerequisite_evidence":
                prerequisite_evidence[e.concept_id].add(e.content_id)
        for concept in data.concepts:
            if (
                not supports[concept.concept_id]
                or set(concept.source_content_ids) != supports[concept.concept_id]
            ):
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        dependencies: dict[str, set[str]] = {cid: set() for cid in concepts}
        edge_keys: set[tuple[str, str, str]] = set()
        for edge in data.relationships:
            key = (edge.concept_id, edge.related_concept_id, edge.relationship_type)
            valid_evidence = (
                prerequisite_evidence
                if edge.relationship_type == "prerequisite"
                else supports
            )
            if (
                edge.concept_id not in concepts
                or edge.related_concept_id not in concepts
                or edge.concept_id == edge.related_concept_id
                or key in edge_keys
                or not edge.evidence_content_ids
                or not set(edge.evidence_content_ids) <= valid_evidence[edge.concept_id]
            ):
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
            edge_keys.add(key)
            if edge.relationship_type == "prerequisite":
                dependencies[edge.concept_id].add(edge.related_concept_id)
        while dependencies:
            removable = {cid for cid, required in dependencies.items() if not required}
            if not removable:
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
            dependencies = {
                cid: required - removable
                for cid, required in dependencies.items()
                if cid not in removable
            }

    def _views(self, data: CanonicalKnowledge) -> dict[str, ConceptView]:
        evidence: dict[str, list[EvidenceSummary]] = defaultdict(list)
        prerequisites: dict[str, list[str]] = defaultdict(list)
        related: dict[str, list[str]] = defaultdict(list)
        for e in sorted(
            data.evidence,
            key=lambda row: (
                row.content.sequence_index,
                row.content_id,
                row.support_kind,
            ),
        ):
            evidence[e.concept_id].append(
                EvidenceSummary(
                    content_id=e.content_id,
                    support_kind=e.support_kind,
                    char_start=e.char_start,
                    char_end=e.char_end,
                    extraction_confidence=e.extraction_confidence,
                    content=e.content,
                )
            )
        for edge in data.relationships:
            (prerequisites if edge.relationship_type == "prerequisite" else related)[
                edge.concept_id
            ].append(edge.related_concept_id)
        result: dict[str, ConceptView] = {}
        for c in data.concepts:
            if c.sequence is None:
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
            result[c.concept_id] = ConceptView(
                concept_id=c.concept_id,
                name=c.name,
                definition=c.definition,
                sequence=c.sequence,
                source_content_ids=sorted(c.source_content_ids),
                evidence=evidence[c.concept_id],
                prerequisite_concept_ids=sorted(prerequisites[c.concept_id]),
                related_concept_ids=sorted(related[c.concept_id]),
                provenance_kind=c.provenance.get("provenance_kind", "SOURCE_GROUNDED"),
            )
        return result

    def get_knowledge_map(
        self, scope: SourceScope, *, request_id: str | None = None
    ) -> KnowledgeMap:
        try:
            data = self.repository.get_complete_knowledge_map(scope)
            state = data.readiness
            topics: list[TopicView] = []
            if state.knowledge_state == "READY":
                self._validate(data)
                views = self._views(data)
                concepts_by_sub: dict[str, list[CanonicalConcept]] = defaultdict(list)
                subs_by_topic: dict[str, list[SubtopicView]] = defaultdict(list)
                for c in data.concepts:
                    if c.subtopic_id is None:
                        raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
                    concepts_by_sub[c.subtopic_id].append(c)
                for sub in sorted(
                    data.subtopics, key=lambda row: (row.sequence, row.subtopic_id)
                ):
                    ordered = sorted(
                        concepts_by_sub[sub.subtopic_id],
                        key=lambda row: (row.sequence, row.concept_id),
                    )
                    subs_by_topic[sub.topic_id].append(
                        SubtopicView(
                            subtopic_id=sub.subtopic_id,
                            title=sub.title,
                            description=sub.description,
                            sequence=sub.sequence,
                            concepts=[views[c.concept_id] for c in ordered],
                            provenance_kind=sub.provenance.get("provenance_kind", "SOURCE_GROUNDED"),
                        )
                    )
                for topic in sorted(
                    data.topics, key=lambda row: (row.sequence, row.topic_id)
                ):
                    topics.append(
                        TopicView(
                            topic_id=topic.topic_id,
                            title=topic.title,
                            description=topic.description,
                            sequence=topic.sequence,
                            subtopics=subs_by_topic[topic.topic_id],
                            provenance_kind=topic.provenance.get("provenance_kind", "SOURCE_GROUNDED"),
                        )
                    )
            result = KnowledgeMap(
                **scope.model_dump(),
                knowledge_state=state.knowledge_state,
                schema_version=state.schema_version,
                topics=topics,
                diagnostic_code=(
                    "KNOWLEDGE_BUILD_FAILED"
                    if state.knowledge_state == "FAILED"
                    else None
                ),
            )
            if len(result.model_dump_json().encode()) > MAX_SNAPSHOT_BYTES:
                raise KnowledgeError("PAYLOAD_TOO_LARGE")
            logger.info(
                "knowledge_read",
                extra={
                    "request_id": request_id,
                    "source_id": scope.source_id,
                    "source_version": scope.source_version,
                    "knowledge_state": state.knowledge_state,
                    "topic_count": len(topics),
                    "subtopic_count": len(data.subtopics),
                    "database_calls": self.repository.database_calls,
                    "provider_outcome": "SUCCESS",
                },
            )
            return result
        except KnowledgeError as error:
            logger.warning(
                "knowledge_read_failed",
                extra={
                    "request_id": request_id,
                    "source_id": scope.source_id,
                    "source_version": scope.source_version,
                    "provider_outcome": error.code,
                },
            )
            raise

    def get_topic(self, scope: SourceScope, topic_id: str) -> TopicView:
        result = self.get_knowledge_map(scope)
        if result.knowledge_state != "READY":
            raise KnowledgeError("NOT_READY")
        for topic in result.topics:
            if topic.topic_id == topic_id:
                return topic
        raise KnowledgeError("NOT_FOUND")

    def get_subtopic(
        self, scope: SourceScope, subtopic_id: str, *, topic_id: str | None = None
    ) -> SubtopicView:
        result = self.get_knowledge_map(scope)
        if result.knowledge_state != "READY":
            raise KnowledgeError("NOT_READY")
        for topic in result.topics:
            for sub in topic.subtopics:
                if sub.subtopic_id == subtopic_id and (
                    topic_id is None or topic.topic_id == topic_id
                ):
                    return sub
        raise KnowledgeError("NOT_FOUND")

    def get_concept(self, scope: SourceScope, concept_id: str) -> ConceptView:
        result = self.get_knowledge_map(scope)
        if result.knowledge_state != "READY":
            raise KnowledgeError("NOT_READY")
        for topic in result.topics:
            for sub in topic.subtopics:
                for concept in sub.concepts:
                    if concept.concept_id == concept_id:
                        return concept
        raise KnowledgeError("NOT_FOUND")

    def project_graph(self, scope: SourceScope) -> KnowledgeGraph:
        result = self.get_knowledge_map(scope)
        if result.knowledge_state != "READY":
            raise KnowledgeError("NOT_READY")
        nodes: dict[str, ConceptNode] = {}
        for topic in result.topics:
            for sub in topic.subtopics:
                for c in sub.concepts:
                    try:
                        node = ConceptNode(
                            concept_id=c.concept_id,
                            name=c.name,
                            definition=c.definition,
                            source_content_ids=c.source_content_ids,
                            prerequisite_concept_ids=c.prerequisite_concept_ids,
                            related_concept_ids=c.related_concept_ids,
                        )
                    except ValidationError:
                        raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
                    if (
                        node.concept_id != c.concept_id
                        or node.prerequisite_concept_ids != c.prerequisite_concept_ids
                        or node.related_concept_ids != c.related_concept_ids
                    ):
                        raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
                    nodes[c.concept_id] = node
        try:
            graph = KnowledgeGraph(concepts=nodes)
        except (ValidationError, ConceptCollisionError):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
        if set(graph.concepts) != set(nodes):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return graph

    def commit_snapshot(
        self, scope: SourceScope, operation_id: UUID, snapshot: KnowledgeSnapshot
    ) -> SnapshotCommit:
        fields = {
            "operation_id": str(operation_id),
            "source_id": scope.source_id,
            "source_version": scope.source_version,
        }
        try:
            committed = self.repository.commit_snapshot(scope, operation_id, snapshot)
        except KnowledgeError as error:
            logger.warning(
                "knowledge_commit_failed",
                extra=fields | {"provider_outcome": error.code},
            )
            raise
        logger.info(
            "knowledge_commit",
            extra=fields
            | {
                "knowledge_state": committed.knowledge_state,
                "topic_count": len(snapshot.topics),
                "subtopic_count": len(snapshot.subtopics),
                "provider_outcome": "SUCCESS",
            },
        )
        return committed
