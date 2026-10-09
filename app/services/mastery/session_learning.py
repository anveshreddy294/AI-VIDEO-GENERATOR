"""Canonical session orchestration; existing mastery rules, no local persistence."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid5
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    ValidationError,
)
from ...core.config import settings
from ...core.supabase import SupabaseError, SupabaseConflict
from ..repositories.knowledge_repository import KnowledgeRepository, KnowledgeError
from ..learning_session import LearningSession, LearningSessionRepository
from ..retrieval import RetrievalService, RetrievalRequest
from ..security.source_scope import SourceScope
from ..assessment.session_assessment import (
    SessionAssessmentService,
    AssessmentInsufficientEvidence,
)
from ..assessment.schemas import SessionAssessmentRequest, AssessmentStartResponse
from .models import MasteryConfig, MasteryRecord, MasteryState, DomainInvariantViolation
from .state_machine import MasteryStateMachine
from .attempt_models import AssessmentAttempt
from .misconception_models import MisconceptionEvidence, MisconceptionStatus
from .remediation_models import RemediationJob, RemediationJobStatus

MAX_REMEDIATION_CONCEPTS = 20


class GroundedRemediationPlan(BaseModel):
    """Bounded metadata on the existing remediation entity; no executable work."""

    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=256)
    target_concept_ids: list[str] = Field(min_length=1, max_length=1)
    prerequisite_concept_ids: list[str] = Field(max_length=64)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    content_ids: list[str] = Field(min_length=1, max_length=20)
    completed: StrictBool


class LearningSnapshot(BaseModel):
    """Internal durable aggregate. Attempt answer keys never leave this boundary."""

    revision: int = Field(ge=0)
    mastery: list[MasteryRecord] = Field(default_factory=list)
    gaps: list[MisconceptionEvidence] = Field(default_factory=list)
    remediation: list[RemediationJob] = Field(default_factory=list)
    attempts: list[AssessmentAttempt] = Field(default_factory=list)
    applied_assessments: list[str] = Field(default_factory=list)


class LearningProgress(BaseModel):
    learning_session_id: UUID
    source_id: str
    source_version: int
    mastery: list[MasteryRecord]
    weak_concept_ids: list[str]
    gaps: list[MisconceptionEvidence]
    remediation: list[RemediationJob]
    reassessment_job_ids: list[str]
    human_fallback_concept_ids: list[str]
    human_fallback_reason: str | None


class FinalizeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: str = Field(min_length=1, max_length=128)


class SupabaseLearningRepository:
    """Only verified backend RPCs; unavailable storage is an explicit error."""

    def __init__(self, context: KnowledgeRepository) -> None:
        self.context = context

    def transact(
        self,
        learning: LearningSession,
        action: Literal["load", "finalize", "complete"],
        payload: dict[str, JsonValue] | None = None,
    ) -> LearningSnapshot:
        try:
            value = self.context.runtime.admin_request(
                "POST",
                "/rest/v1/rpc/visualai_learning_transaction",
                body={
                    "p_user_id": str(self.context.user.user_id),
                    "p_learning_session_id": str(learning.session_id),
                    "p_action": action,
                    "p_payload": payload or {},
                },
            )
        except SupabaseConflict:
            raise KnowledgeError("CONFLICT") from None
        except SupabaseError:
            raise KnowledgeError("PROVIDER_UNAVAILABLE") from None
        if value is None:
            raise KnowledgeError("NOT_FOUND")
        try:
            snapshot = LearningSnapshot.model_validate(value)
        except (ValidationError, DomainInvariantViolation):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
        for row in [
            *snapshot.mastery,
            *snapshot.gaps,
            *snapshot.remediation,
            *snapshot.attempts,
        ]:
            if (
                row.user_id != str(self.context.user.user_id)
                or row.learning_session_id != str(learning.session_id)
                or row.source_id != learning.source_id
                or row.source_version != learning.source_version
            ):
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        records = {r.concept_id: r for r in snapshot.mastery}
        if len(records) != len(snapshot.mastery) or len(
            {j.job_id for j in snapshot.remediation}
        ) != len(snapshot.remediation):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        for job in snapshot.remediation:
            try:
                plan = GroundedRemediationPlan.model_validate(job.metadata)
            except ValidationError:
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
            if (
                job.concept_id not in records
                or plan.target_concept_ids != [job.concept_id]
                or job.video_path is not None
            ):
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return snapshot


class SessionLearningService:
    """Close the canonical assessment loop using the existing state machine."""

    def __init__(
        self, context: KnowledgeRepository, *, retrieval: RetrievalService | None = None
    ) -> None:
        self.context = context
        self.repository = SupabaseLearningRepository(context)
        self.retrieval = retrieval or RetrievalService()
        self.assessments = SessionAssessmentService(context, retrieval=self.retrieval)
        self.machine = MasteryStateMachine(
            MasteryConfig(
                min_diagnostic_correct_streak=settings.mastery_threshold,
                max_remediation_attempts=settings.kill_switch_limit,
            )
        )

    def _learning(self, sid: UUID, *, active: bool = False) -> LearningSession:
        learning = LearningSessionRepository(self.context).get(sid)
        if active and learning.state != "ACTIVE":
            raise KnowledgeError("CONFLICT")
        return learning

    @staticmethod
    def _key(learning: LearningSession, kind: str, concept: str, cycle: int = 0) -> str:
        return (
            kind
            + "_"
            + uuid5(
                NAMESPACE_URL,
                f"{learning.user_id}:{learning.session_id}:{learning.source_id}:{learning.source_version}:{concept}:{cycle}",
            ).hex
        )

    @staticmethod
    def _view(learning: LearningSession, saved: LearningSnapshot) -> LearningProgress:
        states = {r.concept_id: r.mastery_state for r in saved.mastery}
        fallback = sorted(
            c for c, state in states.items() if state == MasteryState.NEEDS_SUPPORT
        )
        return LearningProgress(
            learning_session_id=learning.session_id,
            source_id=learning.source_id,
            source_version=learning.source_version,
            mastery=saved.mastery,
            gaps=saved.gaps,
            remediation=saved.remediation,
            weak_concept_ids=sorted(
                c
                for c, state in states.items()
                if state
                in (
                    MasteryState.WEAK,
                    MasteryState.REMEDIATING,
                    MasteryState.REASSESSING,
                )
            ),
            reassessment_job_ids=[
                j.job_id
                for j in saved.remediation
                if j.status == RemediationJobStatus.READY
                and j.metadata.get("completed") is True
                and states.get(j.concept_id) == MasteryState.REASSESSING
                and j.attempt_number
                == next(
                    r.remediation_attempt_count
                    for r in saved.mastery
                    if r.concept_id == j.concept_id
                )
            ],
            human_fallback_concept_ids=fallback,
            human_fallback_reason=(
                "Remediation attempt limit reached" if fallback else None
            ),
        )

    def get(self, sid: UUID) -> LearningProgress:
        learning = self._learning(sid)
        return self._view(learning, self.repository.transact(learning, "load"))

    def finalize(self, sid: UUID, assessment_id: str) -> LearningProgress:
        learning = self._learning(sid, active=True)
        assessment = self.assessments.owned(sid, assessment_id)
        if assessment.status != "SUBMITTED":
            raise KnowledgeError("CONFLICT")
        saved = self.repository.transact(learning, "load")
        if assessment_id in saved.applied_assessments:
            return self._view(learning, saved)
        attempts = sorted(
            (a for a in saved.attempts if a.session_id == assessment_id),
            key=lambda a: (a.submitted_at, a.attempt_id),
        )
        if len(attempts) != len(assessment.questions) or {
            a.question_id for a in attempts
        } != {q.question_id for q in assessment.questions}:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        records = {r.concept_id: r for r in saved.mastery}
        allowed = set(learning.selected_concept_ids)
        if assessment.assessment_type == "REASSESSMENT":
            job = next(
                (
                    j
                    for j in saved.remediation
                    if j.job_id == assessment.reassessment_job_id
                ),
                None,
            )
            if (
                job is None
                or job.concept_id not in records
                or records[job.concept_id].mastery_state != MasteryState.REASSESSING
                or records[job.concept_id].remediation_attempt_count
                != job.attempt_number
            ):
                raise KnowledgeError("CONFLICT")
        for attempt in attempts:
            if attempt.concept_id not in allowed:
                raise KnowledgeError("INVALID_SCOPE")
            record = records.get(attempt.concept_id)
            if record is None:
                record = self.machine.create_initial_record(
                    str(learning.user_id), learning.source_id, attempt.concept_id
                )
                record.learning_session_id, record.source_version = (
                    str(sid),
                    learning.source_version,
                )
                records[attempt.concept_id] = record
            if record.mastery_state == MasteryState.NEEDS_SUPPORT:
                continue
            if record.mastery_state == MasteryState.REMEDIATING:
                raise KnowledgeError("CONFLICT")
            self.machine.record_assessment_attempt(
                record,
                attempt.attempt_id,
                attempt.is_correct,
                session_id=assessment_id,
                assessment_type=attempt.assessment_type,
            )
        saved.mastery = list(records.values())
        knowledge = self.context.get_complete_knowledge_map(
            SourceScope(
                user_id=learning.user_id,
                source_id=learning.source_id,
                source_version=learning.source_version,
            )
        )
        gaps = {g.concept_id: g for g in saved.gaps}
        weak = {c for c, r in records.items() if r.mastery_state == MasteryState.WEAK}
        if len(weak) > MAX_REMEDIATION_CONCEPTS:
            raise KnowledgeError("INVALID_SCOPE")
        for concept, record in records.items():
            if record.mastery_state == MasteryState.MASTERED and concept in gaps:
                gaps[concept].status = MisconceptionStatus.CORRECTED
                gaps[concept].corrected_at = datetime.now(timezone.utc)
            if concept not in weak:
                continue
            parents = sorted(
                {
                    r.related_concept_id
                    for r in knowledge.relationships
                    if r.concept_id == concept
                    and r.relationship_type == "prerequisite"
                    and r.related_concept_id in allowed
                    and r.related_concept_id in records
                    and records[r.related_concept_id].mastery_state
                    in (
                        MasteryState.WEAK,
                        MasteryState.REMEDIATING,
                        MasteryState.REASSESSING,
                    )
                }
            )
            failures = [
                a
                for a in saved.attempts
                if a.concept_id == concept and not a.is_correct
            ]
            if not failures:
                raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
            gap = gaps.get(concept)
            gap = MisconceptionEvidence(
                misconception_id=self._key(learning, "GAP", concept),
                user_id=str(learning.user_id),
                learning_session_id=str(sid),
                source_id=learning.source_id,
                source_version=learning.source_version,
                session_id=assessment_id,
                concept_id=concept,
                misconception_code="PREREQUISITE_GAP" if parents else "CONCEPT_GAP",
                misconception_label="Incorrect responses recorded",
                misconception_type="learning_gap",
                evidence_attempt_ids=sorted({a.attempt_id for a in failures}),
                evidence_question_ids=sorted({a.question_id for a in failures}),
                occurrence_count=len(failures),
                first_detected_at=(
                    gap.first_detected_at
                    if gap
                    else min(a.submitted_at for a in failures)
                ),
                last_detected_at=max(a.submitted_at for a in failures),
                supporting_evidence_summary="Incorrect canonical attempts; no inferred learner beliefs.",
            )
            gaps[concept] = gap
            if (
                record.remediation_attempt_count
                >= self.machine.config.max_remediation_attempts
            ):
                self.machine.transition_to(record, MasteryState.NEEDS_SUPPORT)
                continue
            bundle = self.retrieval.retrieve(
                self.context,
                RetrievalRequest(
                    source_id=learning.source_id,
                    source_version=learning.source_version,
                    topic_id=learning.topic_id,
                    subtopic_id=learning.subtopic_id,
                    concept_ids=[*parents, concept],
                    query="Review canonical evidence for these learning gaps.",
                    purpose="remediation",
                    retrieval_mode="exact",
                    include_prerequisites=False,
                    max_items=MAX_REMEDIATION_CONCEPTS,
                ),
            )
            if (
                bundle.scope
                != SourceScope(
                    user_id=learning.user_id,
                    source_id=learning.source_id,
                    source_version=learning.source_version,
                )
                or bundle.outcome != "READY"
                or not bundle.items
            ):
                raise AssessmentInsufficientEvidence()
            targets = set(parents) | {concept}
            if not targets <= {c for i in bundle.items for c in i.concept_ids} or any(
                i.source_id != learning.source_id
                or i.source_version != learning.source_version
                or not set(i.concept_ids) <= allowed
                for i in bundle.items
            ):
                raise AssessmentInsufficientEvidence()
            self.machine.assign_remediation(record, session_id=assessment_id)
            key = self._key(
                learning, "REMEDIATION", concept, record.remediation_attempt_count
            )
            saved.remediation.append(
                RemediationJob(
                    remediation_job_id=key,
                    idempotency_key=key,
                    user_id=str(learning.user_id),
                    source_id=learning.source_id,
                    source_version=learning.source_version,
                    learning_session_id=str(sid),
                    session_id=assessment_id,
                    concept_id=concept,
                    status=RemediationJobStatus.READY,
                    attempt_number=record.remediation_attempt_count,
                    misconception_code=gap.misconception_code,
                    evidence_attempt_ids=gap.evidence_attempt_ids,
                    strategy_used=(
                        "PREREQUISITE_REVIEW" if parents else "DIRECT_EXPLANATION"
                    ),
                    metadata=GroundedRemediationPlan.model_validate(
                        {
                            "reason": "Canonical incorrect-response evidence",
                            "target_concept_ids": [concept],
                            "prerequisite_concept_ids": parents,
                            "evidence_ids": [i.evidence_id for i in bundle.items],
                            "content_ids": sorted({i.content_id for i in bundle.items}),
                            "completed": False,
                        }
                    ).model_dump(mode="json"),
                )
            )
        saved.gaps = list(gaps.values())
        return self._save(learning, saved, "finalize", assessment_id=assessment_id)

    def _save(
        self,
        learning: LearningSession,
        saved: LearningSnapshot,
        action: Literal["finalize", "complete"],
        **ids: str,
    ) -> LearningProgress:
        payload: dict[str, JsonValue] = {
            "expected_revision": saved.revision,
            "mastery": [r.model_dump(mode="json") for r in saved.mastery],
            "gaps": [g.model_dump(mode="json") for g in saved.gaps],
            "remediation": [j.model_dump(mode="json") for j in saved.remediation],
            **ids,
        }
        return self._view(learning, self.repository.transact(learning, action, payload))

    def complete(self, sid: UUID, job_id: str) -> LearningProgress:
        learning = self._learning(sid, active=True)
        saved = self.repository.transact(learning, "load")
        job = next((j for j in saved.remediation if j.job_id == job_id), None)
        if job is None:
            raise KnowledgeError("NOT_FOUND")
        if job.metadata.get("completed") is True:
            return self._view(learning, saved)
        record = next(
            (r for r in saved.mastery if r.concept_id == job.concept_id), None
        )
        if (
            job.status != RemediationJobStatus.READY
            or record is None
            or record.remediation_attempt_count != job.attempt_number
        ):
            raise KnowledgeError("CONFLICT")
        if record.mastery_state != MasteryState.REMEDIATING:
            raise KnowledgeError("CONFLICT")
        if job.video_job_id is not None:
            from ..video.session_video import SessionVideo
            video = SessionVideo(self.context, sid, job_id).get()
            if video.get("job_id") != job.video_job_id or video.get("status") != "COMPLETED":
                raise KnowledgeError("CONFLICT")
        self.machine.confirm_remediation(record)
        job.metadata["completed"] = True
        job.completed_at = datetime.now(timezone.utc)
        return self._save(learning, saved, "complete", job_id=job_id)

    def reassess(
        self, sid: UUID, job_id: str, request: SessionAssessmentRequest
    ) -> AssessmentStartResponse:
        learning = self._learning(sid, active=True)
        saved = self.repository.transact(learning, "load")
        job = next((j for j in saved.remediation if j.job_id == job_id), None)
        if job is None:
            raise KnowledgeError("NOT_FOUND")
        if job_id not in self._view(learning, saved).reassessment_job_ids:
            raise KnowledgeError("CONFLICT")
        eligible = {job.concept_id}
        requested = set(request.concept_ids or eligible)
        if (
            not requested
            or not requested <= eligible
            or not requested <= set(learning.selected_concept_ids)
        ):
            raise KnowledgeError("INVALID_SCOPE")
        return self.assessments.start(
            sid,
            request.model_copy(update={"concept_ids": sorted(requested)}),
            reassessment_job_id=job_id,
        )
