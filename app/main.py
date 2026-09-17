"""VisualAI — Steps 1 & 2: Multimodal Ingestion + Student Knowledge Profiling."""

from fastapi import FastAPI

from .api.dashboard import router as dashboard_router
from .api.upload import router as upload_router
from .api.assessment import router as assessment_router

app = FastAPI(
    title="VisualAI — Student Knowledge Platform",
    description=(
        "Upload study material → Extract knowledge → Generate quizzes → Track mastery.\n\n"
        "**Step 1 — Ingestion:** Upload PDF, image, text, or video. "
        "System extracts content, builds knowledge graph, stores in vector DB.\n\n"
        "**Step 2 — Assessment:** Generate grounded quiz questions from uploaded material. "
        "Grade submissions, detect prerequisite gaps, track student mastery."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(dashboard_router)
app.include_router(upload_router)
app.include_router(assessment_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "VisualAI", "version": "0.2.0", "steps": ["ingestion", "assessment"]}


@app.get("/sources")
def get_sources():
    """List all registered sources with readiness and concept counts."""
    from .services.registry import _load_sources_index, load_knowledge_graph

    index = _load_sources_index()
    results = []
    for sid, rec in index.items():
        kg = load_knowledge_graph(sid)
        results.append({
            "source_id": sid,
            "filename": rec.get("filename", "unknown"),
            "status": rec.get("status", "UNKNOWN"),
            "modality": rec.get("source_type"),
            "concepts_count": len(kg.concepts) if kg and kg.concepts else 0,
            "created_at": rec.get("created_at"),
        })
    results.sort(key=lambda x: (x["status"] == "READY", x.get("created_at") or ""), reverse=True)
    return {"sources": results}


@app.get("/debug/qdrant")
def debug_qdrant():
    """Diagnostic endpoint to check Qdrant collection state."""
    from .db.vector_store import get_client, ensure_collection, _embed
    from qdrant_client.http import models as qmodels

    client = get_client()
    ensure_collection(client)

    info = client.get_collection("visualai_layer_a")
    result = {
        "points_count": info.points_count,
        "vector_size": info.config.params.vectors.size if info.config.params.vectors else None,
        "status": info.status,
    }

    # Try an unfiltered search
    try:
        vector = _embed(["test query"])[0]
        hits = client.search(
            collection_name="visualai_layer_a",
            query_vector=vector,
            limit=3,
        )
        result["unfiltered_hits"] = len(hits)
        result["sample_payloads"] = []
        for h in hits:
            p = h.payload
            result["sample_payloads"].append({
                "source_id": p.get("source_id", "MISSING"),
                "chunk_id": p.get("chunk_id", "MISSING"),
                "layer": p.get("layer", "MISSING"),
                "text_preview": p.get("text", "")[:80],
            })
    except Exception as exc:
        result["search_error"] = str(exc)

    return result