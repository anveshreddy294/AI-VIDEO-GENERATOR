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
    return genai.GenerativeModel(settings.generation_model)


def describe_image(image_bytes: bytes, source: str = "image") -> str:
    """Send image bytes (or a path to one) to Gemini Vision and get a caption."""
    return _generate(_DIAGRAM_PROMPT, image_bytes, source, mime_type="image/png")


def describe_frame(image_bytes: bytes, source: str = "frame") -> str:
    """Describe a lecture keyframe: equations, bullets, diagrams on the board."""
    return _generate(_FRAME_PROMPT, image_bytes, source, mime_type="image/jpeg")


def _generate(prompt: str, image_bytes: bytes, source: str, mime_type: str) -> str:
    """Shared call: prompt + base64 media -> text answer via OmniRoute or Gemini."""
    if not isinstance(image_bytes, bytes):
        raise TypeError(
            f"_generate() expects raw bytes, got {type(image_bytes).__name__}. "
            "Use describe_image_file() to pass a file path."
        )

    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    # 1. Try OmniRoute vision if configured
    if settings.llm_provider == "omniroute" and settings.omniroute_api_key:
        try:
            import json
            import urllib.request
            url = f"{settings.omniroute_base_url}/chat/completions"
            payload = json.dumps({
                "model": settings.omniroute_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
                            },
                        ],
                    }
                ],
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.omniroute_api_key}",
            }
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip()
        except Exception as exc:
            print(f"[vision] OmniRoute vision failed: {exc}. Trying Gemini fallback.")

    # 2. Try Gemini Vision if key is set
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
            print(f"[vision] Gemini vision failed: {exc}")

    return "[No description returned by vision API]"


def describe_image_file(file_path: Path) -> str:
    """Convenience wrapper for standalone image uploads."""
    with open(file_path, "rb") as fh:
        return describe_image(fh.read(), source=file_path.name)