"""Pydantic data models for Instructor Analytics & Human Intervention Portal."""

from datetime import datetime, timezone
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class HumanInterventionAlert(BaseModel):
    """Alert for a student concept hitting the anti-loop kill switch."""
    student_id: str = Field(description="Student identifier")
    source_id: str = Field(description="Source material identifier")
    concept_id: str = Field(description="Concept identifier")
    concept_name: str = Field(description="Human readable concept name")
    iteration_count: int = Field(description="Total failed attempts triggering the kill switch")
    last_score: float = Field(default=0.0, description="Score on most recent attempt")
    last_attempt_at: Optional[str] = Field(default=None, description="Timestamp of most recent attempt")
    prerequisite_concept_ids: List[str] = Field(default_factory=list, description="Prerequisite concepts")
    instructor_notes: Optional[str] = Field(default=None, description="Instructor review or guidance notes")


class ConceptAnalytics(BaseModel):
    """Cohort-wide mastery and struggle metrics for a single concept."""
    concept_id: str = Field(description="Concept identifier")
    concept_name: str = Field(description="Human readable concept name")
    total_students: int = Field(description="Total students assessed on this concept")
    mastered_count: int = Field(description="Count of students with MASTERED status")
    learning_count: int = Field(description="Count of students with LEARNING status")
    fallback_count: int = Field(description="Count of students flagged for human intervention")
    mastery_rate_percent: float = Field(description="Percentage of assessed students who mastered the concept")
    is_prerequisite_bottleneck: bool = Field(default=False, description="True if failure cascades to downstream concepts")


class CohortOverview(BaseModel):
    """Comprehensive cohort health metrics and action items."""
    total_students: int = Field(description="Total unique students tracked across profiles")
    total_sources: int = Field(description="Total study materials assessed")
    total_interventions_needed: int = Field(description="Total active human intervention alerts")
    average_mastery_percent: float = Field(description="Overall class mastery percentage across concepts")
    alerts: List[HumanInterventionAlert] = Field(default_factory=list, description="Active kill-switch alerts")
    concept_analytics: List[ConceptAnalytics] = Field(default_factory=list, description="Per-concept cohort metrics")


class ResetMasteryRequest(BaseModel):
    """Instructor action to override or reset a student's concept mastery status."""
    student_id: str = Field(description="Student identifier", max_length=128)
    source_id: str = Field(description="Source identifier", max_length=128)
    concept_id: str = Field(description="Concept identifier", max_length=256)
    # SEC-008: Only LEARNING and MASTERED are valid statuses — prevents arbitrary string injection
    new_status: Literal["LEARNING", "MASTERED"] = Field(
        default="LEARNING",
        description="'LEARNING' to allow retry, or 'MASTERED' to manually verify",
    )
    instructor_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Explanation or guidance note for student record (max 2000 chars)",
    )


class ResetMasteryResponse(BaseModel):
    """Result of an instructor mastery override action."""
    student_id: str
    source_id: str
    concept_id: str
    previous_status: str
    new_status: str
    message: str
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
