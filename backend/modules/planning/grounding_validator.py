"""Lightweight post-LLM grounding validator.

Checks that storyboard scene titles and anchor examples contain at least one
significant word that also appears in the retrieved curriculum content.

This catches cases where the LLM hallucinated scene content that has no
connection to the retrieved textbook sections — a clear signal that retrieval
was wrong or the LLM ignored grounding instructions.
"""
from __future__ import annotations

import re
from typing import Any

_STOP_WORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "into",
    "about", "over", "under", "when", "where", "what", "which",
    "have", "been", "will", "would", "could", "should", "does",
    "more", "than", "they", "them", "their", "also", "some",
})


def _content_corpus(curriculum_sections: list[dict[str, Any]]) -> str:
    """Build a lowercase corpus from all retrieved section text + summaries."""
    parts = []
    for sec in curriculum_sections:
        parts.append((sec.get("content") or "").lower())
        parts.append((sec.get("summary") or "").lower())
        parts.append(" ".join(sec.get("keywords") or []).lower())
        parts.append(" ".join(sec.get("semantic_tags") or []).lower())
    return " ".join(parts)


def _significant_words(text: str) -> set[str]:
    """Extract 4+-char non-stop words from text."""
    return {
        w for w in re.findall(r"\b[a-z]{4,}\b", text.lower())
        if w not in _STOP_WORDS
    }


def validate_storyboard_grounding(
    storyboard: list[dict[str, Any]],
    curriculum_sections: list[dict[str, Any]],
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Check each storyboard scene for curriculum overlap.

    Returns a list of issue dicts (empty = all scenes passed).
    Each issue has: scene_id, title, issue, words_checked.

    Args:
        storyboard: List of scene dicts from build_storyboard.
        curriculum_sections: Matched sections from retrieve_curriculum_sections.
        strict: If True, flag scenes with <2 overlapping words instead of 0.
    """
    if not curriculum_sections:
        return []

    corpus = _content_corpus(curriculum_sections)
    issues: list[dict[str, Any]] = []
    threshold = 1 if not strict else 2

    for scene in storyboard:
        sid = scene.get("scene_id")
        # Skip bookend scenes — intro/summary titles are always generic.
        template = scene.get("concept_template", "")
        if template in ("intro", "summary"):
            continue

        title = (scene.get("title") or "").lower()
        anchor = (scene.get("anchor_example") or "").lower()
        combined = f"{title} {anchor}"

        words = _significant_words(combined)
        hits = sum(
            1 for w in words
            if re.search(r"\b" + re.escape(w) + r"\b", corpus)
        )

        if words and hits < threshold:
            issues.append({
                "scene_id": sid,
                "title": scene.get("title"),
                "template": template,
                "issue": "no_curriculum_overlap" if hits == 0 else "low_curriculum_overlap",
                "hits": hits,
                "words_checked": sorted(words)[:10],
            })

    return issues


def log_grounding_issues(
    issues: list[dict[str, Any]],
    logger: Any,
    topic: str = "",
) -> None:
    """Log grounding issues at WARNING level."""
    if not issues:
        logger.info("Grounding validation passed for all scenes (topic=%r)", topic)
        return
    for issue in issues:
        logger.warning(
            "Grounding issue scene=%d template=%r title=%r issue=%s hits=%d words=%s",
            issue["scene_id"],
            issue.get("template"),
            issue["title"],
            issue["issue"],
            issue.get("hits", 0),
            issue.get("words_checked", []),
        )
