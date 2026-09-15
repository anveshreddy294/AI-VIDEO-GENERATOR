import io
import os
import re
from pathlib import Path
import pymupdf
from PIL import Image
from modules.config import PATHS
from modules.learning.schemas import Source, SourceChunk, ImageExtraction, uid
from modules.llm.provider import ProviderClient

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
MIMES = {".pdf": {"application/pdf"}, ".txt": {"text/plain"},
         ".png": {"image/png"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"},
         ".webp": {"image/webp"}}


def chunk_text(text, source, page=None):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    chunks, buffer, first, size = [], [], 1, 0
    for number, line in enumerate(lines, 1):
        # Bound paragraphs without losing line provenance.
        for part in [line[i:i+1800] for i in range(0, len(line), 1800)] or [""]:
            if buffer and size + len(part) > 1800:
                chunks.append(SourceChunk(source_id=source.source_id, text="\n".join(buffer),
                    page=page, section=lines[first-1][:100] if lines else None,
                    line_start=first, line_end=number, url=source.url,
                    source_type=source.source_type, trust_label=source.trust_label))
                buffer, size, first = [], 0, number
            buffer.append(part)
            size += len(part) + 1
    if "\n".join(buffer).strip():
        chunks.append(SourceChunk(source_id=source.source_id, text="\n".join(buffer),
            page=page, line_start=first, line_end=len(lines), url=source.url,
            source_type=source.source_type, trust_label=source.trust_label))
    return chunks


def ingest(data, filename, mime, session_id, client=None):
    if not re.fullmatch(r"[a-f0-9]{32}", session_id):
        raise ValueError("Invalid session identifier")
    filename = filename.replace("\\", "/").split("/")[-1]
    filename = re.sub(r"[^\w. -]", "_", filename)[:100]
    ext = Path(filename).suffix.lower()
    if ext not in MIMES or mime.split(";")[0] not in MIMES[ext]:
        raise ValueError("Unsupported extension or MIME type")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Upload is empty or exceeds the configured size limit")
    if data[:2] == b"MZ" or data[:4] == b"\x7fELF":
        raise ValueError("Executable content is forbidden")
    source = Source(title=filename, source_type="uploaded")
    warnings, extraction, chunks = [], None, []
    if ext == ".txt":
        text = data.decode("utf-8-sig", errors="strict")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise ValueError("TXT contains binary control characters")
        chunks = chunk_text(text, source)
    elif ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature")
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or len(doc) > int(os.getenv("MAX_PDF_PAGES", "200")):
                raise ValueError("Encrypted or oversized PDF is unsupported")
            for index, page in enumerate(doc):
                chunks.extend(chunk_text(page.get_text(), source, page=index + 1))
        if not chunks:
            raise ValueError("No readable PDF text; upload page images for image understanding")
    else:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Image exceeds 20 megapixels")
            expected = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}[ext]
            if image.format != expected:
                raise ValueError("Image signature does not match extension")
            image.verify()
        extraction = ImageExtraction.model_validate((client or ProviderClient()).extract_image(data, mime))
        warnings = extraction.warnings + extraction.uncertain_content
        if extraction.confidence != "high" or extraction.uncertain_content:
            source.trust_label = "uncertain_extraction"
            warnings.append("Verify uncertain handwriting before relying on this lesson.")
        text = extraction.clean_text.strip()
        if not text:
            raise ValueError("The image did not contain readable educational text")
        chunks = chunk_text(text, source)
    if not chunks or sum(len(c.text.strip()) for c in chunks) < 30:
        raise ValueError("Not enough readable educational content")
    material_id = uid()
    directory = PATHS["root"] / "data/uploads" / session_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (material_id + ext)).write_bytes(data)
    material = {"material_id": material_id, "session_id": session_id, "filename": filename,
        "mime_type": mime, "input_type": "image" if ext in (".png", ".jpg", ".jpeg", ".webp") else ext[1:],
        "processing_status": "ready", "extracted_text_preview": chunks[0].text[:800],
        "detected_concepts": extraction.detected_concepts if extraction else [],
        "warnings": warnings, "extraction": extraction.model_dump() if extraction else None}
    return material, source, chunks
