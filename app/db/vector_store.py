"""Layer A RAG sync — embed tagged chunks and upsert them into Qdrant.

Every chunk carries the `layer: "A"` security tag. Payload shape differs by type:

    Document chunk:  { layer, type=authoritative_source, document_name, text, page }
    Video chunk:     { layer, type=authoritative_video, video_name,
                       start_timestamp, end_timestamp, text }

Embeddings come from Gemini's embedding model. The collection is created
once with cosine similarity; subsequent upserts are idempotent by point id.
"""

import logging
import uuid
from typing import Any

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ..core.config import settings
from ..services.schemas import AuthoritativeSourceChunk, AuthoritativeVideoChunk, LayerAChunk

logger = logging.getLogger(__name__)

_client_instance: QdrantClient | None = None


def get_client() -> QdrantClient:
    """Return a singleton QdrantClient.
    
    If QDRANT_URL points to a cloud/remote instance, connect to it.
    If it points to localhost and is unreachable, or if embedded mode is desired,
    seamlessly falls back to embedded on-disk storage (zero-docker needed).
    """
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    url = (settings.qdrant_url or "").strip()

    # 1. Remote cloud instance (e.g. https://...cloud.qdrant.io)
    if url.startswith("https://") or (url and not any(h in url for h in ("localhost", "127.0.0.1"))):
        _client_instance = QdrantClient(url=url, api_key=settings.qdrant_api_key or None)
        return _client_instance

    # 2. Localhost server — probe with short timeout to see if Docker / daemon is running
    if url:
        try:
            probe_client = QdrantClient(url=url, api_key=settings.qdrant_api_key or None, timeout=2.0)
            probe_client.get_collections()
            _client_instance = probe_client
            return _client_instance
        except Exception:
            logger.info("Local Qdrant server unreachable at %s; using embedded storage at %s", url, settings.qdrant_path)

    # 3. Embedded on-disk Qdrant storage (runs directly inside process without Docker)
    settings.qdrant_path.mkdir(parents=True, exist_ok=True)
    _client_instance = QdrantClient(path=str(settings.qdrant_path))
    return _client_instance


def _embed(texts: list[str]) -> list[list[float]]:
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    result = genai.embed_content(
        model=settings.embedding_model,
        content=texts,
        task_type="retrieval_document",
    )
    return result["embedding"]


def ensure_collection(client: QdrantClient) -> None:
    """Idempotent collection creation with the right vector size."""
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
    """Deterministic UUID per (doc, text) so re-uploads don't duplicate points.
    Qdrant requires point IDs to be valid unsigned integers or UUID strings.
    """
    name = getattr(chunk, "document_name", None) or getattr(chunk, "video_name", "unknown")
    raw_key = f"{name}::{chunk.text[:200]}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_key))


def _payload(chunk: LayerAChunk) -> dict[str, Any]:
    """Build the exact payload shape that Layer A retrieval and downstream
    agents rely on to distinguish source types.
    """
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
    """Embed and upsert all chunks into the Layer A collection. Returns count."""
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
    """Retrieve only Layer A ground truth — the guardrail helper for agents."""
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