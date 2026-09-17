"""Pydantic schemas for Step 2: Student Knowledge Profiling & Step 3 Video Targeting.

Defines the data structures for:
1. Ingesting Step 1 JSON payloads & session integrity
2. Grounded questions with source provenance (chunk IDs, page numbers, timestamps)
3. Client-facing sanitized quiz dispatch (hidden answers)
4. Submissions, scoring, mastery calculation & anti-loop kill switch
5. Video Target Matrix blueprint for Step 3 video generation
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ..schemas import ConceptNode, KnowledgeGraph


def _normalize_mastery_status(v: Any) -> str:
    """Normalize legacy status string to current schema."""
    if v == "REQUIRES_FALLBACK":
        return "REQUIRES_HUMAN_FALLBACK"
    return str(v)


MasteryStatus = Annotated[
    Literal["NOT_ATTEMPTED", "LEARNING", "MASTERED", "REQUIRES_HUMAN_FALLBACK"],
    BeforeValidator(_normalize_mastery_status),
]


class AssessmentOption(BaseModel):
    """A single multiple-choice option."""
    index: int = Field(ge=0, le=3, description="0-3 option index")
    text: str = Field(description="The option text")


class SafeOption(BaseModel):
    """Client-facing option (sanitized)."""
    index: int = Field(ge=0, le=3)
    text: str


class Question(BaseModel):
    """A single assessment question grounded in Layer A source chunks with full provenance."""
    question_id: str = Field(default_factory=lambda: f"Q_{uuid4().hex[:12]}")
    concept_id: str = Field(description="The KnowledgeGraph concept this tests")
    concept_name: str = Field(description="Human-readable concept name")
    stem: str = Field(description="The question text")
    options: list[AssessmentOption] = Field(description="Exactly 4 options")
    correct_index: int = Field(ge=0, le=3, description="Index of the correct answer (0-3)")
    explanation: str = Field(description="Why the correct answer is correct")
    chunk_ids: list[str] = Field(default_factory=list, description="Source chunk IDs used for grounding")
    content_ids: list[str] = Field(default_factory=list, description="ContentUnit IDs for grounding")
    page_start: int | None = Field(default=None, description="Starting page number in source document")
    page_end: int | None = Field(default=None, description="Ending page number in source document")
    timestamp_start: float | str | None = Field(default=None, description="Video start timestamp if applicable")
    timestamp_end: float | str | None = Field(default=None, description="Video end timestamp if applicable")
    source_id: str = Field(description="The source document this question came from")
    difficulty: Literal["foundational", "intermediate", "advanced"] = "intermediate"


class SafeQuestion(BaseModel):
    """Frontend-ready question payload: correct_index, correct_answer & explanation are STRIPPED.
    Source provenance (page numbers, chunk IDs) is retained so student can trace back to source.
    """
    question_id: str
    concept_id: str
    concept_name: str
    stem: str
    options: list[SafeOption]
    difficulty: Literal["foundational", "intermediate", "advanced"] = "intermediate"
    page_start: int | None = None
    page_end: int | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    timestamp_start: float | str | None = None
    timestamp_end: float | str | None = None


class ConceptSnapshot(BaseModel):
    """Compact concept dependency snapshot cached inside an AssessmentSession."""
    concept_id: str
    concept_name: str = ""
    definition: str = ""
    prerequisite_concept_ids: list[str] = Field(default_factory=list)
    source_content_ids: list[str] = Field(default_factory=list)
    difficulty: Literal["foundational", "intermediate", "advanced"] = "intermediate"
    source_id: str | None = None


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
    concept_snapshot: dict[str, ConceptSnapshot] = Field(
        default_factory=dict,
        description="Compact KnowledgeGraph concept dependency snapshot for offline grading & prerequisite analysis",
    )


def reconstruct_kg_from_snapshot(
    session: AssessmentSession,
    expected_source_id: str | None = None,
) -> KnowledgeGraph | None:
    """Reconstruct a minimal KnowledgeGraph from the session's concept snapshot.
    Enforces source_id integrity and preserves prerequisite links without global state mutation.
    """
    if expected_source_id and session.source_id != expected_source_id:
        raise ValueError(
            f"Session source_id mismatch: session is for '{session.source_id}', expected '{expected_source_id}'"
        )
    if not session.concept_snapshot:
        return None

    target_source = expected_source_id or session.source_id
    concepts: dict[str, ConceptNode] = {}
    for cid, snap in session.concept_snapshot.items():
        # Source integrity check on per-concept snapshot if source_id is set
        if snap.source_id and target_source and snap.source_id != target_source:
            raise ValueError(
                f"Cross-source integrity violation: concept snapshot '{cid}' belongs to source "
                f"'{snap.source_id}', but session source_id is '{target_source}'."
            )
        concepts[cid] = ConceptNode(
            concept_id=snap.concept_id,
            name=snap.concept_name or cid,
            definition=snap.definition or None,
            prerequisite_concept_ids=list(snap.prerequisite_concept_ids or []),
            source_content_ids=list(snap.source_content_ids or []),
        )
    return KnowledgeGraph(concepts=concepts)


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
    status: MasteryStatus = "NOT_ATTEMPTED"
    iteration_count: int = Field(default=0, description="How many times this concept was tested and failed")
    last_attempt_at: str | None = None
    last_score: float = Field(default=0.0, description="Score on latest attempt (0.0 - 100.0)")


class VideoTarget(BaseModel):
    """A single concept that needs a targeted AI explanation video (Step 3 handoff)."""
    concept_id: str
    concept_name: str
    definition: str = ""
    difficulty: Literal["foundational", "intermediate", "advanced"] = "intermediate"
    score: float = Field(description="Per-concept score on the latest attempt (0-100)")
    status: Literal["NEEDS_VIDEO", "REQUIRES_HUMAN_FALLBACK"] = "NEEDS_VIDEO"
    target_seconds: int = Field(default=30, description="Target AI video duration: 30s foundational, 45s intermediate, 60s advanced")
    directive: str = Field(default="", description="Human-readable directive for video generation")
    chunk_ids: list[str] = Field(default_factory=list, description="Provenance: source chunks to animate/narrate")
    source_content_ids: list[str] = Field(default_factory=list, description="ContentUnit IDs for Step 3 grounding")
    page_start: int | None = None
    page_end: int | None = None


class VideoTargetMatrix(BaseModel):
    """THE Step 2 → Step 3 handoff artifact. Tells the video engine exactly what to animate.

    Built after grading:
    - Everything passed (score >= threshold) is filtered out.
    - Everything on the kill switch (>3 historical failures) is tagged REQUIRES_HUMAN_FALLBACK.
    - Every failed concept gets a duration-scaled video target (30s / 45s / 60s).
    """
    student_id: str
    source_id: str
    source_filename: str = ""
    overall_score: float = 0.0
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: int = 1
    decision: Literal["GENERATE_VIDEOS", "ALL_MASTERED", "HUMAN_INTERVENTION"] = "GENERATE_VIDEOS"
    summary: str = Field(default="", description="Direct summary instruction for Step 3, e.g. 'Generate a 30-second AI video explaining Concept B, and a 45-second AI video explaining Concept C.'")
    videos: list[VideoTarget] = Field(default_factory=list)
    human_intervention_concepts: list[str] = Field(
        default_factory=list,
        description="Concept names that hit the anti-loop kill switch requiring human intervention",
    )
    human_intervention_concept_ids: list[str] = Field(
        default_factory=list,
        description="Concept IDs requiring human instructor intervention",
    )


class StudentLearningProfile(BaseModel):
    """Complete learning profile for a student on a specific source."""
    student_id: str
    source_id: str
    overall_score: float = Field(default=0.0, description="Average score across all sessions (0-100)")
    total_sessions: int = 0
    strong_concepts: list[str] = Field(default_factory=list, description="Concept names mastered")
    weak_concepts: list[str] = Field(default_factory=list, description="Concept names needing work")
    strong_concept_ids: list[str] = Field(default_factory=list, description="Concept IDs mastered")
    weak_concept_ids: list[str] = Field(default_factory=list, description="Concept IDs needing work or on kill switch")
    prerequisite_gaps: list[str] = Field(default_factory=list, description="Prerequisite gap descriptions")
    concept_masteries: dict[str, ConceptMastery] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @model_validator(mode="after")
    def _populate_concept_ids_from_masteries(self) -> "StudentLearningProfile":
        """Safe backward compatibility for legacy profile records."""
        if self.concept_masteries and not self.strong_concept_ids and not self.weak_concept_ids:
            for cid, m in self.concept_masteries.items():
                if m.status == "MASTERED":
                    self.strong_concept_ids.append(cid)
                elif m.status in ("LEARNING", "REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK"):
                    self.weak_concept_ids.append(cid)
        return self


class AssessmentStartRequest(BaseModel):
    """Payload for initiating Step 2 assessment directly from Step 1 output."""
    student_id: str = Field(default="student_default", description="Student identifier")
    source_id: str = Field(description="Target source identifier")
    step1_output: dict[str, Any] | None = Field(
        default=None,
        description="Raw or structured JSON output from Step 1 upload/ingestion",
    )
    max_questions: int | None = Field(
        default=None,
        description="Optional override for target question count",
    )
    # Direct fields if sent flat in request body
    topic_blueprint: dict[str, Any] | None = None
    key_concepts: list[Any] | None = None
    knowledge_graph: dict[str, Any] | None = None
    chunks: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
