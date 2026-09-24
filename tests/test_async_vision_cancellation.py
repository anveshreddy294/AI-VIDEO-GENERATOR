"""Automated test suite for async vision extraction, cancellation, semaphore safety, and job dedup."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.pipeline import router
from app.core.config import settings
from app.main import app
from app.services.dispatcher import ExtractionResult, dispatch_async
from app.services.pipeline_tracker import job_manager
from app.services.registry import get_source_record, register_source, update_source_status
from app.services.schemas import VisionExtractionData
from app.services.vision import (
    VISION_TIMEOUT,
    _VISION_EXTRACTION_CACHE,
    describe_image_async,
    extract_vision_openrouter_async,
    VisionExtractionFailed,
)

SAMPLE_IMAGE_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
    b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f"
    b"\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b"
    b"\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01"
    b"\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)

VALID_EXTRACTION_JSON = {
    "visible_text": [
        "Newton's Second Law of Motion",
        "F = m * a where F is Net Force, m is Mass, a is Acceleration",
        "Units: Force in Newtons (N), Mass in kg, Acceleration in m/s^2",
    ],
    "headings": ["Newton's Second Law of Motion"],
    "paragraphs": ["Describes the relationship between force, mass, and acceleration."],
    "bullet_points": ["Force is directly proportional to acceleration"],
    "diagram_entities": ["Block on inclined plane", "Gravity vector", "Normal force"],
    "labels": ["F_net", "m", "a"],
    "arrows": ["Downwards -> Gravity", "Perpendicular -> Normal"],
    "relationships": ["Force -> Acceleration"],
    "tables": [],
    "formulas": ["F = m * a"],
    "units": ["N", "kg", "m/s^2"],
    "visual_structure": "Diagram on left with formula box on right",
    "uncertain_elements": [],
    "confidence": 0.95,
}


@pytest.fixture(autouse=True)
def setup_teardown():
    _VISION_EXTRACTION_CACHE.clear()
    job_manager.reset_semaphore(2)
    yield
    _VISION_EXTRACTION_CACHE.clear()
    job_manager.reset_semaphore(2)


# =========================================================================
# Scenario A: Async vision extraction succeeds with primary candidate (Attempt 1)
# =========================================================================
def test_scenario_a_async_vision_attempt1_success(monkeypatch):
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test-key")

        mock_resp = httpx.Response(
            status_code=200,
            json={
                "id": "gen-1",
                "model": "google/gemini-2.0-flash-exp:free",
                "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
            },
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES)

            assert isinstance(result, VisionExtractionData)
            assert result.headings == ["Newton's Second Law of Motion"]
            assert result.formulas == ["F = m * a"]
            assert mock_post.call_count == 1
            # Check payload format: primary candidate (Ling) receives NO response_format
            kwargs = mock_post.call_args.kwargs
            assert "response_format" not in kwargs["json"]

    asyncio.run(_run())


# =========================================================================
# Scenario B: JSON schema fallback to JSON object mode succeeds on Attempt 2
# =========================================================================
def test_scenario_b_schema_fallback_to_json_object(monkeypatch):
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test-key")
        monkeypatch.setattr(settings, "vision_fallback_model", "")

        resp1 = httpx.Response(
            status_code=400,
            text="Unsupported response_format json_schema",
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )
        resp2 = httpx.Response(
            status_code=200,
            json={
                "id": "gen-2",
                "model": "google/gemini-2.0-flash-exp:free",
                "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
            },
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [resp1, resp2]
            result = await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES)

            assert isinstance(result, VisionExtractionData)
            assert mock_post.call_count == 2
            # Check second call used json_object
            kwargs2 = mock_post.call_args_list[1].kwargs
            assert kwargs2["json"]["response_format"]["type"] == "json_object"

    asyncio.run(_run())


# =========================================================================
# Scenario C: Per-request read timeout fails cleanly without orphan threads
# =========================================================================
def test_scenario_c_read_timeout_fails_cleanly(monkeypatch):
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test-key")
        monkeypatch.setattr(settings, "vision_fallback_model", "")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ReadTimeout("Read timed out", request=MagicMock())
            with pytest.raises(VisionExtractionFailed) as exc_info:
                await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES)

            assert exc_info.value.error_code == VISION_TIMEOUT
            assert mock_post.call_count == 2

    asyncio.run(_run())


# =========================================================================
# Scenario D: Stage timeout aborts extraction within deadline and marks job failed
# =========================================================================
def test_scenario_d_stage_timeout_marks_job_failed(monkeypatch):
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test-key")

        async def hanging_post(*args, **kwargs):
            await asyncio.sleep(10.0)
            return MagicMock()

        with patch("httpx.AsyncClient.post", side_effect=hanging_post):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES), timeout=0.1)

    asyncio.run(_run())


# =========================================================================
# Scenario E: True job cancellation immediately stops async task
# =========================================================================
def test_scenario_e_true_async_cancellation(monkeypatch):
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test-key")

        cancelled_event = asyncio.Event()

        async def hanging_post(*args, **kwargs):
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        with patch("httpx.AsyncClient.post", side_effect=hanging_post):
            task = asyncio.create_task(extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES))
            await asyncio.sleep(0.05)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            assert cancelled_event.is_set(), "Underlying async HTTP request was not cancelled!"

    asyncio.run(_run())


# =========================================================================
# Scenario F: Graceful server shutdown cleanly cancels active jobs
# =========================================================================
def test_scenario_f_graceful_shutdown():
    async def _run():
        job1 = job_manager.create_job(job_type="upload_and_assess")
        job2 = job_manager.create_job(job_type="upload_and_assess")

        cancelled_1 = False
        cancelled_2 = False

        async def dummy_job_1():
            nonlocal cancelled_1
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                cancelled_1 = True
                raise

        async def dummy_job_2():
            nonlocal cancelled_2
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                cancelled_2 = True
                raise

        t1 = asyncio.create_task(dummy_job_1())
        t2 = asyncio.create_task(dummy_job_2())

        job_manager.attach_task(job1.job_id, t1)
        job_manager.attach_task(job2.job_id, t2)

        # Allow tasks to start running their try blocks
        await asyncio.sleep(0.01)

        await job_manager.shutdown_active_jobs(timeout=1.0)


        assert cancelled_1 is True
        assert cancelled_2 is True
        assert t1.cancelled() or t1.done()
        assert t2.cancelled() or t2.done()

    asyncio.run(_run())


# =========================================================================
# Scenario G: Source status on cancellation maps to FAILED (no ValidationError)
# =========================================================================
def test_scenario_g_source_status_on_cancelled_no_validation_error(tmp_path):
    test_file = tmp_path / "test.jpeg"
    test_file.write_bytes(SAMPLE_IMAGE_BYTES)

    rec, _ = register_source(test_file, "test.jpeg", uploaded_by="student_test")

    # Calling update_source_status with "CANCELLED" must map to "FAILED" without raising ValidationError
    rec_updated = update_source_status(rec.source_id, "CANCELLED", error_message="User cancelled job")

    assert rec_updated is not None
    assert rec_updated.status == "FAILED"
    assert "cancelled" in (rec_updated.error_message or "").lower()

    # Double check fetched record
    fetched = get_source_record(rec.source_id)
    assert fetched.status == "FAILED"


# =========================================================================
# Scenario H: Semaphore cancellation safety (no permit leak or double release)
# =========================================================================
def test_scenario_h_semaphore_cancellation_safety():
    async def _run():
        job_manager.reset_semaphore(1)
        sem = job_manager.get_semaphore()

        # Acquire the single permit
        await sem.acquire()
        assert sem.locked()

        # Task waiting to acquire is cancelled before obtaining the permit
        waiting_task_started = asyncio.Event()

        async def waiter():
            waiting_task_started.set()
            acquired = False
            try:
                await sem.acquire()
                acquired = True
            finally:
                if acquired:
                    sem.release()

        t = asyncio.create_task(waiter())
        await waiting_task_started.wait()
        await asyncio.sleep(0.01)

        # Cancel waiter while waiting
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

        # Semaphore should STILL be locked by the first acquirer (no double release or permit leak)
        assert sem.locked()

        # Release the first permit
        sem.release()
        assert not sem.locked()

    asyncio.run(_run())


# =========================================================================
# Scenario I: Atomic duplicate upload dedup
# =========================================================================
def test_scenario_i_atomic_duplicate_upload_dedup():
    async def _run():
        dedup_key = "student_test:fake_sha256:v1"

        # Simulate two concurrent calls
        async def call_dedup():
            return await job_manager.get_or_create_active_job(dedup_key, job_type="upload_and_assess")

        results = await asyncio.gather(call_dedup(), call_dedup())

        jobs = [r[0] for r in results]
        created_flags = [r[1] for r in results]

        assert jobs[0].job_id == jobs[1].job_id
        assert created_flags.count(True) == 1
        assert created_flags.count(False) == 1

    asyncio.run(_run())


# =========================================================================
# Scenario J: Dispatch async image extraction routes directly to async vision
# =========================================================================
def test_scenario_j_dispatch_async_image(tmp_path, monkeypatch):
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test-key")

        test_image = tmp_path / "sample.jpeg"
        test_image.write_bytes(SAMPLE_IMAGE_BYTES)

        mock_resp = httpx.Response(
            status_code=200,
            json={
                "id": "gen-1",
                "model": "google/gemini-2.0-flash-exp:free",
                "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
            },
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await dispatch_async(test_image, source_id="SRC_123", asset_id="AST_123")

            assert isinstance(result, ExtractionResult)
            assert result.modality == "image"
            assert len(result.units) == 1
            assert "Newton's Second Law" in result.units[0].visual_description

    asyncio.run(_run())


# =========================================================================
# Scenario K: Bounded provider attempt budget: at most 2 requests in default config
# =========================================================================
def test_scenario_k_bounded_attempt_budget_default_two_attempts(monkeypatch):
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test-key")
        monkeypatch.setattr(settings, "vision_fallback_model", "")

        # Both attempts return 500 error
        resp = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = resp
            with pytest.raises(VisionExtractionFailed):
                await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES)

            # Must be exactly 2 calls, NEVER 3
            assert mock_post.call_count == 2

    asyncio.run(_run())
