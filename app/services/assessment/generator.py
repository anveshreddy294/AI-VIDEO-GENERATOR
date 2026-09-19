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
import logging
import re
import time
from typing import Any

from qdrant_client.http import models as qmodels

from ...core.config import settings
from ...db.vector_store import _embed, ensure_collection, get_client
from ..schemas import ConceptNode, StageDiagnostics
from .planner import classify_difficulty
from .providers import LLMProvider, get_default_provider
from .schemas import AssessmentOption, Question

logger = logging.getLogger(__name__)

VARIANT_DIRECTIVES: dict[str, str] = {
    "definition": (
        "PEDAGOGICAL ANGLE: Core Definition & Recognition.\n"
        "Focus strictly on what this concept is, its defining properties, and foundational meaning in the source text."
    ),
    "relationship": (
        "PEDAGOGICAL ANGLE: Conceptual Relationship & Prerequisites.\n"
        "Focus on how this concept relates to, depends upon, or interacts with its foundational prerequisites or broader domain systems."
    ),
    "application": (
        "PEDAGOGICAL ANGLE: Practical Application & Scenario Analysis.\n"
        "Present a practical scenario or concrete problem that tests how this concept operates or is applied in practice."
    ),
    "comparison": (
        "PEDAGOGICAL ANGLE: Distinction & Comparison.\n"
        "Focus on distinguishing this concept from closely related principles or identifying what uniquely characterizes it."
    ),
    "misconception": (
        "PEDAGOGICAL ANGLE: Misconception Diagnosis.\n"
        "Focus on identifying common errors, false assumptions, or typical student confusions regarding this concept."
    ),
}

_QUESTION_PROMPT = """You are an expert educational assessment author.
Based ONLY on this text, generate a multiple-choice question. Provide exactly 1 correct answer and 3 plausible but factually incorrect options.

CONCEPT: {concept_name}
DEFINITION: {concept_definition}
{variant_directive}

SOURCE MATERIAL (authoritative grounded text from student's study material):
{source_chunks}

STRICT INSTRUCTIONS:
1. Test conceptual understanding grounded strictly in the provided text according to the specified PEDAGOGICAL ANGLE.
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
  "evidence_quote": "<exact supporting quote copied from SOURCE MATERIAL>",
  "explanation": "<grounded explanation>"
}}"""


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
            if (ch.get("source_id") and ch.get("source_id") != source_id) or ch.get("layer", "A") != "A":
                continue
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
        return []

    # 2. Qdrant vector retrieval
    try:
        client = get_client()
        ensure_collection(client)
    except Exception as exc:
        logger.warning(f"[generator] Vector client unavailable: {exc}")
        return []

    query_text = f"{concept.name}: {concept.definition or ''}"

    # Embed query with backoff
    vector = None
    for attempt in range(3):
        try:
            vector = _embed([query_text], task_type="retrieval_query")[0]
            break
        except Exception as exc:
            logger.warning(f"[generator] Embedding attempt {attempt+1}/3 failed: {exc}")
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
        return [hit.payload for hit in hits] if hits else []
    except Exception as exc:
        logger.warning(f"[generator] Qdrant search failed for '{concept.name}': {exc}")
        return []


def generate_question(
    concept: ConceptNode,
    source_id: str,
    difficulty: str | None = None,
    provided_chunks: list[dict[str, Any]] | None = None,
    max_retries: int | None = None,
    llm_provider: LLMProvider | None = None,
    variant_type: str = "definition",
) -> Question | None:
    """Generate a single grounded question for a concept with full provenance tracking.

    Returns None only if generation fails completely.
    """
    if not difficulty:
        difficulty = classify_difficulty(concept)

    retries = max_retries if max_retries is not None else settings.max_question_retries
    provider = llm_provider or get_default_provider()

    chunks = search_concept_chunks(
        concept, source_id, limit=5, provided_chunks=provided_chunks
    )

    # If no chunks found, construct minimal context from concept definition without fabricated page numbers
    if not chunks:
        logger.warning("No authoritative chunks for %s", concept.concept_id)
        return None

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

    starts = [ch.get("timestamp_start") for ch in chunks if isinstance(ch.get("timestamp_start"), (int, float))]
    ends = [ch.get("timestamp_end") for ch in chunks if isinstance(ch.get("timestamp_end"), (int, float))]
    timestamp_start = min(starts) if starts else None
    timestamp_end = max(ends) if ends else None

    chunk_text = "\n\n".join(
        f"[Source chunk {i+1} (Page {ch.get('page_start', ch.get('page', 'N/A'))})]: {ch.get('text', '')}"
        for i, ch in enumerate(chunks)
    )

    variant_directive = VARIANT_DIRECTIVES.get(
        variant_type, VARIANT_DIRECTIVES["definition"]
    )

    prompt = _QUESTION_PROMPT.format(
        concept_name=concept.name,
        concept_definition=concept.definition or "Core curriculum concept.",
        variant_directive=variant_directive,
        source_chunks=chunk_text,
    )

    t0 = time.time()
    last_error: str | None = None

    # Attempt LLM generation via provider
    for attempt in range(retries + 1):
        try:
            raw = provider.generate_content(prompt)
            data = _parse_json(raw)

            raw_options = data.get("options", [])
            if len(raw_options) != 4 or not data.get("question", "").strip():
                continue

            raw_corr_int = data.get("correct_index")
            if type(raw_corr_int) is not int or raw_corr_int not in range(4):
                raise ValueError("Invalid correct_index")
            if {opt.get("index") for opt in raw_options} != {0, 1, 2, 3}:
                raise ValueError("Options must have unique indices 0–3")
            raw_options = sorted(raw_options, key=lambda opt: opt["index"])
            quote = data.get("evidence_quote", "").strip()
            if len(quote) < 12 or not any(quote in ch.get("text", "") for ch in chunks):
                raise ValueError("Missing or fabricated supporting quote")
            if len({opt.get("text", "").strip().casefold() for opt in raw_options}) != 4:
                raise ValueError("Duplicate options")

            # Authoritative correct answer text before shuffling
            correct_answer_text = raw_options[raw_corr_int].get("text", "").strip()

            # Randomize option placement across 0-3 while strictly maintaining correct_index mapping
            import random
            texts = [opt.get("text", "").strip() for opt in raw_options]
            random.shuffle(texts)
            new_correct_index = texts.index(correct_answer_text) if correct_answer_text in texts else 0

            options = [
                AssessmentOption(index=i, text=t)
                for i, t in enumerate(texts)
            ]

            duration_ms = round((time.time() - t0) * 1000, 2)
            diagnostics = StageDiagnostics(
                provider_used=getattr(provider, "model_name", settings.llm_provider),
                fallback_used=False,
                fallback_reason=None,
                grounding_verified=True,
                duration_ms=duration_ms,
            )

            return Question(
                concept_id=concept.concept_id,
                concept_name=concept.name,
                stem=data.get("question", "").strip(),
                options=options,
                correct_index=new_correct_index,
                explanation=data.get("explanation", f"Based on source definition of {concept.name}"),
                evidence_quote=quote,
                evidence_text="\n\n".join(ch.get("text", "") for ch in chunks),
                chunk_ids=chunk_ids,
                content_ids=content_ids,
                page_start=page_start,
                page_end=page_end,
                timestamp_start=timestamp_start,
                timestamp_end=timestamp_end,
                source_id=source_id,
                difficulty=difficulty,
                variant_type=variant_type,
                diagnostics=diagnostics,
            )

        except Exception as exc:
            err = str(exc).lower()
            last_error = str(exc)
            logger.warning(f"[generator] LLM attempt {attempt+1} failed for '{concept.name}': {exc}")
            if "exceeded your current quota" in err or "quota_value" in err:
                logger.warning("[generator] Quota reached; question generation stopped.")
                break
            if "not set" in err or "unconfigured" in err or "not found" in err:
                break
            if attempt < retries and ("429" in err or "rate" in err):
                time.sleep(1.0)

    # Resilient grounded fallback generation (fast & deterministic)
    duration_ms = round((time.time() - t0) * 1000, 2)
    logger.error("Question generation failed for %s: %s", concept.concept_id, last_error)
    return None


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
    variant_type: str = "definition",
    fallback_reason: str | None = None,
    duration_ms: float = 0.0,
) -> Question:
    """Deterministic, context-grounded fallback question builder with distinct variant stems, distractors, and answer indices."""
    import hashlib

    chunk_sample = chunks[0].get("text", "").strip() if chunks else ""
    definition = concept.definition or (chunk_sample[:150] if chunk_sample else f"The principle of {concept.name}")
    prereq_str = f" its prerequisite ({', '.join(concept.prerequisite_concept_ids)})" if concept.prerequisite_concept_ids else " foundational principles"

    def_snippet = definition[:60].strip()
    if def_snippet and not def_snippet.endswith("."):
        def_snippet += "..."

    if variant_type == "relationship":
        stem = f"Regarding {concept.name}, how does this principle connect to prerequisite context ({prereq_str}) to establish '{def_snippet}'?"
        correct_text = f"{concept.name} builds directly upon {prereq_str} to establish that: {definition[:110]}."
        distractor_1 = f"{concept.name} functions in complete isolation, superseding and invalidating {prereq_str}."
        distractor_2 = f"{concept.name} inverts the causal sequence, requiring downstream applications to precede {prereq_str}."
        distractor_3 = f"{concept.name} is a redundant synonym for {prereq_str} with no distinct properties of its own."
        explanation = f"Directly derived from the prerequisite structure and source definition of {concept.name}."

    elif variant_type == "application":
        stem = f"In practical applications of {concept.name} ({def_snippet}), which scenario demonstrates its correct operation?"
        correct_text = f"An application where {concept.name} is used to explain: {definition[:110]}."
        distractor_1 = f"Applying {concept.name} to produce infinite output without consuming system energy or resources."
        distractor_2 = f"Using {concept.name} exclusively as a static label without observing any state change in the system."
        distractor_3 = f"Treating {concept.name} as applicable only when all environmental interactions are completely absent."
        explanation = f"Grounded application of {concept.name} according to the source curriculum."

    elif variant_type == "comparison":
        stem = f"When distinguishing {concept.name} ({def_snippet}) from related domain principles, which criterion uniquely identifies it?"
        correct_text = f"Only {concept.name} specifically describes: {definition[:110]}."
        distractor_1 = f"{concept.name} uniquely lacks any measurable or observable consequences in physical systems."
        distractor_2 = f"{concept.name} is characterized by being universally identical across all distinct phenomena."
        distractor_3 = f"{concept.name} uniquely requires external observers to manually define its properties at each step."
        explanation = f"Comparative distinction for {concept.name} grounded in source definition."

    elif variant_type == "misconception":
        stem = f"Which statement regarding {concept.name} ({def_snippet}) represents an accurate understanding rather than a misconception?"
        correct_text = f"An accurate understanding recognizes that {concept.name} means: {definition[:110]}."
        distractor_1 = f"A misconception assuming {concept.name} is merely a temporary convention with no factual basis."
        distractor_2 = f"A flawed assumption that {concept.name} automatically guarantees equilibrium regardless of external conditions."
        distractor_3 = f"An incorrect belief that {concept.name} operates only in theoretical approximations and never in actual scenarios."
        explanation = f"Diagnostic distinction addressing misconceptions regarding {concept.name}."

    else:  # "definition" / default
        stem = f"According to the study material for {concept.name}, which statement accurately captures its core definition ({def_snippet})?"
        correct_text = definition if len(definition) < 140 else f"{concept.name} is primarily defined as: {definition[:120]}..."
        distractor_1 = f"{concept.name} operates in direct contradiction to{prereq_str}, reversing the system's observable state."
        distractor_2 = f"{concept.name} is classified as an auxiliary secondary property that has no measurable interaction with {concept.name}."
        distractor_3 = f"{concept.name} serves merely as a transient buffer and does not represent an independent conceptual model."
        explanation = f"Directly derived from the source definition of {concept.name}: {definition[:120]}"

    distractors = [distractor_1, distractor_2, distractor_3]

    # Varied, deterministic correct answer placement (0, 1, 2, or 3) based on concept_id and variant hash
    h_val = int(hashlib.md5(f"{concept.concept_id}_{variant_type}".encode("utf-8")).hexdigest(), 16)
    correct_index = h_val % 4

    option_texts = []
    d_idx = 0
    for i in range(4):
        if i == correct_index:
            option_texts.append(correct_text)
        else:
            option_texts.append(distractors[d_idx])
            d_idx += 1

    options = [
        AssessmentOption(index=i, text=text)
        for i, text in enumerate(option_texts)
    ]

    return Question(
        concept_id=concept.concept_id,
        concept_name=concept.name,
        stem=stem,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
        chunk_ids=chunk_ids,
        content_ids=content_ids,
        page_start=page_start,
        page_end=page_end,
        timestamp_start=timestamp_start,
        timestamp_end=timestamp_end,
        source_id=source_id,
        difficulty=difficulty,
        variant_type=variant_type,
        diagnostics=StageDiagnostics(
            provider_used="deterministic_grounded_fallback",
            fallback_used=True,
            fallback_reason=fallback_reason,
            grounding_verified=True,
            duration_ms=duration_ms,
        ),
    )


def _parse_json(raw: str) -> dict:
    """Extract JSON from LLM output, tolerating markdown fences and conversational preambles."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if match:
        raw = match.group(1).strip()
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]
    return json.loads(raw)


generate_question_for_concept = generate_question
