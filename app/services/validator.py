"""Quality Validation Gateway for Step 1 Ingestion Pipeline.

Verifies File, ContentUnit, Chunk, Concept, and Storage levels before
marking a source status as READY.
"""

import logging
from pathlib import Path
from typing import Any

from .schemas import ContentUnit, KnowledgeGraph, RichChunk, SourceRecord

logger = logging.getLogger(__name__)


class ValidationFailed(Exception):
    """Raised when quality validation fails at any stage."""

    pass


def validate_ingestion_quality(
    record: SourceRecord,
    file_path: Path,
    units: list[ContentUnit],
    kg: KnowledgeGraph,
    chunks: list[RichChunk],
    upserted_count: int,
) -> dict[str, Any]:
    """Run full validation checks across file, content, chunk, concept, and storage layers."""
    report: dict[str, Any] = {
        "source_id": record.source_id,
        "asset_id": record.asset_id,
        "checks": {},
        "passed": False,
    }

    # 1. File Level Validation
    if not file_path.exists():
        raise ValidationFailed(f"File level failure: Persistent file missing at {file_path}")
    if file_path.stat().st_size == 0:
        raise ValidationFailed("File level failure: Original file is 0 bytes.")
    report["checks"]["file_level"] = "PASSED"

    # 2. Content Level Validation
    if not units:
        raise ValidationFailed("Content level failure: No ContentUnits extracted.")
    unit_ids = {u.content_id for u in units}
    if len(unit_ids) != len(units):
        raise ValidationFailed("Duplicate content IDs")
    for cu in units:
        if not cu.text.strip() or cu.confidence_score <= 0 or cu.source_id != record.source_id or cu.asset_id != record.asset_id:
            raise ValidationFailed("Empty, failed, or mismatched content unit")
        if not cu.content_id or not cu.source_id or not cu.asset_id:
            raise ValidationFailed(f"Content level failure: ContentUnit {cu} missing essential IDs.")
        if cu.modality in ("pdf", "image") and cu.page_number is None and cu.modality == "pdf":
            raise ValidationFailed(f"Content level failure: PDF ContentUnit {cu.content_id} missing page_number.")
    report["checks"]["content_level"] = f"PASSED ({len(units)} ContentUnits)"

    # 3. Chunk Level Validation
    if not chunks:
        raise ValidationFailed("Chunk level failure: No RichChunks created.")
    for ch in chunks:
        if not ch.text.strip() or ch.source_id != record.source_id or ch.asset_id != record.asset_id or not set(ch.content_ids).issubset(unit_ids):
            raise ValidationFailed("Invalid chunk text or provenance")
        if not ch.chunk_id or not ch.source_id or not ch.asset_id:
            raise ValidationFailed(f"Chunk level failure: Chunk {ch} missing essential IDs.")
        if ch.layer != "A":
            raise ValidationFailed(f"Chunk level failure: Chunk {ch.chunk_id} layer is not 'A'.")
        if not ch.content_ids:
            raise ValidationFailed(f"Chunk level failure: Chunk {ch.chunk_id} has no provenance content_ids.")
    report["checks"]["chunk_level"] = f"PASSED ({len(chunks)} Chunks)"

    # 4. Concept Level Validation
    if not kg.concepts:
        raise ValidationFailed("Knowledge graph has no concepts")
    for cid, concept in kg.concepts.items():
        if not concept.source_content_ids or not set(concept.source_content_ids).issubset(unit_ids):
            raise ValidationFailed("Concept has missing or invalid content references")
        if not set(concept.prerequisite_concept_ids).issubset(kg.concepts):
            raise ValidationFailed("Concept has unknown prerequisites")
        if not concept.concept_id or not concept.name:
            raise ValidationFailed(f"Concept level failure: Concept node {cid} missing ID or name.")
        if not concept.source_content_ids:
            logger.warning("[validator] Concept %s (%s) has no source_content_ids mapping.", concept.name, cid)
    report["checks"]["concept_level"] = f"PASSED ({len(kg.concepts)} Concepts)"

    # 5. Storage Level Validation
    if upserted_count != len(chunks):
        raise ValidationFailed(
            f"Storage level failure: Qdrant upserted {upserted_count} points, expected {len(chunks)}."
        )
    report["checks"]["storage_level"] = f"PASSED ({upserted_count} Qdrant points)"

    report["passed"] = True
    return report


class ExtractionQualityError(Exception):
    """Raised when extracted content fails the extraction quality gate."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def validate_extraction_quality(
    units: list[ContentUnit],
    modality: str = "",
) -> tuple[bool, str, str]:
    """Inspect extracted ContentUnits for semantic validity before structuring.

    Rejects:
    - Empty content or whitespace
    - Corrupted or OCR garbage text
    - Generic metadata only (filenames, MIME types, storage paths, image placeholders)
    - Extraction error strings
    - Extremely low meaningful-text content

    Accepts:
    - Legitimate short educational inputs with meaningful domain vocabulary.

    Returns:
        (is_valid, status_code, failure_reason)
        status_code: 'PASSED', 'EXTRACTION_FAILED', or 'EXTRACTION_INSUFFICIENT'
    """
    import re

    if not units:
        return (
            False,
            "EXTRACTION_FAILED",
            "No extractable text or content units were extracted from the source.",
        )

    # Accumulate all extracted text
    combined_texts: list[str] = []
    for u in units:
        t = (u.text or "").strip()
        # If image, also check visual_description
        if u.modality == "image" and getattr(u, "visual_description", None):
            v_desc = (u.visual_description or "").strip()
            if v_desc:
                t = v_desc
        # Strip header markers like [IMAGE: ...]
        clean_t = re.sub(r"^\[IMAGE:[^\]]+\]\s*", "", t, flags=re.IGNORECASE).strip()
        if clean_t:
            combined_texts.append(clean_t)

    if not combined_texts:
        return (
            False,
            "EXTRACTION_FAILED",
            "Extraction produced only empty whitespace or empty content units.",
        )

    full_text = "\n\n".join(combined_texts).strip()

    # 1. Check for extraction error strings
    error_patterns = [
        r"^(error|failed to extract|extraction failed|unsupported format|corrupted file|could not read)",
        r"^traceback \(most recent call last\):",
    ]
    for pat in error_patterns:
        if re.search(pat, full_text[:200], re.IGNORECASE):
            return (
                False,
                "EXTRACTION_FAILED",
                f"Source extraction failed with error: {full_text[:120]}",
            )

    # 2. Check for synthetic image placeholder text
    synthetic_placeholder_pattern = (
        r"^Image asset for '[^']+'\.\s*Visual study reference material from uploaded media\.?$"
    )
    if re.match(synthetic_placeholder_pattern, full_text.strip(), re.IGNORECASE):
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "Extraction yielded only an unresolved image placeholder without educational content.",
        )

    # 3. Check if content consists purely of metadata (filenames, MIME types, file paths)
    # Strip paths, mime types, filenames, timestamps
    metadata_scrubbed = full_text
    metadata_scrubbed = re.sub(r"(?:[a-zA-Z]:)?[\\/]?[\w\.\-]+(?:[\\/][\w\.\-]+)+", " ", metadata_scrubbed)
    metadata_scrubbed = re.sub(r"\b(application|image|video|text|audio)/[a-zA-Z0-9_\.\-]+\b", " ", metadata_scrubbed)
    metadata_scrubbed = re.sub(r"\b[a-zA-Z0-9_\-]+\.(pdf|png|jpg|jpeg|txt|mp4|mov|mkv)\b", " ", metadata_scrubbed, flags=re.IGNORECASE)
    metadata_scrubbed = re.sub(r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)?\b", " ", metadata_scrubbed)
    metadata_scrubbed = re.sub(r"[\s\-_:=]+", " ", metadata_scrubbed).strip()

    if (len(metadata_scrubbed) < 10 or len(re.findall(r"[A-Za-z]{3,}", metadata_scrubbed)) < 3) and len(full_text.split()) <= 12:
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "Source contains only generic metadata, file paths, or MIME types.",
        )

    # 4. Check for genuine extraction corruption, encoding faults, and OCR noise
    # Standard formatting (whitespace runs, dashes, underscores, dots, separators, tables) must pass.

    # 4A. Unicode replacement character corruption (e.g. \ufffd, )
    replacement_count = full_text.count("\ufffd")
    if replacement_count >= 3 or (len(full_text) > 10 and (replacement_count / len(full_text)) > 0.05):
        logger.warning(
            "[validator] Extraction failed: reason_code=UNICODE_REPLACEMENT_CORRUPTION, modality=%s, "
            "units_count=%d, replacement_count=%d, total_chars=%d",
            modality, len(units), replacement_count, len(full_text),
        )
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "The extracted text appears corrupted with unreadable character encoding. Try another file or retry extraction.",
        )

    # 4B. NUL and raw control characters (except standard whitespace \t, \n, \r)
    nul_count = full_text.count("\x00")
    if nul_count >= 2:
        logger.warning(
            "[validator] Extraction failed: reason_code=NUL_BYTE_CORRUPTION, modality=%s, "
            "units_count=%d, nul_count=%d",
            modality, len(units), nul_count,
        )
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "The extracted text contains binary NUL bytes from a corrupted stream or file.",
        )

    bad_controls = len(re.findall(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", full_text))
    if bad_controls > 5:
        logger.warning(
            "[validator] Extraction failed: reason_code=CONTROL_CHARACTER_CORRUPTION, modality=%s, "
            "units_count=%d, bad_controls=%d",
            modality, len(units), bad_controls,
        )
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "The extracted text contains excessive non-printable control characters.",
        )

    # 4C. Extreme repeated alphanumeric garbage (e.g., 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '111111111111111111111111111111')
    # Normal words like 'coooooool' (6 'o's) pass; threshold >= 25 consecutive identical alphanumeric chars
    alphanumeric_repeat_match = re.search(r"([a-zA-Z0-9])\1{24,}", full_text)
    if alphanumeric_repeat_match:
        bad_char = alphanumeric_repeat_match.group(1)
        seq_len = len(alphanumeric_repeat_match.group(0))
        logger.warning(
            "[validator] Extraction failed: reason_code=EXTREME_ALPHANUMERIC_REPEAT, modality=%s, "
            "units_count=%d, bad_char=%r, codepoint=U+%04X, seq_length=%d",
            modality, len(units), bad_char, ord(bad_char), seq_len,
        )
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "Extracted content contains repeated garbage character sequences.",
        )

    # 4D. Extreme repeated non-formatting symbol garbage (e.g., '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
    # Standard separators (spaces, tabs, -, _, =, ., *, #, ~, +, |, /, \, :, ;, <, >, [, ], (, ), {, }, ", ') pass.
    noise_repeat_match = re.search(r"([^a-zA-Z0-9\s\-_=.*#~+|/\\:;<>\[\](){}\"'─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬])\1{14,}", full_text)
    if noise_repeat_match:
        bad_char = noise_repeat_match.group(1)
        seq_len = len(noise_repeat_match.group(0))
        logger.warning(
            "[validator] Extraction failed: reason_code=EXTREME_NOISE_SYMBOL_REPEAT, modality=%s, "
            "units_count=%d, bad_char=%r, codepoint=U+%04X, seq_length=%d",
            modality, len(units), bad_char, ord(bad_char), seq_len,
        )
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "Extracted content contains unreadable OCR garbage or excessive non-text symbols.",
        )

    # 4E. High nonsensical-symbol density check
    unusual_symbols = len(re.findall(r"[^A-Za-z0-9\s.,!?:;'\-_=*#~+/\\|<>\[\](){}%$&@^\"`]", full_text))
    total_chars = max(1, len(full_text))
    if unusual_symbols / total_chars > 0.40 and total_chars > 30:
        logger.warning(
            "[validator] Extraction failed: reason_code=HIGH_SYMBOL_DENSITY, modality=%s, "
            "units_count=%d, unusual_symbols=%d, total_chars=%d, density=%.2f",
            modality, len(units), unusual_symbols, total_chars, unusual_symbols / total_chars,
        )
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "Extracted content contains unreadable OCR garbage or excessive non-text symbols.",
        )

    # 5. Semantic token density check
    # Extract distinct alphabetical words with length >= 3
    words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", full_text)]
    if not words:
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "No meaningful educational words found in extracted source.",
        )

    # Check token diversity: if repetitive tokens (e.g., 'asdf asdf asdf asdf')
    unique_words = set(words)
    if len(words) >= 8 and len(unique_words) <= 2:
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "Extracted content consists of repetitive token gibberish.",
        )

    # Minimum threshold: allow short legitimate educational inputs (e.g., 4+ meaningful words)
    # but reject inputs with fewer than 4 educational tokens
    if len(words) < 4:
        return (
            False,
            "EXTRACTION_INSUFFICIENT",
            "Extracted content is too sparse to support educational concepts (under 4 meaningful words).",
        )

    return True, "PASSED", "Content meets extraction quality standards."

