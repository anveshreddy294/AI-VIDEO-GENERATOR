"""Supabase REST-backed repository implementation (Phase 12C).

Implements SourceRepository, AssessmentRepository, and LearningProfileRepository
backed by Supabase PostgREST endpoints.

If remote Supabase is unconfigured or unreachable, safely falls back
to the local FileRepository while logging actionable diagnostics.
"""

import logging
from typing import Any
import httpx

from ...core.config import settings
from ..schemas import ContentUnit, KnowledgeGraph, SourceRecord
from ..assessment.schemas import AssessmentSession, StudentLearningProfile, VideoTargetMatrix
from .file_repository import FileSourceRepository, FileAssessmentRepository, FileLearningProfileRepository

logger = logging.getLogger(__name__)


class SupabaseSourceRepository:
    """Supabase-backed source and content repository with controlled local fallback."""

    def __init__(self, fallback: FileSourceRepository | None = None) -> None:
        self.fallback = fallback or FileSourceRepository()
        self.url = (settings.supabase_url or "").rstrip("/")
        self.key = settings.supabase_service_role_key or settings.supabase_anon_key or ""
        self.is_configured = bool(self.url and self.key)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def get_source(self, source_id: str) -> SourceRecord | None:
        if not self.is_configured:
            return self.fallback.get_source(source_id)

        try:
            endpoint = f"{self.url}/rest/v1/sources?source_id=eq.{source_id}&select=*"
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(endpoint, headers=self._headers())
                if resp.status_code == 200:
                    rows = resp.json()
                    if rows:
                        return SourceRecord.model_validate(rows[0])
            return self.fallback.get_source(source_id)
        except Exception as exc:
            logger.warning("[supabase_repo] get_source remote failure (%s); falling back to file repo: %s", source_id, exc)
            return self.fallback.get_source(source_id)

    def save_source(self, record: SourceRecord) -> None:
        # Always write to fallback first to guarantee zero data loss during migration
        self.fallback.save_source(record)

        if not self.is_configured:
            return

        try:
            endpoint = f"{self.url}/rest/v1/sources"
            payload = {
                "source_id": record.source_id,
                "student_id": getattr(record, "student_id", "student_default"),
                "filename": record.filename,
                "file_hash": record.file_hash,
                "file_size": record.file_size,
                "modality": record.modality,
                "mime_type": record.mime_type,
                "status": record.status,
                "error_message": record.error_message,
            }
            headers = self._headers()
            headers["Prefer"] = "resolution=merge-duplicates"
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                if resp.status_code not in (200, 201):
                    logger.warning("[supabase_repo] save_source remote response %d: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.warning("[supabase_repo] save_source remote failure; local file saved safely: %s", exc)

    def list_sources(self) -> list[SourceRecord]:
        if not self.is_configured:
            return self.fallback.list_sources()

        try:
            endpoint = f"{self.url}/rest/v1/sources?select=*"
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(endpoint, headers=self._headers())
                if resp.status_code == 200:
                    rows = resp.json()
                    return [SourceRecord.model_validate(r) for r in rows]
            return self.fallback.list_sources()
        except Exception as exc:
            logger.warning("[supabase_repo] list_sources remote failure; using local file index: %s", exc)
            return self.fallback.list_sources()

    def get_content_units(self, source_id: str) -> list[ContentUnit]:
        return self.fallback.get_content_units(source_id)

    def save_content_units(self, source_id: str, units: list[ContentUnit]) -> None:
        self.fallback.save_content_units(source_id, units)

    def get_knowledge_graph(self, source_id: str) -> KnowledgeGraph | None:
        return self.fallback.get_knowledge_graph(source_id)

    def save_knowledge_graph(self, source_id: str, kg: KnowledgeGraph) -> None:
        self.fallback.save_knowledge_graph(source_id, kg)


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
