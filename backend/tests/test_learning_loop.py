import io
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from PIL import Image
import pymupdf
from modules.learning.schemas import LearningSessionKnowledge, Source, SourceChunk
from modules.learning.knowledge import enrich, build_topic
from modules.ingestion.service import ingest
from modules.rag.store import KnowledgeStore
from modules.learning.tutor import answer_session
from modules.learning.assessment import generate, submit, mastery_status, public_assessment
from modules.roadmap.service import roadmap, gaps
from modules.llm.provider import ProviderError, classify, provider_scope, ProviderClient

TEXT = """Inertia is the tendency of an object to resist changes in its state of motion.
Force changes the motion of an object when the forces acting on it are unbalanced.
Acceleration describes the rate at which an object's velocity changes with time.
Mass measures the inertia of an object and is measured in kilograms.
Momentum is the product of the mass of an object and its velocity.
Friction opposes relative sliding motion between surfaces in contact.
Work transfers energy when a force produces displacement of an object.
Kinetic energy is energy associated with the motion of an object."""


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("AICARLS_DB", str(tmp_path / "learning.db"))
    monkeypatch.setenv("EXPENSIVE_REQUESTS_PER_MINUTE", "1000")
    from modules.config import PATHS
    monkeypatch.setitem(PATHS, "root", tmp_path)
    return KnowledgeStore()


def knowledge(store, text=TEXT):
    k = LearningSessionKnowledge(topic="Newton's laws", input_mode="txt")
    m, s, chunks = ingest(text.encode(), "lesson.txt", "text/plain", k.session_id)
    k.materials, k.sources, k.source_chunks = [m], [s], chunks
    return store.save(enrich(k))


def test_txt_persistence_and_fts_isolation(store):
    a = knowledge(store)
    b = knowledge(store, "Photosynthesis converts sunlight into chemical energy in green plants and algae.")
    reopened = KnowledgeStore(store.path)
    assert reopened.load(a.session_id).materials[0]["filename"] == "lesson.txt"
    hits = reopened.retrieve(a.session_id, "inertia")
    assert hits and all("Photosynthesis" not in h["text"] for h in hits)
    assert not reopened.retrieve(b.session_id, "inertia")
    assert hits[0]["line_start"] == 1 and hits[0]["source_type"] == "uploaded"


def test_pdf_ingestion_preserves_actual_pages(store):
    k = LearningSessionKnowledge(topic="PDF")
    doc = pymupdf.open()
    for line in ("Work transfers energy when force produces displacement.", "Kinetic energy is associated with motion."):
        doc.new_page().insert_text((30, 40), line)
    m, source, chunks = ingest(doc.tobytes(), "../../physics.pdf", "application/pdf", k.session_id)
    assert m["filename"] == "physics.pdf"
    assert [c.page for c in chunks] == [1, 2]
    assert all(c.source_id == source.source_id for c in chunks)


def test_image_mock_and_honest_uncertainty(store):
    data = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(data, format="PNG")
    client = Mock()
    client.extract_image.return_value = {"raw_text": TEXT, "clean_text": TEXT,
        "equations": ["F = ma"], "detected_concepts": ["force"], "uncertain_content": ["Subscript unclear"],
        "confidence": "low"}
    m, source, chunks = ingest(data.getvalue(), "note.png", "image/png", "a"*32, client)
    assert m["extraction"]["confidence"] == "low" and m["warnings"]
    assert source.trust_label == "uncertain_extraction" and chunks
    client.extract_image.side_effect = ProviderError("authentication", "gemini")
    with pytest.raises(ProviderError):
        ingest(data.getvalue(), "note.png", "image/png", "b"*32, client)


@pytest.mark.parametrize("name,mime,data", [
    ("bad.exe", "application/octet-stream", b"MZx"),
    ("bad.pdf", "application/pdf", b"not a pdf"),
    ("bad.txt", "image/png", TEXT.encode()),
    ("bad.txt", "text/plain", b"MZnottext"),
    ("bad.txt", "text/plain", b"hello\x00world"),
])
def test_upload_validation(store, name, mime, data):
    with pytest.raises(ValueError):
        ingest(data, name, mime, "a"*32)


def test_upload_limit_and_session_path(store, monkeypatch):
    import modules.ingestion.service as ingestion
    monkeypatch.setattr(ingestion, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(ValueError):
        ingest(TEXT.encode(), "x.txt", "text/plain", "a"*32)
    with pytest.raises(ValueError):
        ingest(b"text", "x.txt", "text/plain", "../outside")


def test_document_to_cited_rag_integration(store):
    k = knowledge(store)
    chunk = store.retrieve(k.session_id, "inertia")[0]
    client = Mock()
    client.chat.return_value = "Inertia resists a change in motion. [" + chunk["chunk_id"] + "]"
    answer = answer_session(k.session_id, "inertia", store=store, client=client)
    assert answer["grounded"] and answer["sources"][0]["source_id"] == k.sources[0].source_id
    assert k.source_chunks[0].text in client.chat.call_args.args[1][0]["content"]
    client.chat.return_value = "Invented claim [999]"
    with pytest.raises(ValueError):
        answer_session(k.session_id, "inertia", store=store, client=client)
    assert not answer_session(k.session_id, "unfindablequux", store=store, client=client)["sources"]


def test_provider_failure_returns_labeled_excerpt(store):
    k = knowledge(store)
    client = Mock()
    client.chat.side_effect = ProviderError("quota", "gemini")
    answer = answer_session(k.session_id, "force", store=store, client=client)
    assert answer["fallback_used"] and answer["confidence"] == "source_excerpts"


def test_original_evidence_preferred(store):
    k = knowledge(store)
    source = Source(title="Narration", source_type="generated", externally_grounded=False)
    k.sources.append(source)
    k.source_chunks.append(SourceChunk(source_id=source.source_id, text="inertia " * 100, source_type="generated"))
    store.save(k)
    assert store.retrieve(k.session_id, "inertia")[0]["source_type"] == "uploaded"


def test_topic_to_assessment_gaps_roadmap_integration(store, monkeypatch):
    from modules.learning.sources import TrustedTopicSource
    from modules.ingestion.service import chunk_text
    source = Source(title="Public fixture", source_type="trusted_topic", url="https://en.wikipedia.org/wiki/Test")
    monkeypatch.setattr(TrustedTopicSource, "obtain", lambda self, topic: ([source], chunk_text(TEXT, source)))
    k, _ = build_topic("Newton's laws", allow_generated=False, store=store)
    assert store.retrieve(k.session_id, "force")
    with pytest.raises(ValueError):
        generate(k.session_id, store=store)
    with pytest.raises(ValueError):
        roadmap(k.session_id, store)
    k.status = "complete"
    store.save(k)
    assessment = generate(k.session_id, store=store)
    assert len(assessment["questions"]) == 6
    assert all(q["source_ids"] for q in assessment["questions"])
    assert all("correct_answer" not in q for q in public_assessment(assessment)["questions"])
    answers = {q["question_id"]: q["correct_answer"] for q in assessment["questions"]}
    answers[assessment["questions"][0]["question_id"]] = "wrong"
    result = submit(assessment["assessment_id"], answers, store=store)
    assert result["score"] < 100 and result["concept_scores"]
    plan = roadmap(k.session_id, store)
    assert "scored" in plan["items"][0]["reason"]
    assert gaps(k.session_id, store)["assessed"]
    # Retest updates only concepts measured by the retest.
    target = assessment["questions"][0]["concept_ids"][0]
    retest = generate(k.session_id, target, store)
    assert len(retest["questions"]) == 3
    submit(retest["assessment_id"], {q["question_id"]: q["correct_answer"] for q in retest["questions"]}, store)
    assert next(m for m in gaps(k.session_id, store)["concept_mastery"] if m["concept_id"] == target)["score"] == 100


def test_generated_topic_has_no_external_citation(store, monkeypatch):
    from modules.learning.sources import TrustedTopicSource, GeneratedLessonSource
    from modules.ingestion.service import chunk_text
    monkeypatch.setattr(TrustedTopicSource, "obtain", Mock(side_effect=ValueError("offline")))
    source = Source(title="Generated", source_type="generated", externally_grounded=False, trust_label="generated")
    monkeypatch.setattr(GeneratedLessonSource, "obtain", lambda self, topic: ([source], chunk_text(TEXT, source)))
    k, warnings = build_topic("arbitrary topic", store=store)
    assert warnings and not k.sources[0].externally_grounded and k.sources[0].url is None


@pytest.mark.parametrize("score,status", [(0,"knowledge_gap"),(59,"knowledge_gap"),(60,"developing"),
                                         (79,"developing"),(80,"mastered"),(100,"mastered")])
def test_thresholds(score,status):
    assert mastery_status(score) == status


def test_descriptive_evaluator_injection(store):
    k = knowledge(store)
    k.status = "complete"
    store.save(k)
    a = generate(k.session_id, store=store)
    evaluator = Mock(return_value={"score": 50, "feedback": "partially_correct", "missing_points": ["inertia"]})
    result = submit(a["assessment_id"], {}, store, evaluator)
    evaluator.assert_called_once()
    assert result["feedback"][-1]["missing_points"] == ["inertia"]


@pytest.mark.parametrize("code,kind", [(401,"authentication"),(403,"authorization"),(429,"quota"),(404,"invalid_model")])
def test_provider_classification(code, kind):
    exc = RuntimeError()
    exc.code = code
    assert classify(exc, "gemini").kind == kind


def test_request_credentials_are_isolated(monkeypatch):
    from modules import config
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "")
    def obtain(key):
        with provider_scope(gemini_key=key):
            return ProviderClient().gemini_key
    with ThreadPoolExecutor() as pool:
        assert list(pool.map(obtain, ["one", "two"])) == ["one", "two"]
    assert ProviderClient().gemini_key is None


def test_pipeline_failure_is_persisted(store, monkeypatch):
    from modules.learning import pipeline
    k = knowledge(store)
    monkeypatch.setattr(pipeline, "build_storyboard", Mock(side_effect=ProviderError("authentication", "gemini")))
    received = []
    assert pipeline.run_lesson(k.session_id, received.append, store=store) is None
    assert received[-1]["stage"] == "error" and received[-1]["failed_stage"] == "planning"
    assert store.get("provenance", k.session_id)["outcome"] == "FAILED"
    assert store.load(k.session_id).status == "failed"


def test_api_upload_assessment_gate(store):
    import api
    with TestClient(api.app) as client:
        response = client.post("/api/materials/upload", files={"file": ("lesson.txt", TEXT.encode(), "text/plain")})
        assert response.status_code == 200
        sid = response.json()["session_id"]
        assert client.get(f"/api/learning/{sid}").json()["source_chunks"]
        assert client.post("/api/assessment/generate", json={"session_id": sid}).status_code == 422
        assert client.post("/api/materials/upload", files={"file": ("bad.exe", b"MZ", "text/plain")}).status_code == 422


def test_local_api_closed_loop_and_reopened_persistence(store, monkeypatch):
    import api
    monkeypatch.setattr(ProviderClient, "chat", lambda self, *args, **kwargs:
                        "Inertia resists changes in motion. [" + chunk_id + "]")
    with TestClient(api.app) as client:
        response = client.post("/api/learning/sessions", json={
            "topic": "Motion", "input_mode": "txt", "text": TEXT})
        assert response.status_code == 200
        sid = response.json()["session_id"]
        k = store.load(sid)
        chunk_id = store.retrieve(sid, "inertia")[0]["chunk_id"]
        answer = client.post("/api/chat", json={"session_id": sid, "message": "inertia"})
        assert answer.status_code == 200
        assert answer.json()["grounded"] and answer.json()["sources"][0]["chunk_id"] == chunk_id
        # Fixture simulates the completion gate; this is not a live generated lesson.
        k.status = "complete"
        store.save(k)
        response = client.post("/api/assessment/generate", json={"session_id": sid})
        assert response.status_code == 200
        public = response.json()
        assert len(public["questions"]) == 6
        assert all("correct_answer" not in q for q in public["questions"])
        assert all(set(q["concept_ids"]) <= {c.concept_id for c in k.concepts} for q in public["questions"])
        aid = public["assessment_id"]
        assert client.get(f"/api/assessment/{aid}").json() == public
        result = client.post(f"/api/assessment/{aid}/submit", json={"answers": {}})
        assert result.status_code == 200 and result.json()["score"] == 0
        plan = result.json()["roadmap"]
        assert plan["items"] and client.get(f"/api/roadmap/{sid}").json() == plan
        assert client.get(f"/api/learning/{sid}/gaps").json()["assessed"]
        reopened = KnowledgeStore(store.path)
        assert reopened.get("roadmap", sid) == plan
        assert reopened.list("mastery", sid)
        other = knowledge(store, "Plants use sunlight for photosynthesis and chemical energy production.")
        assert not reopened.retrieve(other.session_id, "inertia")
        assert not reopened.list("mastery", other.session_id)
