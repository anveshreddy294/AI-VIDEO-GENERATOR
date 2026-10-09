"""Step 5E API Router — Adaptive Learning & Personalized Remediation Endpoints.

Mounts under `/api/learning`.
Coordinates learner progression through the verified Step 5 domain services:
- GET  /api/learning/{source_id}/state
- GET  /api/learning/{source_id}/roadmap
- GET  /api/learning/{source_id}/next-action
- POST /api/learning/{source_id}/assessment/submit
- POST /api/learning/{source_id}/reassessment/generate
- POST /api/learning/{source_id}/remediation
- GET  /api/learning/{source_id}/remediation/{job_id}
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ..services.mastery import (
    AdaptiveLearningService,
    AssessmentServiceError,
    AssessmentSubmissionRequestDTO,
    AssessmentSubmissionResponseDTO,
    ConceptNotEligibleForRemediationError,
    DomainInvariantViolation,
    GroundingIntegrityError,
    InvalidStateTransitionError,
    LearningStateResponse,
    NextActionResponse,
    RemediationJobNotFoundError,
    RemediationStartRequestDTO,
    RemediationStartResponseDTO,
    RemediationStatusResponseDTO,
    RoadmapResponse,
    SafeReassessmentQuestionResponse,
    SourceAccessDeniedError,
    SourceNotFoundError,
    UnknownQuestionError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["Step 5 - Adaptive Learning & Remediation"])

# Singleton application service instance for in-process memory persistence across requests
_service_instance: AdaptiveLearningService | None = None


def get_adaptive_learning_service() -> AdaptiveLearningService:
    """Dependency provider returning singleton AdaptiveLearningService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = AdaptiveLearningService()
    return _service_instance


def resolve_user_id(
    user_id: str | None = Query(
        default=None,
        description="Current learner identity (defaults to 'student_default' in current dev environment).",
    )
) -> str:
    """Resolve active user identity from query parameter.

    DOCUMENTATION BOUNDARY:
    AUTHENTICATION_NOT_YET_PRODUCTION_READY.
    In the current architecture, authenticated Supabase Auth JWT middleware
    is planned for subsequent development. The system currently accepts caller-supplied
    or default student identities while strictly enforcing cross-user and cross-source isolation.
    """
    clean = user_id.strip() if user_id else ""
    return clean or "student_default"


def _handle_domain_exception(exc: Exception) -> None:
    """Map domain exceptions to intentional HTTP status codes without Python tracebacks."""
    if isinstance(exc, SourceNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "SOURCE_NOT_FOUND", "message": str(exc)},
        )
    elif isinstance(exc, UnknownQuestionError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "UNKNOWN_QUESTION", "message": str(exc)},
        )
    elif isinstance(exc, RemediationJobNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REMEDIATION_JOB_NOT_FOUND", "message": str(exc)},
        )
    elif isinstance(exc, (SourceAccessDeniedError, GroundingIntegrityError)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACCESS_DENIED_OR_ISOLATION_VIOLATION", "message": str(exc)},
        )
    elif isinstance(exc, InvalidStateTransitionError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "INVALID_STATE_TRANSITION", "message": str(exc)},
        )
    elif isinstance(exc, ConceptNotEligibleForRemediationError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "CONCEPT_NOT_ELIGIBLE_FOR_REMEDIATION", "message": str(exc)},
        )
    elif isinstance(exc, DomainInvariantViolation):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "DOMAIN_INVARIANT_VIOLATION", "message": str(exc)},
        )
    elif isinstance(exc, AssessmentServiceError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ASSESSMENT_SERVICE_ERROR", "message": str(exc)},
        )
    else:
        logger.error("[learning_api] Unexpected exception: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INTERNAL_SERVER_ERROR", "message": f"{type(exc).__name__}: {exc}"},
        )


# =============================================================================
# 1. Learning State Snapshot
# =============================================================================
@router.get(
    "/{source_id}/state",
    response_model=LearningStateResponse,
    summary="Get Learner State Snapshot",
    description="Retrieve full concept mastery states, attempt counts, and overall progress for a source.",
)
def get_learning_state(
    source_id: str,
    user_id: Annotated[str, Depends(resolve_user_id)],
    session_id: str | None = Query(default=None),
    service: AdaptiveLearningService = Depends(get_adaptive_learning_service),
) -> LearningStateResponse:
    try:
        return service.get_learning_state(
            user_id=user_id,
            source_id=source_id,
            session_id=session_id,
        )
    except Exception as exc:
        _handle_domain_exception(exc)


# =============================================================================
# 2. Pure Roadmap Query
# =============================================================================
@router.get(
    "/{source_id}/roadmap",
    response_model=RoadmapResponse,
    summary="Get Personalized Learning Roadmap",
    description="Pure query returning deterministic partitioned concepts and current next action (0 LLM calls).",
)
def get_roadmap(
    source_id: str,
    user_id: Annotated[str, Depends(resolve_user_id)],
    session_id: str | None = Query(default=None),
    service: AdaptiveLearningService = Depends(get_adaptive_learning_service),
) -> RoadmapResponse:
    try:
        return service.get_roadmap(
            user_id=user_id,
            source_id=source_id,
            session_id=session_id,
        )
    except Exception as exc:
        _handle_domain_exception(exc)


# =============================================================================
# 3. Deterministic Next Action
# =============================================================================
@router.get(
    "/{source_id}/next-action",
    response_model=NextActionResponse,
    summary="Get Deterministic Next Action",
    description="Retrieve the single next pedagogical action for the learner without mutating state.",
)
def get_next_action(
    source_id: str,
    user_id: Annotated[str, Depends(resolve_user_id)],
    session_id: str | None = Query(default=None),
    service: AdaptiveLearningService = Depends(get_adaptive_learning_service),
) -> NextActionResponse:
    try:
        return service.get_next_action(
            user_id=user_id,
            source_id=source_id,
            session_id=session_id,
        )
    except Exception as exc:
        _handle_domain_exception(exc)


# =============================================================================
# 4. Authoritative Assessment Submission
# =============================================================================
@router.post(
    "/{source_id}/assessment/submit",
    response_model=AssessmentSubmissionResponseDTO,
    summary="Submit Assessment Attempt",
    description="Submit answer selection for authoritative server-side grading and mastery state mutation.",
)
def submit_assessment(
    source_id: str,
    user_id: Annotated[str, Depends(resolve_user_id)],
    submission: AssessmentSubmissionRequestDTO = Body(...),
    service: AdaptiveLearningService = Depends(get_adaptive_learning_service),
) -> AssessmentSubmissionResponseDTO:
    try:
        return service.submit_assessment(
            user_id=user_id,
            source_id=source_id,
            submission=submission,
        )
    except Exception as exc:
        _handle_domain_exception(exc)


# =============================================================================
# 5. Grounded Reassessment Generation
# =============================================================================
@router.post(
    "/{source_id}/reassessment/generate",
    response_model=SafeReassessmentQuestionResponse,
    summary="Generate Grounded Reassessment Question",
    description="Generate a novel grounded question for a concept in REASSESSING state with zero answer leakage.",
)
def generate_reassessment(
    source_id: str,
    user_id: Annotated[str, Depends(resolve_user_id)],
    concept_id: str | None = Query(default=None, description="Target concept ID (defaults to current NextLearningAction concept)."),
    session_id: str | None = Query(default=None),
    previous_question_id: str | None = Query(default=None),
    payload: Annotated[dict[str, Any] | None, Body()] = None,
    service: AdaptiveLearningService = Depends(get_adaptive_learning_service),
) -> SafeReassessmentQuestionResponse:
    target_cid = (payload.get("concept_id") if payload and isinstance(payload, dict) else None) or concept_id
    target_sid = (payload.get("session_id") if payload and isinstance(payload, dict) else None) or session_id
    target_prev = (payload.get("previous_question_id") if payload and isinstance(payload, dict) else None) or previous_question_id
    try:
        return service.generate_reassessment(
            user_id=user_id,
            source_id=source_id,
            concept_id=target_cid,
            session_id=target_sid,
            previous_question_id=target_prev,
        )
    except Exception as exc:
        _handle_domain_exception(exc)


# =============================================================================
# 6. Remediation Start (HTTP 202 Accepted)
# =============================================================================
@router.post(
    "/{source_id}/remediation",
    response_model=RemediationStartResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Remediation Video Generation",
    description="Asynchronously initiate or reuse a targeted remedial video job for a WEAK concept.",
)
async def start_remediation(
    source_id: str,
    user_id: Annotated[str, Depends(resolve_user_id)],
    request: RemediationStartRequestDTO = Body(default_factory=RemediationStartRequestDTO),
    service: AdaptiveLearningService = Depends(get_adaptive_learning_service),
) -> RemediationStartResponseDTO:
    try:
        return await service.start_remediation(
            user_id=user_id,
            source_id=source_id,
            concept_id=request.concept_id,
            session_id=request.session_id,
            force=request.force,
        )
    except Exception as exc:
        _handle_domain_exception(exc)


# =============================================================================
# 7. Remediation Status Polling
# =============================================================================
@router.get(
    "/{source_id}/remediation/{job_id}",
    response_model=RemediationStatusResponseDTO,
    summary="Get Remediation Job Status",
    description="Poll remedial video generation status with safe stream URLs and no filesystem disclosure.",
)
def get_remediation_status(
    source_id: str,
    job_id: str,
    user_id: Annotated[str, Depends(resolve_user_id)],
    service: AdaptiveLearningService = Depends(get_adaptive_learning_service),
) -> RemediationStatusResponseDTO:
    try:
        return service.get_remediation_status(
            user_id=user_id,
            source_id=source_id,
            job_id=job_id,
        )
    except Exception as exc:
        _handle_domain_exception(exc)


# =============================================================================
# 8. AI-First Content Explanation (Arbitrary Topic or Source-Assisted)
# =============================================================================
from starlette.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials
from ..core.config import settings
from ..core.supabase import SupabaseError
from ..services.security.auth import bearer_scheme, get_current_user, get_runtime, auth_http_error
from ..services.repositories.factory import get_source_repository
from ..services.ai_explanation import (
    AIExplanationRequest,
    AIExplanationResponse,
    AIExplanationService,
    PromptInjectionError,
)


@router.post(
    "/explain",
    response_model=AIExplanationResponse,
    summary="AI-First Educational Explanation",
    description="Explain arbitrary educational topics or uploaded source observations using the reasoning model without requiring uploads, Qdrant vectors, or web search.",
)
async def explain_topic(
    request: AIExplanationRequest,
    user_id: Annotated[str, Depends(resolve_user_id)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> AIExplanationResponse:
    # 1. Resolve student identity
    effective_user_id = user_id
    supabase_user = None
    if credentials is not None:
        try:
            runtime = get_runtime()
            supabase_user = await run_in_threadpool(get_current_user, credentials.credentials, runtime)
            effective_user_id = str(supabase_user.user_id)
        except SupabaseError as error:
            raise auth_http_error(error) from None
    elif settings.database_provider == "supabase":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. If source_id is requested, enforce access control and extract source observations
    source_observations: list[str] | None = None
    if request.source_id:
        if settings.database_provider == "supabase":
            if supabase_user is None or credentials is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to access saved source observations.",
                )
            runtime = get_runtime()
            repo = get_source_repository(user=supabase_user, token=credentials.credentials, runtime=runtime)
            record = repo.get_source(request.source_id)
            if record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "SOURCE_NOT_FOUND", "message": f"Source {request.source_id} not found or access denied."},
                )
            units = repo.get_content_units(request.source_id, request.source_version)
            source_observations = [u.text for u in units if u.text]
            if not request.topic:
                request.topic = record.title or record.filename or f"Source {request.source_id}"
        else:
            from ..services.registry import get_source_record, load_content_units
            record = get_source_record(request.source_id)
            if record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "SOURCE_NOT_FOUND", "message": f"Source {request.source_id} not found."},
                )
            owner = getattr(record, "user_id", None) or getattr(record, "owner_user_id", None) or getattr(record, "uploaded_by", None)
            if owner and owner not in (effective_user_id, "student_default", "default", "") and effective_user_id != "student_default" and effective_user_id != owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error_code": "ACCESS_DENIED_OR_ISOLATION_VIOLATION", "message": f"User {effective_user_id} is not authorized to access source {request.source_id}."},
                )
            units = load_content_units(request.source_id)
            source_observations = [u.text for u in units if u.text]
            if not request.topic:
                request.topic = record.title or record.filename or f"Source {request.source_id}"

    try:
        service = AIExplanationService()
        return await run_in_threadpool(service.explain, request, source_observations=source_observations)
    except PromptInjectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "PROMPT_INJECTION_DETECTED", "message": str(exc)},
        ) from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[learning] Error generating educational explanation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate explanation. Please try again.",
        ) from exc
