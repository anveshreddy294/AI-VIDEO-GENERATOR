"""Test suite verifying all 13 vision candidate chain requirements.

Requirements covered:
1. openrouter/free absent from production candidate chain
2. Ling receives no response_format
3. Gemma receives {"type":"json_object"}
4. maximum attempts == 2
5. Ling invalid JSON falls back to Gemma
6. Ling timeout falls back to Gemma if stage budget remains
7. Gemma success produces validated VisionExtractionData
8. HTTP 200 without completed body still respects timeout
9. cancellation still stops actual httpx request
10. TXT pipeline remains unaffected
11. qwen3:1.7b reasoning remains untouched
12. OCR fallback remains grounded
13. API key never appears in logs
"""

import asyncio
import json
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core.config import settings
from app.services.schemas import VisionExtractionData
from app.services.vision import (
    VISION_TIMEOUT,
    VISION_INVALID_RESPONSE,
    VisionExtractionFailed,
    VisionModelCandidate,
    _PROMPT_INSTRUCTION_PROMPT_JSON,
    _VISION_EXTRACTION_CACHE,
    _get_vision_candidate_plan,
    describe_image,
    extract_vision_openrouter_async,
)
from app.services.dispatcher import dispatch, dispatch_async


SAMPLE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

VALID_EXTRACTION_JSON = {
    "visible_text": ["Newton's Second Law of Motion: F = ma"],
    "headings": ["Classical Mechanics"],
    "paragraphs": ["Acceleration is proportional to net force."],
    "bullet_points": ["m = mass", "a = acceleration"],
    "diagram_entities": ["Mass Block", "Force Vector"],
    "labels": ["F_net"],
    "arrows": ["Force -> Acceleration"],
    "relationships": ["Force induces acceleration"],
    "tables": [],
    "formulas": ["F = m * a"],
    "units": ["N", "kg", "m/s^2"],
    "visual_structure": "Free body diagram with vector arrow",
    "uncertain_elements": [],
    "confidence": 0.95,
}


@pytest.fixture(autouse=True)
def clean_cache():
    _VISION_EXTRACTION_CACHE.clear()
    yield
    _VISION_EXTRACTION_CACHE.clear()


# =========================================================================
# 1. openrouter/free absent from production candidate chain
# =========================================================================
def test_1_openrouter_free_absent_from_production_candidate_chain(monkeypatch):
    """Verify openrouter/free is never present in the production candidate chain."""
    monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")
    monkeypatch.setattr(settings, "vision_fallback_model", "google/gemma-4-31b-it:free")

    plan = _get_vision_candidate_plan()
    assert len(plan) == 2
    for candidate in plan:
        assert candidate.model != "openrouter/free"
        assert "openrouter/free" not in candidate.model

    assert plan[0].model == "inclusionai/ling-3.0-flash-vl:free"
    assert plan[0].mode == "prompt_json"
    assert plan[1].model == "google/gemma-4-31b-it:free"
    assert plan[1].mode == "json_object"

    # Even if environment inadvertently sets openrouter/free, it is strictly sanitized
    monkeypatch.setattr(settings, "vision_model", "openrouter/free")
    monkeypatch.setattr(settings, "vision_fallback_model", "openrouter/free")
    sanitized_plan = _get_vision_candidate_plan()
    for candidate in sanitized_plan:
        assert candidate.model != "openrouter/free"


# =========================================================================
# 2. Ling receives no response_format
# =========================================================================
def test_2_ling_receives_no_response_format(monkeypatch):
    """Verify Candidate 1 (Ling) receives NO response_format parameter, but explicit JSON instruction in prompt."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")
        monkeypatch.setattr(settings, "vision_fallback_model", "google/gemma-4-31b-it:free")

        captured_payloads = []

        async def mock_post(url, *args, **kwargs):
            payload = kwargs.get("json", {})
            captured_payloads.append(payload)
            return httpx.Response(
                status_code=200,
                json={
                    "id": "gen-ling",
                    "model": "inclusionai/ling-3.0-flash-vl:free",
                    "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            result = await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="test.png")

        assert isinstance(result, VisionExtractionData)
        assert len(captured_payloads) == 1
        ling_payload = captured_payloads[0]
        assert ling_payload["model"] == "inclusionai/ling-3.0-flash-vl:free"
        assert "response_format" not in ling_payload

        # Verify prompt instruction
        messages = ling_payload.get("messages", [])
        user_msg = messages[0]["content"]
        text_parts = [p.get("text", "") for p in user_msg if isinstance(p, dict) and p.get("type") == "text"]
        full_prompt = " ".join(text_parts)
        assert "Return exactly one valid JSON object matching the required extraction structure" in full_prompt

    asyncio.run(_run())


# =========================================================================
# 3. Gemma receives {"type":"json_object"}
# =========================================================================
def test_3_gemma_receives_json_object(monkeypatch):
    """Verify Candidate 2 (Gemma) receives response_format={"type": "json_object"} and no strict json_schema."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")
        monkeypatch.setattr(settings, "vision_fallback_model", "google/gemma-4-31b-it:free")

        captured_payloads = []

        async def mock_post(url, *args, **kwargs):
            payload = kwargs.get("json", {})
            captured_payloads.append(payload)
            if len(captured_payloads) == 1:
                # Ling fails with 503
                return httpx.Response(status_code=503, text='{"error": "Unavailable"}', request=httpx.Request("POST", url))
            # Gemma succeeds
            return httpx.Response(
                status_code=200,
                json={
                    "id": "gen-gemma",
                    "model": "google/gemma-4-31b-it:free",
                    "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            result = await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="test.png")

        assert isinstance(result, VisionExtractionData)
        assert len(captured_payloads) == 2
        gemma_payload = captured_payloads[1]
        assert gemma_payload["model"] == "google/gemma-4-31b-it:free"
        assert gemma_payload.get("response_format") == {"type": "json_object"}
        assert "json_schema" not in str(gemma_payload.get("response_format"))

    asyncio.run(_run())


# =========================================================================
# 4. maximum attempts == 2
# =========================================================================
def test_4_maximum_attempts_equals_two(monkeypatch):
    """Verify strictly at most 2 network attempts per image extraction."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")
        monkeypatch.setattr(settings, "vision_fallback_model", "google/gemma-4-31b-it:free")

        call_count = 0

        async def mock_post(url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(status_code=500, text='{"error": "Internal Error"}', request=httpx.Request("POST", url))

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            with pytest.raises(VisionExtractionFailed):
                await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="test.png")

        assert call_count == 2

    asyncio.run(_run())


# =========================================================================
# 5. Ling invalid JSON falls back to Gemma
# =========================================================================
def test_5_ling_invalid_json_falls_back_to_gemma(monkeypatch):
    """Verify Ling returning invalid JSON/commentary gracefully falls back to Gemma."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")
        monkeypatch.setattr(settings, "vision_fallback_model", "google/gemma-4-31b-it:free")

        captured_models = []

        async def mock_post(url, *args, **kwargs):
            payload = kwargs.get("json", {})
            captured_models.append(payload.get("model"))
            if len(captured_models) == 1:
                # Ling returns non-JSON commentary
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": "gen-ling",
                        "model": "inclusionai/ling-3.0-flash-vl:free",
                        "choices": [{"message": {"content": "Here is an explanation of the image without any JSON format!"}}],
                    },
                    request=httpx.Request("POST", url),
                )
            # Gemma returns valid JSON
            return httpx.Response(
                status_code=200,
                json={
                    "id": "gen-gemma",
                    "model": "google/gemma-4-31b-it:free",
                    "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            result = await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="test.png")

        assert isinstance(result, VisionExtractionData)
        assert captured_models == ["inclusionai/ling-3.0-flash-vl:free", "google/gemma-4-31b-it:free"]
        assert result.headings == ["Classical Mechanics"]

    asyncio.run(_run())


# =========================================================================
# 6. Ling timeout falls back to Gemma if stage budget remains
# =========================================================================
def test_6_ling_timeout_falls_back_to_gemma(monkeypatch):
    """Verify Ling timing out falls back to Gemma when sufficient stage budget remains."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")
        monkeypatch.setattr(settings, "vision_fallback_model", "google/gemma-4-31b-it:free")
        monkeypatch.setattr(settings, "vision_stage_timeout_seconds", 75.0)

        attempts = 0

        async def mock_post(url, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise httpx.ReadTimeout("Ling request timed out")
            return httpx.Response(
                status_code=200,
                json={
                    "id": "gen-gemma",
                    "model": "google/gemma-4-31b-it:free",
                    "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            result = await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="test.png")

        assert isinstance(result, VisionExtractionData)
        assert attempts == 2

    asyncio.run(_run())


# =========================================================================
# 7. Gemma success produces validated VisionExtractionData
# =========================================================================
def test_7_gemma_success_produces_validated_vision_extraction_data(monkeypatch):
    """Verify Gemma success produces a fully validated VisionExtractionData object."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "google/gemma-4-31b-it:free")
        monkeypatch.setattr(settings, "vision_fallback_model", "")

        async def mock_post(url, *args, **kwargs):
            return httpx.Response(
                status_code=200,
                json={
                    "id": "gen-gemma",
                    "model": "google/gemma-4-31b-it:free",
                    "choices": [{"message": {"content": json.dumps(VALID_EXTRACTION_JSON)}}],
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            result = await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="diagram.png")

        assert isinstance(result, VisionExtractionData)
        assert result.confidence == 0.95
        assert "Classical Mechanics" in result.headings
        assert "F = m * a" in result.formulas
        assert "Newton's Second Law of Motion: F = ma" in result.visible_text

    asyncio.run(_run())


# =========================================================================
# 8. HTTP 200 without completed body still respects timeout
# =========================================================================
def test_8_http_200_without_completed_body_respects_timeout(monkeypatch):
    """Verify HTTP 200 with hanging/broken body read aborts within timeout and does not hang."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")
        monkeypatch.setattr(settings, "vision_fallback_model", "")
        monkeypatch.setattr(settings, "vision_timeout_seconds", 0.3)
        monkeypatch.setattr(settings, "vision_stage_timeout_seconds", 0.5)

        async def mock_post(url, *args, **kwargs):
            # Simulate HTTP 200 received but socket read hanging and timing out
            await asyncio.sleep(0.05)
            raise httpx.ReadTimeout("Incomplete read of response body")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            with pytest.raises(VisionExtractionFailed) as exc_info:
                await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="diagram.png")

        assert exc_info.value.error_code == VISION_TIMEOUT

    asyncio.run(_run())


# =========================================================================
# 9. cancellation still stops actual httpx request
# =========================================================================
def test_9_cancellation_still_stops_actual_httpx_request(monkeypatch):
    """Verify cancelling the async task cleanly cancels the in-flight httpx request."""
    async def _run():
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")

        cancelled_event = asyncio.Event()

        async def hanging_post(url, *args, **kwargs):
            try:
                await asyncio.sleep(10.0)
                return httpx.Response(status_code=200, text="{}", request=httpx.Request("POST", url))
            except asyncio.CancelledError:
                cancelled_event.set()
                raise

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=hanging_post):
            task = asyncio.create_task(extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="test.png"))
            await asyncio.sleep(0.05)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

        assert cancelled_event.is_set(), "In-flight HTTP request was not cancelled!"

    asyncio.run(_run())


# =========================================================================
# 10. TXT pipeline remains unaffected
# =========================================================================
def test_10_txt_pipeline_remains_unaffected(tmp_path):
    """Verify TXT pipeline functions completely unaffected by vision candidate changes."""
    txt_content = (
        "Thermodynamics: First Law\n\n"
        "Energy cannot be created or destroyed, only transformed.\n\n"
        "Delta U = Q - W\n"
    )
    txt_file = tmp_path / "thermo.txt"
    txt_file.write_text(txt_content, encoding="utf-8")

    res = dispatch(txt_file, source_id="SRC_TXT_1", asset_id="AST_TXT_1")
    assert res.modality == "txt"
    assert len(res.units) >= 2
    assert "Thermodynamics: First Law" in res.units[0].text
    assert "Delta U = Q - W" in res.units[-1].text


# =========================================================================
# 11. qwen3:1.7b reasoning remains untouched
# =========================================================================
def test_11_qwen3_reasoning_remains_untouched():
    """Verify qwen3:1.7b local reasoning configuration is untouched and active."""
    assert settings.reasoning_model == "qwen3:1.7b"
    assert settings.embedding_model == "embeddinggemma"
    assert settings.ollama_base_url == "http://localhost:11434"


# =========================================================================
# 12. OCR fallback remains grounded
# =========================================================================
def test_12_ocr_fallback_remains_grounded(monkeypatch):
    """Verify local OCR fallback is grounded, fails closed if empty, and does not invent diagrams."""
    monkeypatch.setattr(settings, "vision_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key-chain")

    # When OpenRouter fails and OCR returns empty -> fails closed
    with patch("app.services.vision.extract_vision_openrouter") as mock_extract, \
         patch("app.services.vision._extract_ocr_vision_data", return_value=None):
        mock_extract.side_effect = VisionExtractionFailed("Upstream unavailable", error_code=VISION_TIMEOUT)
        with pytest.raises(VisionExtractionFailed):
            describe_image(SAMPLE_IMAGE_BYTES, source="empty_ocr.png")

    # When OCR returns grounded text -> accepted with 0 fabricated diagram entities
    grounded_ocr = VisionExtractionData(
        visible_text=["Newton's Law of Universal Gravitation"],
        headings=["Gravitation"],
        paragraphs=["Every particle attracts every other particle."],
        bullet_points=[],
        diagram_entities=[],
        labels=["Gravitation"],
        arrows=[],
        relationships=[],
        tables=[],
        formulas=["F = G * (m1*m2)/r^2"],
        units=["N"],
        visual_structure="Text-based document with 1 detected line",
        uncertain_elements=[],
        confidence=0.85,
    )
    with patch("app.services.vision.extract_vision_openrouter") as mock_extract, \
         patch("app.services.vision._extract_ocr_vision_data", return_value=grounded_ocr):
        mock_extract.side_effect = VisionExtractionFailed("Upstream unavailable", error_code=VISION_TIMEOUT)
        result_md = describe_image(SAMPLE_IMAGE_BYTES, source="grounded_ocr.png")
        assert "Gravitation" in result_md
        assert "Every particle attracts every other particle." in result_md
        assert "F = G * (m1*m2)/r^2" in result_md


# =========================================================================
# 13. API key never appears in logs
# =========================================================================
def test_13_api_key_never_appears_in_logs(monkeypatch, caplog):
    """Verify OPENROUTER_API_KEY is never leaked in log records during extraction or errors."""
    async def _run():
        secret_key = "sk-or-v1-super-secret-key-NEVER-LEAK-XYZ98765"
        monkeypatch.setattr(settings, "openrouter_api_key", secret_key)
        monkeypatch.setattr(settings, "vision_model", "inclusionai/ling-3.0-flash-vl:free")

        async def mock_post(url, *args, **kwargs):
            return httpx.Response(status_code=401, text='{"error": "Unauthorized"}', request=httpx.Request("POST", url))

        with caplog.at_level(logging.DEBUG):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
                with pytest.raises(VisionExtractionFailed):
                    await extract_vision_openrouter_async(SAMPLE_IMAGE_BYTES, source="secure.png")

        for record in caplog.records:
            assert secret_key not in record.message
            assert "NEVER-LEAK" not in record.message

    asyncio.run(_run())
