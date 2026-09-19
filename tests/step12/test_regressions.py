import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.config import settings
from app.services.schemas import ContentUnit, ConceptNode, KnowledgeGraph, SourceRecord
from app.services.assessment.schemas import AssessmentSession, AssessmentOption, Question, StudentLearningProfile, StudentSubmission, AnswerSubmission


TEXT = "Gravity attracts objects with mass toward each other."


def unit(**kwargs):
    return ContentUnit(source_id="SRC_test", asset_id="ASSET_test", content_id="CU_test", modality="txt", text=TEXT, extraction_method="txt", **kwargs)


def graph():
    concept = ConceptNode(concept_id="C1", name="Gravity", definition=TEXT, source_content_ids=["CU_test"])
    return KnowledgeGraph(concepts={"C1": concept})


def chunk():
    return dict(source_id="SRC_test", asset_id="ASSET_test", chunk_id="CH1", content_ids=["CU_test"], concept_ids=["C1"], text=TEXT, layer="A", modality="txt")


def question():
    return Question(concept_id="C1", concept_name="Gravity", source_id="SRC_test", stem="What does gravity do?", options=[AssessmentOption(index=i, text=t) for i, t in enumerate(["Attracts objects with mass", "Repels all objects", "Removes mass", "Stops time"])], correct_index=0, explanation=TEXT, content_ids=["CU_test"], chunk_ids=["CH1"], evidence_quote=TEXT, evidence_text=TEXT)


def test_ollama_request_and_empty_response(monkeypatch):
    from app.services.assessment.providers import OllamaProvider
    import urllib.request
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b'{"response":"{}","done":true}'
    call = Mock(return_value=response)
    monkeypatch.setattr(urllib.request, "urlopen", call)
    assert OllamaProvider().generate_content("Return JSON") == "{}"
    payload = json.loads(call.call_args.args[0].data)
    assert payload["think"] is False and payload["format"] == "json"
    response.read.return_value = b'{"response":"","done":true}'
    with pytest.raises(RuntimeError, match="no text"):
        OllamaProvider().generate_content("Return JSON")


@pytest.mark.parametrize("concepts", [[], [dict(concept_id="C1", name="Gravity", definition=TEXT, source_content_ids=["FAKE"])], [dict(concept_id="C1", name="Gravity", definition=TEXT, source_content_ids=["CU_test"], prerequisite_concept_ids=["C1"])]])
def test_invalid_graph_rejected(concepts):
    from app.services.structurer import _assemble_outputs
    with pytest.raises(ValueError):
        _assemble_outputs({"concepts": concepts}, [unit()])


def test_structurer_does_not_truncate_or_fallback(monkeypatch):
    from app.services import structurer
    captured = []
    def fail(prompt):
        captured.append(prompt)
        raise RuntimeError("Ollama offline")
    monkeypatch.setattr(structurer, "_generate_with_llm", fail)
    content = unit()
    content.text = "x" * 500 + "IMPORTANT_TAIL"
    with pytest.raises(RuntimeError, match="Knowledge extraction failed"):
        structurer.process_structure_and_concepts([content])
    assert len(captured) == 2 and "IMPORTANT_TAIL" in captured[0]
    content.text = "x" * 60001
    with pytest.raises(ValueError, match="context limit"):
        structurer.process_structure_and_concepts([content])


def test_chunk_provenance_is_local():
    from app.services.chunker import create_rich_chunks
    first, second = unit(), unit()
    second.content_id = "CU_other"
    second.text = "Unrelated chemistry lesson."
    first.page_number, second.page_number = 1, 9
    chunks = create_rich_chunks([first, second], graph())
    assert len(chunks) == 2
    assert chunks[0].content_ids == ["CU_test"] and chunks[0].page_end == 1
    assert chunks[1].concept_ids == [] and chunks[1].page_start == 9
    assert [c.chunk_id for c in chunks] == [c.chunk_id for c in create_rich_chunks([first, second], graph())]


def test_generator_isolates_source_and_requires_context():
    from app.services.assessment.generator import search_concept_chunks, generate_question
    from app.services.assessment.providers import MockProvider
    other = {**chunk(), "source_id": "OTHER"}
    concept = graph().concepts["C1"]
    assert search_concept_chunks(concept, "SRC_test", provided_chunks=[other]) == []
    assert generate_question(concept, "SRC_test", provided_chunks=[other], llm_provider=MockProvider()) is None


@pytest.mark.parametrize("correct_index", [None, -1, 4, "0", True])
def test_bad_answer_indices_rejected(correct_index):
    from app.services.assessment.generator import generate_question
    from app.services.assessment.providers import MockProvider
    q = question()
    response = dict(question=q.stem, options=[o.model_dump() for o in q.options], correct_index=correct_index, evidence_quote=TEXT)
    assert generate_question(graph().concepts["C1"], "SRC_test", provided_chunks=[chunk()], llm_provider=MockProvider(json.dumps(response)), max_retries=0) is None


def test_unsorted_options_preserve_answer_key():
    from app.services.assessment.generator import generate_question
    from app.services.assessment.providers import MockProvider
    q = question()
    response = dict(question=q.stem, options=[q.options[i].model_dump() for i in [3, 1, 0, 2]], correct_index=0, evidence_quote=TEXT, explanation=TEXT)
    generated = generate_question(graph().concepts["C1"], "SRC_test", provided_chunks=[chunk()], llm_provider=MockProvider(json.dumps(response)), max_retries=0)
    assert generated.options[generated.correct_index].text == q.options[0].text


def test_grounding_rejects_empty_or_fabricated_evidence():
    from app.services.assessment.validator import validate_grounding
    q = question()
    assert not validate_grounding(q, "")[0]
    q.evidence_quote = "Not in the source"
    assert not validate_grounding(q, TEXT)[0]


def test_no_hash_embeddings_when_provider_missing():
    from app.db.vector_store import _embed
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        _embed([TEXT])


def test_dimension_mismatch_never_deletes_collection():
    from app.db.vector_store import ensure_collection
    client = Mock()
    client.get_collections.return_value.collections = [SimpleNamespace(name=settings.collection_name)]
    client.get_collection.return_value.config.params.vectors.size = 3
    with pytest.raises(RuntimeError, match="configure a new collection"):
        ensure_collection(client, expected_dim=5)
    client.delete_collection.assert_not_called()


def test_upsert_failure_never_switches_to_memory(monkeypatch):
    from app.db import vector_store as store
    from app.services.schemas import RichChunk
    client = Mock()
    monkeypatch.setattr(store, "get_client", lambda: client)
    monkeypatch.setattr(store, "ensure_collection", lambda *a: None)
    monkeypatch.setattr(store, "_embed", lambda texts: [[1.0, 0.0] for t in texts])
    client.upsert.side_effect = RuntimeError("disk failure")
    with pytest.raises(RuntimeError, match="disk failure"):
        store.upsert_chunks([RichChunk.model_validate(chunk())])
    assert store._client_instance is None


def test_mastery_requires_consecutive_passes():
    from app.services.assessment.engine import grade_submission
    q = question()
    session = AssessmentSession(student_id="student", source_id="SRC_test", questions=[q])
    profile = StudentLearningProfile(student_id="student", source_id="SRC_test")
    for answer in [0, 1, 0]:
        grade_submission(StudentSubmission(session_id=session.session_id, answers=[AnswerSubmission(question_id=q.question_id, selected_index=answer)]), session, graph(), profile)
    assert profile.concept_masteries["C1"].status == "LEARNING"
    grade_submission(StudentSubmission(session_id=session.session_id, answers=[AnswerSubmission(question_id=q.question_id, selected_index=0)]), session, graph(), profile)
    assert profile.concept_masteries["C1"].status == "MASTERED"


@pytest.mark.parametrize("value", ["../escape", "..\\escape", "C:drive", "CON", "", "a/b"])
def test_path_identifiers_rejected(value):
    from app.services.storage import validate_id
    with pytest.raises(ValueError):
        validate_id(value)


def test_stage_completion_is_not_job_completion():
    from app.services.pipeline_tracker import JobManager
    async def run():
        manager = JobManager()
        job = manager.create_job("test")
        await manager.emit_event(job.job_id, "extracting", "completed", "done", 20)
        assert not job.is_finished and job.status == "running"
        await manager.complete_job(job.job_id, {})
        assert job.is_finished and job.events[-1].terminal
    asyncio.run(run())


def test_forged_handoff_cannot_bypass_registry():
    from app.api.assessment import handoff_from_step1
    from app.services.assessment.schemas import AssessmentStartRequest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        handoff_from_step1(AssessmentStartRequest(source_id="SRC_missing", student_id="student", knowledge_graph=graph().model_dump()))
    assert exc.value.status_code == 404


def test_submission_replay_and_partial_commit_recovery(monkeypatch):
    from app.api import assessment
    from app.services import storage
    from app.services.assessment import session_store, profile as profiles, video_target
    q = question()
    session = AssessmentSession(student_id="student", source_id="SRC_test", status="READY", questions=[q])
    session_store.save_session(session)
    monkeypatch.setattr(assessment, "load_knowledge_graph", lambda _: graph())
    monkeypatch.setattr(assessment, "get_source_record", lambda _: None)
    from app.db import vector_store
    monkeypatch.setattr(vector_store, "retrieve_exact_chunks", lambda **kwargs: [chunk()])
    submission = StudentSubmission(session_id=session.session_id, answers=[AnswerSubmission(question_id=q.question_id, selected_index=0)])
    original_save = video_target.save_video_matrix
    monkeypatch.setattr(video_target, "save_video_matrix", Mock(side_effect=OSError("disk failure")))
    with pytest.raises(OSError):
        assessment.submit_assessment(submission)
    monkeypatch.setattr(video_target, "save_video_matrix", original_save)
    response = assessment.submit_assessment(submission)
    assert response.score == 1
    assert profiles.load_profile("student", "SRC_test").total_sessions == 1
    assert assessment.submit_assessment(submission).model_dump() == response.model_dump()


@pytest.mark.parametrize("background", [False, True])
def test_upload_quiz_submit_contract(monkeypatch, background):
    import re
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import upload, assessment, pipeline
    from app.db import vector_store
    from app.services.assessment import providers, generator, session_store
    class Reasoner:
        model_name = "test-ollama"
        def generate_content(self, prompt):
            if "knowledge graph analyst" in prompt:
                cid = re.search(r"\[(CU_[^\]]+)\]", prompt).group(1)
                return json.dumps({"topic_name": "Gravity", "concepts": [{"concept_id": "C1", "name": "Gravity", "definition": TEXT, "source_content_ids": [cid]}]})
            q = question()
            return json.dumps(dict(question=q.stem, options=[o.model_dump() for o in q.options], correct_index=0, evidence_quote=TEXT, explanation=TEXT))
    monkeypatch.setattr(providers, "get_default_provider", Reasoner)
    monkeypatch.setattr(generator, "get_default_provider", Reasoner)
    monkeypatch.setattr(vector_store, "_embed", lambda texts, **kwargs: [[1.0, 0.0, 0.0] for _ in texts])
    monkeypatch.setattr(vector_store, "_active_embedding_dim", 3)
    app = FastAPI()
    for router in [upload.router, assessment.router, pipeline.router]:
        app.include_router(router)
    client = TestClient(app)
    endpoint = "/pipeline/upload-and-assess" if background else "/upload"
    response = client.post(endpoint, params={"student_id": "student", "max_questions": 1, "auto_start_assessment": True}, files={"file": ("gravity.txt", TEXT, "text/plain")})
    assert response.status_code == 200, response.text
    payload = response.json()
    if background:
        status = client.get(f"/pipeline/jobs/{payload['job_id']}").json()
        assert status["status"] == "completed", status
        payload = status["result"]
    quiz = payload["assessment"]
    assert len(quiz["questions"]) == 1, quiz
    safe = quiz["questions"][0]
    assert isinstance(safe["options"][0], dict)
    assert not {"correct_index", "explanation", "evidence_quote", "evidence_text"} & safe.keys()
    session = session_store.load_session(quiz["session_id"])
    body = {"session_id": session.session_id, "answers": [{"question_id": safe["question_id"], "selected_index": session.questions[0].correct_index}]}
    result = client.post("/assessment/submit", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["score"] == 1 and len(result.json()["results"]) == 1
    assert client.post("/assessment/submit", json=body).json() == result.json()
