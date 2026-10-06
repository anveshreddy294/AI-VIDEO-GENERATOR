"""Supabase REST-backed repository implementation (Phase 12C).

Implements SourceRepository, AssessmentRepository, and LearningProfileRepository
backed by Supabase PostgREST endpoints.

Source persistence is authoritative through the shared runtime.
Assessment and learning-profile adapters remain unchanged and file-based.
"""

from typing import Any

from ...core.config import settings
from ..schemas import ContentUnit, KnowledgeGraph, SourceRecord
from ..assessment.schemas import AssessmentSession, StudentLearningProfile, VideoTargetMatrix
from .file_repository import FileSourceRepository, FileAssessmentRepository, FileLearningProfileRepository



from .source_repository import SupabaseSourceRepository


class SupabaseAssessmentRepository:
    """Supabase-backed assessment session repository with local fallback."""

    def __init__(self, fallback: FileAssessmentRepository | None = None) -> None:
        self.fallback = fallback or FileAssessmentRepository()
        self.url = (settings.supabase_url or "").rstrip("/")
        self.key = settings.supabase_service_role_key or settings.supabase_anon_key or ""
        self.is_configured = bool(self.url and self.key)

    def get_session(self, session_id: str) -> AssessmentSession | None:
        return self.fallback.get_session(session_id)

    def save_session(self, session: AssessmentSession) -> None:
        self.fallback.save_session(session)


class SupabaseLearningProfileRepository:
    """Supabase-backed learning profile repository with local fallback."""

    def __init__(self, fallback: FileLearningProfileRepository | None = None) -> None:
        self.fallback = fallback or FileLearningProfileRepository()
        self.url = (settings.supabase_url or "").rstrip("/")
        self.key = settings.supabase_service_role_key or settings.supabase_anon_key or ""
        self.is_configured = bool(self.url and self.key)

    def get_profile(self, student_id: str, source_id: str) -> StudentLearningProfile | None:
        return self.fallback.get_profile(student_id, source_id)

    def save_profile(self, profile: StudentLearningProfile) -> None:
        self.fallback.save_profile(profile)

    def get_video_matrix(self, student_id: str, source_id: str) -> VideoTargetMatrix | None:
        return self.fallback.get_video_matrix(student_id, source_id)

    def save_video_matrix(self, matrix: VideoTargetMatrix) -> None:
        self.fallback.save_video_matrix(matrix)
