"""Test suite for Vision Extraction 90-Second Guarantee, Bounded Retries, and Fail-Closed Behavior.

Covers Scenarios:
A. Provider never returns (socket/connection hang -> VISION_TIMEOUT within stage budget)
B. Slow trickle response (exceeds deadline during streaming -> VISION_TIMEOUT within stage budget)
C. Primary returns HTTP 429 -> clean bounded fallback
D. Primary fails and fallback succeeds -> bounded fallback success
E. Primary and fallback both timeout -> bounded to 2 attempts, fails with VISION_TIMEOUT within stage budget
F. Malformed response -> fails closed with VISION_INVALID_RESPONSE
G. In-memory cache -> 0 network calls on repeated extraction of same image
H. Zero silent mock fallback -> VISION_PROVIDER=openrouter never falls through to mock extraction
"""

import hashlib
import json
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

from app.core.config import settings
from app.services.schemas import VisionExtractionData
from app.services.vision import (
    VISION_AUTH_FAILED,
    VISION_CACHE_SCHEMA_VERSION,
    VISION_INVALID_RESPONSE,
    VISION_PROMPT_VERSION,
    VISION_PROVIDER_FAILED,
    VISION_RATE_LIMIT,
    VISION_TIMEOUT,
    _VISION_EXTRACTION_CACHE,
    VisionExtractionFailed,
    describe_image,
    extract_vision_openrouter,
)


def _build_valid_payload():
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
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
                    })
                }
            }
        ],
        "model": "qwen/qwen-2.5-vl-72b-instruct:free",
    }


class TestVisionTimeoutRuntime(unittest.TestCase):
    """Verify two-layer timeouts, error classifications, bounded retries, and cache behavior."""

    def setUp(self):
        self.orig_provider = getattr(settings, "vision_provider", "openrouter")
        self.orig_api_key = getattr(settings, "openrouter_api_key", "")
        self.orig_model = getattr(settings, "vision_model", "openrouter/free")
        self.orig_fallback = getattr(settings, "vision_fallback_model", "inclusionai/ling-3.0-flash-vl:free")
        self.orig_timeout = getattr(settings, "vision_timeout_seconds", 60.0)
        self.orig_stage_timeout = getattr(settings, "vision_stage_timeout_seconds", 90.0)
        self.orig_extraction_timeout = getattr(settings, "extraction_stage_timeout_seconds", 100.0)

        settings.vision_provider = "openrouter"
        settings.openrouter_api_key = "test_openrouter_api_key_valid"
        settings.vision_model = "openrouter/free"
        settings.vision_fallback_model = "inclusionai/ling-3.0-flash-vl:free"

        # Clear in-memory vision cache before each test
        _VISION_EXTRACTION_CACHE.clear()

    def tearDown(self):
        settings.vision_provider = self.orig_provider
        settings.openrouter_api_key = self.orig_api_key
        settings.vision_model = self.orig_model
        settings.vision_fallback_model = self.orig_fallback
        settings.vision_timeout_seconds = self.orig_timeout
        settings.vision_stage_timeout_seconds = self.orig_stage_timeout
        settings.extraction_stage_timeout_seconds = self.orig_extraction_timeout
        _VISION_EXTRACTION_CACHE.clear()

    @patch("urllib.request.urlopen")
    def test_scenario_a_provider_never_returns_bounded_timeout(self, mock_urlopen):
        """Scenario A: Provider never returns (hangs); aborts within configured deadline with VISION_TIMEOUT."""
        settings.vision_stage_timeout_seconds = 0.3
        settings.vision_timeout_seconds = 0.2

        def hanging_urlopen(*args, **kwargs):
            time.sleep(0.35)
            raise TimeoutError("Simulated socket timeout")

        mock_urlopen.side_effect = hanging_urlopen
        sample_img = b"\xff\xd8\xff\xe0" + b"\x00" * 32

        t_start = time.monotonic()
        with self.assertRaises(VisionExtractionFailed) as ctx:
            extract_vision_openrouter(sample_img, source="diagram_hang.jpg")
        elapsed = time.monotonic() - t_start

        self.assertEqual(ctx.exception.error_code, VISION_TIMEOUT)
        self.assertLess(elapsed, 1.5, "Stage must not hang indefinitely; should terminate within bounded budget")

    @patch("urllib.request.urlopen")
    def test_scenario_b_slow_trickle_deadline_enforced(self, mock_urlopen):
        """Scenario B: Provider connection succeeds but trickle read exceeds monotonic deadline."""
        settings.vision_stage_timeout_seconds = 0.25
        settings.vision_timeout_seconds = 0.2

        class SlowTrickleResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                time.sleep(0.3)
                return json.dumps(_build_valid_payload()).encode("utf-8")

        mock_urlopen.return_value = SlowTrickleResponse()
        sample_img = b"\xff\xd8\xff\xe0" + b"\x00" * 32

        with self.assertRaises(VisionExtractionFailed) as ctx:
            extract_vision_openrouter(sample_img, source="diagram_slow.jpg")

        self.assertEqual(ctx.exception.error_code, VISION_TIMEOUT)

    @patch("urllib.request.urlopen")
    def test_scenario_c_primary_429_clean_bounded_fallback(self, mock_urlopen):
        """Scenario C: Primary returns HTTP 429 rate limit; bounded fallback is invoked and succeeds."""
        err_429 = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )

        mock_success = MagicMock()
        mock_success.read.return_value = json.dumps(_build_valid_payload()).encode("utf-8")
        mock_success.__enter__.return_value = mock_success

        mock_urlopen.side_effect = [err_429, mock_success]
        sample_img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

        result = extract_vision_openrouter(sample_img, source="diagram_ratelimit.png")

        self.assertIsInstance(result, VisionExtractionData)
        self.assertEqual(mock_urlopen.call_count, 2, "Must attempt primary then fallback (bounded 2 attempts)")
        self.assertEqual(result.visible_text[0], "Newton's Second Law of Motion: F = ma")

    @patch("urllib.request.urlopen")
    def test_scenario_d_primary_fails_fallback_succeeds(self, mock_urlopen):
        """Scenario D: Primary model returns 503; secondary fallback succeeds."""
        err_503 = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )

        mock_success = MagicMock()
        mock_success.read.return_value = json.dumps(_build_valid_payload()).encode("utf-8")
        mock_success.__enter__.return_value = mock_success

        mock_urlopen.side_effect = [err_503, mock_success]
        sample_img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

        result = extract_vision_openrouter(sample_img, source="diagram_fallback.png")

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(result.confidence, 0.95)

    @patch("urllib.request.urlopen")
    def test_scenario_e_primary_and_fallback_both_timeout(self, mock_urlopen):
        """Scenario E: Both candidate models timeout; terminates with VISION_TIMEOUT and strictly at most 2 attempts."""
        settings.vision_stage_timeout_seconds = 0.5
        settings.vision_timeout_seconds = 0.2

        def timeout_urlopen(*args, **kwargs):
            time.sleep(0.15)
            raise urllib.error.URLError("Connection timed out")

        mock_urlopen.side_effect = timeout_urlopen
        sample_img = b"\xff\xd8\xff\xe0" + b"\x00" * 32

        with self.assertRaises(VisionExtractionFailed) as ctx:
            extract_vision_openrouter(sample_img, source="double_timeout.jpg")

        self.assertEqual(ctx.exception.error_code, VISION_TIMEOUT)
        self.assertLessEqual(mock_urlopen.call_count, 2, "Must not retry recursively beyond candidate models")

    @patch("urllib.request.urlopen")
    def test_scenario_f_malformed_response_fails_closed(self, mock_urlopen):
        """Scenario F: Model returns malformed JSON or ungrounded gibberish; fails closed with VISION_INVALID_RESPONSE."""
        malformed_response = {
            "choices": [
                {
                    "message": {
                        "content": "Not valid JSON at all! Just raw rambling text with no schema."
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(malformed_response).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        sample_img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

        with self.assertRaises(VisionExtractionFailed) as ctx:
            extract_vision_openrouter(sample_img, source="corrupt.png")

        self.assertEqual(ctx.exception.error_code, VISION_INVALID_RESPONSE)

    @patch("urllib.request.urlopen")
    def test_scenario_g_in_memory_cache_zero_network_calls_on_repeat(self, mock_urlopen):
        """Scenario G: Cache test proving repeated extraction of same image causes 0 network calls after first success."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(_build_valid_payload()).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        sample_img = b"\x89PNG\r\n\x1a\n" + b"\xca\xfe\xba\xbe" * 16

        # 1. First extraction triggers network call
        first_res = extract_vision_openrouter(sample_img, source="cache_test.png")
        self.assertEqual(mock_urlopen.call_count, 1)

        # 2. Second extraction of same image must hit in-memory cache with ZERO network calls
        second_res = extract_vision_openrouter(sample_img, source="cache_test.png")
        self.assertEqual(mock_urlopen.call_count, 1, "Cache hit must make exactly 0 additional network calls")

        # 3. Third extraction via describe_image also 0 network calls
        third_res_md = describe_image(sample_img, source="cache_test.png")
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertIn("Classical Mechanics", third_res_md)

        # Verify cache key structure
        image_sha = hashlib.sha256(sample_img).hexdigest()
        expected_key = f"{image_sha}:{settings.vision_model}:{VISION_PROMPT_VERSION}:{VISION_CACHE_SCHEMA_VERSION}"
        self.assertIn(expected_key, _VISION_EXTRACTION_CACHE)

    @patch("app.services.vision._mock_vision_extraction")
    @patch("urllib.request.urlopen")
    def test_scenario_h_zero_mock_fallback_in_production(self, mock_urlopen, mock_mock_extract):
        """Scenario H: Proving VISION_PROVIDER=openrouter can NEVER silently fall back to mock extraction."""
        settings.vision_provider = "openrouter"
        # Simulate network failure
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        sample_img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

        with self.assertRaises(VisionExtractionFailed):
            describe_image(sample_img, source="real_production_doc.png")

        # Ensure mock extractor was NEVER called
        mock_mock_extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
