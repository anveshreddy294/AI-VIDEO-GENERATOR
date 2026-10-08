"""Decoded file truth shared by HTTP admission, persistence and extraction."""
from __future__ import annotations
from dataclasses import dataclass
import codecs
import mimetypes
from pathlib import Path
from typing import Literal
from PIL import Image, UnidentifiedImageError
from ..core.config import settings

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_FILE_BYTES = 500 * 1024 * 1024
IMAGE_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
IMAGE_SUFFIXES = frozenset({"jpg", "jpeg", "png", "webp"})
IMAGE_MIMES = frozenset(mime for _, mime in IMAGE_FORMATS.values())
ValidationCode = Literal["EMPTY_FILE", "UNSUPPORTED_FILE_TYPE", "FILE_TYPE_MISMATCH", "CORRUPT_IMAGE", "UNSUPPORTED_IMAGE_FORMAT", "IMAGE_TOO_LARGE", "FILE_TOO_LARGE", "EMPTY_CONTENT", "INVALID_TEXT"]

class UploadValidationError(ValueError):
    def __init__(self, code: ValidationCode) -> None:
        self.code = code
        super().__init__(code)

@dataclass(frozen=True)
class FileTruth:
    source_type: Literal["txt", "pdf", "image", "video"]
    mime_type: str
    extension: str
    actual_format: str
    declared_extension: str
    browser_mime: str | None = None

    def provenance(self) -> dict[str, str | bool | None]:
        return {"actual_mime": self.mime_type, "actual_format": self.actual_format,
                "declared_extension": self.declared_extension, "browser_mime": self.browser_mime,
                "extension_normalized": self.declared_extension not in ({"jpg","jpeg"} if self.actual_format=="JPEG" else {self.extension})}

def inspect_upload(path: Path, filename: str, browser_mime: str | None = None) -> FileTruth:
    """Admit supported bytes before queueing; filename and browser MIME are hints only."""
    if not path.is_file() or path.stat().st_size == 0:
        raise UploadValidationError("EMPTY_FILE")
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in settings.allowed_extensions:
        raise UploadValidationError("UNSUPPORTED_FILE_TYPE")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise UploadValidationError("FILE_TOO_LARGE")
    with path.open("rb") as stream:
        header = stream.read(32)
    mime = browser_mime.split(";",1)[0].strip().lower() if browser_mime else None
    image_magic = header.startswith((b"\x89PNG\r\n\x1a\n",b"\xff\xd8\xff",b"GIF87a",b"GIF89a")) or (header[:4]==b"RIFF" and header[8:12]==b"WEBP")
    if extension in IMAGE_SUFFIXES:
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise UploadValidationError("IMAGE_TOO_LARGE")
        if header.startswith(b"%PDF") or header[:2] in (b"MZ",b"PK"):
            raise UploadValidationError("FILE_TYPE_MISMATCH")
        try:
            with Image.open(path) as image:
                actual = image.format or ""
                if actual not in IMAGE_FORMATS or getattr(image,"n_frames",1)!=1:
                    raise UploadValidationError("UNSUPPORTED_IMAGE_FORMAT")
                if image.width*image.height > MAX_IMAGE_PIXELS:
                    raise UploadValidationError("IMAGE_TOO_LARGE")
                image.verify()
            with Image.open(path) as image:
                image.load()
                # Uniform pixels contain no visible educational evidence.
                if all(low == high for low, high in image.convert("RGB").getextrema()):
                    raise UploadValidationError("EMPTY_CONTENT")
        except UploadValidationError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise UploadValidationError("CORRUPT_IMAGE") from None
        if mime not in IMAGE_MIMES | {None,"application/octet-stream"}:
            raise UploadValidationError("FILE_TYPE_MISMATCH")
        ext, actual_mime = IMAGE_FORMATS[actual]
        return FileTruth("image",actual_mime,ext,actual,extension,mime)
    if image_magic:
        raise UploadValidationError("FILE_TYPE_MISMATCH")
    if extension == "txt":
        if header.startswith((b"%PDF",b"MZ",b"PK")):
            raise UploadValidationError("FILE_TYPE_MISMATCH")
        decoder=codecs.getincrementaldecoder("utf-8-sig")("strict")
        meaningful=False
        try:
            with path.open("rb") as stream:
                while block:=stream.read(65536):
                    text=decoder.decode(block)
                    if any(ord(c)<32 and c not in "\n\r\t" for c in text):
                        raise UploadValidationError("INVALID_TEXT")
                    meaningful=meaningful or bool(text.strip())
                decoder.decode(b"",final=True)
        except UnicodeDecodeError:
            raise UploadValidationError("INVALID_TEXT") from None
        if not meaningful:
            raise UploadValidationError("EMPTY_CONTENT")
        return FileTruth("txt","text/plain","txt","TXT",extension,mime)
    from .modality import detect_modality
    signatures={"pdf":header.startswith(b"%PDF"),"mp4":header[4:8]==b"ftyp",
                "mov":header[4:8] in (b"ftyp",b"moov",b"free",b"wide"),"mkv":header.startswith(b"\x1a\x45\xdf\xa3")}
    if not signatures.get(extension,False):
        raise UploadValidationError("FILE_TYPE_MISMATCH")
    return FileTruth(detect_modality(Path(filename)),mimetypes.guess_type(filename)[0] or "application/octet-stream",extension,extension.upper(),extension,mime)
