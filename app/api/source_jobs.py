"""Source-only background work; bearer tokens never enter job snapshots or logs."""
from __future__ import annotations
import asyncio
import logging
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
from pydantic import JsonValue
from ..services.ingestion.failures import SourceFailure, SourceIngestionFailed, SourceIndexFailed


async def execute_source_job(job_id: str, repo: SupabaseSourceRepository, path: Path | None,
                             filename: str, record: SourceRecord | None = None, *, routing_signals: VisualSignals | None = None) -> None:
    task = asyncio.current_task()
    if task:
        job_manager.attach_task(job_id, task)
    worker: asyncio.Task[dict[str, JsonValue]] | None = None
    try:
        async with job_manager.get_semaphore():
            await job_manager.emit_event(job_id=job_id, stage='ingesting_source', status='running',
                message='Extracting and committing canonical source before vector indexing.', progress_percent=5)
            if record is not None:
                worker = asyncio.create_task(asyncio.to_thread(index_committed_source, repo, record))
            elif path is not None:
                if routing_signals is None:
                    worker = asyncio.create_task(asyncio.to_thread(ingest_source, repo, path, filename))
                else:
                    worker = asyncio.create_task(asyncio.to_thread(ingest_source, repo, path, filename, routing_signals=routing_signals))
            else:
                raise ValueError('Source job has no input')
            result = await asyncio.shield(worker)
            job = job_manager.get_job(job_id)
            if job:
                job.metadata['source_id'] = result['source_id']
                job.result = result
                job.status = 'completed'
                job.is_finished = True
            await job_manager.emit_event(job_id=job_id, stage='source_ready', status='completed',
                message=('Source and knowledge READY; semantic indexing complete.' if result.get('knowledge_state')=='READY'
                         else 'Canonical source committed and indexed.'), progress_percent=100, terminal=True,
                metadata={'source_id': result['source_id']})
    except asyncio.CancelledError:
        # to_thread work may continue; durable INDEXING/FAILED state can be retried independently.
        await job_manager.fail_job(job_id, 'ingesting_source', 'Source job cancelled; check canonical source state')
        raise
    except Exception as error:
        failure = (error.failure if isinstance(error, (SourceIngestionFailed, SourceIndexFailed)) else
                   SourceFailure(stage='PERSISTENCE', code='SOURCE_STORAGE_FAILED', retryable=True,
                                 message='Could not persist or index the source.'))
        job = job_manager.get_job(job_id)
        if job:
            job.failure = failure
        await job_manager.fail_job(job_id, failure.stage, failure.message,
                                   metadata={'error_code': failure.code})
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
                            path: Path, filename: str, *, routing_signals: VisualSignals | None = None) -> JobCreationResponse:
    from .pipeline import JobCreationResponse
    digest = calculate_sha256(path)
    key = f'source:{repo.owner_id}:{filename}:{digest}'
    job, created = await job_manager.get_or_create_active_job(key, job_type='source_ingestion')
    if created:
        job.metadata.update(source_owner=repo.owner_id, filename=filename,
            source_id="SRC_" + uuid5(NAMESPACE_URL, f"visualai:{repo.owner_id}:{filename}:{digest}").hex)
        background.add_task(execute_source_job, job.job_id, repo, path, filename, routing_signals=routing_signals)
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
    source_id = old.metadata.get('source_id')
    if not isinstance(source_id, str):
        raise HTTPException(409, 'Repeat the same upload; deterministic IDs reuse committed records')
    record = repo.get_source(source_id)
    if record is None:
        raise HTTPException(404, 'Source not found')
    job, created = await job_manager.get_or_create_active_job(f'source-retry:{repo.owner_id}:{source_id}', job_type='source_ingestion')
    if created:
        job.metadata.update(source_owner=repo.owner_id, source_id=source_id)
        background.add_task(execute_source_job, job.job_id, repo, None, record.filename, record)
    return JobCreationResponse(job_id=job.job_id, status=job.status)
