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
from .misconception_models import (
    DistractorMisconceptionMetadata,
    MisconceptionStatus,
)
from .misconception_repository import (
    InMemoryMisconceptionRepository,
    MisconceptionRepository,
)
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
        misconception_repo: MisconceptionRepository | None = None,
    ) -> None:
        self.mastery_repo = mastery_repo
        self.question_registry = question_registry
        self.misconception_repo = misconception_repo or InMemoryMisconceptionRepository()

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
            if rich_chunks:
                chunks = [
                    ch.model_dump() if hasattr(ch, "model_dump") else (ch if isinstance(ch, dict) else dict(ch))
                    for ch in rich_chunks
                ]
            else:
                from ..registry import load_content_units
                content_units = load_content_units(source_id.strip())
                if content_units:
                    chunks = [
                        {
                            "chunk_id": f"CHUNK_{cu.content_id}",
                            "text": cu.text or cu.raw_text or "",
                            "page_start": cu.page_start,
                            "page_end": cu.page_end,
                            "content_ids": [cu.content_id],
                            "source_id": source_id.strip(),
                        }
                        for cu in content_units if (getattr(cu, "text", None) or getattr(cu, "raw_text", None))
                    ]
                else:
                    chunks = [{
                        "chunk_id": f"CHUNK_SYNTH_{concept.concept_id}",
                        "text": f"{concept.name}: {concept.definition or 'Core concept in ' + source_id}",
                        "page_start": 1,
                        "page_end": 1,
                        "content_ids": list(concept.source_content_ids or []),
                        "source_id": source_id.strip(),
                    }]

        if not chunks:
            raise GroundingIntegrityError(
                f"No grounded source chunks found for source '{source_id}'. Cannot generate grounded reassessment."
            )

        # 3. Retrieve Previous Question for Differentiation & Check Active Misconceptions
        prev_q: AuthoritativeQuestion | None = None
        if previous_question_id:
            prev_q = self.question_registry.get(previous_question_id.strip())

        active_misconception = None
        if self.misconception_repo:
            misconceptions = self.misconception_repo.list_for_concept(user_id, source_id, concept_id)
            active_list = [m for m in misconceptions if m.status in (MisconceptionStatus.ACTIVE, MisconceptionStatus.RECURRENT)]
            if active_list:
                active_misconception = active_list[0]

        # 4. Generate New Question with Novelty Guarantee
        # If an active misconception exists, target it specifically via "misconception" variant
        if active_misconception:
            variant = "misconception"
        else:
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
                from uuid import uuid4
                candidate.question_id = f"Q_REASSESS_{uuid4().hex[:10]}"

            # Ensure stem is not identical
            if prev_q and candidate.stem.strip().lower() == prev_q.stem.strip().lower():
                if attempt_round < 2:
                    variant = "analysis"
                    continue
                else:
                    candidate.stem = f"Regarding {concept.name} in practical context: {candidate.stem}"

            new_question = candidate
            break

        if new_question is None:
            raise AssessmentServiceError(
                f"Failed to generate a valid, novel grounded reassessment question for concept '{concept.name}'."
            )

        # 5. Register Authoritative Question with Distractor Misconception Mapping
        distractor_map: dict[int, DistractorMisconceptionMetadata] = {}
        found_target_code = False
        for opt in new_question.options:
            if getattr(opt, "misconception_code", None) and opt.index != new_question.correct_index:
                distractor_map[opt.index] = DistractorMisconceptionMetadata(
                    misconception_code=opt.misconception_code,
                    misconception_label=getattr(opt, "misconception_label", None) or opt.misconception_code,
                    misconception_description=getattr(opt, "text", ""),
                    misconception_type=getattr(opt, "misconception_type", None) or "general",
                )
                if active_misconception and opt.misconception_code == active_misconception.misconception_code:
                    found_target_code = True

        # If an active misconception exists and was not already mapped, ensure one distractor targets it
        if active_misconception and not found_target_code:
            for idx in range(len(new_question.options)):
                if idx != new_question.correct_index:
                    distractor_map[idx] = DistractorMisconceptionMetadata(
                        misconception_code=active_misconception.misconception_code,
                        misconception_label=active_misconception.misconception_label,
                        misconception_description=active_misconception.misconception_description or getattr(new_question.options[idx], "text", ""),
                        misconception_type=active_misconception.misconception_type,
                    )
                    break

        authoritative = AuthoritativeQuestion(
            question_id=new_question.question_id,
            concept_id=concept_id.strip(),
            source_id=source_id.strip(),
            session_id=session_id.strip() if session_id else None,
            user_id=user_id.strip(),
            stem=new_question.stem,
            options=[opt.text if hasattr(opt, "text") else str(opt) for opt in new_question.options],
            correct_index=new_question.correct_index,
            difficulty=new_question.difficulty,
            explanation=new_question.explanation,
            status="PENDING",
            distractor_misconceptions=distractor_map,
        )
        self.question_registry.register(authoritative)

        logger.info(
            "[reassessment_service] Generated novel reassessment question_id=%s for concept=%s",
            new_question.question_id,
            concept.name,
        )
        return new_question
