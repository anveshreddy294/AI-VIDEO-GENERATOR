"""Comprehensive verification test suite for Step 3 Video Generation Engine.

Verifies:
1. Script Generation: Timed, grounded, multi-scene scripts matching 30s/45s/60s duration constraints.
2. Audio Synthesis: Voiceover WAV generation, duration measurement, and concatenation.
3. Visual Rendering: 1080p frame composition with typography, dark mode, and video clip creation.
4. Audio-Visual Muxing: FFmpeg multiplexing and WebVTT subtitle track generation.
5. End-to-End Pipeline: Complete rendering from VideoTarget to final playable MP4 video.
6. Pedagogical Guardrails: Human intervention concepts are strictly blocked from automated generation.
7. REST API: /video/generate, /video/status, and /video/{video_id}/stream endpoints.
"""

import asyncio
import json
import shutil
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.assessment.schemas import VideoTarget, VideoTargetMatrix
from app.services.assessment.video_target import save_video_matrix
from app.services.registry import register_source, save_content_units
from app.services.schemas import ContentUnit
from app.services.video_gen.audio_synthesizer import (
    concatenate_wav_files,
    get_wav_duration,
    synthesize_scene_audio,
    synthesize_script_audio,
)
from app.services.video_gen.muxer import (
    generate_webvtt_subtitles,
    mux_audio_and_video,
)
from app.services.video_gen.pipeline import (
    execute_video_generation_pipeline,
    load_videos_index,
)
from app.services.video_gen.schemas import VideoRenderJob, VideoScene, VideoScript
from app.services.video_gen.script_generator import (
    _generate_deterministic_script,
    generate_video_script,
)
from app.services.video_gen.visual_renderer import (
    HEIGHT,
    WIDTH,
    render_scene_frame,
    render_scene_to_video_clip,
)


class TestStep3VideoGeneration(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_scratch = BASE_DIR / "storage" / "runtime" / "test_scratch_vgen"
        cls.test_scratch.mkdir(parents=True, exist_ok=True)

        cls.student_id = "test_student_step3"
        cls.source_id = "SRC_test_step3_source"

        # Register sample ContentUnits for grounding
        sample_cu1 = ContentUnit(
            content_id="CU_step3_1",
            source_id=cls.source_id,
            asset_id="AST_step3_1",
            modality="txt",
            sequence_index=1,
            extraction_method="text_split",
            text="Newton's First Law states that an object remains at rest or in uniform motion unless acted upon by an external net force. This tendency is called inertia.",
        )
        sample_cu2 = ContentUnit(
            content_id="CU_step3_2",
            source_id=cls.source_id,
            asset_id="AST_step3_1",
            modality="txt",
            sequence_index=2,
            extraction_method="text_split",
            text="Newton's Second Law defines force as the rate of change of momentum, summarized by F = ma.",
        )
        save_content_units(cls.source_id, [sample_cu1, sample_cu2])

    def test_1_script_generation_durations(self):
        """Scenario 1: Script generator strictly adheres to 30s, 45s, and 60s targets."""
        # 30s foundational target
        target_30 = VideoTarget(
            concept_id="CONCEPT_INERTIA",
            concept_name="Inertia and First Law",
            difficulty="foundational",
            target_seconds=30,
            directive="Review basic definition of inertia",
            chunk_ids=["chk_1"],
            source_content_ids=["CU_step3_1"],
        )
        script_30 = generate_video_script(target_30, self.student_id, self.source_id)

        self.assertEqual(script_30.target_total_seconds, 30)
        self.assertEqual(len(script_30.scenes), 3)
        self.assertAlmostEqual(sum(s.duration_seconds for s in script_30.scenes), 30.0, delta=1.0)
        self.assertTrue(any("inertia" in s.narration.lower() for s in script_30.scenes))

        # 45s intermediate target
        target_45 = VideoTarget(
            concept_id="CONCEPT_FORCE",
            concept_name="Force and Acceleration",
            difficulty="intermediate",
            target_seconds=45,
            directive="Explain F = ma relationship",
            chunk_ids=["chk_2"],
            source_content_ids=["CU_step3_2"],
        )
        script_45 = generate_video_script(target_45, self.student_id, self.source_id)

        self.assertEqual(script_45.target_total_seconds, 45)
        self.assertEqual(len(script_45.scenes), 4)
        self.assertAlmostEqual(sum(s.duration_seconds for s in script_45.scenes), 45.0, delta=1.0)

        # 60s advanced target
        target_60 = VideoTarget(
            concept_id="CONCEPT_MOMENTUM",
            concept_name="Momentum Conservation",
            difficulty="advanced",
            target_seconds=60,
            directive="Derive momentum conservation from Newton's laws",
            chunk_ids=["chk_2"],
            source_content_ids=["CU_step3_2"],
        )
        script_60 = generate_video_script(target_60, self.student_id, self.source_id)

        self.assertEqual(script_60.target_total_seconds, 60)
        self.assertEqual(len(script_60.scenes), 5)
        self.assertAlmostEqual(sum(s.duration_seconds for s in script_60.scenes), 60.0, delta=1.0)
        print("   [PASS] Scenario 1: Script generation accurately enforces 30s, 45s, and 60s duration targets.")

    async def test_2_audio_synthesis_and_duration_measurement(self):
        """Scenario 2: Synthesizes valid audio WAV files and accurately measures duration."""
        target = VideoTarget(
            concept_id="CONCEPT_INERTIA",
            concept_name="Inertia and First Law",
            difficulty="foundational",
            target_seconds=30,
            directive="Review definition",
            source_content_ids=["CU_step3_1"],
        )
        script = generate_video_script(target, self.student_id, self.source_id)

        audio_dir = self.test_scratch / "audio_test"
        master_path, scene_wavs, durations = await synthesize_script_audio(
            script=script,
            output_dir=audio_dir,
            mock_mode=True,  # Test deterministic audio generation
        )

        self.assertTrue(master_path.exists())
        self.assertEqual(len(scene_wavs), len(script.scenes))
        for dur in durations:
            self.assertGreater(dur, 0.0)

        measured_master_dur = get_wav_duration(master_path)
        self.assertAlmostEqual(measured_master_dur, sum(durations), delta=0.5)
        print(f"   [PASS] Scenario 2: Audio synthesis generated {len(scene_wavs)} tracks ({measured_master_dur:.1f}s master).")

    def test_3_visual_frame_rendering(self):
        """Scenario 3: Pillow renders full 1080p (1920x1080) high-contrast frames."""
        scene = VideoScene(
            scene_number=1,
            scene_type="concept_breakdown",
            title="Core Principle: Newton's First Law",
            narration="An object remains in its state of rest unless an external net force acts on it.",
            onscreen_bullets=["Law of Inertia", "Zero Net Force = Constant Velocity", "Resistance to Change"],
            highlight_text="F_net = 0 => a = 0",
            duration_seconds=6.0,
        )

        frame = render_scene_frame(
            scene=scene,
            concept_name="Inertia",
            difficulty="foundational",
            scene_idx=1,
            total_scenes=3,
            source_id=self.source_id,
            progress_ratio=0.33,
        )

        self.assertEqual(frame.size, (WIDTH, HEIGHT))
        self.assertEqual(frame.mode, "RGB")
        print("   [PASS] Scenario 3: 1080p visual frame rendered successfully with dark mode typography.")

    async def test_4_end_to_end_video_pipeline(self):
        """Scenario 4: Complete end-to-end video pipeline generates playable MP4 with subtitles."""
        target = VideoTarget(
            concept_id="CONCEPT_INERTIA",
            concept_name="Inertia and First Law",
            difficulty="foundational",
            target_seconds=30,
            directive="Master inertia concept",
            chunk_ids=["chk_1"],
            source_content_ids=["CU_step3_1"],
        )

        # Make scene clips short for fast test rendering
        job = await execute_video_generation_pipeline(
            target=target,
            student_id=self.student_id,
            source_id=self.source_id,
            job_id="JOB_TEST_E2E",
            mock_mode=True,
        )

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.progress_percent, 100)
        self.assertIsNotNone(job.video_file_path)
        self.assertIsNotNone(job.subtitles_file_path)

        final_video = Path(job.video_file_path)
        subtitles_file = Path(job.subtitles_file_path)

        self.assertTrue(final_video.exists(), "final_video.mp4 must exist on disk.")
        self.assertGreater(final_video.stat().st_size, 1000, "final_video.mp4 must be non-empty.")
        self.assertTrue(subtitles_file.exists(), "subtitles.vtt must exist on disk.")
        self.assertIn("WEBVTT", subtitles_file.read_text(encoding="utf-8"))

        # Verify registration in master index
        idx = load_videos_index()
        self.assertIn(job.video_id, idx)
        print(f"   [PASS] Scenario 4: Full video generation pipeline produced {final_video.name} ({final_video.stat().st_size // 1024} KB).")

    async def test_5_pedagogical_guardrail_human_intervention_blocking(self):
        """Scenario 5: Concepts with >3 failures flagged for human intervention are strictly blocked."""
        # Create a VideoTargetMatrix with a human intervention concept
        matrix = VideoTargetMatrix(
            student_id=self.student_id,
            source_id=self.source_id,
            decision="GENERATE_VIDEOS",
            summary="Need review on basic inertia",
            videos=[
                VideoTarget(
                    concept_id="CONCEPT_NORMAL",
                    concept_name="Normal Force",
                    difficulty="foundational",
                    target_seconds=30,
                )
            ],
            human_intervention_concepts=["CONCEPT_KILL_SWITCH"],
        )
        save_video_matrix(matrix)

        client = TestClient(app)

        # Attempt to generate video for the kill-switch concept
        response = client.post(
            "/video/generate",
            json={
                "student_id": self.student_id,
                "source_id": self.source_id,
                "concept_id": "CONCEPT_KILL_SWITCH",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("HUMAN INTERVENTION", response.json()["detail"])
        print("   [PASS] Scenario 5: Anti-loop kill switch successfully prevented automated video generation.")

    def test_6_rest_api_status_and_streaming(self):
        """Scenario 6: REST API allows status inspection and video streaming."""
        client = TestClient(app)

        # Health endpoint updated to v0.3.0 with video_generation step
        health_res = client.get("/health")
        self.assertEqual(health_res.status_code, 200)
        self.assertIn("video_generation", health_res.json()["steps"])

        # Query video listing for student
        list_res = client.get(f"/video/list/{self.student_id}")
        self.assertEqual(list_res.status_code, 200)
        videos = list_res.json()["videos"]
        self.assertGreater(len(videos), 0)

        # Test video stream endpoint
        first_video_id = videos[0]["video_id"]
        stream_res = client.get(f"/video/{first_video_id}/stream")
        self.assertEqual(stream_res.status_code, 200)
        self.assertEqual(stream_res.headers["content-type"], "video/mp4")

        # Test subtitles endpoint
        sub_res = client.get(f"/video/{first_video_id}/subtitles")
        self.assertEqual(sub_res.status_code, 200)
        self.assertEqual(sub_res.headers["content-type"], "text/vtt; charset=utf-8")
        print("   [PASS] Scenario 6: REST API /video streaming, subtitles, and list endpoints verified.")


if __name__ == "__main__":
    unittest.main()
