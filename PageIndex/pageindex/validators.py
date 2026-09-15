"""Semantic validation for pipeline output trees."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

JUNK_TITLE_RE = re.compile(
    r"^(?:PHYSICS|CBSE\s+Grade|NCERT|Visual\s+AI\s+Teaching|Physics\s+for\s+Everyone|Grade\s+\d+\s*\|)",
    re.IGNORECASE,
)

TITLE_ONLY_SUMMARY_RE = re.compile(
    r"^This\s+(chapter|section)\s+covers:\s*.{0,120}\.?$",
    re.IGNORECASE,
)

DOUBLED_TITLE_RE = re.compile(
    r"^([A-Za-z]{3,30})\1$",
    re.IGNORECASE,
)

_VERB_LIKE = re.compile(
    r"\b(?:is|are|was|were|has|have|had|can|will|may|show|shows|found|discovered|"
    r"conducted|proposed|known|called|revolve|emit|pass|contain|determine|explain)\b",
    re.IGNORECASE,
)

DEFAULT_FRAGMENT_MAX_RATIO = 0.40


def _is_fragment_sentence(s: str) -> bool:
    words = s.split()
    if len(words) < 4:
        return True
    if not _VERB_LIKE.search(s):
        return True
    return False


def _summary_fragment_ratio(summary: str) -> float:
    parts = re.split(r"(?<=[.!?])\s+|\n+", summary.strip())
    parts = [p.strip() for p in parts if len(p.strip()) > 8]
    if not parts:
        return 1.0
    fragments = sum(1 for p in parts if _is_fragment_sentence(p))
    return fragments / len(parts)


def _walk_nodes(structure: List[dict]) -> List[dict]:
    nodes: List[dict] = []

    def visit(node: dict) -> None:
        nodes.append(node)
        for ch in node.get("children") or node.get("nodes") or []:
            visit(ch)

    for root in structure:
        visit(root)
    return nodes


def validate_semantic_tree(
    result: dict,
    logger=None,
    fragment_max_ratio: Optional[float] = None,
) -> dict:
    """Run semantic checks; return report dict with pass/fail per check."""
    structure = result.get("structure") or []
    nodes = _walk_nodes(structure) if structure else []
    checks: Dict[str, Any] = {}
    frag_threshold = (
        fragment_max_ratio
        if fragment_max_ratio is not None
        else DEFAULT_FRAGMENT_MAX_RATIO
    )

    checks["has_hierarchy_depth"] = any(
        (n.get("children") or n.get("nodes")) for n in structure
    )

    chapters = [n for n in nodes if n.get("content_type") == "chapter"]
    checks["chapters_have_children"] = (
        not chapters
        or all((n.get("children") or n.get("nodes")) for n in chapters)
    )

    summary_nodes = [
        n for n in nodes
        if n.get("content_type") not in ("preface",)
    ]

    def _summary_ok(n: dict) -> bool:
        s = (n.get("summary") or "").strip()
        if len(s) < 30:
            return False
        if TITLE_ONLY_SUMMARY_RE.match(s):
            return False
        if _summary_fragment_ratio(s) > frag_threshold:
            return False
        return True

    checks["summaries_non_empty"] = (
        not summary_nodes
        or all(_summary_ok(n) for n in summary_nodes)
    )

    checks["summaries_not_title_only"] = (
        not summary_nodes
        or not any(TITLE_ONLY_SUMMARY_RE.match((n.get("summary") or "").strip()) for n in summary_nodes)
    )

    checks["semantic_tags_present"] = (
        not summary_nodes
        or all(n.get("semantic_tags") for n in summary_nodes)
    )

    monotonic_ok = True
    last_start = 0
    for n in nodes:
        sp = n.get("start_page") or n.get("start_index")
        ep = n.get("end_page") or n.get("end_index")
        if sp is not None and sp < last_start:
            monotonic_ok = False
        if sp is not None:
            last_start = sp
        if sp is not None and ep is not None and ep < sp:
            monotonic_ok = False
    checks["monotonic_spans"] = monotonic_ok

    checks["no_minimal_success"] = result.get("fallback") != "minimal_success"
    checks["no_junk_headings"] = not any(
        JUNK_TITLE_RE.match((n.get("title") or "").strip())
        or DOUBLED_TITLE_RE.match((n.get("title") or "").strip().replace(" ", ""))
        for n in nodes
    )

    chapter_count = len(chapters)
    adaptive_min = max(chapter_count + 1, 4) if chapter_count else 6
    checks["min_node_count"] = len(nodes) >= adaptive_min

    garbled = (
        chapter_count > 0
        and all(
            TITLE_ONLY_SUMMARY_RE.match((n.get("summary") or "").strip())
            for n in chapters
        )
    )
    checks["ocr_quality_ok"] = not garbled

    failures = [k for k, v in checks.items() if not v]
    hard_failures = [f for f in failures if f != "ocr_quality_ok"]

    report = {
        "passed": len(hard_failures) == 0,
        "checks": checks,
        "failures": hard_failures,
        "advisory": [f for f in failures if f == "ocr_quality_ok"],
        "node_count": len(nodes),
        "chapter_count": chapter_count,
        "adaptive_min_node_count": adaptive_min,
        "fragment_max_ratio": frag_threshold,
    }
    if logger:
        if hard_failures:
            logger.info({"semantic_validation_failed": hard_failures})
        else:
            logger.info({"semantic_validation": "all_passed", "node_count": len(nodes)})
    return report
