"""Canonical source ingestion: extract, atomic commit, then recoverable vector indexing."""

from __future__ import annotations

import shutil
import logging
import time
from pathlib import Path
from typing import Literal, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue, TypeAdapter

from ...core.config import settings
from ...core.supabase import SupabaseResponseError
from ...core.processing_errors import ProcessingError, ProcessingCode
from ..chunker import create_rich_chunks
from ..dispatcher import dispatch
from ..visual_router import VisualSignals
from ..registry import calculate_sha256
from ..file_truth import FileTruth, inspect_upload
from ..repositories.source_repository import SourceVersion, SupabaseSourceRepository
from ..schemas import ContentUnit, RichChunk, SourceRecord
from ..security.content_sanitizer import sanitize_content_records
from ..validator import ValidationFailed
from .normalizer import normalize_content_units
from .failures import ingestion_stage, SourceIndexFailed
from .failures import SourceFailure, SourceIngestionFailed
from .knowledge_publication import prepare_knowledge_index
from .progress import report
from ..content_understanding import UNDERSTANDING_VERSION, UnderstandingError
from ..educational_chunker import ChunkPolicy
from ..repositories.knowledge_repository import KnowledgeError
from ..schemas import KnowledgeGraph

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
logger = logging.getLogger(__name__)


def index_committed_source(
    repo: SupabaseSourceRepository, record: SourceRecord
) -> dict[str, JsonValue]:
    """Retry from durable DB chunks; no extraction, ID regeneration or local JSON reads."""
    from ...db.vector_store import upsert_chunks

    if repo.runtime.verify_user(repo._token).user_id != repo.user.user_id:
        raise KnowledgeError("NOT_FOUND")
    version = repo.get_source_version(record.source_id, record.version)
    if version is None or not version.rich_chunks:
        raise SupabaseResponseError("Committed source version has no retrieval chunks")
    optional = version.provenance.get("downstream_optional") is True
    metrics: dict[str, JsonValue] = {}
    if version.provenance.get("knowledge_pipeline") == UNDERSTANDING_VERSION:
        try:
            report("BUILDING_LEARNING_STRUCTURE")
            chunks, metrics = prepare_knowledge_index(repo, record)
        except (
            UnderstandingError,
            KnowledgeError,
            ProcessingError,
            TimeoutError,
        ) as error:
            reason = "MODEL_TIMEOUT" if isinstance(error, TimeoutError) else error.code
            if record.status != "READY" and not optional:
                repo.mark_status(record, "FAILED", "CONTENT_UNDERSTANDING_FAILED:" + reason)
            raise SourceIngestionFailed(
                SourceFailure(
                    stage="STRUCTURING",
                    code=reason,
                    validation_detail=error.detail if isinstance(error, UnderstandingError) else None,
                    failed_object_type=error.failed_object_type if isinstance(error, UnderstandingError) else None,
                    structural_reason=error.reason_category if isinstance(error, UnderstandingError) else None,
                    label_reference=error.label_reference if isinstance(error, UnderstandingError) else None,
                    repair_attempted=error.repair_attempted if isinstance(error, UnderstandingError) else None,
                    retryable=True,
                    reason_code=(
                        reason
                        if isinstance(error, ProcessingError)
                        or isinstance(error, TimeoutError)
                        else None
                    ),
                    message="Canonical source saved; knowledge preparation failed. Retry this source.",
                )
            ) from None
    else:
        # Historical unmapped sources retain their durable Phase 5B index; no automatic backfill.
        chunks = [RichChunk.model_validate(row) for row in version.rich_chunks]
    # Complete all fallible read-side result preparation before publishing READY.
    content_count = len(repo.get_content_units(record.source_id, record.version))
    diagnostics = None
    count = len(chunks)
    if record.status == "READY" and not optional:
        metrics.update(qdrant_writes=0, indexing_latency_seconds=0.0)
    else:
        report("INDEXING_SOURCE")
        if not optional:
            repo.mark_status(record, "INDEXING")
        started = time.monotonic()
        logger.info(
            "INDEXING_STARTED",
            extra={
                "source_id": record.source_id,
                "version": record.version,
                "chunks": len(chunks),
            },
        )
        try:
            count = upsert_chunks(chunks)
            if count != len(chunks):
                raise ValidationFailed("Vector indexing count mismatch")
        except Exception as error:
            # Persist only a credential-free classification; do not log upstream bodies.
            reason: ProcessingCode = (
                error.code if isinstance(error, ProcessingError) else "VECTOR_INDEX_FAILED"
            )
            persisted_error = (
                error.code
                if isinstance(error, ProcessingError)
                else "QDRANT_INDEX_FAILED:" + type(error).__name__
            )
            if not optional:
                repo.mark_status(record, "FAILED", persisted_error)
            logger.warning(
                "INDEXING_FAILED",
                extra={
                    "source_id": record.source_id,
                    "version": record.version,
                    "reason_code": reason,
                },
            )
            raise SourceIndexFailed(reason) from None
        logger.info(
            "INDEXING_COMPLETED",
            extra={
                "source_id": record.source_id,
                "version": record.version,
                "chunks": count,
                "duration": time.monotonic() - started,
            },
        )
        from ...db.vector_store import get_index_timings
        metrics.update(indexing_latency_seconds=time.monotonic() - started, qdrant_writes=1, **get_index_timings())
        from ...db.vector_store import get_last_embed_diagnostics

        diagnostics = get_last_embed_diagnostics()
        repo.mark_status(record, "READY")
    return {
        "status": "READY",
        "source_id": record.source_id,
        "asset_id": record.asset_id,
        "embedding_diagnostics": (
            JSON_OBJECT.validate_python(diagnostics.model_dump(mode="json"))
            if diagnostics
            else None
        ),
        "upload_id": record.upload_id,
        "filename": record.filename,
        "modality": record.source_type,
        "file_hash": record.file_hash,
        "version": record.version,
        "source_version": record.source_version,
        "content_units": content_count,
        "chunks_synced": count,
        "topic_blueprint": version.topic_blueprint,
        "knowledge_state": (
            "READY"
            if version.provenance.get("knowledge_pipeline") == UNDERSTANDING_VERSION
            else "LEGACY_UNMAPPED"
        ),
        "understanding_metrics": metrics,
    }


def ingest_source(
    repo: SupabaseSourceRepository, temp_path: Path, filename: str,
    *, routing_signals: VisualSignals | None = None, file_truth: FileTruth | None = None,
    enrich: bool = False,
) -> dict[str, JsonValue]:
    """Binary files stay on disk; source/version/content state exists only in Supabase."""
    total_started = time.perf_counter()
    if repo.runtime.verify_user(repo._token).user_id != repo.user.user_id:
        raise KnowledgeError("NOT_FOUND")
    truth = inspect_upload(temp_path, filename, file_truth.browser_mime if file_truth else None)
    source_type, mime_type = truth.source_type, truth.mime_type
    file_hash = calculate_sha256(temp_path)
    existing = repo.find_upload(filename, file_hash)
    if existing:
        return index_committed_source(repo, existing) if enrich else extracted_source_result(repo, existing)
    latest = repo.latest_filename(filename)
    version_number = latest.version + 1 if latest else 1
    identity = uuid5(NAMESPACE_URL, f"visualai:{repo.owner_id}:{filename}:{file_hash}")
    record = SourceRecord(
        source_id="SRC_" + identity.hex,
        asset_id="AST_" + identity.hex,
        upload_id="UPL_" + identity.hex,
        filename=filename,
        source_type=cast(Literal["pdf", "txt", "image", "video"], source_type),
        mime_type=mime_type,
        file_hash=file_hash,
        sha256=file_hash,
        file_size=temp_path.stat().st_size,
        user_id=repo.owner_id,
        owner_user_id=repo.owner_id,
        uploaded_by=repo.owner_id,
        version=version_number,
        source_version=f"v{version_number}",
        parent_source_id=latest.source_id if latest else None,
        status="EXTRACTING",
    )
    persistent_file = (
        settings.upload_dir
        / repo.owner_id
        / record.source_id
        / ("original." + truth.extension)
    )
    persistent_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(temp_path, persistent_file)
    report("EXTRACTING_SOURCE")
    with ingestion_stage("EXTRACTION"):
        from ..visual_router import VisualScope, visual_scope
        from ...core.inference_budget import processing_budget
        with visual_scope(VisualScope(user_id=repo.owner_id, source_id=record.source_id, source_version=record.version)), processing_budget(settings.extraction_stage_timeout_seconds):
            if routing_signals is None:
                extraction = dispatch(persistent_file, source_id=record.source_id, asset_id=record.asset_id)
            else:
                extraction = dispatch(persistent_file, source_id=record.source_id, asset_id=record.asset_id, routing_signals=routing_signals)
        raw_units = extraction.units
        if not raw_units:
            raise ValidationFailed("No extractable content")
        old_to_new = {
            unit.content_id: "CU_" + uuid5(identity, str(i)).hex
            for i, unit in enumerate(raw_units)
        }
        for unit in raw_units:
            unit.provenance["file_truth"] = truth.provenance()
            previous_id = unit.content_id
            unit.content_id = old_to_new[previous_id]
            if unit.parent_content_id:
                unit.parent_content_id = old_to_new.get(
                    unit.parent_content_id, unit.parent_content_id
                )
    normalization_started = time.perf_counter()
    with ingestion_stage("NORMALIZATION"):
        normalized = normalize_content_units(
            raw_units, source_version=record.source_version
        )
        sanitized = sanitize_content_records(normalized)
        clean = {
            row.content_id: row.sanitized_text
            for row in sanitized
            if row.retrieval_allowed
        }
        units: list[ContentUnit] = []
        for unit in raw_units:
            if clean.get(unit.content_id):
                unit.text = clean[unit.content_id]
                units.append(unit)
        if not units:
            raise ValidationFailed("No safe retrievable content")
    normalization_ms = (time.perf_counter() - normalization_started) * 1000
    enriched = units
    # The deployed immutable source RPC requires nonempty retrieval chunks. These bounded
    # bootstrap chunks are never indexed for this policy; READY canonical knowledge owns indexing.
    with ingestion_stage("CHUNKING"):
        chunks = create_rich_chunks(
            enriched,
            KnowledgeGraph(concepts={}),
            user_id=repo.owner_id,
            source_version=record.source_version,
            source_hash=file_hash,
        )
        for chunk in chunks:
            chunk.source_type = record.source_type
            chunk.content_id = chunk.content_ids[0]
        # Validate content/provenance before commit; actual storage count is checked after upsert.
        if any(
            not u.text.strip()
            or (u.confidence_score <= 0 and u.provenance.get("confidence_status") != "unreported")
            for u in enriched
        ):
            raise ValidationFailed("Invalid canonical extraction evidence")
    record.status = "INDEXING"
    version = SourceVersion(
        user_id=repo.user.user_id,
        source_id=record.source_id,
        version=record.version,
        source_version=record.source_version,
        filename=filename,
        file_hash=file_hash,
        sha256=file_hash,
        file_location=str(persistent_file),
        normalized_content=[
            JSON_OBJECT.validate_python(row.model_dump(mode="json"))
            for row in normalized
        ],
        sanitized_content=[
            JSON_OBJECT.validate_python(row.model_dump(mode="json"))
            for row in sanitized
        ],
        quarantined_content=[
            JSON_OBJECT.validate_python(row.model_dump(mode="json"))
            for row in sanitized
            if not row.retrieval_allowed
        ],
        rich_chunks=[
            JSON_OBJECT.validate_python(row.model_dump(mode="json")) for row in chunks
        ],
        provenance={
            "file_truth": truth.provenance(),
            "knowledge_pipeline": UNDERSTANDING_VERSION,
            "downstream_optional": not enrich,
            "chunk_policy": ChunkPolicy().model_dump(mode="json"),
        },
    )
    commit_started = time.perf_counter()
    report("PERSISTING_SOURCE")
    with ingestion_stage("PERSISTENCE"):
        committed = repo.commit_ingestion(record, version, enriched)
    commit_ms = (time.perf_counter()-commit_started)*1000
    result = index_committed_source(repo, committed) if enrich else extracted_source_result(repo, committed)
    result["source_commit_ms"] = commit_ms
    result["ingestion_content_unit_normalization_ms"] = normalization_ms
    routing_metrics: list[JsonValue] = [unit.provenance["routing"] for unit in enriched if unit.provenance.get("routing")]
    result["visual_inference_metrics"] = routing_metrics
    result["total_upload_to_ready_ms" if enrich else "total_upload_to_content_ready_ms"] = (time.perf_counter()-total_started)*1000
    return result


def extracted_source_result(repo: SupabaseSourceRepository, record: SourceRecord) -> dict[str, JsonValue]:
    """Content availability is independent of downstream hierarchy and semantic indexing."""
    from ..security.source_scope import require_source_scope
    require_source_scope(repo, record.source_id, record.version)
    units = repo.get_content_units(record.source_id, record.version)
    if not units:
        raise SupabaseResponseError("Committed source has no extracted content")
    warnings: list[JsonValue] = []
    if any(unit.provenance.get("missing_visual_content") for unit in units):
        warnings.append("OPTIONAL_VISUAL_CONTENT_UNAVAILABLE")
    if any(unit.provenance.get("publication_policy") == "independent-verified-subset-v1" for unit in units):
        warnings.append("PARTIAL_VISUAL_VERIFICATION")
    # Keep legacy READY semantics intact: READY still means indexed. The new explicit
    # content_ready field represents extraction availability without a schema change.
    return {
        "status": record.status, "content_ready": True, "readiness_basis": "EXTRACTED_CONTENT",
        "source_id": record.source_id, "asset_id": record.asset_id,
        "upload_id": record.upload_id, "filename": record.filename, "modality": record.source_type,
        "file_hash": record.file_hash, "version": record.version, "source_version": record.source_version,
        "content_units": len(units), "chunks_synced": 0,
        "warnings": warnings,
        "downstream": {"knowledge": "NOT_REQUESTED", "indexing": "NOT_REQUESTED"},
        "educational_content_endpoint": "/educational-content",
    }
