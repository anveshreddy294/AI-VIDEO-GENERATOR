from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from uuid import uuid4


def uid():
    return uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


class Source(BaseModel):
    source_id: str = Field(default_factory=uid)
    title: str
    source_type: Literal["uploaded", "curriculum", "trusted_topic", "generated"]
    url: str | None = None
    externally_grounded: bool = True
    trust_label: str = "source_backed"


class SourceChunk(BaseModel):
    chunk_id: str = Field(default_factory=uid)
    source_id: str
    text: str
    page: int | None = None
    section: str | None = None
    url: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    source_type: str
    trust_label: str = "source_backed"


class Concept(BaseModel):
    concept_id: str = Field(default_factory=uid)
    name: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class LearningSessionKnowledge(BaseModel):
    session_id: str = Field(default_factory=uid)
    user_id: str | None = None
    topic: str
    subject: str | None = None
    input_mode: str = "topic"
    materials: list[dict] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    source_chunks: list[SourceChunk] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    definitions: list[str] = Field(default_factory=list)
    key_facts: list[dict] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    lesson_summary: str = ""
    storyboard_mapping: list[dict] = Field(default_factory=list)
    narration_mapping: list[dict] = Field(default_factory=list)
    learner_profile: dict = Field(default_factory=dict)
    status: str = "knowledge_ready"
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)


class ImageExtraction(BaseModel):
    raw_text: str
    clean_text: str
    equations: list[str] = Field(default_factory=list)
    detected_concepts: list[str] = Field(default_factory=list)
    diagram_description: str = ""
    graph_description: str = ""
    uncertain_content: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
    warnings: list[str] = Field(default_factory=list)
