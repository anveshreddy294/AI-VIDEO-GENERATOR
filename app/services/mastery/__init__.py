"""Step 5 Domain Package — Mastery Model, State Machine, Attempts & Reassessment.

Exports domain entities, states, state machine, attempt services, and repositories.
"""

from .attempt_models import AssessmentAttempt, AssessmentType
from .attempt_repository import (
    AssessmentAttemptRepository,
    InMemoryAssessmentAttemptRepository,
)
from .attempt_service import (
    AssessmentAttemptResult,
    AssessmentAttemptService,
    AssessmentServiceError,
    AssessmentSubmissionRequest,
    GroundingIntegrityError,
    UnknownQuestionError,
)
from .models import (
    DomainInvariantViolation,
    InvalidStateTransitionError,
    MasteryConfig,
    MasteryRecord,
    MasteryState,
)
from .dependency_provider import ConceptDependencyProvider
from .personalization_service import PersonalizationService
from .question_registry import (
    AuthoritativeQuestion,
    InMemoryQuestionRegistry,
    QuestionRegistry,
)
from .reassessment_service import ReassessmentService
from .repository import InMemoryMasteryRepository, MasteryRepository
from .roadmap_models import (
    LearningActionType,
    LearningRoadmap,
    NextLearningAction,
    ReasonCode,
)
from .state_machine import ALLOWED_TRANSITIONS, MasteryStateMachine

__all__ = [
    "DomainInvariantViolation",
    "InvalidStateTransitionError",
    "MasteryConfig",
    "MasteryRecord",
    "MasteryState",
    "MasteryStateMachine",
    "ALLOWED_TRANSITIONS",
    "MasteryRepository",
    "InMemoryMasteryRepository",
    "AssessmentType",
    "AssessmentAttempt",
    "AssessmentAttemptRepository",
    "InMemoryAssessmentAttemptRepository",
    "AuthoritativeQuestion",
    "QuestionRegistry",
    "InMemoryQuestionRegistry",
    "AssessmentSubmissionRequest",
    "AssessmentAttemptResult",
    "AssessmentAttemptService",
    "AssessmentServiceError",
    "GroundingIntegrityError",
    "UnknownQuestionError",
    "ReassessmentService",
    "LearningActionType",
    "ReasonCode",
    "NextLearningAction",
    "LearningRoadmap",
    "ConceptDependencyProvider",
    "PersonalizationService",
]
