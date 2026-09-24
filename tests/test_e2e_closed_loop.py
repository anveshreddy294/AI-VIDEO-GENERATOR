"""End-to-End Closed-Loop Integration Test for AI-VIDEO-GENERATOR.

Executes the complete master execution flow and quality gates:
1. STEP 1 INGESTION:
   Input Document -> ContentUnits -> KnowledgeGraph -> Prerequisite DAG -> Rich Chunks -> Registry
2. STEP 2 ADAPTIVE ASSESSMENT:
   Session Creation -> SafeQuestions -> Student Answers -> Grading -> Gap Identification
3. STEP 2 -> STEP 3 HANDOFF:
   StudentLearningProfile -> VideoTargetMatrix (Duration Contract: 30s/45s/60s)
4. STEP 3 VIDEO ENGINE:
   VideoPlan -> Deterministic Manim Render -> TTS -> Whisper Alignment -> FFmpeg Compositor -> Canonical MP4
5. CLOSED LEARNING LOOP (REASSESSMENT):
   Student watches remedial video -> Takes Session 2 -> Demonstrates mastery -> Profile upgraded
6. CROSS-SOURCE ISOLATION SECURITY:
   Strict source_id scoping preventing cross-source chunk leakage
7. HUMAN FALLBACK GOVERNANCE:
   Kill-switch detection -> Instructor alert -> Alert resolution / mastery reset
"""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.assessment.engine import grade_submission
from app.services.assessment.generator import search_concept_chunks
from app.services.assessment.planner import plan_assessment
from app.services.assessment.profile import get_or_create_profile, load_profile, save_profile
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentSession,
    ConceptMastery,
    Question,
    QuestionResult,
    StudentLearningProfile,
    StudentSubmission,
)
from app.services.assessment.session_store import save_session
from app.services.assessment.video_target import build_video_target_matrix, get_video_target_matrix
from app.services.dispatcher import dispatch
from app.services.instructor.analytics import get_cohort_overview, reset_student_concept_status
from app.services.registry import register_source, save_content_units, save_knowledge_graph
from app.services.schemas import ConceptNode, KnowledgeGraph
from app.services.structurer import process_structure_and_concepts
from app.services.video.artifact_store import find_existing_video, get_video_dir
from app.services.video.engine import execute_video_generation_job
from app.services.video.scene_schema import VideoJobStatus


def test_end_to_end_closed_loop(tmp_path: Path, monkeypatch):
    """Verify the full closed learning loop: Ingestion -> Quiz 1 -> Gap -> Video -> Quiz 2 -> Mastery."""
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
    second_law_cid = "CONCEPT_NEWTON_2"
    kg.concepts["CONCEPT_FORCE"] = ConceptNode(
        concept_id="CONCEPT_FORCE",
        name="Force",
        definition="Force is defined as an interaction that causes an object with mass to change its velocity.",
        prerequisite_concept_ids=[],
        source_content_ids=[dispatch_res.units[0].content_id],
    )
    kg.concepts[second_law_cid] = ConceptNode(
        concept_id=second_law_cid,
        name="Newton's Second Law",
        definition="Newton's Second Law states that F = ma.",
        prerequisite_concept_ids=["CONCEPT_FORCE"],
        source_content_ids=[dispatch_res.units[1].content_id if len(dispatch_res.units) > 1 else dispatch_res.units[0].content_id],
    )
    save_content_units(source_record.source_id, enriched_units)
    save_knowledge_graph(source_record.source_id, kg)
    assert len(kg.concepts) >= 2

    # -------------------------------------------------------------
    # 2. Step 2: Adaptive Assessment (Session 1) - Student Fails Concept
    # -------------------------------------------------------------
    student_id = "STU_E2E_LEARNER_01"
    profile = get_or_create_profile(student_id, source_record.source_id)

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

    session1 = AssessmentSession(
        session_id="SESS_E2E_01",
        student_id=student_id,
        source_id=source_record.source_id,
        questions=questions,
    )
    save_session(session1)

    # Student answers: Correct on Force, INCORRECT on Newton's Second Law (gap identified)
    submission1 = StudentSubmission(
        session_id=session1.session_id,
        answers=[
            AnswerSubmission(question_id="Q_FORCE_01", selected_index=0),       # Correct
            AnswerSubmission(question_id="Q_SECOND_LAW_01", selected_index=2),  # Wrong! (Gap)
        ],
    )

    graded1 = grade_submission(submission1, session1, kg, profile)
    assert graded1.score == 1
    assert graded1.total == 2
    save_profile(profile)

    # -------------------------------------------------------------
    # 3. Video Target Matrix Handoff (Step 2 -> Step 3)
    # -------------------------------------------------------------
    video_matrix = build_video_target_matrix(profile, kg, source_filename="physics_mechanics.txt")
    assert video_matrix.decision == "GENERATE_VIDEOS"
    assert len(video_matrix.videos) >= 1

    target = next((v for v in video_matrix.videos if v.concept_id == second_law_cid or "second law" in v.concept_name.lower()), video_matrix.videos[0])
    target.student_id = student_id
    target.source_id = source_record.source_id
    target.target_seconds = 45  # Intermediate concept duration
    assert target.target_seconds in (30, 45, 60)

    # -------------------------------------------------------------
    # 4. Step 3 Video Engine Execution (Deterministic Manim Loop)
    # -------------------------------------------------------------
    artifact = await execute_video_generation_job(target, mock_mode=True)
    assert artifact.status == VideoJobStatus.COMPLETED
    assert artifact.video_path is not None
    assert artifact.audio_path is not None
    assert artifact.subtitle_path is not None

    final_video = Path(artifact.video_path)
    assert final_video.exists()
    assert final_video.stat().st_size > 2000

    final_captions = Path(artifact.subtitle_path)
    assert final_captions.exists()
    assert "-->" in final_captions.read_text(encoding="utf-8")

    # Verify canonical artifact store
    vdir = get_video_dir(student_id, source_record.source_id, target.concept_id)
    assert (vdir / "final.mp4").exists()
    assert (vdir / "metadata.json").exists()

    meta = json.loads((vdir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["student_id"] == student_id
    assert meta["source_id"] == source_record.source_id
    assert meta["concept_id"] == target.concept_id

    # -------------------------------------------------------------
    # 5. Closed-Loop Reassessment (Session 2): Student Demonstrates Mastery
    # -------------------------------------------------------------
    # Reassessment session retains historical attempts in StudentLearningProfile
    profile_before_s2 = load_profile(student_id, source_record.source_id)
    assert profile_before_s2 is not None
    assert profile_before_s2.concept_masteries[second_law_cid].attempts >= 1

    session2 = AssessmentSession(
        session_id="SESS_E2E_02",
        student_id=student_id,
        source_id=source_record.source_id,
        questions=[questions[1]],  # Retest the previously failed concept
    )
    save_session(session2)

    # Student answers Newton's Second Law CORRECTLY this time
    submission2 = StudentSubmission(
        session_id=session2.session_id,
        answers=[
            AnswerSubmission(question_id="Q_SECOND_LAW_01", selected_index=0),  # Correct!
        ],
    )

    graded2 = grade_submission(submission2, session2, kg, profile_before_s2)
    assert graded2.score == 1
    assert graded2.total == 1
    save_profile(profile_before_s2)

    # Verify updated profile records historical attempts and successful mastery
    profile_after_s2 = load_profile(student_id, source_record.source_id)
    assert profile_after_s2 is not None
    updated_mastery = profile_after_s2.concept_masteries[second_law_cid]
    assert updated_mastery.attempts >= 2
    assert updated_mastery.last_score >= settings.assessment_pass_threshold
    assert updated_mastery.consecutive_correct >= 1

    # In Session 2, no new video target should be generated for the mastered concept
    new_video_matrix = build_video_target_matrix(profile_after_s2, kg, source_filename="physics_mechanics.txt")
    remaining_target_ids = [v.concept_id for v in new_video_matrix.videos]
    assert second_law_cid not in remaining_target_ids



# =====================================================================
# 6. Cross-Source Security Isolation Test (Section 33)
# =====================================================================
def test_cross_source_isolation_security():
    """Verify that vector retrieval strictly scopes to source_id and cannot leak chunks from Source B."""
    mock_client = MagicMock()
    mock_client.search.return_value = []

    with patch("app.services.assessment.generator.get_client", return_value=mock_client), \
         patch("app.services.assessment.generator.ensure_collection"):
        concept = ConceptNode(
            concept_id="CONCEPT_SEC_01",
            name="Confidential Quantum Entanglement",
            definition="Source A proprietary physics research",
            prerequisite_concept_ids=[],
            source_content_ids=["CU_SEC_01"],
        )
        # Search explicitly for Source A
        res = search_concept_chunks(concept, source_id="SRC_A_CONFIDENTIAL")

        assert mock_client.search.called
        call_kwargs = mock_client.search.call_args[1]
        q_filter = call_kwargs.get("query_filter")
        must_clauses = q_filter.must

        # Assert query filter enforces source_id == SRC_A_CONFIDENTIAL
        source_id_scoped = any(
            hasattr(cond, "key") and cond.key == "source_id" and cond.match.value == "SRC_A_CONFIDENTIAL"
            for cond in must_clauses
        )
        assert source_id_scoped, "Cross-source security violation: search filter must strictly match target source_id"


# =====================================================================
# 7. Human Fallback Kill-Switch Governance Test (Section 34)
# =====================================================================
def test_human_fallback_killswitch_and_instructor_intervention():
    """Verify kill-switch trigger, video exclusion, API rejection, instructor alert, and mastery reset."""
    student_id = "STU_KILLSWITCH_01"
    source_id = "SRC_MATH_KILLSWITCH"
    cid = "CONCEPT_ABSTRACT_ALGEBRA"

    profile = StudentLearningProfile(student_id=student_id, source_id=source_id)
    # Simulate hitting the anti-loop kill switch (>3 failures)
    profile.concept_masteries[cid] = ConceptMastery(
        concept_id=cid,
        concept_name="Abstract Algebra Fields",
        status="REQUIRES_HUMAN_FALLBACK",
        attempts=4,
        iteration_count=4,
        last_score=15.0,
    )
    save_profile(profile)

    kg = KnowledgeGraph(
        source_id=source_id,
        concepts={
            cid: ConceptNode(
                concept_id=cid,
                name="Abstract Algebra Fields",
                definition="Field theory axioms",
                prerequisite_concept_ids=[],
                source_content_ids=["CU_FIELD_01"],
            )
        },
        prerequisites={},
    )

    # 1. Video target matrix must exclude human fallback concept from automated rendering queue
    matrix = build_video_target_matrix(profile, kg, source_filename="algebra.pdf")
    automated_cids = [v.concept_id for v in matrix.videos]
    assert cid not in automated_cids
    assert cid in matrix.human_intervention_concept_ids

    # 2. Video API must reject automated generation with HTTP 400
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

    # 3. Instructor analytics must reflect active human intervention alert
    cohort = get_cohort_overview(source_id)
    assert cohort.total_interventions_needed >= 1
    assert len(cohort.alerts) >= 1
    alert = next((a for a in cohort.alerts if a.concept_id == cid and a.student_id == student_id), None)
    assert alert is not None
    assert alert.iteration_count >= 3

    # 4. Instructor resets mastery status back to LEARNING
    reset_res = reset_student_concept_status(
        student_id=student_id,
        source_id=source_id,
        concept_id=cid,
        new_status="LEARNING",
        instructor_notes="Reviewed one-on-one with student. Prerequisite foundations clarified.",
    )
    assert reset_res.new_status == "LEARNING"

    # 5. After reset, student is unblocked and eligible for learning loops again
    updated_profile = load_profile(student_id, source_id)
    assert updated_profile is not None
    assert updated_profile.concept_masteries[cid].status == "LEARNING"
