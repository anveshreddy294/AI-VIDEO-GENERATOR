"""Canonical-source-only understanding and restart-safe derived index preparation."""

from __future__ import annotations

import logging
import time
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue, TypeAdapter, ValidationError

from ..content_understanding import (
    UNDERSTANDING_VERSION,
    UnderstandingError,
    understand_content,
)
from ..educational_chunker import ChunkPolicy, create_educational_chunks
from ..knowledge_service import KnowledgeService
from ..repositories.knowledge_repository import KnowledgeError, KnowledgeRepository
from ..repositories.source_repository import SupabaseSourceRepository
from ..schemas import RichChunk, SourceRecord
from ..security.content_sanitizer import SanitizedContent

logger = logging.getLogger(__name__)
OBJECT = TypeAdapter(dict[str, JsonValue])


def prepare_knowledge_index(
    repo: SupabaseSourceRepository, record: SourceRecord
) -> tuple[list[RichChunk], dict[str, JsonValue]]:
    """Deliberate callable for one owned version; READY retries never regenerate proposals."""
    knowledge = KnowledgeRepository(repo.user, repo._token, repo.runtime)
    scope = knowledge.scope(record.source_id, record.version)
    state = knowledge.get_knowledge_state(
        scope
    )  # Foreign/missing denied before model or vector access.
    version = repo.get_source_version(scope.source_id, scope.source_version)
    if version is None:
        raise KnowledgeError("NOT_FOUND")
    try:
        policy = ChunkPolicy.model_validate(
            version.provenance.get("chunk_policy") or ChunkPolicy().model_dump()
        )
    except ValidationError:
        raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
    envelopes = knowledge.list_scoped_content(scope)
    try:
        sanitized = {
            row.content_id: row
            for row in (
                SanitizedContent.model_validate(r) for r in version.sanitized_content
            )
        }
    except ValidationError:
        raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
    if not sanitized:
        raise UnderstandingError("NO_SAFE_CONTENT")
    for unit in envelopes:
        safe = sanitized.get(unit.content_id)
        if (
            safe is None
            or not safe.retrieval_allowed
            or safe.injection_status == "quarantined"
            or safe.source_id != scope.source_id
            or safe.source_version != f"v{scope.source_version}"
            or safe.sanitized_text != unit.content.text
        ):
            raise UnderstandingError("NO_SAFE_CONTENT")
    metrics: dict[str, JsonValue] = {
        "structuring_model_calls": 0,
        "repair_model_calls": 0,
        "structuring_latency_seconds": 0.0,
    }
    service = KnowledgeService(knowledge)
    if (state.knowledge_state != "READY" and record.status == "READY"
        and version.provenance.get("downstream_optional") is not True):
        raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
    if state.knowledge_state != "READY":
        result = understand_content(scope, envelopes)
        operation = uuid5(
            NAMESPACE_URL,
            f"{scope.user_id}:{scope.source_id}:{scope.source_version}:{UNDERSTANDING_VERSION}",
        )
        commit_started = time.perf_counter()
        service.commit_snapshot(scope, operation, result.snapshot)
        metrics["knowledge_supabase_commit_ms"] = (time.perf_counter()-commit_started)*1000
        metrics.update(
            stage_timings=result.stage_timings,
            deterministic_repairs=result.deterministic_repairs,
            quality=result.quality.model_dump(mode="json"),
            provider_telemetry=result.provider_telemetry,
            validation_latency_seconds=result.validation_latency_seconds,
            structuring_model_calls=result.structuring_model_calls,
            repair_model_calls=result.repair_model_calls,
            structuring_latency_seconds=result.structuring_latency_seconds,
        )
        logger.info(
            "KNOWLEDGE_COMMITTED",
            extra={
                "source_id": scope.source_id,
                "version": scope.source_version,
                "operation_id": str(operation),
                "topics": result.quality.topics,
                "concepts": result.quality.concepts,
            },
        )
    data = knowledge.get_complete_knowledge_map(scope)
    started = time.monotonic()
    chunks, quality = create_educational_chunks(
        scope, envelopes, data, policy, version.file_hash
    )
    metrics.update(
        chunk_quality=quality.model_dump(mode="json"),
        knowledge_database_calls=knowledge.database_calls,
        topic_count=len(data.topics),
        subtopic_count=len(data.subtopics),
        concept_count=len(data.concepts),
        chunking_latency_seconds=time.monotonic() - started,
    )
    logger.info(
        "CHUNKING_COMPLETED",
        extra={
            "source_id": scope.source_id,
            "version": scope.source_version,
            "chunks": len(chunks),
            "duration": time.monotonic() - started,
        },
    )
    return chunks, OBJECT.validate_python(metrics)
