"""Real SQL + existing Video API contracts; fake AI transport, isolated media."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient

from app.core import postgres
from app.core.config import Settings, settings
from app.main import app
from app.api.sources import source_repository
from app.services import educational_content as ec
from app.services.repositories.lesson_store import read_lesson, write_lesson, lesson_ids
from app.db.import_video_lessons import import_lessons
from tests.video_postgres_fixture import video_cluster, postgres_mode
from tests.test_video_generation_foundation import service, lesson_for
from tests.test_educational_video_enhancements import completed
from tests.test_source_supabase import context, OWNER, OTHER
from tests.test_canonical_retrieval import fixture as canonical_fixture


@pytest.mark.parametrize("variable,value",[("LESSON_PERSISTENCE_PROVIDER","unknown"),
    ("POSTGRES_POOL_SIZE","0"),("POSTGRES_TIMEOUT_SECONDS","nan"),
    ("POSTGRES_TIMEOUT_SECONDS","0"),("POSTGRES_TIMEOUT_SECONDS","61")])
def test_invalid_configuration(monkeypatch,variable,value):
    monkeypatch.setenv(variable,value)
    with pytest.raises(ValueError):
        Settings()


def test_postgres_requires_explicit_dsn(monkeypatch):
    monkeypatch.setenv("LESSON_PERSISTENCE_PROVIDER","postgres")
    monkeypatch.delenv("POSTGRES_DSN",raising=False)
    with pytest.raises(ValueError,match="POSTGRES_DSN is required"):
        Settings()


def test_dsn_error_is_redacted(monkeypatch):
    monkeypatch.setattr(settings,"postgres_dsn",SecretStr("password=private-value broken"))
    with pytest.raises(postgres.VideoDatabaseError) as error:
        postgres.connection_options()
    assert str(error.value) == "VIDEO_DATABASE_CONFIGURATION_INVALID"


def test_migration_and_role_are_ready(postgres_mode):
    postgres.readiness()
    with postgres.transaction() as connection:
        assert connection.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone() == (False,False)
        assert connection.execute("SELECT count(*) FROM visualai_video.schema_migrations").fetchone()[0] == 1


def test_checksum_changes_fail_without_reapplying(postgres_mode,monkeypatch,tmp_path):
    from app.db import video_migrations
    source = video_migrations.DIRECTORY/"001_video_persistence.sql"
    (tmp_path/source.name).write_text(source.read_text(encoding="utf-8")+"\n-- changed",encoding="utf-8")
    monkeypatch.setattr(video_migrations,"DIRECTORY",tmp_path)
    postgres.close_pool()
    monkeypatch.setattr(settings,"postgres_dsn",SecretStr(postgres_mode["admin"]))
    with pytest.raises(postgres.VideoDatabaseError,match="VIDEO_DATABASE_MIGRATION_CHANGED"):
        video_migrations.migrate()
    postgres.close_pool()


def test_privileged_runtime_role_rejected(postgres_mode,monkeypatch):
    postgres.close_pool()
    monkeypatch.setattr(settings,"postgres_dsn",SecretStr(postgres_mode["admin"]))
    with pytest.raises(postgres.VideoDatabaseError,match="VIDEO_DATABASE_PRIVILEGED_ROLE"):
        postgres.readiness()
    postgres.close_pool()


def test_lesson_crud_owner_isolation_and_no_json_fallback(postgres_mode,service):
    lesson = lesson_for(service)
    assert read_lesson(ec.LESSONS_DIR,OTHER,lesson.lesson_id) is None
    assert ec.get_educational_lesson(OTHER,lesson.lesson_id) is None
    assert lesson.lesson_id in lesson_ids(ec.LESSONS_DIR,OWNER)
    assert not list(ec.LESSONS_DIR.glob("*/*.json"))
    loaded = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    loaded.progress["read"] = True
    ec.save_educational_lesson(loaded)
    postgres.close_pool()
    assert ec.get_educational_lesson(OWNER,lesson.lesson_id).progress["read"] is True
    with postgres.transaction() as connection:
        connection.execute("SELECT set_config('visualai.owner_id', %s, true)",(str(OTHER),))
        # Even an unfiltered SELECT cannot read the other owner's document.
        assert connection.execute("SELECT lesson_id FROM visualai_video.lessons WHERE lesson_id=%s",(lesson.lesson_id,)).fetchall() == []
    with postgres.transaction() as connection:
        assert connection.execute("SELECT lesson_id FROM visualai_video.lessons WHERE lesson_id=%s",(lesson.lesson_id,)).fetchall() == []


def test_completed_history_artifact_and_index_failure(postgres_mode,service):
    lesson,artifact = completed(service)
    saved = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    saved.video_generations["generation-a"].indexing_status = "FAILED"
    saved.video_generations["generation-a"].indexing_error_code = "EMBEDDING_MODEL_UNAVAILABLE"
    ec.save_educational_lesson(saved)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        base = f"/educational-content/{lesson.lesson_id}/video"
        assert client.get(base+"/stream",headers={"Range":"bytes=0-6"}).status_code == 206
        assert client.get(base+"/captions").status_code == 200
        assert client.get("/health/database").json()["status"] == "ready"
    postgres.close_pool()
    loaded = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    assert loaded.video_generations["generation-a"].artifact == artifact
    assert loaded.video_generations["generation-a"].indexing_status == "FAILED"
    from app.core.supabase import AuthenticatedUser
    from app.services.repositories.source_repository import SupabaseSourceRepository
    other = SupabaseSourceRepository(AuthenticatedUser(OTHER,None,{}),"other-test-token",service.repository.runtime)
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: other
        assert client.get(base+"/stream?generation_id=generation-a").status_code == 404
        assert client.get(base+"/captions?generation_id=generation-a").status_code == 404
    Path(artifact.video_path).unlink()  # Only this test's disposable fixture.
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: service.repository
        assert client.get(base+"/stream").status_code == 404
    # History is still readable and unrelated notes/progress updates can be saved.
    loaded.progress["read"] = True
    ec.save_educational_lesson(loaded)
    assert ec.get_educational_lesson(OWNER,lesson.lesson_id).video_generations


def test_missing_new_artifact_rolls_back(postgres_mode,service):
    lesson, artifact = completed(service)
    saved = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    saved.video_generations["generation-a"].artifact.video_path = str(settings.renders_dir/"absent.mp4")
    saved.progress["must_rollback"] = True
    with pytest.raises(postgres.VideoDatabaseError,match="VIDEO_ARTIFACT_REFERENCE_INVALID"):
        ec.save_educational_lesson(saved)
    restored = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    assert "must_rollback" not in restored.progress
    assert restored.video_generations["generation-a"].artifact.video_path == artifact.video_path


def test_sql_constraint_failure_rolls_back_related_writes(postgres_mode,service):
    lesson,artifact = completed(service)
    document = lesson.model_dump(mode="json")
    document["progress"]["uncommitted"] = True
    document["video_generations"]["generation-a"]["status"] = "INVALID_STATUS"
    with pytest.raises(postgres.VideoDatabaseError,match="VIDEO_DATABASE_UNAVAILABLE"):
        write_lesson(ec.LESSONS_DIR,OWNER,lesson.lesson_id,document)
    assert "uncommitted" not in ec.get_educational_lesson(OWNER,lesson.lesson_id).progress


def test_concurrent_merge_preserves_other_fields(postgres_mode,service):
    lesson = lesson_for(service)
    first = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    second = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    first.progress["notes_read"] = True
    second.ask_history.append({"question":"What is a tree?","answer":"A hierarchy."})
    ec.save_educational_lesson(first)
    ec.save_educational_lesson(second)
    loaded = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    assert loaded.progress["notes_read"] and len(loaded.ask_history) == 1


def test_orphan_failure_retry_and_previous_version(postgres_mode,service,monkeypatch):
    lesson,artifact = completed(service)
    original = Path(artifact.video_path).read_bytes()
    async def scenario():
        gate = asyncio.Event()
        async def execute(*args):
            await gate.wait()
        monkeypatch.setattr(service,"_execute_video_pipeline",execute)
        before = set(ec._video_tasks)
        first = service.start_video_job(lesson,regenerate=True)
        assert service.start_video_job(lesson)["job_id"] == first["job_id"]
        assert service.get_lesson(lesson.lesson_id).video["status"] == "QUEUED"
        gate.set()
        await asyncio.gather(*(set(ec._video_tasks)-before))
        # Coroutine exited without terminal save: no execution owner remains.
        orphan = service.get_lesson(lesson.lesson_id)
        assert orphan.video["status"] == "FAILED"
        assert orphan.video["error_code"] == "VIDEO_JOB_INTERRUPTED"
        assert orphan.video_generations[first["job_id"]].prior_job_id == "generation-a"
        assert orphan.video_generations["generation-a"].status == "COMPLETED"
        gate.clear()
        before = set(ec._video_tasks)
        retry = service.start_video_job(orphan)
        assert retry["job_id"] != first["job_id"]
        gate.set()
        await asyncio.gather(*(set(ec._video_tasks)-before))
        return first["job_id"]
    job_id = asyncio.run(scenario())
    postgres.close_pool()
    loaded = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    assert loaded.video_generations[job_id].completed_at
    assert Path(artifact.video_path).read_bytes() == original


def test_database_restart_preserves_video(postgres_mode,service):
    lesson,artifact = completed(service)
    original = Path(artifact.video_path).read_bytes()
    postgres_mode["restart"]()
    postgres.readiness()  # Pool checks/discards pre-restart connections.
    loaded = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    assert loaded.video_generations["generation-a"].status == "COMPLETED"
    assert Path(artifact.video_path).read_bytes() == original


def test_real_process_deduplication_and_crash_recovery(postgres_mode,service,tmp_path,monkeypatch):
    from tests.test_video_process_recovery import test_simultaneous_regeneration_survives_real_process_termination
    # Disposable trust-auth DSN only; subprocesses never inherit the developer DSN.
    monkeypatch.setenv("LESSON_PERSISTENCE_PROVIDER","postgres")
    monkeypatch.setenv("POSTGRES_DSN",postgres_mode["dsn"])
    test_simultaneous_regeneration_survives_real_process_termination(service,tmp_path)


def test_real_renderer_persists_completion_in_postgres(postgres_mode,service,context):
    from tests.test_educational_lesson_features import test_video_generation_pipeline
    # Actual renderer/FFmpeg + synthetic test narration; no live AI providers.
    test_video_generation_pipeline(context)


def test_engine_failure_persists_in_postgres(postgres_mode,service,monkeypatch):
    from app.services.video import scene_media
    lesson = lesson_for(service)
    async def fail(*args):
        raise RuntimeError("Fixture audio failure")
    monkeypatch.setattr(scene_media,"assemble_scene_media",fail)
    async def scenario():
        before = set(ec._video_tasks)
        started = service.start_video_job(lesson)
        await asyncio.gather(*(set(ec._video_tasks)-before))
        return started["job_id"]
    job_id = asyncio.run(scenario())
    postgres.close_pool()
    loaded = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    assert loaded.video["status"] == "FAILED"
    assert loaded.video_generations[job_id].status == "FAILED"
    assert loaded.video_generations[job_id].completed_at


def test_failed_required_completion_write_cannot_publish_success(postgres_mode,service,monkeypatch):
    from app.services.video import scene_media
    lesson = lesson_for(service)
    writes = ec.write_lesson
    rejected = []
    def fail_completion(directory, owner, lesson_id, document):
        if (document.get("video") or {}).get("status") == "COMPLETED":
            rejected.append(True)
            raise postgres.VideoDatabaseError()
        return writes(directory,owner,lesson_id,document)
    async def media(plan, job_id, tts, progress):
        # Inject a persistence failure after media creation, independently of rendering.
        path = settings.renders_dir/f"{job_id}.mp4"
        path.write_bytes(b"isolated fixture")
        return {"video_path":str(path),"subtitle_path":None,"duration":2,
                "timeline":[],"validation":{"duration":2}}
    monkeypatch.setattr(ec,"write_lesson",fail_completion)
    monkeypatch.setattr(scene_media,"assemble_scene_media",media)
    async def scenario():
        before = set(ec._video_tasks)
        started = service.start_video_job(lesson)
        await asyncio.gather(*(set(ec._video_tasks)-before))
    asyncio.run(scenario())
    assert rejected
    postgres.close_pool()
    loaded = ec.get_educational_lesson(OWNER,lesson.lesson_id)
    assert loaded.video["status"] == "FAILED"
    assert all(g.status != "COMPLETED" for g in loaded.video_generations.values())


def test_source_scene_traceability_uses_postgres(postgres_mode,service,canonical_fixture,monkeypatch):
    from tests.test_video_reliability import test_bidirectional_traceability_uses_real_chunk_and_filters
    test_bidirectional_traceability_uses_real_chunk_and_filters(canonical_fixture,service,monkeypatch)


def test_corrupted_captions_cannot_be_served_or_indexed_from_postgres(postgres_mode,service,monkeypatch):
    from tests.test_video_reliability import test_corrupted_captions_are_not_served_or_indexed
    test_corrupted_captions_are_not_served_or_indexed(service,monkeypatch)


def test_import_dry_run_apply_idempotency_and_conflict(postgres_mode,service,tmp_path):
    lesson,artifact = completed(service)
    # A distinct legacy ID avoids collisions with the already persisted lesson.
    lesson.lesson_id = "legacy_"+uuid4().hex
    directory = tmp_path/"legacy"
    path = directory/str(OWNER)/f"{lesson.lesson_id}.json"
    path.parent.mkdir(parents=True)
    original = lesson.model_dump_json()
    path.write_text(original,encoding="utf-8")
    assert import_lessons(directory)["eligible"] == 1
    assert ec.get_educational_lesson(OWNER,lesson.lesson_id) is None
    assert import_lessons(directory,apply=True)["imported"] == 1
    assert import_lessons(directory,apply=True)["unchanged"] == 1
    lesson.topic = "Changed legacy file"
    path.write_text(lesson.model_dump_json(),encoding="utf-8")
    new = lesson.model_copy(deep=True,update={"lesson_id":"aaa_"+uuid4().hex})
    (path.parent/f"{new.lesson_id}.json").write_text(new.model_dump_json(),encoding="utf-8")
    with pytest.raises(ValueError,match="IMPORT_CONFLICT"):
        import_lessons(directory,apply=True)
    assert ec.get_educational_lesson(OWNER,lesson.lesson_id).topic != lesson.topic
    assert ec.get_educational_lesson(OWNER,new.lesson_id) is None
    assert Path(artifact.video_path).exists()


def test_database_outage_is_safe_503_without_fallback(monkeypatch):
    postgres.close_pool()
    monkeypatch.setattr(settings,"lesson_persistence_provider","postgres")
    monkeypatch.setattr(settings,"postgres_dsn",SecretStr("host=127.0.0.1 port=1 dbname=missing user=nobody password=private-value"))
    monkeypatch.setattr(settings,"postgres_timeout_seconds",1)
    try:
        with TestClient(app) as client:
            pass
        pytest.fail("Startup accepted unavailable database")
    except postgres.VideoDatabaseError:
        pass
    finally:
        postgres.close_pool()
    # Without lifespan, health still safely classifies the unavailable service.
    try:
        response = TestClient(app).get("/health/database")
        assert response.status_code == 503
        assert "private-value" not in response.text and "127.0.0.1" not in response.text
    finally:
        postgres.close_pool()
