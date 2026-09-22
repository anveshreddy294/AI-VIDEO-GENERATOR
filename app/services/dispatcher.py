"""Modality Dispatcher — routes files to extractors producing ContentUnits.

Supported modalities:
- PDF   -> PyMuPDF text & diagram blocks -> ContentUnits
- Image -> Vision model description -> ContentUnit
- TXT   -> Paragraph/line parsing -> ContentUnits
- Video -> Multimodal A/V fusion -> ContentUnits
"""

from dataclasses import dataclass
from pathlib import Path

from .extractor import extract_from_pdf
from .schemas import ContentUnit
from .vision import VisionExtractionFailed, describe_image_file

IMAGE_EXTENSIONS: set[str] = {"png", "jpg", "jpeg"}
VIDEO_EXTENSIONS: set[str] = {"mp4", "mov", "mkv"}


class UnsupportedFileType(Exception):
    pass



@dataclass
class ExtractionResult:
    """Extraction output containing list of normalized ContentUnits."""

    source_id: str
    asset_id: str
    modality: str
    units: list[ContentUnit]


def dispatch(
    file_path: Path, source_id: str, asset_id: str
) -> ExtractionResult:
    """Route a validated source file to its modality extractor."""
    ext = file_path.suffix.lstrip(".").lower()

    if ext == "pdf":
        units = extract_from_pdf(file_path, source_id=source_id, asset_id=asset_id)
        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="pdf", units=units
        )

    if ext in IMAGE_EXTENSIONS:
        description = describe_image_file(file_path)
        unit = ContentUnit(
            source_id=source_id,
            asset_id=asset_id,
            modality="image",
            text=f"[IMAGE: {file_path.name}]\n{description}",
            visual_description=description,
            sequence_index=0,
            image_id=f"IMG_{file_path.stem}",
            image_path=str(file_path),
            extraction_method="vision_model",
            confidence_score=0.95,
        )
        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="image", units=[unit]
        )

    if ext == "txt":
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

    if ext in VIDEO_EXTENSIONS:
        from .video.pipeline import process_video_units
        units = process_video_units(
            file_path, source_id=source_id, asset_id=asset_id
        )
        return ExtractionResult(
            source_id=source_id, asset_id=asset_id, modality="video", units=units
        )

    raise UnsupportedFileType(
        f"Unsupported extension '.{ext}'. Allowed: pdf, png, jpg, jpeg, txt, mp4, mov, mkv."
    )