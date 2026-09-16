"""Layer A RAG sync — embed tagged chunks and upsert them into Qdrant.

Every chunk carries the `layer: "A"` security tag. Payload shape differs by type:

    Document chunk:  { layer, type=authoritative_source, document_name, text, page }
    Video chunk:     { layer, type=authoritative_video, video_name,
                       start_timestamp, end_timestamp, text }

Embeddings come from Gemini's embedding model. The collection is created
once with cosine similarity; subsequent upserts are idempotent by point id.
"""

import hashlib
from typing import Any

import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ..core.config import settings
from ..services.schemas import AuthoritativeSourceChunk, AuthoritativeVideoChunk, LayerAChunk


def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


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
    """Deterministic id per (doc, text) so re-uploads don't duplicate points."""
    name = getattr(chunk, "document_name", None) or getattr(chunk, "video_name", "unknown")
    return hashlib.sha256(f"{name}::{chunk.text[:200]}".encode()).hexdigest()


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