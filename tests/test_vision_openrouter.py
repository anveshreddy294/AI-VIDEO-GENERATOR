"""Tests for OpenRouter Multimodal Vision Integration and Quality Validation."""

import base64
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

from app.core.config import settings
from app.services.schemas import VisionExtractionData
from app.services.vision import (
    VisionExtractionFailed,
    _clean_json_response,
    _detect_image_mime,
    _validate_vision_extraction,
    describe_image,
    extract_vision_openrouter,
    format_vision_markdown,
)


class TestVisionOpenRouter(unittest.TestCase):
    """Verify OpenRouter vision request formatting, validation rules, and fallbacks."""

    def setUp(self):
        self.orig_provider = getattr(settings, "vision_provider", "openrouter")
        self.orig_api_key = getattr(settings, "openrouter_api_key", "")
        self.orig_model = getattr(settings, "vision_model", "openrouter/free")
        self.orig_fallback = getattr(settings, "vision_fallback_model", "inclusionai/ling-3.0-flash-vl:free")

    def tearDown(self):
        settings.vision_provider = self.orig_provider
        settings.openrouter_api_key = self.orig_api_key
        settings.vision_model = self.orig_model
        settings.vision_fallback_model = self.orig_fallback

    def test_mime_detection_from_bytes(self):
        """Verify magic byte detection for PNG and JPEG without filesystem reliance."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        jpg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20
        self.assertEqual(_detect_image_mime(png_bytes), "image/png")
        self.assertEqual(_detect_image_mime(jpg_bytes), "image/jpeg")

    def test_validation_rejects_empty_content(self):
        """Reject extraction when response contains no extracted content."""
        empty_data = {
            "visible_text": [],
            "headings": [],
            "paragraphs": [],
            "bullet_points": [],
            "diagram_entities": [],
            "labels": [],
            "arrows": [],
            "relationships": [],
            "tables": [],
            "formulas": [],
            "units": [],
            "visual_structure": "",
        }
        with self.assertRaises(VisionExtractionFailed) as ctx:
            _validate_vision_extraction(empty_data, source="circuit.png")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_validation_rejects_filename_only(self):
        """Reject extraction when output merely reflects the filename."""
        filename_data = {
            "visible_text": ["circuit.png"],
            "headings": [],
            "paragraphs": [],
            "bullet_points": [],
            "diagram_entities": [],
            "labels": [],
            "arrows": [],
            "relationships": [],
            "tables": [],
            "formulas": [],
            "units": [],
            "visual_structure": "",
        }
        with self.assertRaises(VisionExtractionFailed) as ctx:
            _validate_vision_extraction(filename_data, source="circuit.png")
        self.assertIn("filename", str(ctx.exception).lower())

    def test_validation_rejects_generic_placeholders(self):
        """Reject extraction when output consists of generic placeholder strings."""
        placeholder_data = {
            "visible_text": [
                "Image asset for 'Original' (123 KB).",
                "Visual study reference material from uploaded media.",
            ],
            "headings": ["Uploaded Image"],
            "paragraphs": [],
            "bullet_points": [],
            "diagram_entities": [],
            "labels": [],
            "arrows": [],
            "relationships": [],
            "tables": [],
            "formulas": [],
            "units": [],
            "visual_structure": "",
        }
        with self.assertRaises(VisionExtractionFailed) as ctx:
            _validate_vision_extraction(placeholder_data, source="original.jpeg")
        self.assertIn("placeholder", str(ctx.exception).lower())

    def test_validation_accepts_valid_educational_extraction(self):
        """Accept valid structured evidence containing text and diagram relations."""
        valid_data = {
            "visible_text": ["Smart Grid Energy System", "Solar Generation: 45 kW"],
            "headings": ["Polar Station Energy Architecture"],
            "paragraphs": ["The system manages renewable sources to reduce fuel consumption."],
            "bullet_points": ["Solar panel array", "Wind turbine generator"],
            "diagram_entities": ["Solar Panels", "AI Engine", "Battery Bank"],
            "labels": ["Generation Input", "Storage"],
            "arrows": ["Solar Panels -> AI Engine", "AI Engine -> Battery Bank"],
            "relationships": ["Solar Panels -> AI Engine", "AI Engine -> Battery Bank"],
            "tables": [],
            "formulas": ["P = V * I"],
            "units": ["kW", "V"],
            "visual_structure": "Left-to-right flowchart showing energy distribution.",
            "uncertain_elements": [],
            "confidence": 0.95,
        }
        validated = _validate_vision_extraction(valid_data, source="polar_energy.png")
        self.assertIsInstance(validated, VisionExtractionData)
        self.assertEqual(validated.confidence, 0.95)
        self.assertIn("Solar Panels", validated.diagram_entities)

        # Markdown formatting check
        md = format_vision_markdown(validated)
        self.assertIn("Polar Station Energy Architecture", md)
        self.assertIn("Solar Panels -> AI Engine", md)
        self.assertIn("P = V * I", md)

    @patch("urllib.request.urlopen")
    def test_openrouter_payload_format(self, mock_urlopen):
        """Verify OpenRouter request uses Base64 data URL and prompt (never local file paths)."""
        settings.vision_provider = "openrouter"
        settings.openrouter_api_key = "test_key_12345"

        sample_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "visible_text": ["Newton's Second Law", "F = ma"],
                            "headings": ["Dynamics"],
                            "paragraphs": ["Force causes acceleration of a given mass."],
                            "bullet_points": [],
                            "diagram_entities": ["Mass Block", "Force Vector"],
                            "labels": ["F_net", "m = 2kg"],
                            "arrows": ["Left to Right"],
                            "relationships": ["Force -> Acceleration"],
                            "tables": [],
                            "formulas": ["F = ma"],
                            "units": ["N", "kg", "m/s^2"],
                            "visual_structure": "Free body diagram",
                            "uncertain_elements": [],
                            "confidence": 0.98,
                        })
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        fake_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        result = extract_vision_openrouter(fake_png_bytes, source="newton.png")

        self.assertEqual(result.confidence, 0.98)
        self.assertIn("F = ma", result.formulas)

        # Verify urllib.request.Request contents
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(req.headers.get("Authorization"), "Bearer test_key_12345")

        sent_body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(sent_body["model"], "openrouter/free")
        messages = sent_body["messages"]
        self.assertEqual(len(messages), 1)
        content_items = messages[0]["content"]
        self.assertEqual(content_items[0]["type"], "text")
        self.assertEqual(content_items[1]["type"], "image_url")
        self.assertTrue(content_items[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertNotIn("c:\\", content_items[1]["image_url"]["url"].lower())

    @patch("urllib.request.urlopen")
    def test_openrouter_fallback_on_primary_model_failure(self, mock_urlopen):
        """Verify fallback model is called when primary model endpoint returns an error."""
        settings.vision_provider = "openrouter"
        settings.openrouter_api_key = "test_key_12345"
        settings.vision_model = "openrouter/free"
        settings.vision_fallback_model = "inclusionai/ling-3.0-flash-vl:free"

        # Primary model fails (503 Service Unavailable), secondary succeeds
        err_503 = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )
        success_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "visible_text": ["Fallback Extracted Text"],
                            "headings": ["Fallback Heading"],
                            "paragraphs": [],
                            "bullet_points": [],
                            "diagram_entities": ["Node A", "Node B"],
                            "labels": [],
                            "arrows": ["Node A -> Node B"],
                            "relationships": ["Node A -> Node B"],
                            "tables": [],
                            "formulas": [],
                            "units": [],
                            "visual_structure": "Linear flowchart",
                            "uncertain_elements": [],
                            "confidence": 0.90,
                        })
                    }
                }
            ]
        }
        mock_success = MagicMock()
        mock_success.read.return_value = json.dumps(success_response).encode("utf-8")
        mock_success.__enter__.return_value = mock_success

        mock_urlopen.side_effect = [err_503, mock_success]

        fake_jpg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 64
        result = extract_vision_openrouter(fake_jpg_bytes, source="sample.jpg")

        self.assertEqual(result.headings, ["Fallback Heading"])
        self.assertEqual(mock_urlopen.call_count, 2)
        second_call_req = mock_urlopen.call_args_list[1][0][0]
        second_body = json.loads(second_call_req.data.decode("utf-8"))
        self.assertEqual(second_body["model"], "inclusionai/ling-3.0-flash-vl:free")

    @patch("urllib.request.urlopen")
    def test_openrouter_rate_limit_fails_immediately_without_fallback_loop(self, mock_urlopen):
        """Verify HTTP 429 stops immediately and does not repeatedly retry fallback models."""
        settings.vision_provider = "openrouter"
        settings.openrouter_api_key = "test_key_12345"

        err_429 = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = err_429

        fake_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        with self.assertRaises(VisionExtractionFailed) as ctx:
            extract_vision_openrouter(fake_png_bytes, source="sample.png")

        # Must have attempted the candidate models without infinite retries
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_missing_api_key_raises_vision_extraction_failed(self):
        """Verify missing OPENROUTER_API_KEY fails safely without raising uncaught errors."""
        settings.vision_provider = "openrouter"
        settings.openrouter_api_key = ""
        fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        with self.assertRaises(VisionExtractionFailed) as ctx:
            describe_image(fake_bytes, source="sample.png")
        self.assertIn("not configured", str(ctx.exception).lower())

    def test_dispatch_image_with_mock_provider(self):
        """Verify dispatching an image file produces a ContentUnit with rich evidence when provider is mock."""
        import tempfile
        settings.vision_provider = "mock"
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
            tmp_path = Path(tmp.name)

        try:
            from app.services.dispatcher import dispatch
            res = dispatch(tmp_path, source_id="SRC_test1", asset_id="AST_test1")
            self.assertEqual(res.modality, "image")
            self.assertEqual(len(res.units), 1)
            unit = res.units[0]
            self.assertTrue(unit.text.startswith(f"[IMAGE: {tmp_path.name}]"))
            self.assertIn("### Headings & Key Topics", unit.text)
            self.assertIn("### Diagram Entities & Conceptual Flow", unit.text)
            self.assertNotIn("Image asset for", unit.text)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_dispatch_image_with_failed_vision_raises_exception(self):
        """Verify dispatching an image file propagates VisionExtractionFailed when extraction fails."""
        import tempfile
        settings.vision_provider = "openrouter"
        settings.openrouter_api_key = ""  # Will trigger failure
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
            tmp_path = Path(tmp.name)

        try:
            from app.services.dispatcher import dispatch
            with self.assertRaises(VisionExtractionFailed):
                dispatch(tmp_path, source_id="SRC_test2", asset_id="AST_test2")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_dispatch_txt_regression_unaffected(self):
        """Verify TXT dispatching remains completely untouched and functional."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as tmp:
            tmp.write("Paragraph 1 on Newton's First Law.\n\nParagraph 2 on Force and Mass.")
            tmp_path = Path(tmp.name)

        try:
            from app.services.dispatcher import dispatch
            res = dispatch(tmp_path, source_id="SRC_txt", asset_id="AST_txt")
            self.assertEqual(res.modality, "txt")
            self.assertEqual(len(res.units), 2)
            self.assertIn("Newton's First Law", res.units[0].text)
            self.assertIn("Force and Mass", res.units[1].text)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_vision_model_default_and_env_override(self):
        """Verify openrouter/free is default and OPENROUTER_VISION_MODEL override works."""
        from app.core.config import Settings
        import os

        # Test canonical default
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENROUTER_VISION_MODEL", None)
            os.environ.pop("VISION_MODEL", None)
            s = Settings()
            self.assertEqual(s.vision_model, "openrouter/free")
            self.assertEqual(s.reasoning_model, "llama3.2:3b")
            self.assertEqual(s.embedding_model, "embeddinggemma")

        # Test OPENROUTER_VISION_MODEL environment override
        with patch.dict(os.environ, {"OPENROUTER_VISION_MODEL": "custom/vision-model:free"}):
            s = Settings()
            self.assertEqual(s.vision_model, "custom/vision-model:free")
            # Ensure local reasoning remains untouched
            self.assertEqual(s.reasoning_model, "llama3.2:3b")

    @patch("urllib.request.urlopen")
    def test_resolved_model_recorded_safely_in_logs(self, mock_urlopen):
        """Verify the actual routed model from OpenRouter is captured and logged safely without leaking keys."""
        settings.vision_provider = "openrouter"
        settings.openrouter_api_key = "secret_api_key_xyz999"
        settings.vision_model = "openrouter/free"

        mock_resp_data = {
            "id": "gen-12345",
            "model": "qwen/qwen-2.5-vl-72b-instruct:free",
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "visible_text": ["Diagram title: Photosynthesis"],
                            "headings": ["Photosynthesis"],
                            "paragraphs": ["Light energy is converted into chemical energy."],
                            "bullet_points": [],
                            "diagram_entities": ["Chloroplast", "Sunlight", "Water"],
                            "labels": ["Light Reaction"],
                            "arrows": ["Sunlight -> Chloroplast"],
                            "relationships": ["Water + CO2 -> Glucose + O2"],
                            "tables": [],
                            "formulas": ["6CO2 + 6H2O -> C6H12O6 + 6O2"],
                            "units": [],
                            "visual_structure": "Biochemical process flow",
                            "uncertain_elements": [],
                            "confidence": 0.95,
                        })
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with self.assertLogs("app.services.vision", level="INFO") as log_capture:
            fake_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
            res = extract_vision_openrouter(fake_png_bytes, source="bio_flow.png")
            self.assertIn("Photosynthesis", res.headings)

            log_output = " ".join(log_capture.output)
            self.assertIn("requested_model=openrouter/free", log_output)
            self.assertIn("resolved_model=qwen/qwen-2.5-vl-72b-instruct:free", log_output)
            self.assertNotIn("secret_api_key_xyz999", log_output)


if __name__ == "__main__":
    unittest.main()


