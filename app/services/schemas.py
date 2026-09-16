"""Pydantic schemas for Step 1 Multimodal Knowledge Ingestion.

Establishes ContentUnit as the canonical source of truth along with
SourceRecord, ConceptNode, KnowledgeGraph, RichChunk, and TopicBlueprint.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
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
    version: int = 1
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
    modality: Literal["pdf", "image", "txt", "video"]
    text: str
    visual_description: str | None = None
    page_number: int | None = None
    slide_number: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
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
    extraction_method: str | None = None


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
    asset_id: str | None = None
    content_unit_count: int = 0
    chunk_count: int = 0