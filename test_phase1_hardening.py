"""Phase 1 Critical Correctness Hardening Unit & Integration Tests.

Covers:
1. Cross-source retrieval elimination (search_layer_a and search_concept_chunks).
2. Anti-loop kill switch exclusion (REQUIRES_HUMAN_FALLBACK excluded from planner).
3. Deterministic source-grounded fallback question generation (stable hash index, no collisions).
4. Cross-source assessment isolation (Source A vs Source B).
"""

import hashlib
from unittest.mock import MagicMock, patch

from app.db.vector_store import search_layer_a
from app.services.assessment.generator import (
    _generate_grounded_fallback,
    _stable_hash_int,
    generate_question,
    search_concept_chunks,
)
from app.services.assessment.planner import plan_assessment
from app.services.assessment.schemas import ConceptMastery, StudentLearningProfile
from app.services.assessment.validator import is_duplicate, validate_question
from app.services.schemas import ConceptNode, KnowledgeGraph


# =====================================================================
# 1. Cross-Source Retrieval Elimination Tests
# =====================================================================

def test_search_layer_a_filters_by_source_id():
    """Verify search_layer_a strictly enforces source_id filter."""
    mock_client = MagicMock()
    mock_hit_a = MagicMock()
    mock_hit_a.payload = {"layer": "A", "source_id": "SRC_AAA", "text": "Content A"}
    mock_client.search.return_value = [mock_hit_a]

    with patch("app.db.vector_store.get_client", return_value=mock_client), \
         patch("app.db.vector_store._embed", return_value=[[0.1] * 768]):
        
        results = search_layer_a("test query", limit=5, source_id="SRC_AAA")
        
        assert len(results) == 1
        assert results[0]["source_id"] == "SRC_AAA"
        
        # Verify the Qdrant filter had both layer='A' AND source_id='SRC_AAA'
        call_args = mock_client.search.call_args
        q_filter = call_args.kwargs.get("query_filter")
        must_keys = [(cond.key, cond.match.value) for cond in q_filter.must]
        assert ("layer", "A") in must_keys
        assert ("source_id", "SRC_AAA") in must_keys


def test_cross_source_retrieval_never_returns_other_source():
    """Verify Source B chunks are NEVER returned when querying Source A."""
    concept = ConceptNode(
        concept_id="CONCEPT_QUANTUM",
        name="Quantum Superposition",
        definition="Particles can exist in multiple states simultaneously.",
        source_content_ids=["CU_A1"],
    )

    # Chunks from Source B (e.g. Biology)
    provided_chunks_b = [
        {
            "chunk_id": "CHUNK_BIO_01",
            "source_id": "SRC_BIOLOGY",
            "text": "Mitochondria are the powerhouse of the cell.",
            "concept_ids": ["CONCEPT_MITOCHONDRIA"],
            "content_ids": ["CU_B1"],
        }
    ]

    # Querying for Source A with provided chunks from Source B should filter them out
    results = search_concept_chunks(
        concept=concept,
        source_id="SRC_PHYSICS",
        limit=5,
        provided_chunks=provided_chunks_b,
    )
    assert len(results) == 0, "Source B chunks must NEVER be returned for Source A query"


def test_vector_search_no_fallback_without_source_id():
    """Verify generator does not execute unconstrained Layer A search when source search is empty."""
    concept = ConceptNode(
        concept_id="CONCEPT_TEST",
        name="Test Concept",
        definition="A test concept.",
        source_content_ids=[],
    )

    mock_client = MagicMock()
    # Mock source-specific search returning empty
    mock_client.search.return_value = []

    with patch("app.services.assessment.generator.get_client", return_value=mock_client), \
         patch("app.services.assessment.generator._embed", return_value=[[0.1] * 768]):
        
        results = search_concept_chunks(concept, source_id="SRC_EMPTY", limit=5)
        
        # Must only call search once with source_id condition, never without it
        assert mock_client.search.call_count == 1
        call_args = mock_client.search.call_args
        q_filter = call_args.kwargs.get("query_filter")
        filter_keys = [c.key for c in q_filter.must]
        assert "source_id" in filter_keys, "Search must strictly include source_id"
        assert results == []


# =====================================================================
# 2. Anti-Loop Kill Switch Exclusion Tests
# =====================================================================

def test_kill_switch_concept_excluded_from_planner():
    """Verify concepts tagged REQUIRES_HUMAN_FALLBACK are NEVER scheduled by planner."""
    kg = KnowledgeGraph(
        concepts={
            "CONCEPT_BASIC": ConceptNode(
                concept_id="CONCEPT_BASIC",
                name="Basic Concept",
                definition="Foundational concept",
                prerequisite_concept_ids=[],
            ),
            "CONCEPT_STUCK": ConceptNode(
                concept_id="CONCEPT_STUCK",
                name="Stuck Concept",
                definition="A concept the student failed >3 times",
                prerequisite_concept_ids=["CONCEPT_BASIC"],
            ),
            "CONCEPT_LEARNING": ConceptNode(
                concept_id="CONCEPT_LEARNING",
                name="Learning Concept",
                definition="A concept currently in progress",
                prerequisite_concept_ids=["CONCEPT_BASIC"],
            ),
        }
    )

    profile = StudentLearningProfile(student_id="STU_001", source_id="SRC_001")
    # Mark CONCEPT_STUCK as kill-switch triggered
    profile.concept_masteries["CONCEPT_STUCK"] = ConceptMastery(
        concept_id="CONCEPT_STUCK",
        concept_name="Stuck Concept",
        status="REQUIRES_HUMAN_FALLBACK",
        iteration_count=4,
    )
    # Mark CONCEPT_LEARNING as in-progress
    profile.concept_masteries["CONCEPT_LEARNING"] = ConceptMastery(
        concept_id="CONCEPT_LEARNING",
        concept_name="Learning Concept",
        status="LEARNING",
        attempts=1,
    )

    planned = plan_assessment(kg=kg, profile=profile, max_questions=5)
    planned_ids = [c.concept_id for c in planned]

    # CONCEPT_STUCK must NOT be in the planned queue
    assert "CONCEPT_STUCK" not in planned_ids, (
        "Anti-loop kill switch violation: REQUIRES_HUMAN_FALLBACK concept was scheduled!"
    )
    # Normal LEARNING concept MUST be scheduled
    assert "CONCEPT_LEARNING" in planned_ids, "Normal LEARNING concepts must be scheduled"


# =====================================================================
# 3. Deterministic Source-Grounded Fallback Generation Tests
# =====================================================================

def test_fallback_questions_multi_concept_validity_and_diversity():
    """Generate fallback questions for 5 distinct concepts and verify:
    - Structurally valid (validate_question passes)
    - correct_index is deterministically distributed across {0, 1, 2, 3}
    - No duplicate collisions (is_duplicate is False across all pairs)
    - Source provenance is strictly preserved
    """
    concepts = [
        ConceptNode(
            concept_id="CONCEPT_C1",
            name="Alpha Factor",
            definition="The initial rate of system transformation.",
            source_content_ids=["CU_01"],
        ),
        ConceptNode(
            concept_id="CONCEPT_C2",
            name="Beta Coefficient",
            definition="The proportional variance between two observable vectors.",
            source_content_ids=["CU_02"],
        ),
        ConceptNode(
            concept_id="CONCEPT_C3",
            name="Gamma Decay",
            definition="Emission of electromagnetic radiation of extremely high frequency.",
            source_content_ids=["CU_03"],
        ),
        ConceptNode(
            concept_id="CONCEPT_C4",
            name="Delta Equilibrium",
            definition="A balanced condition where aggregate input equals aggregate output.",
            source_content_ids=["CU_04"],
        ),
        ConceptNode(
            concept_id="CONCEPT_C5",
            name="Epsilon Gradient",
            definition="The directional derivative representing maximal change in potential.",
            source_content_ids=["CU_05"],
        ),
    ]

    mock_chunks = [
        {
            "chunk_id": f"CHUNK_{c.concept_id}",
            "source_id": "SRC_MATH",
            "text": f"{c.name} is defined as: {c.definition}",
            "page_start": i + 1,
            "page_end": i + 1,
            "concept_ids": [c.concept_id],
            "content_ids": c.source_content_ids,
        }
        for i, c in enumerate(concepts)
    ]

    generated_questions = []
    correct_indices = []

    for c in concepts:
        # Force fallback by providing empty API key
        with patch("app.core.config.settings.gemini_api_key", ""):
            q = generate_question(
                concept=c,
                source_id="SRC_MATH",
                provided_chunks=mock_chunks,
            )
        assert q is not None, f"Failed to generate question for {c.name}"
        
        # 1. Structural validity
        is_valid, err = validate_question(q)
        assert is_valid, f"Question for {c.name} failed validation: {err}"
        
        # 2. Source provenance
        assert q.source_id == "SRC_MATH"
        assert len(q.options) == 4
        assert q.correct_index in (0, 1, 2, 3)
        correct_indices.append(q.correct_index)

        # 3. Verify options within the question are unique
        option_texts = [opt.text.strip().lower() for opt in q.options]
        assert len(set(option_texts)) == 4, f"Options for {c.name} contain duplicates"

        # 4. Check against previously generated questions for duplicates
        assert not is_duplicate(q, generated_questions), (
            f"Question for {c.name} collided with existing questions as duplicate!"
        )
        generated_questions.append(q)

    # Verify correct indices are not all identical (distributed across options)
    unique_indices = set(correct_indices)
    assert len(unique_indices) > 1, f"Correct indices should be distributed, got: {correct_indices}"
    print(f"Generated {len(generated_questions)} valid questions. Correct index distribution: {correct_indices}")


def test_stable_hash_is_deterministic_across_calls():
    """Verify _stable_hash_int returns identical values for identical inputs."""
    h1 = _stable_hash_int("CONCEPT_FORCE", 4)
    h2 = _stable_hash_int("CONCEPT_FORCE", 4)
    assert h1 == h2
    assert 0 <= h1 < 4


# =====================================================================
# 4. End-to-End Cross-Source Isolation & Assessment Flow Test
# =====================================================================

def test_cross_source_assessment_isolation_end_to_end():
    """Test that Source A assessment strictly uses Source A chunks and
    Source B assessment strictly uses Source B chunks.
    Verifies full pipeline: start -> validate -> submit -> profile -> video matrix.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.assessment.profile import load_profile

    client = TestClient(app)

    # Payload for Source A (Classical Mechanics)
    source_a_json = {
        "status": "READY",
        "source_id": "SRC_ISOLATION_PHYSICS",
        "asset_id": "AST_PHYS_01",
        "filename": "physics.pdf",
        "topic_blueprint": {
            "topic_name": "Physics",
            "key_concepts": ["Kinematics", "Dynamics"],
        },
        "knowledge_graph": {
            "concepts": {
                "CONCEPT_KIN": {
                    "concept_id": "CONCEPT_KIN",
                    "name": "Kinematics",
                    "definition": "The branch of mechanics describing the motion of points and objects.",
                    "prerequisite_concept_ids": [],
                    "source_content_ids": ["CU_PHYS_1"],
                },
                "CONCEPT_DYN": {
                    "concept_id": "CONCEPT_DYN",
                    "name": "Dynamics",
                    "definition": "The study of forces and their effect on motion.",
                    "prerequisite_concept_ids": ["CONCEPT_KIN"],
                    "source_content_ids": ["CU_PHYS_2"],
                },
            }
        },
        "chunks": [
            {
                "chunk_id": "CHUNK_PHYS_A1",
                "source_id": "SRC_ISOLATION_PHYSICS",
                "text": "Kinematics describes motion without considering its causes.",
                "page_start": 1,
                "page_end": 2,
                "concept_ids": ["CONCEPT_KIN"],
                "content_ids": ["CU_PHYS_1"],
            },
            {
                "chunk_id": "CHUNK_PHYS_A2",
                "source_id": "SRC_ISOLATION_PHYSICS",
                "text": "Dynamics analyzes how forces influence acceleration and momentum.",
                "page_start": 5,
                "page_end": 6,
                "concept_ids": ["CONCEPT_DYN"],
                "content_ids": ["CU_PHYS_2"],
            },
        ],
    }

    # Payload for Source B (Molecular Biology)
    source_b_json = {
        "status": "READY",
        "source_id": "SRC_ISOLATION_BIOLOGY",
        "asset_id": "AST_BIO_01",
        "filename": "biology.pdf",
        "topic_blueprint": {
            "topic_name": "Biology",
            "key_concepts": ["DNA Replication", "Transcription"],
        },
        "knowledge_graph": {
            "concepts": {
                "CONCEPT_REP": {
                    "concept_id": "CONCEPT_REP",
                    "name": "DNA Replication",
                    "definition": "The biological process of producing two identical replicas of DNA from one original DNA molecule.",
                    "prerequisite_concept_ids": [],
                    "source_content_ids": ["CU_BIO_1"],
                },
                "CONCEPT_TXN": {
                    "concept_id": "CONCEPT_TXN",
                    "name": "Transcription",
                    "definition": "The process of copying a segment of DNA into RNA.",
                    "prerequisite_concept_ids": ["CONCEPT_REP"],
                    "source_content_ids": ["CU_BIO_2"],
                },
            }
        },
        "chunks": [
            {
                "chunk_id": "CHUNK_BIO_B1",
                "source_id": "SRC_ISOLATION_BIOLOGY",
                "text": "DNA replication occurs during the S phase of the cell cycle.",
                "page_start": 20,
                "page_end": 21,
                "concept_ids": ["CONCEPT_REP"],
                "content_ids": ["CU_BIO_1"],
            },
            {
                "chunk_id": "CHUNK_BIO_B2",
                "source_id": "SRC_ISOLATION_BIOLOGY",
                "text": "RNA polymerase synthesizes RNA transcript from template DNA strand.",
                "page_start": 30,
                "page_end": 31,
                "concept_ids": ["CONCEPT_TXN"],
                "content_ids": ["CU_BIO_2"],
            },
        ],
    }

    # 1. Start Assessment for Source A
    resp_a = client.post(
        "/assessment/start",
        json={
            "student_id": "STU_ISOLATION_TEST",
            "source_id": "SRC_ISOLATION_PHYSICS",
            "step1_output": source_a_json,
        },
    )
    assert resp_a.status_code == 200, f"Source A start failed: {resp_a.text}"
    data_a = resp_a.json()
    assert data_a["source_id"] == "SRC_ISOLATION_PHYSICS"
    # Check that every question in Source A quiz has chunk_ids matching CHUNK_PHYS_
    for q in data_a["questions"]:
        for ch_id in q["chunk_ids"]:
            assert "BIO" not in ch_id, f"Cross-source leak! Biology chunk {ch_id} found in Physics quiz"

    # 2. Start Assessment for Source B
    resp_b = client.post(
        "/assessment/start",
        json={
            "student_id": "STU_ISOLATION_TEST",
            "source_id": "SRC_ISOLATION_BIOLOGY",
            "step1_output": source_b_json,
        },
    )
    assert resp_b.status_code == 200, f"Source B start failed: {resp_b.text}"
    data_b = resp_b.json()
    assert data_b["source_id"] == "SRC_ISOLATION_BIOLOGY"
    # Check that every question in Source B quiz has chunk_ids matching CHUNK_BIO_
    for q in data_b["questions"]:
        for ch_id in q["chunk_ids"]:
            assert "PHYS" not in ch_id, f"Cross-source leak! Physics chunk {ch_id} found in Biology quiz"

    # 3. Submit Source A Assessment
    answers_a = [{"question_id": q["question_id"], "selected_index": 0} for q in data_a["questions"]]
    resp_submit_a = client.post(
        "/assessment/submit",
        json={"session_id": data_a["session_id"], "answers": answers_a},
    )
    assert resp_submit_a.status_code == 200
    submit_data_a = resp_submit_a.json()
    assert submit_data_a["status"] == "SUBMITTED"
    assert "video_target_matrix" in submit_data_a

    # 4. Verify profile persisted for Source A
    profile_a = load_profile("STU_ISOLATION_TEST", "SRC_ISOLATION_PHYSICS")
    assert profile_a is not None
    assert profile_a.student_id == "STU_ISOLATION_TEST"
    assert profile_a.source_id == "SRC_ISOLATION_PHYSICS"

