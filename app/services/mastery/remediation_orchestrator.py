"""Step 5D Remediation Orchestrator — Real Video Engine Integration & Lifecycle Control.

Connects NextLearningAction(REMEDIATE) to the verified Step 3 video engine,
managing video generation jobs, idempotency, strict artifact verification,
attempt budget preservation against infrastructure failures, and state machine transitions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from ..assessment.schemas import VideoTarget
from ..schemas import KnowledgeGraph
from ..video.scene_schema import VideoArtifact, VideoJobStatus
from ..video.video_compositor import validate_video_artifact
from .attempt_models import AssessmentAttempt
from .attempt_repository import AssessmentAttemptRepository
from .dependency_provider import ConceptDependencyProvider
from .models import DomainInvariantViolation, MasteryRecord, MasteryState
from .question_registry import AuthoritativeQuestion, QuestionRegistry
from .remediation_models import RemediationJob, RemediationJobStatus
from .remediation_repository import RemediationJobRepository
from .repository import MasteryRepository
from .roadmap_models import LearningActionType, NextLearningAction
from .state_machine import InvalidStateTransitionError, MasteryStateMachine

logger = logging.getLogger(__name__)


class RemediationOrchestrator:
    """Orchestrates personalized video remediation and bridges Step 5 mastery with Step 3 video engine."""

    def __init__(
        self,
        mastery_repo: MasteryRepository,
        remediation_repo: RemediationJobRepository,
        attempt_repo: AssessmentAttemptRepository | None = None,
        question_registry: QuestionRegistry | None = None,
        state_machine: MasteryStateMachine | None = None,
        video_engine_fn: Callable[..., Awaitable[VideoArtifact]] | None = None,
        dependency_provider: ConceptDependencyProvider | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
        curriculum_concepts: dict[str, Any] | None = None,
    ) -> None:
        self.mastery_repo = mastery_repo
        self.remediation_repo = remediation_repo
        self.attempt_repo = attempt_repo
        self.question_registry = question_registry
        self.state_machine = state_machine or MasteryStateMachine()
        self.dependency_provider = dependency_provider
        self.knowledge_graph = knowledge_graph
        self.curriculum_concepts = curriculum_concepts or {}

        if video_engine_fn is None:
            from ..video.engine import execute_video_generation_job

            self.video_engine_fn = execute_video_generation_job
        else:
            self.video_engine_fn = video_engine_fn

        # Per-(user, source, concept) locks for serializing orchestration transitions
        self._locks: dict[tuple[str, str, str], asyncio.Lock] = {}
        # Completion events for concurrent callers to await active jobs
        self._job_events: dict[str, asyncio.Event] = {}

    def _get_lock(self, user_id: str, source_id: str, concept_id: str) -> asyncio.Lock:
        key = (user_id.strip(), source_id.strip(), concept_id.strip())
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _validate_curriculum_grounding(self, concept_id: str) -> None:
        """Ensure concept exists in grounded curriculum if knowledge graph / curriculum provided."""
        cid = concept_id.strip()
        if self.knowledge_graph and cid not in self.knowledge_graph.concepts:
            raise DomainInvariantViolation(
                f"Concept '{cid}' not found in grounded KnowledgeGraph."
            )
        if self.curriculum_concepts and cid not in self.curriculum_concepts:
            raise DomainInvariantViolation(
                f"Concept '{cid}' not found in registered curriculum concepts."
            )

    async def execute_remediation(
        self,
        action_or_user_id: NextLearningAction | str | None = None,
        source_id: str | None = None,
        concept_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        force: bool = False,
        raise_on_failure: bool = False,
        wait_for_completion: bool = True,
        run_in_background: bool = False,
        **engine_kwargs: Any,
    ) -> RemediationJob:
        """Execute or retrieve a grounded remediation video job for the learner."""
        # Normalize input from NextLearningAction or direct parameters
        if isinstance(action_or_user_id, NextLearningAction):
            action = action_or_user_id
            if action.action_type != LearningActionType.REMEDIATE:
                raise DomainInvariantViolation(
                    f"Cannot execute remediation for action of type '{action.action_type.value}'; expected REMEDIATE."
                )
            user_id = action.user_id.strip()
            source_id = action.source_id.strip()
            if not action.concept_id or not action.concept_id.strip():
                raise DomainInvariantViolation(
                    "action.concept_id must be provided and non-empty for REMEDIATE action."
                )
            concept_id = action.concept_id.strip()
            session_id = session_id or action.session_id
        else:
            resolved_uid = user_id or (
                str(action_or_user_id).strip() if action_or_user_id is not None else None
            )
            if not resolved_uid or not resolved_uid.strip():
                raise DomainInvariantViolation("user_id must be provided and non-empty.")
            if not source_id or not source_id.strip():
                raise DomainInvariantViolation("source_id must be provided and non-empty.")
            if not concept_id or not concept_id.strip():
                raise DomainInvariantViolation("concept_id must be provided and non-empty.")
            user_id = resolved_uid.strip()
            source_id = source_id.strip()
            concept_id = concept_id.strip()

        self._validate_curriculum_grounding(concept_id)

        lock = self._get_lock(user_id, source_id, concept_id)
        active_event_to_await: asyncio.Event | None = None
        active_job_to_await: RemediationJob | None = None

        async with lock:
            # 1. Retrieve mastery record and enforce domain invariants
            record = self.mastery_repo.get(user_id, source_id, concept_id)
            if record is None:
                raise DomainInvariantViolation(
                    f"No mastery record found for concept '{concept_id}'. Learner must be assessed first."
                )

            if record.mastery_state == MasteryState.MASTERED:
                raise InvalidStateTransitionError(
                    "Cannot assign remediation to a concept in MASTERED state."
                )
            if record.mastery_state == MasteryState.NEEDS_SUPPORT:
                raise InvalidStateTransitionError(
                    "Concept is in NEEDS_SUPPORT state; remediation attempt limit exceeded and requires instructor intervention."
                )
            if (
                record.remediation_attempt_count >= self.state_machine.config.max_remediation_attempts
            ):
                if record.mastery_state != MasteryState.NEEDS_SUPPORT:
                    self.state_machine.transition_to(record, MasteryState.NEEDS_SUPPORT)
                    self.mastery_repo.save(record)
                raise InvalidStateTransitionError(
                    f"Maximum remediation attempts ({self.state_machine.config.max_remediation_attempts}) exceeded; concept requires human support."
                )

            # Determine attempt number for this cycle
            if record.mastery_state == MasteryState.WEAK:
                attempt_number = record.remediation_attempt_count + 1
            else:
                attempt_number = max(1, record.remediation_attempt_count)

            idempotency_key = f"{user_id}:{source_id}:{concept_id}:{attempt_number}"

            if not force:
                # 2. Check for active (PENDING / RUNNING) job for this attempt cycle
                active_job = self.remediation_repo.find_active_for_concept(
                    user_id=user_id,
                    source_id=source_id,
                    concept_id=concept_id,
                    attempt_number=attempt_number,
                )
                if active_job:
                    logger.info(
                        "[remediation] Found existing active job %s for concept %s (status=%s)",
                        active_job.remediation_job_id,
                        concept_id,
                        active_job.status.value,
                    )
                    if wait_for_completion and active_job.remediation_job_id in self._job_events:
                        active_event_to_await = self._job_events[active_job.remediation_job_id]
                        active_job_to_await = active_job
                    else:
                        return active_job

                # 3. Check for completed (READY) job for this exact attempt cycle
                if not active_event_to_await:
                    existing_ready = self.remediation_repo.find_ready_for_attempt(
                        user_id=user_id,
                        source_id=source_id,
                        concept_id=concept_id,
                        attempt_number=attempt_number,
                    )
                    if (
                        existing_ready
                        and existing_ready.video_path
                        and Path(existing_ready.video_path).exists()
                    ):
                        logger.info(
                            "[remediation] Reusing completed video from job %s (key=%s)",
                            existing_ready.remediation_job_id,
                            existing_ready.idempotency_key,
                        )
                        return existing_ready

            if not active_event_to_await:
                # 4. Advance mastery state machine to REMEDIATING (if WEAK)
                did_increment_attempt = False
                if record.mastery_state == MasteryState.WEAK:
                    self.state_machine.assign_remediation(record, session_id=session_id)
                    self.mastery_repo.save(record)
                    did_increment_attempt = True

                # 5. Create new RemediationJob in RUNNING status
                job_id = f"REM_{uuid4().hex[:10].upper()}"
                job = RemediationJob(
                    remediation_job_id=job_id,
                    user_id=user_id,
                    source_id=source_id,
                    session_id=session_id,
                    concept_id=concept_id,
                    status=RemediationJobStatus.RUNNING,
                    attempt_number=record.remediation_attempt_count,
                    idempotency_key=idempotency_key,
                    started_at=datetime.now(timezone.utc),
                )
                self.remediation_repo.save(job)
                completion_event = asyncio.Event()
                self._job_events[job_id] = completion_event

                # 6. Build grounded VideoTarget
                target = self._build_video_target(
                    user_id=user_id,
                    source_id=source_id,
                    session_id=session_id,
                    concept_id=concept_id,
                    record=record,
                )

        # If waiting on an existing active job from another worker
        if active_event_to_await and active_job_to_await:
            await active_event_to_await.wait()
            completed = self.remediation_repo.get(active_job_to_await.remediation_job_id)
            return completed or active_job_to_await

        async def _run_pipeline() -> RemediationJob:
            try:
                artifact = await self.video_engine_fn(
                    target=target,
                    job_id=job_id,
                    **engine_kwargs,
                )

                # Validate engine returned successful artifact
                if artifact is None or artifact.status == VideoJobStatus.FAILED or not artifact.video_path:
                    error_msg = getattr(artifact, "error", None) or "Video engine returned failed status."
                    raise RuntimeError(f"Video engine error: {error_msg}")

                # 8. Strictly validate final composited video artifact on disk
                video_file = Path(artifact.video_path)
                validation = validate_video_artifact(video_file, expect_audio=True)

                # 9. Success: Acquire lock to finalize job READY and advance mastery to REASSESSING
                async with lock:
                    job.status = RemediationJobStatus.READY
                    job.video_job_id = artifact.job_id
                    job.video_path = str(video_file)
                    job.duration_seconds = float(
                        validation.get("duration", artifact.duration_seconds or 0)
                    )
                    job.completed_at = datetime.now(timezone.utc)
                    self.remediation_repo.save(job)

                    self.state_machine.confirm_remediation(record, session_id=session_id)
                    self.mastery_repo.save(record)

                logger.info(
                    "[remediation] Successfully generated video %s for concept %s (duration=%.1fs); advanced to REASSESSING",
                    job.video_path,
                    concept_id,
                    job.duration_seconds or 0,
                )
                return job

            except Exception as exc:
                # 10. Failure Handling: Record failure and protect educational attempt budget
                logger.error(
                    "[remediation] Video generation failed for job %s: %s",
                    job_id,
                    exc,
                    exc_info=True,
                )
                async with lock:
                    job.status = RemediationJobStatus.FAILED
                    job.failed_at = datetime.now(timezone.utc)
                    job.failure_code = "INFRASTRUCTURE_FAILURE"
                    job.failure_message = str(exc)
                    job.is_infrastructure_failure = True
                    self.remediation_repo.save(job)

                    # Roll back educational attempt counter and return state to WEAK
                    if did_increment_attempt:
                        record.remediation_attempt_count = max(0, record.remediation_attempt_count - 1)
                        record.mastery_state = MasteryState.WEAK
                        record.touch()
                        self.mastery_repo.save(record)
                        logger.info(
                            "[remediation] Rolled back attempt counter for concept %s (attempts=%d, state=WEAK) due to infrastructure failure",
                            concept_id,
                            record.remediation_attempt_count,
                        )

                if raise_on_failure:
                    raise
                return job

            finally:
                if completion_event:
                    completion_event.set()
                    self._job_events.pop(job_id, None)

        if run_in_background:
            asyncio.create_task(_run_pipeline())
            return job

        return await _run_pipeline()

    def _build_video_target(
        self,
        user_id: str,
        source_id: str,
        session_id: str | None,
        concept_id: str,
        record: MasteryRecord,
    ) -> VideoTarget:
        """Construct grounded VideoTarget from curriculum, recent failed attempt, and question registry."""
        concept_name = concept_id
        definition = ""
        difficulty = "intermediate"

        if self.knowledge_graph and concept_id in self.knowledge_graph.concepts:
            node = self.knowledge_graph.concepts[concept_id]
            concept_name = getattr(node, "name", concept_id)
            definition = getattr(node, "definition", "")
            diff_val = getattr(node, "difficulty", "intermediate")
            if diff_val in ("foundational", "intermediate", "advanced"):
                difficulty = diff_val
        elif concept_id in self.curriculum_concepts:
            c_info = self.curriculum_concepts[concept_id]
            if isinstance(c_info, dict):
                concept_name = c_info.get("name", concept_id)
                definition = c_info.get("definition", "")
                diff_val = c_info.get("difficulty", "intermediate")
                if diff_val in ("foundational", "intermediate", "advanced"):
                    difficulty = diff_val
            elif isinstance(c_info, str):
                concept_name = c_info

        # Target seconds scaling
        duration_map = {"foundational": 30, "intermediate": 45, "advanced": 60}
        target_seconds = duration_map.get(difficulty, 45)

        # Grounding from most recent failed attempt and question registry
        q_id = ""
        q_stem = f"Core concept demonstration for {concept_name}"
        sel_idx = -1
        corr_idx = -1
        explanation = definition or f"Authoritative concept explanation for {concept_name}."
        misconception = ""
        chunk_ids: list[str] = []
        source_content_ids: list[str] = []
        authoritative_evidence: list[str] = []

        if self.attempt_repo:
            attempts = self.attempt_repo.list_for_concept(user_id, source_id, concept_id)
            # Find the most recent incorrect attempt
            incorrect_attempts = [a for a in attempts if not a.is_correct]
            if incorrect_attempts:
                latest_incorrect = max(
                    incorrect_attempts,
                    key=lambda a: a.submitted_at or a.created_at,
                )
                q_id = latest_incorrect.question_id
                sel_idx = latest_incorrect.selected_answer

                if self.question_registry:
                    auth_q = self.question_registry.get(q_id)
                    if auth_q:
                        q_stem = auth_q.stem
                        corr_idx = auth_q.correct_index
                        if auth_q.explanation:
                            explanation = auth_q.explanation
                        misconception = (
                            f"Learner selected option {sel_idx} instead of correct option {corr_idx} "
                            f"on question: '{auth_q.stem[:80]}'."
                        )
                        chunk_ids = getattr(auth_q, "chunk_ids", []) or []
                        source_content_ids = getattr(auth_q, "content_ids", []) or []

        if not misconception:
            misconception = f"Learner demonstrated a conceptual gap regarding '{concept_name}'."

        if not authoritative_evidence:
            if definition:
                authoritative_evidence.append(definition)
            if explanation and explanation != definition:
                authoritative_evidence.append(explanation)

        # Prerequisites
        prereqs: list[str] = []
        if self.dependency_provider:
            prereqs = self.dependency_provider.get_prerequisites(concept_id)

        directive = f"Generate a {target_seconds}-second remedial AI animation explaining {concept_name}"
        video_objective = (
            f"Remediate conceptual gap in '{concept_name}' ({difficulty}): "
            f"address misconception '{misconception[:100]}' using grounded source evidence."
        )

        return VideoTarget(
            session_id=session_id or "",
            student_id=user_id,
            source_id=source_id,
            concept_id=concept_id,
            concept_name=concept_name,
            definition=definition,
            difficulty=difficulty,
            assessment_score=record.mastery_score,
            score=record.mastery_score,
            status="NEEDS_VIDEO",
            target_seconds=target_seconds,
            video_objective=video_objective,
            directive=directive,
            question_id=q_id,
            question_stem=q_stem,
            selected_index=sel_idx,
            correct_index=corr_idx,
            explanation=explanation,
            misconception=misconception,
            prerequisite_concept_ids=prereqs,
            chunk_ids=chunk_ids,
            source_content_ids=source_content_ids,
            authoritative_evidence=authoritative_evidence,
            scope="current_session",
        )
