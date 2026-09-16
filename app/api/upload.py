"""POST /upload — the Reception Point of VisualAI.

Validates the extension, saves the file temporarily, dispatches it through the
extraction engine, structures the topic blueprint, and syncs Layer A chunks
into the vector DB. One request completes the whole ingestion pipeline.
"""

import shutil
import traceback
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..core.config import settings
from ..services.chunker import chunk_authoritative_text, chunk_video_text
from ..services.dispatcher import UnsupportedFileType, dispatch
from ..services.structurer import structure_topic

router = APIRouter(prefix="/upload", tags=["ingestion"])


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    """Accept a study file; return the TopicBlueprint + ingest stats."""
    filename = file.filename or "unnamed"
    if not settings.is_allowed(filename):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Extension not allowed: '{Path(filename).suffix}'. "
                f"Allowed: {sorted(settings.allowed_extensions)}"
            ),
        )

    # 1. Save temporarily to the local working directory.
    temp_name = f"{uuid4().hex}_{Path(filename).stem}{Path(filename).suffix}"
    temp_path = settings.upload_dir / temp_name
    with temp_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        # 2. Extraction engine: text + vision descriptions -> Authoritative Source.
        try:
            result = dispatch(temp_path)
        except UnsupportedFileType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[upload] Extraction failed for {filename}: {tb}")
            raise HTTPException(
                status_code=500,
                detail=f"Extraction failed for '{filename}': {exc}",
            ) from exc

        authoritative_text = result.text
        if not authoritative_text.strip():
            raise HTTPException(
                status_code=422,
                detail=f"No extractable content found in '{filename}'. The file may be empty or corrupted.",
            )

        # Persist the raw source for audit/debugging.
        (settings.processed_dir / f"{temp_name}.source.txt").write_text(
            authoritative_text, encoding="utf-8"
        )

        # 3. Knowledge structuring -> TopicBlueprint.
        try:
            blueprint = structure_topic(authoritative_text)
        except Exception as exc:
            print(f"[upload] Structuring failed for {filename}: {exc}")
            # Don't kill the upload — return the raw extraction without a blueprint.
            blueprint = None

        # 4. Layer A RAG sync — document chunks are tagged by page,
        #    video chunks by their clock window.
        synced = 0
        try:
            if result.kind == "video":
                chunks = chunk_video_text(authoritative_text, video_name=filename)
            else:
                chunks = chunk_authoritative_text(authoritative_text, document_name=filename)
            synced = upsert_safely(chunks)
        except Exception as exc:
            print(f"[upload] RAG sync failed for {filename}: {exc}")

        response = {
            "status": "ingested",
            "media_type": result.kind,
            "document_name": filename,
            "layer_a": {
                "chunks_synced": synced,
                "collection": settings.collection_name,
            },
            "source_chars": len(authoritative_text),
        }
        if blueprint:
            response["topic"] = blueprint.model_dump()

        return response
    finally:
        temp_path.unlink(missing_ok=True)  # temp file is always cleaned up


def upsert_safely(chunks) -> int:
    """Wrap the vector upsert so a DB outage surfaces as a clear 503, and
    import it lazily so starting the server doesn't require Qdrant to be up."""
    try:
        from ..db.vector_store import upsert_chunks

        return upsert_chunks(chunks)
    except Exception as exc:  # ConnectionRefusedError, API errors, etc.
        raise HTTPException(
            status_code=503,
            detail=f"Layer A sync failed (is Qdrant running?): {exc}",
        ) from exc
