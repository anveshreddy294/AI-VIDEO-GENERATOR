"""Canonical source ingestion: extract, atomic commit, then recoverable vector indexing."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue, TypeAdapter

from ...core.config import settings
from ...core.supabase import SupabaseResponseError
from ...core.processing_errors import ProcessingError, ProcessingCode
from ..chunker import create_rich_chunks
from ..dispatcher import dispatch
from ..registry import calculate_sha256, validate_file, save_knowledge_graph
from ..repositories.source_repository import SourceVersion, SupabaseSourceRepository
from ..schemas import ContentUnit, RichChunk, SourceRecord
from ..security.content_sanitizer import sanitize_content_records
from ..structurer import process_structure_and_concepts
from ..validator import ValidationFailed, validate_ingestion_quality
from .normalizer import normalize_content_units
from .failures import ingestion_stage, SourceIndexFailed

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


def index_committed_source(repo: SupabaseSourceRepository, record: SourceRecord) -> dict[str, JsonValue]:
    """Retry from durable DB chunks; no extraction, ID regeneration or local JSON reads."""
    from ...db.vector_store import upsert_chunks
    version = repo.get_source_version(record.source_id, record.version)
    if version is None or not version.rich_chunks:
        raise SupabaseResponseError('Committed source version has no retrieval chunks')
    chunks = [RichChunk.model_validate(row) for row in version.rich_chunks]
    repo.mark_status(record, 'INDEXING')
    try:
        count = upsert_chunks(chunks)
        if count != len(chunks):
            raise ValidationFailed('Vector indexing count mismatch')
    except Exception as error:
        # Persist only a credential-free classification; do not log upstream bodies.
        reason: ProcessingCode = error.code if isinstance(error, ProcessingError) else 'VECTOR_INDEX_FAILED'
        persisted_error = error.code if isinstance(error, ProcessingError) else 'QDRANT_INDEX_FAILED:' + type(error).__name__
        repo.mark_status(record, 'FAILED', persisted_error)
        raise SourceIndexFailed(reason) from None
    repo.mark_status(record, 'READY')
    from ...db.vector_store import get_last_embed_diagnostics
    diagnostics = get_last_embed_diagnostics()
    return {'status': 'READY', 'source_id': record.source_id, 'asset_id': record.asset_id,
            'embedding_diagnostics': JSON_OBJECT.validate_python(diagnostics.model_dump(mode='json')) if diagnostics else None,
            'upload_id': record.upload_id, 'filename': record.filename, 'modality': record.source_type,
            'file_hash': record.file_hash, 'version': record.version, 'source_version': record.source_version,
            'content_units': len(repo.get_content_units(record.source_id, record.version)),
            'chunks_synced': count, 'topic_blueprint': version.topic_blueprint}


def ingest_source(repo: SupabaseSourceRepository, temp_path: Path, filename: str) -> dict[str, JsonValue]:
    """Binary files stay on disk; source/version/content state exists only in Supabase."""
    source_type, mime_type = validate_file(temp_path, filename)
    file_hash = calculate_sha256(temp_path)
    existing = repo.find_upload(filename, file_hash)
    if existing:
        return index_committed_source(repo, existing)
    latest = repo.latest_filename(filename)
    version_number = latest.version + 1 if latest else 1
    identity = uuid5(NAMESPACE_URL, f'visualai:{repo.owner_id}:{filename}:{file_hash}')
    record = SourceRecord(source_id='SRC_' + identity.hex, asset_id='AST_' + identity.hex,
        upload_id='UPL_' + identity.hex, filename=filename, source_type=cast(Literal["pdf", "txt", "image", "video"], source_type),
        mime_type=mime_type, file_hash=file_hash, sha256=file_hash, file_size=temp_path.stat().st_size,
        user_id=repo.owner_id, owner_user_id=repo.owner_id, uploaded_by=repo.owner_id,
        version=version_number, source_version=f'v{version_number}',
        parent_source_id=latest.source_id if latest else None, status='EXTRACTING')
    persistent_file = settings.upload_dir / repo.owner_id / record.source_id / ('original' + Path(filename).suffix.lower())
    persistent_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(temp_path, persistent_file)
    with ingestion_stage('EXTRACTION'):
        extraction = dispatch(persistent_file, source_id=record.source_id, asset_id=record.asset_id)
        raw_units = extraction.units
        if not raw_units:
            raise ValidationFailed('No extractable content')
        old_to_new = {unit.content_id: 'CU_' + uuid5(identity, str(i)).hex for i, unit in enumerate(raw_units)}
        for unit in raw_units:
            previous_id = unit.content_id
            unit.content_id = old_to_new[previous_id]
            if unit.parent_content_id:
                unit.parent_content_id = old_to_new.get(unit.parent_content_id, unit.parent_content_id)
    with ingestion_stage('NORMALIZATION'):
        normalized = normalize_content_units(raw_units, source_version=record.source_version)
        sanitized = sanitize_content_records(normalized)
        clean = {row.content_id: row.sanitized_text for row in sanitized if row.retrieval_allowed}
        units: list[ContentUnit] = []
        for unit in raw_units:
            if clean.get(unit.content_id):
                unit.text = clean[unit.content_id]
                units.append(unit)
        if not units:
            raise ValidationFailed('No safe retrievable content')
    with ingestion_stage('STRUCTURING'):
        enriched, graph, blueprint = process_structure_and_concepts(units)
    with ingestion_stage('CHUNKING'):
        chunks = create_rich_chunks(enriched, graph, user_id=repo.owner_id,
            source_version=record.source_version, source_hash=file_hash)
        for chunk in chunks:
            chunk.source_type = record.source_type
            chunk.content_id = chunk.content_ids[0]
        # Validate content/provenance before commit; actual storage count is checked after upsert.
        validate_ingestion_quality(record, persistent_file, enriched, graph, chunks, len(chunks))
    blueprint.chunk_count = len(chunks)
    record.status = 'INDEXING'
    version = SourceVersion(user_id=repo.user.user_id, source_id=record.source_id,
        version=record.version, source_version=record.source_version, filename=filename,
        file_hash=file_hash, sha256=file_hash, file_location=str(persistent_file),
        normalized_content=[JSON_OBJECT.validate_python(row.model_dump(mode='json')) for row in normalized],
        sanitized_content=[JSON_OBJECT.validate_python(row.model_dump(mode='json')) for row in sanitized],
        quarantined_content=[JSON_OBJECT.validate_python(row.model_dump(mode='json')) for row in sanitized if not row.retrieval_allowed],
        rich_chunks=[JSON_OBJECT.validate_python(row.model_dump(mode='json')) for row in chunks],
        topic_blueprint=JSON_OBJECT.validate_python(blueprint.model_dump(mode='json')))
    committed = repo.commit_ingestion(record, version, enriched)
    # Concept/graph persistence remains file-based; it is not canonical source state.
    try:
        save_knowledge_graph(record.source_id, graph)
    except OSError:
        repo.mark_status(committed, 'FAILED', 'LOCAL_GRAPH_ARTIFACT_FAILED')
        raise SupabaseResponseError('Source committed; graph artifact write failed; retry this source') from None
    return index_committed_source(repo, committed)
