"""Step 2: Student Knowledge Profiling — Assessment & Mastery Engine."""

from .engine import grade_submission
from .generator import generate_question
from .planner import classify_difficulty, plan_assessment
from .profile import get_or_create_profile, load_profile, save_profile
from .schemas import (
    AssessmentOption,
    AssessmentSession,
    AssessmentStartRequest,
    ConceptMastery,
    Question,
    QuestionResult,
    SafeOption,
    SafeQuestion,
    StudentLearningProfile,
    StudentSubmission,
    SubmissionResult,
    VideoTarget,
    VideoTargetMatrix,
)
from .session_store import load_session, save_session
from .validator import is_duplicate, validate_question
from .video_target import (
    build_video_target_matrix,
    load_video_matrix,
    save_video_matrix,
)

__all__ = [
    "grade_submission",
    "generate_question",
    "plan_assessment",
    "classify_difficulty",
    "get_or_create_profile",
    "load_profile",
    "save_profile",
    "AssessmentOption",
    "AssessmentSession",
    "AssessmentStartRequest",
    "ConceptMastery",
    "Question",
    "QuestionResult",
    "SafeOption",
    "SafeQuestion",
    "StudentLearningProfile",
    "StudentSubmission",
    "SubmissionResult",
    "VideoTarget",
    "VideoTargetMatrix",
    "load_session",
    "save_session",
    "validate_question",
    "is_duplicate",
    "build_video_target_matrix",
    "save_video_matrix",
    "load_video_matrix",
]
