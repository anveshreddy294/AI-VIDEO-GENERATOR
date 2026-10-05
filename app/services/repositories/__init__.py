"""Repository package exports."""

from .base import AssessmentRepository, LearningProfileRepository, SourceRepository
from .factory import (
    get_assessment_repository,
    get_learning_profile_repository,
    get_source_repository,
)
from .file_repository import (
    FileAssessmentRepository,
    FileLearningProfileRepository,
    FileSourceRepository,
)
from .supabase_repository import (
    SupabaseAssessmentRepository,
    SupabaseLearningProfileRepository,
    SupabaseSourceRepository,
)

__all__ = [
    "SourceRepository",
    "AssessmentRepository",
    "LearningProfileRepository",
    "FileSourceRepository",
    "FileAssessmentRepository",
    "FileLearningProfileRepository",
    "SupabaseSourceRepository",
    "SupabaseAssessmentRepository",
    "SupabaseLearningProfileRepository",
    "get_source_repository",
    "get_assessment_repository",
    "get_learning_profile_repository",
]
