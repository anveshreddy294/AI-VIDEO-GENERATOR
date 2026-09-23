"""Automated test suite for OpenRouter structured output vision extraction and retry."""

import json
import urllib.error
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fastapi.testclient import TestClient

from app.api.pipeline import router
from app.core.config import settings
from app.main import app
from app.services.pipeline_tracker import job_manager
from app.services.registry import register_source, update_source_status
from app.services.schemas import VisionExtractionData
from app.services.vision import (
    VISION_AUTH_FAILED,
    VISION_FALLBACK_UNAVAILABLE,
    VISION_INVALID_RESPONSE,
    VISION_STRUCTURED_OUTPUT_UNAVAILABLE,
    VISION_TIMEOUT,
    _VISION_EXTRACTION_CACHE,
    _clean_json_response,
    extract_vision_openrouter,
    get_vision_extraction_json_schema,
)

SAMPLE_IMAGE_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
    b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f"
    b"\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b"
    b"\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01"
    b"\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)

@pytest.fixture(autouse=True)
def clear_vision_cache():
    _VISION_EXTRACTION_CACHE.clear()
    yield
    _VISION_EXTRACTION_CACHE.clear()

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


def test_schema_normalization():
    """Verify get_vision_extraction_json_schema outputs valid strict schema without title/default."""
    schema = get_vision_extraction_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "properties" in schema
    assert "required" in schema
    assert set(schema["required"]) == set(schema["properties"].keys())

    # Ensure no titles or defaults leak into property definitions
    for prop_name, prop_def in schema["properties"].items():
        assert "title" not in prop_def, f"Title leaked in {prop_name}"
        assert "default" not in prop_def, f"Default leaked in {prop_name}"
        if prop_def.get("type") == "array":
            assert "items" in prop_def
            assert "type" in prop_def["items"], f"Untyped array items in {prop_name}"


def test_clean_json_response_fences():
    """Verify code fence cleaning handles ```json, plain ```, and surrounding text."""
    raw_fenced = f"```json\n{json.dumps(VALID_EXTRACTION_JSON)}\n```"
    cleaned = _clean_json_response(raw_fenced)
    assert cleaned["headings"] == ["Newton's Second Law of Motion"]

    raw_plain = f"```\n{json.dumps(VALID_EXTRACTION_JSON)}\n```"
    cleaned_plain = _clean_json_response(raw_plain)
    assert cleaned_plain["formulas"] == ["F = m * a"]

    raw_chatter = f"Here is your extracted data:\n```json\n{json.dumps(VALID_EXTRACTION_JSON)}\n```\nHope this helps!"
    cleaned_chatter = _clean_json_response(raw_chatter)
    assert cleaned_chatter["confidence"] == 0.95


def test_extract_vision_openrouter_schema_fallback_to_json_object(monkeypatch):
    """Test Attempt 1 (json_schema) returning 404 transitions to Attempt 2 (json_object) and succeeds."""
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key-12345")
    monkeypatch.setattr(settings, "vision_model", "openrouter/free")
    monkeypatch.setattr(settings, "vision_fallback_model", "")
    monkeypatch.setattr(settings, "vision_timeout_seconds", 5.0)

    requests_made = []

    async def mock_post(url, *args, **kwargs):
        payload = kwargs.get("json", {})
        requests_made.append(payload)

        # Attempt 1: json_schema -> simulate 404
        if payload.get("response_format", {}).get("type") == "json_schema":
            return httpx.Response(
                status_code=404,
                text='{"error": {"message": "No endpoint found supporting json_schema"}}',
                request=httpx.Request("POST", url),
            )

        # Attempt 2: json_object -> succeed
        resp_obj = {
            "model": "dots-studio/dots-3-note-preview:free",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(VALID_EXTRACTION_JSON),
                    }
                }
            ],
        }
        return httpx.Response(
            status_code=200,
            json=resp_obj,
            request=httpx.Request("POST", url),
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = extract_vision_openrouter(SAMPLE_IMAGE_BYTES, source="newton.jpeg")

    assert isinstance(result, VisionExtractionData)
    assert result.confidence == 0.95
    assert len(requests_made) == 2
    assert requests_made[0]["response_format"]["type"] == "json_schema"
    assert requests_made[1]["response_format"]["type"] == "json_object"


def test_extract_vision_openrouter_bounded_at_most_two_requests(monkeypatch):
    """Ensure hard cap of at most 2 requests when both attempts fail."""
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key-12345")
    monkeypatch.setattr(settings, "vision_model", "openrouter/free")
    monkeypatch.setattr(settings, "vision_fallback_model", "")
    monkeypatch.setattr(settings, "vision_timeout_seconds", 5.0)

    requests_made = []

    async def mock_post(url, *args, **kwargs):
        payload = kwargs.get("json", {})
        requests_made.append(payload)
        return httpx.Response(
            status_code=500,
            text='{"error": "Internal Server Error"}',
            request=httpx.Request("POST", url),
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        from app.services.vision import VisionExtractionFailed

        with pytest.raises(VisionExtractionFailed):
            extract_vision_openrouter(SAMPLE_IMAGE_BYTES, source="newton.jpeg")

    assert len(requests_made) == 2


def test_extract_vision_fallback_unavailable_code(monkeypatch):
    """When fallback model is configured and Attempt 2 fails with 404, error_code is VISION_FALLBACK_UNAVAILABLE."""
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key-12345")
    monkeypatch.setattr(settings, "vision_model", "openrouter/free")
    monkeypatch.setattr(settings, "vision_fallback_model", "inclusionai/ling-3.0-flash-vl:free")
    monkeypatch.setattr(settings, "vision_timeout_seconds", 5.0)

    async def mock_post(url, *args, **kwargs):
        return httpx.Response(
            status_code=404,
            text='{"error": "Model not found"}',
            request=httpx.Request("POST", url),
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        from app.services.vision import VisionExtractionFailed

        with pytest.raises(VisionExtractionFailed) as exc_info:
            extract_vision_openrouter(SAMPLE_IMAGE_BYTES, source="newton.jpeg")

    assert exc_info.value.error_code == VISION_FALLBACK_UNAVAILABLE



def test_retry_failed_job_endpoint(tmp_path, monkeypatch):
    """Test POST /pipeline/jobs/{job_id}/retry endpoint validation and idempotency."""
    client = TestClient(app)

    # 1. Non-existent job -> 404
    resp = client.post("/pipeline/jobs/JOB_nonexistent/retry")
    assert resp.status_code == 404

    # 2. Register source and create a failed job
    test_file = tmp_path / "test_diagram.jpeg"
    test_file.write_bytes(SAMPLE_IMAGE_BYTES)

    source_record, persistent_file = register_source(test_file, "test_diagram.jpeg", uploaded_by="student_test")
    source_id = source_record.source_id

    # Create job and fail it
    job = job_manager.create_job(job_type="upload_and_assess")
    job.status = "failed"
    job.is_finished = True
    job.events = [
        MagicMock(
            stage="extracting_content",
            status="failed",
            metadata={"source_id": source_id, "filename": "test_diagram.jpeg"},
        )
    ]

    # Try retrying when source status is READY -> should be rejected with 400
    update_source_status(source_id, "READY")
    resp_ready = client.post(f"/pipeline/jobs/{job.job_id}/retry")
    assert resp_ready.status_code == 400
    assert "already successfully processed" in resp_ready.json()["detail"]

    # Set source status back to FAILED
    update_source_status(source_id, "FAILED")

    # Retry failed job -> should succeed
    with patch("app.api.pipeline._execute_upload_and_assess") as mock_exec:
        resp_retry = client.post(f"/pipeline/jobs/{job.job_id}/retry")
        assert resp_retry.status_code == 200
        data = resp_retry.json()
        assert "job_id" in data
        assert data["job_id"] != job.job_id
        new_job_id = data["job_id"]

        # Call retry again while new job is pending -> idempotency guard returns same new_job_id
        resp_idem = client.post(f"/pipeline/jobs/{job.job_id}/retry")
        assert resp_idem.status_code == 200
        assert resp_idem.json()["job_id"] == new_job_id
        assert "Reusing active retry job" in resp_idem.json()["message"]
