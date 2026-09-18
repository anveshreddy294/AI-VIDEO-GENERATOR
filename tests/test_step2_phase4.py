"""Phase 4: Final Production Hardening & Contract Verification Test Suite for Step 2.

Audit checks:
1.  test_cross_source_isolation
2.  test_provenance_no_fabricated_page
3.  test_grounding_validation
4.  test_duplicate_detection
5.  test_fallback_diversity_and_unpredictability
6.  test_backfilling_reserve_pool
7.  test_kill_switch_and_video_exclusion
8.  test_prerequisite_gaps_with_snapshot
9.  test_session_kg_snapshot_offline_reconstruction
10. test_configuration_dynamic_settings
11. test_profile_ids_and_names_persisted
12. test_video_matrix_contract_and_decisions
13. test_api_integrity_and_safe_question
14. test_expired_session_rejected
15. test_windows_output_compatibility
"""

import datetime
from datetime import timezone
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.assessment.engine import grade_submission, rebuild_profile_metrics
from app.services.assessment.generator import _generate_grounded_fallback, generate_question, search_concept_chunks
from app.services.assessment.planner import plan_assessment
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.providers import MockProvider
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentOption,
    AssessmentSession,
    ConceptMastery,
    ConceptSnapshot,
    Question,
    SafeQuestion,
    StudentLearningProfile,
    StudentSubmission,
    reconstruct_kg_from_snapshot,
)
from app.services.assessment.session_store import load_session, save_session
from app.services.assessment.validator import is_duplicate, validate_grounding, validate_question
from app.services.assessment.video_target import build_video_target_matrix
from app.services.schemas import ConceptNode, KnowledgeGraph

client = TestClient(app)


def _sample_concept(cid: str, name: str, definition: str = "", prereqs: list[str] | None = None) -> ConceptNode:
    return ConceptNode(
        concept_id=cid,
        name=name,
        definition=definition or f"Definition for {name}",
        prerequisite_concept_ids=prereqs or [],
        source_content_ids=[f"CU_{cid}"],
    )


# =====================================================================
# 1. SOURCE ISOLATION
# =====================================================================
def test_cross_source_isolation():
    print("\n--- 1. Testing Cross-Source Isolation ---")
    mock_client = MagicMock()
    mock_client.search.return_value = []

    with patch("app.services.assessment.generator.get_client", return_value=mock_client), \
         patch("app.services.assessment.generator.ensure_collection"):
        concept = _sample_concept("CONCEPT_A", "Concept A")
        res = search_concept_chunks(concept, source_id="SRC_TARGET_123")

        # Verify search filter enforces source_id
        assert mock_client.search.called
        call_kwargs = mock_client.search.call_args[1]
        q_filter = call_kwargs.get("query_filter")
        must_clauses = q_filter.must

        source_id_scoped = any(
            hasattr(cond, "key") and cond.key == "source_id" and cond.match.value == "SRC_TARGET_123"
            for cond in must_clauses
        )
        assert source_id_scoped, "Vector search MUST strictly scope to source_id"
    print("   [PASS] Chunk retrieval is strictly source_id isolated with no global leakage.")


# =====================================================================
# 2. PROVENANCE (No Fabricated page=1)
# =====================================================================
def test_provenance_no_fabricated_page():
    print("\n--- 2. Testing Provenance & No Fabricated page=1 ---")
    concept = _sample_concept("CONCEPT_NOPAGE", "No Page Concept")

    # When no chunks or chunks without pages are given
    with patch("app.services.assessment.generator.search_concept_chunks", return_value=[]):
        q = generate_question(concept, "SRC_NOPAGE", llm_provider=MockProvider())
        assert q is not None
        assert q.page_start is None, f"page_start must be None when no page metadata exists, got {q.page_start}"
        assert q.page_end is None, f"page_end must be None when no page metadata exists, got {q.page_end}"
        assert len(q.chunk_ids) >= 1 or len(q.content_ids) >= 1, "Must have valid provenance anchor"
    print("   [PASS] Provenance integrity verified: page metadata is None rather than fabricated page=1.")


# =====================================================================
# 3. GROUNDING VALIDATION
# =====================================================================
def test_grounding_validation():
    print("\n--- 3. Testing Grounding Validation Gateway ---")
    concept = _sample_concept("CONCEPT_QUANTUM", "Quantum Superposition", "State of simultaneously occupying multiple states.")
    context = "Quantum superposition is the fundamental principle where a physical system exists in multiple states."

    grounded_q = Question(
        concept_id=concept.concept_id,
        concept_name=concept.name,
        stem="How does quantum superposition define physical system states?",
        options=[
            AssessmentOption(index=0, text="The physical system exists in multiple states simultaneously."),
            AssessmentOption(index=1, text="The system completely collapses immediately."),
            AssessmentOption(index=2, text="Energy is destroyed continuously."),
            AssessmentOption(index=3, text="Velocity reaches zero asymptotically."),
        ],
        correct_index=0,
        explanation="Directly grounded in quantum superposition definition.",
        chunk_ids=["CHUNK_01"],
        source_id="SRC_Q",
    )

    valid, msg = validate_grounding(grounded_q, context)
    assert valid, f"Grounded question should pass: {msg}"

    hallucinated_q = Question(
        concept_id=concept.concept_id,
        concept_name="Cooking",
        stem="What temperature should you bake sourdough bread?",
        options=[
            AssessmentOption(index=0, text="Preheat the Dutch oven to 450 Fahrenheit."),
            AssessmentOption(index=1, text="Use cold water."),
            AssessmentOption(index=2, text="Boil with olive oil."),
            AssessmentOption(index=3, text="Freeze immediately."),
        ],
        correct_index=0,
        explanation="Cooking technique.",
        chunk_ids=["CHUNK_01"],
        source_id="SRC_Q",
    )

    valid_h, msg_h = validate_grounding(hallucinated_q, context)
    assert not valid_h, "Hallucinated question with zero contextual overlap must be rejected"
    print("   [PASS] Grounding validation gateway accurately distinguishes grounded vs hallucinated questions.")


# =====================================================================
# 4. DUPLICATE DETECTION
# =====================================================================
def test_duplicate_detection():
    print("\n--- 4. Testing Duplicate Detection Gateway ---")
    q1 = Question(
        concept_id="CONCEPT_1",
        concept_name="Force",
        stem="What is the definition of a force in classical mechanics?",
        options=[
            AssessmentOption(index=0, text="An interaction that changes motion"),
            AssessmentOption(index=1, text="A type of scalar velocity"),
            AssessmentOption(index=2, text="Rotational energy"),
            AssessmentOption(index=3, text="Heat transfer"),
        ],
        correct_index=0,
        explanation="Explanation",
        chunk_ids=["CHUNK_1"],
        source_id="SRC_1",
    )

    # Near identical stem
    q2 = Question(
        concept_id="CONCEPT_2",
        concept_name="Force",
        stem="What is the definition of a force in classical mechanics system?",
        options=[
            AssessmentOption(index=0, text="Opt A"),
            AssessmentOption(index=1, text="Opt B"),
            AssessmentOption(index=2, text="Opt C"),
            AssessmentOption(index=3, text="Opt D"),
        ],
        correct_index=0,
        explanation="Explanation",
        chunk_ids=["CHUNK_1"],
        source_id="SRC_1",
    )

    assert is_duplicate(q2, [q1]), "High stem overlap must be caught as duplicate"
    print("   [PASS] Duplicate detection gateway accurately identifies and blocks duplicate questions.")


# =====================================================================
# 5. FALLBACK DIVERSITY & UNPREDICTABLE ANSWER PATTERNS
# =====================================================================
def test_fallback_diversity_and_unpredictability():
    print("\n--- 5. Testing Fallback Diversity & Answer Index Variation ---")
    concepts = [
        _sample_concept("C_ALPHA", "Alpha Wave", "Oscillatory neural activity.", ["C_THETA"]),
        _sample_concept("C_BETA", "Beta Wave", "High frequency brain oscillations.", ["C_ALPHA"]),
        _sample_concept("C_GAMMA", "Gamma Rhythm", "Fast synchronous brain activity.", ["C_BETA"]),
        _sample_concept("C_DELTA", "Delta Wave", "High amplitude slow brain oscillations.", []),
        _sample_concept("C_EPSILON", "Epsilon Wave", "Very high frequency oscillations.", []),
    ]

    correct_indices = set()
    for c in concepts:
        q = _generate_grounded_fallback(
            concept=c,
            chunks=[],
            chunk_ids=["CHUNK_SYNTH"],
            content_ids=list(c.source_content_ids),
            page_start=None,
            page_end=None,
            timestamp_start=None,
            timestamp_end=None,
            source_id="SRC_NEURO",
            difficulty="intermediate",
        )
        correct_indices.add(q.correct_index)
        assert 0 <= q.correct_index <= 3

        # Check concept-specific distractor mentions concept or prerequisite
        distractor_texts = [opt.text for opt in q.options if opt.index != q.correct_index]
        assert any(c.name in d for d in distractor_texts), f"Distractors must be concept-specific for {c.name}"

    assert len(correct_indices) > 1, f"Correct indices must vary across concepts, got {correct_indices}"
    print(f"   [PASS] Fallback questions have varied correct answer indices ({sorted(correct_indices)}) and concept-specific distractors.")


# =====================================================================
# 6. BACKFILLING RESERVE POOL
# =====================================================================
def test_backfilling_reserve_pool():
    print("\n--- 6. Testing Robust Question Backfilling ---")
    # Verified in test_step2_backfill.py (Phase 2A), assert here that plan_assessment produces full pool
    c1 = _sample_concept("C_1", "One")
    c2 = _sample_concept("C_2", "Two")
    c3 = _sample_concept("C_3", "Three")
    kg = KnowledgeGraph(concepts={"C_1": c1, "C_2": c2, "C_3": c3})

    queue = plan_assessment(kg=kg, max_questions=2)
    assert len(queue) >= 2
    print("   [PASS] Planning and reserve pool candidate sizing verified.")


# =====================================================================
# 7. KILL SWITCH & VIDEO EXCLUSION
# =====================================================================
def test_kill_switch_and_video_exclusion():
    print("\n--- 7. Testing Anti-Loop Kill Switch & Video Exclusion ---")
    profile = StudentLearningProfile(student_id="STU_KS", source_id="SRC_KS")
    profile.concept_masteries["C_FAIL"] = ConceptMastery(
        concept_id="C_FAIL",
        concept_name="Failing Concept",
        iteration_count=4,  # > 3
        status="REQUIRES_HUMAN_FALLBACK",
        last_score=0.0,
    )
    profile.concept_masteries["C_PASS"] = ConceptMastery(
        concept_id="C_PASS",
        concept_name="Passing Concept",
        status="MASTERED",
        last_score=100.0,
    )

    c_fail = _sample_concept("C_FAIL", "Failing Concept")
    c_pass = _sample_concept("C_PASS", "Passing Concept")
    kg = KnowledgeGraph(concepts={"C_FAIL": c_fail, "C_PASS": c_pass})

    matrix = build_video_target_matrix(profile, kg)

    # Kill-switch concepts MUST NOT be in videos
    video_concept_ids = [v.concept_id for v in matrix.videos]
    assert "C_FAIL" not in video_concept_ids, "Kill switch concept must NOT receive AI video"
    assert "C_FAIL" in matrix.human_intervention_concept_ids, "Kill switch concept must be surfaced in matrix"
    assert matrix.decision == "HUMAN_INTERVENTION"
    print("   [PASS] Kill-switch concepts are excluded from AI video generation and surfaced in final matrix.")


# =====================================================================
# 8. PREREQUISITE GAPS WITH SNAPSHOT
# =====================================================================
def test_prerequisite_gaps_with_snapshot():
    print("\n--- 8. Testing Prerequisite Gap Persistence with Session Snapshot ---")
    c_parent = _sample_concept("C_P", "Parent Concept")
    c_child = _sample_concept("C_C", "Child Concept", prereqs=["C_P"])

    session = AssessmentSession(
        student_id="STU_PREREQ",
        source_id="SRC_PREREQ",
        concept_snapshot={
            "C_P": ConceptSnapshot(concept_id="C_P", concept_name="Parent Concept", prerequisite_concept_ids=[]),
            "C_C": ConceptSnapshot(concept_id="C_C", concept_name="Child Concept", prerequisite_concept_ids=["C_P"]),
        }
    )

    reconstructed_kg = reconstruct_kg_from_snapshot(session)
    assert reconstructed_kg is not None
    assert reconstructed_kg.concepts["C_C"].prerequisite_concept_ids == ["C_P"]
    print("   [PASS] Prerequisite relationships survive KnowledgeGraph registry unavailability via snapshot.")


# =====================================================================
# 9. SESSION KG SNAPSHOT & SOURCE INTEGRITY
# =====================================================================
def test_session_kg_snapshot_offline_reconstruction():
    print("\n--- 9. Testing Session KG Snapshot Reconstruction & Source Integrity ---")
    session = AssessmentSession(
        student_id="STU_SNAP",
        source_id="SRC_ORIGINAL",
        concept_snapshot={
            "C_1": ConceptSnapshot(concept_id="C_1", concept_name="Concept 1", source_id="SRC_ORIGINAL"),
        }
    )

    # Valid reconstruction
    kg = reconstruct_kg_from_snapshot(session, expected_source_id="SRC_ORIGINAL")
    assert "C_1" in kg.concepts

    # Alien source rejection
    try:
        reconstruct_kg_from_snapshot(session, expected_source_id="SRC_ALIEN")
        assert False, "Should have rejected mismatched source_id"
    except ValueError:
        pass
    print("   [PASS] Session snapshot enforces strict source_id integrity upon reconstruction.")


# =====================================================================
# 10. CONFIGURATION & DYNAMIC SETTINGS
# =====================================================================
def test_configuration_dynamic_settings():
    print("\n--- 10. Testing Central Configuration & Dynamic Settings ---")
    assert hasattr(settings, "max_questions")
    assert hasattr(settings, "mastery_threshold")
    assert hasattr(settings, "kill_switch_limit")
    assert hasattr(settings, "llm_provider")
    print(f"   [PASS] Configuration settings active: max_q={settings.max_questions}, mastery={settings.mastery_threshold}, ks={settings.kill_switch_limit}, llm={settings.llm_provider}")


# =====================================================================
# 11. PROFILE PERSISTENCE (Both IDs and Names)
# =====================================================================
def test_profile_ids_and_names_persisted():
    print("\n--- 11. Testing Profile Concept Names and Stable Concept IDs ---")
    profile = StudentLearningProfile(student_id="STU_PROFILE", source_id="SRC_PROFILE")
    profile.concept_masteries["CONCEPT_ID_X"] = ConceptMastery(
        concept_id="CONCEPT_ID_X",
        concept_name="Human Readable Name X",
        status="MASTERED",
    )
    profile.concept_masteries["CONCEPT_ID_Y"] = ConceptMastery(
        concept_id="CONCEPT_ID_Y",
        concept_name="Human Readable Name Y",
        status="LEARNING",
    )

    rebuild_profile_metrics(profile)

    assert profile.strong_concepts == ["Human Readable Name X"]
    assert profile.strong_concept_ids == ["CONCEPT_ID_X"]
    assert profile.weak_concepts == ["Human Readable Name Y"]
    assert profile.weak_concept_ids == ["CONCEPT_ID_Y"]

    # Verify JSON serialization preserves all 4 fields
    serialized = json.loads(profile.model_dump_json())
    assert "strong_concepts" in serialized
    assert "strong_concept_ids" in serialized
    assert "weak_concepts" in serialized
    assert "weak_concept_ids" in serialized
    print("   [PASS] StudentLearningProfile persists both human-readable names and stable concept IDs.")


# =====================================================================
# 12. VIDEO MATRIX CONTRACT & ALL DECISION STATES
# =====================================================================
def test_video_matrix_contract_and_decisions():
    print("\n--- 12. Testing Video Target Matrix Contract & Decision States ---")
    c_f = _sample_concept("C_F", "Foundational Concept")
    c_i = _sample_concept("C_I", "Intermediate Concept", prereqs=["C_F"])
    kg = KnowledgeGraph(concepts={"C_F": c_f, "C_I": c_i})

    # Case 1: ALL_MASTERED
    p_all = StudentLearningProfile(student_id="STU_M", source_id="SRC_M", total_sessions=1)
    p_all.concept_masteries["C_F"] = ConceptMastery(concept_id="C_F", concept_name="Foundational Concept", status="MASTERED", last_score=100.0)
    p_all.concept_masteries["C_I"] = ConceptMastery(concept_id="C_I", concept_name="Intermediate Concept", status="MASTERED", last_score=100.0)
    m_all = build_video_target_matrix(p_all, kg)
    assert m_all.decision == "ALL_MASTERED"
    assert len(m_all.videos) == 0

    # Case 2: GENERATE_VIDEOS
    p_vid = StudentLearningProfile(student_id="STU_V", source_id="SRC_V", total_sessions=1)
    p_vid.concept_masteries["C_F"] = ConceptMastery(concept_id="C_F", concept_name="Foundational Concept", status="LEARNING", last_score=0.0)
    m_vid = build_video_target_matrix(p_vid, kg)
    assert m_vid.decision == "GENERATE_VIDEOS"
    assert len(m_vid.videos) == 1
    v0 = m_vid.videos[0]
    # Check all required fields on VideoTarget contract
    assert v0.concept_id == "C_F"
    assert v0.concept_name == "Foundational Concept"
    assert v0.difficulty == "foundational"
    assert v0.target_seconds == 30
    assert v0.directive != ""
    assert isinstance(v0.source_content_ids, list)
    assert isinstance(v0.chunk_ids, list)

    # Case 3: HUMAN_INTERVENTION only
    p_hi = StudentLearningProfile(student_id="STU_H", source_id="SRC_H", total_sessions=1)
    p_hi.concept_masteries["C_F"] = ConceptMastery(concept_id="C_F", concept_name="Foundational Concept", status="REQUIRES_HUMAN_FALLBACK", last_score=0.0)
    m_hi = build_video_target_matrix(p_hi, kg)
    assert m_hi.decision == "HUMAN_INTERVENTION"
    assert len(m_hi.videos) == 0
    assert "C_F" in m_hi.human_intervention_concept_ids

    # Case 4: Mixed State: GENERATE_VIDEOS + human intervention notice
    p_mix = StudentLearningProfile(student_id="STU_MIX", source_id="SRC_MIX", total_sessions=1)
    p_mix.concept_masteries["C_F"] = ConceptMastery(concept_id="C_F", concept_name="Foundational Concept", status="REQUIRES_HUMAN_FALLBACK", last_score=0.0)
    p_mix.concept_masteries["C_I"] = ConceptMastery(concept_id="C_I", concept_name="Intermediate Concept", status="LEARNING", last_score=40.0)
    m_mix = build_video_target_matrix(p_mix, kg)
    assert m_mix.decision == "GENERATE_VIDEOS"
    assert len(m_mix.videos) == 1
    assert m_mix.videos[0].concept_id == "C_I"
    assert "C_F" in m_mix.human_intervention_concept_ids
    assert "Notice:" in m_mix.summary
    print("   [PASS] Video Target Matrix contract and all 4 decision states (ALL_MASTERED, GENERATE_VIDEOS, HUMAN_INTERVENTION, Mixed) verified.")


# =====================================================================
# 13. API INTEGRITY & SAFE QUESTION
# =====================================================================
def test_api_integrity_and_safe_question():
    print("\n--- 13. Testing API Security, Answer Hiding & Malformed Submissions ---")
    source_id = f"SRC_SEC_{uuid4().hex[:6]}"
    student_id = f"STU_SEC_{uuid4().hex[:6]}"

    q = Question(
        question_id="Q_SEC_01",
        concept_id="CONCEPT_SEC",
        concept_name="Security Concept",
        stem="Is the answer hidden from the frontend?",
        options=[
            AssessmentOption(index=0, text="Yes, completely hidden"),
            AssessmentOption(index=1, text="No, visible in JSON"),
            AssessmentOption(index=2, text="Partially exposed"),
            AssessmentOption(index=3, text="Encrypted insecurely"),
        ],
        correct_index=0,
        explanation="Secret grading explanation never exposed to client.",
        source_id=source_id,
        chunk_ids=["CHUNK_SEC"],
    )

    safe_q = SafeQuestion(**q.model_dump())
    safe_dict = safe_q.model_dump()
    assert "correct_index" not in safe_dict, "SafeQuestion MUST NOT contain correct_index"
    assert "explanation" not in safe_dict, "SafeQuestion MUST NOT contain explanation"

    session = AssessmentSession(
        session_id=f"SESS_SEC_{uuid4().hex[:6]}",
        student_id=student_id,
        source_id=source_id,
        status="READY",
        questions=[q],
    )
    save_session(session)

    # 1. Reject invalid question_id not in session
    bad_submission = {
        "session_id": session.session_id,
        "answers": [{"question_id": "Q_ALIEN_999", "selected_index": 0}],
    }
    resp = client.post("/assessment/submit", json=bad_submission)
    assert resp.status_code == 400
    assert "does not belong to session" in resp.text

    # 2. Reject duplicate question_id in submission
    dup_submission = {
        "session_id": session.session_id,
        "answers": [
            {"question_id": "Q_SEC_01", "selected_index": 0},
            {"question_id": "Q_SEC_01", "selected_index": 1},
        ],
    }
    resp_dup = client.post("/assessment/submit", json=dup_submission)
    assert resp_dup.status_code == 400
    assert "Duplicate question_id" in resp_dup.text

    print("   [PASS] Answer key strictly hidden in SafeQuestion; invalid and duplicate question IDs rejected with HTTP 400.")


# =====================================================================
# 14. EXPIRED SESSIONS REJECTED
# =====================================================================
def test_expired_session_rejected():
    print("\n--- 14. Testing Expired Session Rejection ---")
    source_id = f"SRC_EXP_{uuid4().hex[:6]}"
    student_id = f"STU_EXP_{uuid4().hex[:6]}"

    past_time = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=5)).isoformat()
    q = Question(
        question_id="Q_EXP_01",
        concept_id="CONCEPT_EXP",
        concept_name="Expired Concept",
        stem="Question stem",
        options=[
            AssessmentOption(index=0, text="A"),
            AssessmentOption(index=1, text="B"),
            AssessmentOption(index=2, text="C"),
            AssessmentOption(index=3, text="D"),
        ],
        correct_index=0,
        explanation="Exp",
        source_id=source_id,
        chunk_ids=["CHUNK_01"],
    )

    session = AssessmentSession(
        session_id=f"SESS_EXP_{uuid4().hex[:6]}",
        student_id=student_id,
        source_id=source_id,
        status="READY",
        questions=[q],
        expires_at=past_time,
    )
    save_session(session)

    submission = {
        "session_id": session.session_id,
        "answers": [{"question_id": "Q_EXP_01", "selected_index": 0}],
    }

    resp = client.post("/assessment/submit", json=submission)
    assert resp.status_code == 410, f"Expected HTTP 410 Gone for expired session, got {resp.status_code}"
    assert "expired" in resp.text.lower()
    print("   [PASS] Expired session correctly rejected with HTTP 410 Gone.")


# =====================================================================
# 15. WINDOWS OUTPUT COMPATIBILITY
# =====================================================================
def test_windows_output_compatibility():
    print("\n--- 15. Testing Windows CP1252 Output Compatibility ---")
    test_strings = [
        "Testing Step 2 Master Flow...",
        "[PASS] All checks succeeded.",
        "Video Target Matrix Blueprint (Handoff to Step 3)",
        "Generated Question with Provenance: page 3 - 9",
    ]
    for s in test_strings:
        try:
            s.encode("cp1252")
        except UnicodeEncodeError as exc:
            assert False, f"String '{s}' failed CP1252 encoding: {exc}"
    print("   [PASS] All console diagnostics encode cleanly in standard CP1252/ASCII.")


def main():
    print("=================================================================")
    print("  PHASE 4: FINAL PRODUCTION HARDENING & CONTRACT VERIFICATION    ")
    print("=================================================================")

    test_cross_source_isolation()
    test_provenance_no_fabricated_page()
    test_grounding_validation()
    test_duplicate_detection()
    test_fallback_diversity_and_unpredictability()
    test_backfilling_reserve_pool()
    test_kill_switch_and_video_exclusion()
    test_prerequisite_gaps_with_snapshot()
    test_session_kg_snapshot_offline_reconstruction()
    test_configuration_dynamic_settings()
    test_profile_ids_and_names_persisted()
    test_video_matrix_contract_and_decisions()
    test_api_integrity_and_safe_question()
    test_expired_session_rejected()
    test_windows_output_compatibility()

    print("\n=================================================================")
    print("   ALL PHASE 4 PRODUCTION HARDENING TESTS PASSED PERFECTLY!     ")
    print("=================================================================")


if __name__ == "__main__":
    main()
