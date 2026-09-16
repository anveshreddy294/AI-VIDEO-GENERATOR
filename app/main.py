"""VisualAI — Step 1: Multimodal Ingestion & Verification (Layer A)."""

from fastapi import FastAPI

from .api.upload import router as upload_router

app = FastAPI(
    title="VisualAI",
    description=(
        "Step 1: Multimodal Ingestion & Verification — populate Layer A "
        "(authoritative source chunks) from student-uploaded study files."
    ),
    version="0.1.0",
)

app.include_router(upload_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "layer": "A", "service": "ingestion"}