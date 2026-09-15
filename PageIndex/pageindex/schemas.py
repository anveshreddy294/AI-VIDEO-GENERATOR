from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TOCEntry(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str
    page_number: int
    structure: str = ""


class TOCDetectionResult(BaseModel):
    model_config = ConfigDict(strict=True)

    toc_found: bool
    toc_entries: List[TOCEntry] = Field(default_factory=list)


class TOCNode(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str
    page_number: int
    node_id: str
    children: List[TOCNode] = Field(default_factory=list)


class HierarchicalTOC(BaseModel):
    model_config = ConfigDict(strict=True)

    root: TOCNode


TOCNode.model_rebuild()


class NodeSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    node_id: str
    summary: str
    keywords: List[str] = Field(default_factory=list)
    semantic_tags: List[str] = Field(default_factory=list)
    content_type: Optional[str] = None


class SummaryBatch(BaseModel):
    model_config = ConfigDict(strict=True)

    nodes: List[NodeSummary]


class TitlePolishItem(BaseModel):
    model_config = ConfigDict(strict=True)

    node_id: str
    title: str


class TitlePolishBatch(BaseModel):
    model_config = ConfigDict(strict=True)

    nodes: List[TitlePolishItem]


class DocDescription(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str
    subject: str
    grade_level: str
    description: str
    primary_topics: List[str]


class ExplanationResult(BaseModel):
    model_config = ConfigDict(strict=True)

    answer: str
    steps: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    key_terms: List[str] = Field(default_factory=list)


class ThinkingCompleted(BaseModel):
    model_config = ConfigDict(strict=True)

    thinking: str = ""
    completed: str


class TocDetectorAnswer(BaseModel):
    model_config = ConfigDict(strict=True)

    thinking: str = ""
    toc_detected: str


class PageIndexInTocAnswer(BaseModel):
    model_config = ConfigDict(strict=True)

    thinking: str = ""
    page_index_given_in_toc: str


class PhysicalIndexEntry(BaseModel):
    model_config = ConfigDict(strict=True)

    structure: Optional[str] = None
    title: str
    physical_index: Optional[str] = None


class TOCPhysicalIndexList(BaseModel):
    model_config = ConfigDict(strict=True)

    items: List[PhysicalIndexEntry]


class AddPageNumberRow(BaseModel):
    model_config = ConfigDict(strict=True)

    structure: Optional[str] = None
    title: str
    start: str = ""
    physical_index: Optional[str] = None


class AddPageNumberResult(BaseModel):
    model_config = ConfigDict(strict=True)

    items: List[AddPageNumberRow]


class TitleAppearanceAnswer(BaseModel):
    model_config = ConfigDict(strict=True)

    thinking: str = ""
    answer: str


class TitleStartAnswer(BaseModel):
    model_config = ConfigDict(strict=True)

    thinking: str = ""
    start_begin: str


class SectionPhysicalIndexAnswer(BaseModel):
    model_config = ConfigDict(strict=True)

    thinking: str = ""
    physical_index: str


class PlainSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    summary: str
