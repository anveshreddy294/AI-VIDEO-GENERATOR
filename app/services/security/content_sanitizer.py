"""Prompt-Injection Quarantine & Content Sanitization Engine.

Scans extracted educational text for prompt-injection attacks, hidden payloads,
and system overrides before semantic chunking and Layer A indexing.
Quarantined segments are excluded from retrieval and never embedded.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from ..ingestion.normalizer import NormalizedContentRecord


class SanitizedContent(BaseModel):
    """Sanitized representation of an ingested content unit."""

    segment_id: str = Field(default_factory=lambda: f"SAN_{uuid4().hex[:12]}")
    content_id: str
    source_id: str
    source_version: str = "v1"
    original_text: str
    sanitized_text: str
    original_text_hash: str
    injection_status: Literal["clean", "sanitized", "quarantined"] = "clean"
    risk_score: float = 0.0
    risk_reasons: list[str] = Field(default_factory=list)
    retrieval_allowed: bool = True
    page_start: int | None = None
    page_end: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# High-risk patterns that directly signal adversarial instruction override attempts
INJECTION_OVERRIDE_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|directives|commands)", "instruction_override"),
    (r"disregard\s+(the\s+)?(system\s+prompt|all\s+prior|previous)\b", "instruction_override"),
    (r"reveal\s+(your\s+)?(instructions|system\s+prompt|hidden\s+prompt|secret)", "system_prompt_extraction"),
    (r"show\s+(your\s+)?(hidden\s+prompt|initial\s+instructions|system\s+message)", "system_prompt_extraction"),
    (r"you\s+are\s+now\s+(a\s+different\s+assistant|DAN|in\s+developer\s+mode|unrestricted)", "role_switching"),
    (r"act\s+as\s+(an\s+unrestricted|DAN|a\s+malicious|a\s+different\s+ai)", "role_switching"),
    (r"(delete|drop)\s+(the\s+)?(database|table|all\s+files|filesystem)\b", "destructive_command"),
    (r"call\s+(this\s+)?tool\s*[:(]", "tool_hijacking"),
    (r"send\s+(this\s+)?message\s+(to|via)\b", "unauthorized_communication"),
    (r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "embedded_script"),
    (r"system\s+message\s*:\s*you\s+must", "system_spoofing"),
    (r"developer\s+instructions\s*:\s*ignore", "developer_spoofing"),
]

# Obfuscation and hidden markup patterns
HIDDEN_PAYLOAD_PATTERNS: list[tuple[str, str]] = [
    (r"<!--[\s\S]*?-->", "hidden_html_comment"),
    (r"display\s*:\s*none", "hidden_css_display_none"),
    (r"visibility\s*:\s*hidden", "hidden_css_visibility"),
    (r"color\s*:\s*(#fff(fff)?|white)\s*;\s*background(-color)?\s*:\s*(#fff(fff)?|white)", "white_on_white_text"),
    (r"font-size\s*:\s*0px", "zero_font_size_text"),
]


def _normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFKC and strip invisible zero-width characters."""
    normalized = unicodedata.normalize("NFKC", text)
    # Remove zero-width spaces, joiners, markers
    zero_width_chars = [
        "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
        "\ufeff", "\u2060", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e"
    ]
    for ch in zero_width_chars:
        normalized = normalized.replace(ch, "")
    return normalized


def sanitize_text(text: str) -> tuple[str, Literal["clean", "sanitized", "quarantined"], list[str], float, bool]:
    """Inspect text for prompt injection and structural hidden payloads.

    Returns:
        (sanitized_text, injection_status, risk_reasons, risk_score, retrieval_allowed)
    """
    if not text or not text.strip():
        return "", "clean", [], 0.0, True

    raw = text.strip()
    norm = _normalize_unicode(raw)
    norm_lower = norm.lower()
    risk_reasons: list[str] = []
    risk_score = 0.0

    # 1. Check direct prompt injection overrides
    for pattern, reason in INJECTION_OVERRIDE_PATTERNS:
        if re.search(pattern, norm_lower, re.IGNORECASE | re.DOTALL):
            if reason not in risk_reasons:
                risk_reasons.append(reason)
            risk_score += 0.8

    # 2. Check hidden HTML / CSS / tracking markup
    had_hidden_markup = False
    cleaned_markup_text = norm
    for pattern, reason in HIDDEN_PAYLOAD_PATTERNS:
        matches = list(re.finditer(pattern, cleaned_markup_text, re.IGNORECASE))
        if matches:
            had_hidden_markup = True
            # Extract content inside comment or tag to see if it has injection commands
            for m in matches:
                matched_str = m.group(0).lower()
                for inj_pattern, inj_reason in INJECTION_OVERRIDE_PATTERNS:
                    if re.search(inj_pattern, matched_str):
                        if inj_reason not in risk_reasons:
                            risk_reasons.append(f"hidden_{inj_reason}")
                        risk_score += 1.0

            # Strip the hidden markup
            cleaned_markup_text = re.sub(pattern, " ", cleaned_markup_text, flags=re.IGNORECASE)
            if reason not in risk_reasons:
                risk_reasons.append(reason)
            risk_score += 0.3

    # Clean residual script and style tags safely
    cleaned_markup_text = re.sub(r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>", " ", cleaned_markup_text, flags=re.IGNORECASE)
    cleaned_markup_text = re.sub(r"<\s*style[^>]*>[\s\S]*?<\s*/\s*style\s*>", " ", cleaned_markup_text, flags=re.IGNORECASE)

    # 3. Decision threshold
    if risk_score >= 0.7 or any("override" in r or "extraction" in r or "destructive" in r or "hijacking" in r or "spoofing" in r for r in risk_reasons):
        # Quarantine: Content represents an adversarial instruction
        return (
            "",  # Quarantined text is scrubbed from the retrievable copy
            "quarantined",
            risk_reasons,
            min(1.0, risk_score),
            False,  # retrieval_allowed = False
        )

    # 4. If benign hidden tags or HTML entities were stripped
    cleaned_text = html.unescape(cleaned_markup_text)
    # Collapse multiple whitespaces
    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
    cleaned_text = re.sub(r"\n\s*\n+", "\n\n", cleaned_text).strip()

    if had_hidden_markup or cleaned_text != raw:
        return (
            cleaned_text,
            "sanitized",
            risk_reasons,
            min(1.0, risk_score),
            True,  # retrieval_allowed = True
        )

    # Completely normal educational content
    return (
        raw,
        "clean",
        [],
        0.0,
        True,
    )


def sanitize_ingested_content(record: NormalizedContentRecord) -> SanitizedContent:
    """Sanitize a normalized content unit, generating audit provenance and quarantine state."""
    raw_text = record.extracted_text or record.raw_text or ""
    orig_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    sanitized_text, status, reasons, score, allowed = sanitize_text(raw_text)

    return SanitizedContent(
        content_id=record.content_id,
        source_id=record.source_id,
        source_version=record.source_version,
        original_text=raw_text,
        sanitized_text=sanitized_text,
        original_text_hash=orig_hash,
        injection_status=status,
        risk_score=score,
        risk_reasons=reasons,
        retrieval_allowed=allowed,
        page_start=record.page_number,
        page_end=record.page_number,
        timestamp_start=record.timestamp_start,
        timestamp_end=record.timestamp_end,
        metadata={
            "content_type": record.content_type,
            "modality": record.modality,
            "heading_path": record.heading_path,
            "speaker": record.speaker,
            "chapter": record.chapter,
            "section": record.section,
        },
    )


def sanitize_content_records(records: list[NormalizedContentRecord]) -> list[SanitizedContent]:
    """Batch sanitize multiple normalized records for a source."""
    return [sanitize_ingested_content(r) for r in records]
