"""Prepublication chunk quality uses existing canonical DTOs with honest PENDING readiness."""

from __future__ import annotations

from .educational_chunker import ChunkPolicy, create_educational_chunks, ChunkQuality
from .knowledge_models import (
    CanonicalKnowledge,
    CanonicalConcept,
    ConceptEvidence,
    ConceptRelationship,
    EvidenceMetadata,
    KnowledgeReadiness,
    KnowledgeSnapshot,
    ScopedContentUnit,
    Topic,
    Subtopic,
)
from .repositories.knowledge_repository import KnowledgeError
from .security.source_scope import SourceScope, vector_version


def snapshot_knowledge(
    scope: SourceScope,
    units: list[ScopedContentUnit],
    snapshot: KnowledgeSnapshot,
) -> CanonicalKnowledge:
    """No generated readiness/hash/timestamp and no database/vector side effects."""
    lookup = {unit.content_id: unit for unit in units}
    evidence: list[ConceptEvidence] = []
    for link in snapshot.content_concepts:
        unit = lookup.get(link.content_id)
        if unit is None:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        metadata = EvidenceMetadata(
            **scope.model_dump(),
            provenance=unit.provenance,
            **{
                k: v
                for k, v in unit.content.model_dump().items()
                if k in EvidenceMetadata.model_fields and k != "provenance"
                and k not in SourceScope.model_fields
            },
        )
        evidence.append(
            ConceptEvidence(**scope.model_dump(), **link.model_dump(), content=metadata)
        )
    content_ids = {
        concept.concept_id: sorted(
            {
                e.content_id
                for e in snapshot.content_concepts
                if e.concept_id == concept.concept_id
            }
        )
        for concept in snapshot.concepts
    }
    pending = KnowledgeReadiness(
        **scope.model_dump(),
        knowledge_state="PENDING",
        schema_version=1,
        operation_id=None,
        payload_hash=None,
        committed_at=None,
        version_label=vector_version(scope.source_version),
    )
    data = CanonicalKnowledge(
        readiness=pending,
        topics=[Topic(**scope.model_dump(), **t.model_dump()) for t in snapshot.topics],
        subtopics=[
            Subtopic(**scope.model_dump(), **s.model_dump()) for s in snapshot.subtopics
        ],
        concepts=[
            CanonicalConcept(
                **scope.model_dump(),
                **c.model_dump(),
                source_content_ids=content_ids[c.concept_id],
            )
            for c in snapshot.concepts
        ],
        evidence=evidence,
        relationships=[
            ConceptRelationship(**scope.model_dump(), **e.model_dump())
            for e in snapshot.relationships
        ],
    )
    return data


def validate_snapshot_chunks(
    scope: SourceScope,
    units: list[ScopedContentUnit],
    snapshot: KnowledgeSnapshot,
    policy: ChunkPolicy | None = None,
) -> ChunkQuality:
    """Validate derived evidence boundaries without database/vector side effects."""
    data = snapshot_knowledge(scope, units, snapshot)
    _, quality = create_educational_chunks(scope, units, data, policy, published=False)
    return quality
