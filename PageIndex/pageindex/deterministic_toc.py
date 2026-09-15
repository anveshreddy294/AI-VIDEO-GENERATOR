"""Regex + line-layout TOC parser (no LLM)."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

TOC_LINE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<num>(?:\d+(?:\.\d+)*)|[A-Z]\.|[IVXLCM]+\.)?\s*"
    r"(?P<title>[^\.\d\n].{0,200}?)"
    r"(?:[\.\s]{2,}|\t+)"
    r"(?P<page>\d{1,4})\s*$",
    re.MULTILINE,
)

TOC_LINE_ALT = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<num>(?:\d+(?:\.\d+)*)|[A-Z]\.)?\s*"
    r"(?P<title>.{2,120}?)\s+(\.{2,}|\t+)\s*(?P<page>\d{1,4})\s*$",
    re.MULTILINE,
)

# Matches "N. Title  M" and "N. Title M" — no dot-leader, plain space(s) before page number.
# Requires the chapter number prefix so we don't match random body sentences.
TOC_LINE_SIMPLE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<num>\d+(?:\.\d+)*)\.\s+"
    r"(?P<title>.{2,120}?)\s{1,10}"
    r"(?P<page>\d{1,4})\s*$",
    re.MULTILINE,
)

_RE_NUM_ONLY = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*$")
_RE_PAGE_ONLY = re.compile(r"^\s*(\d{1,4})\s*$")
_RE_TOC_HEADER = re.compile(r"\bTABLE\s+OF\s+CONTENTS\b", re.IGNORECASE)
_RE_CONTENTS_HEADER = re.compile(r"contents", re.IGNORECASE)

_JUNK_TITLES = re.compile(
    r"^(?:PHYSICS|CBSE\s+Grade|NCERT|Visual\s+AI\s+Teaching|Physics\s+for\s+Everyone|Grade\s+\d+)",
    re.IGNORECASE,
)

_RE_DOUBLED_DOTS = re.compile(r"(\.{2,})\s+\1")
_RE_DOUBLED_STRUCT_PREFIX = re.compile(r"^(\d+)\.\1\.")


def _dedup_repeated_half(text: str) -> str:
    """If text is an exact doubled string (e.g. 'Contentscontents'), return first half."""
    t = text.strip()
    if len(t) >= 6 and len(t) % 2 == 0:
        half = len(t) // 2
        if t[:half].lower() == t[half:].lower():
            return t[:half]
    return t


def _dedup_toc_line(line: str) -> str:
    """Normalize one TOC line with doubled-text PDF artefacts (SCERT Chemistry layout)."""
    if not line.strip():
        return line

    line = _RE_DOUBLED_DOTS.sub(r"\1", line)

    stripped = line.strip()
    if stripped and not re.search(r"\d", stripped):
        line = _dedup_repeated_half(stripped)

    line = _RE_DOUBLED_STRUCT_PREFIX.sub(r"\1.", line)

    m = re.match(r"^(\s*)(\d+(?:\.\d+)*\.)\s*(.*)$", line)
    if m:
        prefix, num_part, rest = m.group(1), m.group(2), m.group(3)
        page_m = re.search(r"([\.\s]{2,}|\t+)\s*(\d{1,4})\s*$", rest)
        if page_m:
            title_part = rest[: page_m.start()].strip()
            suffix = rest[page_m.start() :]
            title_part = _dedup_repeated_half(title_part)
            if len(title_part) >= 6:
                half = len(title_part) // 2
                if title_part[:half].lower() == title_part[half:].lower():
                    title_part = title_part[:half]
            line = f"{prefix}{num_part} {title_part}{suffix}"
        else:
            rest_dedup = _dedup_repeated_half(rest.strip())
            line = f"{prefix}{num_part} {rest_dedup}"

    line = re.sub(r"(\d{1,3})\1\s*$", r"\1", line)
    line = re.sub(r"^(\s*)(\d+(?:\.\d+)*)\.(?=[A-Za-z])", r"\1\2. ", line)
    return line


def _dedup_toc_text(text: str) -> str:
    return "\n".join(_dedup_toc_line(ln) for ln in text.splitlines())


def _filter_entries_by_max_pages(entries: List[dict], max_pages: int) -> List[dict]:
    if max_pages <= 0:
        return entries
    return [e for e in entries if (e.get("page_number") or 0) <= max_pages]


def _indent_level(indent: str) -> int:
    return len(indent.expandtabs(4))


def _structure_level(num: str) -> int:
    if not num:
        return 1
    return len(num.strip().rstrip(".").split("."))


def _normalize_num(num: str) -> str:
    return num.strip().rstrip(".")


_LEADING_SEP = re.compile(r"^[\.\)\-\:\|\s]+")
_TRAILING_DOTS = re.compile(r"[\.\s]+$")


def _clean_title(title: str) -> str:
    """Strip leading/trailing punctuation artefacts (e.g. '. Title .........')."""
    title = _LEADING_SEP.sub("", title)
    title = _TRAILING_DOTS.sub("", title)
    return title.strip()


def _make_entry(num: str, title: str, page_num: int, indent: int = 0) -> dict:
    num = _normalize_num(num)
    return {
        "structure": num or None,
        "title": _clean_title(title),
        "page_number": page_num,
        "level": _structure_level(num) if num else 1,
        "indent": indent,
    }


def _parse_layout_a(text: str) -> List[dict]:
    entries: List[dict] = []
    for pattern in (TOC_LINE, TOC_LINE_ALT, TOC_LINE_SIMPLE):
        found: List[dict] = []
        for m in pattern.finditer(text):
            title = (m.group("title") or "").strip()
            if not title or len(title) < 2 or _JUNK_TITLES.match(title):
                continue
            try:
                page_num = int(m.group("page"))
            except (TypeError, ValueError):
                continue
            num = (m.group("num") or "").strip().rstrip(".")
            found.append(_make_entry(num, title, page_num, _indent_level(m.group("indent") or "")))
        if len(found) > len(entries):
            entries = found
    return entries


def _parse_layout_b_vertical_triplet(text: str) -> List[dict]:
    """Number line / title line / page line (science_grade5.pdf layout)."""
    lines = [ln.strip() for ln in text.splitlines()]
    entries: List[dict] = []
    i = 0
    while i < len(lines) - 2:
        m_num = _RE_NUM_ONLY.match(lines[i])
        if not m_num:
            i += 1
            continue
        num = m_num.group(1)
        title = lines[i + 1].strip()
        m_page = _RE_PAGE_ONLY.match(lines[i + 2])
        if not title or len(title) < 2 or not m_page or _JUNK_TITLES.match(title):
            i += 1
            continue
        try:
            page_num = int(m_page.group(1))
        except ValueError:
            i += 1
            continue
        entries.append(_make_entry(num, title, page_num))
        i += 3
    return entries


def _parse_layout_c_title_page(text: str) -> List[dict]:
    """Section number optional on title line; page on following line."""
    lines = [ln.strip() for ln in text.splitlines()]
    entries: List[dict] = []
    i = 0
    while i < len(lines) - 1:
        line = lines[i]
        m_page = _RE_PAGE_ONLY.match(lines[i + 1])
        if not m_page:
            i += 1
            continue
        m_inline = re.match(
            r"^\s*((?:\d+(?:\.\d+)*)\s+)?(.{2,120}?)\s*$",
            line,
        )
        if not m_inline:
            i += 1
            continue
        num = (m_inline.group(1) or "").strip()
        title = (m_inline.group(2) or "").strip()
        if not title or len(title) < 2 or _JUNK_TITLES.match(title):
            i += 1
            continue
        try:
            page_num = int(m_page.group(1))
        except ValueError:
            i += 1
            continue
        entries.append(_make_entry(num, title, page_num))
        i += 2
    return entries


def parse_toc(text: str, max_pages: int = 9999) -> Tuple[List[dict], float]:
    text = _dedup_toc_text(text)
    best_entries: List[dict] = []
    best_confidence = 0.0
    for parser in (_parse_layout_a, _parse_layout_b_vertical_triplet, _parse_layout_c_title_page):
        entries = _filter_entries_by_max_pages(parser(text), max_pages)
        if len(entries) < 2:
            continue
        confidence = _toc_confidence(entries, text, max_pages=max_pages)
        if confidence > best_confidence or len(entries) > len(best_entries):
            best_entries = entries
            best_confidence = confidence
    best_entries = _filter_entries_by_max_pages(best_entries, max_pages)
    return best_entries, best_confidence


def find_toc_page_index(page_texts: List[str], max_scan: int = 20) -> Optional[int]:
    """Return 0-based index of page containing TABLE OF CONTENTS or CONTENTS."""
    for i, text in enumerate(page_texts[:max_scan]):
        if not text:
            continue
        if _RE_TOC_HEADER.search(text):
            return i
        if _RE_CONTENTS_HEADER.search(text[:800]):
            return i
    return None


def _toc_confidence(entries: List[dict], text: str, max_pages: int = 9999) -> float:
    entries = _filter_entries_by_max_pages(entries, max_pages)
    if len(entries) < 3:
        return 0.0
    lines = [ln for ln in text.splitlines() if ln.strip()]
    density = len(entries) / max(len(lines), 1)
    pages = [e["page_number"] for e in entries if e.get("page_number")]
    monotonic = 0.0
    if len(pages) >= 2:
        inc = sum(1 for i in range(1, len(pages)) if pages[i] >= pages[i - 1])
        monotonic = inc / (len(pages) - 1)
    levels = [e.get("level", 1) for e in entries]
    level_var = len(set(levels)) / max(len(levels), 1)
    score = min(1.0, density * 8 * 0.25 + monotonic * 0.35 + min(level_var, 1.0) * 0.25)
    lower = text.lower()
    if _RE_TOC_HEADER.search(text[:800]) or "contents" in lower[:500]:
        score = min(1.0, score + 0.25)
    structures = [e.get("structure") for e in entries if e.get("structure")]
    if len(structures) >= 3:
        score = min(1.0, score + 0.10)
    return score
