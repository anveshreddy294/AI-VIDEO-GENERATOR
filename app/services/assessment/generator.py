"""Step 3 — Sequential Grounded Question Generation.

Generates questions one concept at a time using:
1. Context Retrieval: Uses chunks from Step 1 JSON or Qdrant Layer A
2. Grounded LLM Generation: Sends exact chunk text to Gemini
3. Negative Prompting: "Based ONLY on this text, generate a multiple-choice question.
   Provide exactly 1 correct answer and 3 plausible but factually incorrect options."
4. Provenance Tracking: Attaches exact page numbers, chunk IDs, and content IDs
   so the student and frontend can trace the question back to source material.
5. Resilient Fallback: If Gemini API is unconfigured or rate-limited, synthesizes
   grounded questions directly from chunk context so the system never breaks.
"""

import json
import re
import time
from typing import Any

import google.generativeai as genai
from qdrant_client.http import models as qmodels

from ...core.config import settings
from ...db.vector_store import _embed, ensure_collection, get_client
from ..schemas import ConceptNode
from .planner import classify_difficulty
from .schemas import AssessmentOption, Question

_QUESTION_PROMPT = """You are an expert educational assessment author.
Based ONLY on this text, generate a multiple-choice question. Provide exactly 1 correct answer and 3 plausible but factually incorrect options.

CONCEPT: {concept_name}
DEFINITION: {concept_definition}

SOURCE MATERIAL (authoritative grounded text from student's study material):
{source_chunks}

STRICT INSTRUCTIONS:
1. Test conceptual understanding grounded strictly in the provided text.
2. Provide exactly 4 options with indices 0, 1, 2, 3.
3. Provide exactly 1 correct answer and 3 plausible but factually incorrect options (common student misconceptions).
4. Negative prompt: Do not use trivial or obviously silly distractors. Every incorrect option must sound plausible.
5. Provide a clear explanation of why the correct answer is right according to the source material.

Respond with STRICT JSON only (no markdown, no explanation outside JSON):
{{
  "question": "<the question text>",
  "options": [
    {{"index": 0, "text": "<option A>"}},
    {{"index": 1, "text": "<option B>"}},
    {{"index": 2, "text": "<option C>"}},
    {{"index": 3, "text": "<option D>"}}
  ],
  "correct_index": <0, 1, 2, or 3>,
  "explanation": "<grounded explanation>"
}}"""


def _client() -> genai.GenerativeModel:
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.generation_model)


def search_concept_chunks(
    concept: ConceptNode,
    source_id: str,
    limit: int = 5,
    provided_chunks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve authoritative chunks for a concept.

    First checks provided_chunks (from Step 1 JSON payload in memory).
    If not available, queries Qdrant Layer A collection filtered by source_id.
    """
    # 1. Fast in-memory resolution from Step 1 JSON payload
    if provided_chunks:
        matched = []
        for ch in provided_chunks:
            c_ids = ch.get("concept_ids", [])
            cu_ids = ch.get("content_ids", [])
            text = ch.get("text", "")
            if (
                concept.concept_id in c_ids
                or any(cid in cu_ids for cid in concept.source_content_ids)
                or concept.name.lower() in text.lower()
            ):
                matched.append(ch)
        if matched:
            return matched[:limit]
        return provided_chunks[:limit]

    # 2. Qdrant vector retrieval
    try:
        client = get_client()
        ensure_collection(client)
    except Exception as exc:
        print(f"[generator] Vector client unavailable: {exc}")
        return []

    query_text = f"{concept.name}: {concept.definition or ''}"

    # Embed query with backoff
    vector = None
    for attempt in range(3):
        try:
            vector = _embed([query_text])[0]
            break
        except Exception as exc:
            print(f"[generator] Embedding attempt {attempt+1}/3 failed: {exc}")
            if attempt < 2:
                time.sleep(1.5 ** (attempt + 1))

    if vector is None:
        return []

    must_conditions = [
        qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A")),
        qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id)),
    ]

    try:
        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=qmodels.Filter(must=must_conditions),
        )
        if hits:
            return [hit.payload for hit in hits]

        # Fallback to layer A only
        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A"))]
            ),
        )
        return [hit.payload for hit in hits] if hits else []
    except Exception as exc:
        print(f"[generator] Qdrant search failed for '{concept.name}': {exc}")
        return []


def generate_question(
    concept: ConceptNode,
    source_id: str,
    difficulty: str | None = None,
    provided_chunks: list[dict[str, Any]] | None = None,
    max_retries: int = 2,
) -> Question | None:
    """Generate a single grounded question for a concept with full provenance tracking.

    Returns None only if generation fails completely.
    """
    if not difficulty:
        difficulty = classify_difficulty(concept)

    chunks = search_concept_chunks(
        concept, source_id, limit=5, provided_chunks=provided_chunks
    )

    # If no chunks found, construct minimal context from concept definition
    if not chunks:
        chunks = [{
            "chunk_id": f"CHUNK_SYNTH_{concept.concept_id}",
            "text": f"{concept.name}: {concept.definition or 'Key foundational concept in ' + source_id}",
            "page_start": 1,
            "page_end": 1,
            "content_ids": list(concept.source_content_ids),
        }]

    # Provenance Tracking: Extract provenance metadata
    chunk_ids = [ch.get("chunk_id", "") for ch in chunks if ch.get("chunk_id")]
    content_ids = []
    for ch in chunks:
        content_ids.extend(ch.get("content_ids", []))
    content_ids = list(dict.fromkeys(content_ids))

    pages = [ch.get("page_start") for ch in chunks if ch.get("page_start") is not None]
    pages_end = [ch.get("page_end") for ch in chunks if ch.get("page_end") is not None]
    page_start = min(pages) if pages else (chunks[0].get("page") if chunks else None)
    page_end = max(pages_end) if pages_end else page_start

    timestamp_start = next(
        (ch.get("timestamp_start") for ch in chunks if ch.get("timestamp_start") is not None),
        None,
    )
    timestamp_end = next(
        (ch.get("timestamp_end") for ch in chunks if ch.get("timestamp_end") is not None),
        None,
    )

    chunk_text = "\n\n".join(
        f"[Source chunk {i+1} (Page {ch.get('page_start', ch.get('page', 'N/A'))})]: {ch.get('text', '')[:800]}"
        for i, ch in enumerate(chunks)
    )

    prompt = _QUESTION_PROMPT.format(
        concept_name=concept.name,
        concept_definition=concept.definition or "Core curriculum concept.",
        source_chunks=chunk_text,
    )

    # Attempt Gemini generation
    for attempt in range(max_retries + 1):
        try:
            if not settings.gemini_api_key or settings.gemini_api_key == "mock_key":
                break  # Go straight to fast grounded fallback

            model = _client()
            response = model.generate_content(prompt)
            raw = response.text or ""
            data = _parse_json(raw)

            options = [
                AssessmentOption(index=opt["index"], text=opt["text"])
                for opt in data.get("options", [])
            ]

            if len(options) != 4 or not data.get("question", "").strip():
                continue

            return Question(
                concept_id=concept.concept_id,
                concept_name=concept.name,
                stem=data.get("question", "").strip(),
                options=options,
                correct_index=int(data.get("correct_index", 0)),
                explanation=data.get("explanation", f"Based on source definition of {concept.name}"),
                chunk_ids=chunk_ids,
                content_ids=content_ids,
                page_start=page_start,
                page_end=page_end,
                timestamp_start=timestamp_start,
                timestamp_end=timestamp_end,
                source_id=source_id,
                difficulty=difficulty,
            )

        except Exception as exc:
            err = str(exc).lower()
            print(f"[generator] LLM attempt {attempt+1} failed for '{concept.name}': {exc}")
            if "exceeded your current quota" in err or "quota_value" in err:
                print(f"[generator] Quota reached, instantly switching to grounded fallback generator.")
                break
            if attempt < max_retries and ("429" in err or "rate" in err):
                time.sleep(1.0)

    # Resilient grounded fallback generation (fast & deterministic)
    return _generate_grounded_fallback(
        concept=concept,
        chunks=chunks,
        chunk_ids=chunk_ids,
        content_ids=content_ids,
        page_start=page_start,
        page_end=page_end,
        timestamp_start=timestamp_start,
        timestamp_end=timestamp_end,
        source_id=source_id,
        difficulty=difficulty,
    )


def _generate_grounded_fallback(
    concept: ConceptNode,
    chunks: list[dict[str, Any]],
    chunk_ids: list[str],
    content_ids: list[str],
    page_start: int | None,
    page_end: int | None,
    timestamp_start: float | str | None,
    timestamp_end: float | str | None,
    source_id: str,
    difficulty: str,
) -> Question:
    """Deterministic, context-grounded fallback question builder."""
    chunk_sample = chunks[0].get("text", "").strip() if chunks else ""
    definition = concept.definition or (chunk_sample[:150] if chunk_sample else f"The principle of {concept.name}")

    stem = f"Which of the following statements accurately characterizes {concept.name} according to the study material?"
    correct_text = definition if len(definition) < 140 else f"{concept.name} is primarily defined as: {definition[:120]}..."
    distractor_1 = f"{concept.name} operates in reverse, negating any effect on related components."
    distractor_2 = f"{concept.name} is strictly deprecated in modern system architectures."
    distractor_3 = f"{concept.name} functions solely as an arbitrary cache layer without structural impact."

    options = [
        AssessmentOption(index=0, text=correct_text),
        AssessmentOption(index=1, text=distractor_1),
        AssessmentOption(index=2, text=distractor_2),
        AssessmentOption(index=3, text=distractor_3),
    ]

    return Question(
        concept_id=concept.concept_id,
        concept_name=concept.name,
        stem=stem,
        options=options,
        correct_index=0,
        explanation=f"Directly derived from the source definition: {definition[:120]}",
        chunk_ids=chunk_ids,
        content_ids=content_ids,
        page_start=page_start,
        page_end=page_end,
        timestamp_start=timestamp_start,
        timestamp_end=timestamp_end,
        source_id=source_id,
        difficulty=difficulty,
    )


def _parse_json(raw: str) -> dict:
    """Extract JSON from LLM output, tolerating markdown fences."""
    without_fences = re.sub(r"```(?:json)?", "", raw).strip()
    return json.loads(without_fences)
