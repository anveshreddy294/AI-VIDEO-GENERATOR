"""Source-only background work; bearer tokens never enter job snapshots or logs."""
from __future__ import annotations
import asyncio
import logging
import time
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .pipeline import JobCreationResponse
from fastapi import BackgroundTasks, HTTPException
from ..services.ingestion.source_ingestion import ingest_source, index_committed_source
from ..services.pipeline_tracker import job_manager
from ..services.registry import calculate_sha256
from ..services.repositories.source_repository import SupabaseSourceRepository
from ..services.schemas import SourceRecord
from ..services.visual_router import VisualSignals
from ..services.ingestion.progress import source_progress, IngestionStage
from ..services.file_truth import FileTruth
from pydantic import JsonValue
from ..core.config import settings
from ..core.inference_budget import processing_budget
from ..services.ingestion.failures import SourceFailure, SourceIngestionFailed, SourceIndexFailed


async def complete_source_job(job_id: str, result: dict[str, JsonValue]) -> None:
    """Publish the terminal job only after the canonical operation has completed."""
    job = job_manager.get_job(job_id)
    logging.getLogger(__name__).info("SOURCE_JOB_TERMINAL job_id=%s status=completed readiness=%s warnings=%s", job_id, "CONTENT_READY" if result.get("content_ready") else "READY", result.get("warnings", []))
    if job:
        job.metadata['source_id'] = result['source_id']
        job.result = result
        job.error = None
        job.failure = None
        job.status = 'completed'
        job.is_finished = True
    await job_manager.emit_event(job_id=job_id, stage='content_ready' if result.get('content_ready') is True else 'source_ready', status='completed',
        message=('Extracted content available; hierarchy and indexing are optional.' if result.get('content_ready') is True else 'Source and knowledge READY; semantic indexing complete.' if result.get('knowledge_state')=='READY'
                 else 'Canonical source committed and indexed.'), progress_percent=100, terminal=True,
        metadata={'source_id': result['source_id']})


async def execute_source_job(job_id: str, repo: SupabaseSourceRepository, path: Path | None,
                             filename: str, record: SourceRecord | None = None, *, routing_signals: VisualSignals | None = None, file_truth: FileTruth | None = None, enrich: bool = False) -> None:
    task = asyncio.current_task()
    if task:
        job_manager.attach_task(job_id, task)
    worker: asyncio.Task[dict[str, JsonValue]] | None = None
    loop = asyncio.get_running_loop()
    stage_started = time.monotonic()
    last_stage: str = "queued"
    def progress(stage: IngestionStage) -> None:
        nonlocal stage_started, last_stage
        from ..core.inference_budget import check_budget
        check_budget()
        now = time.monotonic()
        logging.getLogger(__name__).info("SOURCE_JOB_STAGE job_id=%s stage=%s previous_stage=%s previous_elapsed_seconds=%.3f", job_id, stage, last_stage, now-stage_started)
        stage_started, last_stage = now, stage
        messages = {"EXTRACTING_SOURCE": "Extracting source", "PERSISTING_SOURCE": "Persisting verified source", "PREPARING_IMAGE": "Preparing image", "UNDERSTANDING_IMAGE": "Understanding image",
                    "VALIDATING_VISUAL_EVIDENCE": "Validating visual evidence",
                    "BUILDING_LEARNING_STRUCTURE": "Building learning structure", "INDEXING_SOURCE": "Indexing source"}
        percentages = {"EXTRACTING_SOURCE": 10, "PREPARING_IMAGE": 15, "UNDERSTANDING_IMAGE": 25,
            "VALIDATING_VISUAL_EVIDENCE": 45, "PERSISTING_SOURCE": 60,
            "BUILDING_LEARNING_STRUCTURE": 70, "INDEXING_SOURCE": 90}
        current = job_manager.get_job(job_id)
        percent = max(current.progress_percent if current else 0, percentages[stage])
        asyncio.run_coroutine_threadsafe(job_manager.emit_event(job_id=job_id, stage=stage, status="running",
            message=messages[stage], progress_percent=percent), loop).result(timeout=5)

    try:
        async with job_manager.get_semaphore():
            await job_manager.emit_event(job_id=job_id, stage='ingesting_source', status='running',
                message='Extracting and saving reusable content; enrichment is optional.', progress_percent=5)
            with source_progress(progress), processing_budget(settings.source_job_timeout_seconds):
                if record is not None:
                    worker = asyncio.create_task(asyncio.to_thread(index_committed_source, repo, record))
                elif path is not None:
                    if routing_signals is None and file_truth is None:
                        worker = asyncio.create_task(asyncio.to_thread(ingest_source, repo, path, filename, enrich=enrich))
                    else:
                        worker = asyncio.create_task(asyncio.to_thread(ingest_source, repo, path, filename, routing_signals=routing_signals, file_truth=file_truth, enrich=enrich))
                else:
                    raise ValueError('Source job has no input')
            try:
                result = await asyncio.shield(worker)
            except asyncio.CancelledError:
                # A thread cannot be cancelled: settle its actual publication outcome.
                result = await asyncio.shield(worker)
            await complete_source_job(job_id, result)
    except asyncio.CancelledError:
        # to_thread work may continue; durable INDEXING/FAILED state can be retried independently.
        await job_manager.fail_job(job_id, 'ingesting_source', 'Source job cancelled; check canonical source state')
        raise
    except Exception as error:
        # A lost READY acknowledgement is reconciled through the owned Data API.
        job = job_manager.get_job(job_id)
        source_id = job.metadata.get("source_id") if job else None
        if isinstance(source_id, str):
            try:
                current = await asyncio.to_thread(repo.get_source, source_id)
                if current is not None and current.status == "READY":
                    result = await asyncio.to_thread(index_committed_source, repo, current)
                    await complete_source_job(job_id, result)
                    return
                if current is not None:
                    version = await asyncio.to_thread(repo.get_source_version, current.source_id, current.version)
                    if version is None or version.provenance.get("downstream_optional") is not True:
                        await asyncio.to_thread(repo.mark_status, current, "FAILED", "SOURCE_PROCESSING_FAILED")
            except Exception as reconciliation_error:
                logging.getLogger(__name__).warning("Source reconciliation unavailable: %s", type(reconciliation_error).__name__)
        failure = (error.failure if isinstance(error, (SourceIngestionFailed, SourceIndexFailed)) else
                   SourceFailure(stage='EXTRACTION',code='SOURCE_JOB_TIMEOUT',reason_code='MODEL_TIMEOUT',retryable=True,
                                 message='Source processing exceeded its configured budget. Retry this source.') if isinstance(error, TimeoutError) else
                   SourceFailure(stage='PERSISTENCE', code='SOURCE_STORAGE_FAILED', retryable=True,
                                 message='Could not persist or index the source.'))
        job = job_manager.get_job(job_id)
        if job:
            job.failure = failure
        await job_manager.fail_job(job_id, failure.stage, failure.message,
                                   metadata={'error_code': failure.code})
        logging.getLogger(__name__).warning("SOURCE_JOB_TERMINAL job_id=%s status=failed stage=%s code=%s", job_id, failure.stage, failure.code)
    finally:
        job_manager.detach_task(job_id)
        if path is not None:
            if worker is not None and not worker.done():
                def release_input(done: asyncio.Task[dict[str, JsonValue]]) -> None:
                    # Observe any worker exception after cancellation; caller saw a cancelled job.
                    if not done.cancelled():
                        error = done.exception()
                        if error is not None:
                            logging.getLogger(__name__).warning('Cancelled source worker failed: %s', type(error).__name__)
                    path.unlink(missing_ok=True)
                worker.add_done_callback(release_input)
            else:
                path.unlink(missing_ok=True)


async def queue_source_job(background: BackgroundTasks, repo: SupabaseSourceRepository,
                            path: Path, filename: str, *, routing_signals: VisualSignals | None = None, file_truth: FileTruth | None = None) -> JobCreationResponse:
    from .pipeline import JobCreationResponse
    digest = calculate_sha256(path)
    key = f'source:{repo.owner_id}:{filename}:{digest}'
    job, created = await job_manager.get_or_create_active_job(key, job_type='source_ingestion')
    if created:
        job.metadata.update(source_owner=repo.owner_id, filename=filename,
            source_id="SRC_" + uuid5(NAMESPACE_URL, f"visualai:{repo.owner_id}:{filename}:{digest}").hex)
        background.add_task(execute_source_job, job.job_id, repo, path, filename, routing_signals=routing_signals, file_truth=file_truth)
    else:
        path.unlink(missing_ok=True)
    return JobCreationResponse(job_id=job.job_id, status=job.status, message='Source-only ingestion queued')


async def retry_source_job(background: BackgroundTasks, repo: SupabaseSourceRepository, job_id: str) -> JobCreationResponse:
    from .pipeline import JobCreationResponse
    old = job_manager.get_job(job_id)
    if old is None or old.metadata.get('source_owner') != repo.owner_id:
        raise HTTPException(404, 'Job not found')
    if not old.is_finished or old.status != 'failed':
        raise HTTPException(409, 'Only failed jobs may be retried')
    retry_count = old.metadata.get('retry_count', 0)
    if retry_count >= 3:
        raise HTTPException(429, 'Retry limit reached for this job (maximum 3 attempts)')
    source_id = old.metadata.get('source_id')
    if not isinstance(source_id, str):
        raise HTTPException(409, 'Repeat the same upload; deterministic IDs reuse committed records')
    record = repo.get_source(source_id)
    if record is None:
        raise HTTPException(404, 'Source not found')
    if record.status == 'READY':
        raise HTTPException(409, 'Source is already successfully processed; existing artifacts preserved')
    old_version = old.metadata.get('source_version')
    if old_version is not None and getattr(record, 'version', None) is not None and old_version != record.version:
        raise HTTPException(409, 'Source version has changed; start a new ingestion for the updated version')
    job, created = await job_manager.get_or_create_active_job(f'source-retry:{repo.owner_id}:{source_id}', job_type='source_ingestion')
    if created:
        job.metadata.update(
            source_owner=repo.owner_id,
            source_id=source_id,
            retry_count=retry_count + 1,
            prior_job_id=old.job_id,
            source_version=getattr(record, 'version', None),
        )
        background.add_task(execute_source_job, job.job_id, repo, None, record.filename, record)
    return JobCreationResponse(job_id=job.job_id, status=job.status)
