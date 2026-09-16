"""Extraction engine — the Dispatcher router.

Routes the temporarily saved file based on its extension:

- `.pdf`  -> PyMuPDF text extraction + per-image vision descriptions
- `.png/.jpg/.jpeg` -> the whole image goes straight to Gemini Vision
- `.txt`  -> raw text passthrough
- `.mp4/.mov/.mkv` -> Video Matrix (A/V split -> whisper -> keyframes -> fusion)

Every route returns an `ExtractionResult`: the massive chronological string —
the "Authoritative Source" — plus the kind of media it came from, so the
chunker knows whether to tag chunks by *page* (documents) or by *clock window*
(videos).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .extractor import extract_from_pdf
from .video import process_video
from .vision import describe_image

VIDEO_EXTENSIONS: set[str] = {"mp4", "mov", "mkv"}
IMAGE_EXTENSIONS: set[str] = {"png", "jpg", "jpeg"}


class UnsupportedFileType(Exception):
    pass


@dataclass
class ExtractionResult:
    """The authoritative text plus the media kind it was extracted from."""

    text: str
    kind: Literal["document", "video"]


def dispatch(file_path: Path) -> ExtractionResult:
    """Read a validated file and return its stitched authoritative text."""
    ext = file_path.suffix.lstrip(".").lower()

    if ext == "pdf":
        return ExtractionResult(kind="document", text=extract_from_pdf(file_path))

    if ext in IMAGE_EXTENSIONS:
        description = describe_image(file_path)
        text = (
            f"[SOURCE: {file_path.name} — image]\n"
            f"Vision description:\n{description}\n"
        )
        return ExtractionResult(kind="document", text=text)

    if ext == "txt":
        return ExtractionResult(
            kind="document",
            text=file_path.read_text(encoding="utf-8", errors="replace"),
        )

    if ext in VIDEO_EXTENSIONS:
        return ExtractionResult(kind="video", text=process_video(file_path))

    raise UnsupportedFileType(
        f"Unsupported extension '.{ext}'. Allowed: pdf, png, jpg, jpeg, txt, mp4, mov, mkv."
    )