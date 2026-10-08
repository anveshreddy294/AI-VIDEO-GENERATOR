"""Supabase REST-backed repository implementation (Phase 12C).

Implements SourceRepository, AssessmentRepository, and LearningProfileRepository
backed by Supabase PostgREST endpoints.

Source persistence is authoritative through the shared runtime.
Assessment sessions use canonical transactions. Legacy profiles remain file-only.
"""

from typing import Any, TYPE_CHECKING
from pydantic import JsonValue
if TYPE_CHECKING:
    from .knowledge_repository import KnowledgeRepository
    from ..assessment.schemas import AssessmentPerformance

from ...core.config import settings
from ..schemas import ContentUnit, KnowledgeGraph, SourceRecord
from ..assessment.schemas import AssessmentSession, StudentLearningProfile, VideoTargetMatrix
from .file_repository import FileSourceRepository, FileAssessmentRepository, FileLearningProfileRepository
from ..security.legacy_boundary import require_local_learning_storage



from .source_repository import SupabaseSourceRepository


class SupabaseAssessmentRepository:
    """Backend-only canonical transactions; verified context is required, no fallback."""

    def __init__(self, context: "KnowledgeRepository | None" = None) -> None:
        if context is None:
            from ...core.supabase import SupabaseConfigurationError
            raise SupabaseConfigurationError("Verified assessment context required")
        self.context = context

    def transact(self, action: str, session_id: str, payload: dict[str, JsonValue] | None = None) -> AssessmentSession | None:
        from ...core.supabase import SupabaseError, SupabaseConflict
        from ..repositories.knowledge_repository import KnowledgeError
        from pydantic import ValidationError
        try:
            value = self.context.runtime.admin_request("POST", "/rest/v1/rpc/visualai_assessment_transaction",
                body={"p_action": action, "p_user_id": str(self.context.user.user_id),
                      "p_assessment_id": session_id, "p_payload": payload or {}})
        except SupabaseConflict:
            raise KnowledgeError("CONFLICT") from None
        except SupabaseError:
            raise KnowledgeError("PROVIDER_UNAVAILABLE") from None
        if value is None:
            return None
        try:
            session = AssessmentSession.model_validate(value)
        except ValidationError:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
        if session.student_id != str(self.context.user.user_id) or session.session_id != session_id:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return session

    def get_session(self, session_id: str) -> AssessmentSession | None:
        return self.transact("load", session_id)

    def save_session(self, session: AssessmentSession) -> None:
        from ..repositories.knowledge_repository import KnowledgeError
        if session.student_id != str(self.context.user.user_id) or session.learning_session_id is None or session.source_version is None:
            raise KnowledgeError("INVALID_SCOPE")
        if self.transact("create",session.session_id,session.model_dump(mode="json")) is None:
            raise KnowledgeError("PROVIDER_UNAVAILABLE")

    def submit(self, session: AssessmentSession, answers: dict[str,int], result: "AssessmentPerformance") -> AssessmentSession:
        from ..repositories.knowledge_repository import KnowledgeError
        saved = self.transact("submit",session.session_id,{"answers": answers,"result": result.model_dump(mode="json")})
        if saved is None:
            raise KnowledgeError("NOT_FOUND")
        return saved


class SupabaseLearningProfileRepository:
    """Supabase-backed learning profile repository with local fallback."""

    def __init__(self, fallback: FileLearningProfileRepository | None = None) -> None:
        require_local_learning_storage()
        self.fallback = fallback or FileLearningProfileRepository()

    def get_profile(self, student_id: str, source_id: str) -> StudentLearningProfile | None:
        require_local_learning_storage()
        return self.fallback.get_profile(student_id, source_id)

    def save_profile(self, profile: StudentLearningProfile) -> None:
        require_local_learning_storage()
        self.fallback.save_profile(profile)

    def get_video_matrix(self, student_id: str, source_id: str) -> VideoTargetMatrix | None:
        require_local_learning_storage()
        return self.fallback.get_video_matrix(student_id, source_id)

    def save_video_matrix(self, matrix: VideoTargetMatrix) -> None:
        require_local_learning_storage()
        self.fallback.save_video_matrix(matrix)
