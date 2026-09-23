"""Unit tests for Canonical Concept-ID System and Legacy Migration."""

import pytest
from app.services.concept_id import (
    canonicalize_concept_id,
    validate_concept_id,
    normalize_knowledge_graph,
    ConceptCollisionError,
    InvalidConceptIdError,
)
from app.services.schemas import ConceptNode, KnowledgeGraph


class TestCanonicalConceptId:
    def test_canonicalize_space_in_concept_name(self):
        """'CONCEPT POLAR_RESEARCH_STATION' -> 'CONCEPT_POLAR_RESEARCH_STATION'."""
        cid = canonicalize_concept_id("CONCEPT POLAR_RESEARCH_STATION")
        assert cid == "CONCEPT_POLAR_RESEARCH_STATION"
        validate_concept_id(cid)

    def test_canonicalize_already_canonical(self):
        """'CONCEPT_POLAR_RESEARCH_STATION' -> 'CONCEPT_POLAR_RESEARCH_STATION'."""
        cid = canonicalize_concept_id("CONCEPT_POLAR_RESEARCH_STATION")
        assert cid == "CONCEPT_POLAR_RESEARCH_STATION"
        validate_concept_id(cid)

    def test_canonicalize_natural_language_title(self):
        """'Polar Research Station' -> 'CONCEPT_POLAR_RESEARCH_STATION'."""
        cid = canonicalize_concept_id("Polar Research Station")
        assert cid == "CONCEPT_POLAR_RESEARCH_STATION"
        validate_concept_id(cid)

    def test_canonicalize_hyphens_and_mixed_case(self):
        """'AI-Driven Smart Energy Management' -> 'CONCEPT_AI_DRIVEN_SMART_ENERGY_MANAGEMENT'."""
        cid = canonicalize_concept_id("AI-Driven Smart Energy Management")
        assert cid == "CONCEPT_AI_DRIVEN_SMART_ENERGY_MANAGEMENT"
        validate_concept_id(cid)

    def test_canonicalize_punctuation_and_symbols(self):
        """Handles special characters like parentheses, ampersands, colons, slashes."""
        cid = canonicalize_concept_id("Vectors & Matrices: Part 1 / Fundamentals!")
        assert cid == "CONCEPT_VECTORS_MATRICES_PART_1_FUNDAMENTALS"
        validate_concept_id(cid)

    def test_canonicalize_multiple_spaces_and_underscores(self):
        """Collapses consecutive spaces, underscores, and tabs."""
        cid = canonicalize_concept_id("Quantum    Superposition___States\t\n")
        assert cid == "CONCEPT_QUANTUM_SUPERPOSITION_STATES"
        validate_concept_id(cid)

    def test_canonicalize_unicode_input(self):
        """Handles accented or non-ASCII characters deterministically."""
        cid = canonicalize_concept_id("Schrödinger Wave Equation & Naïve Bayes")
        assert cid == "CONCEPT_SCHRODINGER_WAVE_EQUATION_NAIVE_BAYES"
        validate_concept_id(cid)

    def test_empty_input_rejected(self):
        """Empty or whitespace-only inputs must raise InvalidConceptIdError."""
        with pytest.raises(InvalidConceptIdError):
            canonicalize_concept_id("")
        with pytest.raises(InvalidConceptIdError):
            canonicalize_concept_id("   \t  ")

    def test_validate_concept_id_rejects_whitespace_and_traversal(self):
        """validate_concept_id strictly rejects invalid path components."""
        with pytest.raises(InvalidConceptIdError):
            validate_concept_id("CONCEPT POLAR")
        with pytest.raises(InvalidConceptIdError):
            validate_concept_id("../CONCEPT_MALICIOUS")
        with pytest.raises(InvalidConceptIdError):
            validate_concept_id("CONCEPT/VECTORS")
        with pytest.raises(InvalidConceptIdError):
            validate_concept_id("CONCEPT\\VECTORS")


class TestKnowledgeGraphNormalizationAndCollisions:
    def test_normalize_legacy_knowledge_graph(self):
        """Re-keys legacy concept dictionaries and updates prerequisite references."""
        kg = KnowledgeGraph(
            concepts={
                "CONCEPT POLAR_RESEARCH_STATION": ConceptNode(
                    concept_id="CONCEPT POLAR_RESEARCH_STATION",
                    name="Polar Research Station",
                    definition="A research station in Antarctica.",
                    prerequisite_concept_ids=["Energy Logistics"],
                ),
                "Energy Logistics": ConceptNode(
                    concept_id="Energy Logistics",
                    name="Energy Logistics",
                    definition="Logistics of supplying fuel.",
                    prerequisite_concept_ids=[],
                ),
            }
        )

        normalized_kg, alias_map = normalize_knowledge_graph(kg, source_id="SRC_TEST_MIGRATE")

        assert "CONCEPT_POLAR_RESEARCH_STATION" in normalized_kg.concepts
        assert "CONCEPT_ENERGY_LOGISTICS" in normalized_kg.concepts
        assert "CONCEPT POLAR_RESEARCH_STATION" not in normalized_kg.concepts

        node = normalized_kg.concepts["CONCEPT_POLAR_RESEARCH_STATION"]
        assert node.concept_id == "CONCEPT_POLAR_RESEARCH_STATION"
        assert node.prerequisite_concept_ids == ["CONCEPT_ENERGY_LOGISTICS"]

    def test_collision_detection(self):
        """Fails clearly with ConceptCollisionError if two distinct concepts normalize to same ID."""
        with pytest.raises(ConceptCollisionError) as exc_info:
            KnowledgeGraph(
                concepts={
                    "Polar Research Station": ConceptNode(
                        concept_id="Polar Research Station",
                        name="Polar Research Station",
                        definition="Station 1",
                    ),
                    "polar_research_station": ConceptNode(
                        concept_id="polar_research_station",
                        name="Polar Research Station",
                        definition="Station 2",
                    ),
                }
            )

        assert "collision" in str(exc_info.value).lower()
