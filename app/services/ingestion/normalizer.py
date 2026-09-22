"""Safe Content Normalization Layer for Step 1 Ingestion.

Normalizes PDF, image, text, audio, and lecture video inputs into a canonical
NormalizedContentRecord structure preserving headings, page/slide numbers,
timestamps, and speaker metadata without flattening.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from ..schemas import ContentUnit


class NormalizedContentRecord(BaseModel):
    """Common canonical normalization abstraction for all ingested content."""

    content_id: str = Field(default_factory=lambda: f"NORM_{uuid4().hex[:12]}")
    source_id: str
    source_version: str = "v1"
    content_type: Literal["page", "slide", "transcript_segment", "diagram_description", "text_block"] = "text_block"
    page_number: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    slide_number: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    heading_path: list[str] = Field(default_factory=list)
    raw_text: str = ""
    extracted_text: str = ""
    image_regions: list[dict[str, Any]] = Field(default_factory=list)
    speaker: str | None = None
    modality: str = "text"
    chapter: str | None = None
    section: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def normalize_content_unit(unit: ContentUnit, source_version: str = "v1") -> NormalizedContentRecord:
    """Transform a single ContentUnit into a NormalizedContentRecord."""
    # Determine content_type based on modality and unit structure
    if unit.modality == "video":
        content_type = "transcript_segment"
    elif unit.slide_number is not None:
        content_type = "slide"
    elif unit.page_number is not None:
        content_type = "page"
    elif unit.modality == "image":
        content_type = "diagram_description"
    else:
        content_type = "text_block"

    # Construct structural heading path
    heading_path: list[str] = list(getattr(unit, "heading_path", []) or [])
    if unit.chapter and unit.chapter.strip() not in heading_path:
        heading_path.append(unit.chapter.strip())
    if unit.section and unit.section.strip() not in heading_path:
        heading_path.append(unit.section.strip())

    # Build image_regions if bbox or image_id present
    image_regions = []
    if unit.bbox or unit.image_id:
        image_regions.append({
            "image_id": unit.image_id or "img_region",
            "bbox": unit.bbox,
            "visual_description": unit.visual_description,
            "confidence": unit.confidence_score,
        })

    # Raw vs Extracted text
    text_content = (unit.text or "").strip()
    if unit.visual_description and unit.visual_description not in text_content:
        full_text = f"{text_content}\n[Visual Description]: {unit.visual_description}".strip()
    else:
        full_text = text_content

    # Extract speaker if indicated by common transcript patterns (e.g. "Lecturer: ...")
    speaker = getattr(unit, "speaker", None)
    if not speaker:
        speaker_match = re.match(r"^([A-Z][a-zA-Z\s]{1,20}):\s*(.*)", text_content)
        if speaker_match and unit.modality == "video":
            speaker = speaker_match.group(1).strip()
            extracted = speaker_match.group(2).strip()
        else:
            extracted = full_text
    else:
        extracted = full_text

    pg_start = getattr(unit, "page_start", None) or unit.page_number
    pg_end = getattr(unit, "page_end", None) or unit.page_number

    slide_num = getattr(unit, "slide_number", None)
    unit_meta = getattr(unit, "metadata", None)
    if slide_num is None and isinstance(unit_meta, dict):
        slide_num = unit_meta.get("slide")

    return NormalizedContentRecord(
        content_id=unit.content_id,
        source_id=unit.source_id,
        source_version=source_version,
        content_type=content_type,
        page_number=unit.page_number or pg_start,
        page_start=pg_start,
        page_end=pg_end,
        slide_number=slide_num,
        timestamp_start=unit.timestamp_start,
        timestamp_end=unit.timestamp_end,
        heading_path=heading_path,
        raw_text=full_text,
        extracted_text=extracted,
        image_regions=image_regions,
        speaker=speaker,
        modality=unit.modality,
        chapter=unit.chapter,
        section=unit.section,
        char_start=unit.char_start,
        char_end=unit.char_end,
        metadata=unit_meta if isinstance(unit_meta, dict) else {},
    )


def normalize_content_units(
    units: list[ContentUnit], source_version: str = "v1"
) -> list[NormalizedContentRecord]:
    """Batch normalization for a source's extracted ContentUnits."""
    return [normalize_content_unit(u, source_version=source_version) for u in units]
