"""Pydantic schemas for Step 2: Student Knowledge Profiling.

Defines the data structures for questions, assessment sessions,
submissions, mastery tracking, and the final StudentLearningProfile.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class AssessmentOption(BaseModel):
    """A single multiple-choice option."""
    index: int = Field(description="0-3 option index")
    text: str = Field(description="The option text")


class Question(BaseModel):
    """A single assessment question grounded in Layer A source chunks."""
    question_id: str = Field(default_factory=lambda: f"Q_{uuid4().hex[:12]}")
    concept_id: str = Field(description="The KnowledgeGraph concept this tests")
    concept_name: str = Field(description="Human-readable concept name")
    stem: str = Field(description="The question text")
    options: list[AssessmentOption] = Field(description="Exactly 4 options")
    correct_index: int = Field(ge=0, le=3, description="Index of the correct answer (0-3)")
    explanation: str = Field(description="Why the correct answer is correct")
    chunk_ids: list[str] = Field(default_factory=list, description="Source chunk IDs used for grounding")
    source_id: str = Field(description="The source document this question came from")
    difficulty: Literal["foundational", "intermediate", "advanced"] = "intermediate"


class AssessmentSession(BaseModel):
    """A quiz session for a student on a specific source."""
    session_id: str = Field(default_factory=lambda: f"SESS_{uuid4().hex[:12]}")
    student_id: str
    source_id: str
    questions: list[Question] = Field(default_factory=list)
    status: Literal["PLANNING", "GENERATING", "VALIDATING", "READY", "SUBMITTED", "EXPIRED", "FAILED"] = "PLANNING"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: str | None = None
    submitted_at: str | None = None
    concept_queue: list[str] = Field(default_factory=list, description="Concept IDs queued for question generation")
    current_index: int = 0


class AnswerSubmission(BaseModel):
    """A single answer from a student."""
    question_id: str
    selected_index: int = Field(ge=0, le=3)


class StudentSubmission(BaseModel):
    """The student's full quiz submission."""
    session_id: str
    answers: list[AnswerSubmission] = Field(default_factory=list)


class QuestionResult(BaseModel):
    """Result for a single question after grading."""
    question_id: str
    concept_id: str
    correct: bool
    selected_index: int
    correct_index: int


class SubmissionResult(BaseModel):
    """Graded result of a student's submission."""
    session_id: str
    student_id: str
    source_id: str
    score: int = Field(description="Number correct")
    total: int = Field(description="Total questions")
    percentage: float = Field(description="Score as percentage 0-100")
    results: list[QuestionResult] = Field(default_factory=list)
    prerequisite_gaps: list[str] = Field(default_factory=list, description="Concept IDs where both child and parent failed")
    graded_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ConceptMastery(BaseModel):
    """Tracks a student's mastery of a single concept across sessions."""
    concept_id: str
    concept_name: str = ""
    attempts: int = 0
    correct_attempts: int = 0
    consecutive_correct: int = 0
    status: Literal["NOT_ATTEMPTED", "LEARNING", "MASTERED", "REQUIRES_FALLBACK"] = "NOT_ATTEMPTED"
    iteration_count: int = Field(default=0, description="How many times this concept was tested and failed")
    last_attempt_at: str | None = None


class StudentLearningProfile(BaseModel):
    """Complete learning profile for a student on a specific source.
    This is the artifact passed to Step 3 (video generation)."""
    student_id: str
    source_id: str
    overall_score: float = Field(default=0.0, description="Average score across all sessions (0-100)")
    total_sessions: int = 0
    strong_concepts: list[str] = Field(default_factory=list, description="Concept names mastered")
    weak_concepts: list[str] = Field(default_factory=list, description="Concept names needing work")
    prerequisite_gaps: list[str] = Field(default_factory=list, description="Prerequisite gap descriptions")
    concept_masteries: dict[str, ConceptMastery] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
