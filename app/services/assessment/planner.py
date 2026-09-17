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
    max_questions: int = 10,
    key_concepts: list[str] | None = None,
) -> list[ConceptNode]:
    """Select concepts to test, ordered by priority.

    Args:
        kg: KnowledgeGraph containing concept nodes and prerequisite links.
        profile: Existing StudentLearningProfile if student has taken assessments before.
        max_questions: Target number of questions to generate.
        key_concepts: Optional list of key concept names or IDs from Step 1 JSON.

    Returns:
        Ordered queue of ConceptNode objects ready for question generation.
    """
    concepts = list(kg.concepts.values())
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
        return _plan_with_profile(concepts, profile, max_questions)
    else:
        return _cold_start_plan(concepts, max_questions)


def _cold_start_plan(
    concepts: list[ConceptNode], max_questions: int
) -> list[ConceptNode]:
    """Cold start: no profile exists. Select a balanced mix of foundational and advanced concepts."""
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

    # Apply Prerequisite Pairing Rule
    selected = _apply_prerequisite_pairing(selected, concepts)
    return selected[:max_questions]


def _plan_with_profile(
    concepts: list[ConceptNode],
    profile: StudentLearningProfile,
    max_questions: int,
) -> list[ConceptNode]:
    """Plan with existing profile: prioritize weak/unmastered concepts, strictly excluding kill-switch concepts."""
    # Anti-Loop Kill Switch: Concepts requiring human intervention MUST NOT be automatically re-tested
    kill_switch_ids = {
        cid for cid, m in profile.concept_masteries.items()
        if m.status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK")
    }

    # Filter out kill-switch concepts from candidate pool
    eligible_concepts = [c for c in concepts if c.concept_id not in kill_switch_ids]
    concept_map = {c.concept_id: c for c in eligible_concepts}
    selected: list[ConceptNode] = []
    selected_ids: set[str] = set()

    # Priority 1: LEARNING concepts (failed or unmastered, excluding kill-switch concepts)
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

    # Priority 2: NOT_ATTEMPTED concepts (excluding kill-switch concepts)
    unattempted = [
        c
        for c in eligible_concepts
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

    # Priority 3: Fill remaining with any unselected eligible concepts (e.g. review MASTERED)
    remaining = [c for c in eligible_concepts if c.concept_id not in selected_ids]
    random.shuffle(remaining)
    for c in remaining:
        if len(selected) < max_questions:
            selected.append(c)
            selected_ids.add(c.concept_id)

    # Apply Prerequisite Pairing Rule on eligible concepts, blocking kill-switch concepts
    selected = _apply_prerequisite_pairing(selected, eligible_concepts, exclude_ids=kill_switch_ids)
    return [c for c in selected if c.concept_id not in kill_switch_ids][:max_questions]


def _apply_prerequisite_pairing(
    selected: list[ConceptNode],
    all_concepts: list[ConceptNode],
    exclude_ids: set[str] | None = None,
) -> list[ConceptNode]:
    """Prerequisite Pairing Rule:

    For every advanced or dependent concept selected, automatically queue the
    foundational concept beneath it (e.g. if testing Machine Learning,
    automatically test Linear Regression first).
    Ensures foundational concepts precede dependent concepts without duplicates,
    and never queues excluded concepts (e.g. kill-switch tagged items).
    """
    blocked_ids = exclude_ids or set()
    concept_map = {c.concept_id: c for c in all_concepts if c.concept_id not in blocked_ids}
    ordered_result: list[ConceptNode] = []
    seen_ids: set[str] = set(blocked_ids)

    def _add_with_prereqs(concept: ConceptNode) -> None:
        if concept.concept_id in blocked_ids:
            return
        # First recursively/iteratively add prerequisites that exist in the map
        for prereq_id in concept.prerequisite_concept_ids:
            if prereq_id in concept_map and prereq_id not in seen_ids:
                prereq_node = concept_map[prereq_id]
                _add_with_prereqs(prereq_node)
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
