"""Step 3 Video Engine & Deterministic Manim Pipeline Test Suite.

Tests:
1. VideoPlan schema & scene validator (allowed scene types, bounds, code injection prevention)
2. Video planner generating structured scene plans from VideoTarget
3. Deterministic Manim / programmatic video rendering smoke test
4. TTS audio generation smoke test
5. Whisper alignment and SRT caption generation smoke test
6. Video compositor combining video + audio + subtitles
7. Step 3 FastAPI endpoints (/video/generate, /video/status, /video/captions, /video/{job_id})
"""

import asyncio
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.assessment.schemas import VideoTarget
from app.services.video.engine import execute_video_generation_job, get_video_job
from app.services.video.manim_renderer import render_video_plan
from app.services.video.narration import extract_narration_script
from app.services.video.scene_schema import (
    NarrationSegment,
    ScenePlan,
    SceneType,
    VideoArtifact,
    VideoJobStatus,
    VideoPlan,
)
from app.services.video.scene_validator import SceneValidationError, validate_video_plan
from app.services.video.tts import MockTTSProvider, get_tts_provider
from app.services.video.video_compositor import composite_remedial_video
from app.services.video.video_planner import plan_video_for_target
from app.services.video.whisper_alignment import MockWhisperAligner


@pytest.fixture
def sample_video_plan() -> VideoPlan:
    """Create a valid sample VideoPlan for testing."""
    return VideoPlan(
        student_id="STU_TEST_01",
        source_id="SRC_PHYSICS_101",
        concept_id="CONCEPT_NEWTON_2",
        concept_name="Newton's Second Law",
        duration_seconds=12,
        difficulty="intermediate",
        learning_objective="Understand F = ma relationship",
        key_points=["Force causes acceleration", "Mass resists acceleration"],
        scenes=[
            ScenePlan(
                scene_index=0,
                scene_type=SceneType.TITLE,
                title="Newton's Second Law",
                subtitle="Force, Mass, and Acceleration",
                duration_seconds=3.0,
            ),
            ScenePlan(
                scene_index=1,
                scene_type=SceneType.EQUATION,
                equation="F = ma",
                label="Fundamental Law of Dynamics",
                duration_seconds=3.0,
            ),
            ScenePlan(
                scene_index=2,
                scene_type=SceneType.DIAGRAM,
                diagram_type="force_box",
                object_label="Mass (m)",
                force_label="Force (F)",
                duration_seconds=3.0,
            ),
            ScenePlan(
                scene_index=3,
                scene_type=SceneType.SUMMARY,
                summary_points=["Force accelerates mass", "F = ma connects them"],
                duration_seconds=3.0,
            ),
        ],
        narration=[
            NarrationSegment(scene_index=0, text="Welcome to Newton's Second Law.", target_seconds=3.0),
            NarrationSegment(scene_index=1, text="Force equals mass times acceleration.", target_seconds=3.0),
            NarrationSegment(scene_index=2, text="An applied force changes velocity.", target_seconds=3.0),
            NarrationSegment(scene_index=3, text="Remember this fundamental relationship.", target_seconds=3.0),
        ],
        provenance_chunks=["CHUNK_001", "CHUNK_002"],
    )


def test_videoplan_schema_and_validator(sample_video_plan: VideoPlan):
    """Test 1: Schema validation passes for valid plans and rejects code injection."""
    validated = validate_video_plan(sample_video_plan)
    assert validated.concept_id == "CONCEPT_NEWTON_2"
    assert len(validated.scenes) == 4

    # Test rejection of code injection
    bad_plan = sample_video_plan.model_copy(deep=True)
    bad_plan.scenes[0].title = "Malicious __import__('os').system('ls')"
    with pytest.raises(SceneValidationError, match="dangerous substring"):
        validate_video_plan(bad_plan)


def test_video_planner_generation():
    """Test 2: Video planner generates a valid VideoPlan from VideoTarget."""
    target = VideoTarget(
        concept_id="CONCEPT_NEWTON_2",
        concept_name="Newton's Second Law",
        difficulty="intermediate",
        score=35.0,
        target_seconds=45,
        directive="Generate a 45-second AI video explaining Newton's Second Law",
        chunk_ids=["CHUNK_001"],
        source_content_ids=["CU_001"],
        student_id="STU_TEST_01",
        source_id="SRC_TEST_PHYSICS",
    )
    plan = plan_video_for_target(target)
    assert plan.concept_id == "CONCEPT_NEWTON_2"
    assert plan.duration_seconds == 45
    assert len(plan.scenes) >= 3
    assert len(plan.narration) >= 3


def test_tts_generation_smoke(tmp_path: Path):
    """Test 3: TTS provider generates a valid audio WAV file."""
    tts = MockTTSProvider()
    out_wav = tmp_path / "test_narr.wav"
    res = asyncio.run(tts.generate_audio("Hello, this is a test narration.", out_wav, target_seconds=4.0))
    assert res.exists()
    assert res.stat().st_size > 4000  # Valid non-empty audio header + PCM bytes


def test_whisper_alignment_smoke(tmp_path: Path):
    """Test 4: Whisper aligner generates standard SRT subtitles and QA check."""
    out_wav = tmp_path / "audio.wav"
    asyncio.run(MockTTSProvider().generate_audio("Testing captions alignment.", out_wav, target_seconds=4.0))
    out_srt = tmp_path / "captions.srt"

    aligner = MockWhisperAligner()
    meta = aligner.align_and_transcribe(
        audio_path=out_wav,
        expected_narration="Testing captions alignment.",
        output_srt=out_srt,
    )
    assert out_srt.exists()
    assert "00:00:00" in out_srt.read_text(encoding="utf-8")
    assert meta["qa_passed"] is True
    assert meta["qa_score"] == 1.0


def test_manim_renderer_smoke(sample_video_plan: VideoPlan, tmp_path: Path):
    """Test 5: Deterministic renderer outputs a playable MP4 video."""
    out_mp4 = tmp_path / "test_scene.mp4"
    # Use 4-second quick render
    plan = sample_video_plan.model_copy(deep=True)
    for s in plan.scenes:
        s.duration_seconds = 1.0
    res = render_video_plan(plan, out_mp4)
    assert res.exists()
    assert res.stat().st_size > 1000  # Non-empty MP4 container


def test_video_compositor_smoke(sample_video_plan: VideoPlan, tmp_path: Path):
    """Test 6: Compositor merges video + audio into final MP4."""
    vid_mp4 = tmp_path / "raw_video.mp4"
    render_video_plan(sample_video_plan, vid_mp4)

    aud_wav = tmp_path / "raw_audio.wav"
    asyncio.run(MockTTSProvider().generate_audio("Narration text", aud_wav, target_seconds=3.0))

    final_mp4 = tmp_path / "final_remedial.mp4"
    asyncio.run(composite_remedial_video(vid_mp4, aud_wav, final_mp4))
    assert final_mp4.exists()
    assert final_mp4.stat().st_size > 1000


def test_step3_fastapi_endpoints(sample_video_plan: VideoPlan, tmp_path: Path):
    """Test 7: Step 3 FastAPI endpoints (/video/generate, /video/status, /video/captions, /video/{job_id})."""
    client = TestClient(app)

    # Test health check
    health_resp = client.get("/health/video")
    assert health_resp.status_code == 200
    assert health_resp.json()["service"] == "Step 3 Video Engine"

    # Enqueue a mock generation job
    gen_payload = {
        "student_id": "STU_API_TEST",
        "source_id": "SRC_API_TEST",
        "concept_id": "CONCEPT_NEWTON_2",
        "concept_name": "Newton's Second Law",
        "difficulty": "intermediate",
        "target_seconds": 10,
        "score": 40.0,
        "mock_mode": True,
    }
    resp = client.post("/video/generate", json=gen_payload)
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    job_id = data["job_id"]
    assert data["status"] == "QUEUED"

    # Query status
    status_resp = client.get(f"/video/status/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["job_id"] == job_id
    assert status_data["concept_id"] == "CONCEPT_NEWTON_2"
