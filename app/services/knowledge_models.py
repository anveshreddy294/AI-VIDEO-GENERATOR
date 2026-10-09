"""Canonical scope, evidence and read-only hierarchy contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .schemas import ContentUnit
from .security.source_scope import SourceScope

Identifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
]
Sequence = Annotated[int, Field(strict=True, ge=0)]
SchemaVersion = Annotated[int, Field(strict=True, ge=1, le=1)]
KnowledgeState = Literal["LEGACY_UNMAPPED", "PENDING", "FAILED", "READY"]
SupportKind = Literal["definition", "explanation", "example", "prerequisite_evidence"]
ContentProvenanceKind = Literal["SOURCE_GROUNDED", "AI_ENRICHED"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Topic(SourceScope):
    topic_id: Identifier
    title: str
    description: str | None = None
    sequence: Sequence
    provenance: dict[str, JsonValue]


class Subtopic(SourceScope):
    subtopic_id: Identifier
    topic_id: Identifier
    title: str
    description: str | None = None
    sequence: Sequence
    provenance: dict[str, JsonValue]


class CanonicalConcept(SourceScope):
    concept_id: Identifier
    subtopic_id: Identifier | None
    name: str
    definition: str | None = None
    sequence: Sequence | None
    source_content_ids: list[Identifier]
    provenance: dict[str, JsonValue]


class EvidenceMetadataView(SourceScope):
    """Selected canonical metadata: never text, vectors or local file paths."""

    content_id: Identifier
    page_number: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    slide_number: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    heading_path: list[str]
    chapter: str | None = None
    section: str | None = None
    sequence_index: Sequence
    extraction_method: str
    confidence_score: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class EvidenceMetadata(EvidenceMetadataView):
    """Internal provenance remains intact; public metadata omits arbitrary JSON."""

    provenance: dict[str, JsonValue]


class ConceptEvidence(SourceScope):
    content_id: Identifier
    concept_id: Identifier
    support_kind: SupportKind
    char_start: Sequence | None = None
    char_end: Sequence | None = None
    extraction_confidence: (
        Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None
    ) = None
    provenance: dict[str, JsonValue]
    content: EvidenceMetadata

    @model_validator(mode="after")
    def valid_reference(self) -> ConceptEvidence:
        if (
            self.content.user_id,
            self.content.source_id,
            self.content.source_version,
            self.content.content_id,
        ) != (self.user_id, self.source_id, self.source_version, self.content_id):
            raise ValueError("Evidence scope mismatch")
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("Incomplete evidence span")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end <= self.char_start
        ):
            raise ValueError("Invalid evidence span")
        return self


class ScopedContentUnit(SourceScope):
    """Internal full-content envelope preserving scope without changing ContentUnit."""

    content_id: Identifier
    content: ContentUnit
    provenance: dict[str, JsonValue]

    @model_validator(mode="after")
    def same_content(self) -> ScopedContentUnit:
        if (
            self.content.content_id != self.content_id
            or self.content.source_id != self.source_id
        ):
            raise ValueError("Canonical content identity mismatch")
        return self


class ConceptRelationship(SourceScope):
    concept_id: Identifier
    related_concept_id: Identifier
    relationship_type: Literal["prerequisite", "related"]
    evidence_content_ids: list[Identifier]
    provenance: dict[str, JsonValue]


class KnowledgeReadiness(SourceScope):
    knowledge_state: KnowledgeState
    schema_version: SchemaVersion | None
    operation_id: UUID | None
    payload_hash: str | None
    committed_at: datetime | None
    version_label: str


class CanonicalKnowledge(Contract):
    readiness: KnowledgeReadiness
    topics: list[Topic]
    subtopics: list[Subtopic]
    concepts: list[CanonicalConcept]
    evidence: list[ConceptEvidence]
    relationships: list[ConceptRelationship]


class EvidenceSummary(Contract):
    content_id: Identifier
    support_kind: SupportKind
    char_start: Sequence | None
    char_end: Sequence | None
    extraction_confidence: float | None
    content: EvidenceMetadataView


class ConceptView(Contract):
    concept_id: Identifier
    name: str
    definition: str | None
    sequence: Sequence
    source_content_ids: list[Identifier]
    evidence: list[EvidenceSummary]
    prerequisite_concept_ids: list[Identifier]
    related_concept_ids: list[Identifier]
    provenance_kind: ContentProvenanceKind = "SOURCE_GROUNDED"


class SubtopicView(Contract):
    subtopic_id: Identifier
    title: str
    description: str | None
    sequence: Sequence
    concepts: list[ConceptView]
    provenance_kind: ContentProvenanceKind = "SOURCE_GROUNDED"


class TopicView(Contract):
    topic_id: Identifier
    title: str
    description: str | None
    sequence: Sequence
    subtopics: list[SubtopicView]
    provenance_kind: ContentProvenanceKind = "SOURCE_GROUNDED"


class KnowledgeMap(SourceScope):
    knowledge_state: KnowledgeState
    schema_version: SchemaVersion | None
    topics: list[TopicView] = Field(default_factory=list)
    diagnostic_code: Literal["KNOWLEDGE_BUILD_FAILED"] | None = None


class SnapshotTopic(Contract):
    topic_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=16384)]
    description: str | None = None
    sequence: Sequence
    provenance: dict[str, JsonValue]


class SnapshotSubtopic(SnapshotTopic):
    subtopic_id: Identifier


class SnapshotConcept(Contract):
    concept_id: Identifier
    subtopic_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=16384)]
    definition: str | None = None
    sequence: Sequence
    provenance: dict[str, JsonValue]


class SnapshotEvidence(Contract):
    content_id: Identifier
    concept_id: Identifier
    support_kind: SupportKind
    char_start: Sequence | None = None
    char_end: Sequence | None = None
    extraction_confidence: (
        Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None
    ) = None
    provenance: dict[str, JsonValue]


class SnapshotRelationship(Contract):
    concept_id: Identifier
    related_concept_id: Identifier
    relationship_type: Literal["prerequisite", "related"]
    evidence_content_ids: Annotated[
        list[Identifier], Field(min_length=0, max_length=64)
    ]
    provenance: dict[str, JsonValue]


class KnowledgeSnapshot(Contract):
    schema_version: SchemaVersion
    topics: Annotated[list[SnapshotTopic], Field(min_length=1, max_length=128)]
    subtopics: Annotated[list[SnapshotSubtopic], Field(min_length=1, max_length=512)]
    concepts: Annotated[list[SnapshotConcept], Field(min_length=1, max_length=1024)]
    content_concepts: Annotated[
        list[SnapshotEvidence], Field(min_length=0, max_length=8192)
    ]
    relationships: Annotated[list[SnapshotRelationship], Field(max_length=4096)]


class SnapshotCommit(Contract):
    source_id: str
    source_version: Sequence
    knowledge_state: Literal["READY"]
    schema_version: SchemaVersion
    operation_id: UUID
    payload_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    committed_at: datetime
