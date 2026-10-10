"""Validate an actual visual asset and adapt it into the existing ContentUnit."""

from __future__ import annotations
from contextlib import contextmanager
from collections.abc import Iterator
import logging
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
    safe_vision_error_code,
    VISION_INVALID_RESPONSE,
    extract_vision_ollama,
    format_vision_markdown,
)
from ..core.config import settings

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_CONCURRENT_VISION = max(1, settings.cloudflare_max_concurrency)
_gate = threading.BoundedSemaphore(MAX_CONCURRENT_VISION)
_object = TypeAdapter(dict[str, JsonValue])


logger = logging.getLogger(__name__)


@contextmanager
def _extraction_diagnostics(source_id: str) -> Iterator[None]:
    """Log fixed extraction classifications without exception text or image/source contents."""
    try:
        yield
    except VisionExtractionFailed as error:
        if not isinstance(error, VisualVerificationFailed):
            fields: dict[str, JsonValue] = {"source_id": source_id, "stage": "EXTRACTION",
                      "vision_error_code": safe_vision_error_code(error.error_code)}
            if settings.vision_provider in {"cloudflare", "auto", "ollama", "mock", "test"}:
                fields["provider_route"] = settings.vision_provider
            if error.route_trace is not None:
                fields.update(error.route_trace.model_dump(mode="json"))
            logger.warning("VISUAL_EXTRACTION_FAILED", extra=fields)
        raise


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
    deadline: float | None = None,
) -> ContentUnit:
    """No fabricated locations, confidences or evidence when decode/provider fails."""
    with _extraction_diagnostics(source_id):
        from .ingestion.progress import report
        report("PREPARING_IMAGE")
        from ..core.inference_budget import effective_deadline
        stage_deadline = effective_deadline(min(deadline or float("inf"), time.monotonic() + settings.vision_stage_timeout_seconds))
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
        if settings.vision_provider not in ("cloudflare", "auto", "ollama", "mock", "test"):
            raise VisionExtractionFailed("Visual provider unavailable")
        if not _gate.acquire(timeout=max(0.0, min(settings.vision_stage_timeout_seconds, stage_deadline - time.monotonic()))):
            raise VisionExtractionFailed(
                "Vision concurrency budget exceeded", "VISION_TIMEOUT"
            )
        try:
            report("UNDERSTANDING_IMAGE")
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
                data = get_visual_router().extract(image_bytes, source, routing_signals, deadline=stage_deadline)
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
        from .visual_publication import remove_chrome, verified_subset
        data, chrome_removed = remove_chrome(data)
        context = VisualSourceContext(source_id=source_id, asset_id=asset_id,
            image_sha256=hashlib.sha256(image_bytes).hexdigest(), page_number=page_number,
            bbox=tuple(bbox) if bbox is not None else None)
        report("VALIDATING_VISUAL_EVIDENCE")
        from .independent_visual_verifier import configured_visual_verifier
        verification = (verifier or configured_visual_verifier(deadline=stage_deadline)).verify(image_bytes, data, context=context, anchors=source_anchors)
        from .visual_verifier import verification_summary
        original_summary = verification_summary(verification)
        original_verification = verification.model_dump(mode="json")
        logger.info("VISUAL_VERIFICATION_RESULT %s", original_summary)
        subset_used = False
        if verification.status != "VERIFIED":
            subset = verified_subset(data, verification)
            if subset is None:
                raise VisualVerificationFailed(verification)
            data, verification = subset
            subset_used = True
        description = format_vision_markdown(data)
        if modality not in ("image", "pdf"):
            raise ValueError("Unsupported visual source modality")
        provenance: dict[str, JsonValue] = {
            "publication_policy": "independent-verified-subset-v1" if subset_used else "whole-extraction-v1",
            "original_verification_summary": _object.validate_python(original_summary),
            "unpublished_visual_verification": _object.validate_python(original_verification) if subset_used else None,
            "chrome_claims_excluded": chrome_removed,
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
            "confidence_status": data._routing_provenance.get("confidence_status", "reported" if data.confidence > 0 else "unreported"),
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


def visual_content_units(image_bytes: bytes, *, source_id: str, asset_id: str,
                         source: str, image_path: str,
                         routing_signals: VisualSignals | None = None) -> list[ContentUnit]:
    """Process only high-certainty stacked slide regions; ambiguous images stay whole."""
    from .visual_regions import slide_regions
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise VisionExtractionFailed("Visual asset size rejected", VISION_INVALID_RESPONSE)
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Unsupported image dimensions")
            image.verify()
        regions = slide_regions(image_bytes)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise VisionExtractionFailed("Visual asset decode failed", VISION_INVALID_RESPONSE) from None
    if not regions:
        return [visual_content_unit(image_bytes, source_id=source_id, asset_id=asset_id,
                source=source, image_path=image_path, routing_signals=routing_signals)]
    deadline = time.monotonic() + settings.vision_stage_timeout_seconds
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    from .visual_regions import VisualRegion, MAX_REGION_PARALLELISM
    def process(item: tuple[int, VisualRegion]) -> ContentUnit:
        index, region = item
        unit = visual_content_unit(region.image, source_id=source_id, asset_id=asset_id,
            source=source, image_path=image_path, visual_index=index,
            bbox=list(region.bbox), routing_signals=routing_signals, deadline=deadline)
        unit.provenance.update(original_image_sha256=hashlib.sha256(image_bytes).hexdigest(),
                               region_policy="repeated-panel-boundaries-v2", region_count=len(regions))
        return unit
    # Independently scoped regions share the existing deadline and extraction
    # semaphore. Context copies preserve authenticated cache scope and progress.
    with ThreadPoolExecutor(max_workers=MAX_REGION_PARALLELISM, thread_name_prefix="visual-region") as pool:
        futures = [pool.submit(copy_context().run, process, item) for item in enumerate(regions)]
        return [future.result() for future in futures]
