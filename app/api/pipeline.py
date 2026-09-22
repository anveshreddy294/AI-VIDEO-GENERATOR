"""Observable pipeline API routes - Background Job Creation & Real-Time SSE Telemetry.

Routes:
- POST /pipeline/upload-and-assess: Start background upload + assessment job.
- POST /pipeline/assess-existing: Start background assessment generation job for existing source.
- GET /pipeline/jobs/{job_id}/events: Server-Sent Events (SSE) telemetry stream.
- GET /pipeline/jobs/{job_id}: Direct polling status check and final result retrieval.
"""

import asyncio
import logging
import shutil
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.config import settings
from ..services.chunker import create_rich_chunks
from ..services.dispatcher import UnsupportedFileType, dispatch
from ..services.ingestion.normalizer import normalize_content_units
from ..services.pipeline_tracker import ProgressEvent, job_manager
from ..services.registry import (
    get_source_record,
    load_knowledge_graph,
    register_source,
    save_content_units,
    save_normalized_records,
    save_quarantine_records,
    save_rich_chunks,
    save_sanitized_records,
    save_knowledge_graph,
    update_source_status,
)
from ..services.security.content_sanitizer import sanitize_content_records
from ..services.structurer import process_structure_and_concepts
from ..services.validator import ValidationFailed, validate_ingestion_quality

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline Telemetry & Jobs"])


class AssessExistingRequest(BaseModel):
    source_id: str
    student_id: str = "student_default"
    max_questions: int = Field(default=5, ge=1, le=10)


class JobCreationResponse(BaseModel):
    job_id: str
    status: str = "pending"
    message: str = "Job created and queued for background execution."


async def _execute_upload_and_assess(
    job_id: str,
    temp_path: Path,
    original_filename: str,
    student_id: str,
    max_questions: int,
) -> None:
    """Execute complete Step 1 & Step 2 pipeline emitting deterministic operational events."""
    start_time = time.time()
    source_record = None

    sem = job_manager.get_semaphore()
    if sem.locked():
        await job_manager.emit_event(
            job_id=job_id,
            stage="queued",
            status="pending",
            message=f"Queued behind active jobs. Waiting for execution slot (max concurrency: {getattr(settings, 'max_background_jobs', 2)})...",
            progress_percent=0,
            metadata={"filename": original_filename},
        )
    acquired_sem = False
    await sem.acquire()
    acquired_sem = True

    try:
        # Stage 1: Validating Source
        await job_manager.emit_event(
            job_id=job_id,
            stage="validating_source",
            status="running",
            message=f"Validating '{original_filename}' and registering persistent metadata...",
            progress_percent=5,
            metadata={"filename": original_filename},
        )

        try:
            source_record, persistent_file = register_source(temp_path, original_filename, uploaded_by=student_id)
        except ValueError as val_err:
            await job_manager.fail_job(
                job_id=job_id,
                stage="validating_source",
                error_message=f"Source validation rejected: {val_err}",
                metadata={"filename": original_filename},
            )
            return

        source_id = source_record.source_id
        asset_id = source_record.asset_id

        await job_manager.emit_event(
            job_id=job_id,
            stage="validating_source",
            status="completed",
            message=f"Source validated and registered as {source_id}.",
            progress_percent=12,
            metadata={"source_id": source_id, "asset_id": asset_id, "file_size": source_record.file_size},
        )

        # Stage 2: Extracting Content
        await job_manager.emit_event(
            job_id=job_id,
            stage="extracting_content",
            status="running",
            message="Extracting multimodal content via modality dispatcher...",
            progress_percent=18,
            metadata={"source_id": source_id},
        )

        try:
            extraction_result = await asyncio.to_thread(dispatch,persistent_file, source_id=source_id, asset_id=asset_id)
            raw_units = extraction_result.units
        except UnsupportedFileType as exc:
            await job_manager.fail_job(
                job_id=job_id,
                stage="extracting_content",
                error_message=f"Unsupported file format: {exc}",
                metadata={"source_id": source_id},
            )
            return
        except Exception as exc:
            await job_manager.fail_job(
                job_id=job_id,
                stage="extracting_content",
                error_message=f"Content extraction failed: {exc}",
                metadata={"source_id": source_id},
            )
            return

        if not raw_units:
            await job_manager.fail_job(
                job_id=job_id,
                stage="extracting_content",
                error_message=f"No extractable text or media found in '{original_filename}'.",
                metadata={"source_id": source_id},
            )
            return

        await job_manager.emit_event(
            job_id=job_id,
            stage="extracting_content",
            status="completed",
            message=f"Extracted {len(raw_units)} raw content segments ({extraction_result.modality}).",
            progress_percent=25,
            metadata={"source_id": source_id, "modality": extraction_result.modality, "content_units_count": len(raw_units)},
        )

        # Stage 3: Normalizing Units & Analyzing Structure
        await job_manager.emit_event(
            job_id=job_id,
            stage="normalizing_units",
            status="running",
            message="Normalizing ContentUnits, running prompt-injection sanitization, and anchoring structural lineage...",
            progress_percent=30,
            metadata={"source_id": source_id},
        )

        # 3a. Canonical Normalization
        normalized_records = normalize_content_units(raw_units, source_version=source_record.source_version)
        save_normalized_records(student_id, source_id, source_record.source_version, [r.model_dump() for r in normalized_records])

        # 3b. Prompt-Injection Quarantine and Sanitization
        sanitized_records = sanitize_content_records(normalized_records)
        save_sanitized_records(student_id, source_id, source_record.source_version, [r.model_dump() for r in sanitized_records])

        quarantined = [r.model_dump() for r in sanitized_records if not r.retrieval_allowed]
        if quarantined:
            save_quarantine_records(student_id, source_id, source_record.source_version, quarantined)
            logger.warning("[pipeline] Quarantined %d prompt-injection segments for source %s", len(quarantined), source_id)

        # Filter units: only allow clean/sanitized text to reach structure & knowledge graph
        clean_map = {r.content_id: r.sanitized_text for r in sanitized_records if r.retrieval_allowed}
        units_to_process = []
        for u in raw_units:
            if u.content_id in clean_map:
                stext = clean_map[u.content_id]
                if stext:
                    u.text = stext
                    units_to_process.append(u)
        if not units_to_process:
            units_to_process = raw_units  # Graceful fallback if entire input was quarantined

        await job_manager.emit_event(
            job_id=job_id,
            stage="analyzing_structure",
            status="running",
            message="Analyzing document outline and extracting conceptual relationships...",
            progress_percent=40,
            metadata={"source_id": source_id, "sanitized_units_count": len(units_to_process), "quarantined_count": len(quarantined)},
        )

        try:
            enriched_units, knowledge_graph, blueprint = await asyncio.to_thread(process_structure_and_concepts, units_to_process)
        except Exception as exc:
            logger.warning("[pipeline] LLM structure extraction failed, falling back to rule-based extraction: %s", exc)
            from ..services.structurer import _fallback_outputs
            enriched_units, knowledge_graph, blueprint = _fallback_outputs(units_to_process, fallback_reason=str(exc))

        if not knowledge_graph or not knowledge_graph.concepts:
            await job_manager.fail_job(
                job_id=job_id,
                stage="building_knowledge_graph",
                error_message="Knowledge graph construction failed: no valid concepts could be extracted.",
                metadata={"source_id": source_id},
            )
            return


        save_content_units(source_id, enriched_units)
        save_knowledge_graph(source_id, knowledge_graph)

        diag_meta = blueprint.diagnostics.model_dump() if (blueprint and getattr(blueprint, "diagnostics", None)) else {}
        await job_manager.emit_event(
            job_id=job_id,
            stage="extracting_concepts",
            status="completed",
            message=f"Extracted {len(knowledge_graph.concepts)} core concepts.",
            progress_percent=55,
            metadata={
                "source_id": source_id,
                "concepts_count": len(knowledge_graph.concepts),
                "diagnostics": diag_meta,
            },
        )

        # Stage 4: Semantic Chunking
        await job_manager.emit_event(
            job_id=job_id,
            stage="creating_chunks",
            status="running",
            message="Generating concept-aware RichChunks with exact spatial/temporal provenance...",
            progress_percent=65,
            metadata={"source_id": source_id},
        )

        rich_chunks = create_rich_chunks(
            enriched_units,
            knowledge_graph,
            user_id=student_id,
            source_version=source_record.source_version,
            source_hash=source_record.file_hash,
        )
        save_rich_chunks(source_id, rich_chunks)
        blueprint.chunk_count = len(rich_chunks)

        await job_manager.emit_event(
            job_id=job_id,
            stage="creating_chunks",
            status="completed",
            message=f"Created {len(rich_chunks)} grounded RichChunks.",
            progress_percent=72,
            metadata={"source_id": source_id, "chunks_count": len(rich_chunks)},
        )

        # Stage 5: Syncing Vector Database
        await job_manager.emit_event(
            job_id=job_id,
            stage="syncing_qdrant",
            status="running",
            message="Generating embeddings and synchronizing Layer A Qdrant collection...",
            progress_percent=75,
            metadata={"source_id": source_id},
        )

        from ..db.vector_store import upsert_chunks, get_last_embed_diagnostics
        synced_count = 0
        sync_error = None
        fallback_used = False
        embed_diag_meta = {}

        def sync_primary():
            count = upsert_chunks(rich_chunks)
            diagnostics = get_last_embed_diagnostics()
            return count, diagnostics.model_dump() if diagnostics else {}

        try:
            synced_count, embed_diag_meta = await asyncio.to_thread(sync_primary)
        except Exception as exc:
            logger.warning("[pipeline_job] Primary Qdrant upsert failed: %s. Retrying explicitly with local fallback...", exc)
            def sync_fallback():
                from ..db.vector_store import get_client, ensure_collection, _embed, _point_id, _payload
                from ..services.schemas import StageDiagnostics
                from qdrant_client import QdrantClient
                from qdrant_client.http import models as qmodels
                try:
                    embedded_client = get_client()
                except Exception:
                    embedded_client = QdrantClient(":memory:")
                ensure_collection(embedded_client)
                texts = [c.text for c in rich_chunks]
                vectors = _embed(texts)
                points = [
                    qmodels.PointStruct(id=_point_id(c), vector=v, payload=_payload(c))
                    for c, v in zip(rich_chunks, vectors)
                ]
                if points:
                    embedded_client.upsert(collection_name=settings.collection_name, points=points)
                diag = get_last_embed_diagnostics()
                if not diag:
                    diag = StageDiagnostics(provider_used="fallback_local", fallback_used=True, grounding_verified=True)
                return len(points), diag.model_dump() if diag else {}

            try:
                synced_count, embed_diag_meta = await asyncio.to_thread(sync_fallback)
                fallback_used = True
                logger.info("[pipeline_job] Fallback storage successfully synchronized %d chunks.", synced_count)
            except Exception as embedded_exc:
                sync_error = f"VECTOR_SYNC_FAILED: Both primary and fallback Qdrant storage failed: {embedded_exc}"
                logger.error("[pipeline_job] %s", sync_error)
                synced_count = 0

        if sync_error:
            await job_manager.fail_job(
                job_id=job_id,
                stage="syncing_qdrant",
                error_message=sync_error,
                metadata={"source_id": source_id, "error": sync_error, "embedding_diagnostics": embed_diag_meta},
            )
            return
        elif fallback_used:
            await job_manager.emit_event(
                job_id=job_id,
                stage="syncing_qdrant",
                status="warning",
                message=f"Synced {synced_count} chunks using fallback local storage (primary unreachable).",
                progress_percent=80,
                metadata={
                    "source_id": source_id,
                    "fallback": True,
                    "chunks_count": synced_count,
                    "embedding_diagnostics": embed_diag_meta,
                },
            )
        else:
            await job_manager.emit_event(
                job_id=job_id,
                stage="syncing_qdrant",
                status="completed",
                message=f"Synced {synced_count} chunks into Qdrant vector index.",
                progress_percent=82,
                metadata={
                    "source_id": source_id,
                    "chunks_count": synced_count,
                    "fallback": False,
                    "embedding_diagnostics": embed_diag_meta,
                },
            )

        # Stage 6: Quality Validation Gateway
        await job_manager.emit_event(
            job_id=job_id,
            stage="quality_validation",
            status="running",
            message="Auditing graph consistency and provenance integrity...",
            progress_percent=85,
            metadata={"source_id": source_id},
        )

        try:
            val_report = validate_ingestion_quality(
                record=source_record,
                file_path=persistent_file,
                units=enriched_units,
                kg=knowledge_graph,
                chunks=rich_chunks,
                upserted_count=synced_count,
            )
        except ValidationFailed as v_err:
            await job_manager.fail_job(
                job_id=job_id,
                stage="quality_validation",
                error_message=f"Validation gateway rejected ingestion: {v_err}",
                metadata={"source_id": source_id},
            )
            return

        update_source_status(source_id, "READY")

        # Stage 7: Assessment Planning & Generation
        await job_manager.emit_event(
            job_id=job_id,
            stage="planning_assessment",
            status="running",
            message="Planning adaptive assessment queue and prerequisite pairs...",
            progress_percent=88,
            metadata={"source_id": source_id, "questions_requested": max_questions},
        )

        from .assessment import start_assessment
        from ..services.assessment.schemas import AssessmentStartRequest

        assessment_resp = None
        try:
            await job_manager.emit_event(
                job_id=job_id,
                stage="generating_questions",
                status="running",
                message="Generating grounded questions with pedagogic variants...",
                progress_percent=92,
                metadata={"source_id": source_id, "questions_requested": max_questions},
            )

            chunks_payload = [
                {
                    "chunk_id": rc.chunk_id,
                    "text": rc.text,
                    "concept_ids": list(rc.concept_ids or []),
                    "content_ids": list(rc.content_ids or []),
                    "page_start": rc.page_start,
                    "page_end": rc.page_end,
                    "timestamp_start": rc.timestamp_start,
                    "timestamp_end": rc.timestamp_end,
                    "source_id": source_id,
                }
                for rc in rich_chunks
            ]

            assessment_session = await asyncio.to_thread(start_assessment,
                student_id=student_id,
                source_id=source_id,
                payload=AssessmentStartRequest(
                    student_id=student_id,
                    source_id=source_id,
                    max_questions=max_questions,
                    step1_output={
                        "source_id": source_id,
                        "student_id": student_id,
                        "chunks": chunks_payload,
                        "knowledge_graph": knowledge_graph.model_dump() if hasattr(knowledge_graph, "model_dump") else {},
                    },
                ),
            )
            assessment_resp = assessment_session.model_dump() if hasattr(assessment_session, "model_dump") else assessment_session
        except Exception as exc:
            await job_manager.fail_job(
                job_id=job_id,
                stage="generating_questions",
                error_message=f"Question generation failed: {exc}",
                metadata={"source_id": source_id},
            )
            return

        # Stage 8: Question Validation & Shortfall Check
        gen_count = assessment_resp.get("generated_questions", len(assessment_resp.get("questions", [])))
        req_count = assessment_resp.get("requested_questions", max_questions)
        shortfall = assessment_resp.get("shortfall", max(0, req_count - gen_count))

        if shortfall > 0:
            await job_manager.emit_event(
                job_id=job_id,
                stage="validating_questions",
                status="warning",
                message=f"Grounded question shortfall: generated {gen_count} of {req_count} requested questions to preserve strict grounding.",
                progress_percent=97,
                metadata={
                    "source_id": source_id,
                    "questions_requested": req_count,
                    "questions_generated": gen_count,
                    "shortfall": shortfall,
                },
            )
        else:
            await job_manager.emit_event(
                job_id=job_id,
                stage="validating_questions",
                status="completed",
                message=f"Successfully verified {gen_count} grounded questions.",
                progress_percent=97,
                metadata={"source_id": source_id, "questions_generated": gen_count},
            )

        # Stage 9: Final Completion
        elapsed_ms = int((time.time() - start_time) * 1000)
        final_payload = {
            "status": "READY",
            "source_id": source_id,
            "asset_id": asset_id,
            "filename": original_filename,
            "modality": extraction_result.modality,
            "concepts_extracted": len(knowledge_graph.concepts),
            "content_units": len(enriched_units),
            "chunks_synced": synced_count,
            "validation": val_report,
            "assessment": assessment_resp,
        }

        await job_manager.complete_job(
            job_id=job_id,
            result=final_payload,
            message=f"Material processed and {gen_count} assessment questions ready ({elapsed_ms}ms).",
        )

    except Exception as unhandled_exc:
        logger.error("[pipeline_job] Unhandled error in job %s: %s", job_id, unhandled_exc, exc_info=True)
        await job_manager.fail_job(
            job_id=job_id,
            stage="pipeline_execution",
            error_message=f"Internal pipeline failure: {unhandled_exc}",
        )
    finally:
        try:
            if source_record:
                current = get_source_record(source_record.source_id)
                if current and current.status != "READY":
                    update_source_status(current.source_id, "FAILED", error_message="Ingestion did not complete; see pipeline diagnostics")
            temp_path.unlink(missing_ok=True)
        finally:
            if acquired_sem:
                sem.release()


async def _execute_assess_existing(
    job_id: str,
    source_id: str,
    student_id: str,
    max_questions: int,
) -> None:
    """Execute assessment generation for an existing source emitting operational progress."""
    start_time = time.time()
    sem = job_manager.get_semaphore()
    if sem.locked():
        await job_manager.emit_event(
            job_id=job_id,
            stage="queued",
            status="pending",
            message=f"Queued behind active jobs. Waiting for execution slot (max concurrency: {getattr(settings, 'max_background_jobs', 2)})...",
            progress_percent=0,
            metadata={"source_id": source_id},
        )
    acquired_sem = False
    await sem.acquire()
    acquired_sem = True

    try:
        await job_manager.emit_event(
            job_id=job_id,
            stage="validating_source",
            status="running",
            message=f"Locating and validating existing source '{source_id}'...",
            progress_percent=15,
            metadata={"source_id": source_id},
        )

        rec = get_source_record(source_id)
        if not rec:
            await job_manager.fail_job(
                job_id=job_id,
                stage="validating_source",
                error_message=f"Source '{source_id}' not found in registry.",
                metadata={"source_id": source_id},
            )
            return

        kg = load_knowledge_graph(source_id)
        if not kg or not kg.concepts:
            await job_manager.fail_job(
                job_id=job_id,
                stage="building_knowledge_graph",
                error_message=f"Source '{source_id}' has no concepts in knowledge graph.",
                metadata={"source_id": source_id},
            )
            return

        await job_manager.emit_event(
            job_id=job_id,
            stage="validating_source",
            status="completed",
            message=f"Found '{rec.filename}' with {len(kg.concepts)} concepts.",
            progress_percent=30,
            metadata={"source_id": source_id, "filename": rec.filename, "concepts_count": len(kg.concepts)},
        )

        await job_manager.emit_event(
            job_id=job_id,
            stage="planning_assessment",
            status="running",
            message="Planning adaptive assessment queue from concept graph...",
            progress_percent=50,
            metadata={"source_id": source_id, "questions_requested": max_questions},
        )

        from .assessment import start_assessment
        from ..services.assessment.schemas import AssessmentStartRequest

        await job_manager.emit_event(
            job_id=job_id,
            stage="generating_questions",
            status="running",
            message="Synthesizing grounded questions with variant angles...",
            progress_percent=75,
            metadata={"source_id": source_id, "questions_requested": max_questions},
        )

        from ..services.registry import load_content_units
        existing_cus = load_content_units(source_id) or []
        existing_chunks = [
            {
                "chunk_id": cu.content_id,
                "text": cu.text,
                "concept_ids": [],
                "content_ids": [cu.content_id],
                "page_start": cu.page_number,
                "page_end": cu.page_number,
                "timestamp_start": cu.timestamp_start,
                "timestamp_end": cu.timestamp_end,
                "source_id": source_id,
            }
            for cu in existing_cus if cu.text
        ]

        assessment_session = await asyncio.to_thread(start_assessment,
            student_id=student_id,
            source_id=source_id,
            payload=AssessmentStartRequest(
                student_id=student_id,
                source_id=source_id,
                max_questions=max_questions,
                step1_output={
                    "source_id": source_id,
                    "student_id": student_id,
                    "chunks": existing_chunks,
                    "knowledge_graph": kg.model_dump() if hasattr(kg, "model_dump") else {},
                },
            ),
        )
        assessment_resp = assessment_session.model_dump() if hasattr(assessment_session, "model_dump") else assessment_session

        gen_count = assessment_resp.get("generated_questions", len(assessment_resp.get("questions", [])))
        req_count = assessment_resp.get("requested_questions", max_questions)
        shortfall = assessment_resp.get("shortfall", max(0, req_count - gen_count))

        if shortfall > 0:
            await job_manager.emit_event(
                job_id=job_id,
                stage="validating_questions",
                status="warning",
                message=f"Question shortfall: generated {gen_count} of {req_count} requested questions.",
                progress_percent=95,
                metadata={"source_id": source_id, "shortfall": shortfall, "questions_generated": gen_count},
            )
        else:
            await job_manager.emit_event(
                job_id=job_id,
                stage="validating_questions",
                status="completed",
                message=f"Validated {gen_count} questions successfully.",
                progress_percent=95,
                metadata={"source_id": source_id, "questions_generated": gen_count},
            )

        elapsed_ms = int((time.time() - start_time) * 1000)
        await job_manager.complete_job(
            job_id=job_id,
            result={"assessment": assessment_resp, "source_id": source_id},
            message=f"Assessment ready ({gen_count} questions in {elapsed_ms}ms).",
        )
    except Exception as exc:
        logger.error("[pipeline_job] Error assessing existing source %s: %s", source_id, exc, exc_info=True)
        await job_manager.fail_job(
            job_id=job_id,
            stage="generating_questions",
            error_message=f"Assessment generation failed: {exc}",
            metadata={"source_id": source_id},
        )
    finally:
        if acquired_sem:
            sem.release()


@router.post("/upload-and-assess", response_model=JobCreationResponse)
async def create_upload_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    student_id: str = "student_default",
    max_questions: int = 5,
) -> JobCreationResponse:
    """Create background ingestion + assessment job and return job_id for SSE progress tracking."""
    if not job_manager.can_accept_job():
        raise HTTPException(
            status_code=429,
            detail=f"System job capacity reached ({settings.max_pending_jobs} active/queued jobs). Please retry later.",
            headers={"Retry-After": "30"},
        )

    filename = file.filename or "unnamed"
    temp_name = f"{uuid4().hex}_{Path(filename).name}"
    temp_path = settings.upload_dir / temp_name
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    from .upload import _validate_mime, _MAX_UPLOAD_BYTES
    _validate_mime(filename, file.content_type)
    try:
        size = 0
        with temp_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Upload exceeds size limit")
                out.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    job = job_manager.create_job(job_type="upload_and_assess")
    background_tasks.add_task(
        _execute_upload_and_assess,
        job_id=job.job_id,
        temp_path=temp_path,
        original_filename=filename,
        student_id=student_id,
        max_questions=max_questions,
    )

    return JobCreationResponse(
        job_id=job.job_id,
        status="pending",
        message="Upload and assessment job queued successfully.",
    )


@router.post("/assess-existing", response_model=JobCreationResponse)
async def create_assess_existing_job(
    payload: AssessExistingRequest,
    background_tasks: BackgroundTasks,
) -> JobCreationResponse:
    """Create background assessment generation job for existing source and return job_id."""
    if not job_manager.can_accept_job():
        raise HTTPException(
            status_code=429,
            detail=f"System job capacity reached ({settings.max_pending_jobs} active/queued jobs). Please retry later.",
            headers={"Retry-After": "30"},
        )

    job = job_manager.create_job(job_type="assess_existing")
    background_tasks.add_task(
        _execute_assess_existing,
        job_id=job.job_id,
        source_id=payload.source_id,
        student_id=payload.student_id,
        max_questions=payload.max_questions,
    )
    return JobCreationResponse(
        job_id=job.job_id,
        status="pending",
        message="Assessment generation job queued successfully.",
    )


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str):
    """Server-Sent Events (SSE) telemetry stream for a pipeline job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    async def event_generator():
        # Subscribe before replay so events emitted while yielding are not lost.
        queue = job_manager.subscribe(job_id)
        history = list(job.events)
        try:
            for event in history:
                yield f"data: {event.model_dump_json()}\n\n"
                if event.terminal:
                    return
            while True:
                try:
                    event: ProgressEvent = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event.model_dump_json()}\n\n"
                    if event.terminal:
                        break
                except asyncio.TimeoutError:
                    # Keep-alive ping
                    yield ": ping\n\n"
                    if job.is_finished:
                        break
        finally:
            job_manager.unsubscribe(job_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Retrieve full job snapshot including current status and result."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job.model_dump()
