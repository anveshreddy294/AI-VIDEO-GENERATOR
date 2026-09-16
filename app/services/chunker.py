"""Layer A chunking — Rip the Authoritative Source into overlapping 1000-token
chunks so the AI keeps cross-paragraph context, then tag each chunk as Layer A
ground truth.

Uses LangChain's RecursiveCharacterTextSplitter measured in *tokens*, with a
local tokenizer (tiktoken) so no network round-trip is needed per split. The
separator list makes boundaries land on paragraph breaks whenever possible.

Two entry points:
- `chunk_authoritative_text` — documents (PDF/image/TXT), chunk located by page
- `chunk_video_text`         — lectures, chunk located by its [start - end]
  clock window, extracted by scanning the block markers the fusion engine wrote.
"""

import re

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..core.config import settings
from .schemas import AuthoritativeSourceChunk, AuthoritativeVideoChunk

_encoding = tiktoken.get_encoding("cl100k_base")

# Matches "[01:15 - 01:30]" markers emitted by the fusion engine.
_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\]")


def _token_len(text: str) -> int:
    return len(_encoding.encode(text))


def _make_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,          # ~1000 tokens
        chunk_overlap=settings.chunk_overlap,    # 150-token overlap
        length_function=_token_len,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )


def chunk_authoritative_text(
    text: str, document_name: str, page_map: list[int] | None = None
) -> list[AuthoritativeSourceChunk]:
    """Split a document source and tag every chunk with page-level metadata."""
    splitter = _make_splitter()
    raw_chunks = splitter.split_text(text)

    return [
        AuthoritativeSourceChunk(
            document_name=document_name,
            text=raw.strip(),
            page=page_map[i] if page_map and i < len(page_map) else None,
        )
        for i, raw in enumerate(raw_chunks)
    ]


def chunk_video_text(text: str, video_name: str) -> list[AuthoritativeVideoChunk]:
    """Split the fused lecture and tag every chunk with its clock window.

    Each chunk keeps the *earliest* start and *latest* end among the
    [MM:SS - MM:SS] blocks it contains, so a question answered by this chunk
    can point the student to the exact recording window.
    """
    splitter = _make_splitter()
    raw_chunks = splitter.split_text(text)

    return [
        AuthoritativeVideoChunk(
            video_name=video_name,
            start_timestamp=start,
            end_timestamp=end,
            text=raw.strip(),
        )
        for raw in raw_chunks
        for start, end in [_chunk_window(raw)]
    ]


def _chunk_window(chunk_text: str) -> tuple[str, str]:
    """Earliest start / latest end across all timestamp markers in the chunk."""
    matches = _TIMESTAMP_RE.findall(chunk_text)
    if not matches:
        return "00:00", "00:00"
    starts = [int(m[0]) * 60 + int(m[1]) for m in matches]
    ends = [int(m[2]) * 60 + int(m[3]) for m in matches]
    return _fmt(min(starts)), _fmt(max(ends))


def _fmt(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"