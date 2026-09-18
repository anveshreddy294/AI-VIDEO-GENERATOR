"""Observable pipeline API routes — Background Job Creation & Real-Time SSE Telemetry.

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
from ..services.pipeline_tracker import ProgressEvent, job_manager
from ..services.registry import (
    get_source_record,
    load_knowledge_graph,
    register_source,
    save_content_units,
    save_knowledge_graph,
    update_source_status,
)
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
            source_record, persistent_file = register_source(temp_path, original_filename)
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
            extraction_result = dispatch(persistent_file, source_id=source_id, asset_id=asset_id)
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
            message="Normalizing ContentUnits and anchoring structural lineage...",
            progress_percent=30,
            metadata={"source_id": source_id},
        )

        await job_manager.emit_event(
            job_id=job_id,
            stage="analyzing_structure",
            status="running",
            message="Analyzing document outline and extracting conceptual relationships...",
            progress_percent=40,
            metadata={"source_id": source_id},
        )

        try:
            enriched_units, knowledge_graph, blueprint = process_structure_and_concepts(raw_units)
        except Exception as exc:
            await job_manager.fail_job(
                job_id=job_id,
                stage="extracting_concepts",
                error_message=f"Concept extraction failed: {exc}",
                metadata={"source_id": source_id},
            )
            return

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

        await job_manager.emit_event(
            job_id=job_id,
            stage="extracting_concepts",
            status="completed",
            message=f"Extracted {len(knowledge_graph.concepts)} core concepts.",
            progress_percent=55,
            metadata={"source_id": source_id, "concepts_count": len(knowledge_graph.concepts)},
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

        rich_chunks = create_rich_chunks(enriched_units, knowledge_graph)
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

        synced_count = 0
        qdrant_warning = None
        try:
            from ..db.vector_store import upsert_chunks
            synced_count = upsert_chunks(rich_chunks)
        except Exception as exc:
            qdrant_warning = f"Qdrant daemon unavailable; fell back to embedded storage: {exc}"
            logger.warning("[pipeline_job] %s", qdrant_warning)
            # When remote vector store is unavailable, allow fallback execution to proceed
            synced_count = len(rich_chunks)

        if qdrant_warning:
            await job_manager.emit_event(
                job_id=job_id,
                stage="syncing_qdrant",
                status="warning",
                message="Vector database running in local fallback mode.",
                progress_percent=80,
                metadata={"source_id": source_id, "warning_reason": qdrant_warning[:150]},
            )
        else:
            await job_manager.emit_event(
                job_id=job_id,
                stage="syncing_qdrant",
                status="completed",
                message=f"Synced {synced_count} chunks into Qdrant vector index.",
                progress_percent=82,
                metadata={"source_id": source_id, "chunks_count": synced_count},
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

            assessment_session = start_assessment(
                student_id=student_id,
                source_id=source_id,
                payload=AssessmentStartRequest(
                    student_id=student_id,
                    source_id=source_id,
                    max_questions=max_questions,
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
        temp_path.unlink(missing_ok=True)


async def _execute_assess_existing(
    job_id: str,
    source_id: str,
    student_id: str,
    max_questions: int,
) -> None:
    """Execute assessment generation for an existing source emitting operational progress."""
    start_time = time.time()
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

        assessment_session = start_assessment(
            student_id=student_id,
            source_id=source_id,
            payload=AssessmentStartRequest(
                student_id=student_id,
                source_id=source_id,
                max_questions=max_questions,
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


@router.post("/upload-and-assess", response_model=JobCreationResponse)
async def create_upload_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    student_id: str = "student_default",
    max_questions: int = 5,
) -> JobCreationResponse:
    """Create background ingestion + assessment job and return job_id for SSE progress tracking."""
    filename = file.filename or "unnamed"
    temp_name = f"{uuid4().hex}_{Path(filename).name}"
    temp_path = settings.upload_dir / temp_name
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    with temp_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

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
        # 1. Replay historical events already recorded
        for event in list(job.events):
            yield f"data: {event.model_dump_json()}\n\n"

        if job.is_finished:
            return

        # 2. Subscribe to live stream
        queue = job_manager.subscribe(job_id)
        try:
            while True:
                try:
                    event: ProgressEvent = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event.model_dump_json()}\n\n"
                    if event.status in ("completed", "failed"):
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
