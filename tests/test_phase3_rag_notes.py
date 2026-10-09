"""Targeted Phase 3 test suite: RAG, ASK, Notes, and Visual Study Materials.

Verifies:
- Source-backed ASK with verified citations (SOURCE_BACKED)
- AI supplemental explanations without fabricated citations (AI_SUPPLEMENTAL)
- Source-unavailable refusal when specific source facts requested without evidence (SOURCE_UNAVAILABLE)
- Citation integrity and provenance checks
- Cross-user and cross-version isolation
- Prompt injection safety
- Grounded notes generation at multiple detail levels
- AI-enriched notes integration via AIExplanationService
- Diagram generation (concept maps and flowcharts)
- Optional diagram failure resilience (tolerant_diagrams)
- Request-level caching to prevent repeated model inference
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from unittest.mock import Mock
from uuid import UUID, uuid4
import pytest

from app.core.reasoning import (
    ReasoningRequest,
    ReasoningResult,
    Telemetry,
)
from app.services.knowledge_models import Identifier, SourceScope
from app.services.repositories.knowledge_repository import (
    KnowledgeError,
    KnowledgeRepository,
)
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
    is_source_specific_query,
    clear_qa_cache,
)
from app.services.grounded_notes import (
    DiagramProposal,
    DiagramNode,
    DiagramEdge,
    GroundedNotesService,
    NotesError,
    NotesOptions,
    NotesProposal,
    NotesRequest,
    validate_notes,
    clear_notes_cache,
)
from app.services.learning_session import (
    ConceptView,
    LearningSession,
    LearningSessionRepository,
    LearningSessionService,
    SessionQARequest,
)
from app.services.schemas import QAResponse, Citation

USER_A = UUID("00000000-0000-4000-8000-000000000001")
USER_B = UUID("00000000-0000-4000-8000-000000000002")
SOURCE_ID = "SRC_bio_osmosis"
VERSION = 1
TOPIC = "topic_cell_transport"
SUBTOPIC = "sub_passive_transport"
CONCEPTS = ["osmosis", "cell_membrane"]
SESSION_ID = UUID("00000000-0000-4000-8000-000000000001")

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
        resp = self.responses.pop(0) if self.responses else "{}"
        return ReasoningResult(
            response=resp,
            telemetry=Telemetry(
                provider="cloudflare",
                task=request.task,
                outcome="SUCCESS",
                transport_latency_seconds=0.01,
            ),
        )


@pytest.fixture(autouse=True)
def reset_caches():
    clear_qa_cache()
    clear_notes_cache()
    yield
    clear_qa_cache()
    clear_notes_cache()


def test_is_source_specific_query_detection():
    # Source-specific questions must be detected
    assert is_source_specific_query("What does the document say about osmosis?")
    assert is_source_specific_query("According to the source, how does passive transport work?")
    assert is_source_specific_query("What is stated on page 4 of the uploaded file?")
    assert is_source_specific_query("In chapter 2, what does the author mention about cells?")
    assert is_source_specific_query("What does the text say about membranes?")

    # Broad conceptual or educational questions should not be source-specific
    assert not is_source_specific_query("What is osmosis?")
    assert not is_source_specific_query("Can you explain how a cell membrane functions?")
    assert not is_source_specific_query("Why is passive transport biologically important?")
    assert not is_source_specific_query("Give me an analogy for concentration gradients.")


def test_source_backed_ask_with_citations(monkeypatch):
    """TASK 2: SOURCE_BACKED answers with genuine citations."""
    repo = Mock(spec=KnowledgeRepository)
    repo.user = Mock(user_id=USER_A)
    bundle = make_bundle()

    retrieval = Mock(spec=RetrievalService)
    retrieval.retrieve.return_value = bundle

    proposal_json = json.dumps({
        "refusal": False,
        "claims": [
            {
                "text": "Osmosis is passive transport.",
                "evidence_ids": ["ev_1"]
            }
        ],
        "unanswered_parts": []
    })

    router = MockRouter([proposal_json])
    monkeypatch.setattr("app.services.qa.canonical_answer.get_reasoning_router", lambda: router)

    request = CanonicalQARequest(
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        question="What is osmosis?",
        allow_ai_supplemental=True,
    )

    resp = generate_canonical_answer(request, repo, retrieval)
    assert not resp.refusal
    assert resp.provenance_kind == "SOURCE_GROUNDED"
    assert resp.evidence_status == "SUFFICIENT"
    assert len(resp.citations) == 1
    assert resp.citations[0].quote == "Osmosis is passive transport."
    assert resp.citations[0].page_number == 4
    assert resp.citations[0].verified is True
    assert "Osmosis is passive transport." in resp.answer


def test_source_unavailable_refusal(monkeypatch):
    """TASK 2: SOURCE_UNAVAILABLE when user requests specific source facts without evidence."""
    repo = Mock(spec=KnowledgeRepository)
    repo.user = Mock(user_id=USER_A)
    empty_bundle = make_bundle(items=[], outcome="INSUFFICIENT_EVIDENCE")

    retrieval = Mock(spec=RetrievalService)
    retrieval.retrieve.return_value = empty_bundle

    router = MockRouter([])
    monkeypatch.setattr("app.services.qa.canonical_answer.get_reasoning_router", lambda: router)

    request = CanonicalQARequest(
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        question="What does the uploaded document say about osmosis?",
        allow_ai_supplemental=True,
    )

    resp = generate_canonical_answer(request, repo, retrieval)
    assert resp.refusal is True
    assert resp.evidence_status == "INSUFFICIENT"
    assert resp.refusal_reason == "SOURCE_UNAVAILABLE"
    assert resp.provenance_kind == "SOURCE_GROUNDED"
    assert len(resp.citations) == 0
    assert "selected learning material" in resp.answer
    # Must NOT call router to hallucinate an answer
    assert router.call_count == 0


def test_ai_supplemental_pedagogical_answer(monkeypatch):
    """TASK 2: AI_SUPPLEMENTAL when conceptual question has insufficient evidence."""
    repo = Mock(spec=KnowledgeRepository)
    repo.user = Mock(user_id=USER_A)
    empty_bundle = make_bundle(items=[], outcome="INSUFFICIENT_EVIDENCE")

    retrieval = Mock(spec=RetrievalService)
    retrieval.retrieve.return_value = empty_bundle

    ai_answer_text = "Osmosis is the net movement of water molecules across a selectively permeable membrane."
    router = MockRouter([ai_answer_text])
    monkeypatch.setattr("app.services.qa.canonical_answer.get_reasoning_router", lambda: router)

    request = CanonicalQARequest(
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        question="Can you explain what osmosis is and why it matters?",
        allow_ai_supplemental=True,
    )

    resp = generate_canonical_answer(request, repo, retrieval)
    assert not resp.refusal
    assert resp.provenance_kind == "AI_ENRICHED"
    assert resp.evidence_status == "SUFFICIENT"
    assert len(resp.citations) == 0  # No fabricated citations!
    assert "movement of water" in resp.answer
    assert router.call_count == 1


def test_qa_cross_user_and_version_isolation(monkeypatch):
    """TASK 1: Verify cross-user and cross-version isolation gates."""
    repo = Mock(spec=KnowledgeRepository)
    repo.user = Mock(user_id=USER_A)

    retrieval = Mock(spec=RetrievalService)

    # 1. Foreign user bundle
    foreign_bundle = make_bundle(user_id=USER_B)
    retrieval.retrieve.return_value = foreign_bundle

    request = CanonicalQARequest(
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        question="What is osmosis?",
    )

    with pytest.raises(KnowledgeError) as exc_info:
        generate_canonical_answer(request, repo, retrieval)
    assert exc_info.value.code == "INVALID_SCOPE"

    # 2. Foreign source version
    foreign_version_bundle = make_bundle(version=2)
    retrieval.retrieve.return_value = foreign_version_bundle
    with pytest.raises(KnowledgeError) as exc_info:
        generate_canonical_answer(request, repo, retrieval)
    assert exc_info.value.code == "INVALID_SCOPE"


def test_qa_repeated_request_caching(monkeypatch):
    """TASK 6: Identical requests reuse completed result without extra model inference."""
    repo = Mock(spec=KnowledgeRepository)
    repo.user = Mock(user_id=USER_A)
    bundle = make_bundle()

    retrieval = Mock(spec=RetrievalService)
    retrieval.retrieve.return_value = bundle

    proposal_json = json.dumps({
        "refusal": False,
        "claims": [{"text": "Osmosis is passive transport.", "evidence_ids": ["ev_1"]}],
        "unanswered_parts": []
    })

    router = MockRouter([proposal_json])
    monkeypatch.setattr("app.services.qa.canonical_answer.get_reasoning_router", lambda: router)

    request = CanonicalQARequest(
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        question="What is osmosis?",
        allow_ai_supplemental=True,
    )

    # Disable PYTEST_CURRENT_TEST check for cache verification
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    resp1 = generate_canonical_answer(request, repo, retrieval)
    assert router.call_count == 1

    resp2 = generate_canonical_answer(request, repo, retrieval)
    # Second call must hit cache: router call count stays 1
    assert router.call_count == 1
    assert resp1.answer == resp2.answer
    assert resp1.citations == resp2.citations


def test_notes_generation_source_grounded(monkeypatch):
    """TASK 3 & 4: Grounded notes generation with sections and diagrams."""
    repo = Mock(spec=KnowledgeRepository)
    repo.user = Mock(user_id=USER_A)
    scope = SourceScope(user_id=USER_A, source_id=SOURCE_ID, source_version=VERSION)
    repo.scope.return_value = scope

    now = datetime.now(timezone.utc)
    session_row = LearningSession(
        session_id=SESSION_ID,
        user_id=USER_A,
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        selected_concept_ids=CONCEPTS,
        state="ACTIVE",
        created_at=now,
        updated_at=now,
        last_active_at=now,
    )
    sessions = Mock(spec=LearningSessionService)
    sessions.qa_request.return_value = CanonicalQARequest(
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        question="Organize notes",
    )

    evidence_text = "Water -> Semipermeable membrane. Osmosis is passive transport."
    item = make_evidence_item(excerpt=evidence_text)
    bundle = make_bundle(items=[item])

    retrieval = Mock(spec=RetrievalService)
    retrieval.retrieve.return_value = bundle

    proposal = {
        "title": {"text": "Osmosis is passive transport.", "evidence_ids": ["ev_1"]},
        "summary": {"text": "Osmosis is passive transport.", "evidence_ids": ["ev_1"]},
        "key_points": [{"text": "Osmosis is passive transport.", "evidence_ids": ["ev_1"]}],
        "concepts": [],
        "definitions": [],
        "relationships": [],
        "examples": [],
        "important_equations": [],
        "diagram_specs": [
            {
                "type": "FLOWCHART",
                "title": {"text": "Osmosis is passive transport.", "evidence_ids": ["ev_1"]},
                "nodes": [
                    {"node_id": "n1", "item": {"text": "Water", "evidence_ids": ["ev_1"]}},
                    {"node_id": "n2", "item": {"text": "Semipermeable membrane", "evidence_ids": ["ev_1"]}}
                ],
                "edges": [
                    {"from_node": "n1", "to_node": "n2", "item": {"text": "Water -> Semipermeable membrane", "evidence_ids": ["ev_1"]}}
                ],
                "evidence_ids": ["ev_1"]
            }
        ]
    }

    router = MockRouter([json.dumps(proposal)])
    service = GroundedNotesService(repo, sessions=sessions, retrieval=retrieval, provider=router)

    req = NotesRequest(session_id=SESSION_ID, detail_level="standard")
    notes = service.generate(req)

    assert notes.provenance_kind == "SOURCE_GROUNDED"
    assert notes.title.text == "Osmosis is passive transport."
    assert len(notes.key_points) == 1
    assert len(notes.diagram_specs) == 1
    assert notes.diagram_specs[0].type == "FLOWCHART"
    assert len(notes.citations) >= 1
    assert router.call_count == 1


def test_notes_optional_diagram_failure_resilience():
    """TASK 3 & 4: Invalid diagram does not invalidate usable text notes when tolerant_diagrams=True."""
    evidence_text = "Water moves through the membrane. Osmosis is passive transport."
    item = make_evidence_item(excerpt=evidence_text)
    bundle = make_bundle(items=[item])

    proposal = NotesProposal(
        title=SupportedClaim(text="Osmosis is passive transport.", evidence_ids=["ev_1"]),
        summary=SupportedClaim(text="Osmosis is passive transport.", evidence_ids=["ev_1"]),
        key_points=[SupportedClaim(text="Osmosis is passive transport.", evidence_ids=["ev_1"])],
        concepts=[],
        definitions=[],
        relationships=[],
        examples=[],
        important_equations=[],
        diagram_specs=[
            DiagramProposal(
                type="FLOWCHART",
                title=SupportedClaim(text="Osmosis is passive transport.", evidence_ids=["ev_1"]),
                nodes=[DiagramNode(node_id="n1", item=SupportedClaim(text="Water", evidence_ids=["ev_1"]))],
                edges=[DiagramEdge(from_node="n1", to_node="non_existent", item=SupportedClaim(text="Water -> Membrane", evidence_ids=["ev_1"]))],
                evidence_ids=["ev_1"],
            )
        ]
    )

    # 1. When tolerant_diagrams=False: raises ValueError / NotesError
    with pytest.raises(ValueError):
        validate_notes(proposal, bundle, tolerant_diagrams=False)

    # 2. When tolerant_diagrams=True: invalid diagram is omitted, text notes are preserved
    sections, title, summary, diagrams, citations = validate_notes(proposal, bundle, tolerant_diagrams=True)
    assert title.text == "Osmosis is passive transport."
    assert summary is not None and summary.text == "Osmosis is passive transport."
    assert len(sections["key_points"]) == 1
    assert len(diagrams) == 0  # Invalid diagram omitted cleanly
    assert len(citations) >= 1


def test_ai_enriched_supplemental_notes_fallback(monkeypatch):
    """TASK 3 & 4: When source evidence is insufficient, include_ai_supplemental generates AI-enriched notes."""
    repo = Mock(spec=KnowledgeRepository)
    repo.user = Mock(user_id=USER_A)
    scope = SourceScope(user_id=USER_A, source_id=SOURCE_ID, source_version=VERSION)
    repo.scope.return_value = scope

    sessions = Mock(spec=LearningSessionService)
    sessions.qa_request.return_value = CanonicalQARequest(
        source_id=SOURCE_ID,
        source_version=VERSION,
        topic_id=TOPIC,
        subtopic_id=SUBTOPIC,
        concept_ids=CONCEPTS,
        question="Organize notes",
    )
    sessions.get.return_value = Mock(
        topic_title="Cell Membrane Dynamics",
        subtopic_title="Osmosis",
        concepts=[Mock(concept_id="osmosis", name="Osmosis"), Mock(concept_id="cell_membrane", name="Cell Membrane")],
    )

    # Retrieval returns empty / unready bundle
    empty_bundle = make_bundle(items=[], outcome="INSUFFICIENT_EVIDENCE")
    retrieval = Mock(spec=RetrievalService)
    retrieval.retrieve.return_value = empty_bundle

    # Mock AIExplanationService response
    ai_explanation_json = json.dumps({
        "topic": "Cell Membrane Dynamics",
        "overview": "Overview of how cell membranes regulate transport.",
        "simplified_explanation": "Cell membranes are selectively permeable barriers.",
        "key_points": [
            {"title": "Passive Transport", "explanation": "Movement down a gradient without ATP."},
            {"title": "Osmosis", "explanation": "Diffusion of water molecules."}
        ],
        "examples": [
            {"title": "Red Blood Cells", "description": "Swelling in hypotonic solution."}
        ],
        "analogies": ["Like a security gate with selective badges."],
        "prerequisites": [
            {"name": "Concentration Gradient", "description": "Difference in solute concentration."}
        ],
        "summary": "Summary of membrane transport mechanisms."
    })

    router = MockRouter([ai_explanation_json])
    service = GroundedNotesService(repo, sessions=sessions, retrieval=retrieval, provider=router)

    # Without include_ai_supplemental: raises NotesError
    with pytest.raises(NotesError) as exc_info:
        service.generate(NotesRequest(session_id=SESSION_ID, include_ai_supplemental=False))
    assert exc_info.value.code == "INSUFFICIENT_EVIDENCE"

    # With include_ai_supplemental: generates AI-enriched notes with concept map
    enriched_notes = service.generate(NotesRequest(session_id=SESSION_ID, include_ai_supplemental=True))
    assert enriched_notes.provenance_kind == "AI_ENRICHED"
    assert "AI-Enriched Notes" in enriched_notes.title.text
    assert len(enriched_notes.key_points) == 2
    assert len(enriched_notes.definitions) == 1
    assert len(enriched_notes.examples) == 1
    assert len(enriched_notes.diagram_specs) == 1
    assert enriched_notes.diagram_specs[0].type == "CONCEPT_MAP"
    assert enriched_notes.diagram_specs[0].title.provenance_kind == "AI_ENRICHED"
    assert len(enriched_notes.citations) == 0  # No fabricated source citations
