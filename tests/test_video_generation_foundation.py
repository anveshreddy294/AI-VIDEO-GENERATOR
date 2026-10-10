"""Deterministic generation persistence/recovery and exact evidence contracts."""
import asyncio
import json
import subprocess
import sys
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.api.sources import source_repository
from app.services import educational_content as ec
from app.services.video.generation_lock import GenerationLock
from app.services.video.scene_schema import SceneEvidenceReference, ScenePlan, VideoPlan, NarrationSegment
from app.services.video.scene_validator import validate_video_plan, SceneValidationError
from tests.test_source_supabase import context, OWNER, OTHER
from tests.test_educational_lesson_features import MockProvider


@pytest.fixture
def service(context, monkeypatch, tmp_path):
    monkeypatch.setattr(ec, "LESSONS_DIR", tmp_path / "lessons")
    _, repo, _ = context
    return ec.EducationalContentService(repo, MockProvider())


def lesson_for(service):
    content = service.generate(ec.ContentRequest(topic="Binary Search Trees"))
    return service.get_lesson(str(content.content_id))


def test_start_persists_plan_before_execution_and_deduplicates(service, monkeypatch):
    lesson = lesson_for(service)
    async def scenario():
        release = asyncio.Event()
        async def execute(lesson_id, user_id, plan, job_id):
            saved = ec.get_educational_lesson(user_id, lesson_id)
            record = saved.video_generations[job_id]
            assert record.plan.video_id == job_id
            assert record.plan.scenes == plan.scenes
            await release.wait()
        monkeypatch.setattr(service, "_execute_video_pipeline", execute)
        before = set(ec._video_tasks)
        first = service.start_video_job(lesson)
        job_id = first["job_id"]
        assert ec.get_educational_lesson(OWNER, lesson.lesson_id).video_generations[job_id].status == "QUEUED"
        assert service.get_lesson(lesson.lesson_id).video["status"] == "QUEUED"
        assert service.start_video_job(lesson)["job_id"] == job_id
        assert ec.get_educational_lesson(OTHER, lesson.lesson_id) is None
        release.set()
        await asyncio.gather(*(set(ec._video_tasks) - before))
    asyncio.run(scenario())


def test_orphan_recovery_and_retry_keep_previous_plan(service, monkeypatch):
    lesson = lesson_for(service)
    original_plan = service.create_video_plan(lesson.content)
    lesson.video = {"job_id": "orphan", "status": "RENDERING", "progress": 75}
    lesson.video_generations["orphan"] = ec.EducationalVideoGeneration(job_id="orphan", plan=original_plan)
    ec.save_educational_lesson(lesson)
    recovered = service.get_lesson(lesson.lesson_id)
    assert recovered.video["status"] == "FAILED"
    assert recovered.video["error_code"] == "VIDEO_JOB_INTERRUPTED"
    assert recovered.video_generations["orphan"].status == "FAILED"
    assert recovered.video_generations["orphan"].completed_at
    async def execute(*args):
        pass
    monkeypatch.setattr(service, "_execute_video_pipeline", execute)
    async def scenario():
        before = set(ec._video_tasks)
        result = service.start_video_job(recovered)
        current = ec.get_educational_lesson(OWNER, lesson.lesson_id)
        assert current.video_generations[result["job_id"]].prior_job_id == "orphan"
        assert current.video_generations["orphan"].plan == original_plan
        assert current.video_generations[result["job_id"]].plan.video_id == result["job_id"]
        await asyncio.gather(*(set(ec._video_tasks) - before))
    asyncio.run(scenario())


def test_active_lock_prevents_false_recovery(service):
    lesson = lesson_for(service)
    lesson.video = {"job_id": "live", "status": "RENDERING", "progress": 75}
    ec.save_educational_lesson(lesson)
    lease = GenerationLock.acquire(settings.runtime_dir / "video_execution_locks", "live")
    assert lease is not None
    try:
        assert service.get_lesson(lesson.lesson_id).video["status"] == "RENDERING"
    finally:
        lease.close()
    assert service.get_lesson(lesson.lesson_id).video["status"] == "FAILED"


def test_cancel_before_task_starts_releases_execution_lock(service):
    lesson = lesson_for(service)
    async def scenario():
        before = set(ec._video_tasks)
        result = service.start_video_job(lesson)
        tasks = set(ec._video_tasks) - before
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        recovered = service.get_lesson(lesson.lesson_id)
        assert recovered.video["job_id"] == result["job_id"]
        assert recovered.video["status"] == "FAILED"
    asyncio.run(scenario())


def test_delayed_old_worker_cannot_replace_new_video_or_progress(service):
    lesson = lesson_for(service)
    lesson.video = {"job_id": "old", "status": "RENDERING"}
    ec.save_educational_lesson(lesson)
    delayed = ec.get_educational_lesson(OWNER, lesson.lesson_id)
    latest = ec.get_educational_lesson(OWNER, lesson.lesson_id)
    latest.video = {"job_id": "new", "status": "QUEUED"}
    latest.progress["video_completed"] = False
    ec.save_educational_lesson(latest)
    delayed.video.update(status="COMPLETED", video_path="old.mp4")
    delayed.progress["video_completed"] = True
    ec.save_educational_lesson(delayed)
    saved = ec.get_educational_lesson(OWNER, lesson.lesson_id)
    assert saved.video == {"job_id": "new", "status": "QUEUED"}
    assert saved.progress["video_completed"] is False


def test_public_video_responses_exclude_private_paths_and_history(service):
    lesson = lesson_for(service)
    lesson.video = dict(job_id="completed", status="COMPLETED", progress=100,
                        video_path="private/render.mp4", audio_path="private/audio.wav", plan={"secret": "x"})
    lesson.video_generations["completed"] = ec.EducationalVideoGeneration(
        job_id="completed", plan=service.create_video_plan(lesson.content))
    ec.save_educational_lesson(lesson)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        base = f"/educational-content/{lesson.lesson_id}"
        for path in ("/video/status", "/video"):
            response = client.get(base + path) if path.endswith("status") else client.post(base + path)
            assert response.status_code == 200
            assert response.json() == {"job_id": "completed", "status": "COMPLETED", "progress": 100}
        detail = client.get(base).json()
        assert "video_generations" not in detail
        assert "private/" not in json.dumps(detail)


def test_incomplete_video_is_not_streamable(service, tmp_path):
    lesson = lesson_for(service)
    media = settings.renders_dir / "unfinished.mp4"
    media.write_bytes(b"partial")
    lesson.video = dict(job_id="failed", status="FAILED", video_path=str(media))
    ec.save_educational_lesson(lesson)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        response = client.get(f"/educational-content/{lesson.lesson_id}/video/stream")
        assert response.status_code == 404


def test_plan_owner_mismatch_is_rejected_before_scheduling(service):
    lesson = lesson_for(service)
    plan = service.create_video_plan(lesson.content)
    plan.student_id = str(OTHER)
    with pytest.raises(ValueError, match="owned lesson"):
        service.start_video_job(lesson, plan=plan)
    assert ec.get_educational_lesson(OWNER, lesson.lesson_id).video is None


def test_execution_lock_is_cross_process_and_released_on_exit(tmp_path):
    directory = tmp_path / "locks"
    code = ("import os,sys; from pathlib import Path; "
            "from app.services.video.generation_lock import GenerationLock; "
            "lock=GenerationLock.acquire(Path(sys.argv[1]),'job'); "
            "print(lock is not None,flush=True); os._exit(0)")
    lease = GenerationLock.acquire(directory, "job")
    assert lease is not None
    try:
        result = subprocess.run([sys.executable, "-B", "-c", code, str(directory)],
                                capture_output=True, text=True, timeout=20, check=True)
        assert result.stdout.strip() == "False"
    finally:
        lease.close()
    result = subprocess.run([sys.executable, "-B", "-c", code, str(directory)],
                            capture_output=True, text=True, timeout=20, check=True)
    assert result.stdout.strip() == "True"
    recovered = GenerationLock.acquire(directory, "job")
    assert recovered is not None
    recovered.close()


def grounded_plan():
    reference = SceneEvidenceReference(source_id="s", source_version=2, source_content_id="u",
        chunk_id="k", concept_id="c", quote="A tree", char_start=10, char_end=16)
    return VideoPlan(source_id="s", source_version=2, concept_id="c", concept_name="Trees",
        duration_seconds=5, source_content_ids=["u"], source_chunk_ids=["k"],
        scenes=[ScenePlan(text="A tree", narration="A tree", source_chunk_ids=["k"],
                          evidence_references=[reference])],
        narration=[NarrationSegment(scene_index=0, text="A tree")])


@pytest.mark.parametrize("field,value", [("source_version", 3), ("source_id", "other"),
    ("source_content_id", "other"), ("chunk_id", "other"), ("concept_id", "other"),
    ("quote", "Fake!!"), ("char_end", 99)])
def test_inconsistent_scene_evidence_is_rejected(field, value):
    plan = grounded_plan()
    setattr(plan.scenes[0].evidence_references[0], field, value)
    with pytest.raises(SceneValidationError):
        validate_video_plan(plan)


def test_duplicate_scene_ids_are_rejected():
    plan = grounded_plan()
    plan.scenes.append(plan.scenes[0].model_copy(deep=True))
    with pytest.raises(SceneValidationError, match="Duplicate scene"):
        validate_video_plan(plan)


def test_exact_scene_evidence_roundtrips_without_invented_timing():
    plan = grounded_plan()
    validate_video_plan(plan)
    restored = VideoPlan.model_validate_json(plan.model_dump_json())
    assert restored == plan
    assert "start_seconds" not in restored.scenes[0].model_dump()


@pytest.mark.parametrize("first_quote", ["First quote.", "  " + "Evidence " * 50 + "  "])
def test_canonical_quote_scenes_reference_only_their_supporting_items(monkeypatch, first_quote):
    from app.services.video import session_video as sv
    sid = uuid4()
    learning = NS(user_id=OWNER, source_id="s", source_version=2, topic_id=None, subtopic_id=None)
    job = NS(job_id="r", concept_id="c", attempt_number=1, metadata={})
    mastery = NS(concept_id="c", mastery_state="REMEDIATING", remediation_attempt_count=1)
    saved = NS(remediation=[job], mastery=[mastery])
    learning_service = NS(_learning=lambda *args, **kwargs: learning,
                          repository=NS(transact=lambda *args: saved))
    monkeypatch.setattr(sv, "SessionLearningService", lambda _: learning_service)
    def item(chunk, content, text, offset):
        return NS(source_id="s", source_version=2, concept_ids=["c"], chunk_id=chunk,
                  content_id=content, excerpt=text, char_start=offset, char_end=offset+len(text),
                  page_start=None, page_end=None)
    bundle = NS(outcome="READY", scope=NS(user_id=OWNER), items=[
        item("k1", "u1", first_quote, 10), item("k2", "u2", "Second quote.", 30),
        item("k3", "u3", first_quote, 50)])
    monkeypatch.setattr(sv, "RetrievalService", lambda: NS(retrieve=lambda *args: bundle))
    context = NS(user=NS(user_id=OWNER), get_concept=lambda *args: NS(name="Trees"))
    adapter = sv.SessionVideo(context, sid, "r")
    captured = {}
    def transact(action, payload=None):
        if action == "get":
            return None
        captured.update(payload)
        return {"claimed": True, "video": dict(job_id="v", status="QUEUED", stage="QUEUED",
                                                progress=0, duration_seconds=16)}
    monkeypatch.setattr(adapter, "transact", transact)
    _, target = adapter.prepare()
    assert target is not None
    plan = VideoPlan.model_validate(captured["plan"])
    assert plan.source_version == 2
    assert len(plan.scenes) == (2 if len(first_quote) <= 360 else 3)
    assert plan.scenes[0].source_chunk_ids == ["k1", "k3"]
    assert plan.scenes[-1].source_chunk_ids == ["k2"]
    for scene in plan.scenes:
        for reference in scene.evidence_references:
            original = next(i for i in bundle.items if i.chunk_id == reference.chunk_id)
            assert original.excerpt[reference.char_start-original.char_start:
                                    reference.char_end-original.char_start] == scene.text


def test_generation_completion_metadata_and_unavailable_capabilities_are_truthful(service):
    lesson = lesson_for(service)
    plan = service.create_video_plan(lesson.content)
    lesson.video = dict(job_id="v", status="COMPLETED", duration_seconds=28.125)
    lesson.video_generations["v"] = ec.EducationalVideoGeneration(job_id="v", plan=plan)
    ec.save_educational_lesson(lesson)
    saved = ec.get_educational_lesson(OWNER, lesson.lesson_id).video_generations["v"]
    assert saved.status == "COMPLETED"
    assert saved.actual_duration_seconds == 28.125
    assert saved.completed_at
    assert saved.plan == plan
    assert saved.timing_status == saved.traceability_status == "UNAVAILABLE"
    assert saved.indexing_status == "NOT_REQUESTED"
