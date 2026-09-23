"""Step 5C Personalization Service — Deterministic Next-Action & Learning Roadmap Engine.

Orchestrates personalized curriculum progression based purely on grounded concepts,
prerequisite dependency satisfaction, and learner mastery records.
Strictly side-effect-free, explainable, and free of non-deterministic LLM ranking.
"""

from __future__ import annotations

import logging
from typing import Any

from ..registry import load_knowledge_graph
from ..schemas import KnowledgeGraph
from .attempt_service import GroundingIntegrityError
from .dependency_provider import ConceptDependencyProvider
from .models import DomainInvariantViolation, MasteryRecord, MasteryState
from .repository import MasteryRepository
from .roadmap_models import LearningActionType, LearningRoadmap, NextLearningAction, ReasonCode

logger = logging.getLogger(__name__)


class PersonalizationService:
    """Deterministic personalization engine for learning roadmaps and next-action selection."""

    def __init__(
        self,
        mastery_repo: MasteryRepository,
        dependency_provider: ConceptDependencyProvider | None = None,
    ) -> None:
        self.mastery_repo = mastery_repo
        self.dependency_provider = dependency_provider

    def get_roadmap(
        self,
        user_id: str,
        source_id: str,
        session_id: str | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
    ) -> LearningRoadmap:
        """Compute the full deterministic learning roadmap for a learner and grounded source."""
        clean_user_id = user_id.strip() if user_id else ""
        clean_source_id = source_id.strip() if source_id else ""
        clean_session_id = session_id.strip() if session_id else None

        if not clean_user_id:
            raise DomainInvariantViolation("user_id cannot be empty")
        if not clean_source_id:
            raise DomainInvariantViolation("source_id cannot be empty")

        # 1. Resolve grounded curriculum from source
        kg = knowledge_graph or load_knowledge_graph(clean_source_id)
        if kg is None or not kg.concepts:
            raise GroundingIntegrityError(
                f"No grounded knowledge graph found for source '{clean_source_id}'."
            )

        # Grounded curriculum ordering: preserves author/source order defined in kg.concepts
        curriculum_concepts = [cid.strip() for cid in kg.concepts.keys() if cid and cid.strip()]
        curriculum_set = set(curriculum_concepts)
        curriculum_order_map = {cid: idx for idx, cid in enumerate(curriculum_concepts)}

        # 2. Resolve dependency provider
        dep_provider = self.dependency_provider or ConceptDependencyProvider.from_knowledge_graph(kg)

        # 3. Fetch learner mastery records (pure read)
        mastery_records = self.mastery_repo.list_by_user_source(clean_user_id, clean_source_id)
        # Partition only records belonging to this grounded source curriculum
        mastery_map: dict[str, MasteryRecord] = {}
        for rec in mastery_records:
            if rec.concept_id in curriculum_set:
                mastery_map[rec.concept_id] = rec

        # 4. Determine Mastered Concepts
        mastered_set: set[str] = {
            cid for cid, rec in mastery_map.items()
            if rec.mastery_state == MasteryState.MASTERED
        }

        # 5. Partition concepts into roadmap categories
        mastered_concepts: list[str] = []
        weak_concepts: list[str] = []
        remediating_concepts: list[str] = []
        reassessing_concepts: list[str] = []
        unassessed_concepts: list[str] = []
        blocked_concepts: list[str] = []
        needs_support_concepts: list[str] = []
        learning_concepts: list[str] = []

        for cid in curriculum_concepts:
            is_satisfied = dep_provider.are_dependencies_satisfied(cid, mastered_set)

            if cid not in mastery_map:
                if not is_satisfied:
                    blocked_concepts.append(cid)
                else:
                    unassessed_concepts.append(cid)
            else:
                rec = mastery_map[cid]
                state = rec.mastery_state

                if state == MasteryState.MASTERED:
                    mastered_concepts.append(cid)
                elif not is_satisfied:
                    # An unmastered concept with unsatisfied prerequisites is blocked
                    blocked_concepts.append(cid)
                else:
                    if state == MasteryState.REASSESSING:
                        reassessing_concepts.append(cid)
                    elif state == MasteryState.REMEDIATING:
                        remediating_concepts.append(cid)
                    elif state == MasteryState.WEAK:
                        weak_concepts.append(cid)
                    elif state == MasteryState.LEARNING:
                        learning_concepts.append(cid)
                    elif state == MasteryState.UNASSESSED:
                        unassessed_concepts.append(cid)
                    elif state == MasteryState.NEEDS_SUPPORT:
                        needs_support_concepts.append(cid)

        # 6. Deterministic Next-Action Selection
        next_action = self._select_next_action(
            user_id=clean_user_id,
            source_id=clean_source_id,
            session_id=clean_session_id,
            curriculum_order_map=curriculum_order_map,
            dep_provider=dep_provider,
            mastery_map=mastery_map,
            mastered_concepts=mastered_concepts,
            reassessing_concepts=reassessing_concepts,
            remediating_concepts=remediating_concepts,
            weak_concepts=weak_concepts,
            learning_concepts=learning_concepts,
            unassessed_concepts=unassessed_concepts,
            blocked_concepts=blocked_concepts,
            needs_support_concepts=needs_support_concepts,
            total_curriculum_count=len(curriculum_concepts),
        )

        completed = (
            len(mastered_concepts) == len(curriculum_concepts)
            and len(curriculum_concepts) > 0
            and next_action.action_type == LearningActionType.COMPLETE
        )

        return LearningRoadmap(
            user_id=clean_user_id,
            source_id=clean_source_id,
            session_id=clean_session_id,
            mastered_concepts=mastered_concepts,
            current_concept=next_action.concept_id,
            weak_concepts=weak_concepts,
            remediating_concepts=remediating_concepts,
            reassessing_concepts=reassessing_concepts,
            unassessed_concepts=unassessed_concepts + learning_concepts,
            blocked_concepts=blocked_concepts,
            needs_support_concepts=needs_support_concepts,
            completed=completed,
            next_action=next_action,
        )

    def get_next_action(
        self,
        user_id: str,
        source_id: str,
        session_id: str | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
    ) -> NextLearningAction:
        """Pure query returning only the deterministic next learning action."""
        roadmap = self.get_roadmap(
            user_id=user_id,
            source_id=source_id,
            session_id=session_id,
            knowledge_graph=knowledge_graph,
        )
        return roadmap.next_action

    def _select_next_action(
        self,
        user_id: str,
        source_id: str,
        session_id: str | None,
        curriculum_order_map: dict[str, int],
        dep_provider: ConceptDependencyProvider,
        mastery_map: dict[str, MasteryRecord],
        mastered_concepts: list[str],
        reassessing_concepts: list[str],
        remediating_concepts: list[str],
        weak_concepts: list[str],
        learning_concepts: list[str],
        unassessed_concepts: list[str],
        blocked_concepts: list[str],
        needs_support_concepts: list[str],
        total_curriculum_count: int,
    ) -> NextLearningAction:
        """Execute deterministic next-action selection hierarchy."""

        # Priority 1: Concepts actively awaiting REASSESSMENT
        if reassessing_concepts:
            selected_cid = self._sort_actionable_candidates(
                candidates=reassessing_concepts,
                mastery_map=mastery_map,
                dep_provider=dep_provider,
                curriculum_order_map=curriculum_order_map,
            )[0]
            rec = mastery_map[selected_cid]
            return NextLearningAction(
                user_id=user_id,
                source_id=source_id,
                session_id=session_id,
                concept_id=selected_cid,
                action_type=LearningActionType.REASSESS,
                reason_code=ReasonCode.REASSESSMENT_PENDING,
                priority=10,
                mastery_state=rec.mastery_state,
                mastery_score=rec.mastery_score,
                lifetime_accuracy=rec.lifetime_accuracy,
                dependency_status="SATISFIED",
                metadata={"remediation_attempt_count": rec.remediation_attempt_count},
            )

        # Priority 2: Concepts actively in REMEDIATING state
        if remediating_concepts:
            selected_cid = self._sort_actionable_candidates(
                candidates=remediating_concepts,
                mastery_map=mastery_map,
                dep_provider=dep_provider,
                curriculum_order_map=curriculum_order_map,
            )[0]
            rec = mastery_map[selected_cid]
            return NextLearningAction(
                user_id=user_id,
                source_id=source_id,
                session_id=session_id,
                concept_id=selected_cid,
                action_type=LearningActionType.REMEDIATE,
                reason_code=ReasonCode.ACTIVE_REMEDIATION,
                priority=20,
                mastery_state=rec.mastery_state,
                mastery_score=rec.mastery_score,
                lifetime_accuracy=rec.lifetime_accuracy,
                dependency_status="SATISFIED",
                metadata={"remediation_attempt_count": rec.remediation_attempt_count},
            )

        # Priority 3: WEAK concepts requiring remediation
        if weak_concepts:
            selected_cid = self._sort_weak_candidates(
                candidates=weak_concepts,
                mastery_map=mastery_map,
                dep_provider=dep_provider,
                curriculum_order_map=curriculum_order_map,
            )[0]
            rec = mastery_map[selected_cid]
            return NextLearningAction(
                user_id=user_id,
                source_id=source_id,
                session_id=session_id,
                concept_id=selected_cid,
                action_type=LearningActionType.REMEDIATE,
                reason_code=ReasonCode.WEAK_CONCEPT_REQUIRES_REMEDIATION,
                priority=30,
                mastery_state=rec.mastery_state,
                mastery_score=rec.mastery_score,
                lifetime_accuracy=rec.lifetime_accuracy,
                dependency_status="SATISFIED",
                metadata={
                    "remediation_attempt_count": rec.remediation_attempt_count,
                    "incorrect_count": rec.incorrect_count,
                },
            )

        # Priority 4: Active LEARNING concepts (begun assessment/learning)
        if learning_concepts:
            selected_cid = sorted(learning_concepts, key=lambda c: (curriculum_order_map.get(c, 999), c))[0]
            rec = mastery_map[selected_cid]
            return NextLearningAction(
                user_id=user_id,
                source_id=source_id,
                session_id=session_id,
                concept_id=selected_cid,
                action_type=LearningActionType.ASSESS,
                reason_code=ReasonCode.ACTIVE_LEARNING_PENDING_ASSESSMENT,
                priority=40,
                mastery_state=rec.mastery_state,
                mastery_score=rec.mastery_score,
                lifetime_accuracy=rec.lifetime_accuracy,
                dependency_status="SATISFIED",
            )

        # Priority 5: Eligible UNASSESSED concepts (prerequisites satisfied, in curriculum order)
        if unassessed_concepts:
            selected_cid = sorted(unassessed_concepts, key=lambda c: (curriculum_order_map.get(c, 999), c))[0]
            rec = mastery_map.get(selected_cid)
            return NextLearningAction(
                user_id=user_id,
                source_id=source_id,
                session_id=session_id,
                concept_id=selected_cid,
                action_type=LearningActionType.ASSESS,
                reason_code=ReasonCode.NEXT_GROUNDED_CONCEPT,
                priority=50,
                mastery_state=rec.mastery_state if rec else MasteryState.UNASSESSED,
                mastery_score=rec.mastery_score if rec else 0.0,
                lifetime_accuracy=rec.lifetime_accuracy if rec else 0.0,
                dependency_status="SATISFIED",
            )

        # Priority 6: All remaining unmastered concepts require manual instructor support
        if needs_support_concepts:
            selected_cid = sorted(needs_support_concepts, key=lambda c: (curriculum_order_map.get(c, 999), c))[0]
            rec = mastery_map[selected_cid]
            return NextLearningAction(
                user_id=user_id,
                source_id=source_id,
                session_id=session_id,
                concept_id=selected_cid,
                action_type=LearningActionType.NEEDS_SUPPORT,
                reason_code=ReasonCode.MANUAL_SUPPORT_REQUIRED,
                priority=90,
                mastery_state=rec.mastery_state,
                mastery_score=rec.mastery_score,
                lifetime_accuracy=rec.lifetime_accuracy,
                dependency_status="SATISFIED",
                metadata={"remediation_attempt_count": rec.remediation_attempt_count},
            )

        # Priority 7: If all concepts in the curriculum are MASTERED -> COMPLETE
        if len(mastered_concepts) == total_curriculum_count and total_curriculum_count > 0:
            return NextLearningAction(
                user_id=user_id,
                source_id=source_id,
                session_id=session_id,
                concept_id=None,
                action_type=LearningActionType.COMPLETE,
                reason_code=ReasonCode.ALL_CONCEPTS_MASTERED,
                priority=100,
                dependency_status="NONE",
            )

        # Fallback for empty curriculum
        return NextLearningAction(
            user_id=user_id,
            source_id=source_id,
            session_id=session_id,
            concept_id=None,
            action_type=LearningActionType.COMPLETE,
            reason_code=ReasonCode.ALL_CONCEPTS_MASTERED,
            priority=100,
            dependency_status="NONE",
        )

    def _sort_actionable_candidates(
        self,
        candidates: list[str],
        mastery_map: dict[str, MasteryRecord],
        dep_provider: ConceptDependencyProvider,
        curriculum_order_map: dict[str, int],
    ) -> list[str]:
        """Sort candidates using curriculum order and concept ID tie-breaker."""
        return sorted(candidates, key=lambda c: (curriculum_order_map.get(c, 999), c))

    def _sort_weak_candidates(
        self,
        candidates: list[str],
        mastery_map: dict[str, MasteryRecord],
        dep_provider: ConceptDependencyProvider,
        curriculum_order_map: dict[str, int],
    ) -> list[str]:
        """Deterministic prioritization hierarchy among multiple weak concepts.

        Hierarchy:
        1. Prerequisite concepts before dependents (topological preference)
        2. Lower mastery score first (ascending)
        3. Higher incorrect attempts count first (descending)
        4. Earlier source curriculum position (curriculum_order_map ascending)
        5. Lexicographical concept_id as deterministic tie-breaker
        """
        def candidate_key(c: str) -> tuple[int, float, int, int, str]:
            rec = mastery_map.get(c)
            score = rec.mastery_score if rec else 0.0
            incorrect = rec.incorrect_count if rec else 0
            curriculum_idx = curriculum_order_map.get(c, 999)

            # Count how many other weak candidates depend on this concept c
            # Concepts that are prerequisites to more candidates have a lower ranking number (higher priority)
            dependent_count = sum(1 for other in candidates if other != c and dep_provider.has_prerequisite(other, c))
            topological_priority = -dependent_count  # higher dependent count -> comes first

            return (
                topological_priority,
                score,               # lower score first
                -incorrect,          # more incorrect attempts first
                curriculum_idx,      # earlier source position
                c,                   # deterministic tie-breaker
            )

        return sorted(candidates, key=candidate_key)
