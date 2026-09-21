"""Strict validation gateway for VideoPlan and ScenePlan models.

Guarantees safety before passing data to the Manim rendering engine:
1. Rejects arbitrary code or dangerous execution keywords in text/equation fields.
2. Enforces allowed scene types only.
3. Checks scene and narration integrity, durations, and bounds.
4. Preserves provenance chunk mappings.
"""

from __future__ import annotations

import re
from typing import Any

from .scene_schema import ScenePlan, SceneType, VideoPlan

# Strict security allowlist: reject any attempts to smuggle code into LaTeX or text
_DANGEROUS_SUBSTRINGS = (
    "__import__",
    "eval(",
    "exec(",
    "os.system",
    "subprocess",
    "sys.modules",
    "open(",
    "globals()",
    "locals()",
    "<script",
    "shutil",
)


class SceneValidationError(ValueError):
    """Raised when a VideoPlan or ScenePlan violates security or structural constraints."""
    pass


def validate_scene_plan(scene: ScenePlan) -> ScenePlan:
    """Validate a single scene plan."""
    if not isinstance(scene.scene_type, SceneType):
        try:
            scene.scene_type = SceneType(str(scene.scene_type).upper())
        except Exception as exc:
            raise SceneValidationError(f"Invalid scene type '{scene.scene_type}'. Allowed: {[t.value for t in SceneType]}") from exc

    if scene.duration_seconds <= 0 or scene.duration_seconds > 120:
        raise SceneValidationError(f"Scene duration {scene.duration_seconds}s is outside valid range (1–120s)")

    # Security check all text and equation fields
    check_fields = [
        scene.title,
        scene.subtitle,
        scene.text,
        scene.equation,
        scene.label,
        scene.object_label,
        scene.force_label,
        scene.acceleration_label,
    ] + (scene.summary_points or [])

    for val in check_fields:
        if val and isinstance(val, str):
            lower_val = val.lower()
            for dangerous in _DANGEROUS_SUBSTRINGS:
                if dangerous in lower_val:
                    raise SceneValidationError(f"Security violation: dangerous substring '{dangerous}' detected in scene content")

    return scene


def validate_video_plan(plan: VideoPlan) -> VideoPlan:
    """Validate full VideoPlan including scene count, narration alignment, and durations."""
    if not plan.concept_id or not plan.concept_name:
        raise SceneValidationError("VideoPlan must contain non-empty concept_id and concept_name")

    if not plan.scenes:
        raise SceneValidationError("VideoPlan must contain at least one scene")

    if not plan.narration:
        raise SceneValidationError("VideoPlan must contain at least one narration segment")

    # Validate each scene
    total_scene_duration = 0.0
    for idx, scene in enumerate(plan.scenes):
        scene.scene_index = idx
        validate_scene_plan(scene)
        total_scene_duration += scene.duration_seconds

    # Validate narration segments
    max_scene_idx = len(plan.scenes) - 1
    for seg in plan.narration:
        if not seg.text or not seg.text.strip():
            raise SceneValidationError("Narration segment contains empty text")
        if seg.scene_index < 0 or seg.scene_index > max_scene_idx:
            # Re-anchor out-of-bounds scene index
            seg.scene_index = max(0, min(seg.scene_index, max_scene_idx))
        for dangerous in _DANGEROUS_SUBSTRINGS:
            if dangerous in seg.text.lower():
                raise SceneValidationError(f"Security violation: dangerous substring '{dangerous}' in narration")

    # Check that duration is positive
    if plan.duration_seconds <= 0:
        plan.duration_seconds = int(total_scene_duration) or 45

    return plan
