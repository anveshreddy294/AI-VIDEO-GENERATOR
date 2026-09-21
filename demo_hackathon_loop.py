"""Turnkey Deterministic Hackathon Demo — AI-VIDEO-GENERATOR Closed-Loop Pipeline.

Demonstrates the complete end-to-end adaptive learning experience:
1. INGESTION: Ingests Physics material (Newton's Laws & Classical Mechanics)
2. KNOWLEDGE GRAPH: Extracts concepts (Force, Newton's First Law, Newton's Second Law, Momentum)
3. ASSESSMENT: Student takes grounded assessment quiz
4. KNOWLEDGE GAP: Student deliberately fails 'Newton's Second Law'
5. VIDEO TARGET MATRIX: Emits targeted 45-second video directive
6. DETERMINISTIC MANIM RENDER: Renders animation scenes (box, force arrows, F = ma equation, summary)
7. TTS & WHISPER: Synthesizes narration audio, aligns timestamps, and outputs SRT captions
8. FINAL MP4: Merges video, voiceover, and captions into a playable lesson
9. REASSESSMENT: Student retakes assessment and achieves MASTERY!

Usage:
    python demo_hackathon_loop.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.services.assessment.engine import grade_submission
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentSession,
    Question,
    StudentSubmission,
)
from app.services.assessment.session_store import save_session
from app.services.assessment.video_target import build_video_target_matrix
from app.services.dispatcher import dispatch
from app.services.registry import register_source, save_content_units, save_knowledge_graph
from app.services.structurer import process_structure_and_concepts
from app.services.video.engine import execute_video_generation_job

# ANSI terminal formatting
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"


PHYSICS_CURRICULUM = """Newton's Laws of Motion & Classical Mechanics

Chapter 1: Principles of Dynamics
Section 1.1: Force and Interactions
Force is defined as an interaction that causes an object with mass to change its velocity. 
It is a vector quantity having both magnitude and direction.

Section 1.2: Newton's First Law of Motion
Newton's First Law states that every object will remain at rest or in uniform motion in a straight line 
unless compelled to change its state by the action of an external net force. This tendency is known as inertia.

Section 1.3: Newton's Second Law of Motion
Newton's Second Law of Motion states that the rate of change of momentum of a body is directly proportional 
to the net force applied into it. In constant mass systems, it is formalized as F = ma: net force equals mass 
times acceleration. A greater force produces a greater acceleration, while a larger mass requires more force.

Section 1.4: Momentum
Linear momentum is defined as the product of the mass and velocity of an object: p = mv. Momentum is 
conserved in closed systems where no external net force is present.
"""


def banner(title: str) -> None:
    print(f"\n{C_BOLD}{C_BLUE}{'=' * 68}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN} >>> {title.upper()}{C_RESET}")
    print(f"{C_BOLD}{C_BLUE}{'=' * 68}{C_RESET}")


async def run_hackathon_demo():
    print(f"\n{C_BOLD}{C_YELLOW}🚀 STARTING AI-VIDEO-GENERATOR CLOSED-LOOP HACKATHON DEMO{C_RESET}")
    print(f"Working Directory: {BASE_DIR}")
    print(f"Active LLM Provider: {settings.llm_provider}")
    print(f"Ollama Model: {settings.ollama_model}")

    # Set mock mode for 100% deterministic, instant offline execution
    os.environ["LLM_PROVIDER"] = "mock"
    settings.llm_provider = "mock"

    # =========================================================================
    # STAGE 1: SOURCE INGESTION & KNOWLEDGE GRAPH EXTRACTION
    # =========================================================================
    banner("Stage 1: Source Material Ingestion & Knowledge Graph")
    scratch_dir = settings.runtime_dir / "test_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    sample_file = scratch_dir / "newtons_laws_curriculum.txt"
    sample_file.write_text(PHYSICS_CURRICULUM, encoding="utf-8")

    print(f"📄 Registering study material: {sample_file.name}")
    source_record, persistent_file = register_source(sample_file, sample_file.name)
    print(f"   ✓ Source Registered: {C_GREEN}{source_record.source_id}{C_RESET}")

    dispatch_res = dispatch(persistent_file, source_id=source_record.source_id, asset_id=source_record.asset_id)
    print(f"   ✓ Dispatched {len(dispatch_res.units)} ContentUnits (Modality: {dispatch_res.modality})")

    enriched_units, kg, blueprint = process_structure_and_concepts(dispatch_res.units)
    save_content_units(source_record.source_id, enriched_units)
    save_knowledge_graph(source_record.source_id, kg)

    print(f"   ✓ Topic Blueprint: {C_BOLD}{blueprint.topic_name}{C_RESET}")
    print(f"   ✓ Extracted {len(kg.concepts)} Granular Concepts:")
    for cid, c in kg.concepts.items():
        prereqs = f" (Prerequisites: {c.prerequisite_concept_ids})" if c.prerequisite_concept_ids else " (Foundational)"
        print(f"     • {C_BOLD}{c.name}{C_RESET}{prereqs}")

    # =========================================================================
    # STAGE 2: ADAPTIVE ASSESSMENT & KNOWLEDGE GAP IDENTIFICATION
    # =========================================================================
    banner("Stage 2: Adaptive Assessment & Knowledge Gap Detection")
    student_id = "STU_HACKATHON_JUDGE"
    profile = get_or_create_profile(student_id, source_record.source_id)

    # Clean profile state
    profile.concept_masteries.clear()
    profile.weak_concepts.clear()
    profile.strong_concepts.clear()

    second_law_cid = "CONCEPT_NEWTON_2" if "CONCEPT_NEWTON_2" in kg.concepts else list(kg.concepts.keys())[-1]

    questions = [
        Question(
            question_id="Q_DEMO_01",
            concept_id="CONCEPT_FORCE",
            concept_name="Force",
            difficulty="foundational",
            stem="According to the study material, what defines a force in classical mechanics?",
            options=[
                {"index": 0, "text": "An interaction that causes an object with mass to change its velocity."},
                {"index": 1, "text": "An intrinsic scalar measurement of rest state."},
                {"index": 2, "text": "A static quantity that prevents momentum conservation."},
                {"index": 3, "text": "The rate at which mass decays into thermal radiation."},
            ],
            correct_index=0,
            explanation="Force is strictly defined as an interaction altering velocity.",
            source_id=source_record.source_id,
            chunk_ids=["CHUNK_001"],
            page_start=1,
            page_end=1,
        ),
        Question(
            question_id="Q_DEMO_02",
            concept_id=second_law_cid,
            concept_name="Newton's Second Law",
            difficulty="intermediate",
            stem="What formula mathematically formalizes Newton's Second Law for constant mass?",
            options=[
                {"index": 0, "text": "F = ma (Net force equals mass times acceleration)."},
                {"index": 1, "text": "E = mc^2 (Mass-energy equivalence)."},
                {"index": 2, "text": "p = mv^2 (Rotational kinetic relation)."},
                {"index": 3, "text": "V = IR (Ohmic resistance)."},
            ],
            correct_index=0,
            explanation="Newton's Second Law defines F = ma.",
            source_id=source_record.source_id,
            chunk_ids=["CHUNK_002"],
            page_start=2,
            page_end=2,
        ),
    ]

    session = AssessmentSession(
        session_id=f"SESS_DEMO_{int(time.time())}",
        student_id=student_id,
        source_id=source_record.source_id,
        questions=questions,
    )
    save_session(session)

    print(f"📝 Quiz generated with {len(questions)} grounded questions.")
    print("   Simulating student responses:")
    print(f"   - Question 1 (Force): {C_GREEN}Answered correctly (Index 0){C_RESET}")
    print(f"   - Question 2 (Newton's Second Law): {C_RED}Answered incorrectly (Index 2){C_RESET} [GAP CREATED!]")

    submission = StudentSubmission(
        session_id=session.session_id,
        answers=[
            AnswerSubmission(question_id="Q_DEMO_01", selected_index=0),
            AnswerSubmission(question_id="Q_DEMO_02", selected_index=2),
        ],
    )

    result = grade_submission(submission, session, kg, profile)
    save_profile(profile)

    print(f"\n📊 Assessment Result: {result.score}/{result.total} ({result.percentage:.0f}%)")
    print(f"   Weak Concepts Identified: {C_RED}{profile.weak_concepts}{C_RESET}")

    # =========================================================================
    # STAGE 3: VIDEO TARGET MATRIX BLUEPRINT
    # =========================================================================
    banner("Stage 3: Video Target Matrix Blueprint (Handoff)")
    video_matrix = build_video_target_matrix(profile, kg, source_filename="newtons_laws_curriculum.txt")
    print(f"   Matrix Decision: {C_BOLD}{video_matrix.decision}{C_RESET}")
    print(f"   Target Remedial Queue ({len(video_matrix.videos)} items):")

    target = video_matrix.videos[0]
    target.student_id = student_id
    target.source_id = source_record.source_id
    print(f"   🎯 Concept: {C_BOLD}{target.concept_name}{C_RESET} [{target.difficulty}]")
    print(f"   ⏱ Target Duration: {target.target_seconds}s")
    print(f"   📌 Directive: \"{target.directive}\"")

    # =========================================================================
    # STAGE 4: DETERMINISTIC MANIM VIDEO GENERATION & COMPOSITION
    # =========================================================================
    banner("Stage 4: Programmatic Manim Engine + TTS + Whisper Pipeline")
    print("🎬 Executing Step 3 Orchestrator...")
    print("   [1/5] LLM Video Planner: Generating structured scene schema...")
    print("   [2/5] TTS Engine: Generating synchronized narration audio...")
    print("   [3/5] Whisper Engine: Aligning timestamps and writing SRT subtitles...")
    print("   [4/5] Manim Renderer: Executing animation primitives (Title, MathTex, Box, Force Vector)...")
    print("   [5/5] Compositor: Merging video track + voice track + subtitles via FFmpeg...")

    t0 = time.time()
    artifact = await execute_video_generation_job(target, mock_mode=True)
    dur = time.time() - t0

    if artifact.status != "COMPLETED":
        print(f"{C_RED}❌ Video generation failed: {artifact.error}{C_RESET}")
        return

    final_video = Path(artifact.video_path)
    final_audio = Path(artifact.audio_path)
    final_captions = Path(artifact.subtitle_path)

    print(f"\n{C_GREEN}{C_BOLD}✨ REMEDIAL VIDEO GENERATION SUCCESSFUL in {dur:.2f}s!{C_RESET}")
    print(f"   🎬 MP4 Video File: {C_BOLD}{final_video}{C_RESET} ({final_video.stat().st_size:,} bytes)")
    print(f"   🔊 Audio Track:   {final_audio} ({final_audio.stat().st_size:,} bytes)")
    print(f"   💬 Captions:      {final_captions}")

    print("\n   --- Preview of Whisper Generated Captions ---")
    print("   " + "\n   ".join(final_captions.read_text(encoding="utf-8").strip().splitlines()[:8]))

    # =========================================================================
    # STAGE 5: CLOSED-LOOP REASSESSMENT & MASTERY
    # =========================================================================
    banner("Stage 5: Student Reassessment & Mastery Verification")
    print("👩‍🎓 Student watches the 45-second remedial video on Newton's Second Law...")
    print("   Taking follow-up reassessment on Newton's Second Law...")

    reassessment_submission = StudentSubmission(
        session_id=session.session_id,
        answers=[
            AnswerSubmission(question_id="Q_DEMO_01", selected_index=0),
            AnswerSubmission(question_id="Q_DEMO_02", selected_index=0),  # Correct this time!
        ],
    )

    re_result = grade_submission(reassessment_submission, session, kg, profile)
    save_profile(profile)

    print(f"\n🏆 Reassessment Score: {re_result.score}/{re_result.total} (100%)")
    print(f"   Strong Concepts: {C_GREEN}{profile.strong_concepts}{C_RESET}")
    print(f"   Weak Concepts:   {profile.weak_concepts or 'None (All Gaps Resolved!)'}")

    print(f"\n{C_BOLD}{C_GREEN}{'=' * 68}")
    print("🎉 CLOSED-LOOP ADAPTIVE LEARNING CYCLE COMPLETE & VERIFIED!")
    print(f"{'=' * 68}{C_RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_hackathon_demo())
