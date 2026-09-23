"""Step 5B Assessment Attempt Service.

Orchestrates validated assessment submissions:
1. Validates grounding and isolation (concept, source, session, user).
2. Performs server-side deterministic grading.
3. Enforces idempotency to prevent duplicate evaluations.
4. Executes atomic updates across attempt and mastery persistence boundaries.
"""

from __future__ import annotations

import copy
import logging
from typing import Any
from pydantic import BaseModel, Field

from .attempt_models import AssessmentAttempt, AssessmentType
from .attempt_repository import AssessmentAttemptRepository
from .models import DomainInvariantViolation, MasteryRecord
from .question_registry import QuestionRegistry
from .repository import MasteryRepository
from .state_machine import MasteryStateMachine

logger = logging.getLogger(__name__)


class AssessmentServiceError(Exception):
    """Base error for assessment attempt orchestration."""


class GroundingIntegrityError(AssessmentServiceError):
    """Raised when an attempt violates grounding or multi-tenant isolation constraints."""


class UnknownQuestionError(AssessmentServiceError):
    """Raised when question cannot be resolved in the authoritative registry."""


class AssessmentSubmissionRequest(BaseModel):
    """Payload for submitting an assessment attempt."""

    attempt_id: str
    user_id: str
    source_id: str
    session_id: str | None = None
    concept_id: str
    question_id: str
    selected_answer: int = Field(ge=0, le=10)
    assessment_type: AssessmentType = AssessmentType.DIAGNOSTIC


class AssessmentAttemptResult(BaseModel):
    """Result of processing an assessment attempt."""

    attempt: AssessmentAttempt
    mastery: MasteryRecord
    is_duplicate: bool = False


class AssessmentAttemptService:
    """Core service for grading attempts and updating concept mastery."""

    def __init__(
        self,
        attempt_repo: AssessmentAttemptRepository,
        mastery_repo: MasteryRepository,
        question_registry: QuestionRegistry,
        state_machine: MasteryStateMachine | None = None,
    ) -> None:
        self.attempt_repo = attempt_repo
        self.mastery_repo = mastery_repo
        self.question_registry = question_registry
        self.state_machine = state_machine or MasteryStateMachine()

    def submit_attempt(
        self,
        request: AssessmentSubmissionRequest,
    ) -> AssessmentAttemptResult:
        """Process, grade, and record an assessment attempt deterministically."""
        clean_attempt_id = request.attempt_id.strip()

        # 1. Idempotency Check: if attempt_id exists, return recorded result without side effects
        if self.attempt_repo.exists(clean_attempt_id):
            existing_attempt = self.attempt_repo.get(clean_attempt_id)
            existing_mastery = self.mastery_repo.get(
                request.user_id, request.source_id, request.concept_id
            )
            if existing_attempt is not None and existing_mastery is not None:
                logger.info(
                    "[attempt_service] Duplicate attempt_id=%s detected. Returning cached result.",
                    clean_attempt_id,
                )
                return AssessmentAttemptResult(
                    attempt=existing_attempt,
                    mastery=existing_mastery,
                    is_duplicate=True,
                )

        # 2. Resolve Authoritative Question
        question = self.question_registry.get(request.question_id)
        if question is None:
            raise UnknownQuestionError(
                f"Question '{request.question_id}' not found in authoritative question registry."
            )

        # 3. Enforce Grounding and Multi-Tenant Isolation
        if question.concept_id != request.concept_id.strip():
            raise GroundingIntegrityError(
                f"Question belongs to concept '{question.concept_id}', but submission specifies concept '{request.concept_id}'."
            )
        if question.source_id != request.source_id.strip():
            raise GroundingIntegrityError(
                f"Cross-source violation: question is bound to source '{question.source_id}', but submission specifies source '{request.source_id}'."
            )
        if question.user_id and question.user_id != request.user_id.strip():
            raise GroundingIntegrityError(
                f"Cross-user violation: question is bound to user '{question.user_id}', but submission is from user '{request.user_id}'."
            )
        if question.session_id and request.session_id and question.session_id != request.session_id.strip():
            raise GroundingIntegrityError(
                f"Cross-session violation: question is bound to session '{question.session_id}', but submission is from session '{request.session_id}'."
            )

        # 4. Server-Side Deterministic Grading (never trust client)
        is_correct = (request.selected_answer == question.correct_index)

        attempt = AssessmentAttempt(
            attempt_id=clean_attempt_id,
            user_id=request.user_id.strip(),
            source_id=request.source_id.strip(),
            session_id=request.session_id.strip() if request.session_id else None,
            concept_id=request.concept_id.strip(),
            question_id=request.question_id.strip(),
            assessment_type=request.assessment_type,
            selected_answer=request.selected_answer,
            correct_answer=question.correct_index,
            is_correct=is_correct,
        )

        # 5. Fetch or Initialize Mastery Record
        mastery = self.mastery_repo.get(
            request.user_id.strip(),
            request.source_id.strip(),
            request.concept_id.strip(),
        )
        if mastery is None:
            mastery = self.state_machine.create_initial_record(
                user_id=request.user_id.strip(),
                source_id=request.source_id.strip(),
                concept_id=request.concept_id.strip(),
                session_id=request.session_id.strip() if request.session_id else None,
            )

        # 6. Apply State Machine Update
        mastery_backup = copy.deepcopy(mastery)
        updated_mastery = self.state_machine.record_assessment_attempt(
            record=mastery,
            attempt_id=clean_attempt_id,
            is_correct=is_correct,
            session_id=request.session_id.strip() if request.session_id else None,
            assessment_type=request.assessment_type,
        )

        # 7. Atomic Persistence
        try:
            saved_attempt = self.attempt_repo.save(attempt)
            try:
                saved_mastery = self.mastery_repo.save(updated_mastery)
            except Exception as mastery_err:
                # Rollback attempt to maintain transactional consistency
                if hasattr(self.attempt_repo, "_attempts") and clean_attempt_id in self.attempt_repo._attempts:
                    del self.attempt_repo._attempts[clean_attempt_id]
                raise AssessmentServiceError(
                    f"Mastery persistence failed; rolled back attempt. Error: {mastery_err}"
                ) from mastery_err
        except Exception as err:
            if not isinstance(err, AssessmentServiceError):
                raise AssessmentServiceError(f"Persistence operation failed: {err}") from err
            raise

        return AssessmentAttemptResult(
            attempt=saved_attempt,
            mastery=saved_mastery,
            is_duplicate=False,
        )
