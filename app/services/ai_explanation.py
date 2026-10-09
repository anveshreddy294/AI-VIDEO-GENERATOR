"""AI-First Educational Content Explanation and Supplemental Teaching.

Supports:
1. Explaining arbitrary educational topics on-demand (e.g., Binary Search Trees,
   Photosynthesis, Fourier Transform, Database Normalization) without requiring
   uploaded files, pre-existing source versions, Qdrant vectors, or web search.
2. Explaining and teaching from accepted observations of uploaded sources without
   blocking on exact-source vocabulary restrictions.
3. Truthful provenance tracking: marks content as AI_ENRICHED and never invents
   citations.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from ..core.reasoning import (
    Message,
    ReasoningRequest,
    ReasoningProvider,
    get_reasoning_router,
    ProviderFailure,
)
from .schemas import Citation

logger = logging.getLogger(__name__)

INJECTION_PATTERN = re.compile(
    r"\b(ignore\s+(all\s+)?instructions|system\s+prompt|reveal\s+(the\s+)?secret|developer\s+mode|override\s+rules|exfiltrat)\b",
    re.IGNORECASE,
)


class PromptInjectionError(ValueError):
    """Raised when request topic or query contains prompt injection payloads."""
    pass


class KeyPoint(BaseModel):
    title: str
    explanation: str


class EducationalExample(BaseModel):
    title: str
    description: str


class PrerequisiteConcept(BaseModel):
    name: str
    description: str


class AIExplanationRequest(BaseModel):
    topic: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    detail_level: Literal["concise", "standard", "detailed"] = "standard"
    source_id: str | None = None
    source_version: int | None = None
    concept_id: str | None = None
    target_audience: str = "general_learner"

    @model_validator(mode="after")
    def validate_request(self) -> AIExplanationRequest:
        if not self.topic and not self.source_id:
            raise ValueError("Either 'topic' or 'source_id' must be provided.")
        return self


class AIExplanationResponse(BaseModel):
    topic: str
    provenance_kind: Literal["AI_ENRICHED"] = "AI_ENRICHED"
    overview: str
    simplified_explanation: str
    key_points: list[KeyPoint] = Field(default_factory=list)
    examples: list[EducationalExample] = Field(default_factory=list)
    analogies: list[str] = Field(default_factory=list)
    prerequisites: list[PrerequisiteConcept] = Field(default_factory=list)
    summary: str
    citations: list[Citation] = Field(default_factory=list)
    source_id: str | None = None
    source_version: int | None = None
    timings_ms: float = 0.0
    model_calls: int = 1


_EXPLANATION_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "overview": {"type": "string"},
        "simplified_explanation": {"type": "string"},
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["title", "explanation"],
            },
        },
        "examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        },
        "analogies": {
            "type": "array",
            "items": {"type": "string"},
        },
        "prerequisites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "description"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": [
        "topic",
        "overview",
        "simplified_explanation",
        "key_points",
        "examples",
        "analogies",
        "prerequisites",
        "summary",
    ],
}


class AIExplanationService:
    """Explains arbitrary educational topics and provides supplemental teaching."""

    def __init__(self, provider: ReasoningProvider | None = None) -> None:
        self.provider = provider

    def explain(
        self,
        request: AIExplanationRequest,
        *,
        source_observations: list[str] | None = None,
    ) -> AIExplanationResponse:
        started = time.perf_counter()

        effective_topic = request.topic or (f"Educational Overview of {request.source_id}" if request.source_id else "Educational Topic")

        # 1. Security Check: Prompt injection guard
        if INJECTION_PATTERN.search(effective_topic):
            raise PromptInjectionError("Educational topic contains disallowed instructions or injection patterns.")

        detail_instructions = {
            "concise": "Provide a brief 3-point explanation suitable for a quick review.",
            "standard": "Provide a clear, balanced educational explanation with definitions, analogies, and examples.",
            "detailed": "Provide an in-depth breakdown covering prerequisites, key mechanics, concrete examples, and common pitfalls.",
        }[request.detail_level]

        system_prompt = (
            "You are an expert AI educator and tutor. Your mission is to help students learn and "
            "deeply understand concepts using intuitive language, clear definitions, illustrative "
            "analogies, real-world examples, and prerequisite scaffolding. "
            "Return STRICT JSON matching the supplied schema. "
            "Do not invent false source citations. "
            f"Detail Level: {detail_instructions}"
        )

        user_content = f"TOPIC: {effective_topic}\nAUDIENCE: {request.target_audience}\n"
        if source_observations:
            user_content += (
                "\nACCEPTED SOURCE OBSERVATIONS:\n"
                + "\n---\n".join(source_observations[:10])
                + "\n\nUse these source observations as grounding context where relevant, but you may "
                "freely use analogies, definitions, and examples to explain the concepts clearly."
            )

        reasoning_req = ReasoningRequest(
            task="content_understanding",
            messages=[
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_content),
            ],
            max_tokens=2048,
            response_schema=_EXPLANATION_SCHEMA,
        )

        router = self.provider or get_reasoning_router()
        result = router.generate(reasoning_req)

        cleaned = result.response.strip()
        if "<think>" in cleaned and "</think>" in cleaned:
            cleaned = cleaned.split("</think>", 1)[-1].strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            raw = json.loads(cleaned)
            if not isinstance(raw, dict):
                raise ValueError("Expected JSON dictionary from model")
            parsed = AIExplanationResponse(
                topic=raw.get("topic") or effective_topic,
                provenance_kind="AI_ENRICHED",
                overview=raw.get("overview") or f"Educational overview of {effective_topic}.",
                simplified_explanation=raw.get("simplified_explanation") or raw.get("overview") or f"Clear conceptual breakdown of {effective_topic}.",
                key_points=[
                    KeyPoint(**kp) for kp in raw.get("key_points", [])
                    if isinstance(kp, dict) and "title" in kp and "explanation" in kp
                ] or [KeyPoint(title=effective_topic, explanation=f"Core conceptual foundations of {effective_topic}.")],
                examples=[
                    EducationalExample(**ex) for ex in raw.get("examples", [])
                    if isinstance(ex, dict) and "title" in ex and "description" in ex
                ],
                analogies=[str(a) for a in raw.get("analogies", []) if isinstance(a, str)],
                prerequisites=[
                    PrerequisiteConcept(**pq) for pq in raw.get("prerequisites", [])
                    if isinstance(pq, dict) and "name" in pq and "description" in pq
                ],
                summary=raw.get("summary") or f"Comprehensive conceptual summary of {effective_topic}.",
                citations=[],  # Honest citation provenance: zero citations for pure AI enrichment
                source_id=request.source_id,
                source_version=request.source_version,
                timings_ms=(time.perf_counter() - started) * 1000,
                model_calls=1,
            )
            return parsed
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning("Failed to parse explanation response: %s", exc)
            return AIExplanationResponse(
                topic=effective_topic,
                provenance_kind="AI_ENRICHED",
                overview=f"Educational overview of {effective_topic}.",
                simplified_explanation=result.response[:500] if result.response else f"Conceptual explanation of {effective_topic}.",
                key_points=[
                    KeyPoint(title=effective_topic, explanation=result.response[:200] if result.response else f"Core principle of {effective_topic}.")
                ],
                examples=[],
                analogies=[],
                prerequisites=[],
                summary=f"Summary of {effective_topic}.",
                citations=[],
                source_id=request.source_id,
                source_version=request.source_version,
                timings_ms=(time.perf_counter() - started) * 1000,
                model_calls=1,
            )
