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
    units: list[ContentUnit], kg: KnowledgeGraph
) -> list[RichChunk]:
    """Group ContentUnits by section/concept boundaries into RAG-ready RichChunks."""
    if not units:
        return []

    # Map content_id -> concept_ids
    cu_to_concepts: dict[str, list[str]] = {}
    for cid, concept_node in kg.concepts.items():
        for source_cu_id in concept_node.source_content_ids:
            cu_to_concepts.setdefault(source_cu_id, []).append(cid)

    source_id = units[0].source_id
    asset_id = units[0].asset_id
    modality = units[0].modality

    # Group units into section windows
    sections: list[list[ContentUnit]] = []
    current_group: list[ContentUnit] = []
    current_key = None

    for u in units:
        group_key = (u.chapter, u.section)
        if current_key is None:
            current_key = group_key
        if group_key != current_key and current_group:
            sections.append(current_group)
            current_group = []
            current_key = group_key
        current_group.append(u)
    if current_group:
        sections.append(current_group)

    chunks: list[RichChunk] = []

    for sec_units in sections:
        sec_text = "\n\n".join(u.text for u in sec_units)
        cu_ids = [u.content_id for u in sec_units]

        # Gather concept IDs for this group
        group_concepts = set()
        for u in sec_units:
            group_concepts.update(cu_to_concepts.get(u.content_id, []))

        pages = [u.page_number for u in sec_units if u.page_number is not None]
        timestamps = [
            u.timestamp_start for u in sec_units if u.timestamp_start is not None
        ] + [u.timestamp_end for u in sec_units if u.timestamp_end is not None]

        page_start = min(pages) if pages else None
        page_end = max(pages) if pages else None
        ts_start = min(timestamps) if timestamps else None
        ts_end = max(timestamps) if timestamps else None

        # Split section text into token chunks if too large
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=_token_len,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
        )

        split_texts = splitter.split_text(sec_text)
        for sub_text in split_texts:
            chunk = RichChunk(
                source_id=source_id,
                asset_id=asset_id,
                layer="A",
                type="rich_chunk",
                text=sub_text.strip(),
                modality=modality,
                chapter=sec_units[0].chapter,
                section=sec_units[0].section,
                concept_ids=sorted(list(group_concepts)),
                content_ids=cu_ids,
                page_start=page_start,
                page_end=page_end,
                timestamp_start=ts_start,
                timestamp_end=ts_end,
                extraction_method=sec_units[0].extraction_method,
            )
            chunks.append(chunk)

    return chunks


# Legacy backwards-compatible helpers
def chunk_authoritative_text(text: str, document_name: str, page_map=None):
    from .schemas import AuthoritativeSourceChunk

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=_token_len,
    )
    return [
        AuthoritativeSourceChunk(document_name=document_name, text=raw.strip())
        for raw in splitter.split_text(text)
    ]


def chunk_video_text(text: str, video_name: str):
    from .schemas import AuthoritativeVideoChunk

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=_token_len,
    )
    return [
        AuthoritativeVideoChunk(
            video_name=video_name,
            start_timestamp="00:00",
            end_timestamp="00:00",
            text=raw.strip(),
        )
        for raw in splitter.split_text(text)
    ]