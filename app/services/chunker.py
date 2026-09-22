"""Concept-Aware Semantic Chunker with Full Provenance Mapping.

Converts normalized ContentUnits and KnowledgeGraph concepts into RAG-ready
RichChunks tagged with source_id, asset_id, concept_ids, content_ids, page
ranges, timestamps, and layer="A".
"""

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..core.config import settings
from .schemas import ContentUnit, KnowledgeGraph, RichChunk

_encoding = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_encoding.encode(text))


def create_rich_chunks(
    units: list[ContentUnit],
    kg: KnowledgeGraph,
    user_id: str = "student_default",
    source_version: str = "v1",
    source_hash: str | None = None,
) -> list[RichChunk]:
    """Group ContentUnits by section/concept boundaries into RAG-ready RichChunks."""
    if not units:
        return []

    # Map content_id -> concept_ids
    cu_to_concepts: dict[str, list[str]] = {}
    for cid, concept_node in kg.concepts.items():
        for source_cu_id in concept_node.source_content_ids:
            cu_to_concepts.setdefault(source_cu_id, []).append(cid)

    # Keep each chunk's provenance limited to text it actually contains.
    from uuid import uuid5, NAMESPACE_URL
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap,
        length_function=_token_len, separators=["\n\n", "\n", ". ", " ", ""], keep_separator=True,
    )
    chunks = []
    for unit in units:
        unit_text = unit.text.strip() if unit.text else ""
        if not unit_text:
            continue
        for index, text in enumerate(splitter.split_text(unit_text)):
            if not text.strip():
                continue
            chunks.append(RichChunk(
                chunk_id="CHUNK_" + uuid5(NAMESPACE_URL, f"{unit.source_id}:{unit.content_id}:{index}:{text}").hex,
                source_id=unit.source_id,
                asset_id=unit.asset_id,
                user_id=user_id,
                source_version=source_version,
                source_hash=source_hash,
                trust_status="user_uploaded_source",
                injection_status="clean",
                retrieval_allowed=True,
                parser_version="v1",
                text=text.strip(),
                layer="A",
                type="rich_chunk",
                modality=unit.modality,
                chapter=unit.chapter,
                section=unit.section,
                concept_ids=sorted(cu_to_concepts.get(unit.content_id, [])),
                content_ids=[unit.content_id],
                page_start=getattr(unit, "page_start", None) or unit.page_number,
                page_end=getattr(unit, "page_end", None) or unit.page_number,
                slide_start=getattr(unit, "slide_number", None),
                slide_end=getattr(unit, "slide_number", None),
                speaker=getattr(unit, "speaker", None),
                timestamp_start=unit.timestamp_start,
                timestamp_end=unit.timestamp_end,
                extraction_method=unit.extraction_method,
            ))
    return chunks
