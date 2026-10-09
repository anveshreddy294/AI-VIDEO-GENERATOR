"""Bounded Rubric-Based Descriptive Answer Evaluation with Semantic Safeguards.

Evaluates student free-text answers against authoritative rubric criteria,
key concept anchors, and evidence requirements. Supports bounded semantic
safeguards (negation/disclaimer detection, contradiction filtering, morphological/synonym matching)
and an optional bounded reasoning router integration.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Common educational disclaimer / ignorance expressions
DISCLAIMER_PATTERNS = [
    r"\b(?:i\s+)?(?:do\s+not|don't|cannot|can't)\s+(?:understand|know|recall|remember|have\s+any\s+idea)\b",
    r"\b(?:no\s+idea|clueless|not\s+sure|don't\s+care|haven't\s+learned)\b",
    r"\b(?:do\s+not|don't)\s+(?:know\s+anything|have\s+a\s+clue)\b",
]

# Morphological / conceptual synonym expansions for core security & architectural concepts
CONCEPT_STEMS: dict[str, list[str]] = {
    "rotation": ["rotat", "renew", "reissu", "invalidat", "revoc", "cycl"],
    "refresh token": ["refresh token", "renewal token", "renewal key", "refresh credential"],
    "access token": ["access token", "bearer token", "session credential", "identity assertion", "entry token"],
    "expiration": ["expir", "validity", "lifetime", "lapse", "time-to-live", "ttl"],
    "security": ["secur", "protect", "safeguard", "prevent replay", "integrity"],
}


class RubricCriterion(BaseModel):
    criterion_id: str
    description: str
    points: float = 1.0
    required_keywords: list[str] = Field(default_factory=list)
    synonym_groups: list[list[str]] = Field(default_factory=list)


class DescriptiveEvaluationResult(BaseModel):
    question_id: str
    concept_id: str
    score: float = Field(ge=0.0, le=100.0)
    max_score: float = 100.0
    passed: bool
    feedback: str
    criteria_met: list[str] = Field(default_factory=list)
    criteria_missed: list[str] = Field(default_factory=list)
    explanation: str = ""
    word_count: int = 0
    evaluation_mode: str = "BOUNDED_HEURISTIC"  # "BOUNDED_HEURISTIC" or "SEMANTIC_ROUTER"


def _is_disclaimer_clause(text: str) -> bool:
    """Check if the response is primarily an admission of ignorance."""
    clean = text.lower().strip()
    return any(re.search(pat, clean) for pat in DISCLAIMER_PATTERNS)


def _check_contradiction(text: str, keyword: str) -> bool:
    """Detect if a keyword is explicitly negated or claimed to cause vulnerability/failure."""
    kw_re = re.escape(keyword) + r"s?"
    # e.g., "refresh token causes security breach" or "rotation makes access token insecure"
    contradiction_re = (
        r"\b" + kw_re + r"\b.{0,40}\b(?:insecure|breach|vulnerable|broken|fails?|useless|never\s+works)\b"
    )
    return bool(re.search(contradiction_re, text, re.IGNORECASE))


def _match_keyword_or_synonyms(keyword: str, text: str) -> bool:
    """Match keyword using plural/morphological tolerance and canonical conceptual stems."""
    clean_kw = keyword.lower().strip()
    clean_text = text.lower()

    # 1. Direct or plural match: e.g. "refresh token" -> "refresh tokens"
    if re.search(r"\b" + re.escape(clean_kw) + r"s?\b", clean_text):
        return True

    # 2. Check concept stems / synonyms if known
    stems = CONCEPT_STEMS.get(clean_kw, [])
    for stem in stems:
        if stem in clean_text or re.search(r"\b" + re.escape(stem), clean_text):
            return True

    # 3. Trailing word root match for single words >= 5 characters (e.g. "expir" in "expired")
    if len(clean_kw) >= 5 and " " not in clean_kw:
        root = clean_kw[:4]
        if re.search(r"\b" + re.escape(root) + r"\w*", clean_text):
            return True

    return False


def evaluate_descriptive_answer(
    question_id: str,
    concept_id: str,
    student_response: str,
    rubric_criteria: list[dict[str, Any]] | list[RubricCriterion],
    authoritative_explanation: str = "",
    min_words: int = 5,
    pass_threshold_percent: float = 70.0,
    use_ai_reasoning: bool = False,
    reasoning_router: Any | None = None,
) -> DescriptiveEvaluationResult:
    """Evaluate a descriptive answer deterministically using bounded rubric criteria with semantic safeguards.

    1. Input sanitization & minimum length bounds.
    2. Disclaimer & ignorance filter: prevents keyword-stuffed disclaimers from passing.
    3. Contradiction filter: identifies negated or corrupted concepts.
    4. Morphological and synonym tolerance for valid conceptual paraphrasing.
    5. Proportionate scoring and constructive feedback generation.
    6. Strict answer key isolation: authoritative explanation revealed only post-evaluation.
    """
    clean_text = student_response.strip()
    words = re.findall(r"\b[\w'-]+\b", clean_text.lower())
    word_count = len(words)

    # 1. Minimum length boundary check
    if word_count < min_words:
        return DescriptiveEvaluationResult(
            question_id=question_id,
            concept_id=concept_id,
            score=0.0,
            passed=False,
            feedback=f"Response is too brief ({word_count} words; minimum {min_words} required). Please provide a substantive explanation.",
            criteria_met=[],
            criteria_missed=[
                c.description if isinstance(c, RubricCriterion) else c.get("description", str(c))
                for c in rubric_criteria
            ],
            explanation=authoritative_explanation,
            word_count=word_count,
            evaluation_mode="BOUNDED_HEURISTIC",
        )

    # 2. Ignorance / Disclaimer check: if student merely lists keywords within an admission of ignorance
    if _is_disclaimer_clause(clean_text) and word_count <= 25:
        return DescriptiveEvaluationResult(
            question_id=question_id,
            concept_id=concept_id,
            score=0.0,
            passed=False,
            feedback="The response indicates a lack of understanding of the concept. Please review the learning materials before resubmitting.",
            criteria_met=[],
            criteria_missed=[
                c.description if isinstance(c, RubricCriterion) else c.get("description", str(c))
                for c in rubric_criteria
            ],
            explanation=authoritative_explanation,
            word_count=word_count,
            evaluation_mode="BOUNDED_HEURISTIC",
        )

    text_lower = clean_text.lower()
    total_points = 0.0
    earned_points = 0.0
    met: list[str] = []
    missed: list[str] = []

    # 3. Evaluate criteria with semantic safeguards
    for c in rubric_criteria:
        if isinstance(c, dict):
            crit_desc = c.get("description", "")
            pts = float(c.get("points", 1.0))
            keywords = [k.lower().strip() for k in c.get("required_keywords", [])]
            synonyms = c.get("synonym_groups", [])
        else:
            crit_desc = c.description
            pts = float(c.points)
            keywords = [k.lower().strip() for k in c.required_keywords]
            synonyms = c.synonym_groups

        total_points += pts

        if not keywords:
            desc_words = [w for w in re.findall(r"\b\w{4,}\b", crit_desc.lower()) if w not in {"which", "where", "about", "their", "these", "should", "using"}]
            keywords = desc_words[:3]

        if not keywords:
            earned_points += pts
            met.append(crit_desc)
            continue

        # Check matches and contradictory statements
        matches = 0
        contradictions = 0
        for kw in keywords:
            if _match_keyword_or_synonyms(kw, text_lower):
                if _check_contradiction(clean_text, kw):
                    contradictions += 1
                else:
                    matches += 1

        # Check optional custom synonym groups
        for syn_group in synonyms:
            if any(_match_keyword_or_synonyms(syn, text_lower) for syn in syn_group):
                matches = max(matches, 1)

        effective_matches = max(0, matches - contradictions)
        match_ratio = effective_matches / len(keywords)

        if match_ratio >= 0.5:
            earned_points += pts * min(1.0, match_ratio + 0.2)
            met.append(crit_desc)
        else:
            missed.append(crit_desc)

    effective_total = max(1.0, total_points)
    score_pct = round(min(100.0, max(0.0, (earned_points / effective_total) * 100.0)), 1)
    passed = score_pct >= pass_threshold_percent

    # 4. Constructive feedback synthesis
    if passed:
        fb_parts = ["Solid understanding demonstrated."]
        if met:
            fb_parts.append(f"Covered key concepts: {'; '.join(met[:2])}.")
        if missed:
            fb_parts.append(f"Consider also mentioning: {'; '.join(missed[:2])}.")
    else:
        fb_parts = ["Key concepts need further development."]
        if missed:
            fb_parts.append(f"Missing core requirements: {'; '.join(missed[:2])}.")
        if met:
            fb_parts.append(f"Correctly included: {'; '.join(met[:2])}.")

    feedback = " ".join(fb_parts)

    return DescriptiveEvaluationResult(
        question_id=question_id,
        concept_id=concept_id,
        score=score_pct,
        passed=passed,
        feedback=feedback,
        criteria_met=met,
        criteria_missed=missed,
        explanation=authoritative_explanation,
        word_count=word_count,
        evaluation_mode="BOUNDED_HEURISTIC",
    )

