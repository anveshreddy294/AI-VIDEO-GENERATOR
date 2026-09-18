"""Pydantic schemas for Video RAG & Timestamp Q&A Agent."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    """Source grounding reference from authoritative study material."""
    chunk_id: str = Field(description="Unique identifier of the grounded source chunk")
    page: Optional[int] = Field(default=None, description="Page number in original document if available")
    text_preview: str = Field(description="Explanatory snippet from the source text")


class SceneReference(BaseModel):
    """Timestamp window and metadata for an active video scene."""
    scene_number: int = Field(description="1-based scene index")
    title: str = Field(description="Scene title / header")
    start_seconds: float = Field(description="Start time in seconds")
    end_seconds: float = Field(description="End time in seconds")
    timestamp_label: str = Field(description="Human readable time range e.g. '0:14 - 0:28'")


class VideoQARequest(BaseModel):
    """Student query payload submitted from the video player."""
    video_id: str = Field(description="Unique video identifier")
    question: str = Field(description="Student query or clarification request")
    timestamp: Optional[float] = Field(default=None, ge=0.0, description="Current video playback position in seconds")
    student_id: Optional[str] = Field(default=None, description="Student identifier")


class VideoQAResponse(BaseModel):
    """Pedagogical response with grounded source citations and timestamp references."""
    answer: str = Field(description="Authoritative, pedagogical explanation")
    video_id: str = Field(description="Video identifier")
    concept_name: str = Field(description="Target concept name")
    active_scene: Optional[SceneReference] = Field(default=None, description="Active video scene at requested timestamp")
    citations: List[SourceCitation] = Field(default_factory=list, description="Authoritative grounding citations")
    suggested_questions: List[str] = Field(default_factory=list, description="Recommended follow-up questions")
