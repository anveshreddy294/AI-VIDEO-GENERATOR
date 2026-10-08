"""Canonical session assessment orchestration using existing planner/generator/grader."""

from __future__ import annotations
import hashlib
import json
from uuid import UUID, NAMESPACE_URL, uuid5
from typing import cast
from pydantic import ValidationError
from ..learning_session import (
    LearningSessionService,
    LearningSessionRepository,
    SessionQARequest,
)
from ..retrieval import RetrievalService, RetrievalRequest
from ..repositories.knowledge_repository import KnowledgeRepository, KnowledgeError
from ..repositories.supabase_repository import SupabaseAssessmentRepository
from ..schemas import ConceptNode
from .schemas import (
    SessionAssessmentRequest,
    AssessmentSession,
    AssessmentStartResponse,
    SafeQuestion,
    SafeOption,
    CanonicalSubmission,
    AssessmentPerformance,
    AssessmentPlan,
    Question,
)
from .planner import AssessmentPlanner
from .generator import generate_canonical_questions
from .engine import grade_canonical_submission


class AssessmentInsufficientEvidence(RuntimeError):
    """No provider call or persistence is allowed without usable canonical evidence."""


class SessionAssessmentService:
    """Owned immutable scope, safe learner views and explicit durable repository failures."""

    def __init__(
        self,
        context: KnowledgeRepository,
        *,
        repository: SupabaseAssessmentRepository | None = None,
        retrieval: RetrievalService | None = None,
    ) -> None:
        self.context = context
        from ..repositories.factory import get_assessment_repository

        self.repository = repository or cast(
            SupabaseAssessmentRepository, get_assessment_repository(context=context)
        )
        self.retrieval = retrieval or RetrievalService()

    def start(
        self, learning_session_id: UUID, request: SessionAssessmentRequest
    ) -> AssessmentStartResponse:
        if request.concept_ids is not None and len(set(request.concept_ids)) != len(
            request.concept_ids
        ):
            raise KnowledgeError("INVALID_SCOPE")
        narrowed = LearningSessionService(self.context).qa_request(
            SessionQARequest(
                session_id=learning_session_id,
                question="Generate evidence-grounded assessment questions for this session.",
                concept_ids=request.concept_ids,
            )
        )
        key = (
            "ASSESS_"
            + uuid5(
                NAMESPACE_URL,
                str(self.context.user.user_id) + ":" + str(request.request_id),
            ).hex
        )
        digest = hashlib.sha256(
            json.dumps(
                {
                    "learning_session_id": str(learning_session_id),
                    "source_id": narrowed.source_id,
                    "version": narrowed.source_version,
                    "topic": narrowed.topic_id,
                    "subtopic": narrowed.subtopic_id,
                    "concepts": sorted(narrowed.concept_ids or []),
                    "count": request.question_count,
                    "difficulty": request.difficulty,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        existing = self.repository.get_session(key)
        if existing is not None:
            if existing.request_hash != digest:
                raise KnowledgeError("CONFLICT")
            return self.safe(existing, request.question_count)
        retrieval_request = RetrievalRequest(
            source_id=narrowed.source_id,
            source_version=narrowed.source_version,
            query=narrowed.query,
            topic_id=narrowed.topic_id,
            subtopic_id=narrowed.subtopic_id,
            concept_ids=narrowed.concept_ids,
            purpose="assessment",
            include_prerequisites=False,
            max_items=20,
        )
        bundle = self.retrieval.retrieve(self.context, retrieval_request)
        expected = self.context.scope(narrowed.source_id, narrowed.source_version)
        allowed = narrowed.concept_ids or []
        if (
            bundle.scope != expected
            or bundle.topic_id != narrowed.topic_id
            or bundle.subtopic_id != narrowed.subtopic_id
            or not set(bundle.concept_ids) <= set(allowed)
            or any(
                i.source_id != expected.source_id
                or i.source_version != expected.source_version
                or i.topic_id != narrowed.topic_id
                or (
                    narrowed.subtopic_id is not None
                    and i.subtopic_id != narrowed.subtopic_id
                )
                or not set(i.concept_ids) <= set(allowed)
                for i in bundle.items
            )
        ):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        if bundle.outcome != "READY" or not bundle.items:
            raise AssessmentInsufficientEvidence()
        knowledge = self.context.get_complete_knowledge_map(expected)
        concepts = [
            ConceptNode(
                concept_id=c.concept_id,
                name=c.name,
                definition=c.definition,
                prerequisite_concept_ids=[
                    r.related_concept_id
                    for r in knowledge.relationships
                    if r.concept_id == c.concept_id
                    and r.relationship_type == "prerequisite"
                    and r.related_concept_id in allowed
                ],
                source_content_ids=c.source_content_ids,
            )
            for c in knowledge.concepts
            if c.concept_id in allowed
        ]
        plan = AssessmentPlanner().plan(
            concepts, bundle, request.question_count, request.difficulty
        )
        if not plan.question_count:
            raise AssessmentInsufficientEvidence()
        questions = generate_canonical_questions(
            bundle, plan, concepts, key, request.difficulty
        )
        session = AssessmentSession(
            session_id=key,
            student_id=str(self.context.user.user_id),
            source_id=narrowed.source_id,
            source_version=narrowed.source_version,
            learning_session_id=learning_session_id,
            request_hash=digest,
            concept_queue=plan.concept_targets,
            questions=questions,
            status="READY",
        )
        self.repository.save_session(session)
        saved = self.repository.get_session(key)
        if saved is None:
            raise KnowledgeError("PROVIDER_UNAVAILABLE")
        return self.safe(saved, request.question_count)

    def owned(self, learning_session_id: UUID, assessment_id: str) -> AssessmentSession:
        learning = LearningSessionRepository(self.context).get(learning_session_id)
        assessment = self.repository.get_session(assessment_id)
        if assessment is None or assessment.learning_session_id != learning_session_id:
            raise KnowledgeError("NOT_FOUND")
        if (
            assessment.student_id != str(self.context.user.user_id)
            or assessment.source_id != learning.source_id
            or assessment.source_version != learning.source_version
        ):
            raise KnowledgeError("NOT_FOUND")
        return assessment

    def get(
        self, learning_session_id: UUID, assessment_id: str
    ) -> AssessmentStartResponse:
        return self.safe(self.owned(learning_session_id, assessment_id))

    def submit(
        self,
        learning_session_id: UUID,
        assessment_id: str,
        submission: CanonicalSubmission,
    ) -> AssessmentPerformance:
        session = self.owned(learning_session_id, assessment_id)
        learning = LearningSessionRepository(self.context).get(learning_session_id)
        if learning.state != "ACTIVE" or not set(session.concept_queue) <= set(
            learning.selected_concept_ids
        ):
            raise KnowledgeError("CONFLICT")
        answers = {a.question_id: a.selected_index for a in submission.answers}
        if len(answers) != len(submission.answers):
            raise KnowledgeError("INVALID_SCOPE")
        if session.status == "SUBMITTED":
            if session.submitted_answers != answers:
                raise KnowledgeError("CONFLICT")
            return self.result(learning_session_id, assessment_id)
        if session.status != "READY":
            raise KnowledgeError("CONFLICT")
        try:
            result = grade_canonical_submission(session, submission.answers)
        except ValueError:
            raise KnowledgeError("INVALID_SCOPE") from None
        saved = self.repository.submit(session, answers, result)
        if saved.submission_response is None:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return self.result(learning_session_id, assessment_id)

    def result(
        self, learning_session_id: UUID, assessment_id: str
    ) -> AssessmentPerformance:
        session = self.owned(learning_session_id, assessment_id)
        if session.status != "SUBMITTED" or session.submission_response is None:
            raise KnowledgeError("NOT_READY")
        try:
            return AssessmentPerformance.model_validate(session.submission_response)
        except ValidationError:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None

    @staticmethod
    def safe(
        session: AssessmentSession, requested: int | None = None
    ) -> AssessmentStartResponse:
        if session.status not in ("READY", "SUBMITTED"):
            raise KnowledgeError("NOT_READY")
        questions = [
            SafeQuestion(
                question_id=q.question_id,
                concept_id=q.concept_id,
                concept_name=q.concept_name,
                stem=q.stem,
                options=[SafeOption(index=o.index, text=o.text) for o in q.options],
                difficulty=q.difficulty,
                page_start=q.page_start,
                page_end=q.page_end,
                timestamp_start=q.timestamp_start,
                timestamp_end=q.timestamp_end,
                source_version=session.source_version,
            )
            for q in session.questions
        ]
        count = requested or len(questions)
        return AssessmentStartResponse(
            status=session.status,
            session_id=session.session_id,
            student_id=session.student_id,
            source_id=session.source_id,
            source_version=session.source_version,
            learning_session_id=session.learning_session_id,
            question_count=len(questions),
            questions=questions,
            requested_questions=count,
            generated_questions=len(questions),
            concepts_tested=[q.concept_name for q in session.questions],
            shortfall=max(0, count - len(questions)),
        )
