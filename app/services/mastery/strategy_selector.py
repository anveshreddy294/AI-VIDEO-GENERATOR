"""Step 5 Deterministic Teaching Strategy Selector (M4).

Selects pedagogy 100% deterministically from learner evidence, misconception taxonomy,
grounded prerequisite mastery, and prior remediation attempt history.
Zero LLM calls for policy selection.
"""

from __future__ import annotations

import logging
from typing import Sequence

from .dependency_provider import ConceptDependencyProvider
from .misconception_models import (
    MisconceptionEvidence,
    MisconceptionStatus,
    TeachingStrategyDecision,
    TeachingStrategyReasonCode,
    TeachingStrategyType,
)
from .models import MasteryRecord, MasteryState

logger = logging.getLogger(__name__)

# Fallback sequence for novelty on successive remediation retries
_NOVELTY_PROGRESSION: list[TeachingStrategyType] = [
    TeachingStrategyType.VISUAL_COMPARISON,
    TeachingStrategyType.COUNTEREXAMPLE,
    TeachingStrategyType.CONTRAST,
    TeachingStrategyType.WORKED_EXAMPLE,
    TeachingStrategyType.PREDICTION_AND_REVEAL,
    TeachingStrategyType.DIRECT_EXPLANATION,
]


class TeachingStrategySelector:
    """Deterministic policy engine mapping misconceptions and mastery states to pedagogical strategies."""

    def __init__(
        self,
        *args: Any,
        dependency_provider: ConceptDependencyProvider | None = None,
        misconception_repo: Any | None = None,
        mastery_repo: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.dependency_provider = dependency_provider
        self.misconception_repo = misconception_repo
        self.mastery_repo = mastery_repo

        for arg in args:
            if arg is None:
                continue
            if hasattr(arg, "get_unsatisfied_dependencies") or hasattr(arg, "get_prerequisites"):
                self.dependency_provider = arg
            elif hasattr(arg, "find_active_by_code") or hasattr(arg, "list_for_concept"):
                self.misconception_repo = arg
            elif hasattr(arg, "list_by_user_source"):
                self.mastery_repo = arg

    def select_strategy(
        self,
        *args: Any,
        concept_id: str | None = None,
        attempt_number: int | None = None,
        misconception: MisconceptionEvidence | None = None,
        previous_strategies: Sequence[Any] | None = None,
        previous_strategy: Any | None = None,
        mastered_concept_ids: set[str] | None = None,
        **kwargs: Any,
    ) -> TeachingStrategyDecision:
        """Select a pedagogical strategy deterministically."""
        user_id: str | None = None
        source_id: str | None = None

        if len(args) >= 3 and isinstance(args[0], str) and isinstance(args[1], str) and isinstance(args[2], str):
            # Signature: select_strategy(user_id, source_id, concept_id)
            user_id = args[0].strip()
            source_id = args[1].strip()
            concept_id = args[2].strip()
            attempt_number = attempt_number or kwargs.get("attempt", 1)
        elif len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], (int, float)):
            # Signature: select_strategy(concept_id, attempt_number)
            concept_id = args[0].strip()
            attempt_number = int(args[1])
        elif len(args) == 1 and isinstance(args[0], str):
            concept_id = args[0].strip()

        if not concept_id:
            raise ValueError("concept_id must be provided to select_strategy")

        clean_cid = concept_id.strip()
        attempt = max(1, attempt_number or 1)

        # Parse previous strategies
        prev_strategies: list[TeachingStrategyType] = []
        raw_prev = list(previous_strategies or kwargs.get("previous_strategies") or [])
        single_prev = previous_strategy or kwargs.get("previous_strategy") or kwargs.get("prev_strategy")
        if single_prev is not None and single_prev not in raw_prev:
            raw_prev.append(single_prev)
        for p in raw_prev:
            if isinstance(p, TeachingStrategyType):
                prev_strategies.append(p)
            elif isinstance(p, str):
                try:
                    prev_strategies.append(TeachingStrategyType(p))
                except Exception:
                    pass

        # If user_id and source_id provided, look up active misconception and mastered concepts
        if user_id and source_id:
            if misconception is None and self.misconception_repo:
                misconceptions = self.misconception_repo.list_for_concept(user_id, source_id, clean_cid)
                active_list = [
                    m for m in misconceptions
                    if getattr(m, "status", None) in (
                        MisconceptionStatus.ACTIVE,
                        MisconceptionStatus.RECURRENT,
                        "ACTIVE",
                        "RECURRENT",
                    )
                ]
                if active_list:
                    misconception = active_list[0]

            if mastered_concept_ids is None and self.mastery_repo:
                mastered_concept_ids = set()
                all_rec = self.mastery_repo.list_by_user_source(user_id, source_id)
                for r in all_rec:
                    if getattr(r, "mastery_state", None) == MasteryState.MASTERED:
                        mastered_concept_ids.add(r.concept_id)

        # 1. Prerequisite Review check: If learner has an unmastered grounded prerequisite
        if self.dependency_provider:
            if mastered_concept_ids is not None:
                unsatisfied = self.dependency_provider.get_unsatisfied_dependencies(
                    clean_cid, mastered_concept_ids
                )
            else:
                unsatisfied = self.dependency_provider.get_prerequisites(clean_cid)

            if unsatisfied and TeachingStrategyType.PREREQUISITE_REVIEW not in prev_strategies:
                return TeachingStrategyDecision(
                    concept_id=clean_cid,
                    strategy=TeachingStrategyType.PREREQUISITE_REVIEW,
                    reason_code=TeachingStrategyReasonCode.UNMASTERED_PREREQUISITE,
                    misconception_code=getattr(misconception, "misconception_code", None) if misconception else None,
                    attempt_number=attempt,
                    previous_strategies=prev_strategies,
                    supporting_evidence_ids=getattr(misconception, "evidence_attempt_ids", []) if misconception else [],
                    prerequisite_concept_id=unsatisfied[0],
                )

        # 2. No Misconception: Fall back to normal grounded remediation without inventing personalization
        if misconception is None:
            strategy = TeachingStrategyType.DIRECT_EXPLANATION
            reason_code = TeachingStrategyReasonCode.DEFAULT_CONCEPT_GROUNDED
            if strategy in prev_strategies:
                for candidate in _NOVELTY_PROGRESSION:
                    if candidate not in prev_strategies:
                        strategy = candidate
                        reason_code = TeachingStrategyReasonCode.NOVELTY_FALLBACK_NEXT_STRATEGY
                        break

            return TeachingStrategyDecision(
                concept_id=clean_cid,
                strategy=strategy,
                reason_code=reason_code,
                misconception_code=None,
                attempt_number=attempt,
                previous_strategies=prev_strategies,
                supporting_evidence_ids=[],
            )

        # 3. Deterministic Mapping by Misconception Type / Taxonomy
        m_type = (misconception.misconception_type or "general").lower()
        m_code = misconception.misconception_code.upper()

        primary_strategy = TeachingStrategyType.DIRECT_EXPLANATION
        primary_reason = TeachingStrategyReasonCode.DEFINITION_CONFUSION

        if "procedural" in m_type or "workflow" in m_type or "order" in m_code:
            primary_strategy = TeachingStrategyType.WORKED_EXAMPLE
            primary_reason = TeachingStrategyReasonCode.PROCEDURAL_ERROR
        elif "conflat" in m_type or "conflation" in m_code or "comparison" in m_type:
            primary_strategy = TeachingStrategyType.CONTRAST
            primary_reason = TeachingStrategyReasonCode.CONCEPT_CONFLATION
        elif "prediction" in m_type or "outcome" in m_type:
            primary_strategy = TeachingStrategyType.PREDICTION_AND_REVEAL
            primary_reason = TeachingStrategyReasonCode.PERSISTENT_PREDICTION_ERROR
        elif "causal" in m_type or "cause" in m_type or "negation" in m_code or "same_force" in m_code.lower():
            primary_strategy = TeachingStrategyType.COUNTEREXAMPLE
            primary_reason = TeachingStrategyReasonCode.INCORRECT_CAUSAL_BELIEF
        elif "visual" in m_type:
            primary_strategy = TeachingStrategyType.VISUAL_COMPARISON
            primary_reason = TeachingStrategyReasonCode.CONCEPT_CONFLATION
        else:
            primary_strategy = TeachingStrategyType.DIRECT_EXPLANATION
            primary_reason = TeachingStrategyReasonCode.DEFINITION_CONFUSION

        # 4. Retry Novelty: If primary strategy was already used in a previous attempt,
        # choose the next valid strategy from the progression sequence.
        final_strategy = primary_strategy
        final_reason = primary_reason

        if final_strategy in prev_strategies:
            # Fallback to alternate strategy
            for candidate in _NOVELTY_PROGRESSION:
                if candidate not in prev_strategies:
                    final_strategy = candidate
                    final_reason = TeachingStrategyReasonCode.NOVELTY_FALLBACK_NEXT_STRATEGY
                    break

        return TeachingStrategyDecision(
            concept_id=clean_cid,
            strategy=final_strategy,
            reason_code=final_reason,
            misconception_code=misconception.misconception_code,
            attempt_number=attempt,
            previous_strategies=prev_strategies,
            supporting_evidence_ids=list(misconception.evidence_attempt_ids),
        )
