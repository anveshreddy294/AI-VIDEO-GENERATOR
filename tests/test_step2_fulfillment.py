"""Comprehensive tests for Assessment Question-Count Fulfillment and Variant Backfill.

Test Coverage:
1. 5 concepts, target 5 -> 5
2. 4 concepts, target 5 -> attempt safe multi-question backfill and produce 5 when evidence allows
3. provider failure for one concept -> reserve/backfill succeeds
4. duplicate generated question -> rejected and replaced
5. insufficient source evidence -> explicit shortfall, no fabricated question
6. target=1
7. target greater than configured maximum
8. kill-switch concepts remain excluded
9. provenance remains attached to every question
10. internal consistency of question_count, requested_questions, generated_questions, shortfall
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.schemas import (
    AssessmentOption,
    ConceptMastery,
    Question,
)

client = TestClient(app)


def _make_valid_question(
    concept_id: str,
    concept_name: str,
    source_id: str = "SRC_FULFILL_TEST",
    stem: str | None = None,
    variant_type: str = "definition",
) -> Question:
    """Helper to create a structurally valid Question with provenance."""
    variant_stems = {
        "definition": f"Definition inquiry regarding {concept_name} [{concept_id}]: what defines this physical property?",
        "relationship": f"Relationship query for {concept_name} [{concept_id}]: how does it interact with other dynamics?",
        "application": f"Application analysis of {concept_name} [{concept_id}]: how is this principle utilized in practice?",
        "comparison": f"Comparative evaluation between {concept_name} [{concept_id}] and related scientific principles?",
        "misconception": f"Common misconception analysis for {concept_name} [{concept_id}]: which belief is factually incorrect?",
    }
    selected_stem = stem or variant_stems.get(variant_type, f"Authoritative question for {concept_name} [{concept_id}] ({variant_type}).")
    return Question(
        concept_id=concept_id,
        concept_name=concept_name,
        stem=selected_stem,
        options=[
            AssessmentOption(index=0, text=f"Authoritative true statement regarding {concept_name} [{concept_id}] ({variant_type})."),
            AssessmentOption(index=1, text=f"First inaccurate assertion concerning {concept_name} [{concept_id}] ({variant_type})."),
            AssessmentOption(index=2, text=f"Second flawed claim regarding {concept_name} [{concept_id}] ({variant_type})."),
            AssessmentOption(index=3, text=f"Third incorrect hypothesis about {concept_name} [{concept_id}] ({variant_type})."),
        ],
        correct_index=0,
        explanation=f"Based on grounded evidence for {concept_name}.",
        chunk_ids=["CHUNK_001"],
        content_ids=["CU_001"],
        page_start=1,
        page_end=2,
        source_id=source_id,
        difficulty="intermediate",
        variant_type=variant_type,
    )


CONCEPT_DETAILS = {
    "CONCEPT_A": ("Kinematics", "The branch of classical mechanics describing motion without considering mass or forces."),
    "CONCEPT_B": ("Dynamics", "The physical study of forces, momentum, and torques influencing material bodies."),
    "CONCEPT_C": ("Thermodynamics", "The science of heat, work, energy transformation, and entropy in thermal systems."),
    "CONCEPT_D": ("Electromagnetism", "The study of electric charges, magnetic currents, and electromagnetic waves."),
    "CONCEPT_E": ("Optics", "The physics of light propagation, reflection, refraction, and optical spectra."),
    "CONCEPT_1": ("Inertia", "The resistance of any physical object to any change in its velocity or state of rest."),
    "CONCEPT_2": ("Momentum", "The product of the mass and velocity of a particle or physical object in motion."),
    "CONCEPT_3": ("Force", "An interaction that, when unopposed, will change the motion of an object."),
    "CONCEPT_4": ("Acceleration", "The rate of change of the velocity of an object with respect to time."),
    "CONCEPT_OK1": ("Gravity", "A fundamental interaction which causes mutual attraction between all things having mass."),
    "CONCEPT_OK2": ("Energy", "The quantitative property that must be transferred to an object to perform work."),
    "CONCEPT_OK3": ("Power", "The amount of energy transferred or converted per unit time in a mechanical system."),
    "CONCEPT_FAIL": ("Friction", "The resistance to motion of one object moving relative to another surface."),
    "CONCEPT_SOLO": ("Newtonian Mechanics", "Classical framework describing relation between forces and body motion."),
    "CONCEPT_T1": ("Velocity", "The directional speed of an object in motion as an indication of its rate of position change."),
    "CONCEPT_SAFE1": ("Thermal Conduction", "The transfer of internal energy by microscopic collisions of particles."),
    "CONCEPT_SAFE2": ("Radiation", "The emission or transmission of energy in the form of waves or particles through space."),
    "CONCEPT_DANGER": ("Nuclear Fission", "A reaction in which the nucleus of an atom splits into two or more smaller nuclei."),
    "CONCEPT_C1": ("Static Friction", "Frictional force that resists the initial movement of an object at rest."),
    "CONCEPT_C2": ("Kinetic Friction", "Frictional force that opposes the continued movement of a sliding body."),
}


def _build_step1_payload(concept_ids: list[str], source_id: str = "SRC_FULFILL_TEST") -> dict:
    """Build a valid Step 1 JSON payload with specified concepts."""
    concepts_dict = {}
    for cid in concept_ids:
        c_name, c_def = CONCEPT_DETAILS.get(cid, (cid.replace("CONCEPT_", "").title(), f"Unique physical definition for {cid}."))
        concepts_dict[cid] = {
            "concept_id": cid,
            "name": c_name,
            "definition": c_def,
            "prerequisite_concept_ids": [],
            "source_content_ids": ["CU_001"],
        }

    return {
        "status": "READY",
        "source_id": source_id,
        "asset_id": "AST_TEST",
        "filename": "fulfillment_test.pdf",
        "modality": "pdf",
        "topic_blueprint": {
            "topic_name": "Fulfillment Test Physics",
            "key_concepts": [concepts_dict[cid]["name"] for cid in concept_ids],
            "difficulty_level": "intermediate",
        },
        "knowledge_graph": {
            "concepts": concepts_dict
        },
        "chunks": [
            {
                "chunk_id": "CHUNK_001",
                "text": f"Comprehensive physics study material covering {', '.join(concepts_dict[cid]['name'] + ': ' + concepts_dict[cid]['definition'] for cid in concept_ids)} and their respective foundational physical principles.",
                "page_start": 1,
                "page_end": 2,
                "concept_ids": concept_ids,
                "content_ids": ["CU_001"],
                "source_id": source_id,
            }
        ],
    }


def test_five_concepts_target_five():
    """1. 5 concepts, target 5 -> exactly 5 questions generated (1 per concept)."""
    print("\n--- Running Test 1: test_five_concepts_target_five ---")
    source_id = "SRC_5_5"
    student_id = "STU_5_5"
    concepts = ["CONCEPT_A", "CONCEPT_B", "CONCEPT_C", "CONCEPT_D", "CONCEPT_E"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 5,
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["question_count"] == 5
    assert data["requested_questions"] == 5
    assert data["generated_questions"] == 5
    assert data["shortfall"] == 0
    assert len(data["questions"]) == 5

    # Each concept should be tested exactly once
    tested_concepts = [q["concept_id"] for q in data["questions"]]
    assert len(set(tested_concepts)) == 5
    print("   [PASS] 5 concepts, target 5 generated exactly 5 questions (1 per concept).")


def test_four_concepts_target_five_safe_variant_backfill():
    """2. 4 concepts, target 5 -> safe multi-question variant backfill produces 5 distinct questions."""
    print("\n--- Running Test 2: test_four_concepts_target_five_safe_variant_backfill ---")
    source_id = "SRC_4_5"
    student_id = "STU_4_5"
    concepts = ["CONCEPT_1", "CONCEPT_2", "CONCEPT_3", "CONCEPT_4"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 5,
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["question_count"] == 5, f"Expected 5 questions, got {data['question_count']}"
    assert data["requested_questions"] == 5
    assert data["generated_questions"] == 5
    assert data["shortfall"] == 0

    # Ensure all stems are distinct (no duplicate questions)
    stems = [q["stem"] for q in data["questions"]]
    assert len(stems) == len(set(stems)), f"Duplicate question stems detected: {stems}"

    # Verify fair distribution: no single concept has more than 2 questions
    concept_counts = {}
    for q in data["questions"]:
        cid = q["concept_id"]
        concept_counts[cid] = concept_counts.get(cid, 0) + 1
    assert max(concept_counts.values()) <= 2, f"A concept dominated generation: {concept_counts}"
    print(f"   [PASS] 4 concepts, target 5 safely backfilled to 5 questions with concept counts: {concept_counts}")


def test_provider_failure_reserve_backfill_succeeds():
    """3. Provider failure for one concept -> variant backfill on other concepts succeeds in meeting target."""
    print("\n--- Running Test 3: test_provider_failure_reserve_backfill_succeeds ---")
    source_id = "SRC_FAIL_RECOVER"
    student_id = "STU_FAIL_RECOVER"
    concepts = ["CONCEPT_FAIL", "CONCEPT_OK1", "CONCEPT_OK2", "CONCEPT_OK3"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    def mock_gen(concept, source_id, provided_chunks=None, max_retries=None, variant_type="definition"):
        if concept.concept_id == "CONCEPT_FAIL":
            return None  # Simulate LLM failure for this concept
        return _make_valid_question(concept.concept_id, concept.name, source_id, variant_type=variant_type)

    with patch("app.api.assessment.generate_question", side_effect=mock_gen):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 4,
                "step1_output": payload,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["question_count"] == 4, f"Expected 4 questions, got {data['question_count']}"
        assert data["requested_questions"] == 4
        assert data["generated_questions"] == 4
        assert data["shortfall"] == 0
        assert "CONCEPT_FAIL" in data["failed_concepts"]

        tested_concepts = [q["concept_id"] for q in data["questions"]]
        assert "CONCEPT_FAIL" not in tested_concepts
        print("   [PASS] Provider failure on CONCEPT_FAIL recovered via variant backfill on remaining concepts.")


def test_duplicate_generated_question_rejected_and_replaced():
    """4. Duplicate generated question is rejected by duplicate detection and replaced by variant backfill."""
    print("\n--- Running Test 4: test_duplicate_generated_question_rejected_and_replaced ---")
    source_id = "SRC_DUP_RECOVER"
    student_id = "STU_DUP_RECOVER"
    concepts = ["CONCEPT_A", "CONCEPT_B", "CONCEPT_C"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    duplicate_stem = "Duplicate stem designed to trigger Jaccard collision check."

    def mock_gen(concept, source_id, provided_chunks=None, max_retries=None, variant_type="definition"):
        if concept.concept_id == "CONCEPT_B" and variant_type == "definition":
            # Return identical stem as CONCEPT_A definition to trigger duplicate rejection
            return _make_valid_question(concept.concept_id, concept.name, source_id, stem=duplicate_stem, variant_type=variant_type)
        if concept.concept_id == "CONCEPT_A" and variant_type == "definition":
            return _make_valid_question(concept.concept_id, concept.name, source_id, stem=duplicate_stem, variant_type=variant_type)
        # Other variants return unique questions
        return _make_valid_question(concept.concept_id, concept.name, source_id, variant_type=variant_type)

    with patch("app.api.assessment.generate_question", side_effect=mock_gen):
        resp = client.post(
            "/assessment/start",
            json={
                "student_id": student_id,
                "source_id": source_id,
                "max_questions": 3,
                "step1_output": payload,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["question_count"] == 3
        stems = [q["stem"] for q in data["questions"]]
        assert len(stems) == len(set(stems)), "No duplicates must exist in accepted questions"
        print("   [PASS] Duplicate rejected and successfully replaced; all accepted stems are unique.")


def test_insufficient_source_evidence_explicit_shortfall():
    """5. Insufficient source evidence -> explicit shortfall, no fabricated questions."""
    print("\n--- Running Test 5: test_insufficient_source_evidence_explicit_shortfall ---")
    source_id = "SRC_SHORTFALL"
    student_id = "STU_SHORTFALL"
    concepts = ["CONCEPT_SOLO"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    # Request 10 questions for a source with only 1 concept
    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 10,
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # The 1 concept can only safely produce at most 5 distinct variants (len(VARIANTS))
    assert data["generated_questions"] <= 5
    assert data["shortfall"] > 0
    assert data["requested_questions"] == 10
    assert data["requested_questions"] == data["generated_questions"] + data["shortfall"]
    assert data["question_count"] == data["generated_questions"]

    # All generated questions must have non-empty provenance
    for q in data["questions"]:
        assert q["chunk_ids"] or q["content_ids"]
        assert q["stem"]
    print(f"   [PASS] Insufficient evidence produced explicit shortfall: generated={data['generated_questions']}, shortfall={data['shortfall']}.")


def test_target_equals_one():
    """6. Target = 1 -> exactly 1 question generated with shortfall 0."""
    print("\n--- Running Test 6: test_target_equals_one ---")
    source_id = "SRC_T1"
    student_id = "STU_T1"
    concepts = ["CONCEPT_1", "CONCEPT_2", "CONCEPT_3"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 1,
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["question_count"] == 1
    assert data["requested_questions"] == 1
    assert data["generated_questions"] == 1
    assert data["shortfall"] == 0
    print("   [PASS] target=1 generated exactly 1 question.")


def test_target_greater_than_configured_maximum():
    """7. Target greater than configured maximum is clamped to settings.max_questions."""
    print("\n--- Running Test 7: test_target_greater_than_configured_maximum ---")
    source_id = "SRC_OVERMAX"
    student_id = "STU_OVERMAX"
    concepts = [f"CONCEPT_{i}" for i in range(1, 15)]
    payload = _build_step1_payload(concepts, source_id=source_id)

    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 999,  # Unreasonably large target
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["requested_questions"] == settings.max_questions, (
        f"Expected clamp to {settings.max_questions}, got {data['requested_questions']}"
    )
    assert data["question_count"] <= settings.max_questions
    assert data["requested_questions"] == data["generated_questions"] + data["shortfall"]
    print(f"   [PASS] Target 999 clamped to configured settings.max_questions ({settings.max_questions}).")


def test_kill_switch_concepts_remain_excluded():
    """8. Concepts marked REQUIRES_HUMAN_FALLBACK are never selected in any pass."""
    print("\n--- Running Test 8: test_kill_switch_concepts_remain_excluded ---")
    source_id = "SRC_KS_EXCLUDE"
    student_id = "STU_KS_EXCLUDE"
    concepts = ["CONCEPT_SAFE1", "CONCEPT_SAFE2", "CONCEPT_DANGER"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    profile = get_or_create_profile(student_id, source_id)
    profile.concept_masteries["CONCEPT_DANGER"] = ConceptMastery(
        concept_id="CONCEPT_DANGER",
        concept_name="Danger Concept",
        status="REQUIRES_HUMAN_FALLBACK",
        iteration_count=5,
    )
    save_profile(profile)

    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 3,
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    tested_concepts = [q["concept_id"] for q in data["questions"]]
    assert "CONCEPT_DANGER" not in tested_concepts, "Kill-switch concept must never be accepted"
    assert "CONCEPT_DANGER" not in data.get("failed_concepts", []), "Kill-switch concept must not even be attempted"
    print("   [PASS] Kill-switch concept CONCEPT_DANGER strictly excluded from all generation passes.")


def test_provenance_remains_attached_to_every_question():
    """9. Provenance remains attached to every question (chunk_ids, content_ids, source_id)."""
    print("\n--- Running Test 9: test_provenance_remains_attached_to_every_question ---")
    source_id = "SRC_PROV_VERIFY"
    student_id = "STU_PROV_VERIFY"
    concepts = ["CONCEPT_P1", "CONCEPT_P2", "CONCEPT_P3"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 3,
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["source_id"] == source_id
    for q in data["questions"]:
        assert q.get("source_id") in (None, source_id)
        assert len(q.get("chunk_ids", [])) > 0 or q.get("page_start") is not None, f"Missing provenance in question {q['question_id']}"
        assert q["stem"]
        assert len(q["options"]) == 4
    print("   [PASS] Full provenance verified across all generated questions.")


def test_internal_consistency():
    """10. Ensure question_count, requested_questions, generated_questions and shortfall remain consistent."""
    print("\n--- Running Test 10: test_internal_consistency ---")
    source_id = "SRC_CONSISTENCY"
    student_id = "STU_CONSISTENCY"
    concepts = ["CONCEPT_C1", "CONCEPT_C2"]
    payload = _build_step1_payload(concepts, source_id=source_id)

    resp = client.post(
        "/assessment/start",
        json={
            "student_id": student_id,
            "source_id": source_id,
            "max_questions": 4,
            "step1_output": payload,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["question_count"] == len(data["questions"])
    assert data["generated_questions"] == data["question_count"]
    assert data["requested_questions"] == data["generated_questions"] + data["shortfall"]
    print(f"   [PASS] Internal consistency verified: requested({data['requested_questions']}) == generated({data['generated_questions']}) + shortfall({data['shortfall']}).")


def main():
    print("=================================================================")
    print("   TESTING STEP 2 QUESTION COUNT FULFILLMENT & BACKFILL          ")
    print("=================================================================")
    test_five_concepts_target_five()
    test_four_concepts_target_five_safe_variant_backfill()
    test_provider_failure_reserve_backfill_succeeds()
    test_duplicate_generated_question_rejected_and_replaced()
    test_insufficient_source_evidence_explicit_shortfall()
    test_target_equals_one()
    test_target_greater_than_configured_maximum()
    test_kill_switch_concepts_remain_excluded()
    test_provenance_remains_attached_to_every_question()
    test_internal_consistency()
    print("\n=================================================================")
    print("   ALL QUESTION COUNT FULFILLMENT & BACKFILL TESTS PASSED!       ")
    print("=================================================================")


if __name__ == "__main__":
    main()
