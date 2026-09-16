"""Gemini Vision API — describes diagrams and images for the extraction engine.

Both PDF-embedded images (raw bytes) and standalone image uploads (file path)
flow through `describe_image`. The prompt forces a strict, structured read of
*labels and relationships* so downstream chunking keeps the diagram's meaning.
"""

import base64
from pathlib import Path

import google.generativeai as genai

from ..core.config import settings

_DIAGRAM_PROMPT = (
    "You are a textbook diagram reader. Describe this image/diagram precisely "
    "as plain text that captures EVERY label, every relationship between the "
    "parts, and the flow/process it represents. If there is a title, caption, "
    "axis labels, or numbered callouts, transcribe them exactly. Do not add "
    "information that is not in the image. Output only the description."
)

_FRAME_PROMPT = (
    "You are analyzing a single frame from a recorded lecture video. "
    "Describe any equations, bullet points, or diagrams visible in this frame, "
    "and transcribe any legible text exactly as written. If the frame shows "
    "only the speaker with no board or slide content, say so in one short "
    "sentence. Do not add information that is not visible. Output only the description."
)


def _client() -> genai.GenerativeModel:
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.generation_model)


def describe_image(image_bytes: bytes, source: str = "image") -> str:
    """Send image bytes (or a path to one) to Gemini Vision and get a caption."""
    return _generate(_DIAGRAM_PROMPT, image_bytes, source, mime_type="image/png")


def describe_frame(image_bytes: bytes, source: str = "frame") -> str:
    """Describe a lecture keyframe: equations, bullets, diagrams on the board."""
    return _generate(_FRAME_PROMPT, image_bytes, source, mime_type="image/jpeg")


def _generate(prompt: str, image_bytes: bytes, source: str, mime_type: str) -> str:
    """Shared call: prompt + base64 media -> the model's text answer."""
    model = _client()

    if not isinstance(image_bytes, bytes):
        raise TypeError(
            f"_generate() expects raw bytes, got {type(image_bytes).__name__}. "
            "Use describe_image_file() to pass a file path."
        )
    media = {
        "mime_type": mime_type,
        "data": base64.b64encode(image_bytes).decode("utf-8"),
    }

    response = model.generate_content([prompt, media])
    text = (response.text or "").strip()
    if not text:
        print(f"[warn] vision returned empty description for {source}")
        return "[No description returned by vision API]"
    return text


def describe_image_file(file_path: Path) -> str:
    """Convenience wrapper for standalone image uploads."""
    with open(file_path, "rb") as fh:
        return describe_image(fh.read(), source=file_path.name)