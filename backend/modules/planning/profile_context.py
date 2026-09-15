"""Learner profile -> prompt-context formatter.

Normalizes both frontend (`academic_level`, `learning_style`, ...) and legacy
(`fullname`, `curriculum_board`, ...) profile shapes into a single internal
dict, and emits a markdown block injected into every planning/narration/code
LLM call so generation is personalized to the user.
"""
from __future__ import annotations

from typing import Any

_ACADEMIC_LABEL = {
    "class_9": "Class 9 (Secondary)",
    "class_10": "Class 10 (Secondary)",
    "class_11": "Class 11 (Senior Secondary)",
    "class_12": "Class 12 (Senior Secondary)",
    "undergraduate": "Undergraduate (College)",
    "competitive": "Competitive Exam (JEE/NEET focus)",
}

_LEVEL_GROUP = {
    "class_9": "lower",
    "class_10": "lower",
    "class_11": "standard",
    "class_12": "standard",
    "undergraduate": "advanced",
    "competitive": "advanced",
}

_PACE_WORD_BUDGET = {
    "slow_deep": (55, 75),
    "balanced": (40, 60),
    "fast_overview": (30, 45),
}

_STYLE_GUIDANCE = {
    "visual": (
        "Lead with animated diagrams, motion, and concrete visuals BEFORE any equation. "
        "Use arrows, color, and analogies to carry the idea."
    ),
    "conceptual": (
        "Open every scene with WHY before HOW. Frame ideas with intuition, "
        "historical context, or limiting-case reasoning. Equations come after meaning."
    ),
    "example_first": (
        "Open every scene with a concrete worked example or numerical scenario. "
        "Generalize to the principle only after the example clicks."
    ),
    "equation_first": (
        "Lead with the governing equation, then interpret each term physically. "
        "Heavier use of MathTex and symbolic derivation."
    ),
}

_LEVEL_DEPTH = {
    "lower": (
        "Use simple sentences, everyday analogies, no calculus, minimal symbolic notation. "
        "Define every term on first use. Prefer 2-3 SHORT worked micro-examples over 1 long one."
    ),
    "standard": (
        "Use NCERT/CBSE vocabulary and full standard notation (vectors, basic calculus OK). "
        "Mix one intuition scene with one quantitative scene."
    ),
    "advanced": (
        "Use rigorous definitions, derivations, vector/calculus notation freely, "
        "and reference advanced edge cases or exam-style applications."
    ),
}


def normalize_profile(raw: dict[str, Any] | None, subject: str = "Physics") -> dict[str, Any]:
    """Coerce a frontend or legacy profile dict into the internal shape."""
    if not raw or not isinstance(raw, dict):
        raw = {}

    academic_level = (
        raw.get("academic_level")
        or _legacy_level(raw.get("curriculum_board", ""))
        or "class_11"
    )
    learning_style = raw.get("learning_style") or "visual"
    pace_preference = raw.get("pace_preference") or "balanced"
    confidence_map = raw.get("confidence_map") or {}
    subject_for_lesson = raw.get("subject_for_lesson") or subject or "Physics"
    subject_confidence = raw.get("subject_confidence")
    if subject_confidence is None:
        subject_confidence = confidence_map.get(subject_for_lesson, 50)

    return {
        "learner_id": raw.get("learner_id", "guest"),
        "name": raw.get("name") or raw.get("fullname") or "Learner",
        "academic_level": academic_level,
        "exam_target": raw.get("exam_target") or [],
        "learning_style": learning_style,
        "pace_preference": pace_preference,
        "weak_subjects": raw.get("weak_subjects") or [],
        "confidence_map": confidence_map,
        "subject_for_lesson": subject_for_lesson,
        "subject_confidence": int(subject_confidence) if isinstance(subject_confidence, (int, float)) else 50,
    }


def _legacy_level(curriculum_board: str) -> str:
    s = (curriculum_board or "").lower()
    if "9" in s:
        return "class_9"
    if "10" in s:
        return "class_10"
    if "11" in s:
        return "class_11"
    if "12" in s:
        return "class_12"
    if "ug" in s or "college" in s or "undergrad" in s:
        return "undergraduate"
    return ""


def level_group(profile: dict[str, Any]) -> str:
    return _LEVEL_GROUP.get(profile.get("academic_level", "class_11"), "standard")


def pace_word_budget(profile: dict[str, Any]) -> tuple[int, int]:
    return _PACE_WORD_BUDGET.get(profile.get("pace_preference", "balanced"), (40, 60))


def confidence_band(profile: dict[str, Any]) -> str:
    c = profile.get("subject_confidence", 50)
    if c < 40:
        return "weak"
    if c > 70:
        return "strong"
    return "standard"


def format_learner_context(
    profile: dict[str, Any] | None,
    topic: str,
    subject: str = "Physics",
) -> str:
    """Return the prompt-injected LEARNER CONTEXT block."""
    p = normalize_profile(profile, subject)
    level_label = _ACADEMIC_LABEL.get(p["academic_level"], p["academic_level"])
    style = p["learning_style"]
    pace = p["pace_preference"]
    word_lo, word_hi = pace_word_budget(p)
    depth = _LEVEL_DEPTH[level_group(p)]
    style_rule = _STYLE_GUIDANCE.get(style, _STYLE_GUIDANCE["visual"])
    band = confidence_band(p)

    band_rule = {
        "weak": (
            f"Self-rated confidence is LOW ({p['subject_confidence']}%). "
            "Prioritize intuition, multiple shallow examples, and define prerequisites in scenes 1-2. "
            "AVOID dense derivations or advanced edge cases."
        ),
        "standard": (
            f"Self-rated confidence is moderate ({p['subject_confidence']}%). "
            "Use standard textbook depth with one intuition pass and one quantitative pass."
        ),
        "strong": (
            f"Self-rated confidence is HIGH ({p['subject_confidence']}%). "
            "Use denser notation, fewer hand-holding analogies, and reach for advanced applications."
        ),
    }[band]

    exam_line = ""
    if p["exam_target"]:
        exam_line = f"\n- Exam targets: {', '.join(p['exam_target'])} — prefer exam-relevant framing and notation"

    cm = p.get("confidence_map") or {}
    weakest_line = ""
    if cm:
        try:
            weakest_subj = min(cm.keys(), key=lambda k: cm.get(k, 50))
            if cm.get(weakest_subj, 50) < 50 and weakest_subj != p["subject_for_lesson"]:
                weakest_line = (
                    f"\n- Cross-subject weakness: {weakest_subj} ({cm[weakest_subj]}%) — "
                    "if the topic touches this area, bridge gently."
                )
        except Exception:
            pass

    return (
        "LEARNER CONTEXT (personalize ALL output to this student):\n"
        f"- Name: {p['name']} | Level: {level_label}{exam_line}\n"
        f"- Subject of lesson: {p['subject_for_lesson']} | Topic: {topic}\n"
        f"- {band_rule}\n"
        f"- Learning style: {style} — {style_rule}\n"
        f"- Pace: {pace} — narration target {word_lo}-{word_hi} words per scene.\n"
        f"- Depth rule: {depth}{weakest_line}\n"
        "- NEVER repeat the same anchor example across two scenes. Each scene must teach "
        "a DISTINCT facet of the topic with its OWN concrete example or scenario."
    )
