"""Pydantic schemas for Step 1 Multimodal Knowledge Ingestion.

Establishes ContentUnit as the canonical source of truth along with
SourceRecord, ConceptNode, KnowledgeGraph, RichChunk, and TopicBlueprint.
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceRecord(BaseModel):
    """Persistent metadata record for an uploaded learning material source."""

    source_id: str = Field(default_factory=lambda: f"SRC_{uuid4().hex[:12]}")
    asset_id: str = Field(default_factory=lambda: f"AST_{uuid4().hex[:12]}")
    upload_id: str = Field(default_factory=lambda: f"UPL_{uuid4().hex[:12]}")
    filename: str
    source_type: Literal["pdf", "image", "txt", "video"]
    mime_type: str
    file_hash: str = Field(description="SHA-256 hash of the original file")
    file_size: int
    uploaded_by: str = "student_default"
    user_id: str = "student_default"
    owner_user_id: str = "student_default"
    version: int = 1
    source_version: str = "v1"
    title: str | None = None
    sha256: str | None = None
    parser_version: str = "v1"
    sanitization_version: str = "v1"
    parent_source_id: str | None = None
    status: Literal[
        "UPLOADED",
        "PROCESSING",
        "EXTRACTING",
        "NORMALIZING",
        "INDEXING",
        "READY",
        "FAILED",
    ] = "UPLOADED"
    error_message: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ContentUnit(BaseModel):
    """The central canonical abstraction of the ingestion system."""

    content_id: str = Field(default_factory=lambda: f"CU_{uuid4().hex[:12]}")
    source_id: str
    asset_id: str
    layer: Literal["A"] = "A"
    modality: Literal["pdf", "image", "txt", "video"]
    text: str
    visual_description: str | None = None
    page_number: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    slide_number: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    speaker: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    frame_id: str | None = None
    sequence_index: int = 0
    chapter: str | None = None
    section: str | None = None
    parent_content_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    bbox: list[float] | None = Field(
        default=None, description="Bounding box [x0, y0, x1, y1] if applicable"
    )
    region_id: str | None = None
    image_id: str | None = None
    image_path: str | None = None
    extraction_method: str
    confidence_score: float = Field(
        default=1.0, description="Extraction or OCR/Vision confidence score (0.0 - 1.0)"
    )


class ConceptNode(BaseModel):
    """A granular knowledge concept extracted from ContentUnits."""

    concept_id: str
    name: str
    definition: str | None = None
    prerequisite_concept_ids: list[str] = Field(default_factory=list)
    related_concept_ids: list[str] = Field(default_factory=list)
    source_content_ids: list[str] = Field(
        default_factory=list, description="ContentUnit IDs where this concept is defined"
    )


class KnowledgeGraph(BaseModel):
    """Network of extracted concepts and their prerequisite dependencies."""

    concepts: dict[str, ConceptNode] = Field(default_factory=dict)


class RichChunk(BaseModel):
    """RAG-ready chunk with full provenance metadata for Qdrant payload."""

    chunk_id: str = Field(default_factory=lambda: f"CHUNK_{uuid4().hex[:12]}")
    source_id: str
    asset_id: str
    layer: Literal["A"] = "A"
    type: Literal["rich_chunk"] = "rich_chunk"
    text: str
    modality: Literal["pdf", "image", "txt", "video"]
    chapter_id: str | None = None
    chapter: str | None = None
    section_id: str | None = None
    section: str | None = None
    concept_ids: list[str] = Field(default_factory=list)
    content_ids: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    timestamp_start: float | str | None = None
    timestamp_end: float | str | None = None
    user_id: str = "student_default"
    source_version: str = "v1"
    slide_start: int | None = None
    slide_end: int | None = None
    speaker: str | None = None
    trust_status: str = "user_uploaded_source"
    injection_status: Literal["clean", "sanitized", "quarantined"] = "clean"
    retrieval_allowed: bool = True
    source_hash: str | None = None
    parser_version: str = "v1"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class LayerBVideoSceneChunk(BaseModel):
    """Layer B: Approved generated teaching artifact representing an animated video scene."""

    chunk_id: str = Field(default_factory=lambda: f"SCENE_CHUNK_{uuid4().hex[:12]}")
    layer: Literal["B"] = "B"
    type: Literal["video_scene"] = "video_scene"
    scene_id: str
    video_id: str
    plan_id: str = "plan_default"
    user_id: str = "student_default"
    source_id: str
    source_version: str = "v1"
    concept_id: str | None = None
    concept_ids: list[str] = Field(default_factory=list)
    scene_type: str = "concept"
    title: str = ""
    narration_text: str = ""
    text: str = ""
    source_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Direct provenance back to Layer A chunk IDs",
    )
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0
    page_start: int | None = None
    page_end: int | None = None
    approval_status: str = "approved"
    grounding_status: str = "grounded"
    retrieval_allowed: bool = True
    injection_status: Literal["clean", "sanitized"] = "clean"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.text:
            if self.narration_text:
                self.text = f"{self.title}: {self.narration_text}".strip() if self.title else self.narration_text
            elif self.title:
                self.text = self.title
        if not self.narration_text and self.text:
            self.narration_text = self.text
        if self.concept_id and not self.concept_ids:
            self.concept_ids = [self.concept_id]


# Legacy chunk support for backwards compatibility during transition
class AuthoritativeSourceChunk(BaseModel):
    layer: Literal["A"] = "A"
    type: Literal["authoritative_source"] = "authoritative_source"
    document_name: str
    text: str
    page: int | None = None


class AuthoritativeVideoChunk(BaseModel):
    layer: Literal["A"] = "A"
    type: Literal["authoritative_video"] = "authoritative_video"
    video_name: str
    start_timestamp: str
    end_timestamp: str
    text: str


LayerAChunk = Annotated[
    Union[RichChunk, AuthoritativeSourceChunk, AuthoritativeVideoChunk],
    Field(discriminator="type"),
]

LayerChunk = Annotated[
    Union[RichChunk, AuthoritativeSourceChunk, AuthoritativeVideoChunk, LayerBVideoSceneChunk],
    Field(discriminator="type"),
]


class StageDiagnostics(BaseModel):
    """Observable diagnostics envelope emitted across subsystem boundaries."""

    stage: str = "general"
    provider_used: str = "default"
    fallback_used: bool = False
    fallback_reason: str | None = None
    error_code: str | None = None
    grounding_verified: bool = True
    dimension_validated: bool | None = None
    duration_ms: float = 0.0


class TopicBlueprint(BaseModel):
    """Derived representation over normalized ContentUnits and KnowledgeGraph."""

    topic_name: str = Field(description="Short title of what the document teaches")
    key_concepts: list[str] = Field(
        description="Core terms a student must know to master this topic"
    )
    prerequisites: list[str] = Field(
        description="Concepts the student should know before starting"
    )
    difficulty_level: Literal["beginner", "intermediate", "advanced"] = Field(
        description="Rough difficulty level"
    )
    source_id: str | None = None
    diagnostics: StageDiagnostics | None = None

    asset_id: str | None = None
    content_unit_count: int = 0
    chunk_count: int = 0


# Step 4: Grounded Q&A Schemas with Dual-Traceability
class Citation(BaseModel):
    chunk_id: str
    source_id: str | None = None
    page_number: int | None = None
    quote: str = ""
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    similarity_score: float | None = None
    verified: bool = False


class QARequest(BaseModel):
    user_id: str = "student_default"
    source_id: str
    question: str
    video_id: str | None = None
    current_timestamp: float | None = None
    active_concept_id: str | None = None
    source_version: str | None = None
    top_k: int = 5


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    grounding_confidence: float = 1.0
    refusal: bool = False
    refusal_reason: str | None = None
    active_scene: dict[str, Any] | None = None
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex[:12]}")
    diagnostics: StageDiagnostics | None = None


class QAAnswerTrace(BaseModel):
    trace_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str
    source_id: str
    question: str
    video_id: str | None = None
    video_timestamp: float | None = None
    retrieved_layer_b_scene: dict[str, Any] | None = None
    retrieved_layer_a_chunks: list[dict[str, Any]] = Field(default_factory=list)
    raw_llm_response: str = ""
    validated_answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    grounding_confidence: float = 1.0
    refusal: bool = False