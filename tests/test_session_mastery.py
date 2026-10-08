"""Offline canonical learning contracts through HTTP mock transport and persisted attempts."""

from __future__ import annotations
import copy
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.core.supabase import SupabaseConfig, SupabaseRuntime, AuthenticatedUser
from app.services.repositories.knowledge_repository import KnowledgeError
from app.services.mastery.session_learning import (
    SessionLearningService,
    LearningSnapshot,
    FinalizeAssessment,
)
from app.services.mastery.models import MasteryRecord, MasteryState
from app.services.mastery.attempt_models import AssessmentAttempt
from app.services.assessment.schemas import (
    SessionAssessmentRequest,
    CanonicalSubmission,
    AnswerSubmission,
)
from app.services.assessment.session_assessment import (
    SessionAssessmentService,
    AssessmentInsufficientEvidence,
)
from app.services.learning_session import LearningSessionRepository
from tests.test_canonical_assessment import setup, SID, fixture, OWNER


class LearningTransport:
    """Durable contract double; independent aggregate store and CAS journal."""

    def __init__(self, assessment_transport, learning) -> None:
        self.assessments = assessment_transport
        self.learning = learning
        self.saved = LearningSnapshot(revision=0)
        self.unavailable = False
        self.conflict = False
        self.writes = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("visualai_assessment_transaction"):
            response = self.assessments(request)
            body = json.loads(request.content)
            if body["p_action"] == "submit" and response.status_code == 200:
                row = response.json()
                if row and not any(
                    a.session_id == row["session_id"] for a in self.saved.attempts
                ):
                    for q in row["questions"]:
                        selected = row["submitted_answers"][q["question_id"]]
                        self.saved.attempts.append(
                            AssessmentAttempt(
                                attempt_id="A_" + q["question_id"],
                                learning_session_id=row["learning_session_id"],
                                user_id=row["student_id"],
                                source_id=row["source_id"],
                                source_version=row["source_version"],
                                session_id=row["session_id"],
                                concept_id=q["concept_id"],
                                question_id=q["question_id"],
                                assessment_type=row.get(
                                    "assessment_type", "DIAGNOSTIC"
                                ),
                                selected_answer=selected,
                                correct_answer=q["correct_index"],
                                is_correct=selected == q["correct_index"],
                            )
                        )
            return response
        assert request.url.path == "/rest/v1/rpc/visualai_learning_transaction"
        body = json.loads(request.content)
        if self.unavailable:
            return httpx.Response(503)
        if body["p_user_id"] != str(OWNER) or body["p_learning_session_id"] != str(
            self.learning.session_id
        ):
            return httpx.Response(200, json=None)
        if body["p_action"] != "load":
            payload = body["p_payload"]
            key = payload.get("assessment_id")
            if key in self.saved.applied_assessments:
                return httpx.Response(200, json=self.saved.model_dump(mode="json"))
            if self.conflict or payload["expected_revision"] != self.saved.revision:
                return httpx.Response(409)
            self.saved = LearningSnapshot.model_validate(
                {
                    **payload,
                    "revision": self.saved.revision + 1,
                    "attempts": self.saved.attempts,
                    "applied_assessments": self.saved.applied_assessments
                    + ([key] if key else []),
                }
            )
            self.writes += 1
        return httpx.Response(200, json=self.saved.model_dump(mode="json"))


@pytest.fixture
def loop(setup):
    repo, assessments, transport, provider, learning, retrieval = setup
    store = LearningTransport(transport, learning)
    old = repo.runtime
    repo.runtime = SupabaseRuntime(
        SupabaseConfig("https://test.supabase.co", "public-test", "backend-test"),
        transport=httpx.MockTransport(store),
    )
    service = SessionLearningService(repo, retrieval=retrieval)
    yield service, store, learning, provider, repo
    repo.runtime.close()
    repo.runtime = old


def diagnostic(loop, correct=True):
    service = loop[0]
    result = service.assessments.start(
        SID, SessionAssessmentRequest(request_id=uuid4(), question_count=1)
    )
    service.assessments.submit(
        SID,
        result.session_id,
        CanonicalSubmission(
            answers=[
                AnswerSubmission(
                    question_id=result.questions[0].question_id,
                    selected_index=0 if correct else 1,
                )
            ]
        ),
    )
    return result.session_id


def reattempt(loop, job_id, correct=True):
    service = loop[0]
    result = service.reassess(
        SID, job_id, SessionAssessmentRequest(request_id=uuid4(), question_count=1)
    )
    service.assessments.submit(
        SID,
        result.session_id,
        CanonicalSubmission(
            answers=[
                AnswerSubmission(
                    question_id=result.questions[0].question_id,
                    selected_index=0 if correct else 1,
                )
            ]
        ),
    )
    return service.finalize(SID, result.session_id)


def test_canonical_attempts_threshold_and_idempotency(loop):
    service, store, *_ = loop
    key = diagnostic(loop)
    result = service.finalize(SID, key)
    assert result.mastery[0].mastery_state == MasteryState.LEARNING
    assert result.mastery[0].attempt_count == result.mastery[0].consecutive_correct == 1
    assert service.finalize(SID, key) == result and store.writes == 1
    second = service.finalize(SID, diagnostic(loop))
    assert second.mastery[0].mastery_state == MasteryState.MASTERED
    assert second.mastery[0].correct_count == second.mastery[0].attempt_count == 2
    assert second.remediation == second.weak_concept_ids == []
    assert service.get(SID) == second


def test_grounded_gap_plan_exact_scope_and_no_duplicate_jobs(loop):
    service, store, learning, provider, repo = loop
    key = diagnostic(loop, False)
    result = service.finalize(SID, key)
    record, gap, job = result.mastery[0], result.gaps[0], result.remediation[0]
    assert record.mastery_state == MasteryState.REMEDIATING
    assert (
        gap.misconception_code == "CONCEPT_GAP"
        and gap.confidence_state.value == "POSSIBLE"
    )
    assert (
        gap.evidence_attempt_ids == record.processed_attempt_ids
        and gap.evidence_question_ids
    )
    assert (
        job.metadata["prerequisite_concept_ids"] == [] and job.metadata["evidence_ids"]
    )
    assert (
        job.source_version == learning.source_version == 1
        and job.learning_session_id == str(SID)
    )
    assert job.video_job_id is None and job.video_path is None
    assert service.finalize(SID, key) == result and len(store.saved.remediation) == 1
    assert len(provider.calls) == 1


def test_remediation_completion_reassessment_and_mastery(loop):
    service = loop[0]
    result = service.finalize(SID, diagnostic(loop, False))
    job = result.remediation[0].job_id
    with pytest.raises(KnowledgeError):
        service.reassess(SID, job, SessionAssessmentRequest(request_id=uuid4()))
    ready = service.complete(SID, job)
    assert ready.reassessment_job_ids == [job]
    assert service.complete(SID, job) == ready
    first = reattempt(loop, job)
    assert first.mastery[0].mastery_state == MasteryState.REASSESSING
    final = reattempt(loop, job)
    assert final.mastery[0].mastery_state == MasteryState.MASTERED
    assert final.gaps[0].status.value == "CORRECTED"
    assert final.reassessment_job_ids == []


def test_failure_limit_persists_human_fallback_and_stops_loop(loop):
    service, store, *_ = loop
    result = service.finalize(SID, diagnostic(loop, False))
    for cycle in range(1, 4):
        job = result.remediation[-1].job_id
        service.complete(SID, job)
        result = reattempt(loop, job, False)
        if cycle < 3:
            assert result.mastery[0].mastery_state == MasteryState.REMEDIATING
    assert result.mastery[0].mastery_state == MasteryState.NEEDS_SUPPORT
    assert (
        result.human_fallback_concept_ids == ["osmosis"]
        and result.human_fallback_reason
    )
    assert (
        len(result.remediation) == 3
        and result.mastery[0].remediation_attempt_count == 3
    )
    assert service.get(SID) == result
    with pytest.raises(KnowledgeError):
        service.reassess(SID, job, SessionAssessmentRequest(request_id=uuid4()))
    assert store.saved.mastery[0].mastery_state == MasteryState.NEEDS_SUPPORT


@pytest.mark.parametrize("concepts", [["foreign"], ["osmosis", "foreign"]])
def test_reassessment_cannot_broaden(loop, concepts):
    service = loop[0]
    job = service.finalize(SID, diagnostic(loop, False)).remediation[0].job_id
    service.complete(SID, job)
    with pytest.raises(KnowledgeError, match="INVALID_SCOPE"):
        service.reassess(
            SID, job, SessionAssessmentRequest(request_id=uuid4(), concept_ids=concepts)
        )


def test_phase9_engine_reused_and_no_direct_video_or_qdrant():
    source = inspect.getsource(SessionLearningService)
    assert "self.assessments.start(" in source
    assert "self.retrieval.retrieve(" in source and 'retrieval_mode="exact"' in source
    assert all(
        name not in source
        for name in (
            "qdrant_client",
            "generate_question(",
            "video_pipeline",
            "get_reasoning_router",
            "_embed(",
        )
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_version", 2),
        ("source_id", "foreign"),
        ("learning_session_id", str(uuid4())),
        ("user_id", str(uuid4())),
    ],
)
def test_repository_rejects_foreign_or_version_response(loop, field, value):
    service, store, *_ = loop
    service.finalize(SID, diagnostic(loop))
    setattr(store.saved.mastery[0], field, value)
    with pytest.raises(KnowledgeError, match="INVALID_PROVIDER_RESPONSE"):
        service.get(SID)


def test_storage_failure_no_memory_fallback(loop):
    service, store, *_ = loop
    key = diagnostic(loop)
    store.unavailable = True
    with pytest.raises(KnowledgeError, match="PROVIDER_UNAVAILABLE"):
        service.finalize(SID, key)
    assert store.writes == 0


def test_conflict_has_no_partial_write(loop):
    service, store, *_ = loop
    key = diagnostic(loop, False)
    store.conflict = True
    with pytest.raises(KnowledgeError, match="CONFLICT"):
        service.finalize(SID, key)
    assert store.writes == 0 and not store.saved.mastery and not store.saved.remediation


def test_missing_persisted_attempt_fail_closed(loop):
    service, store, *_ = loop
    key = diagnostic(loop)
    store.saved.attempts.clear()
    with pytest.raises(KnowledgeError, match="INVALID_PROVIDER_RESPONSE"):
        service.finalize(SID, key)
    assert not store.writes


def test_foreign_learning_and_assessment_and_job(loop):
    service = loop[0]
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        service.get(uuid4())
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        service.finalize(SID, "foreign")
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        service.complete(SID, "foreign")


def test_frontend_view_excludes_answer_keys(loop):
    service = loop[0]
    progress = service.finalize(SID, diagnostic(loop, False))
    raw = progress.model_dump_json()
    assert all(
        k not in raw
        for k in ("correct_answer", "selected_answer", "correct_index", "backend-test")
    )
    assert progress.weak_concept_ids and progress.remediation and progress.gaps


@pytest.mark.parametrize(
    "field",
    [
        "scores",
        "correct_count",
        "user_id",
        "student_id",
        "source_version",
        "failure_count",
    ],
)
def test_finalize_rejects_client_authority(field):
    with pytest.raises(ValidationError):
        FinalizeAssessment.model_validate({"assessment_id": "test", field: 1})


def test_retrieval_insufficient_evidence_no_partial_commit(loop, monkeypatch):
    service, store, *_ = loop
    key = diagnostic(loop, False)
    original = service.retrieval.retrieve

    def insufficient(*args, **kwargs):
        return original(*args, **kwargs).model_copy(
            update={"outcome": "INSUFFICIENT_EVIDENCE", "items": []}
        )

    monkeypatch.setattr(service.retrieval, "retrieve", insufficient)
    with pytest.raises(AssessmentInsufficientEvidence):
        service.finalize(SID, key)
    assert store.writes == 0


def test_mastered_unrelated_concept_unchanged(loop):
    service, store, learning, *_ = loop
    now = datetime.now(timezone.utc)
    mastered = MasteryRecord(
        user_id=str(OWNER),
        source_id=learning.source_id,
        source_version=1,
        learning_session_id=str(SID),
        concept_id="untouched",
        mastery_state=MasteryState.MASTERED,
        attempt_count=2,
        correct_count=2,
        mastery_score=100,
        consecutive_correct=2,
    )
    store.saved.mastery.append(mastered)
    result = service.finalize(SID, diagnostic(loop, False))
    assert next(r for r in result.mastery if r.concept_id == "untouched") == mastered
    assert all(j.concept_id != "untouched" for j in result.remediation)


def test_prerequisites_only_from_graph_and_supported_history(loop, monkeypatch):
    service, store, learning, provider, repo = loop
    key = diagnostic(loop, False)
    learning.selected_concept_ids.append("parent")
    parent = MasteryRecord(
        user_id=str(OWNER),
        source_id=learning.source_id,
        source_version=1,
        learning_session_id=str(SID),
        concept_id="parent",
        mastery_state=MasteryState.REMEDIATING,
        attempt_count=1,
        incorrect_count=1,
        remediation_attempt_count=1,
    )
    store.saved.mastery.append(parent)
    from tests.test_canonical_retrieval import SCOPE

    knowledge = repo.get_complete_knowledge_map(SCOPE)
    from app.services.knowledge_models import ConceptRelationship

    knowledge = knowledge.model_copy(
        update={
            "concepts": [
                *knowledge.concepts,
                knowledge.concepts[0].model_copy(
                    update={"concept_id": "parent", "name": "Parent", "sequence": 1}
                ),
            ],
            "evidence": [
                *knowledge.evidence,
                knowledge.evidence[0].model_copy(update={"concept_id": "parent"}),
                knowledge.evidence[0].model_copy(
                    update={"support_kind": "prerequisite_evidence"}
                ),
            ],
        }
    )
    relation = ConceptRelationship(
        user_id=OWNER,
        source_id=learning.source_id,
        source_version=1,
        concept_id="osmosis",
        related_concept_id="parent",
        relationship_type="prerequisite",
        evidence_content_ids=["content"],
        provenance={},
    )
    monkeypatch.setattr(
        repo,
        "get_complete_knowledge_map",
        lambda scope: knowledge.model_copy(update={"relationships": [relation]}),
    )
    original = service.retrieval.retrieve

    def evidence(*args, **kwargs):
        result = original(*args, **kwargs)
        return result.model_copy(
            update={
                "items": [
                    i.model_copy(update={"concept_ids": ["osmosis", "parent"]})
                    for i in result.items
                ]
            }
        )

    monkeypatch.setattr(service.retrieval, "retrieve", evidence)
    result = service.finalize(SID, key)
    assert result.remediation[-1].metadata["prerequisite_concept_ids"] == ["parent"]
    assert result.gaps[-1].misconception_code == "PREREQUISITE_GAP"


def test_api_anonymous_is_401():
    with TestClient(app) as client:
        assert client.get(f"/learning-sessions/{SID}/mastery").status_code == 401


def test_migration_backend_only_atomic_and_session_scoped():
    sql = Path("migrations/20261008120000_session_mastery.sql").read_text(
        encoding="utf-8"
    )
    assert (
        "READY_TO_APPLY" in sql
        and "mastery_applied_at" in sql
        and "mastery_revision" in sql
    )
    assert "FOR UPDATE" in sql and "FROM PUBLIC,anon,authenticated" in sql
    assert (
        "concept_mastery_learning_scope" in sql
        and "assessment_transaction_phase9" in sql
    )
    assert "DISABLE ROW LEVEL SECURITY" not in sql


def test_http_owned_progress_foreign_denials_and_client_authority(loop, monkeypatch):
    service, store, learning, provider, repo = loop
    from app.api import learning_sessions as api
    from app.api import qa as auth_api
    import app.services.repositories.factory as factory

    monkeypatch.setattr(auth_api, "get_runtime", lambda: repo.runtime)
    monkeypatch.setattr(factory, "get_knowledge_repository", lambda **kwargs: repo)
    monkeypatch.setattr(api, "SessionLearningService", lambda context: service)
    base = f"/learning-sessions/{SID}"
    headers = {"Authorization": "Bearer test-only"}
    key = diagnostic(loop, False)
    with TestClient(app) as client:
        assert (
            client.post(
                base + "/mastery/finalize", json={"assessment_id": key}
            ).status_code
            == 401
        )
        assert (
            client.post(
                base + "/mastery/finalize",
                json={"assessment_id": key, "student_id": "foreign"},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.get(
                f"/learning-sessions/{uuid4()}/mastery", headers=headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                base + "/mastery/finalize",
                json={"assessment_id": "foreign"},
                headers=headers,
            ).status_code
            == 404
        )
        response = client.post(
            base + "/mastery/finalize", json={"assessment_id": key}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["weak_concept_ids"] == ["osmosis"]
        assert client.get(base + "/mastery", headers=headers).json() == response.json()
        assert (
            client.post(
                base + "/remediation/foreign/complete", headers=headers
            ).status_code
            == 404
        )
        job = response.json()["remediation"][0]["remediation_job_id"]
        assert (
            client.post(
                base + f"/remediation/{job}/complete", headers=headers
            ).status_code
            == 200
        )
        assert (
            client.post(
                base + f"/remediation/{job}/reassessment",
                json={"request_id": str(uuid4()), "question_count": 1},
                headers=headers,
            ).status_code
            == 200
        )


def test_foreign_authenticated_user(loop):
    service, store, learning, provider, repo = loop
    repo.user = AuthenticatedUser(UUID(int=2), None, {"student_id": str(OWNER)})
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        service.get(SID)
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        service.finalize(SID, "foreign")


def test_restart_reload_uses_canonical_store(loop):
    service, store, learning, provider, repo = loop
    progress = service.finalize(SID, diagnostic(loop, False))
    restarted = SessionLearningService(repo, retrieval=service.retrieval)
    assert restarted.get(SID) == progress
    assert len(store.saved.mastery) == len(store.saved.remediation) == 1


def test_unknown_prerequisite_has_no_gap(loop, monkeypatch):
    service, store, learning, provider, repo = loop
    key = diagnostic(loop, False)
    from tests.test_canonical_retrieval import SCOPE
    from app.services.knowledge_models import ConceptRelationship

    knowledge = repo.get_complete_knowledge_map(SCOPE)
    edge = ConceptRelationship(
        **SCOPE.model_dump(),
        concept_id="osmosis",
        related_concept_id="parent",
        relationship_type="prerequisite",
        evidence_content_ids=["content"],
        provenance={},
    )
    knowledge = knowledge.model_copy(update={"relationships": [edge]})
    original = service.retrieval.retrieve
    bundle = original(
        repo,
        __import__(
            "app.services.retrieval", fromlist=["RetrievalRequest"]
        ).RetrievalRequest(
            source_id="source",
            source_version=1,
            query="review",
            topic_id="topic",
            subtopic_id="sub",
            concept_ids=["osmosis"],
            retrieval_mode="exact",
            purpose="remediation",
        ),
    )
    monkeypatch.setattr(repo, "get_complete_knowledge_map", lambda scope: knowledge)
    monkeypatch.setattr(service.retrieval, "retrieve", lambda *args, **kwargs: bundle)
    result = service.finalize(SID, key)
    assert result.gaps[0].misconception_code == "CONCEPT_GAP"
    assert result.remediation[0].metadata["prerequisite_concept_ids"] == []
