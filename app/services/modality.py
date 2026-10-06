"""Authoritative file routing and page-level visual extraction decisions."""
from pathlib import Path
from typing import Literal

Modality = Literal['txt', 'pdf', 'image', 'video']
IMAGE_EXTENSIONS: set[str] = {'png', 'jpg', 'jpeg'}
VIDEO_EXTENSIONS: set[str] = {'mp4', 'mov', 'mkv'}


class UnsupportedFileType(ValueError):
    """The source has no supported extraction route."""


def detect_modality(path: Path) -> Modality:
    """Choose from the validated extension, never from provider configuration."""
    extension = path.suffix.lower().lstrip('.')
    if extension in {'txt', 'pdf'}:
        return 'txt' if extension == 'txt' else 'pdf'
    if extension in IMAGE_EXTENSIONS:
        return 'image'
    if extension in VIDEO_EXTENSIONS:
        return 'video'
    raise UnsupportedFileType(f"Unsupported source extension: .{extension}")


def visual_extraction_required(modality: Modality, *, has_text: bool = False,
                               has_visual_content: bool = False) -> bool:
    """PDF text alone needs no vision; images or scanned pages do."""
    return modality == 'image' or (modality == 'pdf' and (has_visual_content or not has_text))
