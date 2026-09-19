"""Layer A RAG sync — embed RichChunks and upsert into Qdrant.

Every chunk carries layer: "A" and full provenance payload metadata:
{
  "layer": "A",
  "type": "rich_chunk",
  "chunk_id": "...",
  "source_id": "...",
  "asset_id": "...",
  "text": "...",
  "modality": "...",
  "chapter": "...",
  "section": "...",
  "concept_ids": [...],
  "content_ids": [...],
  "page_start": 15,
  "page_end": 16,
  "timestamp_start": ...,
  "timestamp_end": ...
}
"""

import logging
import time
import uuid
from typing import Any

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ..core.config import settings
from ..services.schemas import (
    AuthoritativeSourceChunk,
    AuthoritativeVideoChunk,
    LayerAChunk,
    RichChunk,
    StageDiagnostics,
)

import contextvars

logger = logging.getLogger(__name__)

_client_instance: QdrantClient | None = None
_embed_diagnostics_var: contextvars.ContextVar[StageDiagnostics | None] = contextvars.ContextVar(
    "embed_diagnostics", default=None
)


_active_embedding_dim: int = 3072 if "gemini-embedding-2" in getattr(settings, "embedding_model", "") else 768


def get_last_embed_diagnostics() -> StageDiagnostics | None:
    """Retrieve execution diagnostics for the most recent embedding pass in current context."""
    return _embed_diagnostics_var.get()


def get_client() -> QdrantClient:
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    url = (settings.qdrant_url or "").strip()

    if url.startswith("https://") or (
        url and not any(h in url for h in ("localhost", "127.0.0.1"))
    ):
        _client_instance = QdrantClient(url=url, api_key=settings.qdrant_api_key or None)
        return _client_instance

    if url:
        try:
            probe_client = QdrantClient(
                url=url, api_key=settings.qdrant_api_key or None, timeout=2.0
            )
            probe_client.get_collections()
            _client_instance = probe_client
            return _client_instance
        except Exception:
            logger.info(
                "Local Qdrant server unreachable at %s; using embedded storage at %s",
                url,
                settings.qdrant_path,
            )

    settings.qdrant_path.mkdir(parents=True, exist_ok=True)
    _client_instance = QdrantClient(path=str(settings.qdrant_path))
    return _client_instance


def _deterministic_embedding(text: str, dim: int | None = None) -> list[float]:
    """Generate a deterministic normalized vector representation for offline/fallback mode."""
    import hashlib
    target_dim = dim or _active_embedding_dim
    vec = [0.0] * target_dim
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % target_dim
        vec[idx] += 1.0
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _embed(texts: list[str], task_type: str = "retrieval_document") -> list[list[float]]:
    """Require genuine embeddings; never mix hash vectors into the collection."""
    global _active_embedding_dim
    import math
    if not texts:
        return []
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    result = genai.embed_content(model=settings.embedding_model, content=texts, task_type=task_type)
    vectors = result.get("embedding", [])
    if len(vectors) != len(texts) or not vectors or not vectors[0]:
        raise RuntimeError("Embedding provider returned an incomplete batch")
    dim = len(vectors[0])
    if any(len(v) != dim or not all(math.isfinite(x) for x in v) or not any(v) for v in vectors):
        raise RuntimeError("Embedding provider returned invalid vectors")
    _active_embedding_dim = dim
    _embed_diagnostics_var.set(StageDiagnostics(provider_used="gemini", fallback_used=False, grounding_verified=False))
    return vectors


def ensure_collection(client: QdrantClient, expected_dim: int | None = None) -> None:
    """Validate an existing collection without ever deleting user data."""
    expected_dim = expected_dim or _active_embedding_dim
    existing = [c.name for c in client.get_collections().collections]
    if settings.collection_name in existing:
        params = client.get_collection(collection_name=settings.collection_name).config.params.vectors
        current_dim = getattr(params, "size", None)
        if current_dim != expected_dim:
            raise RuntimeError(f"Collection dimension {current_dim} does not match embedding dimension {expected_dim}; configure a new collection and reingest")
        return
    client.create_collection(collection_name=settings.collection_name,
        vectors_config=qmodels.VectorParams(size=expected_dim, distance=qmodels.Distance.COSINE))


def _point_id(chunk: LayerAChunk) -> str:
    if isinstance(chunk, RichChunk):
        raw_key = f"{chunk.source_id}::{chunk.chunk_id}::{chunk.text[:100]}"
    else:
        name = getattr(chunk, "document_name", None) or getattr(chunk, "video_name", "unknown")
        raw_key = f"{name}::{chunk.text[:200]}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_key))


def _payload(chunk: LayerAChunk) -> dict[str, Any]:
    if isinstance(chunk, RichChunk):
        return chunk.model_dump()

    payload: dict[str, Any] = {
        "layer": "A",
        "type": chunk.type,
        "text": chunk.text,
    }
    if isinstance(chunk, AuthoritativeSourceChunk):
        payload["document_name"] = chunk.document_name
        payload["page"] = chunk.page
    elif isinstance(chunk, AuthoritativeVideoChunk):
        payload["video_name"] = chunk.video_name
        payload["start_timestamp"] = chunk.start_timestamp
        payload["end_timestamp"] = chunk.end_timestamp
    return payload


def upsert_chunks(chunks: list[LayerAChunk]) -> int:
    if not chunks:
        return 0

    client = get_client()
    vectors = _embed([c.text for c in chunks])
    ensure_collection(client, len(vectors[0]))
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding count mismatch")
    points = [qmodels.PointStruct(id=_point_id(c), vector=v, payload=_payload(c)) for c, v in zip(chunks, vectors)]
    client.upsert(collection_name=settings.collection_name, points=points, wait=True)
    stored = client.retrieve(collection_name=settings.collection_name, ids=[p.id for p in points], with_payload=True)
    if {str(p.id) for p in stored} != {str(p.id) for p in points}:
        raise RuntimeError("Vector storage verification failed")
    return len(points)


def search_layer_a(
    query: str,
    limit: int = 5,
    source_id: str | None = None,
    score_threshold: float | None = None,
) -> list[dict[str, Any]]:
    client = get_client()
    try:
        vector = _embed([query], task_type="retrieval_query")[0]
        must_conditions = [qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A"))]
        if source_id:
            must_conditions.append(qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id)))
        threshold = score_threshold if score_threshold is not None else getattr(settings, "vector_similarity_threshold", 0.35)
        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=qmodels.Filter(must=must_conditions),
            score_threshold=threshold,
        )
        return [h.payload for h in hits]
    except Exception as exc:
        logger.warning("[vector_store] search_layer_a query failed: %s", exc)
        return []


def retrieve_exact_chunks(
    source_id: str | None = None,
    chunk_ids: list[str] | None = None,
    concept_ids: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Deterministically retrieve exact stored chunks from Qdrant by provenance IDs.

    Bypasses semantic vector search when exact chunk_ids, source_id, or concept_ids
    are already known from the assessment / knowledge graph provenance trail.
    """
    try:
        client = get_client()
        existing_collections = [c.name for c in client.get_collections().collections]
        if settings.collection_name not in existing_collections:
            return []

        must_conditions: list[Any] = [qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A"))]
        if source_id:
            must_conditions.append(
                qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id))
            )
        if chunk_ids:
            clean_chunk_ids = [c for c in chunk_ids if c]
            if len(clean_chunk_ids) == 1:
                must_conditions.append(
                    qmodels.FieldCondition(key="chunk_id", match=qmodels.MatchValue(value=clean_chunk_ids[0]))
                )
            elif len(clean_chunk_ids) > 1:
                must_conditions.append(
                    qmodels.FieldCondition(key="chunk_id", match=qmodels.MatchAny(any=clean_chunk_ids))
                )
        if concept_ids:
            clean_concept_ids = [c for c in concept_ids if c]
            if clean_concept_ids:
                must_conditions.append(
                    qmodels.FieldCondition(key="concept_ids", match=qmodels.MatchAny(any=clean_concept_ids))
                )

        scroll_filter = qmodels.Filter(must=must_conditions) if must_conditions else None

        records, _ = client.scroll(
            collection_name=settings.collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [record.payload for record in records if record and record.payload]
    except Exception as exc:
        logger.warning(
            "Failed deterministic Qdrant chunk retrieval (source=%s, chunks=%s): %s",
            source_id,
            chunk_ids,
            exc,
        )
        return []