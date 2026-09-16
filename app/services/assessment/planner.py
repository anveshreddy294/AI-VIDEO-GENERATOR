"""Step 2 — Assessment Planning & Concept Pairing.

Selects which concepts to test based on:
1. Cold Start: balanced sampling (30% foundational, 40% intermediate, 30% advanced)
2. Existing Profile: prioritize weak concepts, revisit unmastered ones
3. Prerequisite Pairing: advanced concept auto-queues its parent
"""

import random
from ..schemas import ConceptNode, KnowledgeGraph
from .schemas import ConceptMastery, StudentLearningProfile


def plan_assessment(
    kg: KnowledgeGraph,
    profile: StudentLearningProfile | None = None,
    max_questions: int = 10,
) -> list[ConceptNode]:
    """Select concepts to test, ordered by priority.

    Returns a queue of ConceptNode objects to generate questions for.
    """
    concepts = list(kg.concepts.values())
    if not concepts:
        return []

    if profile and profile.concept_masteries:
        return _plan_with_profile(concepts, profile, max_questions)
    else:
        return _cold_start_plan(concepts, max_questions)


def _cold_start_plan(concepts: list[ConceptNode], max_questions: int) -> list[ConceptNode]:
    """Cold start: no profile exists. Sample across difficulty spectrum."""
    # Classify concepts by their prerequisite count as a proxy for difficulty
    foundational = [c for c in concepts if not c.prerequisite_concept_ids]
    intermediate = [
        c for c in concepts
        if c.prerequisite_concept_ids and len(c.prerequisite_concept_ids) <= 2
    ]
    advanced = [
        c for c in concepts
        if len(c.prerequisite_concept_ids) > 2
    ]

    # If we can't cleanly split, use all as intermediate
    if not foundational and not advanced:
        intermediate = concepts

    # 30% foundational, 40% intermediate, 30% advanced
    n_foundational = max(1, int(max_questions * 0.30))
    n_intermediate = max(1, int(max_questions * 0.40))
    n_advanced = max(1, max_questions - n_foundational - n_intermediate)

    selected: list[ConceptNode] = []

    selected.extend(_safe_sample(foundational, n_foundational))
    selected.extend(_safe_sample(intermediate, n_intermediate))
    selected.extend(_safe_sample(advanced, n_advanced))

    # Apply prerequisite pairing
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

    # Priority 1: REQUIRES_FALLBACK concepts (need human/static intervention)
    for cid, mastery in profile.concept_masteries.items():
        if mastery.status == "REQUIRES_FALLBACK" and cid in concept_map:
            if cid not in selected_ids:
                selected.append(concept_map[cid])
                selected_ids.add(cid)

    # Priority 2: LEARNING concepts (attempted but not mastered)
    learning = [
        (cid, m) for cid, m in profile.concept_masteries.items()
        if m.status == "LEARNING" and cid in concept_map and cid not in selected_ids
    ]
    random.shuffle(learning)
    for cid, _ in learning:
        if len(selected) < max_questions:
            selected.append(concept_map[cid])
            selected_ids.add(cid)

    # Priority 3: NOT_ATTEMPTED concepts
    unattempted = [
        c for c in concepts
        if c.concept_id not in selected_ids
        and profile.concept_masteries.get(c.concept_id, ConceptMastery(concept_id=c.concept_id)).status == "NOT_ATTEMPTED"
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

    # Apply prerequisite pairing
    selected = _apply_prerequisite_pairing(selected, concepts)

    return selected[:max_questions]


def _apply_prerequisite_pairing(
    selected: list[ConceptNode],
    all_concepts: list[ConceptNode],
) -> list[ConceptNode]:
    """Ensure that for every advanced concept, its direct parent is also included."""
    concept_map = {c.concept_id: c for c in all_concepts}
    selected_ids = {c.concept_id for c in selected}
    extras: list[ConceptNode] = []

    for concept in selected:
        # If this concept has prerequisites, ensure at least one parent is included
        for prereq_id in concept.prerequisite_concept_ids:
            if prereq_id not in selected_ids and prereq_id in concept_map:
                extras.append(concept_map[prereq_id])
                selected_ids.add(prereq_id)

    # Insert prerequisites right before their dependent concept
    result: list[ConceptNode] = []
    for concept in selected:
        for prereq_id in concept.prerequisite_concept_ids:
            if prereq_id in {e.concept_id for e in extras}:
                result.append(concept_map[prereq_id])
        result.append(concept)

    return result


def _safe_sample(pool: list, n: int) -> list:
    """Sample up to n items from pool, handling small pools gracefully."""
    if not pool:
        return []
    return random.sample(pool, min(n, len(pool)))
