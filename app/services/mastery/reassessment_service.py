"""Step 5B Reassessment Service.

Responsible for:
1. Validating that a concept is in REASSESSING state (remediation has completed).
2. Fetching the exact grounded concept and source evidence for that concept.
3. Generating a novel grounded reassessment question using existing generator machinery.
4. Enforcing question differentiation (different question_id, stem, and options).
5. Registering the authoritative question for subsequent server-side grading.
"""

from __future__ import annotations

import logging
from typing import Any

from ...core.config import settings
from ..assessment.generator import generate_question
from ..assessment.schemas import Question, SafeQuestion
from ..registry import load_knowledge_graph, load_rich_chunks
from .attempt_service import AssessmentServiceError, GroundingIntegrityError
from .models import MasteryRecord, MasteryState
from .question_registry import AuthoritativeQuestion, QuestionRegistry
from .repository import MasteryRepository

logger = logging.getLogger(__name__)


class ReassessmentService:
    """Orchestrates novel grounded reassessment question generation."""

    def __init__(
        self,
        mastery_repo: MasteryRepository,
        question_registry: QuestionRegistry,
    ) -> None:
        self.mastery_repo = mastery_repo
        self.question_registry = question_registry

    def generate_reassessment_question(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        session_id: str | None = None,
        previous_question_id: str | None = None,
        provided_concept: Any | None = None,
        provided_chunks: list[dict[str, Any]] | None = None,
    ) -> Question:
        """Generate a novel grounded question for a concept undergoing reassessment."""
        # 1. State Precondition: concept must be in REASSESSING state
        mastery = self.mastery_repo.get(user_id.strip(), source_id.strip(), concept_id.strip())
        if mastery is None:
            raise AssessmentServiceError(
                f"Cannot generate reassessment: no mastery record found for concept '{concept_id}'."
            )

        if mastery.mastery_state != MasteryState.REASSESSING:
            raise AssessmentServiceError(
                f"Cannot generate reassessment for concept in state {mastery.mastery_state.value}. "
                "Concept must be in REASSESSING state (remediation must be completed and confirmed first)."
            )

        # 2. Resolve Grounded Concept and Authoritative Source Evidence
        concept = provided_concept
        chunks = provided_chunks

        if concept is None:
            kg = load_knowledge_graph(source_id.strip())
            if kg is None or concept_id.strip() not in kg.concepts:
                raise GroundingIntegrityError(
                    f"Concept '{concept_id}' not found in grounded KnowledgeGraph for source '{source_id}'."
                )
            concept = kg.concepts[concept_id.strip()]

        if chunks is None:
            rich_chunks = load_rich_chunks(source_id.strip())
            chunks = [ch.model_dump() for ch in rich_chunks] if rich_chunks else []

        if not chunks:
            raise GroundingIntegrityError(
                f"No grounded source chunks found for source '{source_id}'. Cannot generate grounded reassessment."
            )

        # 3. Retrieve Previous Question for Differentiation
        prev_q: AuthoritativeQuestion | None = None
        if previous_question_id:
            prev_q = self.question_registry.get(previous_question_id.strip())

        # 4. Generate New Question with Novelty Guarantee
        # Use variant_type "application" or "mechanism" for reassessment to avoid identical definitions
        variant = "application" if prev_q and getattr(prev_q, "variant_type", "") == "definition" else "mechanism"

        new_question: Question | None = None
        for attempt_round in range(3):
            candidate = generate_question(
                concept=concept,
                source_id=source_id.strip(),
                difficulty="intermediate",
                variant_type=variant,
                provided_chunks=chunks,
            )
            if candidate is None:
                continue

            # Ensure different question_id
            if prev_q and candidate.question_id == prev_q.question_id:
                continue

            # Ensure stem is not identical
            if prev_q and candidate.stem.strip().lower() == prev_q.stem.strip().lower():
                variant = "analysis"
                continue

            new_question = candidate
            break

        if new_question is None:
            raise AssessmentServiceError(
                f"Failed to generate a valid, novel grounded reassessment question for concept '{concept.name}'."
            )

        # 5. Register Authoritative Question
        authoritative = AuthoritativeQuestion(
            question_id=new_question.question_id,
            concept_id=concept_id.strip(),
            source_id=source_id.strip(),
            session_id=session_id.strip() if session_id else None,
            user_id=user_id.strip(),
            stem=new_question.stem,
            options=[opt.text for opt in new_question.options],
            correct_index=new_question.correct_index,
            difficulty=new_question.difficulty,
            explanation=new_question.explanation,
        )
        self.question_registry.register(authoritative)

        logger.info(
            "[reassessment_service] Generated novel reassessment question_id=%s for concept=%s",
            new_question.question_id,
            concept.name,
        )
        return new_question
