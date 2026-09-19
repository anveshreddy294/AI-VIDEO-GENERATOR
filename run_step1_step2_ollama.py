"""VisualAI — Run Step 1 & Step 2 End-to-End with local Ollama.

Flow:
1. Ingest topic text into ContentUnits
2. Step 1: Extract Knowledge Graph, Chapters, and Concepts via Ollama (qwen3:8b)
3. Step 1: Generate Rich Chunks and validate ingestion quality
4. Step 2: Dynamic Assessment Planning (Prerequisite Pairing & Cold Start)
5. Step 2: Generate Grounded Multiple-Choice Questions via Ollama (qwen3:8b)
6. Step 2: Sanitize Safe Questions (hide answers/explanations for student dispatch)
7. Step 2: Simulate Student Quiz Submission
8. Step 2: Grade answers, detect prerequisite gaps, update StudentLearningProfile
9. Step 2: Produce Video Target Matrix blueprint
"""

import os
import sys
import json
import time

# Ensure UTF-8 output on Windows terminal
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.services.registry import (
    register_source,
    update_source_status,
    save_content_units,
    save_knowledge_graph,
    save_rich_chunks,
)
from app.services.dispatcher import dispatch
from app.services.structurer import process_structure_and_concepts
from app.services.chunker import create_rich_chunks
from app.services.validator import validate_ingestion_quality

from app.services.assessment.planner import plan_assessment
from app.services.assessment.generator import generate_question
from app.services.assessment.validator import validate_question
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.engine import grade_submission
from app.services.assessment.video_target import build_video_target_matrix, save_video_matrix
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentSession,
    SafeOption,
    SafeQuestion,
    StudentSubmission,
)


DEFAULT_TOPIC_TEXT = """Thermodynamics and Heat Transfer

Chapter 1: Thermal Foundations
Section 1.1: Thermal Equilibrium and Temperature
The Zeroth Law of Thermodynamics establishes temperature as a fundamental state property. It states that if two thermodynamic systems are each in thermal equilibrium with a third system, then they are in thermal equilibrium with each other. Temperature is the physical quantity that determines whether systems are in thermal equilibrium. When two objects with different temperatures are brought into contact, thermal energy flows spontaneously from the higher temperature object to the lower temperature object until equilibrium is achieved.

Section 1.2: Conservation of Thermal Energy
The First Law of Thermodynamics is the principle of conservation of energy applied to thermodynamic systems. It states that the change in internal energy (Delta U) of a closed system is equal to the net heat added to the system (Q) minus the work done by the system on its surroundings (W): Delta U = Q - W. Internal energy is a state function representing the microscopic kinetic and potential energy of the molecules. Heat and work are path-dependent mechanisms of energy transfer across system boundaries.

Chapter 2: Entropy and Cycles
Section 2.1: The Second Law and Entropy
The Second Law of Thermodynamics states that the total entropy of an isolated system always increases over time in any spontaneous natural process. Entropy is a measure of the molecular disorder or unavailable energy in a system. Heat cannot spontaneously flow from a colder body to a hotter body without external work being done on the system. All real processes are irreversible, generating positive entropy production.

Section 2.2: Heat Engines and the Carnot Efficiency
A heat engine absorbs heat from a high-temperature thermal reservoir, converts a fraction of it into mechanical work, and expels the remainder to a low-temperature reservoir. The Carnot cycle defines the theoretical upper limit for the thermal efficiency of any heat engine operating between two temperature reservoirs: eta = 1 - (T_cold / T_hot), where temperatures are expressed in Kelvin. No real heat engine can achieve higher efficiency than a reversible Carnot engine operating between the same two temperatures.
"""


def main():
    print("=" * 75)
    print("   VISUALAI: STEP 1 & STEP 2 PIPELINE POWERED BY LOCAL OLLAMA (qwen3:8b)   ")
    print("=" * 75)

    print(f"\nConfiguration Check:")
    print(f"  * LLM Provider: {settings.llm_provider.upper()}")
    print(f"  * Ollama URL:   {settings.ollama_url}")
    print(f"  * Ollama Model: {settings.ollama_model}")

    # -------------------------------------------------------------
    # STEP 1: MULTIMODAL INGESTION & KNOWLEDGE GRAPH EXTRACTION
    # -------------------------------------------------------------
    print("\n" + "-" * 75)
    print(" [STEP 1] MULTIMODAL INGESTION & KNOWLEDGE GRAPH EXTRACTION")
    print("-" * 75)

    scratch_dir = BASE_DIR / "storage" / "runtime" / "test_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    topic_file = scratch_dir / "thermodynamics_topic.txt"
    topic_file.write_text(DEFAULT_TOPIC_TEXT, encoding="utf-8")

    print(f"\n1. Registering Source: {topic_file.name} ({len(DEFAULT_TOPIC_TEXT)} chars)...")
    source_record, persistent_file = register_source(topic_file, topic_file.name)
    source_id = source_record.source_id
    print(f"   [OK] Source ID: {source_id}")
    print(f"   [OK] Asset ID:  {source_record.asset_id}")

    print("\n2. Dispatching & Normalizing ContentUnits...")
    dispatch_result = dispatch(persistent_file, source_id=source_id, asset_id=source_record.asset_id)
    raw_units = dispatch_result.units
    print(f"   [OK] Extracted {len(raw_units)} ContentUnit(s):")
    for i, cu in enumerate(raw_units, 1):
        preview = cu.text.replace("\n", " ")[:70]
        print(f"     [{i}] {cu.content_id}: \"{preview}...\"")

    print("\n3. Extracting Concepts, Hierarchy & Knowledge Graph using Ollama...")
    t0 = time.time()
    enriched_units, kg, blueprint = process_structure_and_concepts(raw_units)
    t_kg = time.time() - t0

    print(f"   [OK] Extracted in {t_kg:.1f}s via {settings.ollama_model}!")
    print(f"   [OK] Topic Name:        {blueprint.topic_name}")
    print(f"   [OK] Difficulty:        {blueprint.difficulty_level.upper()}")
    print(f"   [OK] Concepts ({len(kg.concepts)}):")
    for cid, node in kg.concepts.items():
        prereqs = f" (Requires: {', '.join(node.prerequisite_concept_ids)})" if node.prerequisite_concept_ids else ""
        print(f"     * [{node.concept_id}] {node.name}{prereqs}")
        print(f"       Definition: {node.definition[:90]}...")

    print("\n4. Generating Semantic RichChunks...")
    rich_chunks = create_rich_chunks(enriched_units, kg)
    print(f"   [OK] Generated {len(rich_chunks)} RichChunk(s)")

    # Save to registry
    save_content_units(source_id, enriched_units)
    save_knowledge_graph(source_id, kg)
    save_rich_chunks(source_id, rich_chunks)
    update_source_status(source_id, "READY")
    print(f"   [OK] Source {source_id} state set to READY in registry.")

    # Ingestion Quality Gateway
    val_report = validate_ingestion_quality(
        record=source_record,
        file_path=persistent_file,
        units=enriched_units,
        kg=kg,
        chunks=rich_chunks,
        upserted_count=len(rich_chunks),
    )
    assert val_report["passed"], "Validation gateway check failed"
    print("   [OK] 5-Tier Quality Validation Gateway: PASSED")

    # -------------------------------------------------------------
    # STEP 2: DIAGNOSTIC ASSESSMENT & KNOWLEDGE PROFILING
    # -------------------------------------------------------------
    print("\n" + "-" * 75)
    print(" [STEP 2] DIAGNOSTIC ASSESSMENT & KNOWLEDGE PROFILING")
    print("-" * 75)

    student_id = "student_thermo_learner"
    profile = get_or_create_profile(student_id, source_id)

    print(f"\n1. Dynamic Assessment Planning for Student '{student_id}'...")
    planned_concepts = plan_assessment(kg=kg, profile=profile, max_questions=3)
    print(f"   [OK] Scheduled {len(planned_concepts)} Concepts in Pedagogical Order:")
    for idx, c in enumerate(planned_concepts, 1):
        print(f"     [{idx}] {c.name} ({c.concept_id})")

    print(f"\n2. Generating Grounded Questions via Ollama ({settings.ollama_model})...")
    questions = []
    chunk_dicts = [
        {
            "chunk_id": ch.chunk_id,
            "source_id": ch.source_id,
            "text": ch.text,
            "concept_ids": ch.concept_ids,
            "content_ids": ch.content_ids,
            "layer": ch.layer,
            "page_start": ch.page_start or 1,
            "page_end": ch.page_end or 1,
        }
        for ch in rich_chunks
    ]

    for idx, concept in enumerate(planned_concepts, 1):
        print(f"\n   [Question {idx}/{len(planned_concepts)}] Prompting Ollama for: '{concept.name}'...")
        t_q_start = time.time()
        q = generate_question(
            concept=concept,
            source_id=source_id,
            provided_chunks=chunk_dicts,
            variant_type="definition" if idx == 1 else ("application" if idx == 2 else "misconception"),
        )
        t_q_dur = time.time() - t_q_start
        assert q is not None, f"Question generation failed for {concept.name}"
        questions.append(q)

        print(f"   [OK] Generated in {t_q_dur:.1f}s")
        print(f"     Stem: {q.stem}")
        for opt in q.options:
            marker = " ([OK] Correct Key)" if opt.index == q.correct_index else ""
            print(f"       [{chr(65 + opt.index)}] {opt.text}{marker}")
        print(f"     Explanation: {q.explanation[:90]}...")

    # Validate all questions
    for q in questions:
        is_val, msg = validate_question(q)
        assert is_val, f"Validation failure: {msg}"
    print("\n3. Question Validation Gateway: All questions passed strict Pydantic rules.")

    # Create active session
    session = AssessmentSession(
        student_id=student_id,
        source_id=source_id,
        questions=questions,
        status="READY",
    )

    # 4. Safe Student Dispatch
    print("\n4. Preparing Safe Quiz Dispatch (Hidden Answers for Learner UI)...")
    safe_questions = [
        SafeQuestion(
            question_id=q.question_id,
            concept_id=q.concept_id,
            concept_name=q.concept_name,
            stem=q.stem,
            options=[SafeOption(index=opt.index, text=opt.text) for opt in q.options],
            page_start=q.page_start,
            page_end=q.page_end,
            variant_type=q.variant_type,
            difficulty=q.difficulty,
        )
        for q in session.questions
    ]
    for sq in safe_questions:
        assert not hasattr(sq, "correct_index") or sq.model_dump().get("correct_index") is None
        print(f"   [OK] Dispatched: Q [{sq.concept_name}]: \"{sq.stem[:60]}...\" ({len(sq.options)} options)")

    # 5. Simulate Student Answers
    print("\n5. Simulating Student Submission...")
    # Answer Q1 correct, Q2 wrong, Q3 correct (if 3 questions)
    answers = []
    for idx, q in enumerate(questions):
        if idx == 1:
            chosen = (q.correct_index + 1) % 4  # Deliberate wrong answer
            print(f"   * Student answered Q{idx+1} ({q.concept_name}): INCORRECT (Option {chr(65+chosen)})")
        else:
            chosen = q.correct_index  # Correct answer
            print(f"   * Student answered Q{idx+1} ({q.concept_name}): CORRECT (Option {chr(65+chosen)})")
        answers.append(AnswerSubmission(question_id=q.question_id, selected_index=chosen))

    submission = StudentSubmission(session_id=session.session_id, answers=answers)
    result = grade_submission(submission, session, kg, profile)

    print("\n6. Diagnostic Grading & Knowledge Profile:")
    print(f"   [OK] Overall Score:     {result.score}/{result.total} ({result.percentage:.1f}%)")
    print(f"   [OK] Strong Concepts:   {profile.strong_concepts}")
    print(f"   [OK] Weak Concepts:     {profile.weak_concepts}")
    if result.prerequisite_gaps:
        print(f"   [OK] Prerequisite Gaps: {result.prerequisite_gaps}")

    # 7. Video Target Matrix Blueprint
    print("\n7. Generating Video Target Matrix (Handoff Blueprint for Remediation):")
    matrix = build_video_target_matrix(profile, kg, source_filename="thermodynamics_topic.txt")
    save_video_matrix(matrix)
    print(f"   [OK] Decision: {matrix.decision}")
    print(f"   [OK] Directive: {matrix.summary}")
    for item in matrix.videos:
        print(f"     * Remediation Target: '{item.concept_name}' [{item.difficulty.upper()}] -> Duration: {item.target_seconds}s")
        if item.misconception:
            print(f"       Misconception: {item.misconception}")

    print("\n" + "=" * 75)
    print("   [SUCCESS] FULL STEP 1 & STEP 2 EXECUTED COMPLETELY WITH OLLAMA!      ")
    print("=" * 75)


if __name__ == "__main__":
    main()
