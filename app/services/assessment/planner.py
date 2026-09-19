"""Step 2 — Dynamic Assessment Planning & Concept Pairing.

Goal: Decide which parts of the Step 1 JSON / KnowledgeGraph need to be tested.
Implements:
1. Reading Key Concepts from Step 1 JSON / Knowledge Graph
2. Cold Start Rule: Balanced mix of foundational, intermediate, and advanced concepts
3. Prerequisite Pairing Rule: For every advanced/dependent concept selected,
   automatically queue the foundational concept beneath it (e.g. Linear Regression before Machine Learning)
4. Existing Profile: Prioritize weak concepts, revisit unmastered ones, and handle kill-switch tagged items
"""

import random
from typing import Literal

from ...core.config import settings
from ..schemas import ConceptNode, KnowledgeGraph
from .schemas import ConceptMastery, StudentLearningProfile


def classify_difficulty(
    concept: ConceptNode,
) -> Literal["foundational", "intermediate", "advanced"]:
    """Classify a concept's difficulty by prerequisite depth.

    Single source of truth across Planner, Generator, and Video Target Matrix.
    - 0 prerequisites: foundational (core building block)
    - 1-2 prerequisites: intermediate
    - >2 prerequisites: advanced
    """
    n = len(concept.prerequisite_concept_ids)
    if n == 0:
        return "foundational"
    if n <= 2:
        return "intermediate"
    return "advanced"


def plan_assessment(
    kg: KnowledgeGraph,
    profile: StudentLearningProfile | None = None,
    max_questions: int | None = None,
    key_concepts: list[str] | None = None,
) -> list[ConceptNode]:
    """Select concepts to test, ordered by priority.

    Args:
        kg: KnowledgeGraph containing concept nodes and prerequisite links.
        profile: Existing StudentLearningProfile if student has taken assessments before.
        max_questions: Target number of questions to generate (defaults to settings.max_questions).
        key_concepts: Optional list of key concept names or IDs from Step 1 JSON.

    Returns:
        Ordered queue of ConceptNode objects ready for question generation.
    """
    limit = max_questions if max_questions is not None else settings.max_questions
    blocked = {cid for cid, m in profile.concept_masteries.items() if m.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK")} if profile else set()
    concepts = [c for c in kg.concepts.values() if c.concept_id not in blocked]
    if not concepts:
        return []

    # If key_concepts are specified in Step 1 JSON, prioritize matching nodes
    if key_concepts:
        key_lower = {k.strip().lower() for k in key_concepts if isinstance(k, str)}
        matching = [
            c for c in concepts
            if c.concept_id.lower() in key_lower
            or c.name.lower() in key_lower
        ]
        non_matching = [c for c in concepts if c not in matching]
        # Place key concepts first, followed by others as fallback
        concepts = matching + non_matching

    if profile and profile.concept_masteries:
        return _plan_with_profile(concepts, profile, limit)
    else:
        return _cold_start_plan(concepts, limit, has_key_concepts=bool(key_concepts))


def _cold_start_plan(
    concepts: list[ConceptNode],
    max_questions: int,
    has_key_concepts: bool = False,
) -> list[ConceptNode]:
    """Cold start: no profile exists. Select a balanced mix of foundational and advanced concepts."""
    if has_key_concepts:
        # Explicit key concepts priority from source blueprint
        selected = _apply_prerequisite_pairing(concepts[:max_questions], concepts)
        return selected[:max_questions]

    foundational = [c for c in concepts if classify_difficulty(c) == "foundational"]
    intermediate = [c for c in concepts if classify_difficulty(c) == "intermediate"]
    advanced = [c for c in concepts if classify_difficulty(c) == "advanced"]

    if not foundational and not advanced:
        intermediate = concepts

    # Cold Start Rule: balanced mix (approx 30% foundational, 40% intermediate, 30% advanced)
    n_foundational = max(1, int(max_questions * 0.30))
    n_intermediate = max(1, int(max_questions * 0.40))
    n_advanced = max(1, max_questions - n_foundational - n_intermediate)

    selected: list[ConceptNode] = []
    selected.extend(_safe_sample(foundational, n_foundational))
    selected.extend(_safe_sample(intermediate, n_intermediate))
    selected.extend(_safe_sample(advanced, n_advanced))

    # If pool tiers were empty or small, fill remaining from unselected concepts
    if len(selected) < max_questions:
        selected_ids = {c.concept_id for c in selected}
        remaining = [c for c in concepts if c.concept_id not in selected_ids]
        selected.extend(_safe_sample(remaining, max_questions - len(selected)))

    # Apply Prerequisite Pairing Rule
    selected = _apply_prerequisite_pairing(selected, concepts)
    return selected[:max_questions]


def _plan_with_profile(
    concepts: list[ConceptNode],
    profile: StudentLearningProfile,
    max_questions: int,
) -> list[ConceptNode]:
    """Plan with existing profile: prioritize weak/unmastered concepts."""
    concept_map = {c.concept_id: c for c in concepts}
    selected: list[ConceptNode] = []
    selected_ids: set[str] = set()

    # Priority 1: REQUIRES_HUMAN_FALLBACK concepts (flagged by kill switch)
    for cid, mastery in profile.concept_masteries.items():
        if (
            mastery.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK")
            and cid in concept_map
        ):
            if cid not in selected_ids:
                selected.append(concept_map[cid])
                selected_ids.add(cid)

    # Priority 2: LEARNING concepts (failed or unmastered)
    learning = [
        (cid, m)
        for cid, m in profile.concept_masteries.items()
        if m.status == "LEARNING" and cid in concept_map and cid not in selected_ids
    ]
    random.shuffle(learning)
    for cid, _ in learning:
        if len(selected) < max_questions:
            selected.append(concept_map[cid])
            selected_ids.add(cid)

    # Priority 3: NOT_ATTEMPTED concepts
    unattempted = [
        c
        for c in concepts
        if c.concept_id not in selected_ids
        and profile.concept_masteries.get(
            c.concept_id, ConceptMastery(concept_id=c.concept_id)
        ).status == "NOT_ATTEMPTED"
    ]
    random.shuffle(unattempted)
    for c in unattempted:
        if len(selected) < max_questions:
            selected.append(c)
            selected_ids.add(c.concept_id)

    # Priority 4: Fill remaining with any unselected concepts
    remaining = [c for c in concepts if c.concept_id not in selected_ids]
    random.shuffle(remaining)
    for c in remaining:
        if len(selected) < max_questions:
            selected.append(c)
            selected_ids.add(c.concept_id)

    # Apply Prerequisite Pairing Rule
    selected = _apply_prerequisite_pairing(selected, concepts)
    return selected[:max_questions]


def _apply_prerequisite_pairing(
    selected: list[ConceptNode],
    all_concepts: list[ConceptNode],
) -> list[ConceptNode]:
    """Prerequisite Pairing Rule:

    For every advanced or dependent concept selected, automatically queue the
    foundational concept beneath it (e.g. if testing Machine Learning,
    automatically test Linear Regression first).
    Ensures foundational concepts precede dependent concepts without duplicates.
    """
    concept_map = {c.concept_id: c for c in all_concepts}
    ordered_result: list[ConceptNode] = []
    seen_ids: set[str] = set()
    visiting: set[str] = set()

    def _add_with_prereqs(concept: ConceptNode) -> None:
        if concept.concept_id in seen_ids or concept.concept_id in visiting:
            return
        visiting.add(concept.concept_id)
        # First recursively add prerequisites that exist in the map
        for prereq_id in concept.prerequisite_concept_ids:
            if prereq_id in concept_map and prereq_id not in seen_ids and prereq_id not in visiting:
                prereq_node = concept_map[prereq_id]
                _add_with_prereqs(prereq_node)
        visiting.remove(concept.concept_id)
        # Then add the concept itself
        if concept.concept_id not in seen_ids:
            seen_ids.add(concept.concept_id)
            ordered_result.append(concept)

    for item in selected:
        _add_with_prereqs(item)

    return ordered_result


def _safe_sample(pool: list, n: int) -> list:
    """Sample up to n items from pool, handling small pools gracefully."""
    if not pool:
        return []
    return random.sample(pool, min(n, len(pool)))
