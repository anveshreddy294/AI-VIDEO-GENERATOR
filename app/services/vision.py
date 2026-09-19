"""Gemini Vision API — describes diagrams and images for the extraction engine.

Both PDF-embedded images (raw bytes) and standalone image uploads (file path)
flow through `describe_image`. The prompt forces a strict, structured read of
*labels and relationships* so downstream chunking keeps the diagram's meaning.
"""

import base64
import logging
from pathlib import Path

import google.generativeai as genai

from ..core.config import settings

logger = logging.getLogger(__name__)

_DIAGRAM_PROMPT = (
    "You are an expert textbook diagram and image reader with perfect visual "
    "recognition. Analyze this image with extreme precision:\n"
    "1. Transcribe ALL text exactly as written — every label, title, caption, "
    "axis label, equation, number, and callout. Preserve spelling and formatting.\n"
    "2. Describe ALL visual elements — shapes, arrows, lines, colors, symbols, "
    "graphs, charts, tables, and their spatial relationships.\n"
    "3. Explain the flow, process, or concept the diagram represents.\n"
    "4. If it contains a graph or chart, describe the axes, data points, and trends.\n"
    "5. If it contains equations, write them out exactly with all notation.\n"
    "Output ONLY the description. Do NOT add information not present in the image."
)

_FRAME_PROMPT = (
    "You are an expert lecture frame analyzer with perfect visual recognition. "
    "Analyze this single frame from a recorded lecture video with extreme precision:\n"
    "1. Transcribe ALL text visible — whiteboard writing, slide text, subtitles, "
    "equations, bullet points. Preserve exact spelling and formatting.\n"
    "2. Describe ALL diagrams, charts, figures, and visual aids with their labels.\n"
    "3. If equations are shown, write them out with full mathematical notation.\n"
    "4. Describe the speaker's actions if relevant (pointing at something, writing).\n"
    "5. If the frame shows only the speaker with no content, say: "
    "'Speaker visible, no board/slide content.'\n"
    "Output ONLY the description. Do NOT add information not visible in the frame."
)


def _client() -> genai.GenerativeModel:
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    model_name = settings.generation_model if "gemini" in settings.generation_model.lower() else "gemini-3.5-flash-lite"
    return genai.GenerativeModel(model_name)


def describe_image(image_bytes: bytes, source: str = "image") -> str:
    """Send image bytes (or a path to one) to Gemini Vision and get a caption."""
    mime_type = "image/jpeg" if image_bytes.startswith(b"\xff\xd8\xff") else "image/png"
    return _generate(_DIAGRAM_PROMPT, image_bytes, source, mime_type=mime_type)


def describe_frame(image_bytes: bytes, source: str = "frame") -> str:
    """Describe a lecture keyframe: equations, bullets, diagrams on the board."""
    return _generate(_FRAME_PROMPT, image_bytes, source, mime_type="image/jpeg")


def _generate(prompt: str, image_bytes: bytes, source: str, mime_type: str) -> str:
    """Shared call: prompt + base64 media -> text answer via Gemini Vision."""
    if not isinstance(image_bytes, bytes):
        raise TypeError(
            f"_generate() expects raw bytes, got {type(image_bytes).__name__}. "
            "Use describe_image_file() to pass a file path."
        )

    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    # Call Gemini Vision if key is set
    if settings.gemini_api_key:
        try:
            model = _client()
            media = {
                "mime_type": mime_type,
                "data": b64_data,
            }
            response = model.generate_content([prompt, media])
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("[vision] Gemini vision analysis failed for '%s': %s", source, exc)

    raise RuntimeError(f"Vision extraction unavailable or empty for {source}")


def describe_image_file(file_path: Path) -> str:
    """Convenience wrapper for standalone image uploads."""
    with open(file_path, "rb") as fh:
        return describe_image(fh.read(), source=file_path.name)
