"""Canonical execution never enters legacy planning, JSON or vector persistence."""
import asyncio
import pytest
from app.services.video import engine
from app.services.video.scene_schema import VideoArtifact, VideoPlan, VideoJobStatus
from app.services.assessment.schemas import VideoTarget


def test_canonical_adapter_preserves_failure_without_legacy_fallback(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Canonical execution entered legacy storage")
    for name in ("require_local_learning_storage", "find_existing_video", "_save_video_artifact", "plan_video_for_target", "store_video_artifacts"):
        monkeypatch.setattr(engine, name, forbidden)
    monkeypatch.setattr(engine.job_manager, "get_semaphore", lambda: asyncio.Semaphore(1))
    saved = []
    class Adapter:
        def plan(self, target: VideoTarget) -> VideoPlan:
            raise RuntimeError("Grounded plan unavailable")
        def save(self, artifact: VideoArtifact) -> None:
            saved.append(artifact.model_copy(deep=True))
    result = asyncio.run(engine.execute_video_generation_job(
        VideoTarget(concept_id="c", concept_name="Cell", source_id="owned"),
        job_id="canonical", canonical=Adapter(),
    ))
    assert [item.status for item in saved] == [VideoJobStatus.QUEUED, VideoJobStatus.PLANNING, VideoJobStatus.FAILED]
    assert result.status == VideoJobStatus.FAILED
    assert result.video_path is None


from types import SimpleNamespace
from uuid import uuid4
from app.services.video.session_video import SessionVideo
from app.services.repositories.knowledge_repository import KnowledgeError


def test_video_status_never_exposes_private_metadata():
    video = dict(job_id="v",status="FAILED",stage="FAILED",progress=0,duration_seconds=0,
                 video_path="private/path",error="provider secret",plan={"hidden":"body"})
    value = SessionVideo.view(video).model_dump()
    assert set(value) == {"job_id","status","stage","progress","duration_seconds","error_code"}
    assert value["error_code"] == "VIDEO_RENDER_FAILED"


def test_video_rpc_owner_and_session_are_backend_authority():
    owner,sid = uuid4(),uuid4()
    calls=[]
    class Runtime:
        def admin_request(self,*args,**kwargs):
            calls.append(kwargs["body"])
            return {"video":{"user_id":str(uuid4()),"output_metadata":{}}}
    adapter=SessionVideo(SimpleNamespace(user=SimpleNamespace(user_id=owner),runtime=Runtime()),sid,"r")
    with pytest.raises(KnowledgeError,match="INVALID_PROVIDER_RESPONSE"):
        adapter.get()
    assert calls[0]["p_user_id"] == str(owner)
    assert calls[0]["p_learning_session_id"] == str(sid)


def test_stream_rejects_outside_render_root(monkeypatch,tmp_path):
    adapter=SessionVideo(SimpleNamespace(),uuid4(),"r")
    private=tmp_path/"private.mp4";private.write_bytes(b"not public")
    monkeypatch.setattr(engine.settings,"renders_dir",tmp_path/"renders")
    monkeypatch.setattr(adapter,"get",lambda:{"status":"COMPLETED","video_path":str(private)})
    with pytest.raises(KnowledgeError,match="NOT_READY"):
        adapter.stream_path()


def test_canonical_speech_never_accepts_synthetic_fallback(monkeypatch):
    from app.services.video.tts import get_tts_provider, EdgeTTSProvider
    assert get_tts_provider("edge_tts",require_spoken=True).allow_fallback is False
    with pytest.raises(RuntimeError,match="SPOKEN_TTS_UNAVAILABLE"):
        get_tts_provider("local",require_spoken=True)
    assert isinstance(get_tts_provider("edge_tts"),EdgeTTSProvider)


def test_completed_status_reports_actual_duration_without_terminal_write(monkeypatch, tmp_path):
    from app.services.video import session_video
    adapter = SessionVideo(SimpleNamespace(), uuid4(), "r")
    media = tmp_path / "completed.mp4"
    media.write_bytes(b"fixture")
    monkeypatch.setattr(session_video.settings, "renders_dir", tmp_path)
    monkeypatch.setattr(adapter, "get", lambda: dict(job_id="v", status="COMPLETED",
        stage="COMPLETED", progress=100, duration_seconds=8, video_path=str(media)))
    monkeypatch.setattr(adapter, "save", lambda _: pytest.fail("Terminal row modified"))
    monkeypatch.setattr(session_video, "validate_video_artifact", lambda path, expect_audio: {"duration": 4.0})
    result = adapter.status()
    assert result.duration_seconds == 4.0
    assert "video_path" not in result.model_dump()


def test_completed_status_fails_closed_for_missing_artifact(monkeypatch, tmp_path):
    adapter = SessionVideo(SimpleNamespace(), uuid4(), "r")
    monkeypatch.setattr(adapter, "get", lambda: dict(job_id="v", status="COMPLETED",
        stage="COMPLETED", progress=100, duration_seconds=8, video_path=str(tmp_path / "missing.mp4")))
    with pytest.raises(KnowledgeError, match="NOT_READY"):
        adapter.status()
