import time
from app.services.mastery.reassessment_service import ReassessmentService
from app.services.mastery import (
    InMemoryMasteryRepository,
    InMemoryQuestionRegistry,
    MasteryRecord,
    MasteryState,
    AdaptiveLearningService,
    InMemoryAssessmentAttemptRepository,
    InMemoryRemediationJobRepository,
    MasteryStateMachine,
)
from app.services.schemas import ConceptNode

print("--- Testing Real Local Ollama llama3.2:3b Performance ---")
concept = ConceptNode(
    concept_id="CONCEPT_PERF",
    name="Linear Transformations",
    definition="A mapping between vector spaces that preserves vector addition and scalar multiplication.",
    prerequisite_concept_ids=[],
    source_content_ids=["cu_001"],
)
chunks = [{
    "chunk_id": "ch_perf_01",
    "text": "A linear transformation T: V -> W is a mapping between vector spaces that preserves the operations of vector addition and scalar multiplication. In matrix form, T(x) = Ax where A is the transformation matrix.",
    "page_start": 1,
    "page_end": 1,
    "source_id": "SRC_PERF",
}]

m_repo = InMemoryMasteryRepository()
q_reg = InMemoryQuestionRegistry()
m = MasteryRecord(
    user_id="student_real",
    source_id="SRC_PERF",
    concept_id="CONCEPT_PERF",
    attempt_count=1,
    incorrect_count=1,
    mastery_state=MasteryState.REASSESSING,
    remediation_attempt_count=1,
)
m_repo.save(m)

svc = ReassessmentService(mastery_repo=m_repo, question_registry=q_reg)

t0 = time.monotonic()
questions = svc.generate_reassessment_batch(
    user_id="student_real",
    source_id="SRC_PERF",
    concept_id="CONCEPT_PERF",
    target_count=2,
    provided_concept=concept,
    provided_chunks=chunks,
)
duration_ms = (time.monotonic() - t0) * 1000
print(f"REAL_OLLAMA_BATCH_MS: {duration_ms:.1f}ms")
print(f"QUESTIONS_GENERATED: {len(questions)}")
for i, q in enumerate(questions):
    print(f"  Q{i+1}: {q.stem[:60]}... ({len(q.options)} options, variant={getattr(q, 'variant_type', None)})")
    for opt in q.options:
        print(f"     [{opt.index}] {opt.text}")

# Benchmark prefetched retrieval
app_svc = AdaptiveLearningService(
    mastery_repo=m_repo,
    attempt_repo=InMemoryAssessmentAttemptRepository(),
    question_registry=q_reg,
    remediation_repo=InMemoryRemediationJobRepository(),
    state_machine=MasteryStateMachine(),
)
auth_q1 = q_reg.get(questions[0].question_id)
auth_q2 = q_reg.get(questions[1].question_id)
app_svc.reassessment_queue.register_batch(
    user_id="student_real",
    source_id="SRC_PERF",
    concept_id="CONCEPT_PERF",
    cycle=1,
    questions=[auth_q1, auth_q2],
)

t_retr0 = time.monotonic()
sess = app_svc.reassessment_queue.get_session("student_real", "SRC_PERF", "CONCEPT_PERF")
retrieved_q, q_num, total_q = sess.get_current_tuple()
retrieval_ms = (time.monotonic() - t_retr0) * 1000
print(f"PREFETCHED_RETRIEVAL_MS: {retrieval_ms:.3f}ms")
print(f"RETRIEVED_Q: {retrieved_q.question_id} (Q{q_num} of {total_q})")
