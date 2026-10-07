"""Deterministic educational boundaries with scoped, verifiable canonical spans."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from .chunker import _token_len
from .content_understanding import ContentRole
from .knowledge_models import CanonicalKnowledge, Contract, ScopedContentUnit
from .schemas import RichChunk
from .security.source_scope import SourceScope, vector_version

CHUNK_POLICY_VERSION = "educational-chunks-v1"


def classify_content_role(text: str, modality: str = "txt") -> ContentRole:
    """Conservative lexical roles for uncategorized evidence; never fabricate concepts."""
    rules: tuple[tuple[ContentRole, str], ...] = (
        ("WORKED_EXAMPLE", r"\bworked example\b|\bexample\b[\s\S]*\bstep\b"),
        ("DIAGRAM_DESCRIPTION", r"\b(diagram|figure|arrow)\b"),
        ("TABLE", r"\btable\b.*\b(row|column)\b"),
        ("QUESTION", r"\?|^\s*(question|Q:)"),
        ("ANSWER", r"^\s*(answer|A:|solution)"),
        ("SUMMARY", r"^\s*summary|\bin conclusion\b"),
        (
            "PREREQUISITE_EVIDENCE",
            r"\brequires?\b|\bdepends? on\b|\b(prerequisite|needed for)\b|\b(must|should)\b[\s\S]*\bbefore\b",
        ),
        ("EXAMPLE", r"\bexample\b|\bfor instance\b"),
        ("FORMULA", r"[=∑∫≈]"),
        ("PROCEDURE", r"\bstep\s*\d|\bfirst\b[\s\S]*\bthen\b"),
        ("DEFINITION", r"\b(is|are|means|defined as|refers to)\b"),
        (
            "EXPLANATION",
            r"\b(because|therefore|causes?|explains?|due to|as a result)\b",
        ),
    )
    return next(
        (role for role, pattern in rules if re.search(pattern, text, re.I)),
        "GENERAL_CONTENT",
    )


class ChunkPolicy(Contract):
    """Token ceilings are safety defaults, not a universally optimal retrieval size."""

    version: Literal["educational-chunks-v1"] = CHUNK_POLICY_VERSION
    max_tokens: int = Field(default=384, ge=64, le=1024)
    target_tokens: int = Field(default=256, ge=32, le=1024)
    explanatory_overlap_tokens: int = Field(default=40, ge=0, le=64)
    minimum_context_tokens: int = Field(default=24, ge=0, le=64)

    @model_validator(mode="after")
    def coherent_bounds(self) -> ChunkPolicy:
        if (
            self.target_tokens > self.max_tokens
            or self.explanatory_overlap_tokens > self.max_tokens // 4
        ):
            raise ValueError("Invalid structural chunk policy bounds")
        return self


class CanonicalSpan(Contract):
    content_id: str
    char_start: int
    char_end: int


class ChunkMetadata(Contract):
    topic_id: str | None
    subtopic_id: str | None
    content_role: ContentRole
    sequence: int
    heading_path: list[str]
    canonical_spans: list[CanonicalSpan]
    chunking_policy_version: str
    chunking_policy_hash: str
    canonical_source_version: int
    understanding_version: str


class ChunkQuality(Contract):
    chunks: int
    chunk_evidence_coverage: float
    unassigned_content_ids: list[str]
    excessive_fragments: int
    oversized_chunks: int
    oversized_structural_blocks: int


@dataclass(frozen=True)
class Block:
    unit: ScopedContentUnit
    start: int
    end: int
    topic: str | None
    subtopic: str | None
    role: ContentRole
    concepts: tuple[str, ...]

    @property
    def text(self) -> str:
        return self.unit.content.text[self.start : self.end]


def create_educational_chunks(
    scope: SourceScope,
    units: list[ScopedContentUnit],
    knowledge: CanonicalKnowledge,
    policy: ChunkPolicy | None = None,
    source_hash: str | None = None,
    *,
    published: bool = True,
) -> tuple[list[RichChunk], ChunkQuality]:
    """Paragraph/knowledge boundaries precede token splitting; combine compatible neighbors."""
    from .repositories.knowledge_repository import KnowledgeError
    from .knowledge_service import KnowledgeService

    policy = policy or ChunkPolicy()
    if (
        policy.version != CHUNK_POLICY_VERSION
        or policy.target_tokens > policy.max_tokens
    ):
        raise KnowledgeError("INVALID_SCOPE")
    if knowledge.readiness.knowledge_state != ("READY" if published else "PENDING"):
        raise KnowledgeError("NOT_READY")
    KnowledgeService._validate(knowledge)
    if (
        knowledge.readiness.user_id,
        knowledge.readiness.source_id,
        knowledge.readiness.source_version,
    ) != (scope.user_id, scope.source_id, scope.source_version):
        raise KnowledgeError("NOT_FOUND")
    lookup = {u.content_id: u for u in units}
    if len(lookup) != len(units) or any(
        (u.user_id, u.source_id, u.source_version)
        != (scope.user_id, scope.source_id, scope.source_version)
        for u in units
    ):
        raise KnowledgeError("INVALID_SCOPE")
    subs = {s.subtopic_id: s for s in knowledge.subtopics}
    concepts = {c.concept_id: c for c in knowledge.concepts}
    supported: dict[str, list[tuple[int, int, str, str, str, ContentRole]]] = {}
    for e in knowledge.evidence:
        if e.content_id not in lookup or e.char_start is None or e.char_end is None:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        if e.char_end > len(lookup[e.content_id].content.text):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        c = concepts[e.concept_id]
        if c.subtopic_id is None:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        role = e.provenance.get("content_role")
        from pydantic import TypeAdapter, ValidationError

        try:
            typed_role = TypeAdapter(ContentRole).validate_python(
                role
                or (
                    "DEFINITION"
                    if e.support_kind == "definition"
                    else "GENERAL_CONTENT"
                )
            )
        except ValidationError:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
        supported.setdefault(e.content_id, []).append(
            (
                e.char_start,
                e.char_end,
                e.concept_id,
                subs[c.subtopic_id].topic_id,
                c.subtopic_id,
                typed_role,
            )
        )
    blocks: list[Block] = []
    oversized_blocks = 0
    for unit in sorted(units, key=lambda u: (u.content.sequence_index, u.content_id)):
        spans = supported.get(unit.content_id, [])
        paragraphs = list(re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", unit.content.text))
        for paragraph in paragraphs:
            start, end = paragraph.span()
            cuts = {start, end}
            # A single extracted unit may contain unrelated subjects; split at their actual evidence.
            interior = sorted({a for a, b, *_ in spans if start < a < end})
            if len({(t, s) for a, b, c, t, s, r in spans if a < end and b > start}) > 1:
                cuts.update(interior)
            boundaries = sorted(cuts)
            for a, b in zip(boundaries, boundaries[1:]):
                while a < b and unit.content.text[a].isspace():
                    a += 1
                while b > a and unit.content.text[b - 1].isspace():
                    b -= 1
                if a == b:
                    continue
                active = [row for row in spans if row[0] < b and row[1] > a]
                if len({(row[3], row[4]) for row in active}) > 1:
                    raise KnowledgeError(
                        "INVALID_PROVIDER_RESPONSE"
                    )  # Ambiguous shared span cannot choose a topic silently.
                topic, sub, role = (
                    (active[0][3], active[0][4], active[0][5])
                    if active
                    else (
                        None,
                        None,
                        classify_content_role(
                            unit.content.text[a:b], unit.content.modality
                        ),
                    )
                )
                block = Block(
                    unit,
                    a,
                    b,
                    topic,
                    sub,
                    role,
                    tuple(sorted({row[2] for row in active})),
                )
                if _token_len(block.text) <= policy.max_tokens:
                    blocks.append(block)
                    continue
                oversized_blocks += 1
                # Reuse the existing token-aware recursive splitter only for oversized structures.
                from langchain_text_splitters import RecursiveCharacterTextSplitter

                overlap = (
                    policy.explanatory_overlap_tokens
                    if role in {"EXPLANATION", "GENERAL_CONTENT"}
                    else 0
                )
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=policy.max_tokens,
                    chunk_overlap=overlap,
                    length_function=_token_len,
                    separators=["\n\n", "\n", ". ", " ", ""],
                    keep_separator=True,
                )
                previous = a
                for piece in splitter.split_text(block.text):
                    pos = unit.content.text.find(piece, previous, b)
                    if pos < 0:
                        raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
                    previous = pos + 1
                    piece_end = pos + len(piece)
                    present = tuple(
                        sorted(
                            {
                                row[2]
                                for row in active
                                if row[0] < piece_end and row[1] > pos
                            }
                        )
                    )
                    blocks.append(
                        Block(unit, pos, piece_end, topic, sub, role, present)
                    )
    # Attach tiny heading-only prefixes to their following educational body in the same unit.
    enriched: list[Block] = []
    for i, block in enumerate(blocks):
        if (
            i
            and blocks[i - 1].role == "GENERAL_CONTENT"
            and _token_len(blocks[i - 1].text) < policy.minimum_context_tokens
        ):
            prefix = blocks[i - 1]
            if (
                prefix.unit.content_id == block.unit.content_id
                and prefix.end <= block.start
                and not prefix.concepts
            ):
                combined = Block(
                    block.unit,
                    prefix.start,
                    block.end,
                    block.topic,
                    block.subtopic,
                    block.role,
                    block.concepts,
                )
                if (
                    _token_len(combined.text) <= policy.max_tokens
                    and enriched
                    and enriched[-1] == prefix
                ):
                    enriched.pop()
                    block = combined
        enriched.append(block)
    groups: list[list[Block]] = []
    for block in enriched:
        prior = groups[-1][-1] if groups else None
        compatible = prior is not None and (
            prior.topic,
            prior.subtopic,
            prior.role,
            prior.unit.content.modality,
            prior.unit.content.heading_path,
            prior.unit.content.section,
            prior.unit.content.sequence_index,
        ) == (
            block.topic,
            block.subtopic,
            block.role,
            block.unit.content.modality,
            block.unit.content.heading_path,
            block.unit.content.section,
            block.unit.content.sequence_index - 1,
        )
        # Same-unit adjacent paragraphs are also coherent if scope/role/heading agree.
        compatible = compatible or (
            prior is not None
            and prior.unit.content_id == block.unit.content_id
            and prior.end <= block.start
            and (prior.topic, prior.subtopic, prior.role)
            == (block.topic, block.subtopic, block.role)
        )
        combined = (
            "\n\n".join(b.text for b in groups[-1] + [block]) if groups else block.text
        )
        if compatible and _token_len(combined) <= policy.target_tokens:
            groups[-1].append(block)
        else:
            groups.append([block])
    policy_hash = hashlib.sha256(policy.model_dump_json().encode()).hexdigest()
    chunks: list[RichChunk] = []
    for position, group in enumerate(groups):
        first = group[0]
        text = "\n\n".join(b.text for b in group)
        spans = [
            CanonicalSpan(
                content_id=b.unit.content_id, char_start=b.start, char_end=b.end
            )
            for b in group
        ]
        metadata = ChunkMetadata(
            topic_id=first.topic,
            subtopic_id=first.subtopic,
            content_role=first.role,
            sequence=position,
            heading_path=first.unit.content.heading_path,
            canonical_spans=spans,
            chunking_policy_version=policy.version,
            chunking_policy_hash=policy_hash,
            canonical_source_version=scope.source_version,
            understanding_version="educational-v1",
        )
        identity = f"{scope.user_id}:{scope.source_id}:{scope.source_version}:{metadata.model_dump_json()}:{text}"
        pages = [b.unit.content.page_start or b.unit.content.page_number for b in group]
        ends = [b.unit.content.page_end or b.unit.content.page_number for b in group]
        chunks.append(
            RichChunk(
                chunk_id="CHUNK_" + uuid5(NAMESPACE_URL, identity).hex,
                source_id=scope.source_id,
                asset_id=first.unit.content.asset_id,
                user_id=str(scope.user_id),
                source_version=vector_version(scope.source_version),
                source_hash=source_hash,
                source_type=first.unit.content.modality,
                content_id=first.unit.content_id,
                text=text,
                modality=first.unit.content.modality,
                chapter=first.unit.content.chapter,
                section=first.unit.content.section,
                concept_ids=sorted({c for b in group for c in b.concepts}),
                content_ids=sorted({b.unit.content_id for b in group}),
                page_start=(
                    min(p for p in pages if p is not None)
                    if any(p is not None for p in pages)
                    else None
                ),
                page_end=(
                    max(p for p in ends if p is not None)
                    if any(p is not None for p in ends)
                    else None
                ),
                slide_start=first.unit.content.slide_number,
                slide_end=group[-1].unit.content.slide_number,
                timestamp_start=first.unit.content.timestamp_start,
                timestamp_end=group[-1].unit.content.timestamp_end,
                extraction_method=first.unit.content.extraction_method,
                injection_status="sanitized",
                retrieval_allowed=True,
                metadata=metadata.model_dump(mode="json"),
            )
        )
    oversized = sum(_token_len(c.text) > policy.max_tokens for c in chunks)
    if not chunks or oversized:
        raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
    assigned = {cid for c in chunks for cid in c.content_ids}
    return chunks, ChunkQuality(
        chunks=len(chunks),
        chunk_evidence_coverage=1.0,
        unassigned_content_ids=sorted(set(lookup) - assigned),
        excessive_fragments=sum(
            _token_len(c.text) < policy.minimum_context_tokens
            and c.metadata["content_role"] == "GENERAL_CONTENT"
            for c in chunks
        ),
        oversized_chunks=oversized,
        oversized_structural_blocks=oversized_blocks,
    )
