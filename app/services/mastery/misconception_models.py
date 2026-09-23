"""Step 5 Misconception Intelligence Domain Models (M1–M4).

Defines the domain entities, enumerations, and metadata structures for:
1. Misconception confidence states (POSSIBLE -> LIKELY -> CONFIRMED)
2. Misconception lifecycle statuses (ACTIVE, CORRECTED, RECURRENT)
3. Distractor-to-misconception mappings
4. Teaching strategies and deterministic strategy selection decisions
5. Normalized code sanitization preventing generic placeholders
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator

from .models import DomainInvariantViolation


class MisconceptionConfidenceState(str, Enum):
    """Confidence levels for accumulated misconception evidence."""

    POSSIBLE = "POSSIBLE"      # 1 independent mapped attempt
    LIKELY = "LIKELY"          # 2 independent grounded attempts
    CONFIRMED = "CONFIRMED"    # 3+ independent attempts or explicit verification


class MisconceptionStatus(str, Enum):
    """Lifecycle status of a misconception for a specific learner and concept."""

    ACTIVE = "ACTIVE"
    CORRECTED = "CORRECTED"
    RECURRENT = "RECURRENT"


class TeachingStrategyType(str, Enum):
    """Pedagogical remediation strategies executable by the VideoPlanner."""

    DIRECT_EXPLANATION = "DIRECT_EXPLANATION"
    VISUAL_COMPARISON = "VISUAL_COMPARISON"
    CONTRAST = "CONTRAST"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    WORKED_EXAMPLE = "WORKED_EXAMPLE"
    PREREQUISITE_REVIEW = "PREREQUISITE_REVIEW"
    PREDICTION_AND_REVEAL = "PREDICTION_AND_REVEAL"


class TeachingStrategyReasonCode(str, Enum):
    """Deterministic attribution reasons for strategy selection."""

    DEFINITION_CONFUSION = "DEFINITION_CONFUSION"
    CONCEPT_CONFLATION = "CONCEPT_CONFLATION"
    INCORRECT_CAUSAL_BELIEF = "INCORRECT_CAUSAL_BELIEF"
    PROCEDURAL_ERROR = "PROCEDURAL_ERROR"
    UNMASTERED_PREREQUISITE = "UNMASTERED_PREREQUISITE"
    PERSISTENT_PREDICTION_ERROR = "PERSISTENT_PREDICTION_ERROR"
    NOVELTY_FALLBACK_NEXT_STRATEGY = "NOVELTY_FALLBACK_NEXT_STRATEGY"
    DEFAULT_CONCEPT_GROUNDED = "DEFAULT_CONCEPT_GROUNDED"
    DEFAULT_DIRECT = "DEFAULT_DIRECT"


_GENERIC_CODE_BLACKLIST = {
    "WRONG_ANSWER",
    "WRONG_ANSWER_1",
    "WRONG_ANSWER_2",
    "WRONG_ANSWER_3",
    "BAD_REASONING",
    "UNKNOWN_MISTAKE",
    "UNKNOWN",
    "PLACEHOLDER",
    "MISTAKE",
    "INCORRECT",
    "ERROR",
    "NONE",
    "NULL",
    "MISC_1",
    "MISC_2",
    "MISC_3",
    "MISCONCEPTION_1",
    "MISCONCEPTION_2",
    "MISCONCEPTION_3",
}


def normalize_misconception_code(raw: str | None) -> str | None:
    """Normalize and validate a misconception code.

    Enforces format [A-Z0-9_]+ and rejects generic non-diagnostic placeholders.
    Returns cleaned string or None if invalid/empty/placeholder.
    """
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().upper()
    cleaned = re.sub(r"[^A-Z0-9_]+", "_", cleaned).strip("_")
    if not cleaned or len(cleaned) < 3:
        return None
    if cleaned in _GENERIC_CODE_BLACKLIST:
        return None
    if re.match(r"^MISC_\d+$", cleaned) or re.match(r"^MISCONCEPTION_\d+$", cleaned):
        return None
    return cleaned


class DistractorMisconceptionMetadata(BaseModel):
    """Diagnostic misconception metadata associated with a multiple-choice distractor."""

    misconception_code: str
    misconception_label: str
    misconception_description: str = ""
    misconception_type: str = "general"

    def __init__(self, **data: Any) -> None:
        if "code" in data and "misconception_code" not in data:
            data["misconception_code"] = data.pop("code")
        if "label" in data and "misconception_label" not in data:
            data["misconception_label"] = data.pop("label")
        super().__init__(**data)

    @field_validator("misconception_code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        norm = normalize_misconception_code(v)
        if not norm:
            raise DomainInvariantViolation(
                f"Invalid or generic distractor misconception code: '{v}'"
            )
        return norm


class MisconceptionEvidence(BaseModel):
    """Domain entity tracking accumulated misconception evidence for a learner and concept."""

    misconception_id: str = ""
    user_id: str
    source_id: str
    session_id: str | None = None
    concept_id: str

    misconception_code: str
    misconception_label: str = ""
    misconception_description: str = ""
    misconception_type: str = "general"

    evidence_question_ids: list[str] = Field(default_factory=list)
    evidence_attempt_ids: list[str] = Field(default_factory=list)
    occurrence_count: int = Field(default=1, ge=1)

    confidence_state: MisconceptionConfidenceState = Field(
        default=MisconceptionConfidenceState.POSSIBLE
    )
    status: MisconceptionStatus = Field(default=MisconceptionStatus.ACTIVE)

    first_detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    corrected_at: datetime | None = None

    source_chunk_ids: list[str] = Field(default_factory=list)
    supporting_evidence_summary: str | None = None

    def __init__(self, **data: Any) -> None:
        if "code" in data and "misconception_code" not in data:
            data["misconception_code"] = data.pop("code")
        if "label" in data and "misconception_label" not in data:
            data["misconception_label"] = data.pop("label")
        if "confidence" in data and "confidence_state" not in data:
            conf_val = data.pop("confidence")
            if isinstance(conf_val, str):
                conf_val = MisconceptionConfidenceState(conf_val)
            data["confidence_state"] = conf_val
        if not data.get("misconception_id"):
            u = data.get("user_id", "u")
            c = data.get("concept_id", "c")
            m = data.get("misconception_code", "m")
            data["misconception_id"] = f"MISC_{u}_{c}_{m}"
        if "evidence_attempt_ids" in data and ("occurrence_count" not in data or data.get("occurrence_count", 0) <= 1):
            ids = data["evidence_attempt_ids"]
            if isinstance(ids, list) and len(ids) > 1:
                data["occurrence_count"] = len(ids)
        try:
            super().__init__(**data)
        except Exception as err:
            if isinstance(err, DomainInvariantViolation):
                raise
            from pydantic import ValidationError
            if isinstance(err, ValidationError):
                first_msg = err.errors()[0].get("msg", str(err)) if err.errors() else str(err)
                raise DomainInvariantViolation(first_msg) from err
            raise

    @property
    def confidence(self) -> MisconceptionConfidenceState:
        return self.confidence_state

    @property
    def evidence_count(self) -> int:
        if self.evidence_attempt_ids:
            return max(len(self.evidence_attempt_ids), self.occurrence_count)
        return self.occurrence_count

    @property
    def code(self) -> str:
        return self.misconception_code

    @property
    def label(self) -> str:
        return self.misconception_label

    @field_validator("misconception_id", "user_id", "source_id", "concept_id")
    @classmethod
    def _validate_non_empty_ids(cls, v: str, info: Any) -> str:
        if not v or not v.strip():
            raise DomainInvariantViolation(
                f"Field '{info.field_name}' cannot be empty or whitespace only."
            )
        return v.strip()

    @field_validator("misconception_code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        norm = normalize_misconception_code(v)
        if not norm:
            raise DomainInvariantViolation(
                f"Invalid or generic misconception code: '{v}'"
            )
        return norm

    def record_occurrence(
        self,
        question_id: str,
        attempt_id: str,
        source_chunk_ids: list[str] | None = None,
    ) -> bool:
        """Record an independent observation of this misconception.

        Enforces idempotency: duplicate attempt_id does not increment occurrence_count.
        Transitions confidence deterministically:
        - 1 attempt -> POSSIBLE
        - 2 independent attempts -> LIKELY
        - 3+ independent attempts -> CONFIRMED
        """
        clean_qid = question_id.strip()
        clean_aid = attempt_id.strip()

        if clean_aid in self.evidence_attempt_ids:
            return False  # Idempotent: already recorded

        self.evidence_attempt_ids.append(clean_aid)
        if clean_qid not in self.evidence_question_ids:
            self.evidence_question_ids.append(clean_qid)

        if source_chunk_ids:
            for cid in source_chunk_ids:
                if cid and cid.strip() not in self.source_chunk_ids:
                    self.source_chunk_ids.append(cid.strip())

        self.occurrence_count = len(self.evidence_attempt_ids)
        self.last_detected_at = datetime.now(timezone.utc)

        # Confidence progression: based on independent questions observed
        independent_count = len(self.evidence_question_ids)
        if independent_count >= 3:
            self.confidence_state = MisconceptionConfidenceState.CONFIRMED
        elif independent_count == 2:
            self.confidence_state = MisconceptionConfidenceState.LIKELY
        else:
            self.confidence_state = MisconceptionConfidenceState.POSSIBLE

        # If previously corrected and observed again, mark as RECURRENT
        if self.status == MisconceptionStatus.CORRECTED:
            self.status = MisconceptionStatus.RECURRENT
        elif self.status != MisconceptionStatus.RECURRENT:
            self.status = MisconceptionStatus.ACTIVE

        return True

    def mark_corrected(self) -> None:
        """Mark this misconception as corrected following successful reassessment."""
        self.status = MisconceptionStatus.CORRECTED
        self.corrected_at = datetime.now(timezone.utc)


class TeachingStrategyDecision(BaseModel):
    """Deterministic result of evaluating a learner's state and misconceptions."""

    concept_id: str
    strategy: TeachingStrategyType
    reason_code: TeachingStrategyReasonCode
    misconception_code: str | None = None
    attempt_number: int = 1
    previous_strategies: list[TeachingStrategyType] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    prerequisite_concept_id: str | None = None

    @property
    def target_concept_id(self) -> str | None:
        return self.prerequisite_concept_id or self.concept_id
