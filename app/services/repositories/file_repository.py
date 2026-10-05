"""File-based local JSON repository implementation (Phase 12C).

Implements SourceRepository, AssessmentRepository, and LearningProfileRepository
backed by the local atomic runtime storage.
"""

from typing import Any
from pathlib import Path
from ..schemas import ContentUnit, KnowledgeGraph, SourceRecord
from ..assessment.schemas import AssessmentSession, StudentLearningProfile, VideoTargetMatrix
from ..registry import (
    get_source_record,
    save_source_record,
    load_content_units,
    save_content_units,
    load_knowledge_graph,
    save_knowledge_graph,
    _load_sources_index,
)
from ..assessment.session_store import load_session, save_session
from ..assessment.profile import load_profile, save_profile
from ..assessment.video_target import load_video_matrix, save_video_matrix
from .base import SourceRepository, AssessmentRepository, LearningProfileRepository


class FileSourceRepository:
    """File-backed source registry and content unit repository."""

    def get_source(self, source_id: str) -> SourceRecord | None:
        try:
            return get_source_record(source_id)
        except Exception:
            return None

    def save_source(self, record: SourceRecord) -> None:
        save_source_record(record)

    def list_sources(self) -> list[SourceRecord]:
        index = _load_sources_index()
        records: list[SourceRecord] = []
        for sid, data in index.items():
            try:
                records.append(SourceRecord.model_validate(data))
            except Exception:
                continue
        return records

    def get_content_units(self, source_id: str) -> list[ContentUnit]:
        return load_content_units(source_id)

    def save_content_units(self, source_id: str, units: list[ContentUnit]) -> None:
        save_content_units(source_id, units)

    def get_knowledge_graph(self, source_id: str) -> KnowledgeGraph | None:
        return load_knowledge_graph(source_id)

    def save_knowledge_graph(self, source_id: str, kg: KnowledgeGraph) -> None:
        save_knowledge_graph(source_id, kg)


class FileAssessmentRepository:
    """File-backed assessment session repository."""

    def get_session(self, session_id: str) -> AssessmentSession | None:
        return load_session(session_id)

    def save_session(self, session: AssessmentSession) -> None:
        save_session(session)


class FileLearningProfileRepository:
    """File-backed learning profile and video target repository."""

    def get_profile(self, student_id: str, source_id: str) -> StudentLearningProfile | None:
        return load_profile(student_id, source_id)

    def save_profile(self, profile: StudentLearningProfile) -> None:
        save_profile(profile)

    def get_video_matrix(self, student_id: str, source_id: str) -> VideoTargetMatrix | None:
        return load_video_matrix(student_id, source_id)

    def save_video_matrix(self, matrix: VideoTargetMatrix) -> None:
        save_video_matrix(matrix)
