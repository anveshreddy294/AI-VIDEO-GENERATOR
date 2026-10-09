import os
import time
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
import pytest

from app.core.reasoning import ReasoningRequest, ReasoningResult, Telemetry
from app.services.knowledge_models import Identifier, SourceScope
from app.services.repositories.knowledge_repository import KnowledgeRepository
from app.services.retrieval import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceBudget,
    RetrievalRequest,
    RetrievalService,
)
from app.services.qa.canonical_answer import (
    AnswerProposal,
    CanonicalQARequest,
    SupportedClaim,
    generate_canonical_answer,
    clear_qa_cache,
    _QA_CACHE,
)
from app.services.grounded_notes import (
    GroundedNotesService,
    NotesRequest,
    clear_notes_cache,
    _NOTES_CACHE,
)
from app.services.pipeline_tracker import DurableJobStore, JobManager, PipelineJob
from app.services.schemas import QAResponse

USER_A = UUID("00000000-0000-4000-8000-000000000001")
USER_B = UUID("00000000-0000-4000-8000-000000000002")
SOURCE_ID = "SRC_bio_osmosis"
VERSION = 1
TOPIC = "topic_cell_transport"
SUBTOPIC = "sub_passive_transport"
CONCEPTS = ["osmosis", "cell_membrane"]
SAMPLE_EXCERPT = "Water moves through a semipermeable cell membrane along a concentration gradient. Osmosis is passive transport."


def make_evidence_item(evidence_id: str = "ev_1", excerpt: str = SAMPLE_EXCERPT, version: int = VERSION, source_id: str = SOURCE_ID) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        chunk_id=f"chk_{evidence_id}",
        content_id="cnt_chapter_1",
        source_id=source_id,
        source_version=version,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        citation="Biology Chapter 1, Page 4",
        excerpt=excerpt,
        char_start=0,
        char_end=len(excerpt),
        page_start=4,
        page_end=4,
        slide=None,
        timestamp_start=None,
        timestamp_end=None,
        chapter=None,
        section=None,
        heading_path=["Cell Biology", "Transport"],
        content_role="text",
        retrieval_score=0.95,
        embedding_provenance=None,
    )


def make_bundle(items: list[EvidenceItem] | None = None, outcome: str = "READY", user_id: UUID = USER_A, version: int = VERSION, source_id: str = SOURCE_ID) -> EvidenceBundle:
    items = items if items is not None else [make_evidence_item(version=version, source_id=source_id)]
    return EvidenceBundle(
        evidence_bundle_id=f"bundle_{uuid4().hex[:8]}",
        scope=SourceScope(user_id=user_id, source_id=source_id, source_version=version),
        purpose="qa",
        query="What is osmosis?",
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        items=items,
        manifest_digest=f"digest_{len(items)}_{version}",
        outcome=outcome,
        rejected_candidates={},
        token_count=100,
        token_budget=EvidenceBudget(max_total_tokens=1000, max_item_tokens=500),
        embedding_provenance=None,
        latencies={},
    )


class MockRouter:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.calls: list[ReasoningRequest] = []

    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        self.call_count += 1
        self.calls.append(request)
        resp_text = self.responses.pop(0) if self.responses else "{}"
        return ReasoningResult(
            response=resp_text,
            telemetry=Telemetry(
                provider="cloudflare",
                task=request.task,
                outcome="SUCCESS",
                transport_latency_seconds=0.01,
            ),
        )


class TestPhase4Performance:

    def setup_method(self):
        os.environ["VISUALAI_TEST_CACHE"] = "1"
        clear_qa_cache()
        clear_notes_cache()

    def teardown_method(self):
        os.environ.pop("VISUALAI_TEST_CACHE", None)
        clear_qa_cache()
        clear_notes_cache()

    def test_semantic_paraphrase_reaches_grounding(self):
        repo = Mock(spec=KnowledgeRepository)
        repo.user = Mock(user_id=USER_A)
        retrieval = Mock(spec=RetrievalService)
        bundle = make_bundle()
        retrieval.retrieve.return_value = bundle

        router = MockRouter([
            '{"refusal": false, "claims": [{"text": "' + SAMPLE_EXCERPT + '", "evidence_ids": ["ev_1"]}]}'
        ])

        # Paraphrase using different vocabulary: "fluid barrier" instead of "semipermeable membrane"
        req = CanonicalQARequest(
            question="How do fluid barriers facilitate molecular movement?",
            source_id=SOURCE_ID,
            source_version=VERSION,
            topic_id=TOPIC,
            subtopic_id=SUBTOPIC,
            concept_ids=CONCEPTS,
        )

        with patch("app.services.qa.canonical_answer.get_reasoning_router", return_value=router):
            resp = generate_canonical_answer(req, repo, retrieval)
            assert resp.refusal is False
            assert router.call_count == 1
            assert len(resp.citations) > 0

    def test_early_qa_cache_avoids_retrieval(self):
        repo = Mock(spec=KnowledgeRepository)
        repo.user = Mock(user_id=USER_A)
        retrieval = Mock(spec=RetrievalService)
        bundle = make_bundle()
        retrieval.retrieve.return_value = bundle

        router = MockRouter([
            '{"refusal": false, "claims": [{"text": "' + SAMPLE_EXCERPT + '", "evidence_ids": ["ev_1"]}]}'
        ])

        req = CanonicalQARequest(
            question="What is osmosis?",
            source_id=SOURCE_ID,
            source_version=VERSION,
            topic_id=TOPIC,
            subtopic_id=SUBTOPIC,
            concept_ids=CONCEPTS,
        )

        with patch("app.services.qa.canonical_answer.get_reasoning_router", return_value=router):
            # First call populates cache
            resp1 = generate_canonical_answer(req, repo, retrieval)
            assert resp1.refusal is False
            assert retrieval.retrieve.call_count == 1
            assert router.call_count == 1

            # Second call MUST hit early cache and bypass retrieval & router completely
            resp2 = generate_canonical_answer(req, repo, retrieval)
            assert resp2.answer == resp1.answer
            assert resp2.diagnostics.stage == "canonical_qa_cache_hit"
            # Crucial: retrieval and router calls did NOT increment
            assert retrieval.retrieve.call_count == 1
            assert router.call_count == 1

    def test_qa_cache_user_and_version_isolation(self):
        repo_a = Mock(spec=KnowledgeRepository)
        repo_a.user = Mock(user_id=USER_A)
        repo_b = Mock(spec=KnowledgeRepository)
        repo_b.user = Mock(user_id=USER_B)

        retrieval = Mock(spec=RetrievalService)
        retrieval.retrieve.side_effect = lambda ctx, req: make_bundle(user_id=ctx.user.user_id, version=req.source_version)

        router = MockRouter([
            '{"refusal": false, "claims": [{"text": "' + SAMPLE_EXCERPT + '", "evidence_ids": ["ev_1"]}]}',
            '{"refusal": false, "claims": [{"text": "' + SAMPLE_EXCERPT + '", "evidence_ids": ["ev_1"]}]}',
            '{"refusal": false, "claims": [{"text": "' + SAMPLE_EXCERPT + '", "evidence_ids": ["ev_1"]}]}',
        ])

        with patch("app.services.qa.canonical_answer.get_reasoning_router", return_value=router):
            req_a = CanonicalQARequest(
                question="What is osmosis?",
                source_id=SOURCE_ID,
                source_version=VERSION,
                topic_id=TOPIC,
                subtopic_id=SUBTOPIC,
                concept_ids=CONCEPTS,
            )
            resp_a = generate_canonical_answer(req_a, repo_a, retrieval)
            assert retrieval.retrieve.call_count == 1

            # Different user MUST NOT hit User A's cache
            resp_b = generate_canonical_answer(req_a, repo_b, retrieval)
            assert retrieval.retrieve.call_count == 2

            # Different source version MUST NOT hit Version 1 cache
            req_v2 = req_a.model_copy(update={"source_version": 2})
            resp_v2 = generate_canonical_answer(req_v2, repo_a, retrieval)
            assert retrieval.retrieve.call_count == 3

    def test_empty_retrieval_fast_refusal(self):
        repo = Mock(spec=KnowledgeRepository)
        repo.user = Mock(user_id=USER_A)
        retrieval = Mock(spec=RetrievalService)
        # Empty evidence bundle: no retrieved items
        bundle = make_bundle(items=[])
        retrieval.retrieve.return_value = bundle

        router = MockRouter([])  # Empty router: must NOT be called

        req = CanonicalQARequest(
            question="According to the document, what is the spark plug torque specification?",
            source_id=SOURCE_ID,
            source_version=VERSION,
            topic_id=TOPIC,
            subtopic_id=SUBTOPIC,
            concept_ids=CONCEPTS,
            allow_ai_supplemental=False,
        )

        with patch("app.services.qa.canonical_answer.get_reasoning_router", return_value=router):
            resp = generate_canonical_answer(req, repo, retrieval)
            assert resp.refusal is True
            assert resp.refusal_reason == "SOURCE_UNAVAILABLE"
            assert resp.evidence_status == "INSUFFICIENT"
            # Router must NOT have been called on empty retrieval!
            assert router.call_count == 0

    def test_unsupported_fact_honest_model_refusal(self):
        repo = Mock(spec=KnowledgeRepository)
        repo.user = Mock(user_id=USER_A)
        retrieval = Mock(spec=RetrievalService)
        bundle = make_bundle()
        retrieval.retrieve.return_value = bundle

        # Router honestly returns refusal
        router = MockRouter(['{"refusal": true, "claims": []}'])

        req = CanonicalQARequest(
            question="According to the document, what is the spark plug torque specification?",
            source_id=SOURCE_ID,
            source_version=VERSION,
            topic_id=TOPIC,
            subtopic_id=SUBTOPIC,
            concept_ids=CONCEPTS,
            allow_ai_supplemental=False,
        )

        with patch("app.services.qa.canonical_answer.get_reasoning_router", return_value=router):
            resp = generate_canonical_answer(req, repo, retrieval)
            assert resp.refusal is True
            assert resp.evidence_status == "INSUFFICIENT"
            assert router.call_count == 1
            assert "couldn't find enough evidence" in resp.answer

    def test_durable_job_store_restart_recovery(self, tmp_path):
        db_path = str(tmp_path / "test_jobs.sqlite3")
        store = DurableJobStore(db_path=db_path)

        job1 = PipelineJob(
            job_id="job_1",
            job_type="notes_generation",
            status="completed",
            current_stage="COMPLETED",
            progress_percent=100,
            is_finished=True,
            metadata={"user_id": "user_1"},
        )
        job2 = PipelineJob(
            job_id="job_2",
            job_type="video_rendering",
            status="running",
            current_stage="RENDERING",
            progress_percent=45,
            is_finished=False,
            metadata={"user_id": "user_1"},
        )

        # Save jobs
        store.save_job(job1)
        store.save_job(job2)

        # Simulate server restart by creating a new Store instance on the same SQLite file
        new_store = DurableJobStore(db_path=db_path)
        interrupted = new_store.recover_interrupted_jobs()

        assert len(interrupted) == 1
        assert interrupted[0].job_id == "job_2"
        assert interrupted[0].status == "failed"
        assert "Server restarted" in interrupted[0].error

        # Check job1 was untouched
        loaded_job1 = new_store.load_job("job_1")
        assert loaded_job1 is not None
        assert loaded_job1.status == "completed"
