"""Quality Validation Gateway for Step 1 Ingestion Pipeline.

Verifies File, ContentUnit, Chunk, Concept, and Storage levels before
marking a source status as READY.
"""

import logging
from pathlib import Path
from typing import Any

from .schemas import ContentUnit, KnowledgeGraph, RichChunk, SourceRecord

logger = logging.getLogger(__name__)


class ValidationFailed(Exception):
    """Raised when quality validation fails at any stage."""

    pass


def validate_ingestion_quality(
    record: SourceRecord,
    file_path: Path,
    units: list[ContentUnit],
    kg: KnowledgeGraph,
    chunks: list[RichChunk],
    upserted_count: int,
) -> dict[str, Any]:
    """Run full validation checks across file, content, chunk, concept, and storage layers."""
    report: dict[str, Any] = {
        "source_id": record.source_id,
        "asset_id": record.asset_id,
        "checks": {},
        "passed": False,
    }

    # 1. File Level Validation
    if not file_path.exists():
        raise ValidationFailed(f"File level failure: Persistent file missing at {file_path}")
    if file_path.stat().st_size == 0:
        raise ValidationFailed("File level failure: Original file is 0 bytes.")
    report["checks"]["file_level"] = "PASSED"

    # 2. Content Level Validation
    if not units:
        raise ValidationFailed("Content level failure: No ContentUnits extracted.")
    unit_ids = {u.content_id for u in units}
    if len(unit_ids) != len(units):
        raise ValidationFailed("Duplicate content IDs")
    for cu in units:
        if not cu.text.strip() or cu.confidence_score <= 0 or cu.source_id != record.source_id or cu.asset_id != record.asset_id:
            raise ValidationFailed("Empty, failed, or mismatched content unit")
        if not cu.content_id or not cu.source_id or not cu.asset_id:
            raise ValidationFailed(f"Content level failure: ContentUnit {cu} missing essential IDs.")
        if cu.modality in ("pdf", "image") and cu.page_number is None and cu.modality == "pdf":
            raise ValidationFailed(f"Content level failure: PDF ContentUnit {cu.content_id} missing page_number.")
    report["checks"]["content_level"] = f"PASSED ({len(units)} ContentUnits)"

    # 3. Chunk Level Validation
    if not chunks:
        raise ValidationFailed("Chunk level failure: No RichChunks created.")
    for ch in chunks:
        if not ch.text.strip() or ch.source_id != record.source_id or ch.asset_id != record.asset_id or not set(ch.content_ids).issubset(unit_ids):
            raise ValidationFailed("Invalid chunk text or provenance")
        if not ch.chunk_id or not ch.source_id or not ch.asset_id:
            raise ValidationFailed(f"Chunk level failure: Chunk {ch} missing essential IDs.")
        if ch.layer != "A":
            raise ValidationFailed(f"Chunk level failure: Chunk {ch.chunk_id} layer is not 'A'.")
        if not ch.content_ids:
            raise ValidationFailed(f"Chunk level failure: Chunk {ch.chunk_id} has no provenance content_ids.")
    report["checks"]["chunk_level"] = f"PASSED ({len(chunks)} Chunks)"

    # 4. Concept Level Validation
    if not kg.concepts:
        raise ValidationFailed("Knowledge graph has no concepts")
    for cid, concept in kg.concepts.items():
        if not concept.source_content_ids or not set(concept.source_content_ids).issubset(unit_ids):
            raise ValidationFailed("Concept has missing or invalid content references")
        if not set(concept.prerequisite_concept_ids).issubset(kg.concepts):
            raise ValidationFailed("Concept has unknown prerequisites")
        if not concept.concept_id or not concept.name:
            raise ValidationFailed(f"Concept level failure: Concept node {cid} missing ID or name.")
        if not concept.source_content_ids:
            logger.warning("[validator] Concept %s (%s) has no source_content_ids mapping.", concept.name, cid)
    report["checks"]["concept_level"] = f"PASSED ({len(kg.concepts)} Concepts)"

    # 5. Storage Level Validation
    if upserted_count != len(chunks):
        raise ValidationFailed(
            f"Storage level failure: Qdrant upserted {upserted_count} points, expected {len(chunks)}."
        )
    report["checks"]["storage_level"] = f"PASSED ({upserted_count} Qdrant points)"

    report["passed"] = True
    return report
