"""Step 3 — Sequential Grounded Question Generation.

Generates one question at a time using:
1. Qdrant retrieval for the current concept
2. LLM generation grounded in retrieved chunks
3. Negative prompting for plausible distractors
4. Python-side provenance injection (LLM never generates metadata)
"""

import json
import re

import google.generativeai as genai

from ...core.config import settings
from ...db.vector_store import get_client, _embed, ensure_collection
from qdrant_client.http import models as qmodels
from ..schemas import ConceptNode
from .schemas import AssessmentOption, Question

import random


_QUESTION_PROMPT = """You are an expert assessment item writer for educational content.
Generate exactly ONE multiple-choice question that tests understanding of the concept below.

CONCEPT: {concept_name}
DEFINITION: {concept_definition}

SOURCE MATERIAL (grounded context from the student's study material):
{source_chunks}

INSTRUCTIONS:
1. Create a question that tests DEEP understanding, not just surface recall.
2. The question MUST be answerable using ONLY the source material above.
3. Provide exactly 4 options (A, B, C, D) where:
   - ONE option is clearly correct (based on the source material)
   - THREE options are plausible but factually INCORRECT (common misconceptions)
4. The incorrect options should be tempting — they should sound reasonable to someone who hasn't studied carefully.
5. Include a brief explanation of why the correct answer is correct.

NEGATIVE INSTRUCTION: Do NOT create options that are obviously wrong or silly.
Every distractor must be a realistic misconception that a student might actually hold.

Respond with STRICT JSON only — no markdown fences, no commentary:
{{
  "question": "<the question text>",
  "options": [
    {{"index": 0, "text": "<option A>"}},
    {{"index": 1, "text": "<option B>"}},
    {{"index": 2, "text": "<option C>"}},
    {{"index": 3, "text": "<option D>"}}
  ],
  "correct_index": <0, 1, 2, or 3>,
  "explanation": "<why the correct answer is correct>"
}}"""


def _client() -> genai.GenerativeModel:
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.generation_model)


def search_concept_chunks(
    concept: ConceptNode,
    source_id: str,
    limit: int = 5,
) -> list[dict]:
    """Search Qdrant for chunks related to a concept, filtered by source_id.

    Uses a combination of the concept name + definition as the query,
    filtered to only return chunks from the specific source.
    Retries embedding calls up to 3 times with backoff for rate limits.
    """
    client = get_client()
    ensure_collection(client)

    query_text = f"{concept.name}: {concept.definition or ''}"

    # Retry embedding with backoff for rate limits
    vector = None
    for attempt in range(3):
        try:
            vector = _embed([query_text])[0]
            break
        except Exception as exc:
            print(f"[generator] Embedding attempt {attempt+1}/3 failed for '{concept.name}': {exc}")
            if attempt < 2:
                import time
                time.sleep(2 ** (attempt + 1))  # 2s, 4s backoff
    if vector is None:
        print(f"[generator] All embedding attempts failed for '{concept.name}'")
        return []

    # Filter by layer=A AND source_id
    must_conditions = [
        qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A")),
        qmodels.FieldCondition(key="source_id", match=qmodels.MatchValue(value=source_id)),
    ]

    # If concept has source_content_ids, also filter by content_ids intersection
    if concept.source_content_ids:
        must_conditions.append(
            qmodels.FieldCondition(
                key="content_ids",
                match=qmodels.MatchAny(any=concept.source_content_ids),
            )
        )

    try:
        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=qmodels.Filter(must=must_conditions),
        )
        if hits:
            return [hit.payload for hit in hits]

        # Fallback: search with just layer=A (handles legacy chunks without source_id)
        print(f"[generator] No source-filtered hits for '{concept.name}', trying unfiltered...")
        hits = client.search(
            collection_name=settings.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="layer", match=qmodels.MatchValue(value="A"))]
            ),
        )
        if hits:
            print(f"[generator] Found {len(hits)} unfiltered hits for '{concept.name}'")
        return [hit.payload for hit in hits]
    except Exception as exc:
        print(f"[generator] Qdrant search failed for concept {concept.name}: {exc}")
        # Final fallback: no filter at all
        try:
            hits = client.search(
                collection_name=settings.collection_name,
                query_vector=vector,
                limit=limit,
            )
            return [hit.payload for hit in hits]
        except Exception as exc2:
            print(f"[generator] Final fallback search also failed: {exc2}")
            return []


def generate_question(
    concept: ConceptNode,
    source_id: str,
    difficulty: str = "intermediate",
    max_retries: int = 2,
) -> Question | None:
    """Generate a single grounded question for a concept.

    Returns None if generation fails after retries (concept should be dropped).
    Includes retry with exponential backoff for rate limit errors.
    """
    import time

    chunks = search_concept_chunks(concept, source_id, limit=5)

    if not chunks:
        print(f"[generator] Zero hits for concept '{concept.name}' — skipping")
        return None

    # Format chunks for the prompt
    chunk_text = "\n\n".join(
        f"[Source chunk {i+1}]: {ch.get('text', '')[:800]}"
        for i, ch in enumerate(chunks)
    )

    chunk_ids = [ch.get("chunk_id", "") for ch in chunks if ch.get("chunk_id")]

    prompt = _QUESTION_PROMPT.format(
        concept_name=concept.name,
        concept_definition=concept.definition or "No definition available",
        source_chunks=chunk_text,
    )

    for attempt in range(max_retries + 1):
        try:
            response = _client().generate_content(prompt)
            raw = response.text or ""
            data = _parse_json(raw)

            options = [
                AssessmentOption(index=opt["index"], text=opt["text"])
                for opt in data.get("options", [])
            ]

            question = Question(
                concept_id=concept.concept_id,
                concept_name=concept.name,
                stem=data.get("question", ""),
                options=options,
                correct_index=data.get("correct_index", 0),
                explanation=data.get("explanation", ""),
                chunk_ids=chunk_ids,
                source_id=source_id,
                difficulty=difficulty,
            )

            # Basic structural validation
            if len(question.options) != 4:
                print(f"[generator] Attempt {attempt+1}: Got {len(options)} options, need 4")
                continue
            if not question.stem.strip():
                print(f"[generator] Attempt {attempt+1}: Empty question stem")
                continue

            return question

        except Exception as exc:
            error_str = str(exc).lower()
            print(f"[generator] Attempt {attempt+1} failed for '{concept.name}': {exc}")
            # Rate limit — backoff before retry
            if "429" in error_str or "quota" in error_str or "rate" in error_str:
                wait = 2 ** (attempt + 1)
                print(f"[generator] Rate limited, waiting {wait}s before retry...")
                time.sleep(wait)
            continue

    print(f"[generator] All attempts failed for concept '{concept.name}'")
    return None


def _parse_json(raw: str) -> dict:
    """Extract JSON from LLM output, tolerating markdown fences."""
    without_fences = re.sub(r"```(?:json)?", "", raw).strip()
    return json.loads(without_fences)
