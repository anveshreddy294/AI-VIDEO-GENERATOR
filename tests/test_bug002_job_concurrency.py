"""Tests for BUG-002: Bounded Background Jobs and Admission Control."""

import asyncio
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.pipeline_tracker import job_manager, PipelineJob


def test_concurrency_semaphore_bounds_active_jobs():
    """Assert that concurrent jobs never exceed MAX_BACKGROUND_JOBS."""
    async def _test():
        job_manager.reset_semaphore(limit=2)
        sem = job_manager.get_semaphore()

        max_concurrent_observed = 0
        currently_running = 0

        async def worker():
            nonlocal max_concurrent_observed, currently_running
            async with sem:
                currently_running += 1
                if currently_running > max_concurrent_observed:
                    max_concurrent_observed = currently_running
                await asyncio.sleep(0.05)
                currently_running -= 1

        tasks = [asyncio.create_task(worker()) for _ in range(6)]
        await asyncio.gather(*tasks)

        assert max_concurrent_observed == 2
        assert currently_running == 0

    asyncio.run(_test())


def test_semaphore_slot_released_on_exception():
    """Verify that semaphore slot is released even when an exception occurs."""
    async def _test():
        job_manager.reset_semaphore(limit=1)
        sem = job_manager.get_semaphore()

        async def failing_worker():
            acquired = False
            await sem.acquire()
            acquired = True
            try:
                raise RuntimeError("Simulated unhandled failure in worker")
            finally:
                if acquired:
                    sem.release()

        with pytest.raises(RuntimeError, match="Simulated unhandled failure"):
            await failing_worker()

        # Slot must be free and available for next job
        assert not sem.locked()
        await sem.acquire()
        sem.release()

    asyncio.run(_test())


def test_semaphore_slot_released_on_cancellation():
    """Verify that semaphore slot is released when a task is cancelled."""
    async def _test():
        job_manager.reset_semaphore(limit=1)
        sem = job_manager.get_semaphore()

        acquired_event = asyncio.Event()

        async def long_worker():
            acquired = False
            await sem.acquire()
            acquired = True
            try:
                acquired_event.set()
                await asyncio.sleep(10.0)
            finally:
                if acquired:
                    sem.release()

        task = asyncio.create_task(long_worker())
        await acquired_event.wait()
        assert sem.locked()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # After cancellation, slot must be released
        assert not sem.locked()

    asyncio.run(_test())


def test_admission_control_rejects_when_backlog_full(monkeypatch):
    """Verify HTTP 429 when max_pending_jobs is exceeded."""
    monkeypatch.setattr(settings, "max_pending_jobs", 3)

    # Populate job manager with 3 active jobs
    job_manager._jobs.clear()
    for i in range(3):
        j = job_manager.create_job("upload_and_assess", job_id=f"JOB_active_{i}")
        j.status = "running"
        j.is_finished = False

    assert not job_manager.can_accept_job()

    client = TestClient(app)
    resp = client.post(
        "/pipeline/assess-existing",
        json={"source_id": "SRC_NONEXISTENT", "student_id": "test_stu", "max_questions": 3},
    )
    assert resp.status_code == 429
    assert "capacity reached" in resp.json().get("detail", "").lower()
    assert resp.headers.get("Retry-After") == "30"


def test_job_retention_pruning(monkeypatch):
    """Verify that oldest completed jobs are pruned when exceeding job_retention_max."""
    monkeypatch.setattr(settings, "job_retention_max", 5)
    job_manager._jobs.clear()

    # Create 10 completed jobs
    for i in range(10):
        j = job_manager.create_job("upload_and_assess", job_id=f"JOB_old_{i:02d}")
        j.status = "completed"
        j.is_finished = True

    # 11th job triggers cleanup
    job_manager.create_job("upload_and_assess", job_id="JOB_new")

    # Only retention limit items should remain, and newest should be present
    assert len(job_manager._jobs) <= 6
    assert "JOB_new" in job_manager._jobs
    assert "JOB_old_00" not in job_manager._jobs  # Oldest pruned
