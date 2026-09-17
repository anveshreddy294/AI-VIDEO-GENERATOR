"""Pipeline progress tracking and telemetry event broadcaster.

Provides:
1. Structured ProgressEvent modeling.
2. Metadata sanitization ensuring no secrets, API keys, prompts, or stack traces leak.
3. Thread-safe in-memory job registry and async subscriber queues for SSE streaming.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ProgressStatus = Literal["pending", "running", "completed", "warning", "failed"]

SAFE_METADATA_KEYS = {
    "filename",
    "file_size",
    "source_id",
    "asset_id",
    "modality",
    "content_units_count",
    "concepts_count",
    "chunks_count",
    "questions_requested",
    "questions_generated",
    "shortfall",
    "failed_concepts",
    "fallback_used",
    "warning_reason",
    "error_code",
    "duration_ms",
    "score",
    "total",
    "percentage",
    "session_id",
    "student_id",
}


def sanitize_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Strictly sanitize metadata to allow only safe operational metrics.

    Strips any keys or values containing secrets, tokens, API keys, prompts,
    filesystem paths, or stack traces.
    """
    if not meta:
        return {}

    sanitized: dict[str, Any] = {}
    for key, val in meta.items():
        if key not in SAFE_METADATA_KEYS:
            continue

        # Prevent nested secret leakage
        if isinstance(val, (int, float, bool)):
            sanitized[key] = val
        elif isinstance(val, list):
            # Allow clean string/number lists (e.g. failed_concepts)
            clean_list = [
                str(item)[:100]
                for item in val
                if not any(s in str(item).lower() for s in ("key", "token", "secret", "bearer", "traceback"))
            ]
            sanitized[key] = clean_list
        elif isinstance(val, str):
            # Filter out sensitive patterns
            low = val.lower()
            if any(s in low for s in ("api_key", "bearer ", "secret", "private_key", "traceback", "password")):
                continue
            sanitized[key] = val[:250]

    return sanitized


class ProgressEvent(BaseModel):
    """A single observable operational event in the pipeline execution telemetry."""
    job_id: str
    stage: str
    status: ProgressStatus
    message: str
    progress_percent: int = Field(ge=0, le=100)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineJob(BaseModel):
    """Tracks state and event history for a background pipeline execution job."""
    job_id: str
    job_type: str
    status: ProgressStatus = "pending"
    current_stage: str = "queued"
    progress_percent: int = 0
    events: list[ProgressEvent] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_finished: bool = False


class JobManager:
    """Thread-safe in-memory job registry and SSE event broadcaster."""

    def __init__(self):
        self._jobs: dict[str, PipelineJob] = {}
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    def create_job(self, job_type: str, job_id: str | None = None) -> PipelineJob:
        jid = job_id or f"JOB_{uuid4().hex[:12]}"
        job = PipelineJob(job_id=jid, job_type=job_type)
        self._jobs[jid] = job
        self._subscribers[jid] = set()
        return job

    def get_job(self, job_id: str) -> PipelineJob | None:
        return self._jobs.get(job_id)

    async def emit_event(
        self,
        job_id: str,
        stage: str,
        status: ProgressStatus,
        message: str,
        progress_percent: int,
        metadata: dict[str, Any] | None = None,
    ) -> ProgressEvent:
        """Record an event and dispatch it asynchronously to all active SSE subscribers."""
        safe_meta = sanitize_metadata(metadata)
        event = ProgressEvent(
            job_id=job_id,
            stage=stage,
            status=status,
            message=message,
            progress_percent=max(0, min(100, progress_percent)),
            metadata=safe_meta,
        )

        job = self._jobs.get(job_id)
        if job:
            job.current_stage = stage
            job.status = status if status in ("failed", "completed") else ("warning" if status == "warning" else "running")
            job.progress_percent = event.progress_percent
            job.updated_at = event.timestamp
            job.events.append(event)
            if status in ("completed", "failed"):
                job.is_finished = True

        # Dispatch to active SSE queues
        subs = list(self._subscribers.get(job_id, []))
        for q in subs:
            try:
                q.put_nowait(event)
            except Exception as exc:
                logger.debug("Failed putting event to queue: %s", exc)

        return event

    async def complete_job(
        self,
        job_id: str,
        result: dict[str, Any],
        message: str = "Pipeline execution completed successfully.",
    ) -> None:
        """Mark job as completed and send final completion event."""
        job = self._jobs.get(job_id)
        if job:
            job.result = result
            job.status = "completed"
            job.is_finished = True
        await self.emit_event(
            job_id=job_id,
            stage="assessment_ready",
            status="completed",
            message=message,
            progress_percent=100,
            metadata={"questions_generated": len(result.get("assessment", {}).get("questions", [])) if "assessment" in result else 0},
        )

    async def fail_job(
        self,
        job_id: str,
        stage: str,
        error_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mark job as failed and emit terminal failure event."""
        job = self._jobs.get(job_id)
        if job:
            job.error = error_message
            job.status = "failed"
            job.is_finished = True
        await self.emit_event(
            job_id=job_id,
            stage=stage,
            status="failed",
            message=error_message,
            progress_percent=job.progress_percent if job else 0,
            metadata=metadata,
        )

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Register a new SSE client subscriber queue for a given job."""
        q: asyncio.Queue = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = set()
        self._subscribers[job_id].add(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        """Unregister an SSE client queue."""
        if job_id in self._subscribers:
            self._subscribers[job_id].discard(q)


# Singleton instance across application
job_manager = JobManager()
