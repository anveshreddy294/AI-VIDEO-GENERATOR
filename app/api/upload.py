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

import shutil
import traceback
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..core.config import settings
from ..services.chunker import create_rich_chunks
from ..services.dispatcher import UnsupportedFileType, dispatch
from ..services.registry import (
    register_source,
    save_content_units,
    save_knowledge_graph,
    update_source_status,
)
from ..services.structurer import process_structure_and_concepts
from ..services.validator import ValidationFailed, validate_ingestion_quality

router = APIRouter(prefix="/upload", tags=["Step 1 — Ingestion"])


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
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename or "unnamed"

    # Save to temp location for hash calculation and validation
    temp_name = f"{uuid4().hex}_{Path(filename).name}"
    temp_path = settings.upload_dir / temp_name
    with temp_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    source_record = None

    try:
        # Step 2 & 3: File Validation & Registration
        try:
            source_record, persistent_file = register_source(temp_path, filename)
        except ValueError as val_err:
            raise HTTPException(status_code=400, detail=str(val_err)) from val_err

        source_id = source_record.source_id
        asset_id = source_record.asset_id

        # Update status -> PROCESSING / EXTRACTING
        update_source_status(source_id, "PROCESSING")
        update_source_status(source_id, "EXTRACTING")

        # Step 4 & 5: Dispatcher & Modality Extraction -> ContentUnits
        try:
            extraction_result = dispatch(
                persistent_file, source_id=source_id, asset_id=asset_id
            )
            raw_units = extraction_result.units
        except UnsupportedFileType as exc:
            update_source_status(source_id, "FAILED", error_message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[upload] Extraction failed for {filename}: {tb}")
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
        enriched_units, knowledge_graph, blueprint = process_structure_and_concepts(raw_units)

        # Persist normalized ContentUnits and Knowledge Graph to registry storage
        save_content_units(source_id, enriched_units)
        save_knowledge_graph(source_id, knowledge_graph)

        # Step 9 & 10: Semantic Chunking & Provenance Mapping
        update_source_status(source_id, "INDEXING")
        rich_chunks = create_rich_chunks(enriched_units, knowledge_graph)
        blueprint.chunk_count = len(rich_chunks)

        # Step 15: Qdrant Payload Upsert
        synced_count = 0
        if rich_chunks:
            synced_count = upsert_safely(rich_chunks)

        # Step 17: Quality Validation Gateway
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

        return {
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

    except ValidationFailed as val_exc:
        if source_record:
            update_source_status(source_record.source_id, "FAILED", error_message=str(val_exc))
        raise HTTPException(status_code=422, detail=f"Validation failed: {val_exc}") from val_exc

    finally:
        temp_path.unlink(missing_ok=True)


def upsert_safely(chunks) -> int:
    try:
        from ..db.vector_store import upsert_chunks

        return upsert_chunks(chunks)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Layer A vector sync failed (Qdrant error): {exc}",
        ) from exc
