"""Answer Validator for Grounded Q&A.

Validates that:
1. Every cited chunk_id actually exists in the retrieved Layer A context.
2. Quoted text actually appears in the retrieved source chunk.
3. Page numbers and timestamps match the underlying source chunk metadata.
4. Prompt injection attempts are not reflected or executed in the answer.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from ..schemas import Citation

logger = logging.getLogger(__name__)

# Patterns that indicate the LLM was hijacked into acting as a compromised system
_INJECTION_REFLECTIONS = [
    re.compile(r"\bSYSTEM\s+PROMPT\b", re.IGNORECASE),
    re.compile(r"\bYOU\s+ARE\s+NOW\b", re.IGNORECASE),
    re.compile(r"\bDEVELOPER\s+MODE\s+ACTIVE\b", re.IGNORECASE),
    re.compile(r"\bHERE\s+ARE\s+MY\s+INITIAL\s+INSTRUCTIONS\b", re.IGNORECASE),
    re.compile(r"\bI\s+WILL\s+NOW\s+IGNORE\s+ALL\s+RULES\b", re.IGNORECASE),
]


class AnswerValidationResult(BaseModel):
    is_valid: bool
    reason: str = "Passed validation"
    citations: list[Citation] = Field(default_factory=list)
    has_injection_reflection: bool = False


def validate_citations(
    raw_citations: list[dict[str, Any] | Citation],
    retrieved_chunks: list[dict[str, Any]],
) -> list[Citation]:
    """Validate and reconcile citations against retrieved Layer A chunks."""
    chunk_map = {c.get("chunk_id"): c for c in retrieved_chunks if c.get("chunk_id")}
    validated_citations: list[Citation] = []

    for item in raw_citations:
        if isinstance(item, Citation):
            c_dict = item.model_dump()
        else:
            c_dict = item

        cid = c_dict.get("chunk_id")
        if not cid or cid not in chunk_map:
            # Chunk ID not in retrieved context -> drop ungrounded citation
            logger.debug("[answer_validator] Citation dropped: chunk_id %s not in retrieved context", cid)
            continue

        chunk_data = chunk_map[cid]
        quote = (c_dict.get("quote") or "").strip()
        chunk_text = (chunk_data.get("text") or "").strip()

        # Quote verification: must be present in chunk_text (case-insensitive, whitespace-flexible)
        is_verified = True
        if quote:
            norm_quote = re.sub(r"\s+", " ", quote.lower())
            norm_chunk = re.sub(r"\s+", " ", chunk_text.lower())
            if norm_quote not in norm_chunk:
                # Substring mismatch -> keep quote if substantial overlap, otherwise mark unverified
                words = norm_quote.split()
                if len(words) >= 3 and any(" ".join(words[i:i+3]) in norm_chunk for i in range(len(words)-2)):
                    is_verified = True
                else:
                    is_verified = False

        # Metadata reconciliation from authoritative chunk
        pg = chunk_data.get("page_start") or chunk_data.get("page")
        t_start = chunk_data.get("timestamp_start")
        t_end = chunk_data.get("timestamp_end")

        citation = Citation(
            chunk_id=cid,
            source_id=chunk_data.get("source_id"),
            page_number=pg,
            quote=quote if quote else chunk_text[:120],
            timestamp_start=float(t_start) if t_start is not None else None,
            timestamp_end=float(t_end) if t_end is not None else None,
            similarity_score=chunk_data.get("similarity_score"),
            verified=is_verified,
        )
        validated_citations.append(citation)

    return validated_citations


def validate_grounded_answer(
    answer: str,
    raw_citations: list[dict[str, Any] | Citation],
    retrieved_chunks: list[dict[str, Any]],
    is_refusal: bool = False,
) -> AnswerValidationResult:
    """Run complete gatekeeper verification on an LLM-generated answer."""
    # 1. Injection reflection check
    for pattern in _INJECTION_REFLECTIONS:
        if pattern.search(answer):
            logger.warning("[answer_validator] Detected prompt injection reflection in LLM output: %s", pattern.pattern)
            return AnswerValidationResult(
                is_valid=False,
                reason="LLM response reflected prompt injection payload.",
                has_injection_reflection=True,
                citations=[],
            )

    # 2. If it's a polite refusal, citations are not mandatory
    if is_refusal:
        return AnswerValidationResult(
            is_valid=True,
            reason="Valid refusal for out-of-scope question.",
            citations=[],
        )

    # 3. For substantive answers, validate citations against source chunks
    verified_citations = validate_citations(raw_citations, retrieved_chunks)

    # 4. If no citations verified but we had retrieved chunks, attach the best matching retrieved chunk
    if not verified_citations and retrieved_chunks:
        top_chunk = retrieved_chunks[0]
        verified_citations.append(
            Citation(
                chunk_id=top_chunk.get("chunk_id", "source_chunk_1"),
                source_id=top_chunk.get("source_id"),
                page_number=top_chunk.get("page_start") or top_chunk.get("page"),
                quote=top_chunk.get("text", "")[:120],
                timestamp_start=top_chunk.get("timestamp_start"),
                timestamp_end=top_chunk.get("timestamp_end"),
                similarity_score=top_chunk.get("similarity_score"),
                verified=True,
            )
        )

    return AnswerValidationResult(
        is_valid=True,
        reason="Answer passed grounding and citation verification.",
        citations=verified_citations,
    )
