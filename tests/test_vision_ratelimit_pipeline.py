"""Test image pipeline recovery and progression on OpenRouter HTTP 429 rate limit."""

import asyncio
from unittest.mock import AsyncMock, patch
from pathlib import Path
import httpx
import pytest

from app.core.config import settings
from app.services.pipeline_tracker import job_manager
from app.services.registry import get_source
from app.api.pipeline import _execute_upload_and_assess
from app.services.vision import VisionExtractionFailed, VISION_RATE_LIMIT


SAMPLE_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_image_pipeline_recovers_from_429_rate_limit(tmp_path, monkeypatch):
    """Verify that when OpenRouter vision returns 429, the pipeline recovers and completes structuring."""
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
        monkeypatch.setattr(settings, "vision_rate_limit_fallback", True)
        monkeypatch.setattr(settings, "llm_provider", "mock")

        test_img = tmp_path / "ratelimit_sample.png"
        test_img.write_bytes(SAMPLE_PNG_BYTES)

        job = job_manager.create_job("upload_and_assess")
        job_id = job.job_id

        async def mock_dispatch_async(*args, **kwargs):
            raise VisionExtractionFailed("All OpenRouter vision models rate-limited (HTTP 429)", error_code=VISION_RATE_LIMIT)

        with patch("app.api.pipeline.dispatch_async", side_effect=mock_dispatch_async):
            await _execute_upload_and_assess(
                job_id=job_id,
                temp_path=test_img,
                original_filename="ratelimit_sample.png",
                student_id="student_123",
                max_questions=3,
            )

        # Check job status
        finished_job = job_manager.get_job(job_id)
        assert finished_job is not None
        assert finished_job.status == "completed"
        assert finished_job.progress_percent == 100

        # Source must be READY
        source_id = None
        for event in finished_job.events:
            if "source_id" in event.metadata:
                source_id = event.metadata["source_id"]
        assert source_id is not None
        source = get_source(source_id)
        assert source is not None
        assert source.status == "READY", f"Expected READY, got {source.status} with error: {source.error_message}"

    asyncio.run(_run())


def test_image_pipeline_fails_closed_when_fallback_disabled(tmp_path, monkeypatch):
    """Verify that when vision_rate_limit_fallback is explicitly False, 429 fails closed."""
    async def _run():
        monkeypatch.setattr(settings, "vision_provider", "openrouter")
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
        monkeypatch.setattr(settings, "vision_rate_limit_fallback", False)

        test_img = tmp_path / "ratelimit_fail_closed.png"
        test_img.write_bytes(SAMPLE_PNG_BYTES)

        job = job_manager.create_job("upload_and_assess")
        job_id = job.job_id

        async def mock_dispatch_async(*args, **kwargs):
            raise VisionExtractionFailed("All OpenRouter vision models rate-limited (HTTP 429)", error_code=VISION_RATE_LIMIT)

        with patch("app.api.pipeline.dispatch_async", side_effect=mock_dispatch_async):
            await _execute_upload_and_assess(
                job_id=job_id,
                temp_path=test_img,
                original_filename="ratelimit_fail_closed.png",
                student_id="student_123",
                max_questions=3,
            )

        finished_job = job_manager.get_job(job_id)
        assert finished_job is not None
        assert finished_job.status == "failed"

        source_id = None
        for event in finished_job.events:
            if "source_id" in event.metadata:
                source_id = event.metadata["source_id"]
        assert source_id is not None
        source = get_source(source_id)
        assert source is not None
        assert source.status == "FAILED"
        assert "VISION_RATE_LIMIT" in (source.error_message or "")

    asyncio.run(_run())
