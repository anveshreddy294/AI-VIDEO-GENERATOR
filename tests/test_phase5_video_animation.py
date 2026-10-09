"""Comprehensive deterministic test suite for Phase 5: Educational Animation & Synchronized Narration.

Covers:
- Part 2: Structured scene planning (3–5 scenes for 20–30s lesson).
- Part 3: Secure rendering, arbitrary code execution protection, bounded lengths.
- Part 4: Voice & scene synchronization, TTS scaling, Whisper fallback, audio validation.
- Part 5: Source grounding vs AI-enriched provenance contracts.
- Part 6: Fast first-visual preview before final MP4 composition.
- Part 7: Reliable video jobs, restart recovery, retry when source is READY.
- Part 8: Stream endpoint path containment and HTTP 206 partial content.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.assessment.schemas import VideoTarget
from app.services.video import engine
from app.services.video.engine import (
    execute_video_generation_job,
    get_video_job,
    recover_interrupted_video_jobs,
)
from app.services.video.manim_renderer import render_video_plan
from app.services.video.scene_schema import (
    NarrationSegment,
    ScenePlan,
    SceneType,
    VideoArtifact,
    VideoJobStatus,
    VideoPlan,
)
from app.services.video.scene_validator import (
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    SceneValidationError,
    validate_scene_plan,
    validate_video_plan,
)
from app.services.video.tts import MockTTSProvider
from app.services.video.video_compositor import (
    composite_remedial_video,
    probe_media,
    validate_video_artifact,
)
from app.services.video.video_planner import plan_video_for_target


client = TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Structured Scene Planning (3–5 scenes for ~20–30s lesson)
# ---------------------------------------------------------------------------
def test_01_structured_scene_planning_bounded_3_to_5_scenes():
    target = VideoTarget(
        concept_id="CONCEPT_PHOTOSYNTHESIS",
        concept_name="Photosynthesis Light Reactions",
        difficulty="foundational",
        score=45.0,
        target_seconds=25,
        directive="Explain chlorophyll photon absorption and ATP synthesis in 25 seconds.",
        student_id="STU_PLAN_TEST",
        source_id="SRC_PLAN_TEST",
    )

    plan = plan_video_for_target(target)
    assert plan.concept_name == "Photosynthesis Light Reactions"
    assert plan.target_seconds == 25
    assert 3 <= len(plan.scenes) <= 5, f"Expected 3–5 scenes for 25s lesson, got {len(plan.scenes)}"

    total_duration = sum(s.duration_seconds for s in plan.scenes)
    assert 22.0 <= total_duration <= 28.0, f"Total duration {total_duration}s deviates too far from 25s"

    # Verify each scene has required structure and valid narration segment
    assert len(plan.narration) == len(plan.scenes)
    for idx, (scene, narr) in enumerate(zip(plan.scenes, plan.narration)):
        assert scene.scene_index == idx
        assert scene.scene_type in SceneType
        assert scene.duration_seconds >= 1.0
        assert narr.text and len(narr.text.strip()) > 0
        assert narr.scene_index == idx


# ---------------------------------------------------------------------------
# Test 2: Unsupported Scene Type Rejection
# ---------------------------------------------------------------------------
def test_02_unsupported_scene_type_rejection():
    with pytest.raises((SceneValidationError, ValueError)):
        invalid_scene = ScenePlan(
            scene_index=0,
            scene_type="UNSUPPORTED_3D_HOLOGRAM",  # Invalid type
            title="Invalid",
            duration_seconds=5.0,
        )
        validate_scene_plan(invalid_scene)


# ---------------------------------------------------------------------------
# Test 3: Bounded Text Length Enforcement
# ---------------------------------------------------------------------------
def test_03_bounded_text_lengths_enforced():
    # Title exceeds maximum length
    long_title = "A" * (MAX_TITLE_LENGTH + 10)
    scene_long_title = ScenePlan(
        scene_index=0,
        scene_type=SceneType.TITLE,
        title=long_title,
        duration_seconds=5.0,
    )
    with pytest.raises(SceneValidationError, match="title exceeds maximum"):
        validate_scene_plan(scene_long_title)

    # Text exceeds maximum length
    long_text = "B" * (MAX_TEXT_LENGTH + 50)
    scene_long_text = ScenePlan(
        scene_index=1,
        scene_type=SceneType.EXPLANATION,
        title="Valid Title",
        text=long_text,
        duration_seconds=5.0,
    )
    with pytest.raises(SceneValidationError, match="text exceeds maximum"):
        validate_scene_plan(scene_long_text)


# ---------------------------------------------------------------------------
# Test 4: Arbitrary Code Injection Protection
# ---------------------------------------------------------------------------
def test_04_arbitrary_code_injection_prevention():
    malicious_inputs = [
        "__import__('os').system('calc.exe')",
        "eval('__import__(\"subprocess\")')",
        "exec('open(\"/etc/passwd\").read()')",
        "<script>alert(1)</script>",
        "subprocess.Popen(['rm', '-rf', '/'])",
        "shutil.rmtree('/tmp')",
        "globals()['__builtins__']",
    ]

    for attack in malicious_inputs:
        # Injection in title
        scene_attack_title = ScenePlan(
            scene_index=0,
            scene_type=SceneType.TITLE,
            title=f"Valid Concept {attack}",
            duration_seconds=5.0,
        )
        with pytest.raises(SceneValidationError, match="Security violation"):
            validate_scene_plan(scene_attack_title)

        # Injection in visual_payload dictionary
        scene_attack_payload = ScenePlan(
            scene_index=1,
            scene_type=SceneType.DIAGRAM,
            title="Legitimate Title",
            visual_payload={"raw_code": attack},
            duration_seconds=5.0,
        )
        with pytest.raises(SceneValidationError, match="Security violation"):
            validate_scene_plan(scene_attack_payload)


# ---------------------------------------------------------------------------
# Test 5: Source Grounded vs AI-Enriched Provenance
# ---------------------------------------------------------------------------
def test_05_source_grounded_vs_ai_enriched_provenance():
    # Case A: Real evidence chunks provided -> SOURCE_GROUNDED
    target_grounded = VideoTarget(
        concept_id="CONCEPT_MEMBRANE",
        concept_name="Cell Membrane Structure",
        target_seconds=25,
        chunk_ids=["CHUNK_EVIDENCE_001", "CHUNK_EVIDENCE_002"],
        source_id="SRC_UPLOADED_BIOLOGY",
    )
    plan_grounded = plan_video_for_target(target_grounded)
    assert plan_grounded.provenance_kind == "SOURCE_GROUNDED"
    assert "CHUNK_EVIDENCE_001" in plan_grounded.source_chunk_ids

    # Case B: No uploaded source or evidence chunks -> AI_ENRICHED
    target_ai = VideoTarget(
        concept_id="CONCEPT_GENERAL_AI",
        concept_name="General Algorithm Complexity",
        target_seconds=25,
        chunk_ids=[],
        source_id="",
    )
    plan_ai = plan_video_for_target(target_ai)
    assert plan_ai.provenance_kind == "AI_ENRICHED"


# ---------------------------------------------------------------------------
# Test 6: Mathematical Symbols and Flowchart Render Safely
# ---------------------------------------------------------------------------
def test_06_mathematical_symbols_and_flowchart_diagrams_render_safely(tmp_path: Path):
    plan = VideoPlan(
        concept_id="CONCEPT_MATH_FLOW",
        concept_name="Kinetic Energy & Work Theorem",
        target_seconds=20,
        duration_seconds=20,
        scenes=[
            ScenePlan(
                scene_index=0,
                scene_type=SceneType.TITLE,
                title="Work-Energy Theorem",
                subtitle="Core Principles",
                duration_seconds=5.0,
            ),
            ScenePlan(
                scene_index=1,
                scene_type=SceneType.EQUATION,
                equation="W = \\Delta K = \\frac{1}{2} m v^2",
                label="Governing Equation",
                duration_seconds=5.0,
            ),
            ScenePlan(
                scene_index=2,
                scene_type=SceneType.DIAGRAM,
                title="Energy Conversion Flow",
                diagram_type="concept_flow",
                subtitle="Force Input",
                label="Kinetic State",
                duration_seconds=5.0,
            ),
            ScenePlan(
                scene_index=3,
                scene_type=SceneType.SUMMARY,
                summary_points=["Work equals change in kinetic energy", "Units in Joules (J)"],
                duration_seconds=5.0,
            ),
        ],
        narration=[
            NarrationSegment(scene_index=0, text="Welcome to Work Energy.", target_seconds=5.0),
            NarrationSegment(scene_index=1, text="The work energy equation states work equals delta K.", target_seconds=5.0),
            NarrationSegment(scene_index=2, text="Trace the energy transformation from input to output.", target_seconds=5.0),
            NarrationSegment(scene_index=3, text="Remember these core takeaways.", target_seconds=5.0),
        ],
    )

    out_mp4 = tmp_path / "math_flow.mp4"
    rendered = render_video_plan(plan, out_mp4)
    assert rendered.exists()
    assert rendered.stat().st_size > 5000

    probe = probe_media(rendered)
    v_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
    assert len(v_streams) > 0
    assert float(probe["format"]["duration"]) >= 15.0


# ---------------------------------------------------------------------------
# Test 7: TTS Duration Handling & Scene Synchronization
# ---------------------------------------------------------------------------
def test_07_tts_duration_scaling_and_scene_synchronization(tmp_path: Path):
    target = VideoTarget(
        concept_id="CONCEPT_SYNC_TEST",
        concept_name="Synchronized Narration Demo",
        target_seconds=20,
        student_id="STU_SYNC",
        source_id="SRC_SYNC",
    )

    artifact = asyncio.run(execute_video_generation_job(target, mock_mode=True, force=True))
    assert artifact.status == VideoJobStatus.COMPLETED
    assert artifact.video_path is not None

    final_mp4 = Path(artifact.video_path)
    assert final_mp4.exists()

    # Validate audio and video streams using compositor validation
    val = validate_video_artifact(final_mp4, expect_audio=True)
    assert val["duration"] >= 15.0
    assert val["video_codec"] is not None
    assert val["audio_codec"] is not None
    assert val["size"] > 10000


# ---------------------------------------------------------------------------
# Test 8: Missing or 0-Byte TTS Audio Fails Truthfully
# ---------------------------------------------------------------------------
def test_08_missing_or_empty_tts_audio_fails_truthfully(monkeypatch, tmp_path: Path):
    class BrokenTTSProvider:
        async def generate_audio(self, text: str, output_path: Path, target_seconds: float = 0.0) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"")  # 0-byte corrupt file
            return output_path

    monkeypatch.setattr(engine, "get_tts_provider", lambda *args, **kwargs: BrokenTTSProvider())

    target = VideoTarget(
        concept_id="CONCEPT_FAIL_AUDIO",
        concept_name="Missing Audio Test",
        target_seconds=20,
        student_id="STU_FAIL_AUDIO",
        source_id="SRC_FAIL_AUDIO",
    )

    artifact = asyncio.run(execute_video_generation_job(target, force=True))
    assert artifact.status == VideoJobStatus.FAILED
    assert "missing or 0 bytes" in (artifact.error or "").lower() or "no valid audio stream" in (artifact.error or "").lower()
    assert artifact.video_path is None


# ---------------------------------------------------------------------------
# Test 9: Optional Whisper Alignment Failure Degrades Gracefully
# ---------------------------------------------------------------------------
def test_09_optional_whisper_alignment_failure_degrades_gracefully(monkeypatch, tmp_path: Path):
    class FailingAligner:
        def align_and_transcribe(self, **kwargs):
            raise RuntimeError("Whisper model out of memory or unavailable")

    monkeypatch.setattr(engine, "get_whisper_aligner", lambda *args, **kwargs: FailingAligner())

    target = VideoTarget(
        concept_id="CONCEPT_WHISPER_FAIL",
        concept_name="Whisper Graceful Degradation",
        target_seconds=20,
        student_id="STU_WHISPER",
        source_id="SRC_WHISPER",
    )

    # Job must still succeed cleanly without subtitles
    artifact = asyncio.run(execute_video_generation_job(target, mock_mode=True, force=True))
    assert artifact.status == VideoJobStatus.COMPLETED
    assert artifact.video_path is not None
    assert Path(artifact.video_path).exists()
    assert artifact.subtitle_path is None or not Path(artifact.subtitle_path).exists()


# ---------------------------------------------------------------------------
# Test 10: FFmpeg Failure Fails Truthfully
# ---------------------------------------------------------------------------
def test_10_ffmpeg_composition_failure_fails_truthfully(tmp_path: Path):
    fake_video = tmp_path / "corrupt_video.mp4"
    fake_video.write_bytes(b"not a valid mp4 stream")

    fake_audio = tmp_path / "corrupt_audio.wav"
    fake_audio.write_bytes(b"not a valid wav stream")

    out_mp4 = tmp_path / "out.mp4"

    with pytest.raises(Exception):
        asyncio.run(composite_remedial_video(fake_video, fake_audio, out_mp4))


# ---------------------------------------------------------------------------
# Test 11: Video Job Idempotency and Force Override
# ---------------------------------------------------------------------------
def test_11_video_job_idempotency_and_force_override():
    target = VideoTarget(
        concept_id="CONCEPT_IDEMPOTENT",
        concept_name="Idempotency Test",
        target_seconds=20,
        student_id="STU_IDEM",
        source_id="SRC_IDEM",
    )

    # Run 1: initial render
    art1 = asyncio.run(execute_video_generation_job(target, mock_mode=True, force=True))
    assert art1.status == VideoJobStatus.COMPLETED

    # Run 2 with force=False: reuses existing completed artifact
    art2 = asyncio.run(execute_video_generation_job(target, mock_mode=True, force=False))
    assert art2.status == VideoJobStatus.COMPLETED
    assert Path(art2.video_path).exists()


# ---------------------------------------------------------------------------
# Test 12: READY Source with FAILED Video Allows Video Retry
# ---------------------------------------------------------------------------
def test_12_ready_source_with_failed_video_allows_video_retry(tmp_path: Path):
    # Setup: a failed video job record on disk
    failed_job_id = "JOB_FAILED_FOR_RETRY"
    failed_artifact = VideoArtifact(
        job_id=failed_job_id,
        student_id="student_123",
        source_id="SRC_READY_SOURCE",
        concept_id="CONCEPT_REMEDY",
        concept_name="Remedial Target",
        duration_seconds=25.0,
        status=VideoJobStatus.FAILED,
        stage="FAILED",
        error="Previous render timed out",
        retry_count=0,
    )
    settings.renders_dir.mkdir(parents=True, exist_ok=True)
    art_file = settings.renders_dir / f"{failed_job_id}_artifact.json"
    art_file.write_text(failed_artifact.model_dump_json(indent=2), encoding="utf-8")

    # API call to retry the video
    resp = client.post(f"/video/{failed_job_id}/retry")
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "QUEUED"
    assert data["concept_id"] == "CONCEPT_REMEDY"
    assert data["job_id"] != failed_job_id  # Fresh job ID issued for retry


# ---------------------------------------------------------------------------
# Test 13: Bounded Retry Limit (Max 3 retries)
# ---------------------------------------------------------------------------
def test_13_bounded_retry_limit():
    maxed_job_id = "JOB_MAXED_RETRIES"
    maxed_artifact = VideoArtifact(
        job_id=maxed_job_id,
        student_id="student_123",
        source_id="SRC_MAXED",
        concept_id="CONCEPT_MAXED",
        concept_name="Maxed Retries Target",
        duration_seconds=25.0,
        status=VideoJobStatus.FAILED,
        stage="FAILED",
        error="Previous render failed",
        retry_count=3,  # Already at retry limit
    )
    art_file = settings.renders_dir / f"{maxed_job_id}_artifact.json"
    art_file.write_text(maxed_artifact.model_dump_json(indent=2), encoding="utf-8")

    resp = client.post(f"/video/{maxed_job_id}/retry")
    assert resp.status_code == 429
    assert "Retry limit reached" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 14: Cross-User Media Access & Path Traversal Confinement
# ---------------------------------------------------------------------------
def test_14_cross_user_media_access_and_path_traversal_prevention(tmp_path: Path):
    # Create an artifact claiming video path outside renders_dir
    secret_file = tmp_path / "secret.mp4"
    secret_file.write_bytes(b"forbidden content")

    malicious_job_id = "JOB_TRAVERSAL"
    malicious_artifact = VideoArtifact(
        job_id=malicious_job_id,
        student_id="student_attacker",
        source_id="SRC_ATTACK",
        concept_id="CONCEPT_ATTACK",
        concept_name="Attack",
        duration_seconds=20.0,
        status=VideoJobStatus.COMPLETED,
        video_path=str(secret_file),  # Outside settings.renders_dir!
    )
    art_file = settings.renders_dir / f"{malicious_job_id}_artifact.json"
    art_file.write_text(malicious_artifact.model_dump_json(indent=2), encoding="utf-8")

    # Both stream and download endpoints must reject access to path outside renders_dir
    stream_resp = client.get(f"/video/{malicious_job_id}/stream")
    assert stream_resp.status_code == 404

    dl_resp = client.get(f"/video/{malicious_job_id}")
    assert dl_resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 15: Interrupted Rendering Recovery on Restart
# ---------------------------------------------------------------------------
def test_15_interrupted_rendering_recovery_on_restart():
    interrupted_id = "JOB_INTERRUPTED_RESTART"
    # An artifact left in RENDERING state on disk
    interrupted_artifact = VideoArtifact(
        job_id=interrupted_id,
        student_id="student_123",
        source_id="SRC_INTERRUPTED",
        concept_id="CONCEPT_INTERRUPTED",
        concept_name="Interrupted Concept",
        duration_seconds=25.0,
        status=VideoJobStatus.RENDERING,
        stage="Rendering Animation Scenes",
        progress=75,
    )
    art_file = settings.renders_dir / f"{interrupted_id}_artifact.json"
    art_file.write_text(interrupted_artifact.model_dump_json(indent=2), encoding="utf-8")

    # Evict from in-memory cache to simulate server process restart
    engine._ACTIVE_JOBS.pop(interrupted_id, None)

    # get_video_job should detect server restart and recover to truthful FAILED
    recovered = get_video_job(interrupted_id)
    assert recovered is not None
    assert recovered.status == VideoJobStatus.FAILED
    assert recovered.stage == "INTERRUPTED"
    assert "interrupted before completion" in (recovered.error or "").lower()


# ---------------------------------------------------------------------------
# Test 16: Fast First-Visual Preview Endpoint
# ---------------------------------------------------------------------------
def test_16_fast_first_visual_preview_endpoint():
    job_id = "JOB_PREVIEW_TEST"
    artifact = VideoArtifact(
        job_id=job_id,
        student_id="student_123",
        source_id="SRC_PREVIEW",
        concept_id="CONCEPT_PREVIEW",
        concept_name="Mitochondria ATP Synthase",
        duration_seconds=25.0,
        status=VideoJobStatus.RENDERING,
        preview={
            "concept_name": "Mitochondria ATP Synthase",
            "duration_seconds": 25,
            "learning_objective": "Understand proton gradients driving ATP synthase rotational catalysis.",
            "key_points": ["Proton electrochemical gradient", "F0 rotor rotation", "ATP catalytic formation"],
            "scenes": [
                {"scene_index": 0, "scene_type": "TITLE", "title": "ATP Synthase Mechanism", "duration_seconds": 5.0},
                {"scene_index": 1, "scene_type": "EXPLANATION", "title": "Gradient Dynamics", "duration_seconds": 10.0},
                {"scene_index": 2, "scene_type": "SUMMARY", "title": "Key Takeaways", "duration_seconds": 10.0},
            ],
        },
    )
    art_file = settings.renders_dir / f"{job_id}_artifact.json"
    art_file.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    engine._ACTIVE_JOBS[job_id] = artifact

    resp = client.get(f"/video/{job_id}/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["concept_name"] == "Mitochondria ATP Synthase"
    assert len(data["scenes"]) == 3
    assert "Proton electrochemical gradient" in data["key_points"]


# ---------------------------------------------------------------------------
# Test 17: Frontend Playback & HTTP 206 Partial Content Stream
# ---------------------------------------------------------------------------
def test_17_frontend_playback_and_stream_partial_content(tmp_path: Path):
    target = VideoTarget(
        concept_id="CONCEPT_STREAM_206",
        concept_name="Partial Content Streaming Demo",
        target_seconds=20,
        student_id="STU_STREAM",
        source_id="SRC_STREAM",
    )
    art = asyncio.run(execute_video_generation_job(target, mock_mode=True, force=True))
    assert art.status == VideoJobStatus.COMPLETED

    # Request first 500 bytes via HTTP Range
    resp = client.get(f"/video/{art.job_id}/stream", headers={"Range": "bytes=0-499"})
    assert resp.status_code == 206
    assert resp.headers["Content-Type"] == "video/mp4"
    assert "bytes 0-499/" in resp.headers["Content-Range"]
    assert len(resp.content) == 500
