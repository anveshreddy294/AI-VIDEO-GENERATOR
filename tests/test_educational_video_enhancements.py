"""Second-round contracts with isolated owned storage; no production providers."""
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.api.sources import source_repository
from app.services import educational_content as ec
from app.services.video import educational_video as ev
from app.services.video.scene_schema import VideoArtifact, SceneTimelineEntry, VideoJobStatus
from tests.test_source_supabase import context, OWNER, OTHER
from tests.test_video_generation_foundation import service, lesson_for, grounded_plan


def completed(service, *, plan=None, job="generation-a"):
    lesson = lesson_for(service)
    plan = plan or ev.build_video_plan(service, lesson.content, ev.VideoOptions())
    plan.video_id = job
    media = settings.renders_dir / f"{job}.mp4"
    media.write_bytes(b"fixture; real encoding tested separately")
    captions = settings.captions_dir / f"{job}.vtt"
    captions.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nA scene\n")
    timeline = [SceneTimelineEntry(scene_id=s.scene_id, scene_index=i, start_seconds=i*2,
                                  end_seconds=(i+1)*2, duration_seconds=2) for i,s in enumerate(plan.scenes)]
    artifact = VideoArtifact(job_id=job, student_id=str(OWNER), source_id=plan.source_id,
        concept_id=plan.concept_id, concept_name=plan.concept_name, status=VideoJobStatus.COMPLETED,
        video_path=str(media), subtitle_path=str(captions), duration_seconds=len(timeline)*2,
        scene_timeline=timeline, timing_status="MEASURED", caption_quality="SCENE_TIMED")
    lesson.video = dict(job_id=job, status="COMPLETED", duration_seconds=artifact.duration_seconds, video_path=str(media))
    lesson.video_generations[job] = ec.EducationalVideoGeneration(job_id=job, plan=plan,
        artifact=artifact, timing_status="MEASURED")
    ec.save_educational_lesson(lesson)
    return lesson, artifact


@pytest.mark.parametrize("body", [{"target_seconds":0},{"target_seconds":"45"},
    {"difficulty":"expert"},{"unknown":True},{"regenerate":"true"}])
def test_options_are_strict_and_bounded(service, body):
    lesson = lesson_for(service)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        assert client.post(f"/educational-content/{lesson.lesson_id}/video", json=body).status_code == 422
    assert not service.get_lesson(lesson.lesson_id).video_generations


@pytest.mark.parametrize("options,code", [({"topic":"Photosynthesis"},"VIDEO_TOPIC_MISMATCH"),
    ({"grounded":True},"VIDEO_SOURCE_REQUIRED"),({"chunk_ids":["k"]},"VIDEO_GROUNDING_REQUIRED")])
def test_plan_rejects_ambiguous_scope(service, options, code):
    lesson = lesson_for(service)
    with pytest.raises(HTTPException) as error:
        ev.build_video_plan(service, lesson.content, ev.VideoOptions(**options))
    assert error.value.detail["code"] == code


def test_topic_plan_uses_bounded_model_schema_and_labelled_bst_animation(service, monkeypatch):
    lesson = lesson_for(service)
    captured = []
    def model(request, schema):
        captured.append(request)
        return ev.VideoTeaching(scenes=[ev.SceneTeaching(scene_type=t, title=title,
            text="Compare keys and select a subtree.", narration="Compare keys and select a subtree.")
            for t,title in [("TITLE","Trees"),("DIAGRAM","Search"),("SUMMARY","Remember")]])
    monkeypatch.setattr(service,"_model",model)
    plan = ev.build_video_plan(service, lesson.content, ev.VideoOptions(target_seconds=60,difficulty="advanced"))
    assert plan.provenance["planning_status"] == "MODEL"
    assert plan.provenance_kind == "AI_ENRICHED"
    assert plan.difficulty == "advanced"
    assert sum(s.duration_seconds for s in plan.scenes) == pytest.approx(60)
    example = next(s for s in plan.scenes if s.diagram_type == "binary_search_tree")
    assert example.visual_payload["path"] == [0,1,4]
    assert "illustrative" in example.narration
    assert not example.evidence_references
    assert captured[0].response_schema is not None


def test_provider_failure_is_explicit_lesson_fallback(service, monkeypatch):
    lesson = lesson_for(service)
    monkeypatch.setattr(service,"_model",lambda *args: (_ for _ in ()).throw(RuntimeError("private-provider-error")))
    plan = ev.build_video_plan(service,lesson.content,ev.VideoOptions())
    assert plan.provenance["planning_status"] == "LESSON_FALLBACK"
    assert "private-provider-error" not in plan.model_dump_json()


def test_short_request_allocates_safe_speech_budget_without_truncating_model_narration(service, monkeypatch):
    lesson = lesson_for(service)
    teaching = ev.VideoTeaching(scenes=[ev.SceneTeaching(scene_type="EXPLANATION",title="Explain",
        text="Compare keys.",narration="Compare keys in the appropriate subtree. "*10) for _ in range(3)])
    monkeypatch.setattr(service,"_model",lambda *args:teaching)
    plan = ev.build_video_plan(service,lesson.content,ev.VideoOptions(target_seconds=30))
    assert plan.provenance["requested_seconds"] == 30
    assert 30 < plan.target_seconds <= 180
    assert plan.scenes[0].narration == teaching.scenes[0].narration
    from app.services.video.scene_validator import validate_video_plan
    validate_video_plan(plan)


def test_unsafe_model_scene_uses_valid_lesson_fallback(service, monkeypatch):
    lesson = lesson_for(service)
    teaching = ev.VideoTeaching(scenes=[ev.SceneTeaching(scene_type="EXPLANATION",title="Explain",
        text="exec(unsafe)",narration="Compare keys.") for _ in range(3)])
    monkeypatch.setattr(service,"_model",lambda *args:teaching)
    plan = ev.build_video_plan(service,lesson.content,ev.VideoOptions(target_seconds=30))
    assert plan.provenance["planning_status"] == "LESSON_FALLBACK"
    assert "exec(" not in plan.model_dump_json()


def test_metadata_timeline_lookup_pagination_captions_and_no_paths(service):
    lesson, artifact = completed(service)
    base = f"/educational-content/{lesson.lesson_id}/video"
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        response = client.get(base+"/metadata")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        metadata = response.json()
        assert metadata["media_available"] is True
        assert metadata["caption_quality"] == "SCENE_TIMED"
        assert str(settings.renders_dir) not in json.dumps(metadata)
        assert client.get(base+"/at?seconds=0").json()["scene_index"] == 0
        assert client.get(base+"/at?seconds=2").json()["scene_index"] == 1
        assert client.get(base+f"/at?seconds={artifact.duration_seconds}").status_code == 404
        for value in ("nan","inf","-1"):
            assert client.get(base+"/at?seconds="+value).status_code == 422
        assert client.get(base+"/scenes?offset=1&limit=1").json()["scenes"][0]["scene_index"] == 1
        assert client.get(base+"/scenes/missing").status_code == 404
        assert client.get(base+"/evidence").json()["traceability_status"] == "UNAVAILABLE"
        assert client.get(base+"/captions").text.startswith("WEBVTT")
        assert client.get(base+"/stream?generation_id=generation-a").content.startswith(b"fixture")
        assert client.get(base+"/metadata?generation_id=missing").status_code == 404


def test_legacy_timing_is_unavailable_not_estimated(service):
    lesson, _ = completed(service)
    generation = lesson.video_generations["generation-a"]
    generation.timing_status = generation.artifact.timing_status = "UNAVAILABLE"
    generation.artifact.scene_timeline = []
    ec.save_educational_lesson(lesson)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        response = client.get(f"/educational-content/{lesson.lesson_id}/video/at?seconds=1")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "VIDEO_TIMING_UNAVAILABLE"


def test_foreign_owner_cannot_read_metadata_stream_captions_or_reindex(service):
    lesson, _ = completed(service)
    service.repository.user = replace(service.repository.user,user_id=OTHER)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        base = f"/educational-content/{lesson.lesson_id}/video"
        for endpoint in ("metadata","stream","captions","scenes","evidence"):
            assert client.get(base+"/"+endpoint).status_code == 404
        assert client.post(base+"/reindex?generation_id=generation-a").status_code == 404


def test_regeneration_keeps_completed_artifact_and_pinned_history(service, monkeypatch):
    lesson, artifact = completed(service)
    async def scenario():
        gate = asyncio.Event()
        async def execute(*args):
            await gate.wait()
        monkeypatch.setattr(service,"_execute_video_pipeline",execute)
        before = set(ec._video_tasks)
        assert service.start_video_job(lesson)["job_id"] == "generation-a"
        new = service.start_video_job(lesson,regenerate=True)
        assert new["job_id"] != "generation-a"
        saved = service.get_lesson(lesson.lesson_id)
        assert saved.video_generations[new["job_id"]].prior_job_id == "generation-a"
        assert saved.video_generations["generation-a"].artifact.video_path == artifact.video_path
        with TestClient(app) as client:
            app.dependency_overrides[source_repository] = lambda: service.repository
            base = f"/educational-content/{lesson.lesson_id}/video"
            assert client.get(base+"/stream").status_code == 200
            assert client.get(base+"/stream?generation_id=generation-a").status_code == 200
            assert client.post(base,json={"regenerate":True}).status_code == 409
        gate.set()
        await asyncio.gather(*(set(ec._video_tasks)-before))
    asyncio.run(scenario())


def fake_index(monkeypatch, *, broken=False):
    from app.db import vector_store as vs
    class Index:
        points = {}
        def upsert(self, name, points, wait):
            if broken:
                raise RuntimeError("private-vector-error")
            self.points.update({p.id:p for p in points})
        def retrieve(self, name, ids, with_payload):
            return [self.points[i] for i in ids if i in self.points]
        def search(self, name, **kwargs):
            self.filter = kwargs["query_filter"]
            return [NS(payload=p.payload,score=.9) for p in self.points.values()]
    index = Index()
    monkeypatch.setattr(vs,"get_client",lambda:index)
    monkeypatch.setattr(vs,"embed_documents",lambda values:[[1.0,0.0] for v in values])
    monkeypatch.setattr(vs,"embed_query",lambda value:[1.0,0.0])
    monkeypatch.setattr(vs,"embedding_provenance",lambda:{"embedding_kind":"mock"})
    monkeypatch.setattr(vs,"semantic_filter_conditions",lambda:[])
    monkeypatch.setattr(vs,"ensure_collection",lambda *args:None)
    from app.services.video import video_compositor
    monkeypatch.setattr(video_compositor,"validate_video_artifact",lambda *args,**kwargs:{"duration":8})
    return index


def test_index_reconciliation_idempotency_search_owner_digest_and_missing_file(service, monkeypatch):
    lesson, artifact = completed(service)
    index = fake_index(monkeypatch)
    for _ in range(2):
        assert ev.reconcile_scene_index(service.repository,lesson.lesson_id,"generation-a")["indexing_status"] == "INDEXED"
    assert len(index.points) == len(lesson.video_generations["generation-a"].plan.scenes)
    result = ev.search_scenes(service.repository,"search",0,2)
    assert len(result["scenes"]) == 2 and result["next_offset"] == 2
    assert any(c.key == "user_id" and c.match.value == str(OWNER) for c in index.filter.must)
    point = next(iter(index.points.values()))
    point.payload["metadata_digest"] = "stale"
    assert len(ev.search_scenes(service.repository,"search",0,50)["scenes"]) == len(index.points)-1
    point.payload["user_id"] = str(OTHER)
    assert all(s["scene_id"] != point.payload["scene_id"] for s in ev.search_scenes(service.repository,"search",0,50)["scenes"])
    from pathlib import Path
    Path(artifact.video_path).unlink()
    assert ev.search_scenes(service.repository,"search",0,50)["scenes"] == []
    assert ev.video_metadata(service.repository,lesson.lesson_id)["media_available"] is False


def test_index_failure_keeps_completed_video_and_retry_succeeds(service, monkeypatch):
    lesson, _ = completed(service)
    fake_index(monkeypatch,broken=True)
    result = ev.reconcile_scene_index(service.repository,lesson.lesson_id,"generation-a")
    assert result["indexing_status"] == "FAILED"
    saved = service.get_lesson(lesson.lesson_id)
    assert saved.video["status"] == "COMPLETED"
    assert "private-vector-error" not in saved.model_dump_json()
    fake_index(monkeypatch)
    assert ev.reconcile_scene_index(service.repository,lesson.lesson_id,"generation-a")["indexing_status"] == "INDEXED"


def test_evidence_revalidated_in_both_directions_and_default_stream(service, monkeypatch):
    plan = grounded_plan()
    lesson, _ = completed(service,plan=plan)
    # Fixture validates exact quotations; live RLS is separately unverified.
    ref = plan.scenes[0].evidence_references[0]
    unit = NS(content_id=ref.source_content_id,text=" "*ref.char_start+ref.quote)
    from app.services.security.content_sanitizer import SanitizedContent
    safe = SanitizedContent(content_id=unit.content_id,source_id=plan.source_id,source_version=f"v{plan.source_version}",
        original_text=unit.text,sanitized_text=unit.text,original_text_hash="fixture")
    monkeypatch.setattr(ev,"require_source_scope",lambda *args:(None,NS(sanitized_content=[safe.model_dump()])))
    monkeypatch.setattr(service.repository,"get_content_units",lambda *args:[unit])
    assert ev.video_metadata(service.repository,lesson.lesson_id)["scenes"][0]["evidence_references"][0]["quote"] == ref.quote
    found = ev.scenes_for_source(service.repository,plan.source_id,plan.source_version,ref.chunk_id,None,0,20)
    assert found["scenes"][0]["scene_id"] == plan.scenes[0].scene_id
    unit.text = "changed"
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        base = f"/educational-content/{lesson.lesson_id}/video"
        for endpoint in ("metadata","evidence","stream","stream?generation_id=generation-a","captions"):
            assert client.get(base+"/"+endpoint).status_code == 409


def test_captions_reject_path_outside_private_caption_storage(service, tmp_path):
    lesson, _ = completed(service)
    outside = tmp_path/"private.vtt"
    outside.write_text("private")
    lesson.video_generations["generation-a"].artifact.subtitle_path = str(outside)
    ec.save_educational_lesson(lesson)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        assert client.get(f"/educational-content/{lesson.lesson_id}/video/captions").status_code == 404


def test_grounded_planning_preserves_literal_offsets_and_concept_mappings(service, monkeypatch):
    from app.services.retrieval import RetrievalService
    lesson = lesson_for(service)
    lesson.content = lesson.content.model_copy(update={"source_id":"source-a", "source_version":2})
    monkeypatch.setattr(ev,"require_source_scope",lambda *args:None)
    def item(n):
        return NS(source_id="source-a",source_version=2,content_id=f"unit-{n}",chunk_id=f"chunk-{n}",
                  concept_ids=[f"concept-{n}"],excerpt="Smaller keys belong in the left subtree.",
                  char_start=7,char_end=45,page_start=n,page_end=n)
    bundle = NS(outcome="READY",items=[item(1),item(2)])
    monkeypatch.setattr(RetrievalService,"retrieve",lambda *args:bundle)
    plan = ev.build_video_plan(service,lesson.content,ev.VideoOptions(grounded=True))
    assert plan.provenance_kind == "SOURCE_GROUNDED"
    assert plan.provenance["planning_status"] == "EXTRACTIVE"
    assert plan.concept_ids == ["concept-1","concept-2"]
    for scene in plan.scenes:
        ref = scene.evidence_references[0]
        assert ref.char_start == 7 and ref.char_end == 7+len(scene.narration)
        assert scene.source_chunk_ids == [ref.chunk_id]
    with pytest.raises(HTTPException) as error:
        ev.build_video_plan(service,lesson.content,ev.VideoOptions(grounded=True,chunk_ids=["missing"]))
    assert error.value.detail["code"] == "VIDEO_EVIDENCE_INSUFFICIENT"
    bundle.outcome = "INDEX_UNAVAILABLE"
    with pytest.raises(HTTPException):
        ev.build_video_plan(service,lesson.content,ev.VideoOptions(grounded=True))


@pytest.mark.parametrize("final_duration,valid", [(8.0,True),(11.0,False)])
def test_scene_media_measures_audio_boundaries_and_rejects_final_mismatch(monkeypatch, final_duration, valid):
    from app.services.video import scene_media as sm
    from app.services.video.scene_schema import VideoPlan, ScenePlan, NarrationSegment
    monkeypatch.setattr(sm,"_resolve_binary",lambda name:"ffmpeg")
    commands = []
    async def command(args,**kwargs):
        commands.append(args)
        kwargs["output_path"].write_bytes(b"test")
        return 0,"",""
    monkeypatch.setattr(sm,"run_subprocess_bounded",command)
    monkeypatch.setattr(sm,"render_video_plan",lambda plan,path:path.write_bytes(b"test"))
    monkeypatch.setattr(sm,"probe_media",lambda path:{"format":{"duration":2 if path.stem.endswith("_0") else 5},
                                                       "streams":[{"codec_type":"audio"}]})
    monkeypatch.setattr(sm,"validate_video_artifact",lambda path,*args:{"duration":
        (3 if "_0_scene" in path.stem else 5) if "_scene" in path.stem else final_duration})
    class TTS:
        async def generate_audio(self,text,path,**kwargs):
            path.write_bytes(b"audio")
    plan = VideoPlan(concept_id="c",concept_name="Trees",duration_seconds=6, scenes=[
        ScenePlan(scene_index=i,title="Trees",narration="Compare keys",duration_seconds=3) for i in range(2)],
        narration=[NarrationSegment(scene_index=i,text="Compare keys") for i in range(2)])
    async def scenario():
        return await sm.assemble_scene_media(plan,"timing-test",TTS(),lambda *args:None)
    if not valid:
        with pytest.raises(ValueError,match="FINAL_TIMELINE_MISMATCH"):
            asyncio.run(scenario())
        return
    result = asyncio.run(scenario())
    timeline = result["timeline"]
    assert [(t.start_seconds,t.end_seconds) for t in timeline] == [(0,3),(3,8)]
    assert "duration=5.0" in commands[1][commands[1].index("-af")+1]
    assert result["duration"] == 8
    from pathlib import Path
    assert "00:00:03.000 --> 00:00:08.000" in Path(result["subtitle_path"]).read_text()
