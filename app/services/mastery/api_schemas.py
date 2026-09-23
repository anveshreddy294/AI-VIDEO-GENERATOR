"""Step 5E DTO Schemas — Adaptive Learning API Requests, Responses, and Snapshots.

Client-facing Pydantic models for:
- Learning state snapshots
- Roadmap and deterministic next actions
- Authoritative assessment submissions and grading responses
- Safe reassessment question presentations (zero answer leakage)
- Remediation job start and status polling
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from .attempt_models import AssessmentType
from .models import MasteryState
from .remediation_models import RemediationJobStatus
from .roadmap_models import LearningActionType, ReasonCode


class ConceptMasterySummary(BaseModel):
    """Client-safe summary of learner mastery for a single concept."""

    concept_id: str
    mastery_state: MasteryState
    mastery_score: float = Field(ge=0.0, le=100.0)
    lifetime_accuracy: float = Field(ge=0.0, le=100.0)
    attempt_count: int = Field(ge=0)
    reassessment_attempt_count: int = Field(ge=0)
    remediation_attempt_count: int = Field(ge=0)
    last_assessed_at: datetime | None = None
    last_remediation_at: datetime | None = None

    # M7 Explainable Misconception History & Journey
    initial_state: MasteryState | None = None
    current_state: MasteryState | None = None
    active_misconception_label: str | None = None
    misconception_confidence: str | None = None
    strategy_used: str | None = None
    reassessment_result: str | None = None
    misconception_status: str | None = None
    why_chosen: str | None = None


class NextActionResponse(BaseModel):
    """Deterministic next pedagogical action for the learner."""

    user_id: str
    source_id: str
    session_id: str | None = None
    concept_id: str | None = None
    action_type: LearningActionType
    reason_code: ReasonCode
    priority: int = Field(ge=1, le=100)
    mastery_state: MasteryState | None = None
    mastery_score: float | None = None
    lifetime_accuracy: float | None = None
    dependency_status: str = "NONE"
    metadata: dict[str, Any] = Field(default_factory=dict)
    why_chosen: dict[str, Any] | str | None = None
    active_misconception_label: str | None = None


class RoadmapResponse(BaseModel):
    """Complete partitioned learning roadmap for a source curriculum."""

    user_id: str
    source_id: str
    session_id: str | None = None
    mastered_concepts: list[str] = Field(default_factory=list)
    current_concept: str | None = None
    weak_concepts: list[str] = Field(default_factory=list)
    remediating_concepts: list[str] = Field(default_factory=list)
    reassessing_concepts: list[str] = Field(default_factory=list)
    unassessed_concepts: list[str] = Field(default_factory=list)
    blocked_concepts: list[str] = Field(default_factory=list)
    needs_support_concepts: list[str] = Field(default_factory=list)
    completed: bool = False
    next_action: NextActionResponse
    concept_summaries: list[ConceptMasterySummary] = Field(default_factory=list)
    misconception_journey: list[dict[str, Any]] = Field(default_factory=list)


class LearningStateResponse(BaseModel):
    """Comprehensive snapshot of a learner's state across an educational source."""

    user_id: str
    source_id: str
    session_id: str | None = None
    total_concepts: int = Field(ge=0)
    mastered_count: int = Field(ge=0)
    weak_count: int = Field(ge=0)
    progress_percentage: float = Field(ge=0.0, le=100.0)
    concepts: list[ConceptMasterySummary] = Field(default_factory=list)
    next_action: NextActionResponse
    completed: bool = False


class AssessmentSubmissionRequestDTO(BaseModel):
    """Client request body for submitting an assessment attempt.

    Notice: Client cannot submit is_correct, correct_answer, mastery_score,
    or mastery_state. Grading is strictly authoritative and server-side.
    """

    attempt_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    selected_answer: int = Field(ge=0, le=10)
    session_id: str | None = None
    assessment_type: AssessmentType = AssessmentType.DIAGNOSTIC


class AssessmentSubmissionResponseDTO(BaseModel):
    """Authoritative grading and state mutation response."""

    attempt_id: str
    user_id: str
    source_id: str
    concept_id: str
    question_id: str
    selected_answer: int
    is_correct: bool
    is_duplicate: bool = False
    mastery_state: MasteryState
    mastery_score: float
    lifetime_accuracy: float
    attempt_count: int
    reassessment_attempt_count: int
    remediation_attempt_count: int
    next_action: NextActionResponse


class SafeReassessmentQuestionResponse(BaseModel):
    """Client-safe presentation of a novel reassessment question.

    CRITICAL SECURITY INVARIANT:
    Does NOT contain correct_index, correct_answer, or hidden grading prompts.
    """

    question_id: str
    concept_id: str
    source_id: str
    stem: str
    options: list[str]
    difficulty: str = "intermediate"
    variant_type: str = "application"


class RemediationStartRequestDTO(BaseModel):
    """Optional client request body for initiating remediation."""

    concept_id: str | None = None
    session_id: str | None = None
    force: bool = False


class RemediationStartResponseDTO(BaseModel):
    """Response returned upon accepting a remediation video job."""

    remediation_job_id: str
    user_id: str
    source_id: str
    concept_id: str
    attempt_number: int
    status: RemediationJobStatus
    stream_url: str | None = None
    message: str


class RemediationStatusResponseDTO(BaseModel):
    """Pollable status of a remediation video generation job."""

    remediation_job_id: str
    user_id: str
    source_id: str
    concept_id: str
    attempt_number: int
    status: RemediationJobStatus
    duration_seconds: float | None = None
    stream_url: str | None = None
    is_infrastructure_failure: bool = False
    failure_code: str | None = None
    failure_message: str | None = None
