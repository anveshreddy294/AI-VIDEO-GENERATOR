"""Validate an actual visual asset and adapt it into the existing ContentUnit."""

from __future__ import annotations
import hashlib
import io
import threading
import time
from typing import Literal, TYPE_CHECKING
if TYPE_CHECKING:
    from .visual_router import VisualSignals
from PIL import Image, UnidentifiedImageError
from pydantic import JsonValue, TypeAdapter
from .schemas import ContentUnit
from .visual_verifier import SourceAnchor, VisualSourceContext, VisualEvidenceVerifier, VisualVerificationFailed
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
    routing_signals: VisualSignals | None = None,
    source_anchors: tuple[SourceAnchor, ...] = (),
    verifier: VisualEvidenceVerifier | None = None,
) -> ContentUnit:
    """No fabricated locations, confidences or evidence when decode/provider fails."""
    preprocess_started = time.perf_counter()
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
    preprocessing_ms = (time.perf_counter()-preprocess_started)*1000
    if settings.vision_provider not in ("cloudflare", "auto", "ollama", "openrouter", "mock", "test"):
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
        elif settings.vision_provider in ("cloudflare", "auto"):
            from .visual_router import get_visual_router
            data = get_visual_router().extract(image_bytes, source, routing_signals)
        else:
            started = time.perf_counter()
            data = extract_vision_ollama(image_bytes, source=source)
            data._routing_provenance = data._routing_provenance or {"provider_requested":"ollama", "provider_used":data._actual_provider,
                "model_requested":settings.vision_model, "actual_model_used":data._actual_model,
                "fallback_used":False, "fallback_reason":None, "attempt_count":1,
                "provider_latency_ms":(time.perf_counter()-started)*1000, "explicit_local_mode":True}
    finally:
        _gate.release()
    if not data._actual_provider or not data._actual_model:
        raise VisionExtractionFailed(
            "Visual provider provenance missing", VISION_INVALID_RESPONSE
        )
    data._routing_provenance["image_preprocessing_ms"] = float(data._routing_provenance.get("image_preprocessing_ms", 0.0)) + preprocessing_ms
    context = VisualSourceContext(source_id=source_id, asset_id=asset_id,
        image_sha256=hashlib.sha256(image_bytes).hexdigest(), page_number=page_number,
        bbox=tuple(bbox) if bbox is not None else None)
    from .independent_visual_verifier import configured_visual_verifier
    verification = (verifier or configured_visual_verifier()).verify(image_bytes, data, context=context, anchors=source_anchors)
    if verification.status != "VERIFIED":
        raise VisualVerificationFailed(verification)
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
        "visual_verification": _object.validate_python(verification.model_dump(mode="json")),
        "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "extraction": _object.validate_python(data.model_dump(mode="json")),
        "routing": data._routing_provenance,
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
