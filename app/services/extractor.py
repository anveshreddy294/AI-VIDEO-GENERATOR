"""PDF extraction engine returning normalized ContentUnits.

Extracts text blocks and embedded image diagrams page-by-page, capturing
page numbers, bounding boxes, visual descriptions, and confidence scores.
"""

from pathlib import Path
from uuid import uuid4

import pymupdf as fitz

from .schemas import ContentUnit
from .vision import describe_image


def extract_from_pdf(
    pdf_path: Path, source_id: str, asset_id: str
) -> list[ContentUnit]:
    """Extract page-level ContentUnits from a PDF file."""
    doc = fitz.open(pdf_path)
    units: list[ContentUnit] = []
    seq_index = 0

    for page_number, page in enumerate(doc, start=1):
        # 1. Text blocks extraction with bounding box provenance
        text_page = page.get_text("blocks")  # list of (x0, y0, x1, y1, text, block_no, block_type)
        page_text_combined = []

        for block in text_page:
            if len(block) >= 5 and block[4].strip():
                bbox = [float(block[0]), float(block[1]), float(block[2]), float(block[3])]
                block_text = block[4].strip()
                page_text_combined.append(block_text)

                unit = ContentUnit(
                    source_id=source_id,
                    asset_id=asset_id,
                    modality="pdf",
                    text=block_text,
                    page_number=page_number,
                    sequence_index=seq_index,
                    bbox=bbox,
                    extraction_method="pymupdf_block",
                    confidence_score=1.0,
                )
                units.append(unit)
                seq_index += 1

        # 2. Embedded images on page -> describe via Gemini Vision
        images_on_page = _extract_page_images_with_info(page, page_number)
        if images_on_page:
            for img_info in images_on_page:
                image_bytes = img_info["bytes"]
                bbox = img_info.get("bbox")
                image_id = f"IMG_{page_number}_{img_info['xref']}"

                try:
                    description = describe_image(
                        image_bytes, source=f"{pdf_path.name} p.{page_number}"
                    )
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
                        extraction_method="gemini_vision",
                        confidence_score=0.95,
                    )
                    units.append(unit)
                    seq_index += 1
                except Exception as exc:
                    print(f"[warn] vision failed for image on page {page_number}: {exc}")
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
                        extraction_method="gemini_vision_scanned",
                        confidence_score=0.90,
                    )
                    units.append(unit)
                    seq_index += 1
                except Exception as exc:
                    print(f"[warn] scanned page render failed on page {page_number}: {exc}")

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
            except Exception:
                pass

            results.append({"xref": xref, "bytes": img_bytes, "bbox": bbox})

    return results


def _try_extract_image(page: fitz.Page, xref: int, page_number: int) -> bytes | None:
    try:
        pix = fitz.Pixmap(doc=page.parent, xref=xref)
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix, 0)
        elif pix.colorspace and pix.colorspace.n > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        if pix.width < 50 or pix.height < 50:
            return None
        png = pix.tobytes("png")
        return png
    except Exception:
        pass
    return None


def _render_page(page: fitz.Page) -> bytes:
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    png = pix.tobytes("png")
    return png
