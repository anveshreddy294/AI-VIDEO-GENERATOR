"""Modality Dispatcher — routes files to extractors producing ContentUnits.

Supported modalities:
- PDF   -> PyMuPDF text & diagram blocks -> ContentUnits
- Image -> Vision model description -> ContentUnit
- TXT   -> Paragraph/line parsing -> ContentUnits
- Video -> Multimodal A/V fusion -> ContentUnits
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .extractor import extract_from_pdf
from .schemas import ContentUnit
from .vision import VisionExtractionFailed, describe_image_file, describe_image_file_async

from .modality import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, UnsupportedFileType, detect_modality


@dataclass
class ExtractionResult:
    """Extraction output containing list of normalized ContentUnits."""

    source_id: str
    asset_id: str
    modality: str
    units: list[ContentUnit]


def dispatch(
    file_path: Path,
    source_id: str,
    asset_id: str,
    on_progress: Callable[[str], None] | None = None,
) -> ExtractionResult:
    """Route a validated source file to its modality extractor."""
    modality = detect_modality(file_path)

    if modality == "pdf":
        units = extract_from_pdf(file_path, source_id=source_id, asset_id=asset_id)
        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="pdf", units=units
        )

    if modality == "image":
        from .visual_evidence import visual_content_unit
        unit = visual_content_unit(file_path.read_bytes(), source_id=source_id,
            asset_id=asset_id, source=file_path.name, image_path=str(file_path))
        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="image", units=[unit]
        )

    if modality == "txt":
        raw_text = file_path.read_text(encoding="utf-8", errors="replace")
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        units: list[ContentUnit] = []
        char_cursor = 0

        for idx, para in enumerate(paragraphs):
            char_cursor = raw_text.index(para, char_cursor)
            para_len = len(para)
            unit = ContentUnit(
                source_id=source_id,
                asset_id=asset_id,
                modality="txt",
                text=para,
                sequence_index=idx,
                char_start=char_cursor,
                char_end=char_cursor + para_len,
                extraction_method="txt_paragraph",
                confidence_score=1.0,
            )
            units.append(unit)
            char_cursor += para_len

        if not units:
            units.append(
                ContentUnit(
                    source_id=source_id,
                    asset_id=asset_id,
                    modality="txt",
                    text=raw_text,
                    sequence_index=0,
                    extraction_method="txt_raw",
                    confidence_score=1.0,
                )
            )

        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="txt", units=units
        )

    if modality == "video":
        from .video.pipeline import process_video_units
        units = process_video_units(
            file_path, source_id=source_id, asset_id=asset_id
        )
        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="video", units=units
        )




async def dispatch_async(
    file_path: Path,
    source_id: str,
    asset_id: str,
    on_progress: Callable[[str], None] | None = None,
) -> ExtractionResult:
    """Route a validated source file to its modality extractor asynchronously."""
    modality = detect_modality(file_path)

    if modality == "image":
        from .visual_evidence import visual_content_unit
        unit = await asyncio.to_thread(visual_content_unit, file_path.read_bytes(),
            source_id=source_id, asset_id=asset_id, source=file_path.name, image_path=str(file_path))
        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="image", units=[unit]
        )

    # For other extractors (PDF, TXT, Video), run in thread pool to prevent blocking event loop
    return await asyncio.to_thread(dispatch, file_path, source_id, asset_id, on_progress)
