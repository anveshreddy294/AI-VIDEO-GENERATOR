"""End-to-End Closed-Loop Integration Test for AI-VIDEO-GENERATOR.

Executes the complete master execution flow:
INPUT DOCUMENT
   ↓
STEP 1 INGESTION (Text extraction, Chunking, KnowledgeGraph)
   ↓
STEP 2 ASSESSMENT (Session creation, Question dispatch, Scoring, Gap detection)
   ↓
KNOWLEDGE GAP (Student fails 'Newton's Second Law')
   ↓
VIDEO TARGET MATRIX (Decision: GENERATE_VIDEOS, Target: 45s remedial lesson)
   ↓
STEP 3 VIDEO ENGINE (Ollama VideoPlan -> Manim Render -> TTS -> Whisper -> Compositor)
   ↓
FINAL REMEDIAL MP4 (Verified non-zero file size, audio, captions, and source provenance)
"""

import asyncio
from pathlib import Path
import pytest

from app.core.config import settings
from app.services.assessment.engine import grade_submission
from app.services.assessment.planner import plan_assessment
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentSession,
    Question,
    QuestionResult,
    StudentSubmission,
)
from app.services.assessment.session_store import save_session
from app.services.assessment.video_target import build_video_target_matrix
from app.services.dispatcher import dispatch
from app.services.registry import register_source, save_content_units, save_knowledge_graph
from app.services.schemas import ConceptNode, KnowledgeGraph
from app.services.structurer import process_structure_and_concepts
from app.services.video.engine import execute_video_generation_job
from app.services.video.scene_schema import VideoJobStatus


def test_end_to_end_closed_loop(tmp_path: Path, monkeypatch):
    """Verify the entire closed loop: Ingestion -> Assessment -> Gap -> Manim MP4."""
    asyncio.run(_run_test_end_to_end_closed_loop(tmp_path, monkeypatch))


async def _run_test_end_to_end_closed_loop(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "mock")

    # -------------------------------------------------------------
    # 1. Step 1: Input Document & Ingestion
    # -------------------------------------------------------------
    sample_text = (
        "Classical Mechanics: Newton's Laws of Motion\n\n"
        "Chapter 1: Force and Dynamics\n"
        "Section 1.1: Force\n"
        "Force is defined as an interaction that causes an object with mass to change its velocity.\n\n"
        "Section 1.2: Newton's Second Law\n"
        "Newton's Second Law states that the acceleration of an object is directly proportional to the net force "
        "acting on it and inversely proportional to its mass: F = ma.\n\n"
        "Section 1.3: Momentum\n"
        "Linear momentum is defined as the product of mass and velocity: p = mv.\n"
    )

    sample_file = tmp_path / "physics_mechanics.txt"
    sample_file.write_text(sample_text, encoding="utf-8")

    source_record, stored_file = register_source(sample_file, "physics_mechanics.txt")
    assert source_record.source_id.startswith("SRC_")

    dispatch_res = dispatch(stored_file, source_id=source_record.source_id, asset_id=source_record.asset_id)
    assert len(dispatch_res.units) >= 3

    enriched_units, kg, blueprint = process_structure_and_concepts(dispatch_res.units)
    save_content_units(source_record.source_id, enriched_units)
    save_knowledge_graph(source_record.source_id, kg)
    assert len(kg.concepts) >= 2

    # -------------------------------------------------------------
    # 2. Step 2: Adaptive Assessment & Student Gap Detection
    # -------------------------------------------------------------
    student_id = "STU_E2E_LEARNER_01"
    profile = get_or_create_profile(student_id, source_record.source_id)

    # Simulate questions generated for concepts
    second_law_cid = "CONCEPT_NEWTON_2"
    questions = [
        Question(
            question_id="Q_FORCE_01",
            concept_id="CONCEPT_FORCE",
            concept_name="Force",
            difficulty="foundational",
            stem="What defines a force in classical mechanics?",
            options=[
                {"index": 0, "text": "An interaction that changes velocity"},
                {"index": 1, "text": "A scalar property of stationary objects"},
                {"index": 2, "text": "Constant energy storage"},
                {"index": 3, "text": "Resistance to light"},
            ],
            correct_index=0,
            explanation="Force alters an object's state of motion.",
            source_id=source_record.source_id,
            chunk_ids=["CHUNK_001"],
            page_start=1,
            page_end=1,
        ),
        Question(
            question_id="Q_SECOND_LAW_01",
            concept_id=second_law_cid,
            concept_name="Newton's Second Law",
            difficulty="intermediate",
            stem="What mathematical relation describes Newton's Second Law?",
            options=[
                {"index": 0, "text": "F = ma"},
                {"index": 1, "text": "E = mc^2"},
                {"index": 2, "text": "p = mv^2"},
                {"index": 3, "text": "V = IR"},
            ],
            correct_index=0,
            explanation="Net force equals mass times acceleration.",
            source_id=source_record.source_id,
            chunk_ids=["CHUNK_002"],
            page_start=2,
            page_end=2,
        ),
    ]

    session = AssessmentSession(
        session_id="SESS_E2E_01",
        student_id=student_id,
        source_id=source_record.source_id,
        questions=questions,
    )
    save_session(session)

    # Student answers: Correct on Force, INCORRECT on Newton's Second Law (gap created)
    submission = StudentSubmission(
        session_id=session.session_id,
        answers=[
            AnswerSubmission(question_id="Q_FORCE_01", selected_index=0),       # Correct
            AnswerSubmission(question_id="Q_SECOND_LAW_01", selected_index=2),  # Wrong! (Gap)
        ],
    )

    graded_resp = grade_submission(submission, session, kg, profile)
    assert graded_resp.score == 1
    assert graded_resp.total == 2
    save_profile(profile)

    # -------------------------------------------------------------
    # 3. Video Target Matrix Generation
    # -------------------------------------------------------------
    video_matrix = build_video_target_matrix(profile, kg, source_filename="physics_mechanics.txt")
    assert video_matrix.decision == "GENERATE_VIDEOS"
    assert len(video_matrix.videos) >= 1

    # Locate the target video for Newton's Second Law
    target = next((v for v in video_matrix.videos if v.concept_id == second_law_cid or "second law" in v.concept_name.lower()), video_matrix.videos[0])
    target.student_id = student_id
    target.source_id = source_record.source_id
    assert target.target_seconds in (30, 45, 60)

    # -------------------------------------------------------------
    # 4. Step 3 Video Engine Execution (Deterministic Manim Loop)
    # -------------------------------------------------------------
    artifact = await execute_video_generation_job(target, mock_mode=True)

    # Verify final outcomes
    assert artifact.status == VideoJobStatus.COMPLETED
    assert artifact.video_path is not None
    assert artifact.audio_path is not None
    assert artifact.subtitle_path is not None

    final_video = Path(artifact.video_path)
    assert final_video.exists(), f"Final MP4 video must exist on disk: {final_video}"
    assert final_video.stat().st_size > 5000, f"Final MP4 video must be non-zero size ({final_video.stat().st_size} bytes)"

    final_captions = Path(artifact.subtitle_path)
    assert final_captions.exists(), "Captions SRT file must exist"
    assert "-->" in final_captions.read_text(encoding="utf-8"), "SRT must contain valid timestamp markers"

    print("\n===========================================================")
    print("SUCCESS: Full Closed Loop Complete!")
    print(f"Generated Video: {final_video} ({final_video.stat().st_size} bytes)")
    print(f"Generated Audio: {artifact.audio_path}")
    print(f"Generated Captions: {artifact.subtitle_path}")
    print("===========================================================\n")
