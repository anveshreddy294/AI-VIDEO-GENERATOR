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
from ..core.processing_errors import ProcessingError, ProcessingCode
from ..services.schemas import (
    AuthoritativeSourceChunk,
    AuthoritativeVideoChunk,
    LayerAChunk,
    LayerBVideoSceneChunk,
    LayerChunk,
    RichChunk,
    StageDiagnostics,
)

import atexit
import contextvars
import threading

logger = logging.getLogger(__name__)

_client_instance: QdrantClient | None = None
_client_lock = threading.Lock()
_embed_diagnostics_var: contextvars.ContextVar[StageDiagnostics | None] = contextvars.ContextVar(
    "embed_diagnostics", default=None
)


def close_client() -> None:
    """Close active Qdrant client connection and release underlying file handles."""
    global _client_instance
    with _client_lock:
        if _client_instance is not None:
            try:
                _client_instance.close()
            except Exception:
                pass
            _client_instance = None


atexit.register(close_client)


_active_embedding_dim: int = 768
_resolved_ollama_model: str | None = None
_embedding_fallback_warnings: set[tuple[str, str]] = set()
SUPPORTED_EMBEDDING_FALLBACKS = {"embeddinggemma", "nomic-embed-text"}


def get_last_embed_diagnostics() -> StageDiagnostics | None:
    """Retrieve execution diagnostics for the most recent embedding pass in current context."""
    return _embed_diagnostics_var.get()


def get_client() -> QdrantClient:
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    with _client_lock:
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
            except Exception as probe_err:
                logger.info(
                    "Local Qdrant server unreachable at %s (%s); falling back to embedded storage at %s",
                    url,
                    probe_err,
                    settings.qdrant_path,
                )

        try:
            settings.qdrant_path.mkdir(parents=True, exist_ok=True)
            _client_instance = QdrantClient(path=str(settings.qdrant_path))
            return _client_instance
        except Exception as emb_err:
            logger.error(
                "[vector_store] Failed to initialize embedded Qdrant store at %s: %s",
                settings.qdrant_path,
                emb_err,
            )
            raise RuntimeError(
                f"Vector database unavailable: remote '{url}' is unreachable and embedded store at "
                f"'{settings.qdrant_path}' failed to open ({emb_err})."
            ) from emb_err


def _deterministic_embedding(text: str, dim: int | None = None) -> list[float]:
    """Generate a deterministic normalized vector representation for offline/fallback mode."""
    if settings.embedding_provider != 'mock':
        raise ProcessingError('EMBEDDING_FAILED', 'Synthetic embeddings are disabled outside explicit test mode')
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


_QUERY_EMBED_CACHE: dict[tuple[str, str, str], list[float]] = {}
_QUERY_EMBED_CACHE_MAX = 512


def clear_embed_cache() -> None:
    _QUERY_EMBED_CACHE.clear()


def _embedding_failed(code: ProcessingCode) -> None:
    """Record a safe failure for the legacy optional-vector boundary."""
    _embed_diagnostics_var.set(StageDiagnostics(provider_used='ollama', error_code=code,
        grounding_verified=False, dimension_validated=False, configured_model=settings.embedding_model))


def _embed_ollama(texts: list[str], task_type: str = "retrieval_document") -> list[list[float]] | None:
    """Use one configured model; only model-not-found permits the explicit supported fallback."""
    import json
    import math
    import urllib.error
    import urllib.request
    if not texts:
        return []
    if len(texts) == 1 and task_type == "retrieval_query" and "PYTEST_CURRENT_TEST" not in os.environ:
        cache_key = (texts[0], task_type, settings.embedding_model)
        if cache_key in _QUERY_EMBED_CACHE:
            return [_QUERY_EMBED_CACHE[cache_key]]
    global _resolved_ollama_model
    _resolved_ollama_model = None
    primary = settings.embedding_model
    fallback = settings.embedding_fallback_model
    candidates = [primary]
    if fallback and fallback != primary and fallback.split(':')[0] in SUPPORTED_EMBEDDING_FALLBACKS:
        candidates.append(fallback)
    base_url = settings.ollama_base_url.rstrip('/')
    for index, model in enumerate(candidates):
        prefix = 'search_query: ' if task_type == 'retrieval_query' else 'search_document: '
        formatted = ([text if text.startswith(('search_query: ', 'search_document: ')) else prefix + text
                      for text in texts] if 'nomic-embed' in model else texts)
        payload = json.dumps({'model': model, 'input': formatted, 'truncate': False,
                              'keep_alive': getattr(settings, 'ollama_keep_alive', '15m')}).encode('utf-8')
        request = urllib.request.Request(base_url + '/api/embed', data=payload,
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=settings.ollama_timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            if error.code == 404 and index + 1 < len(candidates):
                pair = (primary, fallback)
                if pair not in _embedding_fallback_warnings:
                    logger.warning('Embedding model %s unavailable; using configured fallback %s', primary, fallback)
                    _embedding_fallback_warnings.add(pair)
                continue
            _embedding_failed('EMBEDDING_MODEL_UNAVAILABLE' if error.code == 404 else 'EMBEDDING_FAILED')
            return None
        except (urllib.error.URLError, TimeoutError):
            _embedding_failed('EMBEDDING_MODEL_UNAVAILABLE')
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            _embedding_failed('EMBEDDING_FAILED')
            return None
        vectors = data.get('embeddings') if isinstance(data, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            _embedding_failed('EMBEDDING_FAILED')
            return None
        clean: list[list[float]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != _active_embedding_dim:
                _embedding_failed('EMBEDDING_FAILED')
                return None
            if any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in vector):
                _embedding_failed('EMBEDDING_FAILED')
                return None
            row = [float(value) for value in vector]
            if not any(value != 0 for value in row):
                _embedding_failed('EMBEDDING_FAILED')
                return None
            clean.append(row)
        resolved = data.get('model', model)
        if not isinstance(resolved, str) or resolved.split(':')[0] != model.split(':')[0]:
            _embedding_failed('EMBEDDING_FAILED')
            return None
        _resolved_ollama_model = resolved
        _embed_diagnostics_var.set(StageDiagnostics(provider_used='ollama', fallback_used=index > 0,
            fallback_reason='Configured model unavailable' if index > 0 else None,
            grounding_verified=True, dimension_validated=True, configured_model=primary,
            model_used=resolved, vector_dimension=len(clean[0])))
        if len(texts) == 1 and len(clean) == 1 and task_type == "retrieval_query" and "PYTEST_CURRENT_TEST" not in os.environ:
            cache_key = (texts[0], task_type, settings.embedding_model)
            if len(_QUERY_EMBED_CACHE) >= _QUERY_EMBED_CACHE_MAX:
                try:
                    _QUERY_EMBED_CACHE.pop(next(iter(_QUERY_EMBED_CACHE)))
                except KeyError:
                    pass
            _QUERY_EMBED_CACHE[cache_key] = clean[0]
        return clean
    _embedding_failed('EMBEDDING_MODEL_UNAVAILABLE')
    return None


def _embed(texts: list[str], task_type: str = "retrieval_document") -> list[list[float]]:
    """Production embeddings fail closed; test vectors require an explicit independent provider."""
    if not texts:
        return []
    if settings.embedding_provider == 'mock':
        _embed_diagnostics_var.set(StageDiagnostics(provider_used='deterministic_test', fallback_used=False,
            grounding_verified=False, dimension_validated=True, vector_dimension=_active_embedding_dim))
        return [_deterministic_embedding(text) for text in texts]
    if settings.embedding_provider != 'ollama':
        raise ProcessingError('EMBEDDING_MODEL_UNAVAILABLE', 'Embedding provider is unavailable')
    vectors = _embed_ollama(texts, task_type=task_type)
    if vectors is not None:
        return vectors
    diagnostics = get_last_embed_diagnostics()
    code: ProcessingCode = ('EMBEDDING_MODEL_UNAVAILABLE' if diagnostics and
                            diagnostics.error_code == 'EMBEDDING_MODEL_UNAVAILABLE' else 'EMBEDDING_FAILED')
    raise ProcessingError(code, 'Configured embedding model unavailable' if code == 'EMBEDDING_MODEL_UNAVAILABLE'
                          else 'Embedding generation or vector validation failed')


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Authoritative document embedding entrypoint for indexing (retrieval_document)."""
    return _embed(texts, task_type="retrieval_document")


def embed_query(query: str | list[str]) -> list[float] | list[list[float]]:
    """Authoritative query embedding entrypoint for vector search (retrieval_query)."""
    if isinstance(query, str):
        res = _embed([query], task_type="retrieval_query")
        return res[0] if res else []
    return _embed(query, task_type="retrieval_query")


_INDEXES_ENSURED: set[str] = set()


def ensure_collection(client: QdrantClient, expected_dim: int | None = None) -> None:
    """Validate an existing collection without ever deleting user data, ensuring payload indexes."""
    expected_dim = expected_dim or _active_embedding_dim
    coll_key = f"{settings.collection_name}:{expected_dim}"
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

    if coll_key in _INDEXES_ENSURED:
        return

    # Payload indexes only apply to server Qdrant; skip on local/in-memory Qdrant
    is_local = type(getattr(client, "_client", None)).__name__ in ("QdrantLocal", "LocalQdrant")
    if not is_local:
        # SEC / PERF: Ensure payload indexes for high-speed tenant-isolated retrieval
        index_fields = [
            ("layer", qmodels.PayloadSchemaType.KEYWORD),
            ("source_id", qmodels.PayloadSchemaType.KEYWORD),
            ("user_id", qmodels.PayloadSchemaType.KEYWORD),
            ("session_id", qmodels.PayloadSchemaType.KEYWORD),
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

    _INDEXES_ENSURED.add(coll_key)


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
        payload=chunk.model_dump()
        if isinstance(chunk,RichChunk) and chunk.metadata.get('chunking_policy_version'):
            from ..services.educational_chunker import ChunkMetadata
            payload.update(ChunkMetadata.model_validate(chunk.metadata).model_dump(mode='json'))
        return payload

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



class RetrievalUnavailable(RuntimeError):
    """Semantic retrieval cannot safely provide verified evidence."""


def _require_supported_retrieval_mode() -> None:
    """Legacy retrieval lacks canonical hydration; reject before any vector/provider call."""
    if settings.database_provider not in {'file', 'local'}:
        raise RetrievalUnavailable('Canonical evidence verification is required for this database provider')


def embedding_provenance() -> dict[str, str | int]:
    """Describe the model that actually produced the last validated vector batch."""
    diagnostic = get_last_embed_diagnostics()
    if settings.embedding_provider == "mock":
        return {"embedding_provider": "mock", "embedding_model": "deterministic_test",
                "embedding_dimension": _active_embedding_dim, "embedding_kind": "synthetic_test",
                "embedding_version": "1"}
    if (diagnostic is None or not diagnostic.dimension_validated or
            diagnostic.provider_used != "ollama" or not diagnostic.model_used or
            diagnostic.vector_dimension != _active_embedding_dim):
        raise ProcessingError("EMBEDDING_FAILED", "Validated embedding provenance unavailable")
    return {"embedding_provider": diagnostic.provider_used,
            "embedding_model": diagnostic.model_used.removesuffix(":latest"),
            "embedding_dimension": _active_embedding_dim,
            "embedding_kind": "semantic", "embedding_version": "1"}


def semantic_filter_conditions(model: str | None = None) -> list[qmodels.FieldCondition]:
    """Confine production queries to the exact validated query embedding space."""
    if settings.embedding_provider == "mock":
        return []  # Explicit isolated test mode retains historical fixture compatibility.
    expected = (embedding_provenance() if model is None else {
        "embedding_provider": "ollama", "embedding_model": model.removesuffix(":latest"),
        "embedding_dimension": _active_embedding_dim, "embedding_kind": "semantic", "embedding_version": "1"})
    return [qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))
            for key, value in expected.items()]

_index_timings: contextvars.ContextVar[dict[str, float]] = contextvars.ContextVar("index_timings", default={})

def get_index_timings() -> dict[str, float]:
    """Inference/index timing only; no payloads, credentials or embedding changes."""
    return dict(_index_timings.get())

def upsert_chunks(chunks: list[LayerAChunk]) -> int:
    if not chunks:
        return 0

    if settings.embedding_provider == 'mock' and any(isinstance(c,RichChunk)
            and c.metadata.get('chunking_policy_version') for c in chunks):
        raise ProcessingError('EMBEDDING_MODEL_UNAVAILABLE','Educational indexing requires semantic embeddings')

    _index_timings.set({})
    client = get_client()
    embedding_started = time.perf_counter()
    vectors = _embed([c.text for c in chunks])
    embedding_ms = (time.perf_counter()-embedding_started)*1000
    ensure_collection(client, len(vectors[0]))
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding count mismatch")
    points = [qmodels.PointStruct(id=_point_id(c), vector=v, payload={**_payload(c), **embedding_provenance()}) for c, v in zip(chunks, vectors)]
    qdrant_started = time.perf_counter()
    client.upsert(collection_name=settings.collection_name, points=points, wait=True)
    stored = client.retrieve(collection_name=settings.collection_name, ids=[p.id for p in points], with_payload=True)
    if {str(p.id) for p in stored} != {str(p.id) for p in points}:
        raise RuntimeError("Vector storage verification failed")
    _index_timings.set({"embedding_ms":embedding_ms,"qdrant_index_ms":(time.perf_counter()-qdrant_started)*1000})
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
        qmodels.PointStruct(id=_point_id(s), vector=v, payload={**_payload(s), **embedding_provenance()})
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
    user_id: str = "student_default",
) -> list[dict[str, Any]]:
    """Legacy compatibility search: delegates to authoritative search_source_chunks."""
    _require_supported_retrieval_mode()
    return search_source_chunks(
        user_id=user_id,
        source_id=source_id or "",
        query=query,
        top_k=limit,
        score_threshold=score_threshold,
    )


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
    _require_supported_retrieval_mode()
    try:
        client = get_client()
        vector = _embed([query], task_type="retrieval_query")[0]
        must_conditions: list[Any] = [
            qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A")),
            qmodels.FieldCondition(key="retrieval_allowed", match=qmodels.MatchValue(value=True)),
        ]
        if source_id:
            must_conditions.append(
                qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id))
            )
        should_conditions: list[Any] = []
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
            # Enforce session isolation: match this session's chunks OR canonical document chunks
            # (which have no session_id). Never match chunks tagged with a different session_id.
            should_conditions.extend([
                qmodels.FieldCondition(key="session_id", match=qmodels.MatchValue(value=session_id)),
                qmodels.IsNullCondition(is_null=qmodels.PayloadField(key="session_id")),
                qmodels.IsEmptyCondition(is_empty=qmodels.PayloadField(key="session_id")),
            ])
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

        must_conditions.extend(semantic_filter_conditions())
        filter_kwargs: dict[str, Any] = {"must": must_conditions}
        if should_conditions:
            filter_kwargs["should"] = should_conditions

        if settings.embedding_provider != "mock" and client.count(
                settings.collection_name, count_filter=qmodels.Filter(**filter_kwargs), exact=True).count == 0:
            raise RetrievalUnavailable("No compatible semantic vectors available for this source")
        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=top_k,
            query_filter=qmodels.Filter(**filter_kwargs),
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
    except RetrievalUnavailable:
        raise
    except Exception as exc:
        logger.warning("[vector_store] search_source_chunks failed: %s", type(exc).__name__)
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
    _require_supported_retrieval_mode()
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
    _require_supported_retrieval_mode()
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

        must_conditions.extend(semantic_filter_conditions(model=settings.embedding_model))
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
