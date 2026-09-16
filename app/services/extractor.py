"""Text & image extraction from PDFs using PyMuPDF (fitz).

Strategy (matches the blueprint):
1. Rip all raw text page-by-page, tracked *chronologically*.
2. Whenever a page hosts an embedded image/diagram, crop the bytes and send
   them to Gemini Vision — the returned description is stitched inline at the
   page position where the diagram actually appeared.
3. If individual image extraction fails, render the entire page as a high-res
   PNG and send that to Gemini Vision instead (fallback).
4. Return one massive chronological string = the Authoritative Source.
"""

from pathlib import Path

import pymupdf as fitz

from .vision import describe_image


def extract_from_pdf(pdf_path: Path) -> str:
    """Extract text + diagram descriptions from a PDF, stitched in order."""
    doc = fitz.open(pdf_path)
    blocks: list[str] = []

    for page_number, page in enumerate(doc, start=1):
        blocks.append(f"\n===== PAGE {page_number} =====\n")

        # 1. Raw text for this page.
        text = page.get_text("text").strip()
        if text:
            blocks.append(text)

        # 2. Embedded images on this page -> crop + describe via vision.
        images_on_page = _extract_page_images(page, page_number)
        if images_on_page:
            for image_bytes in images_on_page:
                try:
                    description = describe_image(
                        image_bytes, source=f"{pdf_path.name} p.{page_number}"
                    )
                    blocks.append(
                        f"\n[DIAGRAM on page {page_number} — vision description]\n{description}"
                    )
                except Exception as exc:
                    print(f"[warn] vision failed for image on page {page_number}: {exc}")
        else:
            # 3. Fallback: render the full page as an image if it has visual
            #    content but no extractable embedded images (scans, figures, etc.)
            has_text = bool(text)
            has_images = bool(page.get_images(full=True))
            if has_images and not has_text:
                # Page is image-only (scanned document) — render and describe.
                try:
                    page_png = _render_page(page)
                    description = describe_image(
                        page_png, source=f"{pdf_path.name} p.{page_number} (full-page render)"
                    )
                    blocks.append(
                        f"\n[PAGE {page_number} — full-page vision description]\n{description}"
                    )
                except Exception as exc:
                    print(f"[warn] full-page render failed for page {page_number}: {exc}")

    doc.close()
    return "\n\n".join(blocks).strip()


def _extract_page_images(page: fitz.Page, page_number: int) -> list[bytes]:
    """Return PNG bytes for each embedded image on the page.

    Tries multiple extraction strategies:
    1. Direct Pixmap extraction via xref
    2. Pixmap with explicit RGB conversion
    3. Clip-based extraction (crop the image region from the page)
    """
    pngs: list[bytes] = []
    seen: set[int] = set()

    for image_info in page.get_images(full=True):
        xref = image_info[0]
        if xref in seen:
            continue
        seen.add(xref)

        extracted = _try_extract_image(page, xref, page_number)
        if extracted is not None:
            pngs.append(extracted)

    return pngs


def _try_extract_image(page: fitz.Page, xref: int, page_number: int) -> bytes | None:
    """Try multiple strategies to extract a single image from the page."""

    # Strategy 1: Direct Pixmap extraction
    try:
        pix = fitz.Pixmap(doc=page.parent, xref=xref)
        # Flatten alpha / CMYK to RGB
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix, 0)  # drop alpha
        elif pix.colorspace and pix.colorspace.n > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        # Skip tiny images (likely icons/logos, not diagrams)
        if pix.width < 50 or pix.height < 50:
            pix = None
            return None
        png = pix.tobytes("png")
        pix = None
        return png
    except Exception:
        pass

    # Strategy 2: Try extracting with a clipped region approach
    try:
        # Get the image bounding box on the page
        rects = page.get_image_rects(xref)
        if rects:
            rect = rects[0]
            # Only process reasonably sized images
            if rect.width >= 50 and rect.height >= 50:
                # Render the page at high DPI and crop to the image region
                mat = fitz.Matrix(2.0, 2.0)  # 2x scale for quality
                clip = rect
                page_pix = page.get_pixmap(matrix=mat, clip=clip)
                png = page_pix.tobytes("png")
                page_pix = None
                return png
    except Exception:
        pass

    print(f"[warn] could not extract image xref={xref} on page {page_number}")
    return None


def _render_page(page: fitz.Page) -> bytes:
    """Render an entire page as a high-res PNG (fallback for scanned pages)."""
    mat = fitz.Matrix(2.0, 2.0)  # 2x scale = ~144 DPI
    pix = page.get_pixmap(matrix=mat)
    png = pix.tobytes("png")
    pix = None
    return png
