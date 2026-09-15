"""Deterministic extractive summarization (no LLM)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List

from .heading_hints import (
    _RE_MCQ_INLINE,
    _RE_MCQ_OPTION,
    _RE_NUMERIC_ANSWER,
    _RE_SOLUTION_PHRASE,
    _RE_WATERMARK,
    is_junk_heading,
)

_RE_FIG_TABLE = re.compile(r"^(?:Fig\.?|Figure|Table)\b", re.IGNORECASE)
_RE_DOTTED_BLANK = re.compile(r"\.{3,}")
_RE_MOSTLY_SYMBOLS = re.compile(r"^[\d\s\W]+$")
_RE_PAGE_MARKER = re.compile(r"^---\s*PAGE\s+\d+\s*---$", re.IGNORECASE)
_RE_ANSWER_LINE = re.compile(
    r"^\s*(?:\d+\.\s*)?\(?[a-dA-D]\)?[\s.:]|"
    r"^\s*\d+(?:\.\d+)?\s*(?:cm|m|mm|V|A|W|s|Hz|N|J)\b",
    re.IGNORECASE,
)
_VERB_LIKE = re.compile(
    r"\b(?:is|are|was|were|has|have|had|can|will|may|show|shows|found|discovered|"
    r"conducted|proposed|known|called|revolve|emit|pass|contain|determine|explain)\b",
    re.IGNORECASE,
)


def _is_noise_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) < 8:
        return True
    if _RE_PAGE_MARKER.match(s):
        return True
    if _RE_FIG_TABLE.match(s):
        return True
    if _RE_DOTTED_BLANK.search(s):
        return True
    if _RE_WATERMARK.search(s):
        return True
    if _RE_ANSWER_LINE.match(s):
        return True
    if _RE_MCQ_OPTION.match(s):
        return True
    if _RE_MCQ_INLINE.fullmatch(s.strip("(). ")):
        return True
    is_junk, _ = is_junk_heading(s, strict=False)
    if is_junk and len(s.split()) <= 12:
        return True
    alpha = sum(1 for c in s if c.isalpha())
    if alpha < 8:
        return True
    if _RE_MOSTLY_SYMBOLS.match(s.replace(" ", "")):
        return True
    if _RE_SOLUTION_PHRASE.search(s) and len(s.split()) <= 15:
        return True
    if len(s) < 25 and not _VERB_LIKE.search(s):
        return True
    return False


def _clean_for_summary(text: str) -> str:
    if not text:
        return ""
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if _is_noise_line(s):
            continue
        # Strip inline watermark / NCERT boilerplate fragments
        s = _RE_WATERMARK.sub("", s).strip()
        if len(s) < 8:
            continue
        kept.append(s)
    return "\n".join(kept)


def _is_fragment_sentence(s: str) -> bool:
    words = s.split()
    if len(words) < 4:
        return True
    if not _VERB_LIKE.search(s):
        return True
    if s.isupper() and len(words) <= 8:
        return True
    return False


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    out = []
    for p in parts:
        p = p.strip()
        if len(p) <= 10:
            continue
        if _is_fragment_sentence(p):
            continue
        alpha_tokens = re.findall(r"[a-zA-Z]{2,}", p)
        if len(alpha_tokens) < 5:
            continue
        out.append(p)
    return out


def _top_keywords(text: str, n: int = 8) -> List[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    stop = {
        "that", "this", "with", "from", "have", "been", "were", "which",
        "their", "there", "about", "would", "could", "should", "these",
        "those", "into", "than", "then", "when", "what", "your", "also",
    }
    words = [w for w in words if w not in stop]
    if not words:
        return []
    counts = Counter(words)
    return [w for w, _ in counts.most_common(n)]


def _textrank_scores(sentences: List[str]) -> List[tuple]:
    if len(sentences) <= 1:
        return [(0, s) for s in sentences]
    word_freq: Counter = Counter()
    sent_words: List[List[str]] = []
    for s in sentences:
        words = re.findall(r"[a-zA-Z]{3,}", s.lower())
        sent_words.append(words)
        word_freq.update(words)
    if not word_freq:
        return [(i, s) for i, s in enumerate(sentences)]
    scores = []
    for i, words in enumerate(sent_words):
        if not words:
            scores.append((0.0, sentences[i]))
            continue
        tf = sum(word_freq[w] for w in words) / len(words)
        position = 1.0 - (i / max(len(sentences), 1))
        scores.append((tf * 0.7 + position * 0.3, sentences[i]))
    return sorted(scores, key=lambda x: x[0], reverse=True)


def _score_confidence(sentences: List[str], picked: List[str], keywords: List[str]) -> float:
    if not sentences or not picked:
        return 0.0
    coverage = len(" ".join(picked)) / max(len(" ".join(sentences)), 1)
    kw_signal = min(len(keywords) / 5.0, 1.0)
    length_signal = min(len(picked) / 3.0, 1.0)
    return min(1.0, coverage * 0.5 + kw_signal * 0.25 + length_signal * 0.25)


def should_use_extractive(opt=None) -> bool:
    """Return False when high quality mode forces LLM summarization."""
    from .quality_policy import prefer_llm_summaries
    return not prefer_llm_summaries(opt)


def summarize(
    text: str,
    max_sentences: int = 3,
    max_keywords: int = 8,
) -> Dict:
    cleaned = _clean_for_summary(text)
    sents = _split_sentences(cleaned)
    if not sents:
        return {"summary": "", "keywords": [], "confidence": 0.0}
    scored = _textrank_scores(sents)
    picked = [s for _, s in scored[:max_sentences]]
    summary = " ".join(picked)
    keywords = _top_keywords(cleaned or text, n=max_keywords)
    confidence = _score_confidence(sents, picked, keywords)
    return {"summary": summary, "keywords": keywords, "confidence": confidence}
