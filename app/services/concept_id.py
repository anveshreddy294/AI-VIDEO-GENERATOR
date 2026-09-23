"""Canonical Concept-ID System & Migration Utilities.

Enforces a single authoritative concept-ID format across all subsystems:
- Format: CONCEPT_<SLUG>
- Allowed characters: [A-Za-z0-9_.-]
- No whitespace, no slashes, no path separators.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schemas import KnowledgeGraph, ConceptNode


SAFE_CONCEPT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
CANONICAL_CONCEPT_ID_PATTERN = re.compile(r"^CONCEPT_[A-Za-z0-9_.-]+$")


class InvalidConceptIdError(ValueError):
    """Raised when a concept ID contains disallowed characters or cannot be canonicalized."""


class ConceptCollisionError(ValueError):
    """Raised when two distinct concepts normalize to the same canonical ID."""


def canonicalize_concept_id(raw: str) -> str:
    """Transform an arbitrary concept name or legacy ID into a canonical concept ID.

    Examples:
        'Polar Research Station' -> 'CONCEPT_POLAR_RESEARCH_STATION'
        'CONCEPT POLAR_RESEARCH_STATION' -> 'CONCEPT_POLAR_RESEARCH_STATION'
        'CONCEPT_POLAR_RESEARCH_STATION' -> 'CONCEPT_POLAR_RESEARCH_STATION'
        'AI-Driven Smart Energy Management' -> 'CONCEPT_AI_DRIVEN_SMART_ENERGY_MANAGEMENT'
        'Vectors & Matrices' -> 'CONCEPT_VECTORS_MATRICES'
    """
    if not raw or not str(raw).strip():
        raise InvalidConceptIdError("Concept identifier or title cannot be empty.")

    text = str(raw).strip()

    # Unicode normalization to ASCII
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Strip existing concept prefix variants if present
    prefix_match = re.match(r"^(concept)[\s_:.-]+", text, flags=re.IGNORECASE)
    if prefix_match:
        text = text[prefix_match.end():].strip()

    # If removing the prefix left it empty (e.g. input was just "concept"), revert to fallback
    if not text:
        text = "GENERAL"

    # Replace all non-alphanumeric characters (spaces, hyphens, punctuation) with underscores
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)

    # Collapse multiple consecutive underscores
    text = re.sub(r"_+", "_", text)

    # Strip leading/trailing underscores from the slug body
    text = text.strip("_")
    if not text:
        text = "GENERAL"

    # Convert to uppercase
    canonical_id = f"CONCEPT_{text.upper()}"

    # Validate against strict safety invariants
    validate_concept_id(canonical_id)

    return canonical_id


def validate_concept_id(concept_id: str) -> str:
    """Validate that a concept ID satisfies domain boundary constraints.

    Must contain only [A-Za-z0-9_.-], have no whitespace, no path separators,
    and no directory traversal sequences.
    """
    if not concept_id or not str(concept_id).strip():
        raise InvalidConceptIdError("Concept ID cannot be empty.")

    ident = str(concept_id).strip()

    if any(c.isspace() for c in ident):
        raise InvalidConceptIdError(
            f"Invalid concept_id '{ident}': contains whitespace. Only [A-Za-z0-9_.-] are permitted."
        )

    if ident in (".", "..") or ".." in ident:
        raise InvalidConceptIdError(
            f"Invalid concept_id '{ident}': directory traversal attempt detected."
        )

    if "/" in ident or "\\" in ident or ":" in ident:
        raise InvalidConceptIdError(
            f"Invalid concept_id '{ident}': path separators or drive prefixes detected."
        )

    if not SAFE_CONCEPT_ID_PATTERN.fullmatch(ident):
        raise InvalidConceptIdError(
            f"Invalid concept_id '{ident}': contains disallowed characters. Only [A-Za-z0-9_.-] are permitted."
        )

    return ident


def normalize_knowledge_graph(
    kg: KnowledgeGraph,
    source_id: str | None = None,
) -> tuple[KnowledgeGraph, dict[str, str]]:
    """Deterministically normalize and migrate concept IDs within a KnowledgeGraph.

    Detects collisions, updates concept keys, prerequisite IDs, and related IDs.
    Returns the normalized KnowledgeGraph and the alias map (old_id -> canonical_id).
    """
    alias_map: dict[str, str] = {}
    reverse_map: dict[str, str] = {}

    # 1. First pass: compute canonical IDs and detect collisions
    for old_id, node in kg.concepts.items():
        canonical = canonicalize_concept_id(node.concept_id or node.name or old_id)

        if canonical in reverse_map and reverse_map[canonical] != old_id:
            raise ConceptCollisionError(
                f"Concept normalization collision in source '{source_id or 'unknown'}': "
                f"concepts '{reverse_map[canonical]}' and '{old_id}' both normalize to '{canonical}'."
            )

        alias_map[old_id] = canonical
        reverse_map[canonical] = old_id

    # 2. Second pass: reconstruct concepts dictionary with canonical IDs
    new_concepts: dict[str, ConceptNode] = {}
    for old_id, node in kg.concepts.items():
        canonical_id = alias_map[old_id]
        node.concept_id = canonical_id

        # Update prerequisites
        node.prerequisite_concept_ids = [
            alias_map.get(p, canonicalize_concept_id(p))
            for p in node.prerequisite_concept_ids
            if p
        ]

        # Update related concepts
        node.related_concept_ids = [
            alias_map.get(r, canonicalize_concept_id(r))
            for r in node.related_concept_ids
            if r
        ]

        new_concepts[canonical_id] = node

    kg.concepts = new_concepts
    return kg, alias_map
