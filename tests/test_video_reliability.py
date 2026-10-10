"""Real canonical chunk reconstruction and protected media contracts; offline DB doubles."""
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.api.sources import source_repository
from app.services.video import educational_video as ev
from app.services.video.scene_schema import VideoPlan, ScenePlan, SceneEvidenceReference, NarrationSegment
from app.services.repositories.source_repository import SupabaseSourceRepository
from tests.test_canonical_retrieval import fixture as canonical_fixture, SCOPE, TEXT
from tests.test_source_supabase import context
from tests.test_video_generation_foundation import service
from tests.test_educational_video_enhancements import completed, fake_index


def canonical_plan(canonical_fixture,monkeypatch):
    context, candidate = canonical_fixture
    version = SupabaseSourceRepository.get_source_version(None,None,None)
    repo = NS(user=context.user,_token=context._token,runtime=context.runtime,
              get_content_units=lambda *args:[u.content for u in context.units])
    monkeypatch.setattr(ev,"require_source_scope",lambda *args:(SCOPE,version))
    monkeypatch.setattr("app.services.repositories.knowledge_repository.KnowledgeRepository",lambda *args:context)
    ref = SceneEvidenceReference(source_id=SCOPE.source_id,source_version=SCOPE.source_version,
        source_content_id="content",chunk_id=candidate.payload["chunk_id"],concept_id="osmosis",
        quote=TEXT,char_start=0,char_end=len(TEXT))
    plan = VideoPlan(student_id=str(SCOPE.user_id),source_id=SCOPE.source_id,source_version=SCOPE.source_version,
        concept_id="osmosis",concept_name="Osmosis",duration_seconds=25,
        source_chunk_ids=[ref.chunk_id],source_content_ids=["content"],
        scenes=[ScenePlan(text=TEXT,narration=TEXT,duration_seconds=25,
                          source_chunk_ids=[ref.chunk_id],evidence_references=[ref])],
        narration=[NarrationSegment(scene_index=0,text=TEXT)])
    return repo,plan


def test_real_canonical_chunk_contains_the_scene_quote(canonical_fixture,monkeypatch):
    repo,plan = canonical_plan(canonical_fixture,monkeypatch)
    ev.validate_plan_evidence(repo,plan)


def test_valid_content_quote_with_forged_chunk_id_is_rejected(canonical_fixture,monkeypatch):
    repo,plan = canonical_plan(canonical_fixture,monkeypatch)
    # All saved declarations agree: only canonical reconstruction reveals the forgery.
    plan.source_chunk_ids = ["forged-chunk"]
    plan.scenes[0].source_chunk_ids = ["forged-chunk"]
    plan.scenes[0].evidence_references[0].chunk_id = "forged-chunk"
    with pytest.raises(HTTPException) as error:
        ev.validate_plan_evidence(repo,plan)
    assert error.value.status_code == 409


def test_valid_quote_cannot_be_attached_to_unrelated_scene(canonical_fixture,monkeypatch):
    repo,plan = canonical_plan(canonical_fixture,monkeypatch)
    plan.scenes[0].text = plan.scenes[0].narration = "Unrelated teaching."
    with pytest.raises(HTTPException):
        ev.validate_plan_evidence(repo,plan)


def test_quote_cannot_cross_its_actual_chunk_boundary(canonical_fixture,monkeypatch):
    repo,plan = canonical_plan(canonical_fixture,monkeypatch)
    from app.services.educational_chunker import ChunkMetadata, ChunkPolicy, create_educational_chunks
    from app.services.security.content_sanitizer import SanitizedContent
    context,_ = canonical_fixture
    version = SupabaseSourceRepository.get_source_version(None,None,None)
    text = (TEXT+" ")*12
    context.units[0].content.text = text
    context.data = context.data.model_copy(update={"evidence":[
        e.model_copy(update={"char_end":len(text)}) for e in context.data.evidence]})
    version.provenance["chunk_policy"] = ChunkPolicy(max_tokens=64,target_tokens=32,
        explanatory_overlap_tokens=0).model_dump()
    version.sanitized_content = [SanitizedContent(content_id="content",source_id=SCOPE.source_id,
        original_text=text,sanitized_text=text,original_text_hash="hash").model_dump()]
    chunks,_ = create_educational_chunks(SCOPE,context.units,context.data,
        ChunkPolicy.model_validate(version.provenance["chunk_policy"]),version.file_hash)
    chunk = chunks[0]
    span = ChunkMetadata.model_validate(chunk.metadata).canonical_spans[0]
    assert span.char_end+5 < len(text)
    scene = plan.scenes[0]
    ref = scene.evidence_references[0]
    plan.source_chunk_ids = scene.source_chunk_ids = [chunk.chunk_id]
    ref.chunk_id, ref.char_start, ref.char_end = chunk.chunk_id, span.char_start, span.char_end
    ref.quote = text[ref.char_start:ref.char_end]
    scene.text = scene.narration = plan.narration[0].text = ref.quote
    ev.validate_plan_evidence(repo,plan)
    ref.char_end += 5
    ref.quote = text[ref.char_start:ref.char_end]
    scene.text = scene.narration = plan.narration[0].text = ref.quote
    with pytest.raises(HTTPException):
        ev.validate_plan_evidence(repo,plan)


def test_bidirectional_traceability_uses_real_chunk_and_filters(canonical_fixture,service,monkeypatch):
    repo,plan = canonical_plan(canonical_fixture,monkeypatch)
    lesson,_ = completed(service,plan=plan)
    metadata = ev.video_metadata(repo,lesson.lesson_id,"generation-a")
    ref = metadata["scenes"][0]["evidence_references"][0]
    page = ev.scenes_for_source(repo,SCOPE.source_id,SCOPE.source_version,ref["chunk_id"],"content",0,20)
    assert page["scenes"][0]["scene_id"] == plan.scenes[0].scene_id
    assert page["scenes"][0]["evidence_references"][0] == ref
    assert ev.scenes_for_source(repo,SCOPE.source_id,SCOPE.source_version,"wrong-chunk",None,0,20)["scenes"] == []


def test_corrupted_captions_are_not_served_or_indexed(service,monkeypatch):
    lesson,artifact = completed(service)
    from pathlib import Path
    path = Path(artifact.subtitle_path)
    path.write_text(path.read_text().replace("00:00:02.000","00:00:01.500",1),encoding="utf-8")
    index = fake_index(monkeypatch,duration=artifact.duration_seconds)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda:service.repository
        response = client.get(f"/educational-content/{lesson.lesson_id}/video/captions")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "VIDEO_CAPTIONS_INVALID"
    assert ev.reconcile_scene_index(service.repository,lesson.lesson_id,"generation-a")["indexing_status"] == "FAILED"
    assert not index.points
    assert service.get_lesson(lesson.lesson_id).video["status"] == "COMPLETED"


def test_authenticated_range_download_and_invalid_timestamps(service):
    lesson,artifact = completed(service)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda:service.repository
        base = f"/educational-content/{lesson.lesson_id}/video"
        response = client.get(base+"/stream?generation_id=generation-a",headers={"Range":"bytes=0-6"})
        assert response.status_code == 206
        assert response.content == b"fixture"
        assert response.headers["cache-control"] == "private, no-store"
        for value in ("NaN","Infinity","-1"):
            assert client.get(base+"/at",params={"seconds":value}).status_code == 422
        assert client.get(base+"/at",params={"seconds":artifact.duration_seconds}).status_code == 404


@pytest.mark.parametrize("missing", [False,True])
def test_ollama_scene_embedding_path_reports_missing_model_without_name_error(monkeypatch,missing):
    import json
    import urllib.request
    import urllib.error
    from contextlib import contextmanager
    from app.db import vector_store as vs
    from app.core.processing_errors import ProcessingError
    from app.core.config import settings
    monkeypatch.setattr(settings,"embedding_provider","ollama")
    monkeypatch.setattr(settings,"embedding_model","embeddinggemma")
    monkeypatch.setattr(settings,"embedding_fallback_model","embeddinggemma")
    monkeypatch.setattr(vs,"_QUERY_EMBED_CACHE",{})
    monkeypatch.delenv("PYTEST_CURRENT_TEST",raising=False)
    @contextmanager
    def response(request,**kwargs):
        if missing:
            raise urllib.error.HTTPError(request.full_url,404,"not found",{},None)
        yield NS(read=lambda:json.dumps({"model":"embeddinggemma","embeddings":[[1.0]*768]}).encode())
    monkeypatch.setattr(urllib.request,"urlopen",response)
    if missing:
        with pytest.raises(ProcessingError) as error:
            vs.embed_query("Binary search tree scene")
        assert error.value.code == "EMBEDDING_MODEL_UNAVAILABLE"
    else:
        assert len(vs.embed_query("Binary search tree scene")) == 768
        assert vs.embedding_provenance()["embedding_kind"] == "semantic"
