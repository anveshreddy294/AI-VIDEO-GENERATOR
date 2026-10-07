"""Canonical evidence authority; vectors are untrusted candidate pointers only."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from collections import Counter
from typing import Annotated, Literal, Protocol
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import Field, JsonValue, TypeAdapter, ValidationError
from qdrant_client import models as qm
from qdrant_client.http.exceptions import UnexpectedResponse, ResponseHandlingException
import httpx

from ..core.config import settings
from ..core.processing_errors import ProcessingError
from .chunker import _token_len
from .educational_chunker import ChunkMetadata, ChunkPolicy, create_educational_chunks
from .knowledge_models import Contract, Identifier
from .knowledge_service import KnowledgeService
from .repositories.knowledge_repository import KnowledgeError, KnowledgeRepository
from .repositories.source_repository import SupabaseSourceRepository
from .security.content_sanitizer import SanitizedContent
from .security.source_scope import SourceScope

logger = logging.getLogger(__name__)
MAX_CANDIDATES = 80
MAX_PREREQUISITES = 32
MIN_SEMANTIC_SCORE = 0.35


class RetrievalRequest(Contract):
    source_id: Identifier
    source_version: Annotated[int, Field(ge=1)]
    query: Annotated[str, Field(min_length=1, max_length=4000)]
    topic_id: Identifier | None = None
    subtopic_id: Identifier | None = None
    concept_ids: Annotated[list[Identifier], Field(max_length=64)] | None = None
    content_ids: Annotated[list[Identifier], Field(max_length=64)] | None = None
    purpose: Literal[
        "qa", "notes", "assessment", "video", "roadmap", "remediation", "agent"
    ] = "qa"
    max_items: Annotated[int, Field(ge=1, le=20)] = 5
    include_prerequisites: bool = False
    retrieval_mode: Literal["semantic", "exact"] = "semantic"


class EvidenceBudget(Contract):
    max_total_tokens: Annotated[int, Field(ge=1, le=8000)] = 3000
    max_item_tokens: Annotated[int, Field(ge=1, le=2000)] = 800


class EmbeddingSpace(Contract):
    embedding_provider: Literal["ollama"] = "ollama"
    embedding_model: Literal["embeddinggemma"] = "embeddinggemma"
    embedding_dimension: Literal[768] = 768
    embedding_kind: Literal["semantic"] = "semantic"
    embedding_version: Literal["1"] = "1"


class EvidenceItem(Contract):
    evidence_id: str
    content_id: str
    chunk_id: str
    source_id: str
    source_version: int
    topic_id: str | None
    subtopic_id: str | None
    concept_ids: list[str]
    excerpt: str = Field(repr=False)
    char_start: int
    char_end: int
    page_start: int | None
    page_end: int | None
    slide: int | None
    timestamp_start: float | None
    timestamp_end: float | None
    chapter: str | None
    section: str | None
    heading_path: list[str]
    content_role: str
    retrieval_score: float | None
    citation: str
    embedding_provenance: EmbeddingSpace | None


class EvidenceBundle(Contract):
    evidence_bundle_id: str
    scope: SourceScope
    purpose: str
    query: str = Field(repr=False)
    topic_id: str | None
    subtopic_id: str | None
    concept_ids: list[str]
    items: list[EvidenceItem]
    manifest_digest: str
    outcome: Literal["READY", "INSUFFICIENT_EVIDENCE", "INDEX_UNAVAILABLE"]
    rejected_candidates: dict[str, int]
    token_count: int
    token_budget: EvidenceBudget
    embedding_provenance: EmbeddingSpace | None
    latencies: dict[str, float]
    indexed_point_count: int | None = None


class Candidate(Contract):
    point_id: str
    score: float
    payload: dict[str, JsonValue] = Field(repr=False)


class IndexUnavailable(RuntimeError):
    """Retryable infrastructure condition, never an empty successful retrieval."""

    def __init__(
        self, code: Literal["INDEX_UNAVAILABLE", "PROVIDER_UNAVAILABLE"]
    ) -> None:
        self.code = code
        super().__init__(code)


class CandidateIndex(Protocol):
    def search(
        self, request: RetrievalRequest, scope: SourceScope, concepts: list[str] | None
    ) -> list[Candidate]: ...


class QdrantCandidateIndex:
    """Read-only existing semantic space, with mandatory exact ownership filters."""

    embedding_seconds: float = 0.0
    indexed_point_count: int | None = None

    def search(
        self, request: RetrievalRequest, scope: SourceScope, concepts: list[str] | None
    ) -> list[Candidate]:
        from ..db import vector_store as vs

        if settings.embedding_provider != "ollama":
            raise IndexUnavailable("PROVIDER_UNAVAILABLE")
        try:
            embedding_started = time.perf_counter()
            vector = vs._embed([request.query], task_type="retrieval_query")[0]
            self.embedding_seconds = time.perf_counter() - embedding_started
            space = EmbeddingSpace.model_validate(vs.embedding_provenance())
            if len(vector) != space.embedding_dimension or not all(
                math.isfinite(v) for v in vector
            ):
                raise IndexUnavailable("PROVIDER_UNAVAILABLE")
            fields: dict[str, str | int | bool] = {
                "user_id": str(scope.user_id),
                "source_id": scope.source_id,
                "source_version": f"v{scope.source_version}",
                "canonical_source_version": scope.source_version,
                "layer": "A",
                "retrieval_allowed": True,
                "injection_status": "sanitized",
                "chunking_policy_version": "educational-chunks-v1",
                **space.model_dump(),
            }
            if request.topic_id:
                fields["topic_id"] = request.topic_id
            if request.subtopic_id:
                fields["subtopic_id"] = request.subtopic_id
            conditions = [
                qm.FieldCondition(key=k, match=qm.MatchValue(value=v))
                for k, v in fields.items()
            ]
            if concepts is not None:
                conditions.append(
                    qm.FieldCondition(
                        key="concept_ids", match=qm.MatchAny(any=concepts)
                    )
                )
            filter_ = qm.Filter(must=conditions)
            client = vs.get_client()
            base_filter = qm.Filter(
                must=[
                    c
                    for c in conditions
                    if c.key not in {"topic_id", "subtopic_id", "concept_ids"}
                ]
            )
            self.indexed_point_count = client.count(
                settings.collection_name, count_filter=base_filter, exact=True
            ).count
            if self.indexed_point_count == 0:
                raise IndexUnavailable("INDEX_UNAVAILABLE")
            hits = client.search(
                collection_name=settings.collection_name,
                query_vector=vector,
                query_filter=filter_,
                limit=MAX_CANDIDATES,
                score_threshold=MIN_SEMANTIC_SCORE,
            )
            return [
                Candidate(
                    point_id=str(h.id),
                    score=float(h.score),
                    payload=TypeAdapter(dict[str, JsonValue]).validate_python(
                        h.payload or {}
                    ),
                )
                for h in hits
            ]
        except IndexUnavailable:
            raise
        except ProcessingError:
            raise IndexUnavailable("PROVIDER_UNAVAILABLE") from None
        except (
            ValidationError,
            OSError,
            RuntimeError,
            ValueError,
            UnexpectedResponse,
            ResponseHandlingException,
            httpx.HTTPError,
        ):
            raise IndexUnavailable("INDEX_UNAVAILABLE") from None


class RetrievalService:
    """Request-scoped canonical reads; no local fallback, cache, publication or writes."""

    def __init__(
        self, index: CandidateIndex | None = None, budget: EvidenceBudget | None = None
    ) -> None:
        self.index = index or QdrantCandidateIndex()
        self.budget = budget or EvidenceBudget()

    def retrieve(
        self, context: KnowledgeRepository, request: RetrievalRequest
    ) -> EvidenceBundle:
        started = time.perf_counter()
        scope = context.scope(request.source_id, request.source_version)
        service = KnowledgeService(context)
        mapping = service.get_knowledge_map(scope)
        if mapping.knowledge_state != "READY":
            raise KnowledgeError("NOT_READY")
        allowed: set[str] = set()
        all_concepts = {
            c.concept_id: c
            for t in mapping.topics
            for s in t.subtopics
            for c in s.concepts
        }
        topic_ids = {t.topic_id for t in mapping.topics}
        sub_ids = {
            s.subtopic_id: t.topic_id for t in mapping.topics for s in t.subtopics
        }
        if request.topic_id and request.topic_id not in topic_ids:
            raise KnowledgeError("NOT_FOUND")
        if request.subtopic_id and (
            request.subtopic_id not in sub_ids
            or request.topic_id
            and sub_ids[request.subtopic_id] != request.topic_id
        ):
            raise KnowledgeError("NOT_FOUND")
        for topic in mapping.topics:
            if request.topic_id and topic.topic_id != request.topic_id:
                continue
            for sub in topic.subtopics:
                if request.subtopic_id and sub.subtopic_id != request.subtopic_id:
                    continue
                allowed.update(c.concept_id for c in sub.concepts)
        if request.concept_ids is not None:
            if not set(request.concept_ids) <= allowed:
                raise KnowledgeError("NOT_FOUND")
            allowed.intersection_update(request.concept_ids)
        if request.include_prerequisites:
            pending = list(allowed)
            expanded = 0
            while pending:
                for cid in all_concepts[pending.pop()].prerequisite_concept_ids:
                    # Hierarchy selectors remain intersections even for prerequisites.
                    parent = next(
                        (
                            s
                            for t in mapping.topics
                            for s in t.subtopics
                            if any(c.concept_id == cid for c in s.concepts)
                        ),
                        None,
                    )
                    if (
                        parent is None
                        or request.subtopic_id
                        and parent.subtopic_id != request.subtopic_id
                        or request.topic_id
                        and sub_ids[parent.subtopic_id] != request.topic_id
                    ):
                        continue
                    if cid not in allowed:
                        if expanded >= MAX_PREREQUISITES:
                            raise KnowledgeError("PAYLOAD_TOO_LARGE")
                        allowed.add(cid)
                        pending.append(cid)
                        expanded += 1
        selected = any(
            (request.topic_id, request.subtopic_id, request.concept_ids is not None)
        )
        source = SupabaseSourceRepository(context.user, context._token, context.runtime)
        version = source.get_source_version(scope.source_id, scope.source_version)
        if version is None:
            raise KnowledgeError("NOT_FOUND")
        units = context.list_scoped_content(scope)
        lookup = {u.content_id: u.content for u in units}
        if request.content_ids is not None and not set(request.content_ids) <= set(
            lookup
        ):
            raise KnowledgeError("NOT_FOUND")
        safe = {
            s.content_id: s
            for s in (
                SanitizedContent.model_validate(r) for r in version.sanitized_content
            )
        }
        for unit in units:
            s = safe.get(unit.content_id)
            if (
                s is None
                or not s.retrieval_allowed
                or s.injection_status == "quarantined"
                or s.sanitized_text != unit.content.text
                or s.source_id != scope.source_id
                or s.source_version != f"v{scope.source_version}"
            ):
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        data = context.get_complete_knowledge_map(scope)
        chunks, _ = create_educational_chunks(
            scope,
            units,
            data,
            ChunkPolicy.model_validate(
                version.provenance.get("chunk_policy") or ChunkPolicy().model_dump()
            ),
            version.file_hash,
        )
        manifest = {c.chunk_id: c for c in chunks}
        digest = hashlib.sha256(
            json.dumps(
                sorted((c.chunk_id, c.text, c.metadata) for c in chunks), sort_keys=True
            ).encode()
        ).hexdigest()
        hydration_seconds = time.perf_counter() - started
        rejected: Counter[str] = Counter()
        search_start = time.perf_counter()
        space = EmbeddingSpace() if request.retrieval_mode == "semantic" else None
        if selected and not allowed or request.content_ids == []:
            candidates: list[Candidate] = []
        elif request.retrieval_mode == "exact":
            if not selected and request.content_ids is None:
                raise KnowledgeError("INVALID_SCOPE")
            candidates = [
                Candidate(point_id=c.chunk_id, score=0.0, payload={}) for c in chunks
            ]
        else:
            candidates = self.index.search(
                request, scope, sorted(allowed) if selected else None
            )
        search_seconds = time.perf_counter() - search_start
        items: list[EvidenceItem] = []
        occupied: dict[str, list[tuple[int, int]]] = {}
        tokens = 0
        remaining = sorted(candidates, key=lambda c: (-c.score, c.point_id))
        ordered: list[Candidate] = []
        covered: set[str] = set()
        while remaining:

            def diversity(candidate: Candidate) -> tuple[bool, float, str]:
                key = (
                    str(candidate.payload.get("chunk_id"))
                    if space
                    else candidate.point_id
                )
                chunk = manifest.get(key)
                concepts = set(chunk.concept_ids) if chunk else set()
                if selected:
                    concepts.intersection_update(allowed)
                return (
                    not bool(concepts - covered),
                    -candidate.score,
                    candidate.point_id,
                )

            candidate = min(remaining, key=diversity)
            remaining.remove(candidate)
            ordered.append(candidate)
            key = (
                str(candidate.payload.get("chunk_id")) if space else candidate.point_id
            )
            if key in manifest:
                covered.update(manifest[key].concept_ids)
        for candidate in ordered:
            p = candidate.payload
            cid = (
                str(p.get("chunk_id"))
                if request.retrieval_mode == "semantic"
                else candidate.point_id
            )
            chunk = manifest.get(cid)
            if chunk is None:
                rejected["stale_chunk"] += 1
                continue
            meta = ChunkMetadata.model_validate(chunk.metadata)
            if request.retrieval_mode == "semantic":
                from ..db.vector_store import _point_id

                expected = {
                    "user_id": str(scope.user_id),
                    "source_id": scope.source_id,
                    "source_version": f"v{scope.source_version}",
                    "layer": "A",
                    "retrieval_allowed": True,
                    "injection_status": "sanitized",
                    "source_hash": version.file_hash,
                    "content_ids": chunk.content_ids,
                    "concept_ids": chunk.concept_ids,
                    **meta.model_dump(mode="json"),
                    **EmbeddingSpace().model_dump(),
                }
                if (
                    candidate.point_id != str(_point_id(chunk))
                    or not math.isfinite(candidate.score)
                    or any(p.get(k) != v for k, v in expected.items())
                ):
                    rejected["manifest_mismatch"] += 1
                    continue
            if (
                request.topic_id
                and meta.topic_id != request.topic_id
                or request.subtopic_id
                and meta.subtopic_id != request.subtopic_id
            ):
                rejected["selector_mismatch"] += 1
                continue
            for span in meta.canonical_spans:
                if (
                    request.content_ids is not None
                    and span.content_id not in request.content_ids
                ):
                    continue
                unit = lookup[span.content_id]
                associations = [
                    e
                    for e in data.evidence
                    if e.content_id == span.content_id
                    and e.char_start is not None
                    and e.char_end is not None
                    and e.char_start < span.char_end
                    and e.char_end > span.char_start
                    and (not selected or e.concept_id in allowed)
                ]
                bounds = (
                    [(span.char_start, span.char_end)]
                    if not selected and request.retrieval_mode != "exact"
                    else [
                        (
                            max(span.char_start, e.char_start),
                            min(span.char_end, e.char_end),
                        )
                        for e in associations
                        if e.char_start is not None and e.char_end is not None
                    ]
                )
                for begin, end in sorted(set(bounds)):
                    if any(
                        a <= begin and b >= end
                        for a, b in occupied.get(span.content_id, [])
                    ):
                        rejected["duplicate_overlap"] += 1
                        continue
                    # Collapse partial overlaps by emitting only previously unseen canonical text.
                    for a, b in occupied.get(span.content_id, []):
                        if a <= begin < b:
                            begin = b
                        if a < end <= b:
                            end = a
                    if end <= begin:
                        continue
                    ceiling = min(
                        self.budget.max_item_tokens,
                        self.budget.max_total_tokens - tokens,
                    )
                    while end > begin and _token_len(unit.text[begin:end]) > ceiling:
                        end -= max(1, (end - begin) // 8)
                    if end <= begin or len(items) >= request.max_items:
                        continue
                    excerpt = unit.text[begin:end]
                    concepts = sorted(
                        {
                            e.concept_id
                            for e in associations
                            if e.char_start is not None
                            and e.char_end is not None
                            and e.char_start < end
                            and e.char_end > begin
                        }
                    )
                    eid = str(
                        uuid5(
                            NAMESPACE_URL,
                            f"{scope.user_id}:{scope.source_id}:{scope.source_version}:{span.content_id}:{begin}:{end}:{excerpt}",
                        )
                    )
                    location = (
                        f"Page {unit.page_start or unit.page_number}"
                        if unit.page_start or unit.page_number
                        else (
                            f"Slide {unit.slide_number}"
                            if unit.slide_number
                            else (
                                f"Timestamp {unit.timestamp_start}–{unit.timestamp_end}"
                                if unit.timestamp_start is not None
                                else (
                                    f"Section {unit.section}"
                                    if unit.section
                                    else f"Content {unit.sequence_index + 1}"
                                )
                            )
                        )
                    )
                    title = " / ".join(unit.heading_path)
                    items.append(
                        EvidenceItem(
                            evidence_id=eid,
                            content_id=span.content_id,
                            chunk_id=cid,
                            source_id=scope.source_id,
                            source_version=scope.source_version,
                            topic_id=meta.topic_id,
                            subtopic_id=meta.subtopic_id,
                            concept_ids=concepts,
                            excerpt=excerpt,
                            char_start=begin,
                            char_end=end,
                            page_start=unit.page_start or unit.page_number,
                            page_end=unit.page_end or unit.page_number,
                            slide=unit.slide_number,
                            timestamp_start=unit.timestamp_start,
                            timestamp_end=unit.timestamp_end,
                            chapter=unit.chapter,
                            section=unit.section,
                            heading_path=unit.heading_path,
                            content_role=meta.content_role,
                            retrieval_score=candidate.score if space else None,
                            citation=location + (f" — {title}" if title else ""),
                            embedding_provenance=space,
                        )
                    )
                    tokens += _token_len(excerpt)
                    occupied.setdefault(span.content_id, []).append((begin, end))
        bundle = EvidenceBundle(
            indexed_point_count=(
                self.index.indexed_point_count
                if isinstance(self.index, QdrantCandidateIndex)
                else None
            ),
            evidence_bundle_id=str(uuid4()),
            scope=scope,
            purpose=request.purpose,
            query=request.query,
            topic_id=request.topic_id,
            subtopic_id=request.subtopic_id,
            concept_ids=sorted(allowed) if selected else [],
            items=items,
            manifest_digest=digest,
            outcome="READY" if items else "INSUFFICIENT_EVIDENCE",
            rejected_candidates=dict(rejected),
            token_count=tokens,
            token_budget=self.budget,
            embedding_provenance=space,
            latencies={
                "hydration_seconds": hydration_seconds,
                "search_seconds": search_seconds,
                "embedding_seconds": (
                    self.index.embedding_seconds
                    if isinstance(self.index, QdrantCandidateIndex)
                    else 0.0
                ),
                "total_seconds": time.perf_counter() - started,
            },
        )
        logger.info(
            "canonical_retrieval",
            extra={
                "bundle_id": bundle.evidence_bundle_id,
                "user_id": str(scope.user_id),
                "source_id": scope.source_id,
                "source_version": scope.source_version,
                "candidate_count": len(candidates),
                "accepted_count": len(items),
                "rejections": dict(rejected),
                "manifest_digest": digest,
                "latencies": bundle.latencies,
            },
        )
        return bundle
