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
import uuid
from typing import Any

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ..core.config import settings
from ..services.schemas import AuthoritativeSourceChunk, AuthoritativeVideoChunk, LayerAChunk, RichChunk

logger = logging.getLogger(__name__)

_client_instance: QdrantClient | None = None


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


def _deterministic_embedding(text: str, dim: int = 768) -> list[float]:
    """Generate a deterministic normalized vector representation for offline/fallback mode."""
    import hashlib
    vec = [0.0] * dim
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts using OmniRoute, Gemini, or deterministic fallback."""
    # 1. Try OmniRoute embeddings if configured
    if settings.llm_provider == "omniroute" and settings.omniroute_api_key:
        try:
            import json
            import urllib.request
            url = f"{settings.omniroute_base_url}/embeddings"
            payload = json.dumps({
                "model": "text-embedding-3-small",
                "input": texts,
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.omniroute_api_key}",
            }
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "data" in data and isinstance(data["data"], list):
                    return [item["embedding"] for item in data["data"]]
        except Exception as exc:
            logger.info(f"[vector_store] OmniRoute embedding endpoint not used: {exc}")

    # 2. Try Gemini API if key is set
    if settings.gemini_api_key:
        try:
            genai.configure(api_key=settings.gemini_api_key)
            result = genai.embed_content(
                model=settings.embedding_model,
                content=texts,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as exc:
            logger.warning(f"[vector_store] Gemini embed failed: {exc}. Using fallback.")

    # 3. Deterministic normalized embedding fallback
    return [_deterministic_embedding(t) for t in texts]


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if settings.collection_name in existing:
        return

    probe = _embed(["dimension probe"])
    client.create_collection(
        collection_name=settings.collection_name,
        vectors_config=qmodels.VectorParams(
            size=len(probe[0]),
            distance=qmodels.Distance.COSINE,
        ),
    )


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
    ensure_collection(client)

    texts = [c.text for c in chunks]
    vectors = _embed(texts)

    points = [
        qmodels.PointStruct(
            id=_point_id(chunk),
            vector=vector,
            payload=_payload(chunk),
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    if points:
        client.upsert(collection_name=settings.collection_name, points=points)
    return len(points)


def search_layer_a(query: str, limit: int = 5) -> list[dict[str, Any]]:
    client = get_client()
    vector = _embed([query])[0]
    hits = client.search(
        collection_name=settings.collection_name,
        query_vector=vector,
        limit=limit,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A"))]
        ),
    )
    return [hit.payload for hit in hits]


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

        must_conditions: list[Any] = []
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