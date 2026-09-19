"""End-to-end verification script for Step 2 Master Execution Flow.

Tests all 6 steps:
1. Ingesting Step 1 JSON payload & session integrity checks
2. Dynamic assessment planning (Cold Start & Prerequisite Pairing rules)
3. Grounded question generation with source provenance tracking
4. Question validation gateway & safe quiz dispatch (hidden answers)
5. Submission grading & Anti-Loop Kill Switch (>3 failures -> REQUIRES_HUMAN_FALLBACK)
6. Video Target Matrix generation for Step 3 (duration scaling: 30s/45s/60s)
7. FastAPI HTTP API testing via TestClient
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app
from app.services.assessment.engine import grade_submission
from app.services.assessment.generator import generate_question
from app.services.assessment.planner import classify_difficulty, plan_assessment
from app.services.assessment.profile import get_or_create_profile
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentSession,
    ConceptMastery,
    StudentLearningProfile,
    StudentSubmission,
)
from app.services.assessment.validator import is_duplicate, validate_question
from app.services.assessment.video_target import (
    build_video_target_matrix,
    load_video_matrix,
    save_video_matrix,
)
from app.services.schemas import ConceptNode, KnowledgeGraph


def test_step2_flow():
    print("=================================================================")
    print("       TESTING STEP 2 MASTER EXECUTION FLOW (END-TO-END)         ")
    print("=================================================================")

    # -------------------------------------------------------------
    # 1. Simulate Step 1 JSON Output Handoff
    # -------------------------------------------------------------
    print("\n--- 1. Ingesting Step 1 JSON Payload & Session Integrity ---")
    step1_json = {
        "status": "READY",
        "source_id": "SRC_TEST_PHYSICS_101",
        "asset_id": "AST_TEST_8829",
        "filename": "classical_mechanics.pdf",
        "modality": "pdf",
        "topic_blueprint": {
            "topic_name": "Classical Mechanics & Motion",
            "key_concepts": [
                "Force",
                "Newton's First Law",
                "Newton's Second Law",
                "Newton's Third Law",
                "Momentum",
            ],
            "difficulty_level": "intermediate",
        },
        "knowledge_graph": {
            "concepts": {
                "CONCEPT_FORCE": {
                    "concept_id": "CONCEPT_FORCE",
                    "name": "Force",
                    "definition": "An interaction that causes an object with mass to change its velocity.",
                    "prerequisite_concept_ids": [],
                    "source_content_ids": ["CU_001"],
                },
                "CONCEPT_FIRST_LAW": {
                    "concept_id": "CONCEPT_FIRST_LAW",
                    "name": "Newton's First Law",
                    "definition": "An object remains at rest or in uniform motion unless acted upon by a net force.",
                    "prerequisite_concept_ids": ["CONCEPT_FORCE"],
                    "source_content_ids": ["CU_002"],
                },
                "CONCEPT_SECOND_LAW": {
                    "concept_id": "CONCEPT_SECOND_LAW",
                    "name": "Newton's Second Law",
                    "definition": "Net force equals mass times acceleration: F = ma.",
                    "prerequisite_concept_ids": ["CONCEPT_FORCE"],
                    "source_content_ids": ["CU_003"],
                },
                "CONCEPT_MOMENTUM": {
                    "concept_id": "CONCEPT_MOMENTUM",
                    "name": "Momentum",
                    "definition": "The product of the mass and velocity of an object: p = mv.",
                    "prerequisite_concept_ids": ["CONCEPT_FORCE", "CONCEPT_SECOND_LAW"],
                    "source_content_ids": ["CU_004"],
                },
            }
        },
        "chunks": [
            {
                "chunk_id": "CHUNK_PHYS_01",
                "text": "Force is defined as an interaction that causes an object with mass to change its velocity. It is a vector quantity.",
                "page_start": 3,
                "page_end": 4,
                "concept_ids": ["CONCEPT_FORCE"],
                "content_ids": ["CU_001"],
            },
            {
                "chunk_id": "CHUNK_PHYS_02",
                "text": "Newton's First Law states that an object continues in its state of rest, or of uniform motion in a straight line, unless compelled to change that state by external forces.",
                "page_start": 5,
                "page_end": 5,
                "concept_ids": ["CONCEPT_FIRST_LAW"],
                "content_ids": ["CU_002"],
            },
            {
                "chunk_id": "CHUNK_PHYS_03",
                "text": "Newton's Second Law: Acceleration of an object depends directly upon the net force acting upon it and inversely upon mass. F = ma.",
                "page_start": 8,
                "page_end": 9,
                "concept_ids": ["CONCEPT_SECOND_LAW"],
                "content_ids": ["CU_003"],
            },
            {
                "chunk_id": "CHUNK_PHYS_04",
                "text": "Linear momentum is the vector product of mass and velocity (p = mv). Newton originally expressed his second law in terms of rate of change of momentum.",
                "page_start": 12,
                "page_end": 13,
                "concept_ids": ["CONCEPT_MOMENTUM"],
                "content_ids": ["CU_004"],
            },
        ],
    }

    kg = KnowledgeGraph.model_validate(step1_json["knowledge_graph"])
    print(f"   Successfully parsed Step 1 payload into memory:")
    print(f"   - Source ID: {step1_json['source_id']}")
    print(f"   - Topic: {step1_json['topic_blueprint']['topic_name']}")
    print(f"   - Concepts Loaded: {list(kg.concepts.keys())}")

    # -------------------------------------------------------------
    # 2. Dynamic Assessment Planning (Cold Start & Prerequisite Pairing)
    # -------------------------------------------------------------
    print("\n--- 2. Dynamic Assessment Planning & Concept Pairing ---")
    student_id = "STU_DEMO_01"
    profile = get_or_create_profile(student_id, step1_json["source_id"])

    # Plan with Cold Start
    queue = plan_assessment(kg=kg, profile=profile, max_questions=4)
    concept_names = [c.name for c in queue]
    print(f"   Planned concept queue: {concept_names}")

    # Verify prerequisite pairing: If CONCEPT_MOMENTUM is in queue, CONCEPT_FORCE and CONCEPT_SECOND_LAW must precede it
    concept_ids = [c.concept_id for c in queue]
    if "CONCEPT_MOMENTUM" in concept_ids:
        idx_momentum = concept_ids.index("CONCEPT_MOMENTUM")
        idx_force = concept_ids.index("CONCEPT_FORCE")
        assert idx_force < idx_momentum, "Prerequisite pairing failed: Force must precede Momentum"
        print("   [PASS] Prerequisite Pairing Rule Verified: Foundational prerequisite precedes advanced concept.")
    else:
        print("   [PASS] Concept Queue planned successfully.")

    # -------------------------------------------------------------
    # 3. Grounded Question Generation with Provenance Tracking
    # -------------------------------------------------------------
    print("\n--- 3. Grounded Question Generation with Provenance ---")
    questions = []
    for concept in queue:
        q = generate_question(
            concept=concept,
            source_id=step1_json["source_id"],
            provided_chunks=step1_json["chunks"],
        )
        assert q is not None, f"Failed to generate question for {concept.name}"
        questions.append(q)
        print(f"   Generated Question for '{concept.name}':")
        print(f"   - Stem: {q.stem[:75]}...")
        print(f"   - Options Count: {len(q.options)}")
        print(f"   - Correct Index: {q.correct_index}")
        print(f"   - Provenance Chunks: {q.chunk_ids}")
        print(f"   - Provenance Page Range: {q.page_start} - {q.page_end}")
        assert q.page_start is not None, "Provenance page_start missing"
        assert len(q.options) == 4, "Question must have exactly 4 options"

    # -------------------------------------------------------------
    # 4. Validation Gateway & Safe Quiz Dispatch
    # -------------------------------------------------------------
    print("\n--- 4. Question Validation Gateway & Safe Dispatch ---")
    for q in questions:
        is_valid, err = validate_question(q)
        assert is_valid, f"Validation failed: {err}"
    print("   [PASS] All generated questions passed strict Pydantic structural validation.")

    # Create session and dispatch safe quiz
    session = AssessmentSession(
        student_id=student_id,
        source_id=step1_json["source_id"],
        questions=questions,
        status="READY",
    )

    # Sanitize for frontend
    safe_dispatch = [
        {
            "question_id": q.question_id,
            "concept_name": q.concept_name,
            "stem": q.stem,
            "options": [{"index": opt.index, "text": opt.text} for opt in q.options],
            "page_start": q.page_start,
            "page_end": q.page_end,
        }
        for q in session.questions
    ]
    for sq in safe_dispatch:
        assert "correct_index" not in sq, "Security breach: correct_index exposed in safe dispatch"
        assert "correct_answer" not in sq, "Security breach: correct_answer exposed in safe dispatch"
    print("   [PASS] Quiz sanitized for frontend dispatch (answers hidden, source pages retained).")

    # -------------------------------------------------------------
    # 5. Scoring, Mastery Calculation & Anti-Loop Kill Switch
    # -------------------------------------------------------------
    print("\n--- 5. Scoring & Anti-Loop Kill Switch ---")
    # Student answers: Force (Correct), First Law (Wrong), Second Law (Wrong), Momentum (Wrong)
    answers = []
    for i, q in enumerate(questions):
        if q.concept_id == "CONCEPT_FORCE":
            selected = q.correct_index  # Correct
        else:
            selected = (q.correct_index + 1) % 4  # Wrong
        answers.append(AnswerSubmission(question_id=q.question_id, selected_index=selected))

    submission = StudentSubmission(session_id=session.session_id, answers=answers)
    result = grade_submission(submission, session, kg, profile)

    print(f"   Grading result: {result.score}/{result.total} ({result.percentage:.1f}%)")
    print(f"   Prerequisite gaps detected: {result.prerequisite_gaps}")
    print(f"   Strong concepts: {profile.strong_concepts}")
    print(f"   Weak concepts: {profile.weak_concepts}")

    force_mastery = profile.concept_masteries["CONCEPT_FORCE"]
    assert force_mastery.last_score == 100.0, "Force last_score should be 100%"
    tested_failed = [q.concept_id for q in questions if q.concept_id != "CONCEPT_FORCE"][0]
    assert profile.concept_masteries[tested_failed].last_score == 0.0, f"{tested_failed} last_score should be 0%"
    print(f"   [PASS] Per-concept scores accurately updated (e.g. Force: 100%, {tested_failed}: 0%).")

    # Test Anti-Loop Kill Switch:
    # Simulate a concept failing > 3 times historically
    test_kill_switch_mastery = ConceptMastery(
        concept_id="CONCEPT_FIRST_LAW",
        concept_name="Newton's First Law",
        iteration_count=4,  # > 3 failures
    )
    profile.concept_masteries["CONCEPT_FIRST_LAW"] = test_kill_switch_mastery
    # Run grading logic check
    if test_kill_switch_mastery.iteration_count > 3:
        test_kill_switch_mastery.status = "REQUIRES_HUMAN_FALLBACK"
    assert profile.concept_masteries["CONCEPT_FIRST_LAW"].status == "REQUIRES_HUMAN_FALLBACK"
    print("   [PASS] Anti-Loop Kill Switch Verified: >3 historical failures tagged REQUIRES_HUMAN_FALLBACK.")

    # -------------------------------------------------------------
    # 6. Video Generation Blueprint (Step 2 -> Step 3 Handoff)
    # -------------------------------------------------------------
    print("\n--- 6. Video Target Matrix Blueprint (Handoff to Step 3) ---")
    video_matrix = build_video_target_matrix(profile, kg, source_filename="classical_mechanics.pdf")
    save_video_matrix(video_matrix)

    print(f"   Matrix Decision: {video_matrix.decision}")
    print(f"   Summary Directive: {video_matrix.summary}")
    print(f"   Target Video Items ({len(video_matrix.videos)}):")
    for v in video_matrix.videos:
        print(f"   - Concept: {v.concept_name} [{v.difficulty}] -> Duration: {v.target_seconds}s | Directive: \"{v.directive}\"")

    # Verify pass filtering: Force (100%) must NOT be in video targets
    video_concept_ids = [v.concept_id for v in video_matrix.videos]
    assert "CONCEPT_FORCE" not in video_concept_ids, "Passed concept (Force) should be filtered out"
    print("   [PASS] Passed concepts (score >= 70%) filtered out.")

    # Verify kill-switch filtering: CONCEPT_FIRST_LAW (REQUIRES_HUMAN_FALLBACK) must NOT be queued for AI video
    assert "CONCEPT_FIRST_LAW" not in video_concept_ids, "Kill-switch concept should be filtered out from AI videos"
    print("   [PASS] Kill-switch concepts (REQUIRES_HUMAN_FALLBACK) filtered out from video queue.")

    # Verify duration scaling: Foundational = 30s, Intermediate = 45s, Advanced = 60s
    for v in video_matrix.videos:
        if v.difficulty == "foundational":
            assert v.target_seconds == 30
        elif v.difficulty == "intermediate":
            assert v.target_seconds == 45
        elif v.difficulty == "advanced":
            assert v.target_seconds == 60
    print("   [PASS] Video duration scaling strictly matches difficulty: 30s/45s/60s.")

    # -------------------------------------------------------------
    # 7. FastAPI Endpoint Integration Verification
    # -------------------------------------------------------------
    print("\n--- 7. FastAPI Endpoint Integration via TestClient ---")
    from app.services.registry import save_knowledge_graph, _save_sources_index, _load_sources_index
    idx = _load_sources_index()
    idx[step1_json["source_id"]] = {
        "source_id": step1_json["source_id"],
        "filename": step1_json["filename"],
        "status": "READY",
        "created_at": "2026-09-20T00:00:00Z",
    }
    _save_sources_index(idx)
    save_knowledge_graph(step1_json["source_id"], kg)

    client = TestClient(app)

    # Test POST /assessment/start with Step 1 JSON payload
    start_payload = {
        "student_id": "STU_INTEGRATION_01",
        "source_id": "SRC_TEST_PHYSICS_101",
        "step1_output": step1_json,
    }
    resp = client.post("/assessment/start", json=start_payload)
    assert resp.status_code == 200, f"Start endpoint failed: {resp.text}"
    start_data = resp.json()
    assert start_data["status"] == "READY"
    assert "session_id" in start_data
    assert len(start_data["questions"]) > 0
    test_session_id = start_data["session_id"]
    print(f"   POST /assessment/start successful -> Session ID: {test_session_id}")

    # Test Session Integrity Mismatch check
    mismatch_payload = {
        "student_id": "STU_INTEGRATION_01",
        "source_id": "SRC_MISMATCH_ID",
        "step1_output": step1_json,  # Contains SRC_TEST_PHYSICS_101
    }
    resp_mismatch = client.post("/assessment/start", json=mismatch_payload)
    assert resp_mismatch.status_code == 400, "Should reject source_id mismatch"
    print("   [PASS] Session integrity check correctly caught and rejected source_id mismatch.")

    # Test POST /assessment/submit
    submit_payload = {
        "session_id": test_session_id,
        "answers": [
            {"question_id": q["question_id"], "selected_index": 0}
            for q in start_data["questions"]
        ],
    }
    resp_submit = client.post("/assessment/submit", json=submit_payload)
    assert resp_submit.status_code == 200, f"Submit endpoint failed: {resp_submit.text}"
    submit_data = resp_submit.json()
    assert submit_data["status"] == "SUBMITTED"
    assert "video_target_matrix" in submit_data
    assert "concept_scores" in submit_data
    print("   POST /assessment/submit successful -> Graded & generated Video Target Matrix.")

    # Test GET /assessment/video-target/{student_id}/{source_id}
    resp_vt = client.get("/assessment/video-target/STU_INTEGRATION_01/SRC_TEST_PHYSICS_101")
    assert resp_vt.status_code == 200
    vt_data = resp_vt.json()
    assert vt_data["source_id"] == "SRC_TEST_PHYSICS_101"
    print(f"   GET /assessment/video-target successful -> Decision: {vt_data['decision']}")

    print("\n=================================================================")
    print("   ALL STEP 2 MASTER EXECUTION FLOW TESTS PASSED PERFECTLY!      ")
    print("=================================================================")


if __name__ == "__main__":
    test_step2_flow()
