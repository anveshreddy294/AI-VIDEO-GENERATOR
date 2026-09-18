"""VisualAI — Steps 1 & 2: Multimodal Ingestion + Student Knowledge Profiling."""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.dashboard import router as dashboard_router
from .api.upload import router as upload_router
from .api.assessment import router as assessment_router
from .api.pipeline import router as pipeline_router
from .api.video import router as video_router
from .api.remediation import router as remediation_router
from .api.video_rag import router as video_rag_router
from .api.instructor import router as instructor_router

# ---------------------------------------------------------------------------
# Allowed origins — override via VISUALAI_CORS_ORIGINS env var (comma-sep)
# ---------------------------------------------------------------------------
_cors_origins_raw = os.getenv("VISUALAI_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app = FastAPI(
    title="VisualAI — Personalized Educational Video Platform",
    description=(
        "Upload study material → Extract knowledge → Generate quizzes → Track mastery → Generate targeted videos → Verify mastery → Interactive Video RAG → Instructor Analytics.\n\n"
        "**Step 1 — Ingestion:** Upload PDF, image, text, or video. "
        "System extracts content, builds knowledge graph, stores in vector DB.\n\n"
        "**Step 2 — Assessment:** Generate grounded quiz questions from uploaded material. "
        "Grade submissions, detect prerequisite gaps, track student mastery.\n\n"
        "**Step 3 — Video Generation:** Synthesize timed multi-scene remedial video lessons with voiceover and diagrams.\n\n"
        "**Step 4 — Remediation Verification:** Grounded 1-2 question re-testing loop to verify comprehension and close knowledge gaps.\n\n"
        "**Interactive Video RAG:** In-player timestamp-synchronized conversational Q&A agent.\n\n"
        "**Instructor Analytics:** Human intervention management for kill-switch alerts and cohort gap heatmaps."
    ),
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# SEC-011: Explicit CORS policy — prevent unintended cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(dashboard_router)
app.include_router(upload_router)
app.include_router(assessment_router)
app.include_router(pipeline_router)
app.include_router(video_router)
app.include_router(remediation_router)
app.include_router(video_rag_router)
app.include_router(instructor_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "VisualAI",
        "version": "0.4.0",
        "steps": ["ingestion", "assessment", "video_generation", "remediation", "video_rag", "instructor_analytics"],
    }


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
def debug_qdrant(request: Request):
    """Diagnostic endpoint to check Qdrant collection state.

    SEC-002: Only available when VISUALAI_DEBUG=true is set in environment.
    Must never be enabled in production deployments.
    """
    if os.getenv("VISUALAI_DEBUG", "").lower() not in ("1", "true", "yes"):
        return JSONResponse(
            status_code=403,
            content={"detail": "Debug endpoint disabled. Set VISUALAI_DEBUG=true to enable (development only)."},
        )
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