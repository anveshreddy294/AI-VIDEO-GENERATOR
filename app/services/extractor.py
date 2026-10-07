"""PDF extraction engine returning normalized ContentUnits.

Extracts text blocks and embedded image diagrams page-by-page, capturing
page numbers, bounding boxes, visual descriptions, and confidence scores.
"""

import logging
from pathlib import Path
from typing import TypedDict

import pymupdf as fitz

from ..core.config import settings
from .schemas import ContentUnit
from .vision import describe_image

logger = logging.getLogger(__name__)
PDF_MAX_VISION_CALLS = 25
PDF_MIN_VISUAL_PIXELS = 50
PDF_RENDER_SCALE = 2.0


def extract_from_pdf(
    pdf_path: Path, source_id: str, asset_id: str
) -> list[ContentUnit]:
    """Read text first; call vision only for actual page images or scanned drawings."""
    from .modality import visual_extraction_required
    from .vision import VisionExtractionFailed

    units: list[ContentUnit] = []
    calls = 0
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            has_text = False
            for block in page.get_text("blocks"):
                if block[6] != 0 or not block[4].strip():
                    continue
                has_text = True
                units.append(
                    ContentUnit(
                        source_id=source_id,
                        asset_id=asset_id,
                        modality="pdf",
                        text=block[4].strip(),
                        page_number=page_number,
                        sequence_index=len(units),
                        bbox=[float(value) for value in block[:4]],
                        extraction_method="pymupdf_block",
                        confidence_score=1.0,
                    )
                )
            images = _extract_page_images_with_info(page, page_number)
            scanned = not has_text and bool(
                images or page.get_images(full=True) or page.get_drawings()
            )
            if not visual_extraction_required(
                "pdf", has_text=has_text, has_visual_content=bool(images)
            ):
                continue
            # Blank pages are not scanned evidence. Never manufacture diagram placeholders.
            if not images and not scanned:
                continue
            visual_inputs: list[PageImage] = (
                [{"bytes": _render_page(page), "bbox": None, "xref": 0}]
                if scanned
                else images
            )
            for image in visual_inputs:
                if calls >= PDF_MAX_VISION_CALLS:
                    raise VisionExtractionFailed(
                        "PDF visual extraction budget exceeded"
                    )
                calls += 1
                image_id = f"IMG_{page_number}_{image['xref']}"
                images_dir = settings.upload_dir / source_id / "images"
                images_dir.mkdir(parents=True, exist_ok=True)
                image_path = images_dir / (image_id + ".png")
                image_path.write_bytes(image["bytes"])
                from .visual_evidence import visual_content_unit
                from .visual_router import VisualSignals
                from .visual_verifier import SourceAnchor, VisualSourceContext
                import hashlib

                # Native parser text is independently scoped to this exact page/region.
                anchor_text = page.get_text("text", clip=fitz.Rect(image["bbox"]) if image["bbox"] else page.rect).strip()
                anchor_context = VisualSourceContext(source_id=source_id, asset_id=asset_id,
                    image_sha256=hashlib.sha256(image["bytes"]).hexdigest(), page_number=page_number,
                    bbox=tuple(float(v) for v in image["bbox"]) if image["bbox"] else None)
                source_anchors = (SourceAnchor(origin="pdf_native", context=anchor_context, text=anchor_text),) if anchor_text else ()

                unit = visual_content_unit(
                    image["bytes"],
                    source_id=source_id,
                    asset_id=asset_id,
                    source=f"{pdf_path.name} p.{page_number}",
                    modality="pdf",
                    page_number=page_number,
                    source_anchors=source_anchors,
                    visual_index=calls - 1,
                    bbox=image["bbox"],
                    image_path=str(image_path),
                    routing_signals=VisualSignals(visual_region_count=len(visual_inputs),native_pdf_text=has_text),
                )
                unit.sequence_index = len(units)
                if unit.bbox:
                    unit.provenance["normalized_bbox"] = [
                        unit.bbox[0] / page.rect.width,
                        unit.bbox[1] / page.rect.height,
                        unit.bbox[2] / page.rect.width,
                        unit.bbox[3] / page.rect.height,
                    ]
                units.append(unit)
    return units


class PageImage(TypedDict):
    """Embedded image bytes and their page provenance."""

    xref: int
    bytes: bytes
    bbox: list[float] | None


def _extract_page_images_with_info(
    page: fitz.Page, page_number: int
) -> list[PageImage]:
    """Extract embedded images with xref and bounding box info."""
    results: list[PageImage] = []
    seen: set[int] = set()

    for image_info in page.get_images(full=True):
        from .visual_evidence import MAX_IMAGE_PIXELS
        from .vision import VisionExtractionFailed

        if image_info[2] * image_info[3] > MAX_IMAGE_PIXELS:
            raise VisionExtractionFailed("PDF image pixel budget exceeded")
        xref = image_info[0]
        if xref in seen:
            continue
        seen.add(xref)

        img_bytes = _try_extract_image(page, xref, page_number)
        if img_bytes is not None:
            bbox = None
            try:
                rects = page.get_image_rects(xref)
                if rects:
                    r = rects[0]
                    bbox = [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]
            except Exception as exc:
                logger.debug(
                    "[extractor] Could not get image rect for xref %s: %s", xref, exc
                )

            if len(results) >= PDF_MAX_VISION_CALLS:
                from .vision import VisionExtractionFailed

                raise VisionExtractionFailed("PDF visual extraction budget exceeded")
            results.append({"xref": xref, "bytes": img_bytes, "bbox": bbox})

    return results


def _try_extract_image(page: fitz.Page, xref: int, page_number: int) -> bytes | None:
    try:
        pix = fitz.Pixmap(page.parent, xref)
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)
        elif pix.colorspace and pix.colorspace.n > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        if pix.width < PDF_MIN_VISUAL_PIXELS or pix.height < PDF_MIN_VISUAL_PIXELS:
            return None
        png = pix.tobytes("png")
        return png
    except Exception as exc:
        from .vision import VisionExtractionFailed

        raise VisionExtractionFailed("Required PDF image could not be decoded") from exc


def _render_page(page: fitz.Page) -> bytes:
    from .visual_evidence import MAX_IMAGE_PIXELS
    from .vision import VisionExtractionFailed

    if page.rect.width * page.rect.height * PDF_RENDER_SCALE**2 > MAX_IMAGE_PIXELS:
        raise VisionExtractionFailed("PDF page pixel budget exceeded")
    mat = fitz.Matrix(PDF_RENDER_SCALE, PDF_RENDER_SCALE)
    pix = page.get_pixmap(matrix=mat)
    png = pix.tobytes("png")
    return png
