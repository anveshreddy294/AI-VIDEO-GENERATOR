"""Quality-level routing: fast | balanced | high."""

from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger(__name__)

VALID_LEVELS = frozenset({"fast", "balanced", "high"})
_QUALITY_LEVEL = "fast"

_PATH_STATS: Dict[str, int] = {
    "deterministic_toc": 0,
    "llm_toc": 0,
    "deterministic_subsections": 0,
    "llm_subsections": 0,
    "extractive_summary": 0,
    "llm_summary": 0,
    "title_polish_llm": 0,
    "deterministic_fallback": 0,
}


def configure_quality_level(level: str | None) -> None:
    global _QUALITY_LEVEL
    lv = (level or "fast").strip().lower()
    if lv not in VALID_LEVELS:
        lv = "fast"
    _QUALITY_LEVEL = lv
    logger.info("quality_level=%s", lv)


def get_quality_level() -> str:
    return _QUALITY_LEVEL


def is_high_quality() -> bool:
    return _QUALITY_LEVEL == "high"


def is_balanced_or_higher() -> bool:
    return _QUALITY_LEVEL in ("balanced", "high")


def skip_deterministic_toc(opt=None) -> bool:
    if opt is not None and getattr(opt, "skip_deterministic_toc", None):
        return str(opt.skip_deterministic_toc).lower() in ("yes", "true", "1")
    return _QUALITY_LEVEL == "high"


def prefer_llm_summaries(opt=None) -> bool:
    if opt is not None and getattr(opt, "force_llm_summaries", None):
        return str(opt.force_llm_summaries).lower() in ("yes", "true", "1")
    return _QUALITY_LEVEL == "high"


def force_llm_subsections(opt=None) -> bool:
    if opt is not None and getattr(opt, "force_llm_subsections", None):
        return str(opt.force_llm_subsections).lower() in ("yes", "true", "1")
    return _QUALITY_LEVEL == "high"


def force_title_polish(opt=None) -> bool:
    if opt is not None and getattr(opt, "force_title_polish", None):
        return str(opt.force_title_polish).lower() in ("yes", "true", "1")
    return _QUALITY_LEVEL == "high"


def junk_filter_strict(opt=None) -> bool:
    if opt is not None and getattr(opt, "junk_filter_strict", None) is not None:
        return str(opt.junk_filter_strict).lower() in ("yes", "true", "1")
    # Always strict — high mode previously relaxed this and let front matter through.
    return True


def record_path(name: str, count: int = 1) -> None:
    _PATH_STATS[name] = _PATH_STATS.get(name, 0) + count


def reset_path_stats() -> None:
    global _PATH_STATS
    _PATH_STATS = {k: 0 for k in _PATH_STATS}


def path_stats() -> Dict[str, int]:
    return dict(_PATH_STATS)


def log_quality_path_summary(*, quality_level: str | None = None) -> None:
    lv = quality_level or _QUALITY_LEVEL
    det = (
        _PATH_STATS.get("deterministic_toc", 0)
        + _PATH_STATS.get("deterministic_subsections", 0)
        + _PATH_STATS.get("extractive_summary", 0)
        + _PATH_STATS.get("deterministic_fallback", 0)
    )
    llm = (
        _PATH_STATS.get("llm_toc", 0)
        + _PATH_STATS.get("llm_subsections", 0)
        + _PATH_STATS.get("llm_summary", 0)
        + _PATH_STATS.get("title_polish_llm", 0)
    )
    msg = (
        f"quality_paths level={lv} deterministic_calls={det} llm_calls={llm} "
        f"detail={dict(_PATH_STATS)}"
    )
    print(f"[PageIndex] {msg}", flush=True)
    logger.info(msg)
