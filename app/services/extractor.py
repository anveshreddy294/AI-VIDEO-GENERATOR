"""PDF extraction engine returning normalized ContentUnits.

Extracts text blocks and embedded image diagrams page-by-page, capturing
page numbers, bounding boxes, visual descriptions, and confidence scores.
"""

import logging
from pathlib import Path

import pymupdf as fitz

from ..core.config import settings
from .schemas import ContentUnit
from .vision import describe_image

logger = logging.getLogger(__name__)


def extract_from_pdf(
    pdf_path: Path, source_id: str, asset_id: str
) -> list[ContentUnit]:
    """Extract page-level ContentUnits from a PDF file."""
    doc = fitz.open(pdf_path)
    units: list[ContentUnit] = []
    seq_index = 0

    images_dir = settings.upload_dir / source_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    vision_calls_count = 0
    max_vision_budget = getattr(settings, "max_vision_calls", 25)

    for page_number, page in enumerate(doc, start=1):
        # 1. Text blocks extraction with bounding box provenance
        page_text_combined: list[str] = []
        text_page = page.get_text("blocks")
        for block in text_page:
            # block format: (x0, y0, x1, y1, text, block_no, block_type)
            # block_type == 0 is text; 1 is image
            if block[6] == 0:
                text = block[4].strip()
                if not text:
                    continue
                bbox = [float(block[0]), float(block[1]), float(block[2]), float(block[3])]
                page_text_combined.append(text)

                unit = ContentUnit(
                    source_id=source_id,
                    asset_id=asset_id,
                    modality="pdf",
                    text=text,
                    page_number=page_number,
                    sequence_index=seq_index,
                    bbox=bbox,
                    extraction_method="pymupdf_block",
                    confidence_score=1.0,
                )
                units.append(unit)
                seq_index += 1

        # 2. Embedded images on page -> save asset and describe via Vision Engine
        images_on_page = _extract_page_images_with_info(page, page_number)
        if images_on_page:
            for img_info in images_on_page:
                image_bytes = img_info["bytes"]
                bbox = img_info.get("bbox")
                image_id = f"IMG_{page_number}_{img_info['xref']}"
                saved_img_path = images_dir / f"diagram_{page_number}_{img_info['xref']}.png"

                try:
                    saved_img_path.write_bytes(image_bytes)
                except Exception as save_err:
                    logger.warning("[extractor] Could not write image: %s", save_err)

                description = ""
                if vision_calls_count < max_vision_budget:
                    try:
                        description = describe_image(
                            image_bytes, source=f"{pdf_path.name} p.{page_number}"
                        )
                        vision_calls_count += 1
                    except Exception as exc:
                        logger.warning("[extractor] Vision failed for image on page %s: %s", page_number, exc)
                else:
                    logger.info("[extractor] Vision budget reached (%d calls); skipping description for page %s image", max_vision_budget, page_number)
                    description = f"Educational diagram on page {page_number} (visual description skipped due to processing budget)"

                if not description:
                    logger.warning("[extractor] Could not describe diagram on page %s, using fallback", page_number)
                    description = f"Educational diagram on page {page_number}"

                unit = ContentUnit(
                    source_id=source_id,
                    asset_id=asset_id,
                    modality="pdf",
                    text=f"[DIAGRAM on page {page_number}]\n{description}",
                    visual_description=description,
                    page_number=page_number,
                    sequence_index=seq_index,
                    bbox=bbox,
                    image_id=image_id,
                    image_path=str(saved_img_path) if saved_img_path.exists() else None,
                    extraction_method="vision_model" if description else "pymupdf_image",
                    confidence_score=0.95,
                )
                units.append(unit)
                seq_index += 1
        else:
            # Fallback for scanned/image-only pages
            has_text = bool("".join(page_text_combined).strip())
            has_images = bool(page.get_images(full=True))
            if has_images and not has_text:
                try:
                    page_png = _render_page(page)
                    description = describe_image(
                        page_png, source=f"{pdf_path.name} p.{page_number} (scanned)"
                    )
                    unit = ContentUnit(
                        source_id=source_id,
                        asset_id=asset_id,
                        modality="pdf",
                        text=f"[SCANNED PAGE {page_number}]\n{description}",
                        visual_description=description,
                        page_number=page_number,
                        sequence_index=seq_index,
                        extraction_method="vision_model_scanned",
                        confidence_score=0.90,
                    )
                    units.append(unit)
                    seq_index += 1
                except Exception as exc:
                    logger.warning("[extractor] Scanned page render failed on page %s: %s", page_number, exc)

    doc.close()

    # If no units created (e.g. empty PDF), create a placeholder error unit
    if not units:
        units.append(
            ContentUnit(
                source_id=source_id,
                asset_id=asset_id,
                modality="pdf",
                text="",
                page_number=1,
                sequence_index=0,
                extraction_method="pymupdf_empty",
                confidence_score=0.0,
            )
        )

    return units


def _extract_page_images_with_info(page: fitz.Page, page_number: int) -> list[dict]:
    """Extract embedded images with xref and bounding box info."""
    results = []
    seen = set()

    for image_info in page.get_images(full=True):
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
                logger.debug("[extractor] Could not get image rect for xref %s: %s", xref, exc)

            results.append({"xref": xref, "bytes": img_bytes, "bbox": bbox})

    return results


def _try_extract_image(page: fitz.Page, xref: int, page_number: int) -> bytes | None:
    try:
        pix = fitz.Pixmap(page.parent, xref)
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)
        elif pix.colorspace and pix.colorspace.n > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        if pix.width < 50 or pix.height < 50:
            return None
        png = pix.tobytes("png")
        return png
    except Exception as exc:
        logger.debug("[extractor] Could not extract pixmap for xref %s on page %s: %s", xref, page_number, exc)
    return None


def _render_page(page: fitz.Page) -> bytes:
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    png = pix.tobytes("png")
    return png
