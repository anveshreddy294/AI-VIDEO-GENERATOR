"""Performance and latency benchmark for reassessment batch generation with Ollama."""

import time
import pytest
from app.core.config import settings
from app.services.mastery import (
    AdaptiveLearningService,
    InMemoryAssessmentAttemptRepository,
    InMemoryMasteryRepository,
    InMemoryQuestionRegistry,
    InMemoryRemediationJobRepository,
    MasteryRecord,
    MasteryState,
    MasteryStateMachine,
)
from app.services.mastery.reassessment_service import ReassessmentService
from app.services.schemas import ConceptNode, KnowledgeGraph, SourceRecord


@pytest.mark.filterwarnings("ignore")
def test_ollama_batch_generation_and_prefetch_retrieval_performance(monkeypatch):
    """Verify ONE Ollama call generates 2 validated reassessment questions and prefetched retrieval is < 1s."""
    concept = ConceptNode(
        concept_id="CONCEPT_PERF_TEST",
        name="Linear Transformations",
        definition="Mapping between vector spaces preserving addition and scalar multiplication.",
        prerequisite_concept_ids=[],
        source_content_ids=["cu_001"],
    )
    kg = KnowledgeGraph(concepts={"CONCEPT_PERF_TEST": concept})
    rec = SourceRecord(
        source_id="SRC_PERF_TEST",
        filename="perf.pdf",
        source_type="pdf",
        mime_type="application/pdf",
        file_hash="h1",
        sha256="h1",
        file_size=100,
        uploaded_by="perf_student",
        user_id="perf_student",
        owner_user_id="perf_student",
        version=1,
        source_version="v1",
        status="READY",
    )
    monkeypatch.setattr("app.services.mastery.application_service.get_source_record", lambda sid: rec if sid == "SRC_PERF_TEST" else None)
    monkeypatch.setattr("app.services.mastery.application_service.load_knowledge_graph", lambda sid: kg if sid == "SRC_PERF_TEST" else None)
    monkeypatch.setattr("app.services.mastery.reassessment_service.load_knowledge_graph", lambda sid: kg if sid == "SRC_PERF_TEST" else None)

    chunks = [{
        "chunk_id": "ch_perf_01",
        "text": "A linear transformation T: V -> W is a mapping between vector spaces that preserves operations of vector addition and scalar multiplication. In matrix form, T(x) = Ax.",
        "page_start": 1,
        "page_end": 1,
        "source_id": "SRC_PERF_TEST",
    }]

    mastery_repo = InMemoryMasteryRepository()
    question_registry = InMemoryQuestionRegistry()
    m = MasteryRecord(
        user_id="perf_student",
        source_id="SRC_PERF_TEST",
        concept_id="CONCEPT_PERF_TEST",
        attempt_count=1,
        incorrect_count=1,
        mastery_state=MasteryState.REASSESSING,
        remediation_attempt_count=1,
    )
    mastery_repo.save(m)

    reassess_svc = ReassessmentService(
        mastery_repo=mastery_repo,
        question_registry=question_registry,
    )

    # 1. Warm call to Ollama batch generation
    t0 = time.monotonic()
    questions = reassess_svc.generate_reassessment_batch(
        user_id="perf_student",
        source_id="SRC_PERF_TEST",
        concept_id="CONCEPT_PERF_TEST",
        target_count=2,
        provided_concept=concept,
        provided_chunks=chunks,
    )
    batch_gen_duration_ms = (time.monotonic() - t0) * 1000

    print(f"\n[BENCHMARK] Reassessment batch generation (2 questions in 1 call): {batch_gen_duration_ms:.1f}ms")
    assert len(questions) == 2
    assert questions[0].question_id != questions[1].question_id
    assert len(questions[0].options) == 4
    assert len(questions[1].options) == 4

    # 2. Test prefetched retrieval via AdaptiveLearningService
    app_svc = AdaptiveLearningService(
        mastery_repo=mastery_repo,
        attempt_repo=InMemoryAssessmentAttemptRepository(),
        question_registry=question_registry,
        remediation_repo=InMemoryRemediationJobRepository(),
        state_machine=MasteryStateMachine(),
    )
    # Register batch into queue
    auth_q1 = question_registry.get(questions[0].question_id)
    auth_q2 = question_registry.get(questions[1].question_id)
    app_svc.reassessment_queue.register_batch(
        user_id="perf_student",
        source_id="SRC_PERF_TEST",
        concept_id="CONCEPT_PERF_TEST",
        cycle=1,
        questions=[auth_q1, auth_q2],
    )

    t_retrieval_0 = time.monotonic()
    retrieved_q = app_svc.generate_reassessment("perf_student", "SRC_PERF_TEST", "CONCEPT_PERF_TEST")
    retrieval_duration_ms = (time.monotonic() - t_retrieval_0) * 1000

    print(f"[BENCHMARK] Prefetched question retrieval overhead: {retrieval_duration_ms:.2f}ms")
    assert retrieved_q.question_id == auth_q1.question_id
    assert retrieval_duration_ms < 1000.0, f"Prefetched retrieval took {retrieval_duration_ms}ms, target is < 1000ms"
