"""Validate an actual visual asset and adapt it into the existing ContentUnit."""

from __future__ import annotations
import hashlib
import io
import threading
from typing import Literal
from PIL import Image, UnidentifiedImageError
from pydantic import JsonValue, TypeAdapter
from .schemas import ContentUnit
from .vision import (
    VisionExtractionFailed,
    VISION_INVALID_RESPONSE,
    extract_vision_ollama,
    format_vision_markdown,
)
from ..core.config import settings

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_CONCURRENT_VISION = 2
_gate = threading.BoundedSemaphore(MAX_CONCURRENT_VISION)
_object = TypeAdapter(dict[str, JsonValue])


def visual_content_unit(
    image_bytes: bytes,
    *,
    source_id: str,
    asset_id: str,
    source: str,
    modality: Literal["image", "pdf"] = "image",
    page_number: int | None = None,
    visual_index: int = 0,
    bbox: list[float] | None = None,
    image_path: str | None = None,
) -> ContentUnit:
    """No fabricated locations, confidences or evidence when decode/provider fails."""
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise VisionExtractionFailed(
            "Visual asset size rejected", VISION_INVALID_RESPONSE
        )
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if (
                image.width * image.height > MAX_IMAGE_PIXELS
                or getattr(image, "n_frames", 1) != 1
            ):
                raise ValueError("Unsupported image dimensions or animation")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise VisionExtractionFailed(
            "Visual asset decode failed", VISION_INVALID_RESPONSE
        ) from None
    if settings.vision_provider not in ("ollama", "openrouter", "mock", "test"):
        raise VisionExtractionFailed("Visual provider unavailable")
    if not _gate.acquire(timeout=settings.vision_stage_timeout_seconds):
        raise VisionExtractionFailed(
            "Vision concurrency budget exceeded", "VISION_TIMEOUT"
        )
    try:
        if settings.vision_provider in ("mock", "test"):
            if settings.database_provider == "supabase":
                raise VisionExtractionFailed(
                    "Mock visual evidence cannot be canonically accepted"
                )
            from .vision import _mock_vision_extraction

            data = _mock_vision_extraction(source)
            data._actual_provider = "mock"
            data._actual_model = "mock-fixture"
        else:
            data = extract_vision_ollama(image_bytes, source=source)
    finally:
        _gate.release()
    if not data._actual_provider or not data._actual_model:
        raise VisionExtractionFailed(
            "Visual provider provenance missing", VISION_INVALID_RESPONSE
        )
    description = format_vision_markdown(data)
    if modality not in ("image", "pdf"):
        raise ValueError("Unsupported visual source modality")
    provenance: dict[str, JsonValue] = {
        "visual_schema_version": "visual-v2",
        "source_type": modality,
        "semantic_kind": data.content_kind,
        "visual_index": visual_index,
        "provider": data._actual_provider,
        "model": data._actual_model,
        "validation_state": "VALIDATED",
        "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "extraction": _object.validate_python(data.model_dump(mode="json")),
    }
    return ContentUnit(
        source_id=source_id,
        asset_id=asset_id,
        modality=modality,
        text=description,
        visual_description=description,
        page_number=page_number,
        bbox=bbox,
        sequence_index=visual_index,
        image_id=f"IMG_{visual_index}",
        image_path=image_path,
        extraction_method="vision_" + data._actual_provider,
        confidence_score=data.confidence,
        heading_path=data.headings[:8],
        provenance=provenance,
    )
