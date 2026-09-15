"""Per-stage Ollama model routing.

Quality / max-quality inference order (when hybrid NVIDIA is enabled):
  1. NVIDIA NIM (cloud) for configured nvidia_stages
  2. Local Ollama ``qwen2.5:3b`` — never ``qwen2.5-coder:7b`` by default
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Default local model for every stage in normal (fast) mode.
STAGE_MODEL_MAP: Dict[str, str] = {
    "toc_detection": "ollama/qwen2.5:3b",
    "toc_index_extractor": "ollama/qwen2.5:3b",
    "no_toc_outline": "ollama/qwen2.5:3b",
    "tree_construction": "ollama/qwen2.5:3b",
    "summary_generation": "ollama/qwen2.5:3b",
    "chapter_summary": "ollama/qwen2.5:3b",
    "title_cleanup": "ollama/qwen2.5:3b",
    "ocr_cleanup": "ollama/qwen2.5:3b",
    "extractive_polish": "ollama/qwen2.5:3b",
    "doc_description": "ollama/qwen2.5:3b",
}

# Local fallback after NVIDIA failure in quality modes — lightweight, Apple-Silicon friendly.
LOCAL_FALLBACK_MODEL = "ollama/qwen2.5:3b"

# Legacy aliases kept for tests / imports; all point at 3b (no 7b promotion).
QUALITY_STAGE_OVERRIDES: Dict[str, str] = {
    "chapter_summary": LOCAL_FALLBACK_MODEL,
    "toc_index_extractor": LOCAL_FALLBACK_MODEL,
    "no_toc_outline": LOCAL_FALLBACK_MODEL,
}

MAX_QUALITY_STAGE_OVERRIDES: Dict[str, str] = {
    "toc_detection": LOCAL_FALLBACK_MODEL,
    "toc_index_extractor": LOCAL_FALLBACK_MODEL,
    "no_toc_outline": LOCAL_FALLBACK_MODEL,
    "chapter_summary": LOCAL_FALLBACK_MODEL,
    "title_cleanup": LOCAL_FALLBACK_MODEL,
    "tree_construction": LOCAL_FALLBACK_MODEL,
}

HIGH_QUALITY_STAGE_OVERRIDES: Dict[str, str] = {
    **MAX_QUALITY_STAGE_OVERRIDES,
    "summary_generation": LOCAL_FALLBACK_MODEL,
    "extractive_polish": LOCAL_FALLBACK_MODEL,
    "ocr_cleanup": LOCAL_FALLBACK_MODEL,
}

_stage_models_override: Optional[Dict[str, str]] = None
_quality_mode: bool = False
_max_quality_mode: bool = False
_nvidia_stages: frozenset = frozenset()
_nvidia_route_after_timeouts: int = 1
_nvidia_first: bool = True


def configure_stage_models(stage_models: Optional[Dict[str, Any]] = None) -> None:
    global _stage_models_override
    if not stage_models:
        _stage_models_override = None
        return
    _stage_models_override = {str(k): str(v) for k, v in stage_models.items() if v}


def set_quality_mode(enabled: bool = True, quality_overrides: Optional[Dict[str, str]] = None) -> None:
    """Enable quality mode — local stages stay on qwen2.5:3b (NVIDIA handles heavy lifting)."""
    global _quality_mode, _stage_models_override
    _quality_mode = enabled
    if enabled:
        overrides = quality_overrides or QUALITY_STAGE_OVERRIDES
        # Never promote to 7b — normalize any legacy config values to LOCAL_FALLBACK_MODEL.
        overrides = {
            k: LOCAL_FALLBACK_MODEL if "7b" in str(v).lower() or "coder" in str(v).lower() else v
            for k, v in overrides.items()
        }
        merged = dict(_stage_models_override or {})
        merged.update(overrides)
        _stage_models_override = merged
        import logging
        logging.getLogger(__name__).info(
            "quality_mode=ON local_fallback=%s stages=%s",
            LOCAL_FALLBACK_MODEL,
            list(overrides.keys()),
        )


def set_max_quality_mode(
    enabled: bool = True,
    nvidia_stages: Optional[list] = None,
    route_after_timeouts: int = 1,
    nvidia_first: bool = True,
) -> None:
    """Enable max-quality: NVIDIA-first for heavy stages, local fallback qwen2.5:3b."""
    global _max_quality_mode, _nvidia_stages, _nvidia_route_after_timeouts, _nvidia_first
    global _stage_models_override
    _max_quality_mode = enabled
    if enabled:
        stages = nvidia_stages or [
            "toc_detection",
            "chapter_summary",
            "no_toc_outline",
        ]
        _nvidia_stages = frozenset(str(s) for s in stages)
        _nvidia_route_after_timeouts = max(0, int(route_after_timeouts))
        _nvidia_first = bool(nvidia_first)
        merged = dict(_stage_models_override or {})
        merged.update(MAX_QUALITY_STAGE_OVERRIDES)
        _stage_models_override = merged
        import logging
        logging.getLogger(__name__).info(
            "max_quality_mode=ON inference_order=NVIDIA→%s nvidia_stages=%s nvidia_first=%s",
            LOCAL_FALLBACK_MODEL,
            list(_nvidia_stages),
            _nvidia_first,
        )
    else:
        _nvidia_stages = frozenset()
        _nvidia_route_after_timeouts = 1
        _nvidia_first = True


def is_max_quality() -> bool:
    return _max_quality_mode


def nvidia_stage_eligible(stage: Optional[str]) -> bool:
    return bool(stage and stage in _nvidia_stages)


def route_after_timeouts() -> int:
    return _nvidia_route_after_timeouts


def nvidia_first_enabled() -> bool:
    """When True, eligible stages call NVIDIA NIM before local Ollama."""
    return _nvidia_first and _max_quality_mode


def local_fallback_model() -> str:
    """Ollama model id used after NVIDIA failure in quality modes."""
    return LOCAL_FALLBACK_MODEL


def set_high_quality_mode(enabled: bool = True) -> None:
    """High quality: same local fallback as max-quality (3b, not 7b)."""
    global _stage_models_override
    if enabled:
        merged = dict(_stage_models_override or {})
        merged.update(HIGH_QUALITY_STAGE_OVERRIDES)
        _stage_models_override = merged
        import logging
        logging.getLogger(__name__).info(
            "high_quality_mode=ON local_fallback=%s stages=%s",
            LOCAL_FALLBACK_MODEL,
            list(HIGH_QUALITY_STAGE_OVERRIDES.keys()),
        )


def model_for_stage(stage: Optional[str], default: str) -> str:
    if not stage:
        return default
    if _max_quality_mode or _quality_mode:
        return LOCAL_FALLBACK_MODEL
    if _stage_models_override and stage in _stage_models_override:
        routed = _stage_models_override[stage]
        if "7b" in routed.lower() or "coder" in routed.lower():
            return LOCAL_FALLBACK_MODEL
        return routed
    return STAGE_MODEL_MAP.get(stage, default)
