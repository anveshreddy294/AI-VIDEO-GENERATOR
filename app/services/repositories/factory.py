"""Repository factory for VisualAI persistence (Phase 12C).

Returns the configured repository implementation (File or Supabase).
"""

from ...core.config import settings
from ...core.supabase import AuthenticatedUser, SupabaseRuntime, SupabaseConfigurationError
from .base import SourceRepository, AssessmentRepository, LearningProfileRepository
from .file_repository import FileSourceRepository, FileAssessmentRepository, FileLearningProfileRepository
from .supabase_repository import SupabaseSourceRepository, SupabaseAssessmentRepository, SupabaseLearningProfileRepository
from ..security.legacy_boundary import require_local_learning_storage


def get_source_repository(*, user: AuthenticatedUser | None = None, token: str | None = None,
                          runtime: SupabaseRuntime | None = None) -> SourceRepository:
    """Return the active source repository based on database provider configuration."""
    if settings.database_provider == "supabase":
        if user is None or not token or runtime is None:
            raise SupabaseConfigurationError("Verified user context required for Supabase sources")
        return SupabaseSourceRepository(user, token, runtime)
    if settings.database_provider not in {"file", "local"}:
        raise SupabaseConfigurationError("Unknown source database provider")
    return FileSourceRepository()


def get_assessment_repository() -> AssessmentRepository:
    """Return the active assessment repository based on database provider configuration."""
    require_local_learning_storage()
    return FileAssessmentRepository()


def get_learning_profile_repository() -> LearningProfileRepository:
    """Return the active learning profile repository based on database provider configuration."""
    require_local_learning_storage()
    return FileLearningProfileRepository()
