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
from .reassessment_queue import ReassessmentQueue, ReassessmentSession
from .reassessment_service import ReassessmentService
from .repository import InMemoryMasteryRepository, MasteryRepository
from .roadmap_models import (
    LearningActionType,
    LearningRoadmap,
    NextLearningAction,
    ReasonCode,
)
from .state_machine import ALLOWED_TRANSITIONS, MasteryStateMachine

from .remediation_models import RemediationJob, RemediationJobStatus
from .remediation_repository import (
    InMemoryRemediationJobRepository,
    RemediationJobRepository,
)
from .remediation_orchestrator import RemediationOrchestrator

from .api_schemas import (
    AssessmentSubmissionRequestDTO,
    AssessmentSubmissionResponseDTO,
    ConceptMasterySummary,
    LearningStateResponse,
    NextActionResponse,
    RemediationStartRequestDTO,
    RemediationStartResponseDTO,
    RemediationStatusResponseDTO,
    RoadmapResponse,
    SafeReassessmentQuestionResponse,
)
from .application_service import (
    AdaptiveLearningService,
    ConceptNotEligibleForRemediationError,
    RemediationJobNotFoundError,
    SourceAccessDeniedError,
    SourceNotFoundError,
)
from .misconception_models import (
    DistractorMisconceptionMetadata,
    MisconceptionConfidenceState,
    MisconceptionEvidence,
    MisconceptionStatus,
    TeachingStrategyDecision,
    TeachingStrategyReasonCode,
    TeachingStrategyType,
    normalize_misconception_code,
)
from .misconception_repository import (
    InMemoryMisconceptionRepository,
    MisconceptionRepository,
)
from .strategy_selector import TeachingStrategySelector

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
    "ReassessmentQueue",
    "ReassessmentSession",
    "LearningActionType",
    "ReasonCode",
    "NextLearningAction",
    "LearningRoadmap",
    "ConceptDependencyProvider",
    "PersonalizationService",
    "RemediationJobStatus",
    "RemediationJob",
    "RemediationJobRepository",
    "InMemoryRemediationJobRepository",
    "RemediationOrchestrator",
    "AssessmentSubmissionRequestDTO",
    "AssessmentSubmissionResponseDTO",
    "ConceptMasterySummary",
    "LearningStateResponse",
    "NextActionResponse",
    "RemediationStartRequestDTO",
    "RemediationStartResponseDTO",
    "RemediationStatusResponseDTO",
    "RoadmapResponse",
    "SafeReassessmentQuestionResponse",
    "AdaptiveLearningService",
    "SourceNotFoundError",
    "SourceAccessDeniedError",
    "ConceptNotEligibleForRemediationError",
    "RemediationJobNotFoundError",
    "DistractorMisconceptionMetadata",
    "MisconceptionConfidenceState",
    "MisconceptionEvidence",
    "MisconceptionStatus",
    "TeachingStrategyType",
    "TeachingStrategyReasonCode",
    "TeachingStrategyDecision",
    "normalize_misconception_code",
    "MisconceptionRepository",
    "InMemoryMisconceptionRepository",
    "TeachingStrategySelector",
]

