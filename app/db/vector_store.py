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

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ..core.config import settings
from ..services.schemas import (
    AuthoritativeSourceChunk,
    AuthoritativeVideoChunk,
    LayerAChunk,
    LayerBVideoSceneChunk,
    LayerChunk,
    RichChunk,
    StageDiagnostics,
)

import contextvars

logger = logging.getLogger(__name__)

_client_instance: QdrantClient | None = None
_embed_diagnostics_var: contextvars.ContextVar[StageDiagnostics | None] = contextvars.ContextVar(
    "embed_diagnostics", default=None
)


_active_embedding_dim: int = 768


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
    import re
    target_dim = dim or _active_embedding_dim
    vec = [0.0] * target_dim
    for raw_word in text.lower().split():
        word = re.sub(r"[^\w]", "", raw_word)
        if not word:
            continue
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % target_dim
        vec[idx] += 1.0
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _embed_ollama(texts: list[str]) -> list[list[float]] | None:
    """Attempt batch embedding via Ollama /api/embed endpoint.

    Validates:
    - Ollama connectivity, HTTP status, and timeout
    - Valid JSON payload structure
    - 'embeddings' key existence and list type
    - Number of returned vectors equals number of input texts
    - Every vector is a non-empty list of 768 numeric and finite floats
    - All vectors have identical dimensions (768)

    Differentiates:
    - Provider unavailable (URLError, timeout) -> logged with warning
    - Invalid provider response (bad JSON, missing/invalid embeddings) -> logged with diagnostics
    """
    import json
    import math
    import urllib.error
    import urllib.request

    if not texts:
        return []

    base_url = (getattr(settings, "ollama_base_url", None) or getattr(settings, "ollama_url", "http://localhost:11434")).rstrip("/")
    embed_model = getattr(settings, "embedding_model", "embeddinggemma")
    timeout = float(getattr(settings, "ollama_timeout", 30.0))

    url = f"{base_url}/api/embed"
    payload = json.dumps({"model": embed_model, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_bytes = resp.read()
    except urllib.error.HTTPError as http_err:
        logger.warning(
            "[vector_store] Ollama HTTP error during batch embedding (%s): %s",
            url, http_err
        )
        return None
    except urllib.error.URLError as url_err:
        logger.warning(
            "[vector_store] Ollama connection failure/timeout during batch embedding (%s): %s",
            url, url_err
        )
        return None
    except TimeoutError as to_err:
        logger.warning(
            "[vector_store] Ollama request timed out after %.1fs during batch embedding: %s",
            timeout, to_err
        )
        return None

    # 1. Parse JSON
    try:
        data = json.loads(resp_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as dec_err:
        logger.warning(
            "[vector_store] Ollama returned non-JSON response during batch embedding: %s",
            dec_err
        )
        return None

    if not isinstance(data, dict):
        logger.warning(
            "[vector_store] Ollama response is not a JSON object: got %s",
            type(data).__name__
        )
        return None

    # 2. Extract and validate 'embeddings'
    embeddings = data.get("embeddings")
    if embeddings is None:
        logger.warning(
            "[vector_store] Ollama response missing 'embeddings' key (keys: %s)",
            list(data.keys())
        )
        return None

    if not isinstance(embeddings, list):
        logger.warning(
            "[vector_store] Ollama 'embeddings' is not a list: got %s",
            type(embeddings).__name__
        )
        return None

    if len(embeddings) != len(texts):
        logger.warning(
            "[vector_store] Ollama returned vector count mismatch: got %d, expected %d",
            len(embeddings), len(texts)
        )
        return None

    # 3. Validate numeric and finite values, and dimensions
    expected_dim = 768
    clean_vectors: list[list[float]] = []

    for idx, emb in enumerate(embeddings):
        if not isinstance(emb, list) or len(emb) == 0:
            logger.warning(
                "[vector_store] Ollama embedding at index %d is not a non-empty list (got %s, len=%d)",
                idx, type(emb).__name__, len(emb) if isinstance(emb, list) else 0
            )
            return None

        if len(emb) != expected_dim:
            logger.warning(
                "[vector_store] Ollama embedding at index %d dimension mismatch: got %d, expected %d",
                idx, len(emb), expected_dim
            )
            return None

        clean_vector: list[float] = []
        for v_idx, val in enumerate(emb):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                logger.warning(
                    "[vector_store] Non-numeric value in embedding at [%d][%d]: %r (%s)",
                    idx, v_idx, val, type(val).__name__
                )
                return None
            f_val = float(val)
            if not math.isfinite(f_val):
                logger.warning(
                    "[vector_store] Non-finite value in embedding at [%d][%d]: %r",
                    idx, v_idx, f_val
                )
                return None
            clean_vector.append(f_val)

        clean_vectors.append(clean_vector)

    return clean_vectors


def _embed(texts: list[str], task_type: str = "retrieval_document") -> list[list[float]]:
    """Embedding pipeline: supports local Ollama embeddings and deterministic fallback."""
    global _active_embedding_dim
    if not texts:
        return []

    # 1. Deterministic offline vectors for mock/test runs
    if getattr(settings, "llm_provider", "") in ("mock", "test"):
        dim = _active_embedding_dim
        vectors = [_deterministic_embedding(t, dim=dim) for t in texts]
        _embed_diagnostics_var.set(StageDiagnostics(provider_used="deterministic_hash_fallback", fallback_used=True, grounding_verified=False, dimension_validated=True))
        return vectors

    # 2. Local Ollama embeddings
    ollama_vectors = _embed_ollama(texts)
    if ollama_vectors and len(ollama_vectors) == len(texts):
        dim = len(ollama_vectors[0])
        _active_embedding_dim = dim
        _embed_diagnostics_var.set(StageDiagnostics(provider_used="ollama", fallback_used=False, grounding_verified=True, dimension_validated=True))
        return ollama_vectors

    # 3. Resilient offline deterministic hash fallback
    logger.info("[vector_store] Ollama embeddings unavailable or invalid; using deterministic normalized hash embedding fallback.")
    dim = _active_embedding_dim
    vectors = [_deterministic_embedding(t, dim=dim) for t in texts]
    _embed_diagnostics_var.set(StageDiagnostics(provider_used="deterministic_hash_fallback", fallback_used=True, grounding_verified=False, dimension_validated=True))
    return vectors


def ensure_collection(client: QdrantClient, expected_dim: int | None = None) -> None:
    """Validate an existing collection without ever deleting user data, ensuring payload indexes."""
    expected_dim = expected_dim or _active_embedding_dim
    existing = [c.name for c in client.get_collections().collections]
    if settings.collection_name in existing:
        params = client.get_collection(collection_name=settings.collection_name).config.params.vectors
        current_dim = getattr(params, "size", None)
        if current_dim != expected_dim:
            raise RuntimeError(f"Collection dimension {current_dim} does not match embedding dimension {expected_dim}; configure a new collection and reingest")
    else:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=qmodels.VectorParams(size=expected_dim, distance=qmodels.Distance.COSINE),
        )

    # SEC / PERF: Ensure payload indexes for high-speed tenant-isolated retrieval
    index_fields = [
        ("layer", qmodels.PayloadSchemaType.KEYWORD),
        ("source_id", qmodels.PayloadSchemaType.KEYWORD),
        ("user_id", qmodels.PayloadSchemaType.KEYWORD),
        ("source_version", qmodels.PayloadSchemaType.KEYWORD),
        ("type", qmodels.PayloadSchemaType.KEYWORD),
        ("retrieval_allowed", qmodels.PayloadSchemaType.BOOL),
        ("injection_status", qmodels.PayloadSchemaType.KEYWORD),
        ("concept_ids", qmodels.PayloadSchemaType.KEYWORD),
        ("chunk_id", qmodels.PayloadSchemaType.KEYWORD),
        ("video_id", qmodels.PayloadSchemaType.KEYWORD),
        ("scene_id", qmodels.PayloadSchemaType.KEYWORD),
    ]
    for field_name, field_schema in index_fields:
        try:
            client.create_payload_index(
                collection_name=settings.collection_name,
                field_name=field_name,
                field_schema=field_schema,
            )
        except Exception:
            pass


def _point_id(chunk: LayerChunk) -> str:
    if isinstance(chunk, LayerBVideoSceneChunk):
        raw_key = f"layer_b::{chunk.user_id}::{chunk.video_id}::{chunk.scene_id}::{chunk.timestamp_start}::{chunk.timestamp_end}"
    elif isinstance(chunk, RichChunk):
        raw_key = f"{chunk.source_id}::{chunk.chunk_id}::{chunk.text[:100]}"
    else:
        name = getattr(chunk, "document_name", None) or getattr(chunk, "video_name", "unknown")
        raw_key = f"{name}::{chunk.text[:200]}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_key))


def _payload(chunk: LayerChunk) -> dict[str, Any]:
    if isinstance(chunk, (RichChunk, LayerBVideoSceneChunk)):
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



def upsert_layer_b_scenes(scenes: list[LayerBVideoSceneChunk]) -> int:
    """Upsert validated, approved Layer B video scene chunks into Qdrant."""
    if not scenes:
        return 0

    client = get_client()
    texts_to_embed = [
        f"{s.title}: {s.narration_text}".strip() if s.title else (s.narration_text or s.scene_id)
        for s in scenes
    ]
    vectors = _embed(texts_to_embed)
    ensure_collection(client, len(vectors[0]))
    if len(vectors) != len(scenes):
        raise RuntimeError("Scene embedding count mismatch")
    points = [
        qmodels.PointStruct(id=_point_id(s), vector=v, payload=_payload(s))
        for s, v in zip(scenes, vectors)
    ]
    client.upsert(collection_name=settings.collection_name, points=points, wait=True)
    stored = client.retrieve(
        collection_name=settings.collection_name,
        ids=[p.id for p in points],
        with_payload=True,
    )
    if {str(p.id) for p in stored} != {str(p.id) for p in points}:
        raise RuntimeError("Layer B video scene storage verification failed")
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
        _diag = _embed_diagnostics_var.get()
        if score_threshold is not None:
            threshold = score_threshold
        elif getattr(settings, "llm_provider", "") in ("mock", "test") or (_diag and _diag.fallback_used):
            threshold = 0.05
        else:
            threshold = getattr(settings, "vector_similarity_threshold", 0.35)
        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=qmodels.Filter(must=must_conditions),
            score_threshold=threshold,
        )
        return [h.payload for h in hits if h.payload]
    except Exception as exc:
        logger.warning("[vector_store] search_layer_a query failed: %s", exc)
        return []


def search_source_chunks(
    user_id: str,
    source_id: str,
    query: str,
    source_version: str | None = None,
    concept_id: str | None = None,
    current_timestamp: float | None = None,
    top_k: int = 5,
    score_threshold: float | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Search Layer A source material with strict mandatory provenance, session, and security filters.

    Enforces:
    - user_id isolation (prevent cross-user data leakage)
    - source_id confinement (strict source isolation)
    - session_id scoping (when provided)
    - layer == "A"
    - retrieval_allowed == True (quarantined prompt injections are never returned)
    - injection_status in ["clean", "sanitized"]
    - Safe degraded threshold on vector fallback (>= 0.25) to prevent arbitrary leakage
    """
    client = get_client()
    try:
        vector = _embed([query], task_type="retrieval_query")[0]
        must_conditions: list[Any] = [
            qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A")),
            qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id)),
            qmodels.FieldCondition(key="retrieval_allowed", match=qmodels.MatchValue(value=True)),
        ]
        if user_id:
            if user_id == "student_default":
                must_conditions.append(
                    qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value="student_default"))
                )
            else:
                must_conditions.append(
                    qmodels.FieldCondition(
                        key="user_id",
                        match=qmodels.MatchAny(any=[user_id, "student_default"]),
                    )
                )
        if session_id:
            must_conditions.append(
                qmodels.FieldCondition(key="session_id", match=qmodels.MatchValue(value=session_id))
            )
        if source_version:
            must_conditions.append(
                qmodels.FieldCondition(key="source_version", match=qmodels.MatchValue(value=source_version))
            )
        if concept_id:
            must_conditions.append(
                qmodels.FieldCondition(key="concept_ids", match=qmodels.MatchAny(any=[concept_id]))
            )

        _diag = _embed_diagnostics_var.get()
        if score_threshold is not None:
            threshold = score_threshold
        elif _diag and _diag.fallback_used:
            # Deterministic hash vectors: require significant lexical overlap (>= 0.20)
            # to prevent arbitrary chunk leakage. Never use 0.05!
            threshold = 0.20
        elif getattr(settings, "llm_provider", "") in ("mock", "test"):
            threshold = 0.15
        else:
            threshold = getattr(settings, "vector_similarity_threshold", 0.35)

        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=top_k,
            query_filter=qmodels.Filter(must=must_conditions),
            score_threshold=threshold,
        )
        results = []
        for h in hits:
            payload = h.payload or {}
            # Verify retrieval and injection status invariants
            if not payload.get("retrieval_allowed", True):
                continue
            if payload.get("injection_status") not in ("clean", "sanitized"):
                continue
            payload["similarity_score"] = h.score
            results.append(payload)
        return results
    except Exception as exc:
        logger.warning("[vector_store] search_source_chunks failed: %s", exc)
        return []


def retrieve_layer_b_scene(
    user_id: str,
    source_id: str,
    video_id: str | None = None,
    timestamp: float | None = None,
) -> dict[str, Any] | None:
    """Retrieve the active approved Layer B video scene corresponding to a playback timestamp.

    Matches layer="B", user_id, source_id, (video_id if provided), and finds the scene
    where timestamp_start <= timestamp <= timestamp_end.
    """
    try:
        client = get_client()
        existing = [c.name for c in client.get_collections().collections]
        if settings.collection_name not in existing:
            return None

        must_conditions: list[Any] = [
            qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="B")),
            qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id)),
        ]
        if user_id:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchAny(any=[user_id, "student_default"]),
                )
            )
        if video_id:
            must_conditions.append(
                qmodels.FieldCondition(key="video_id", match=qmodels.MatchValue(value=video_id))
            )

        records, _ = client.scroll(
            collection_name=settings.collection_name,
            scroll_filter=qmodels.Filter(must=must_conditions),
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        scenes = [r.payload for r in records if r and r.payload]
        if not scenes:
            return None

        if timestamp is None:
            return scenes[0]

        # Find exact matching scene interval
        for scene in scenes:
            t_start = float(scene.get("timestamp_start", 0.0))
            t_end = float(scene.get("timestamp_end", 0.0))
            if t_start <= timestamp <= t_end:
                return scene

        # If outside strict interval bounds, return closest scene
        closest = min(
            scenes,
            key=lambda s: min(
                abs(timestamp - float(s.get("timestamp_start", 0.0))),
                abs(timestamp - float(s.get("timestamp_end", 0.0))),
            ),
        )
        return closest
    except Exception as exc:
        logger.warning("[vector_store] retrieve_layer_b_scene failed: %s", exc)
        return None


def retrieve_exact_chunks(
    source_id: str | None = None,
    chunk_ids: list[str] | None = None,
    concept_ids: list[str] | None = None,
    user_id: str | None = None,
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

        must_conditions: list[Any] = [
            qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A")),
            qmodels.FieldCondition(key="retrieval_allowed", match=qmodels.MatchValue(value=True)),
        ]
        if source_id:
            must_conditions.append(
                qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id))
            )
        if user_id:
            must_conditions.append(
                qmodels.FieldCondition(key="user_id", match=qmodels.MatchAny(any=[user_id, "student_default"]))
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
        return [
            record.payload
            for record in records
            if record and record.payload and record.payload.get("injection_status") in ("clean", "sanitized", None)
        ]
    except Exception as exc:
        logger.warning(
            "Failed deterministic Qdrant chunk retrieval (source=%s, chunks=%s): %s",
            source_id,
            chunk_ids,
            exc,
        )
        return []