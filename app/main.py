"""VisualAI — Steps 1 & 2: Multimodal Ingestion + Student Knowledge Profiling."""

import os

from .core.config import settings

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.dashboard import router as dashboard_router
from .api.upload import router as upload_router
from .api.assessment import router as assessment_router
from .api.pipeline import router as pipeline_router
from .api.instructor import router as instructor_router
from .api.video import router as video_router
from .api.qa import router as qa_router

# ---------------------------------------------------------------------------
# Allowed origins — override via VISUALAI_CORS_ORIGINS env var (comma-sep)
# ---------------------------------------------------------------------------
_cors_origins_raw = os.getenv("VISUALAI_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app = FastAPI(
    title="VisualAI — Personalized Educational Assessment & Video Generation Platform",
    description=(
        "Upload study material → Extract knowledge → Generate quizzes → Track mastery → Remedial Video Lessons.\n\n"
        "**Step 1 — Ingestion:** Upload PDF, image, text, or video. "
        "System extracts content, builds knowledge graph, stores in vector DB.\n\n"
        "**Step 2 — Assessment:** Generate grounded quiz questions from uploaded material. "
        "Grade submissions, detect prerequisite gaps, track student mastery.\n\n"
        "**Step 3 — Video Engine:** Deterministic Manim animations + local TTS + Whisper alignment.\n\n"
        "**Step 4 — Grounded Q&A:** Multi-layer source and video timestamp-aware question answering."
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
app.include_router(instructor_router)
app.include_router(video_router)
app.include_router(qa_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "VisualAI",
        "version": "0.3.0",
        "steps": ["ingestion", "assessment", "video_engine", "instructor_analytics"],
    }


@app.get("/health/llm")
def health_llm() -> dict:
    from .core.llm import get_llm_provider
    provider = get_llm_provider()
    if hasattr(provider, "health_check"):
        return provider.health_check()
    return {
        "provider": getattr(settings, "llm_provider", "ollama"),
        "configured_model": getattr(settings, "ollama_model", "unknown"),
        "reachable": True,
        "latency_ms": 0,
    }


@app.get("/health/qdrant")
def health_qdrant() -> dict:
    from .db.vector_store import get_client
    try:
        client = get_client()
        collections = client.get_collections().collections
        return {
            "service": "Qdrant",
            "status": "connected",
            "collections": [c.name for c in collections],
        }
    except Exception as exc:
        return {
            "service": "Qdrant",
            "status": "unreachable",
            "error": str(exc),
        }


@app.get("/health/video")
def health_video() -> dict:
    import shutil
    manim_ok = False
    try:
        import manim
        manim_ok = True
    except Exception:
        pass
    ffmpeg_bin = shutil.which("ffmpeg")
    return {
        "service": "Step 3 Video Engine",
        "status": "ready" if (manim_ok or shutil.which("say")) else "degraded",
        "manim_available": manim_ok,
        "ffmpeg_available": bool(ffmpeg_bin),
        "tts_provider": getattr(settings, "tts_provider", "edge_tts"),
        "whisper_model": getattr(settings, "whisper_model", "base"),
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
    from .core.config import settings

    client = get_client()
    ensure_collection(client)

    info = client.get_collection(settings.collection_name)
    result = {
        "points_count": info.points_count,
        "vector_size": info.config.params.vectors.size if info.config.params.vectors else None,
        "status": info.status,
    }

    # Try an unfiltered search
    try:
        vector = _embed(["test query"])[0]
        hits = client.search(
            collection_name=settings.collection_name,
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


if __name__ == "__main__":
    from pathlib import Path
    import uvicorn

    root_dir = Path(__file__).resolve().parent.parent
    app_dir = root_dir / "app"
    venv_dir = root_dir / ".venv"
    storage_dir = root_dir / "storage"

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(app_dir)],
        reload_excludes=[str(venv_dir), str(storage_dir)],
    )