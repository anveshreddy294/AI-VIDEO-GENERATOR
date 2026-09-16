"""Text & image extraction from PDFs using PyMuPDF (fitz).

Strategy (matches the blueprint):
1. Rip all raw text page-by-page, tracked *chronologically*.
2. Whenever a page hosts an embedded image/diagram, crop the bytes and send
   them to Gemini Vision — the returned description is stitched inline at the
   page position where the diagram actually appeared.
3. Return one massive chronological string = the Authoritative Source.
"""

from pathlib import Path

import fitz  # PyMuPDF

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
        for image_bytes in images_on_page:
            description = describe_image(image_bytes, source=f"{pdf_path.name} p.{page_number}")
            blocks.append(
                f"\n[DIAGRAM on page {page_number} — vision description]\n{description}"
            )

    doc.close()
    return "\n\n".join(blocks).strip()


def _extract_page_images(page: fitz.Page, page_number: int) -> list[bytes]:
    """Return PNG bytes for each embedded image on the page.

    Uses `page.get_images()` to find xrefs, then `fitz.Pixmap` to render a
    usable PNG. Skipping xrefs already seen across pages avoids re-describing
    the same logo/figure repeatedly.
    """
    pngs: list[bytes] = []
    seen: set[int] = set()

    for image_info in page.get_images(full=True):
        xref = image_info[0]
        if xref in seen:
            continue
        seen.add(xref)
        try:
            pix = fitz.Pixmap(doc=page.parent, xref=xref)
            if pix.colorspace and pix.colorspace.n > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)  # flatten CMYK/transparency
            pngs.append(pix.tobytes("png"))
            pix = None
        except Exception:
            # A corrupted or generations image shouldn't sink the whole doc.
            print(f"[warn] could not extract image xref={xref} on page {page_number}")
            continue

    return pngs