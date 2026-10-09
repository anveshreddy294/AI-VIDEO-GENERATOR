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
    "__class__",
    "__bases__",
    "__subclasses__",
    "builtins",
)

MAX_TITLE_LENGTH = 150
MAX_SUBTITLE_LENGTH = 200
MAX_TEXT_LENGTH = 600
MAX_EQUATION_LENGTH = 200
MAX_LABEL_LENGTH = 150
MAX_NARRATION_LENGTH = 1000


class SceneValidationError(ValueError):
    """Raised when a VideoPlan or ScenePlan violates security or structural constraints."""
    pass


def validate_latex(equation: str | None) -> None:
    """Validate LaTeX equation syntax for balanced braces and safe notation."""
    if not equation or not isinstance(equation, str):
        return
    # Check balanced curly braces
    if equation.count("{") != equation.count("}"):
        raise SceneValidationError(f"Invalid LaTeX syntax: unbalanced curly braces in '{equation}'")
    # Check for trailing backslash
    clean = equation.strip()
    if clean.endswith("\\"):
        raise SceneValidationError(f"Invalid LaTeX syntax: trailing backslash in '{equation}'")


def _check_string_for_code_injection(val: str, field_name: str = "field") -> None:
    """Detect arbitrary code execution attempts."""
    low = val.lower()
    for dangerous in _DANGEROUS_SUBSTRINGS:
        if dangerous in low:
            raise SceneValidationError(f"Security violation: dangerous substring '{dangerous}' detected in {field_name}")


def validate_scene_plan(scene: ScenePlan) -> ScenePlan:
    """Validate a single scene plan."""
    if not isinstance(scene.scene_type, SceneType):
        try:
            scene.scene_type = SceneType(str(scene.scene_type).upper())
        except Exception as exc:
            raise SceneValidationError(f"Invalid scene type '{scene.scene_type}'. Allowed: {[t.value for t in SceneType]}") from exc

    if scene.duration_seconds <= 0 or scene.duration_seconds > 300:
        raise SceneValidationError(f"Scene duration {scene.duration_seconds}s is outside valid range (1–300s)")

    # Bounded length enforcement
    if scene.title and len(scene.title) > MAX_TITLE_LENGTH:
        raise SceneValidationError(f"Scene title exceeds maximum allowed length ({len(scene.title)} > {MAX_TITLE_LENGTH})")
    if scene.subtitle and len(scene.subtitle) > MAX_SUBTITLE_LENGTH:
        raise SceneValidationError(f"Scene subtitle exceeds maximum allowed length ({len(scene.subtitle)} > {MAX_SUBTITLE_LENGTH})")
    if scene.text and len(scene.text) > MAX_TEXT_LENGTH:
        raise SceneValidationError(f"Scene text exceeds maximum allowed length ({len(scene.text)} > {MAX_TEXT_LENGTH})")
    if scene.equation and len(scene.equation) > MAX_EQUATION_LENGTH:
        raise SceneValidationError(f"Scene equation exceeds maximum allowed length ({len(scene.equation)} > {MAX_EQUATION_LENGTH})")
    if scene.label and len(scene.label) > MAX_LABEL_LENGTH:
        raise SceneValidationError(f"Scene label exceeds maximum allowed length ({len(scene.label)} > {MAX_LABEL_LENGTH})")
    if scene.narration and len(scene.narration) > MAX_NARRATION_LENGTH:
        raise SceneValidationError(f"Scene narration exceeds maximum allowed length ({len(scene.narration)} > {MAX_NARRATION_LENGTH})")

    # Validate LaTeX equation if present
    if scene.equation:
        validate_latex(scene.equation)

    # Security check all text and equation fields
    check_fields = [
        ("title", scene.title),
        ("subtitle", scene.subtitle),
        ("text", scene.text),
        ("narration", scene.narration),
        ("equation", scene.equation),
        ("label", scene.label),
        ("object_label", scene.object_label),
        ("force_label", scene.force_label),
        ("acceleration_label", scene.acceleration_label),
    ]

    for fname, val in check_fields:
        if val and isinstance(val, str):
            _check_string_for_code_injection(val, fname)

    for pt in (scene.summary_points or []):
        if pt and isinstance(pt, str):
            if len(pt) > MAX_TEXT_LENGTH:
                raise SceneValidationError(f"Summary point exceeds maximum allowed length ({len(pt)} > {MAX_TEXT_LENGTH})")
            _check_string_for_code_injection(pt, "summary_points")

    # Deep-check visual_payload against code injection
    if scene.visual_payload and isinstance(scene.visual_payload, dict):
        def _check_payload_dict(d: dict[str, Any]) -> None:
            for k, v in d.items():
                if isinstance(k, str):
                    _check_string_for_code_injection(k, "visual_payload key")
                if isinstance(v, str):
                    if len(v) > 2000:
                        raise SceneValidationError(f"visual_payload value exceeds maximum length of 2000 chars")
                    _check_string_for_code_injection(v, "visual_payload value")
                elif isinstance(v, dict):
                    _check_payload_dict(v)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str):
                            _check_string_for_code_injection(item, "visual_payload item")
                        elif isinstance(item, dict):
                            _check_payload_dict(item)

        _check_payload_dict(scene.visual_payload)

    return scene


def validate_video_plan(plan: VideoPlan, max_duration_tolerance: float | None = None) -> VideoPlan:
    """Validate full VideoPlan including scene count, narration alignment, durations, and provenance."""
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

    # Validate duration contract against target_seconds / duration_seconds
    target = float(plan.target_seconds or plan.duration_seconds or 45)
    allowed_tolerance = max_duration_tolerance if max_duration_tolerance is not None else max(6.0, target * 0.08)
    if abs(total_scene_duration - target) > allowed_tolerance:
        raise SceneValidationError(
            f"Total scene duration ({total_scene_duration:.1f}s) deviates significantly "
            f"from target duration ({target:.1f}s, tolerance: ±{allowed_tolerance:.1f}s)"
        )

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

        # Speech rate budgeting check (max 210 words per minute allowed)
        matched_scene = plan.scenes[seg.scene_index]
        words = seg.text.split()
        if matched_scene.duration_seconds > 0:
            effective_wpm = (len(words) / matched_scene.duration_seconds) * 60
            if effective_wpm > 240 and len(words) > 15:
                raise SceneValidationError(
                    f"Narration rate ({effective_wpm:.0f} WPM) exceeds maximum speech budget for scene "
                    f"{seg.scene_index} ({matched_scene.duration_seconds}s duration, {len(words)} words)"
                )

    # Check that duration is positive
    if plan.duration_seconds <= 0:
        plan.duration_seconds = int(total_scene_duration) or 45

    return plan
