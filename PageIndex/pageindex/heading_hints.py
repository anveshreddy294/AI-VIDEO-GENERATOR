"""Tunable heading-detection hints for subsection extraction."""

from __future__ import annotations

import re
from typing import Optional, Tuple

# Recall boost: candidate containing any of these (case-insensitive) is heading-likely.
SCIENCE_HEADING_HINTS = frozenset({
    "model", "law", "experiment", "experiments", "rays", "reaction", "reactions",
    "bonding", "number", "configuration", "isotope", "isotopes", "isobars", "isotones",
    "valency", "oxidation", "reduction", "redox", "periodic", "atom", "electron",
    "proton", "neutron", "nucleus", "orbit", "shell", "radioactivity", "discovery",
    "discharge", "cathode", "anode", "molecule", "compound", "element",
})

# Reject list: lines starting with these are body/questions/captions, not headings.
JUNK_STARTERS = frozenset({
    "fig", "figure", "table", "let", "note", "activity", "analyse", "analyze",
    "complete", "write", "find", "what", "how", "why", "which", "draw", "select",
    "match", "prepare", "list", "observe", "calculate", "the", "a", "an", "in", "on",
    "see", "you", "hey", "yes", "no", "then", "when", "if", "can", "are", "is", "was",
    "element", "compound", "cation", "anion", "true", "false",
})

CONTINUATION_WORDS = frozenset({"of", "and", "in", "the", "for", "with", "to", "from", "on"})

# Single-word headings allowed when in this set (e.g. Isotopes, Isobars).
SINGLE_WORD_HEADINGS = frozenset({
    "isotopes", "isobars", "isotones", "radioactivity",
})

# Short answer-key / MCQ tokens that must never become headings.
ANSWER_KEY_STOPWORDS = frozenset({
    "yes", "no", "true", "false", "inversely", "directly", "virtual", "erect",
    "inverted", "reduced", "real", "magnified", "diminished", "behind", "front",
})

# Watermark / boilerplate fragments common in NCERT PDFs.
WATERMARK_PATTERNS = (
    r"not\s+to\s+be\s+republished",
    r"reproduce\s+distribute",
    r"retrieval\s+system",
    r"correct\s+price\s+of\s+this\s+publication",
    r"sold\s+subject\s+to\s+the\s+condition",
)

_RE_MCQ_OPTION = re.compile(
    r"^\s*(?:\(?[a-dA-D]\)?|\d+\.\s*\(?[a-dA-D]\)?)\s*\.?\s*$"
)
_RE_MCQ_INLINE = re.compile(r"\(\s*[a-dA-D]\s*\)")
_RE_NUMERIC_ANSWER = re.compile(
    r"^\s*\d+(?:\.\d+)?\s*(?:cm|m|mm|km|kg|g|mg|V|A|W|Ω|ohm|s|Hz|N|J|°C|K)\b",
    re.IGNORECASE,
)
_RE_NUMERIC_ONLY = re.compile(r"^\s*\d+(?:\.\d+)?\s*\.?\s*$")
_RE_SOLUTION_PHRASE = re.compile(
    r"\b(?:indicates|from the lens|behind the mirror|image formed|m\s*=\s*[-+]?\d|"
    r"focal length|magnification|virtual,\s*erect|real,\s*inverted|"
    r"same size as the object|inversely|directly proportional)\b",
    re.IGNORECASE,
)
_RE_UNIT_HEAVY = re.compile(
    r"(?:\d+\.?\d*\s*(?:cm|m|mm|km|kg|V|A|W|s|Hz|N|J)\b.*){2,}",
    re.IGNORECASE,
)
_RE_ANSWER_KEY_HEADER = re.compile(
    r"^(?:answers?|answer\s+key|solutions?|mcq)\b",
    re.IGNORECASE,
)
_RE_WATERMARK = re.compile("|".join(WATERMARK_PATTERNS), re.IGNORECASE)

# SCERT / NCERT front matter and TOC layout artefacts.
_RE_DOUBLED_TOC_PREFIX = re.compile(r"^\d+\.\d+\.\s+")  # e.g. "2.2. Periodic Table"
_RE_LEADING_SECTION_NUM = re.compile(r"^\d+\.\d+\.?\s*")

FRONT_MATTER_PHRASES = frozenset({
    "prepared by",
    "national anthem",
    "jana-gana-mana",
    "jana gana mana",
    "pledge",
    "dear students",
    "state council",
    "scert",
    "government of kerala",
    "department of general education",
    "typeset and design",
    "first edition",
    "printed at",
    "copyright",
    "experts",
    "textbook development team",
    "vidhyabhavan",
    "poojappura",
    "foreword",
    "preface",
    "contents",
    "table of contents",
    "continuous assessment",
    "let's assess",
    "extended activities",
})

# Person-name-only lines from credit pages (not curriculum headings).
_RE_PERSON_CREDIT = re.compile(
    r"^[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][a-z]+(?:\s+\d{4}\s*-\s*\d{4})?$"
)


def is_answer_key_page_text(text: str, *, min_signals: int = 2) -> bool:
    """Heuristic: page looks like an answer key / solution sheet."""
    if not text or len(text.strip()) < 40:
        return False
    signals = 0
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    mcq_lines = sum(1 for ln in lines if _RE_MCQ_OPTION.match(ln) or _RE_MCQ_INLINE.search(ln))
    numeric_lines = sum(1 for ln in lines if _RE_NUMERIC_ANSWER.match(ln) or _RE_NUMERIC_ONLY.match(ln))
    solution_lines = sum(1 for ln in lines if _RE_SOLUTION_PHRASE.search(ln))
    if mcq_lines >= 2:
        signals += 1
    if numeric_lines >= 3:
        signals += 1
    if solution_lines >= 2:
        signals += 1
    if _RE_ANSWER_KEY_HEADER.search(text[:500]):
        signals += 2
    short_lines = sum(1 for ln in lines if len(ln) < 35)
    if lines and short_lines / len(lines) > 0.55 and (mcq_lines + numeric_lines) >= 2:
        signals += 1
    return signals >= min_signals


def detect_textbook_content_start(page_list: list, *, max_scan: int = 40) -> int:
    """Return 1-based physical page where main textbook body likely begins."""
    markers = (
        r"\bforeword\b",
        r"\bpreface\b",
        r"\bcontents\b",
        r"\bchapter\s+\d+\b",
        r"chemical\s+reactions",
        r"national\s+council\s+of\s+educational",
        r"ncert",
        r"isbn",
    )
    compiled = [re.compile(p, re.IGNORECASE) for p in markers]
    for idx, raw in enumerate(page_list[:max_scan]):
        text = raw[0] if isinstance(raw, (tuple, list)) else (raw.get("text") or "")
        if not text:
            continue
        if is_answer_key_page_text(text, min_signals=2):
            continue
        hits = sum(1 for rx in compiled if rx.search(text[:2500]))
        if hits >= 2 or (hits >= 1 and re.search(r"chapter\s+\d+", text, re.I)):
            return idx + 1
    # Fallback: first page after consecutive answer-key pages at start
    skip = 0
    for idx, raw in enumerate(page_list[:min(10, len(page_list))]):
        text = raw[0] if isinstance(raw, (tuple, list)) else (raw.get("text") or "")
        if is_answer_key_page_text(text, min_signals=1):
            skip = idx + 1
        else:
            break
    return max(1, skip + 1)


def is_front_matter_title(title: str) -> Tuple[bool, str]:
    """Detect cover/credits/anthem lines that are not real chapters."""
    if not title:
        return True, "empty"
    s = title.strip()
    lower = s.lower()
    if _RE_PERSON_CREDIT.match(s):
        return True, "person_credit"
    for phrase in FRONT_MATTER_PHRASES:
        if phrase in lower:
            return True, "front_matter"
    if lower in {"pledge", "experts", "advisor", "chairperson", "members"}:
        return True, "front_matter_label"
    return False, ""


def normalize_chapter_title(title: str) -> str:
    """Strip SCERT doubled numbering from TOC lines (``2.2. Periodic Table`` → ``Periodic Table``)."""
    s = title.strip()
    s = _RE_DOUBLED_TOC_PREFIX.sub("", s)
    s = _RE_LEADING_SECTION_NUM.sub("", s)
    return s.strip() or title.strip()


def is_junk_heading(title: str, *, strict: bool = False) -> Tuple[bool, str]:
    """Return (is_junk, reason) for a candidate heading or TOC title."""
    if not title:
        return True, "empty"
    s = title.strip()
    if not s or "\n" in s:
        return True, "multiline_or_empty"
    if len(s) < 4:
        return True, "too_short"
    fm, fm_reason = is_front_matter_title(s)
    if fm:
        return True, fm_reason
    lower = s.lower()
    if lower in ANSWER_KEY_STOPWORDS:
        return True, "answer_stopword"
    if _RE_MCQ_OPTION.match(s):
        return True, "mcq_option"
    if _RE_NUMERIC_ONLY.match(s):
        return True, "numeric_only"
    if _RE_NUMERIC_ANSWER.match(s):
        return True, "numeric_with_units"
    if _RE_ANSWER_KEY_HEADER.match(s):
        return True, "answer_key_header"
    if _RE_SOLUTION_PHRASE.search(s) and len(s.split()) <= 22:
        return True, "solution_phrase"
    if _RE_UNIT_HEAVY.search(s):
        return True, "unit_heavy"
    if _RE_WATERMARK.search(s):
        return True, "watermark"
    if re.match(r"^\(\s*[a-dA-D]\s*\)\.?\s*$", s):
        return True, "mcq_paren"
    if re.match(r"^\d+\.\s*\([a-dA-D]\)\.?\s*$", s):
        return True, "numbered_mcq"
    # Semicolon-separated answer fragments: "6.0 cm, behind the mirror; virtual, erect"
    if ";" in s and (_RE_NUMERIC_ANSWER.search(s) or "virtual" in lower or "mirror" in lower):
        return True, "answer_fragment"
    if s.endswith(".") and len(s.split()) <= 3 and any(ch.isdigit() for ch in s):
        return True, "numbered_fragment"
    if strict and len(s) > 90 and _RE_SOLUTION_PHRASE.search(s):
        return True, "long_solution"
    return False, ""

