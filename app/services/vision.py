"""Multimodal Vision Engine — describes diagrams and images for the extraction engine.

Uses local Ollama multimodal API with resilient deterministic/OCR fallback.
Zero external cloud or Gemini dependency.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..core.config import settings

logger = logging.getLogger(__name__)

_DIAGRAM_PROMPT = (
    "You are an expert textbook diagram and image reader. Analyze this image:\n"
    "1. Transcribe visible text, labels, and mathematical equations exactly.\n"
    "2. Describe visual components (boxes, arrows, shapes, charts, axes, trends).\n"
    "3. Explain the scientific or educational concept depicted.\n"
    "Output only the concise factual description."
)

_FRAME_PROMPT = (
    "You are an expert lecture video frame analyzer. Analyze this frame:\n"
    "1. Transcribe visible whiteboard writing, slide text, and equations.\n"
    "2. Describe any diagrams or visual aids shown.\n"
    "3. If the frame is purely the speaker with no visual content, state 'Speaker visible, no board/slide content.'\n"
    "Output only the concise description."
)


def _generate_with_ollama(prompt: str, image_b64: str) -> str | None:
    """Attempt multimodal description via Ollama /api/generate."""
    base_url = (
        getattr(settings, "ollama_base_url", None)
        or getattr(settings, "ollama_url", "http://localhost:11434")
    ).rstrip("/")
    model_name = getattr(settings, "ollama_model", "llama3.2:3b")

    url = f"{base_url}/api/generate"
    payload = json.dumps({
        "model": model_name,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            response_text = data.get("response", "").strip()
            if response_text:
                return response_text
    except Exception as exc:
        logger.info("[vision] Ollama multimodal vision unavailable or not configured (%s)", exc)
    return None


def _extract_ocr_text(image_bytes: bytes) -> str:
    """Best-effort local OCR using tesseract CLI with contrast enhancement if installed."""
    import shutil
    import subprocess
    import tempfile
    tess = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
    if os.path.exists(tess):
        try:
            # Preprocess image with PIL to improve OCR on colored/stylized backgrounds
            try:
                import io
                from PIL import Image, ImageEnhance
                pil_img = Image.open(io.BytesIO(image_bytes)).convert("L")
                enh = ImageEnhance.Contrast(pil_img).enhance(2.5)
                buf = io.BytesIO()
                enh.save(buf, format="PNG")
                processed_bytes = buf.getvalue()
            except Exception:
                processed_bytes = image_bytes

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(processed_bytes)
                tmp_path = tmp.name

            detected_words: list[str] = []
            for psm in ("6", "11"):
                res = subprocess.run(
                    [tess, tmp_path, "stdout", "--psm", psm],
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                )
                raw_ocr = res.stdout.strip()
                lines = [l.strip() for l in raw_ocr.splitlines() if len(l.strip()) >= 2]
                for line in lines:
                    for w in line.split():
                        cleaned_w = "".join(ch for ch in w if ch.isalnum() or ch in "-_")
                        if len(cleaned_w) >= 3 and cleaned_w.lower() not in [x.lower() for x in detected_words]:
                            detected_words.append(cleaned_w)

            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            if detected_words:
                return " ".join(detected_words)
        except Exception:
            pass
    return ""


def describe_image(image_bytes: bytes, source: str = "image") -> str:
    """Analyze diagram or document image bytes using model_manager with fallback."""
    if not isinstance(image_bytes, bytes):
        raise TypeError(f"describe_image expects raw bytes, got {type(image_bytes).__name__}")

    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    # 1. Try model_manager with active model and fallback chain
    try:
        from ..core.model_manager import model_manager
        # Only query model if active model or fallback model has vision capability
        available_models = model_manager.get_available_models()
        has_vision = any(m.get("supports_vision") and m.get("provider") == "ollama" for m in available_models)
        if has_vision:
            res, model_used = model_manager.generate_with_fallback(
                _DIAGRAM_PROMPT,
                images=[b64_data],
                is_json=False,
                timeout=15.0,
            )
            if res and res.strip() and not res.startswith("Textbook diagram/figure") and not res.strip().startswith("{"):
                return res.strip()
    except Exception as exc:
        logger.info("[vision] Model fallback chain could not describe image (%s)", exc)

    # 2. Try OCR transcription if available
    ocr_text = _extract_ocr_text(image_bytes)
    if ocr_text:
        return f"Image asset '{source}' with visible text: {ocr_text}"

    # 3. Resilient grounded fallback based strictly on source identity
    size_kb = max(1, len(image_bytes) // 1024)
    clean_src = Path(source).stem.replace("_", " ").title() if source else "Visual Asset"
    return f"Image asset for '{clean_src}' ({size_kb} KB). Visual study reference material from uploaded media."


def describe_frame(image_bytes: bytes, source: str = "frame") -> str:
    """Analyze lecture video keyframe bytes using model_manager with fallback."""
    if not isinstance(image_bytes, bytes):
        raise TypeError(f"describe_frame expects raw bytes, got {type(image_bytes).__name__}")

    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    # 1. Try model_manager with active model and fallback chain
    try:
        from ..core.model_manager import model_manager
        res, model_used = model_manager.generate_with_fallback(
            _FRAME_PROMPT,
            images=[b64_data],
            is_json=False,
            timeout=15.0,
        )
        if res and res.strip():
            return res.strip()
    except Exception as exc:
        logger.info("[vision] Model fallback chain could not describe frame (%s)", exc)

    # 2. Try OCR transcription
    ocr_text = _extract_ocr_text(image_bytes)
    if ocr_text:
        return f"Lecture video keyframe {source} with visible board text: {ocr_text}"

    return f"Lecture video keyframe {source}: visual board contents and instructional notes."



def describe_image_file(file_path: Path) -> str:
    """Convenience wrapper for standalone image uploads."""
    with open(file_path, "rb") as fh:
        return describe_image(fh.read(), source=file_path.name)
