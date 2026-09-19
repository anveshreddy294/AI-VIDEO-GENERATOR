"""Pydantic data models and contracts for Step 3 Video Generation Engine."""

from datetime import datetime, timezone
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class VideoScene(BaseModel):
    """A single coherent scene/slide in the targeted remediation video."""

    scene_number: int = Field(ge=1, description="Sequential scene index (1-based)")
    scene_type: Literal[
        "title_hook",
        "concept_breakdown",
        "diagram_focus",
        "formula_derivation",
        "summary_takeaway",
    ] = Field(
        default="concept_breakdown",
        description="Pedagogical scene classification",
    )
    title: str = Field(..., max_length=100, description="On-screen scene title / header")
    narration: str = Field(..., description="Voiceover spoken narration text for this scene")
    onscreen_bullets: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Key bullet points displayed on screen",
    )
    highlight_text: Optional[str] = Field(
        default=None,
        description="Core law, formula, or definition to render in an emphasized callout card",
    )
    diagram_cu_id: Optional[str] = Field(
        default=None,
        description="ContentUnit ID of source diagram or image asset if applicable",
    )
    duration_seconds: float = Field(
        gt=0.0,
        description="Target duration for this scene in seconds",
    )


class VideoScript(BaseModel):
    """Complete multi-scene script for a targeted video lesson."""

    video_id: str = Field(..., description="Unique deterministic or random identifier for video")
    student_id: str = Field(..., description="ID of student receiving remediation")
    source_id: str = Field(..., description="Source document ID")
    concept_id: str = Field(..., description="Concept being taught")
    concept_name: str = Field(..., description="Human-readable concept name")
    difficulty: Literal["foundational", "intermediate", "advanced"] = Field(
        default="intermediate",
        description="Difficulty level dictating target length (30s, 45s, 60s)",
    )
    target_total_seconds: int = Field(
        ...,
        description="Strict target duration (30 for foundational, 45 for intermediate, 60 for advanced)",
    )
    scenes: List[VideoScene] = Field(
        ...,
        min_length=1,
        description="Ordered list of scenes comprising the micro-lesson",
    )
    estimated_word_count: int = Field(
        default=0,
        ge=0,
        description="Total spoken word count across all scenes",
    )
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Source RichChunk IDs used for factual grounding",
    )
    diagnostics: Optional[dict] = Field(
        default=None,
        description="Structured stage diagnostics detailing provider, grounding, and fallback state",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of script generation",
    )


class VideoRenderJob(BaseModel):
    """Execution status and artifact tracking for video rendering jobs."""

    job_id: str = Field(..., description="Unique job identifier")
    video_id: str = Field(..., description="Identifier of the generated video")
    student_id: str = Field(..., description="Target student ID")
    source_id: str = Field(..., description="Origin source document ID")
    concept_id: str = Field(..., description="Target concept ID")
    concept_name: str = Field(..., description="Target concept name")
    status: Literal[
        "pending",
        "generating_script",
        "synthesizing_voiceover",
        "rendering_visuals",
        "muxing_media",
        "completed",
        "failed",
    ] = Field(default="pending", description="Current execution state")
    progress_percent: int = Field(
        ge=0,
        le=100,
        default=0,
        description="Overall progress percentage 0-100",
    )
    current_stage: str = Field(
        default="Queued",
        description="Human-readable status of the current stage",
    )
    video_file_path: Optional[str] = Field(
        default=None,
        description="Relative or absolute path to the generated MP4 file",
    )
    subtitles_file_path: Optional[str] = Field(
        default=None,
        description="Path to WebVTT subtitle track",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if the job failed",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Actual measured duration of the final video",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Job creation timestamp",
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="Job completion timestamp",
    )
