"""Step 5E Adaptive Learning Application Service.

Orchestrates the verified Step 5 domain services:
- MasteryRepository & State Machine
- AssessmentAttemptService & QuestionRegistry
- ReassessmentService
- PersonalizationService
- RemediationOrchestrator

Translates between API DTOs and domain entities without leaking answer keys,
bypassing state validation, or exposing internal filesystem paths.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from pathlib import Path

from ..assessment.schemas import SafeOption
from ..registry import get_source_record, load_knowledge_graph
from ..schemas import KnowledgeGraph
from .api_schemas import (
    AssessmentSubmissionRequestDTO,
    AssessmentSubmissionResponseDTO,
    ConceptMasterySummary,
    LearningStateResponse,
    NextActionResponse,
    RemediationStartResponseDTO,
    RemediationStatusResponseDTO,
    RoadmapResponse,
    SafeReassessmentQuestionResponse,
)
from .attempt_models import AssessmentType
from .attempt_repository import AssessmentAttemptRepository, InMemoryAssessmentAttemptRepository
from .attempt_service import (
    AssessmentAttemptService,
    AssessmentServiceError,
    AssessmentSubmissionRequest,
    GroundingIntegrityError,
    UnknownQuestionError,
)
from .dependency_provider import ConceptDependencyProvider
from .models import DomainInvariantViolation, MasteryRecord, MasteryState
from .personalization_service import PersonalizationService
from .question_registry import AuthoritativeQuestion, InMemoryQuestionRegistry, QuestionRegistry
from .reassessment_queue import ReassessmentQueue, ReassessmentSession
from .reassessment_service import ReassessmentService
from .misconception_models import (
    MisconceptionEvidence,
    MisconceptionStatus,
)
from .misconception_repository import (
    InMemoryMisconceptionRepository,
    MisconceptionRepository,
)
from .strategy_selector import TeachingStrategySelector
from .remediation_models import RemediationJob, RemediationJobStatus
from .remediation_orchestrator import RemediationOrchestrator
from .remediation_repository import InMemoryRemediationJobRepository, RemediationJobRepository
from .repository import InMemoryMasteryRepository, MasteryRepository
from .roadmap_models import LearningActionType, NextLearningAction, ReasonCode
from .state_machine import InvalidStateTransitionError, MasteryStateMachine

logger = logging.getLogger(__name__)


class SourceNotFoundError(Exception):
    """Raised when a requested source does not exist in registry."""


class SourceAccessDeniedError(Exception):
    """Raised when the requesting user is not authorized to access the source."""


class ConceptNotEligibleForRemediationError(Exception):
    """Raised when a remediation request targets a concept not permitted by current next action."""


class RemediationJobNotFoundError(Exception):
    """Raised when a requested remediation job cannot be found."""


class AdaptiveLearningService:
    """Core application service orchestrating adaptive learning workflows."""

    def __init__(
        self,
        mastery_repo: MasteryRepository | None = None,
        attempt_repo: AssessmentAttemptRepository | None = None,
        question_registry: QuestionRegistry | None = None,
        remediation_repo: RemediationJobRepository | None = None,
        state_machine: MasteryStateMachine | None = None,
        video_engine_fn: Any | None = None,
        misconception_repo: MisconceptionRepository | None = None,
        strategy_selector: TeachingStrategySelector | None = None,
        reassessment_queue: ReassessmentQueue | None = None,
    ) -> None:
        self.mastery_repo = mastery_repo or InMemoryMasteryRepository()
        self.attempt_repo = attempt_repo or InMemoryAssessmentAttemptRepository()
        self.question_registry = question_registry or InMemoryQuestionRegistry()
        self.remediation_repo = remediation_repo or InMemoryRemediationJobRepository()
        self.state_machine = state_machine or MasteryStateMachine()
        self.misconception_repo = misconception_repo or InMemoryMisconceptionRepository()
        self.strategy_selector = strategy_selector or TeachingStrategySelector()
        self.reassessment_queue = reassessment_queue or ReassessmentQueue()

        self.attempt_service = AssessmentAttemptService(
            attempt_repo=self.attempt_repo,
            mastery_repo=self.mastery_repo,
            question_registry=self.question_registry,
            state_machine=self.state_machine,
            misconception_repo=self.misconception_repo,
        )

        self.reassessment_service = ReassessmentService(
            mastery_repo=self.mastery_repo,
            question_registry=self.question_registry,
            misconception_repo=self.misconception_repo,
        )

        self.personalization_service = PersonalizationService(
            mastery_repo=self.mastery_repo,
        )

        self.remediation_orchestrator = RemediationOrchestrator(
            mastery_repo=self.mastery_repo,
            remediation_repo=self.remediation_repo,
            attempt_repo=self.attempt_repo,
            question_registry=self.question_registry,
            state_machine=self.state_machine,
            video_engine_fn=video_engine_fn,
            misconception_repo=self.misconception_repo,
            strategy_selector=self.strategy_selector,
        )

    # -------------------------------------------------------------------------
    # Source Verification & Grounding
    # -------------------------------------------------------------------------
    def _verify_source_access(self, user_id: str, source_id: str) -> KnowledgeGraph:
        """Verify source exists in registry and user is authorized under current dev semantics."""
        clean_user = user_id.strip() if user_id else ""
        clean_source = source_id.strip() if source_id else ""

        if not clean_source:
            raise DomainInvariantViolation("source_id cannot be empty.")
        if not clean_user:
            raise DomainInvariantViolation("user_id cannot be empty.")

        # Check source registry
        record = get_source_record(clean_source)
        if record is None:
            raise SourceNotFoundError(f"Source '{clean_source}' was not found in registry.")

        # Source ownership / access check:
        # In current development semantics, user is permitted if record has no user, or matches user,
        # or matches 'student_default', or matches owner_user_id.
        owner = getattr(record, "user_id", None) or getattr(record, "owner_user_id", None) or getattr(record, "uploaded_by", None)
        if owner and owner not in (clean_user, "student_default", "default", ""):
            # If explicit non-matching owner, disallow
            if clean_user != "student_default" and clean_user != owner:
                raise SourceAccessDeniedError(f"User '{clean_user}' is not authorized to access source '{clean_source}'.")

        kg = load_knowledge_graph(clean_source)
        if kg is None or not kg.concepts:
            raise SourceNotFoundError(f"Knowledge graph for source '{clean_source}' is missing or empty.")

        return kg

    def _to_next_action_dto(self, action: NextLearningAction) -> NextActionResponse:
        """Convert domain NextLearningAction to API DTO with rehydration metadata."""
        meta = dict(action.metadata or {})
        if action.concept_id:
            if hasattr(self.remediation_repo, "find_active_for_concept"):
                active_job = self.remediation_repo.find_active_for_concept(
                    action.user_id, action.source_id, action.concept_id
                )
                if active_job:
                    meta["active_remediation_job_id"] = active_job.remediation_job_id
                    meta["active_remediation_status"] = active_job.status.value

            if hasattr(self.remediation_repo, "list_for_concept"):
                jobs = self.remediation_repo.list_for_concept(action.user_id, action.source_id, action.concept_id)
                ready_jobs = [j for j in jobs if j.status == RemediationJobStatus.READY]
                if ready_jobs:
                    latest_ready = ready_jobs[-1]
                    vid_id = latest_ready.video_job_id or latest_ready.remediation_job_id
                    meta["stream_url"] = self._build_safe_stream_url(vid_id)
                    meta["video_ready"] = True
                    meta["video_job_id"] = latest_ready.remediation_job_id
                    if action.action_type == LearningActionType.REMEDIATE:
                        action.action_type = LearningActionType.REASSESS
                        action.reason_code = ReasonCode.REASSESSMENT_PENDING
                        if hasattr(self, "mastery_repo"):
                            rec = self.mastery_repo.get(action.user_id, action.source_id, action.concept_id)
                            if rec and rec.mastery_state in (MasteryState.REMEDIATING, MasteryState.WEAK):
                                rec.mastery_state = MasteryState.REASSESSING
                                rec.touch()
                                self.mastery_repo.save(rec)

            if action.action_type == LearningActionType.REASSESS:
                user_attempts = self.attempt_repo.list_for_concept(action.user_id, action.source_id, action.concept_id)
                reassess_attempts = [
                    att for att in user_attempts
                    if getattr(att, "assessment_type", None) in (AssessmentType.REASSESSMENT, "REASSESSMENT")
                ]
                meta["reassessment_attempts_count"] = len(reassess_attempts)

                pending_q = None
                if hasattr(self.question_registry, "get_pending_for_concept"):
                    pending_q = self.question_registry.get_pending_for_concept(action.user_id, action.source_id, action.concept_id)
                if pending_q:
                    attempted_qids = {att.question_id for att in user_attempts}
                    if pending_q.question_id not in attempted_qids:
                        meta["pending_question"] = {
                            "question_id": pending_q.question_id,
                            "concept_id": pending_q.concept_id,
                            "stem": pending_q.stem,
                            "options": [opt.model_dump() if hasattr(opt, "model_dump") else opt for opt in pending_q.get_safe_options()],
                            "difficulty": pending_q.difficulty,
                        }

        # M7 Explainable history for NextAction
        why_chosen = None
        active_label = None
        if action.concept_id and self.misconception_repo:
            misc_list = self.misconception_repo.list_for_concept(action.user_id, action.source_id, action.concept_id)
            act_m = next((m for m in misc_list if m.status in (MisconceptionStatus.ACTIVE, MisconceptionStatus.RECURRENT)), None)
            corr_m = next((m for m in misc_list if m.status == MisconceptionStatus.CORRECTED), None)
            if act_m:
                active_label = act_m.misconception_label
                jobs = self.remediation_repo.list_for_concept(action.user_id, action.source_id, action.concept_id)
                st_used = (jobs[0].strategy_used or jobs[0].metadata.get("strategy_used")) if jobs else "Targeted review"
                status_label = "Under review" if act_m.status == MisconceptionStatus.ACTIVE else "Recurrent"
                why_chosen = {
                    "detected_learning_gap": act_m.misconception_label,
                    "evidence": f"{act_m.evidence_count} assessment attempt{'s' if act_m.evidence_count > 1 else ''}",
                    "teaching_approach": st_used,
                    "status": status_label,
                }
            elif corr_m:
                active_label = corr_m.misconception_label
                jobs = self.remediation_repo.list_for_concept(action.user_id, action.source_id, action.concept_id)
                st_used = (jobs[0].strategy_used or jobs[0].metadata.get("strategy_used")) if jobs else "Targeted review"
                why_chosen = {
                    "detected_learning_gap": corr_m.misconception_label,
                    "evidence": f"{corr_m.evidence_count} assessment attempt{'s' if corr_m.evidence_count > 1 else ''}",
                    "teaching_approach": st_used,
                    "status": "Corrected",
                }

        return NextActionResponse(
            user_id=action.user_id,
            source_id=action.source_id,
            session_id=action.session_id,
            concept_id=action.concept_id,
            action_type=action.action_type,
            reason_code=action.reason_code,
            priority=action.priority,
            mastery_state=action.mastery_state,
            mastery_score=action.mastery_score,
            lifetime_accuracy=action.lifetime_accuracy,
            dependency_status=action.dependency_status,
            metadata=meta,
            why_chosen=why_chosen,
            active_misconception_label=active_label,
        )

    # -------------------------------------------------------------------------
    # 1. Learning State & Roadmap (Pure Reads)
    # -------------------------------------------------------------------------
    def get_roadmap(
        self,
        user_id: str,
        source_id: str,
        session_id: str | None = None,
    ) -> RoadmapResponse:
        """Pure read: returns full deterministic roadmap without mutations or LLM calls."""
        kg = self._verify_source_access(user_id=user_id, source_id=source_id)
        roadmap = self.personalization_service.get_roadmap(
            user_id=user_id.strip(),
            source_id=source_id.strip(),
            session_id=session_id.strip() if session_id else None,
            knowledge_graph=kg,
        )

        clean_user = user_id.strip()
        clean_source = source_id.strip()
        records = self.mastery_repo.list_by_user_source(clean_user, clean_source)
        rec_map = {r.concept_id: r for r in records}

        concept_summaries: list[ConceptMasterySummary] = []
        misconception_journey: list[dict[str, Any]] = []

        for cid in kg.concepts.keys():
            rec = rec_map.get(cid)
            m_state = rec.mastery_state if rec else MasteryState.UNASSESSED
            m_score = rec.mastery_score if rec else 0.0
            l_acc = rec.lifetime_accuracy if rec else 0.0
            att_cnt = rec.attempt_count if rec else 0
            reass_cnt = rec.reassessment_attempt_count if rec else 0
            rem_cnt = rec.remediation_attempt_count if rec else 0
            last_ass = rec.last_assessed_at if rec else None
            last_rem = rec.last_remediation_at if rec else None

            # Misconceptions for this concept
            misc_list = self.misconception_repo.list_for_concept(clean_user, clean_source, cid)
            act_m = next((m for m in misc_list if m.status in (MisconceptionStatus.ACTIVE, MisconceptionStatus.RECURRENT)), None)
            corr_m = next((m for m in misc_list if m.status == MisconceptionStatus.CORRECTED), None)
            m_target = act_m or corr_m

            # Jobs for strategy
            c_jobs = self.remediation_repo.list_for_concept(clean_user, clean_source, cid)
            st_used = (c_jobs[0].strategy_used or c_jobs[0].metadata.get("strategy_used")) if c_jobs else None

            # Reassessment result
            reass_res = None
            if reass_cnt > 0:
                c_atts = self.attempt_repo.list_for_concept(clean_user, clean_source, cid)
                reass_atts = [a for a in c_atts if getattr(a, "assessment_type", None) in (AssessmentType.REASSESSMENT, "REASSESSMENT")]
                if reass_atts:
                    latest_reass = max(reass_atts, key=lambda a: a.submitted_at or a.created_at)
                    reass_res = "PASSED" if latest_reass.is_correct else "FAILED"

            why_c = None
            if act_m:
                st_display = st_used or "Targeted review"
                status_display = "Under review" if act_m.status == MisconceptionStatus.ACTIVE else "Recurrent"
                why_c = (
                    f"Detected learning gap: {act_m.misconception_label}. "
                    f"Evidence: {act_m.occurrence_count} assessment attempt{'s' if act_m.occurrence_count > 1 else ''}. "
                    f"Teaching approach: {st_display}. "
                    f"Status: {status_display}."
                )
            elif corr_m:
                why_c = (
                    f"Detected learning gap: {corr_m.misconception_label}. "
                    f"Evidence: {corr_m.occurrence_count} assessment attempts. "
                    f"Status: Corrected."
                )

            summary = ConceptMasterySummary(
                concept_id=cid,
                mastery_state=m_state,
                mastery_score=m_score,
                lifetime_accuracy=l_acc,
                attempt_count=att_cnt,
                reassessment_attempt_count=reass_cnt,
                remediation_attempt_count=rem_cnt,
                last_assessed_at=last_ass,
                last_remediation_at=last_rem,
                initial_state=MasteryState.WEAK if att_cnt > 0 and (act_m or corr_m) else (MasteryState.UNASSESSED if att_cnt == 0 else m_state),
                current_state=m_state,
                active_misconception_label=m_target.misconception_label if m_target else None,
                misconception_confidence=m_target.confidence_state.value if m_target else None,
                strategy_used=st_used,
                reassessment_result=reass_res,
                misconception_status=m_target.status.value if m_target else None,
                why_chosen=why_c,
            )
            concept_summaries.append(summary)

            if m_target:
                misconception_journey.append({
                    "concept_id": cid,
                    "initial_state": summary.initial_state.value if summary.initial_state else None,
                    "current_state": summary.current_state.value if summary.current_state else None,
                    "active_misconception_label": m_target.misconception_label,
                    "misconception_confidence": m_target.confidence_state.value,
                    "strategy_used": st_used,
                    "reassessment_result": reass_res,
                    "misconception_status": m_target.status.value,
                    "why_chosen": why_c,
                })

        return RoadmapResponse(
            user_id=roadmap.user_id,
            source_id=roadmap.source_id,
            session_id=roadmap.session_id,
            mastered_concepts=roadmap.mastered_concepts,
            current_concept=roadmap.current_concept,
            weak_concepts=roadmap.weak_concepts,
            remediating_concepts=roadmap.remediating_concepts,
            reassessing_concepts=roadmap.reassessing_concepts,
            unassessed_concepts=roadmap.unassessed_concepts,
            blocked_concepts=roadmap.blocked_concepts,
            needs_support_concepts=roadmap.needs_support_concepts,
            completed=roadmap.completed,
            next_action=self._to_next_action_dto(roadmap.next_action),
            concept_summaries=concept_summaries,
            misconception_journey=misconception_journey,
        )

    def get_next_action(
        self,
        user_id: str,
        source_id: str,
        session_id: str | None = None,
    ) -> NextActionResponse:
        """Pure read: returns deterministic next learning action."""
        kg = self._verify_source_access(user_id=user_id, source_id=source_id)
        action = self.personalization_service.get_next_action(
            user_id=user_id.strip(),
            source_id=source_id.strip(),
            session_id=session_id.strip() if session_id else None,
            knowledge_graph=kg,
        )
        return self._to_next_action_dto(action)

    get_next_learning_action = get_next_action

    def get_learning_state(
        self,
        user_id: str,
        source_id: str,
        session_id: str | None = None,
    ) -> LearningStateResponse:
        """Structured snapshot of all concept states, scores, and overall progress."""
        kg = self._verify_source_access(user_id=user_id, source_id=source_id)
        clean_user = user_id.strip()
        clean_source = source_id.strip()
        clean_session = session_id.strip() if session_id else None

        records = self.mastery_repo.list_by_user_source(clean_user, clean_source)
        rec_map = {r.concept_id: r for r in records}

        concept_summaries: list[ConceptMasterySummary] = []
        mastered_count = 0
        weak_count = 0

        for cid in kg.concepts.keys():
            if cid in rec_map:
                r = rec_map[cid]
                if r.mastery_state == MasteryState.MASTERED:
                    mastered_count += 1
                elif r.mastery_state in (MasteryState.WEAK, MasteryState.REMEDIATING, MasteryState.NEEDS_SUPPORT):
                    weak_count += 1

                misc_list = self.misconception_repo.list_for_concept(clean_user, clean_source, cid)
                act_m = next((m for m in misc_list if m.status in (MisconceptionStatus.ACTIVE, MisconceptionStatus.RECURRENT)), None)
                corr_m = next((m for m in misc_list if m.status == MisconceptionStatus.CORRECTED), None)
                m_target = act_m or corr_m
                c_jobs = self.remediation_repo.list_for_concept(clean_user, clean_source, cid)
                st_used = (c_jobs[0].strategy_used or c_jobs[0].metadata.get("strategy_used")) if c_jobs else None

                concept_summaries.append(
                    ConceptMasterySummary(
                        concept_id=cid,
                        mastery_state=r.mastery_state,
                        mastery_score=r.mastery_score,
                        lifetime_accuracy=r.lifetime_accuracy,
                        attempt_count=r.attempt_count,
                        reassessment_attempt_count=r.reassessment_attempt_count,
                        remediation_attempt_count=r.remediation_attempt_count,
                        last_assessed_at=r.last_assessed_at,
                        last_remediation_at=r.last_remediation_at,
                        initial_state=MasteryState.WEAK if r.attempt_count > 0 and (act_m or corr_m) else r.mastery_state,
                        current_state=r.mastery_state,
                        active_misconception_label=m_target.misconception_label if m_target else None,
                        misconception_confidence=m_target.confidence_state.value if m_target else None,
                        strategy_used=st_used,
                        misconception_status=m_target.status.value if m_target else None,
                    )
                )
            else:
                concept_summaries.append(
                    ConceptMasterySummary(
                        concept_id=cid,
                        mastery_state=MasteryState.UNASSESSED,
                        mastery_score=0.0,
                        lifetime_accuracy=0.0,
                        attempt_count=0,
                        reassessment_attempt_count=0,
                        remediation_attempt_count=0,
                        initial_state=MasteryState.UNASSESSED,
                        current_state=MasteryState.UNASSESSED,
                    )
                )

        total = len(kg.concepts)
        progress = round((mastered_count / total * 100.0), 2) if total > 0 else 0.0

        roadmap = self.personalization_service.get_roadmap(
            user_id=clean_user,
            source_id=clean_source,
            session_id=clean_session,
            knowledge_graph=kg,
        )

        return LearningStateResponse(
            user_id=clean_user,
            source_id=clean_source,
            session_id=clean_session,
            total_concepts=total,
            mastered_count=mastered_count,
            weak_count=weak_count,
            progress_percentage=progress,
            concepts=concept_summaries,
            next_action=self._to_next_action_dto(roadmap.next_action),
            completed=roadmap.completed,
        )

    # -------------------------------------------------------------------------
    # 2. Authoritative Assessment Submission
    # -------------------------------------------------------------------------
    def submit_assessment(
        self,
        user_id: str,
        source_id: str,
        submission: AssessmentSubmissionRequestDTO,
    ) -> AssessmentSubmissionResponseDTO:
        """Submit assessment attempt for server-side grading and mastery update."""
        kg = self._verify_source_access(user_id=user_id, source_id=source_id)

        clean_user = user_id.strip()
        clean_source = source_id.strip()
        clean_concept = submission.concept_id.strip()
        clean_qid = submission.question_id.strip()

        # Enforce concept exists in grounded curriculum
        if clean_concept not in kg.concepts:
            raise GroundingIntegrityError(
                f"Concept '{clean_concept}' does not exist in grounded curriculum for source '{source_id}'."
            )

        # Check if question is stale or invalidated in reassessment queue
        if self.reassessment_queue.is_stale_or_invalidated(clean_user, clean_source, clean_concept, clean_qid):
            raise AssessmentServiceError(
                f"Question '{clean_qid}' is stale or from an invalidated cycle and cannot be submitted."
            )

        req = AssessmentSubmissionRequest(
            attempt_id=submission.attempt_id.strip(),
            user_id=clean_user,
            source_id=clean_source,
            session_id=submission.session_id.strip() if submission.session_id else None,
            concept_id=clean_concept,
            question_id=clean_qid,
            selected_answer=submission.selected_answer,
            assessment_type=submission.assessment_type,
        )

        result = self.attempt_service.submit_attempt(req)

        # Retrieve authoritative question for explanation
        authoritative_q = self.question_registry.get(clean_qid)
        explanation_text = getattr(authoritative_q, "explanation", None) if authoritative_q else None

        # Resolve next action after attempt mutation
        next_action = self.personalization_service.get_next_action(
            user_id=clean_user,
            source_id=clean_source,
            session_id=submission.session_id.strip() if submission.session_id else None,
            knowledge_graph=kg,
        )

        # Advance or invalidate reassessment queue based on outcome and state
        m = result.mastery
        if m.mastery_state != MasteryState.REASSESSING:
            # Concept has left REASSESSING (e.g. MASTERED or returned to WEAK/NEEDS_SUPPORT)
            self.reassessment_queue.invalidate_concept(clean_user, clean_source, clean_concept)
        else:
            # Still reassessing: advance queue to next question
            self.reassessment_queue.advance(clean_user, clean_source, clean_concept, clean_qid)

        return AssessmentSubmissionResponseDTO(
            attempt_id=result.attempt.attempt_id,
            user_id=result.attempt.user_id,
            source_id=result.attempt.source_id,
            concept_id=result.attempt.concept_id,
            question_id=result.attempt.question_id,
            selected_answer=result.attempt.selected_answer,
            is_correct=result.attempt.is_correct,
            is_duplicate=result.is_duplicate,
            mastery_state=m.mastery_state,
            mastery_score=m.mastery_score,
            lifetime_accuracy=m.lifetime_accuracy,
            attempt_count=m.attempt_count,
            reassessment_attempt_count=m.reassessment_attempt_count,
            remediation_attempt_count=m.remediation_attempt_count,
            next_action=self._to_next_action_dto(next_action),
            explanation=explanation_text,
        )

    # -------------------------------------------------------------------------
    # 3. Grounded Reassessment Generation
    # -------------------------------------------------------------------------
    def generate_reassessment(
        self,
        user_id: str,
        source_id: str,
        concept_id: str | None = None,
        session_id: str | None = None,
        previous_question_id: str | None = None,
    ) -> SafeReassessmentQuestionResponse:
        """Generate or serve a novel grounded reassessment question for a concept in REASSESSING state.

        Idempotency / Queue Flow:
        If there is an active queued reassessment session for this (user, source, concept),
        serve the current unanswered question.
        Otherwise, generate a batch via ReassessmentService, enqueue it, and serve question 1.
        """
        kg = self._verify_source_access(user_id=user_id, source_id=source_id)
        clean_user = user_id.strip()
        clean_source = source_id.strip()
        clean_session = session_id.strip() if session_id else None

        # If concept_id not provided, resolve from current NextLearningAction
        target_concept = concept_id.strip() if concept_id else None
        if not target_concept:
            action = self.personalization_service.get_next_action(
                user_id=clean_user,
                source_id=clean_source,
                session_id=clean_session,
                knowledge_graph=kg,
            )
            if action.action_type != LearningActionType.REASSESS or not action.concept_id:
                raise AssessmentServiceError(
                    f"Current next action is '{action.action_type.value}' ({action.reason_code.value}), "
                    "not REASSESS. Concept must be in REASSESSING state."
                )
            target_concept = action.concept_id

        if target_concept not in kg.concepts:
            raise GroundingIntegrityError(f"Concept '{target_concept}' not found in source knowledge graph.")

        # State precondition check: concept must be REASSESSING
        m = self.mastery_repo.get(clean_user, clean_source, target_concept)
        if m is None or m.mastery_state != MasteryState.REASSESSING:
            current_st = m.mastery_state.value if m else "UNASSESSED"
            raise AssessmentServiceError(
                f"Cannot generate reassessment for concept '{target_concept}' in state {current_st}. "
                "Concept must be in REASSESSING state (remediation video must be completed and confirmed)."
            )

        user_attempts = self.attempt_repo.list_for_concept(clean_user, clean_source, target_concept)
        attempted_qids = {att.question_id for att in user_attempts}
        resolved_prev_qid = previous_question_id.strip() if previous_question_id else None
        if not resolved_prev_qid and user_attempts:
            resolved_prev_qid = user_attempts[-1].question_id

        # 1. Check server-side ReassessmentQueue session first
        sess = self.reassessment_queue.get_session(clean_user, clean_source, target_concept)
        if sess and not sess.is_invalidated:
            curr_q = sess.get_current_question()
            if curr_q and curr_q.question_id not in attempted_qids:
                q_idx = sess.current_index + 1
                q_tot = max(len(sess.questions), 2)
                if hasattr(curr_q, "get_safe_options"):
                    sess_opts = curr_q.get_safe_options()
                else:
                    sess_opts = [
                        SafeOption(index=getattr(opt, "index", idx), text=getattr(opt, "text", str(opt)))
                        for idx, opt in enumerate(curr_q.options)
                    ]
                return SafeReassessmentQuestionResponse(
                    question_id=curr_q.question_id,
                    concept_id=curr_q.concept_id,
                    source_id=curr_q.source_id,
                    stem=curr_q.stem,
                    options=sess_opts,
                    difficulty=curr_q.difficulty or "intermediate",
                    variant_type=getattr(curr_q, "variant_type", "application"),
                    question_number=q_idx,
                    total_questions=q_tot,
                )

        # 2. Check standalone pending question in question_registry
        pending_q: AuthoritativeQuestion | None = None
        if hasattr(self.question_registry, "get_pending_for_concept"):
            candidate = self.question_registry.get_pending_for_concept(clean_user, clean_source, target_concept)
            if candidate and candidate.question_id not in attempted_qids:
                pending_q = candidate

        if pending_q is not None:
            return SafeReassessmentQuestionResponse(
                question_id=pending_q.question_id,
                concept_id=pending_q.concept_id,
                source_id=pending_q.source_id,
                stem=pending_q.stem,
                options=pending_q.get_safe_options(),
                difficulty=pending_q.difficulty or "intermediate",
                variant_type=getattr(pending_q, "variant_type", "application"),
                question_number=1,
                total_questions=2,
            )

        # 3. Generate batch of reassessment questions (default target 2 for 2-attempt mastery rule)
        cycle_idx = getattr(m, "remediation_attempt_count", 0) + 1
        batch = self.reassessment_service.generate_reassessment_batch(
            user_id=clean_user,
            source_id=clean_source,
            concept_id=target_concept,
            session_id=clean_session,
            previous_question_id=resolved_prev_qid,
            provided_concept=kg.concepts[target_concept],
            count=2,
        )

        # Register batch into session queue
        new_sess = self.reassessment_queue.register_batch(
            user_id=clean_user,
            source_id=clean_source,
            concept_id=target_concept,
            cycle=cycle_idx,
            questions=batch,
        )

        first_q = new_sess.get_current_question() or batch[0]
        if hasattr(first_q, "get_safe_options"):
            safe_opts = first_q.get_safe_options()
        else:
            safe_opts = [
                SafeOption(index=getattr(opt, "index", idx), text=getattr(opt, "text", str(opt)))
                for idx, opt in enumerate(first_q.options)
            ]

        return SafeReassessmentQuestionResponse(
            question_id=first_q.question_id,
            concept_id=first_q.concept_id,
            source_id=first_q.source_id,
            stem=first_q.stem,
            options=safe_opts,
            difficulty=first_q.difficulty or "intermediate",
            variant_type=getattr(first_q, "variant_type", "application"),
            question_number=1,
            total_questions=len(batch),
        )

    def prefetch_reassessment(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        session_id: str | None = None,
    ) -> None:
        """Trigger background prefetching of the reassessment question batch."""
        clean_user = user_id.strip()
        clean_source = source_id.strip()
        clean_concept = concept_id.strip()

        # If already cached or prefetching in progress, exit early
        existing_sess = self.reassessment_queue.get_session(clean_user, clean_source, clean_concept)
        if existing_sess and not existing_sess.is_invalidated and existing_sess.get_current_question():
            return

        import threading

        def _bg_prefetch() -> None:
            try:
                self.generate_reassessment(
                    user_id=clean_user,
                    source_id=clean_source,
                    concept_id=clean_concept,
                    session_id=session_id,
                )
                logger.info(
                    "[application_service] Prefetched reassessment batch for (%s, %s, %s)",
                    clean_user, clean_source, clean_concept
                )
            except Exception as exc:
                logger.warning(
                    "[application_service] Background prefetch failed for (%s, %s, %s): %s",
                    clean_user, clean_source, clean_concept, exc
                )

        t = threading.Thread(target=_bg_prefetch, daemon=True, name=f"prefetch-{clean_concept}")
        t.start()

    # -------------------------------------------------------------------------
    # 4. Remediation Orchestration (Async & Non-Blocking)
    # -------------------------------------------------------------------------
    async def start_remediation(
        self,
        user_id: str,
        source_id: str,
        concept_id: str | None = None,
        session_id: str | None = None,
        force: bool = False,
    ) -> RemediationStartResponseDTO:
        """Initiate or reuse a targeted video remediation job.

        Server-verifies that concept is eligible for remediation.
        Dispatches video generation in background if not already ready.
        Returns immediate HTTP 202 Accepted semantics with safe stream identifier.
        """
        kg = self._verify_source_access(user_id=user_id, source_id=source_id)
        clean_user = user_id.strip()
        clean_source = source_id.strip()
        clean_session = session_id.strip() if session_id else None

        # 1. Resolve & verify target concept against current next action
        action = self.personalization_service.get_next_action(
            user_id=clean_user,
            source_id=clean_source,
            session_id=clean_session,
            knowledge_graph=kg,
        )

        target_concept = concept_id.strip() if concept_id else action.concept_id

        if not target_concept or target_concept not in kg.concepts:
            raise ConceptNotEligibleForRemediationError(
                f"Concept '{target_concept}' is not recognized in curriculum."
            )

        # Check eligibility: concept must be WEAK or REMEDIATING
        m = self.mastery_repo.get(clean_user, clean_source, target_concept)
        if m is None:
            raise ConceptNotEligibleForRemediationError(
                f"No mastery record found for concept '{target_concept}'. Learner must be assessed first."
            )

        if m.mastery_state == MasteryState.MASTERED:
            raise InvalidStateTransitionError(
                f"Concept '{target_concept}' is already MASTERED. Remediation is not permitted."
            )
        if m.mastery_state == MasteryState.NEEDS_SUPPORT:
            raise InvalidStateTransitionError(
                f"Concept '{target_concept}' is in NEEDS_SUPPORT state. Manual instructor intervention required."
            )
        if m.mastery_state not in (MasteryState.WEAK, MasteryState.REMEDIATING, MasteryState.REASSESSING):
            raise InvalidStateTransitionError(
                f"Concept '{target_concept}' is in state {m.mastery_state.value}. "
                "Remediation is only permitted for WEAK or REMEDIATING concepts."
            )

        # 2. Check for completed READY job or active job
        attempt_num = m.remediation_attempt_count + 1 if m.mastery_state == MasteryState.WEAK else max(1, m.remediation_attempt_count)

        ready_job = self.remediation_repo.find_ready_for_attempt(
            user_id=clean_user,
            source_id=clean_source,
            concept_id=target_concept,
            attempt_number=attempt_num,
        )
        if ready_job and not force:
            stream_url = self._build_safe_stream_url(ready_job.video_job_id or ready_job.remediation_job_id)
            return RemediationStartResponseDTO(
                remediation_job_id=ready_job.remediation_job_id,
                user_id=ready_job.user_id,
                source_id=ready_job.source_id,
                concept_id=ready_job.concept_id,
                attempt_number=ready_job.attempt_number,
                status=ready_job.status,
                stream_url=stream_url,
                message="Completed remedial video ready for playback.",
            )

        active_job = self.remediation_repo.find_active_for_concept(
            user_id=clean_user,
            source_id=clean_source,
            concept_id=target_concept,
            attempt_number=attempt_num,
        )
        if active_job and not force:
            return RemediationStartResponseDTO(
                remediation_job_id=active_job.remediation_job_id,
                user_id=active_job.user_id,
                source_id=active_job.source_id,
                concept_id=active_job.concept_id,
                attempt_number=active_job.attempt_number,
                status=active_job.status,
                stream_url=None,
                message="Remediation video generation is actively running in background.",
            )

        # 3. Launch remediation in background task via orchestrator (non-blocking)
        # Note: wait_for_completion=False so HTTP call returns immediately with job ID
        job = await self.remediation_orchestrator.execute_remediation(
            user_id=clean_user,
            source_id=clean_source,
            concept_id=target_concept,
            session_id=clean_session,
            force=force,
            wait_for_completion=False,
            run_in_background=True,
        )

        stream_url = (
            self._build_safe_stream_url(job.video_job_id or job.remediation_job_id)
            if job.status == RemediationJobStatus.READY
            else None
        )

        msg = (
            "Remedial video generation completed."
            if job.status == RemediationJobStatus.READY
            else "Remedial video generation started in background."
        )

        return RemediationStartResponseDTO(
            remediation_job_id=job.remediation_job_id,
            user_id=job.user_id,
            source_id=job.source_id,
            concept_id=job.concept_id,
            attempt_number=job.attempt_number,
            status=job.status,
            stream_url=stream_url,
            message=msg,
        )

    def get_remediation_status(
        self,
        user_id: str,
        source_id: str,
        job_id: str,
    ) -> RemediationStatusResponseDTO:
        """Poll remediation job status with strict tenant isolation and safe stream URLs."""
        clean_user = user_id.strip()
        clean_source = source_id.strip()
        clean_job = job_id.strip()

        job = self.remediation_repo.get(clean_job)
        if job is None:
            raise RemediationJobNotFoundError(f"Remediation job '{clean_job}' not found.")

        # Multi-tenant and source isolation check
        if job.source_id != clean_source:
            raise SourceAccessDeniedError(f"Job '{clean_job}' belongs to a different source.")
        if job.user_id != clean_user:
            raise SourceAccessDeniedError(f"Job '{clean_job}' belongs to a different user.")

        stream_url = (
            self._build_safe_stream_url(job.video_job_id or job.remediation_job_id)
            if job.status == RemediationJobStatus.READY
            else None
        )

        return RemediationStatusResponseDTO(
            remediation_job_id=job.remediation_job_id,
            user_id=job.user_id,
            source_id=job.source_id,
            concept_id=job.concept_id,
            attempt_number=job.attempt_number,
            status=job.status,
            duration_seconds=job.duration_seconds,
            stream_url=stream_url,
            is_infrastructure_failure=job.is_infrastructure_failure,
            failure_code=job.failure_code,
            failure_message=job.failure_message,
        )

    def _build_safe_stream_url(self, video_job_id: str) -> str:
        """Build client-safe streaming route path without exposing filesystem paths."""
        return f"/video/{video_job_id}/stream"


_default_application_service: ApplicationService | None = None


def get_application_service() -> ApplicationService:
    """Get or initialize singleton ApplicationService instance."""
    global _default_application_service
    if _default_application_service is None:
        try:
            from ...api.learning import get_adaptive_learning_service
            return get_adaptive_learning_service()
        except Exception:
            _default_application_service = ApplicationService()
    return _default_application_service


def set_application_service(svc: ApplicationService | None) -> None:
    """Set global application service instance (useful in tests or initialization)."""
    global _default_application_service
    _default_application_service = svc
