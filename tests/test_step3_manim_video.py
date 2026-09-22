"""Step 3 Video Engine & Deterministic Manim Pipeline Test Suite.

Complete 20-test suite covering Section 31 requirements:
1. VideoPlan schema validation.
2. Invalid duration rejection.
3. Invalid scene type rejection.
4. Invalid LaTeX handling.
5. Grounding/provenance preservation.
6. 30-second foundational plan.
7. 45-second intermediate plan.
8. 60-second advanced plan.
9. Manim renderer test.
10. TTS mock test.
11. Whisper alignment test.
12. FFmpeg compositor test.
13. Final MP4 existence.
14. Final MP4 duration validation.
15. Subtitle generation.
16. Human fallback concept rejection.
17. Missing VideoTargetMatrix rejection.
18. Invalid source_id rejection.
19. Ollama unavailable fallback.
20. End-to-end single concept video generation.
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import cv2

from app.core.config import settings
from app.main import app
from app.services.assessment.profile import save_profile
from app.services.assessment.schemas import (
    ConceptMastery,
    StudentLearningProfile,
    VideoTarget,
)
from app.services.assessment.video_target import save_video_matrix
from app.services.video.artifact_store import get_video_dir, get_metadata
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
from app.services.video.scene_validator import (
    SceneValidationError,
    validate_latex,
    validate_scene_plan,
    validate_video_plan,
)
from app.services.video.tts import MockTTSProvider, get_tts_provider
from app.services.video.video_compositor import composite_remedial_video
from app.services.video.video_planner import plan_video_for_target
from app.services.video.whisper_alignment import MockWhisperAligner, get_whisper_aligner


@pytest.fixture
def sample_video_plan() -> VideoPlan:
    """Create a valid sample VideoPlan for testing."""
    return VideoPlan(
        student_id="STU_TEST_01",
        source_id="SRC_PHYSICS_101",
        concept_id="CONCEPT_NEWTON_2",
        concept_name="Newton's Second Law",
        definition="Net force equals mass times acceleration: F = ma.",
        duration_seconds=30,
        target_seconds=30,
        difficulty="foundational",
        learning_objective="Understand F = ma relationship",
        key_points=["Force causes acceleration", "Mass resists acceleration"],
        scenes=[
            ScenePlan(
                scene_index=0,
                scene_type=SceneType.TITLE,
                title="Newton's Second Law",
                subtitle="Force, Mass, and Acceleration",
                duration_seconds=4.0,
                source_chunk_ids=["CHUNK_001"],
            ),
            ScenePlan(
                scene_index=1,
                scene_type=SceneType.EXPLANATION,
                title="Core Concept",
                text="Force equals mass times acceleration.",
                duration_seconds=8.0,
                source_chunk_ids=["CHUNK_001"],
            ),
            ScenePlan(
                scene_index=2,
                scene_type=SceneType.EQUATION,
                title="Fundamental Equation",
                equation="F = ma",
                label="Fundamental Law of Dynamics",
                duration_seconds=8.0,
                source_chunk_ids=["CHUNK_002"],
            ),
            ScenePlan(
                scene_index=3,
                scene_type=SceneType.EXAMPLE,
                title="Real-world Example",
                text="Pushing a shopping cart accelerates it proportionally to the applied force.",
                duration_seconds=6.0,
                source_chunk_ids=["CHUNK_002"],
            ),
            ScenePlan(
                scene_index=4,
                scene_type=SceneType.SUMMARY,
                title="Key Takeaways",
                summary_points=["Force accelerates mass", "F = ma connects them"],
                duration_seconds=4.0,
                source_chunk_ids=["CHUNK_001", "CHUNK_002"],
            ),
        ],
        narration=[
            NarrationSegment(scene_index=0, text="Welcome to Newton's Second Law.", target_seconds=4.0),
            NarrationSegment(scene_index=1, text="Force is an interaction causing acceleration.", target_seconds=8.0),
            NarrationSegment(scene_index=2, text="Force equals mass times acceleration: F equals m a.", target_seconds=8.0),
            NarrationSegment(scene_index=3, text="A greater push accelerates an object faster.", target_seconds=6.0),
            NarrationSegment(scene_index=4, text="Remember this fundamental relationship in dynamics.", target_seconds=4.0),
        ],
        source_chunk_ids=["CHUNK_001", "CHUNK_002"],
        provenance_chunks=["CHUNK_001", "CHUNK_002"],
        provenance={"chunks": ["CHUNK_001", "CHUNK_002"], "pages": [1, 2]},
    )


# ===========================================================================
# 1. VideoPlan schema validation & code injection prevention
# ===========================================================================
def test_01_videoplan_schema_validation(sample_video_plan: VideoPlan):
    """Test 1: Schema validation passes for valid plans and rejects code injection."""
    validated = validate_video_plan(sample_video_plan)
    assert validated.concept_id == "CONCEPT_NEWTON_2"
    assert validated.target_seconds == 30
    assert validated.definition is not None
    assert len(validated.scenes) == 5

    # Test rejection of code injection in titles
    bad_plan = sample_video_plan.model_copy(deep=True)
    bad_plan.scenes[0].title = "Malicious __import__('os').system('ls')"
    with pytest.raises(SceneValidationError, match="dangerous substring"):
        validate_video_plan(bad_plan)

    # Test rejection of code injection in narration
    bad_narr_plan = sample_video_plan.model_copy(deep=True)
    bad_narr_plan.narration[0].text = "Let us run eval('1+1') here"
    with pytest.raises(SceneValidationError, match="dangerous substring"):
        validate_video_plan(bad_narr_plan)


# ===========================================================================
# 2. Invalid duration rejection
# ===========================================================================
def test_02_invalid_duration_rejection(sample_video_plan: VideoPlan):
    """Test 2: Rejects plans where scene durations deviate significantly from target."""
    bad_plan = sample_video_plan.model_copy(deep=True)
    # Target is 30s, but make scenes sum to 90s
    for s in bad_plan.scenes:
        s.duration_seconds = 18.0
    with pytest.raises(SceneValidationError, match="deviates significantly"):
        validate_video_plan(bad_plan)

    # Rejects negative or zero duration scenes
    bad_scene_plan = sample_video_plan.model_copy(deep=True)
    bad_scene_plan.scenes[0].duration_seconds = 0
    with pytest.raises(SceneValidationError, match="outside valid range"):
        validate_video_plan(bad_scene_plan)


# ===========================================================================
# 3. Invalid scene type rejection
# ===========================================================================
def test_03_invalid_scene_type_rejection():
    """Test 3: Rejects invalid/unsupported scene types."""
    with pytest.raises(Exception):
        ScenePlan(
            scene_index=0,
            scene_type="EXPLODING_3D_ROBOT",  # type: ignore
            title="Invalid",
            duration_seconds=5.0,
        )


# ===========================================================================
# 4. Invalid LaTeX handling
# ===========================================================================
def test_04_invalid_latex_handling(sample_video_plan: VideoPlan):
    """Test 4: Catches unbalanced curly braces and invalid LaTeX notation."""
    # Unbalanced braces
    with pytest.raises(SceneValidationError, match="unbalanced curly braces"):
        validate_latex(r"\frac{a}{b")

    # Trailing backslash
    with pytest.raises(SceneValidationError, match="trailing backslash"):
        validate_latex(r"F = ma \\")

    # Valid LaTeX passes smoothly
    validate_latex(r"\frac{d v}{d t} = a")
    validate_latex(r"F = m \cdot a")

    # Check that scene validator enforces LaTeX validation
    bad_eq_plan = sample_video_plan.model_copy(deep=True)
    bad_eq_plan.scenes[2].equation = r"F = \frac{m}{a"
    with pytest.raises(SceneValidationError, match="unbalanced curly braces"):
        validate_video_plan(bad_eq_plan)


# ===========================================================================
# 5. Grounding / provenance preservation
# ===========================================================================
def test_05_grounding_provenance_preservation():
    """Test 5: VideoTarget chunk IDs, content IDs, and page ranges survive planning."""
    target = VideoTarget(
        concept_id="CONCEPT_NEWTON_2",
        concept_name="Newton's Second Law",
        difficulty="foundational",
        score=30.0,
        target_seconds=30,
        directive="Explain Newton's Second Law",
        chunk_ids=["CHUNK_A1", "CHUNK_A2"],
        source_content_ids=["CU_001"],
        page_start=12,
        page_end=14,
        student_id="STU_PROV_01",
        source_id="SRC_PROV_01",
    )
    plan = plan_video_for_target(target)
    assert "CHUNK_A1" in plan.source_chunk_ids or "CHUNK_A1" in plan.provenance_chunks
    assert plan.student_id == "STU_PROV_01"
    assert plan.source_id == "SRC_PROV_01"
    assert plan.page_start == 12
    assert plan.page_end == 14
    assert len(plan.scenes) > 0
    # Every scene should have chunk references
    for s in plan.scenes:
        assert s.source_chunk_ids is not None


# ===========================================================================
# 6. 30-second foundational plan
# ===========================================================================
def test_06_foundational_plan_30s():
    """Test 6: Foundational concept generates a compliant ~30s pedagogical plan."""
    target = VideoTarget(
        concept_id="CONCEPT_FOUNDATION",
        concept_name="Velocity and Speed",
        difficulty="foundational",
        score=35.0,
        target_seconds=30,
        directive="Explain velocity",
        chunk_ids=["CHUNK_F1"],
        source_content_ids=["CU_F1"],
        student_id="STU_01",
        source_id="SRC_01",
    )
    plan = plan_video_for_target(target)
    assert plan.target_seconds == 30
    total_dur = sum(s.duration_seconds for s in plan.scenes)
    assert 28.0 <= total_dur <= 32.0

    scene_types = [s.scene_type for s in plan.scenes]
    assert SceneType.TITLE in scene_types
    assert SceneType.SUMMARY in scene_types


# ===========================================================================
# 7. 45-second intermediate plan
# ===========================================================================
def test_07_intermediate_plan_45s():
    """Test 7: Intermediate concept generates a compliant ~45s pedagogical plan."""
    target = VideoTarget(
        concept_id="CONCEPT_INTERMEDIATE",
        concept_name="Work and Kinetic Energy",
        difficulty="intermediate",
        score=40.0,
        target_seconds=45,
        directive="Explain work and energy theorem",
        chunk_ids=["CHUNK_I1"],
        source_content_ids=["CU_I1"],
        student_id="STU_01",
        source_id="SRC_01",
    )
    plan = plan_video_for_target(target)
    assert plan.target_seconds == 45
    total_dur = sum(s.duration_seconds for s in plan.scenes)
    assert 42.0 <= total_dur <= 48.0


# ===========================================================================
# 8. 60-second advanced plan
# ===========================================================================
def test_08_advanced_plan_60s():
    """Test 8: Advanced concept generates a compliant ~60s pedagogical plan."""
    target = VideoTarget(
        concept_id="CONCEPT_ADVANCED",
        concept_name="Rotational Dynamics and Angular Momentum",
        difficulty="advanced",
        score=25.0,
        target_seconds=60,
        directive="Explain angular momentum conservation",
        chunk_ids=["CHUNK_ADV1"],
        source_content_ids=["CU_ADV1"],
        student_id="STU_01",
        source_id="SRC_01",
    )
    plan = plan_video_for_target(target)
    assert plan.target_seconds == 60
    total_dur = sum(s.duration_seconds for s in plan.scenes)
    assert 57.0 <= total_dur <= 63.0


# ===========================================================================
# 9. Manim renderer test
# ===========================================================================
def test_09_manim_renderer_test(sample_video_plan: VideoPlan, tmp_path: Path):
    """Test 9: Deterministic renderer creates a valid MP4 video container."""
    out_mp4 = tmp_path / "manim_test.mp4"
    fast_plan = sample_video_plan.model_copy(deep=True)
    for s in fast_plan.scenes:
        s.duration_seconds = 1.0
    fast_plan.duration_seconds = len(fast_plan.scenes)
    fast_plan.target_seconds = len(fast_plan.scenes)

    rendered = render_video_plan(fast_plan, out_mp4)
    assert rendered.exists()
    assert rendered.stat().st_size > 1000  # Non-empty playable MP4 container


# ===========================================================================
# 10. TTS mock test
# ===========================================================================
def test_10_tts_mock_test(tmp_path: Path):
    """Test 10: TTS provider generates a compliant PCM audio WAV file."""
    tts = MockTTSProvider()
    out_wav = tmp_path / "mock_narration.wav"
    res = asyncio.run(tts.generate_audio("Testing audio synthesis", out_wav, target_seconds=3.0))
    assert res.exists()
    assert res.stat().st_size > 2000
    # Check RIFF header
    with open(res, "rb") as f:
        header = f.read(4)
        assert header == b"RIFF"


# ===========================================================================
# 11. Whisper alignment test
# ===========================================================================
def test_11_whisper_alignment_test(tmp_path: Path):
    """Test 11: Whisper aligner transcribes and generates word-level SRT timestamps."""
    out_wav = tmp_path / "speech.wav"
    asyncio.run(MockTTSProvider().generate_audio("First line. Second line.", out_wav, target_seconds=4.0))
    out_srt = tmp_path / "captions.srt"

    aligner = MockWhisperAligner()
    meta = aligner.align_and_transcribe(
        audio_path=out_wav,
        expected_narration="First line. Second line.",
        output_srt=out_srt,
    )
    assert out_srt.exists()
    content = out_srt.read_text(encoding="utf-8")
    assert "00:00:00,000 -->" in content
    assert "words" in meta
    assert len(meta["words"]) > 0


# ===========================================================================
# 12. FFmpeg compositor test
# ===========================================================================
def test_12_ffmpeg_compositor_test(sample_video_plan: VideoPlan, tmp_path: Path):
    """Test 12: FFmpeg compositor combines visual video and audio WAV into MP4."""
    vid_mp4 = tmp_path / "raw_video.mp4"
    render_video_plan(sample_video_plan, vid_mp4)

    aud_wav = tmp_path / "raw_audio.wav"
    asyncio.run(MockTTSProvider().generate_audio("Compositing test narration", aud_wav, target_seconds=3.0))

    final_mp4 = tmp_path / "composited.mp4"
    asyncio.run(composite_remedial_video(vid_mp4, aud_wav, final_mp4))
    assert final_mp4.exists()
    assert final_mp4.stat().st_size > 1000


# ===========================================================================
# 13. Final MP4 existence
# ===========================================================================
def test_13_final_mp4_existence():
    """Test 13: Job execution outputs a real, existing MP4 file on disk."""
    target = VideoTarget(
        concept_id="CONCEPT_NEWTON_2",
        concept_name="Newton's Second Law",
        difficulty="foundational",
        score=35.0,
        target_seconds=10,
        directive="Explain F = ma",
        chunk_ids=["CHUNK_001"],
        source_content_ids=["CU_001"],
        student_id="STU_EXIST_TEST",
        source_id="SRC_EXIST_TEST",
    )
    artifact = asyncio.run(execute_video_generation_job(target, mock_mode=True))
    assert artifact.status == VideoJobStatus.COMPLETED
    assert artifact.video_path is not None
    assert Path(artifact.video_path).exists()
    assert Path(artifact.video_path).stat().st_size > 2000


# ===========================================================================
# 14. Final MP4 duration validation
# ===========================================================================
def test_14_final_mp4_duration_validation():
    """Test 14: Composited video duration matches expected plan duration."""
    target = VideoTarget(
        concept_id="CONCEPT_DURATION_TEST",
        concept_name="Newton's Second Law",
        difficulty="foundational",
        score=40.0,
        target_seconds=10,
        directive="Short 10s video",
        chunk_ids=["CHUNK_001"],
        source_content_ids=["CU_001"],
        student_id="STU_DUR_TEST",
        source_id="SRC_DUR_TEST",
    )
    artifact = asyncio.run(execute_video_generation_job(target, mock_mode=True))
    assert artifact.video_path is not None
    mp4_path = Path(artifact.video_path)
    assert mp4_path.exists()

    cap = cv2.VideoCapture(str(mp4_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()

    duration = frame_count / fps if fps > 0 else 0
    # Tolerance allows small container header differences (duration should be within 3s of 10s)
    assert 7.0 <= duration <= 13.0


# ===========================================================================
# 15. Subtitle generation
# ===========================================================================
def test_15_subtitle_generation(tmp_path: Path):
    """Test 15: Subtitle SRT file is properly formatted with numbered blocks."""
    out_wav = tmp_path / "sub_test.wav"
    asyncio.run(MockTTSProvider().generate_audio("Hello world from remedial video.", out_wav, target_seconds=3.0))
    out_srt = tmp_path / "test.srt"
    aligner = MockWhisperAligner()
    aligner.align_and_transcribe(out_wav, "Hello world from remedial video.", out_srt)

    assert out_srt.exists()
    lines = [line.strip() for line in out_srt.read_text(encoding="utf-8").splitlines() if line.strip()]
    # SRT structure: first line is '1', second line is timestamp '-->', third line is text
    assert lines[0] == "1"
    assert "-->" in lines[1]
    assert "Hello" in lines[2]


# ===========================================================================
# 16. Human fallback concept rejection
# ===========================================================================
def test_16_human_fallback_concept_rejection():
    """Test 16: Concepts marked REQUIRES_HUMAN_FALLBACK cannot generate videos."""
    student_id = "STU_FALLBACK_TEST"
    source_id = "SRC_FALLBACK_TEST"
    cid = "CONCEPT_FAILED_3X"

    # Create profile with human fallback status
    profile = StudentLearningProfile(student_id=student_id, source_id=source_id)
    profile.concept_masteries[cid] = ConceptMastery(
        concept_id=cid,
        concept_name="Difficult Topology",
        status="REQUIRES_HUMAN_FALLBACK",
        attempt_count=3,
        last_score=10.0,
    )
    save_profile(profile)

    client = TestClient(app)
    resp = client.post(
        "/video/generate",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "concept_id": cid,
            "mock_mode": True,
        },
    )
    assert resp.status_code == 400
    assert "human instructor intervention" in resp.json()["detail"].lower()


# ===========================================================================
# 17. Missing VideoTargetMatrix rejection
# ===========================================================================
def test_17_missing_video_target_matrix_rejection():
    """Test 17: Batch generation without concept_id fails if no matrix exists."""
    client = TestClient(app)
    resp = client.post(
        "/video/generate",
        json={
            "student_id": "STU_UNKNOWN_999",
            "source_id": "SRC_UNKNOWN_999",
            "mock_mode": True,
        },
    )
    assert resp.status_code == 404
    assert "no unmastered video targets found" in resp.json()["detail"].lower()


# ===========================================================================
# 18. Invalid source_id rejection
# ===========================================================================
def test_18_invalid_source_id_rejection():
    """Test 18: Rejects non-existent source_id when mock_mode is False."""
    client = TestClient(app)
    resp = client.post(
        "/video/generate",
        json={
            "student_id": "STU_TEST_01",
            "source_id": "SRC_NON_EXISTENT_99999",
            "concept_id": "CONCEPT_WHATEVER",
            "mock_mode": False,
        },
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ===========================================================================
# 19. Ollama unavailable fallback
# ===========================================================================
def test_19_ollama_unavailable_fallback(monkeypatch):
    """Test 19: System uses deterministic template fallback when Ollama is unavailable."""
    monkeypatch.setattr(settings, "llm_provider", "mock")
    target = VideoTarget(
        concept_id="CONCEPT_FALLBACK_SMOKE",
        concept_name="Electromagnetic Waves",
        difficulty="intermediate",
        score=30.0,
        target_seconds=45,
        directive="Explain EM waves",
        chunk_ids=["CHUNK_EM1"],
        source_content_ids=["CU_EM1"],
        student_id="STU_01",
        source_id="SRC_01",
    )
    plan = plan_video_for_target(target)
    assert plan.concept_id == "CONCEPT_FALLBACK_SMOKE"
    assert plan.duration_seconds == 45
    assert len(plan.scenes) >= 4
    # Must pass validation without raising
    validated = validate_video_plan(plan)
    assert validated is not None


# ===========================================================================
# 20. End-to-end single concept video generation & artifact persistence
# ===========================================================================
def test_20_end_to_end_single_concept_video_generation():
    """Test 20: Full pipeline generates and persists all canonical artifacts."""
    student_id = "STU_E2E_CANONICAL"
    source_id = "SRC_E2E_CANONICAL"
    cid = "CONCEPT_CENTRIPETAL"

    target = VideoTarget(
        concept_id=cid,
        concept_name="Centripetal Acceleration",
        difficulty="foundational",
        score=35.0,
        target_seconds=10,
        directive="Explain centripetal acceleration",
        chunk_ids=["CHUNK_CENT_1"],
        source_content_ids=["CU_CENT_1"],
        student_id=student_id,
        source_id=source_id,
    )

    artifact = asyncio.run(execute_video_generation_job(target, mock_mode=True, force=True))
    assert artifact.status == VideoJobStatus.COMPLETED

    # Check canonical persistent storage directory
    vdir = get_video_dir(student_id, source_id, cid)
    assert vdir.exists()
    assert (vdir / "final.mp4").exists()
    assert (vdir / "metadata.json").exists()
    assert (vdir / "video_plan.json").exists()
    assert (vdir / "subtitles.srt").exists()
    assert (vdir / "narration.txt").exists()

    meta = json.loads((vdir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["student_id"] == student_id
    assert meta["source_id"] == source_id
    assert meta["concept_id"] == cid
    assert meta["status"] == "COMPLETED"
    assert "source_chunk_ids" in meta


# ===========================================================================
# 21. Non-physics grounded video plan generation & rendering
# ===========================================================================
def test_21_non_physics_grounded_video_plan(tmp_path: Path):
    """Test 21: Non-physics concepts do not contain hardcoded physics formulas or force boxes."""
    target = VideoTarget(
        concept_id="CONCEPT_CURRICULUM_REP",
        concept_name="Curriculum Representation",
        difficulty="intermediate",
        score=35.0,
        target_seconds=45,
        directive="Textbook diagram of educational curriculum nodes, competency matrices, and prerequisites.",
        chunk_ids=["CHUNK_CURR_01"],
        source_content_ids=["CU_CURR_01"],
        student_id="STU_TEST_NON_PHYSICS",
        source_id="SRC_TEST_NON_PHYSICS",
    )

    plan = plan_video_for_target(target)
    assert plan.concept_name == "Curriculum Representation"
    assert plan.target_seconds == 45
    total_dur = sum(s.duration_seconds for s in plan.scenes)
    assert 42.0 <= total_dur <= 48.0

    # Verify no hardcoded physics terms in any narration or diagram
    full_narr = " ".join(seg.text for seg in plan.narration).lower()
    assert "f = ma" not in full_narr
    assert "mass (m)" not in full_narr
    assert "net force" not in full_narr
    assert "applied force" not in full_narr
    assert "automobile braking" not in full_narr
    assert "rocket propulsion" not in full_narr

    for scene in plan.scenes:
        assert scene.diagram_type != "force_box"
        assert scene.force_label is None
        assert scene.object_label is None

    # Verify rendering completes without errors
    out_mp4 = tmp_path / "non_physics.mp4"
    rendered = render_video_plan(plan, out_mp4)
    assert rendered.exists()
    assert rendered.stat().st_size > 0

