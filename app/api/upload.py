"""POST /upload — Reception Point & Full Step 1 Ingestion Pipeline.

Executes the complete Step 1 sequence:
1. User Input & Temporary Save
2. File Validation & Persistent Source Registration (source_id, asset_id, upload_id, hash, version)
3. Modality Dispatching -> ContentUnit Normalization
4. Structure Detection, Concept Extraction & Knowledge Graph Generation
5. Concept-Aware Semantic Chunking with Full Provenance Mapping
6. Rich Qdrant Payload Upsert
7. Quality Validation Gateway Check
8. Topic Blueprint derivation & Status READY transition.
"""

import logging
import asyncio
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..core.config import settings
from ..services.chunker import create_rich_chunks
from ..services.dispatcher import UnsupportedFileType, dispatch
from ..services.registry import (
    register_source,
    save_content_units,
    save_rich_chunks,
    save_knowledge_graph,
    update_source_status,
)
from ..services.structurer import process_structure_and_concepts
from ..services.validator import ValidationFailed, validate_ingestion_quality

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Step 1 — Ingestion"])

# SEC-006: Configurable maximum upload size (default: 200 MB)
_MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200")) * 1024 * 1024

# SEC-007: Extension → allowed MIME types mapping for basic content validation
_MIME_ALLOWLIST: dict[str, set[str]] = {
    "pdf":  {"application/pdf"},
    "txt":  {"text/plain", "application/octet-stream"},
    "png":  {"image/png"},
    "jpg":  {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "mp4":  {"video/mp4", "application/octet-stream"},
    "mov":  {"video/quicktime", "video/mp4", "application/octet-stream"},
    "mkv":  {"video/x-matroska", "application/octet-stream"},
}


def _validate_mime(filename: str, content_type: str | None) -> None:
    """SEC-007: Verify the Content-Type header matches the declared extension.

    Protects against trivial extension spoofing (e.g. a .php renamed to .pdf).
    We perform a best-effort check — browser Content-Type can be unreliable,
    so we only reject when there is a clear, unambiguous mismatch.
    """
    if not content_type:
        return  # Cannot validate without Content-Type; proceed with extension check only
    ext = Path(filename).suffix.lstrip(".").lower()
    allowed_mimes = _MIME_ALLOWLIST.get(ext)
    if allowed_mimes is None:
        return  # Extension not in map — already blocked by is_allowed check
    ct_base = content_type.split(";")[0].strip().lower()
    # Allow generic octet-stream from any uploader
    if ct_base == "application/octet-stream":
        return
    if ct_base not in allowed_mimes:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Content-Type '{ct_base}' does not match expected MIME types for .{ext} files. "
                "Please upload a genuine file."
            ),
        )


@router.post(
    "",
    summary="Upload study material → Get knowledge blueprint",
    description=(
        "Upload a PDF, image, text file, or lecture video (MP4/MOV/MKV). "
        "The system extracts content, builds a knowledge graph with concepts and prerequisites, "
        "stores everything in the vector database, and returns a structured JSON blueprint. "
        "Use the returned `source_id` to generate quizzes in Step 2."
    ),
)
async def upload_file(
    file: UploadFile = File(...),
    auto_start_assessment: bool = False,
    student_id: str = "student_default",
    max_questions: int = 5,
):
    filename = file.filename or "unnamed"

    # SEC-007: Validate Content-Type vs extension before reading the file
    _validate_mime(filename, file.content_type)

    # Save to temp location for hash calculation and validation
    temp_name = f"{uuid4().hex}_{Path(filename).name}"
    temp_path = settings.upload_dir / temp_name

    # SEC-006: Stream file to disk, tracking size to enforce upload limit
    bytes_written = 0
    try:
        with temp_path.open("wb") as out:
            chunk_size = 1024 * 1024  # 1 MB chunks
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum upload size is {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )
                out.write(chunk)
    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        logger.exception("Failed to write uploaded file to temp storage")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")

    source_record = None

    try:
        # Step 2 & 3: File Validation & Registration
        try:
            source_record, persistent_file = register_source(temp_path, filename, uploaded_by=student_id)
        except ValueError as val_err:
            raise HTTPException(status_code=400, detail=str(val_err)) from val_err

        source_id = source_record.source_id
        asset_id = source_record.asset_id

        # Update status -> PROCESSING / EXTRACTING
        update_source_status(source_id, "PROCESSING")
        update_source_status(source_id, "EXTRACTING")

        # Step 4 & 5: Dispatcher & Modality Extraction -> ContentUnits
        try:
            extraction_result = await asyncio.to_thread(dispatch,
                persistent_file, source_id=source_id, asset_id=asset_id
            )
            raw_units = extraction_result.units
        except UnsupportedFileType as exc:
            update_source_status(source_id, "FAILED", error_message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("[upload] Extraction failed for %s", filename)
            update_source_status(source_id, "FAILED", error_message=str(exc))
            raise HTTPException(
                status_code=500, detail=f"Extraction failed for '{filename}': {exc}"
            ) from exc

        if not raw_units:
            update_source_status(source_id, "FAILED", error_message="No content extracted")
            raise HTTPException(
                status_code=422,
                detail=f"No extractable content found in '{filename}'.",
            )

        # Step 6, 7 & 8: Structure Detection, Concept Extraction & Knowledge Graph
        update_source_status(source_id, "NORMALIZING")
        enriched_units, knowledge_graph, blueprint = await asyncio.to_thread(process_structure_and_concepts, raw_units)

        # Persist normalized ContentUnits and Knowledge Graph to registry storage
        save_content_units(source_id, enriched_units)
        save_knowledge_graph(source_id, knowledge_graph)

        # Step 9 & 10: Semantic Chunking & Provenance Mapping
        update_source_status(source_id, "INDEXING")
        rich_chunks = create_rich_chunks(enriched_units, knowledge_graph)
        save_rich_chunks(source_id, rich_chunks)

        # Step 11: Rich Qdrant Payload Upsert (Layer A)
        synced_count = await asyncio.to_thread(upsert_safely, rich_chunks)

        # Update blueprint chunk_count with real count
        blueprint.chunk_count = len(rich_chunks)

        # Quality Validation Gateway Check
        val_report = validate_ingestion_quality(
            record=source_record,
            file_path=persistent_file,
            units=enriched_units,
            kg=knowledge_graph,
            chunks=rich_chunks,
            upserted_count=synced_count,
        )

        # Step 12 & 18: Update status -> READY and prepare final response
        update_source_status(source_id, "READY")

        # Automated Step 1 -> Step 2 handoff if requested
        assessment_resp = None
        if auto_start_assessment:
            try:
                from .assessment import start_assessment
                from ..services.assessment.schemas import AssessmentStartRequest

                assessment_session = await asyncio.to_thread(start_assessment,
                    student_id=student_id,
                    source_id=source_id,
                    payload=AssessmentStartRequest(
                        student_id=student_id,
                        source_id=source_id,
                        max_questions=max_questions,
                    ),
                )
                assessment_resp = assessment_session if isinstance(assessment_session, dict) else assessment_session.model_dump()
            except Exception as exc:
                logger.warning("[upload] auto_start_assessment failed: %s", exc)
                assessment_resp = {"error": f"Assessment could not be auto-started: {exc}"}

        resp = {
            "status": "READY",
            "source_id": source_id,
            "asset_id": asset_id,
            "upload_id": source_record.upload_id,
            "filename": filename,
            "modality": extraction_result.modality,
            "file_hash": source_record.file_hash,
            "version": source_record.version,
            "content_units": len(enriched_units),
            "chunks_synced": synced_count,
            "concepts_extracted": len(knowledge_graph.concepts),
            "validation": val_report,
            "topic_blueprint": blueprint.model_dump(),
        }
        if assessment_resp is not None:
            resp["assessment"] = assessment_resp

        return resp

    except ValidationFailed as val_exc:
        if source_record:
            update_source_status(source_record.source_id, "FAILED", error_message=str(val_exc))
        raise HTTPException(status_code=422, detail=f"Validation failed: {val_exc}") from val_exc

    except Exception as exc:
        if source_record:
            update_source_status(source_record.source_id, "FAILED", error_message=type(exc).__name__)
        if isinstance(exc, HTTPException):
            raise
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=503, detail="Ingestion failed; verify model and storage services and retry") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def upsert_safely(chunks) -> int:
    try:
        from ..db.vector_store import upsert_chunks

        return upsert_chunks(chunks)
    except Exception:
        # SEC-010: Do not expose internal Qdrant errors to clients
        logger.exception("Qdrant upsert failure")
        raise HTTPException(
            status_code=503,
            detail="Vector database sync failed. Please try again or contact support.",
        )
