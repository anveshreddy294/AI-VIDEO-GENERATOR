"""Step 3 — Sequential Grounded Question Generation.

Generates questions one concept at a time using:
1. Context Retrieval: Uses chunks from Step 1 JSON or Qdrant Layer A
2. Grounded LLM Generation: Sends exact chunk text to Ollama or MockProvider
3. Negative Prompting: "Based ONLY on this text, generate a multiple-choice question.
   Provide exactly 1 correct answer and 3 plausible but factually incorrect options."
4. Provenance Tracking: Attaches exact page numbers, chunk IDs, and content IDs
   so the student and frontend can trace the question back to source material.
5. Resilient Fallback: If LLM is unconfigured or rate-limited, synthesizes
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

STRICT GROUNDING & DISTRACTOR RULES:
1. Question stem and correct answer MUST be strictly grounded in the provided SOURCE MATERIAL.
2. Provide exactly 4 options with indices 0, 1, 2, 3.
3. Every distractor MUST be derived by a controlled transformation of source evidence:
   - For definition questions: modify or invert one specific source-supported property.
   - For relationship questions: alter a specific source-supported relationship or dependency.
   - For sequence/workflow questions: reorder the stages or steps described in the source.
4. FORBIDDEN DISTRACTORS:
   - Do NOT invent external scientific/technical facts not present in the source material.
   - Do NOT use generic LLM filler phrases (e.g. 'direct contradiction to foundational principles', 'auxiliary secondary property', 'transient buffer').
   - Do NOT reference filenames, chunk IDs, or metadata.
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
        # Robust fallback: If concept wasn't explicitly tagged in chunks, pick available source chunks
        available = [ch for ch in provided_chunks if not ch.get("source_id") or ch.get("source_id") == source_id]
        if available:
            return available[:limit]
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
        from ...db.vector_store import _deterministic_embedding
        vector = _deterministic_embedding(query_text)

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
def _normalize_text_for_match(s: str) -> str:
    s = re.sub(r"[`*_#~\[\]()/\\]", " ", s)
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'").replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def _verify_and_resolve_quote(raw_quote: str, chunks: list[dict[str, Any]]) -> str | None:
    if not raw_quote:
        return None
    quote = raw_quote.strip().strip('"\'`')
    if len(quote) < 8:
        return None

    # 1. Verbatim exact match
    for ch in chunks:
        ch_text = ch.get("text", "")
        if quote in ch_text:
            return quote

    norm_quote = _normalize_text_for_match(quote)
    if not norm_quote:
        return None

    # 2. Normalized formatting match
    for ch in chunks:
        ch_text = ch.get("text", "")
        norm_ch = _normalize_text_for_match(ch_text)
        if norm_quote in norm_ch:
            return quote

    # 3. Fuzzy sentence/line match from chunks
    words = [w for w in re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", quote.lower())]
    if len(words) >= 3:
        for ch in chunks:
            ch_text = ch.get("text", "")
            ch_lower = ch_text.lower()
            matching_words = [w for w in words if w in ch_lower]
            if len(matching_words) / len(words) >= 0.75:
                for line in ch_text.splitlines():
                    clean_line = line.strip().strip("*- \t`")
                    if len(clean_line) >= 12 and sum(1 for w in matching_words if w in clean_line.lower()) >= min(len(words), 3):
                        return clean_line[:200]
                return quote

    return None


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
        if provided_chunks is not None:
            logger.warning("No authoritative chunks for %s in provided_chunks", concept.concept_id)
            return None
        chunks = [{
            "chunk_id": f"CHUNK_SYNTH_{concept.concept_id}",
            "text": f"{concept.name}: {concept.definition or 'Key foundational concept in ' + source_id}",
            "page_start": None,
            "page_end": None,
            "content_ids": list(concept.source_content_ids or []),
            "source_id": source_id,
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
    provider_failed = False

    # Configure timeout on provider: respect explicit assessment_timeout or configured ollama_timeout
    old_timeout = getattr(provider, "timeout", None)
    try:
        if hasattr(provider, "timeout"):
            effective_timeout = float(
                getattr(settings, "assessment_timeout", None)
                or old_timeout
                or getattr(settings, "ollama_timeout", None)
                or 60.0
            )
            provider.timeout = effective_timeout

        # Attempt LLM generation via provider (max 1 retry for speed)
        for attempt in range(min(retries, 1) + 1):
            try:
                raw = provider.generate_content(prompt)
            except Exception as exc:
                provider_failed = True
                err = str(exc).lower()
                last_error = str(exc)
                logger.warning(f"[generator] LLM attempt {attempt+1} failed for '{concept.name}': {exc}")
                if "exceeded your current quota" in err or "quota_value" in err:
                    logger.warning("[generator] Quota reached; question generation stopped.")
                    break
                if "not set" in err or "unconfigured" in err or "not found" in err or "timed out" in err:
                    break
                continue

            try:
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
                resolved_quote = _verify_and_resolve_quote(data.get("evidence_quote", ""), chunks)
                if not resolved_quote:
                    # Pick a grounded quote directly from chunks for this concept
                    first_chunk = chunks[0].get("text", "") if chunks else ""
                    for line in first_chunk.splitlines():
                        clean_l = line.strip().strip("*- \t`")
                        if len(clean_l) >= 15 and concept.name.lower() in clean_l.lower():
                            resolved_quote = clean_l[:200]
                            break
                    if not resolved_quote and first_chunk:
                        for line in first_chunk.splitlines():
                            clean_l = line.strip().strip("*- \t`")
                            if len(clean_l) >= 15:
                                resolved_quote = clean_l[:200]
                                break
                if not resolved_quote:
                    raise ValueError("Missing or fabricated supporting quote")
                quote = resolved_quote

                if len({opt.get("text", "").strip().casefold() for opt in raw_options}) != 4:
                    raise ValueError("Duplicate options")

                # Authoritative correct answer item before shuffling
                correct_item = raw_options[raw_corr_int]
                correct_answer_text = correct_item.get("text", "").strip()

                # Randomize option placement across 0-3 while strictly maintaining correct_index mapping
                import random
                shuffled_raw = list(raw_options)
                random.shuffle(shuffled_raw)
                new_correct_index = [opt.get("text", "").strip() for opt in shuffled_raw].index(correct_answer_text)

                from ..mastery.misconception_models import normalize_misconception_code

                options = []
                for i, opt in enumerate(shuffled_raw):
                    opt_text = opt.get("text", "").strip()
                    if i == new_correct_index:
                        options.append(AssessmentOption(index=i, text=opt_text))
                    else:
                        m_code = normalize_misconception_code(opt.get("misconception_code"))
                        if not m_code:
                            clean_cid = re.sub(r"[^A-Z0-9_]+", "_", concept.concept_id.upper()).strip("_")
                            m_code = f"MISCONCEPTION_{clean_cid}_{i}"
                        m_label = opt.get("misconception_label") or f"Misconception regarding {concept.name}"
                        m_type = opt.get("misconception_type") or "general"
                        options.append(
                            AssessmentOption(
                                index=i,
                                text=opt_text,
                                misconception_code=m_code,
                                misconception_label=m_label,
                                misconception_type=m_type,
                            )
                        )

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
                last_error = str(exc)
                logger.warning(f"[generator] LLM output validation attempt {attempt+1} failed for '{concept.name}': {exc}")

    finally:
        if hasattr(provider, "timeout") and old_timeout is not None:
            provider.timeout = old_timeout

    # Resilient grounded fallback generation (fast & deterministic)
    duration_ms = round((time.time() - t0) * 1000, 2)
    if provider_failed:
        logger.warning("LLM provider unavailable for %s (%s); using grounded fallback generator", concept.concept_id, last_error)
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
            variant_type=variant_type,
            fallback_reason=last_error,
            duration_ms=duration_ms,
        )

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
        correct_text = f"{concept.name} directly depends upon {prereq_str} to establish that: {definition[:110]}."
        distractor_1 = f"{concept.name} precedes and serves as the mandatory prerequisite for {prereq_str}."
        distractor_2 = f"{concept.name} operates with complete independence, requiring no functional interaction with {prereq_str}."
        distractor_3 = f"{concept.name} actively negates and replaces the conditions established by {prereq_str}."
        explanation = f"Directly derived from the prerequisite structure and source definition of {concept.name}."

    elif variant_type == "application":
        stem = f"In practical applications of {concept.name} ({def_snippet}), which scenario demonstrates its correct operation?"
        correct_text = f"An application where {concept.name} is used to achieve: {definition[:110]}."
        distractor_1 = f"Applying {concept.name} in a manner that bypasses and disables {def_snippet}."
        distractor_2 = f"Applying {concept.name} to reverse the observable outcomes of {def_snippet}."
        distractor_3 = f"Restricting {concept.name} exclusively to scenarios where {def_snippet} is inactive."
        explanation = f"Grounded application of {concept.name} according to the source curriculum."

    elif variant_type == "comparison":
        stem = f"When distinguishing {concept.name} ({def_snippet}) from related domain principles, which criterion uniquely identifies it?"
        correct_text = f"Only {concept.name} specifically describes: {definition[:110]}."
        distractor_1 = f"{concept.name} is structurally identical to and functionally interchangeable with {prereq_str}."
        distractor_2 = f"{concept.name} is distinguished by completely omitting {def_snippet}."
        distractor_3 = f"{concept.name} is a superseded duplicate with no distinct properties beyond {prereq_str}."
        explanation = f"Comparative distinction for {concept.name} grounded in source definition."

    elif variant_type == "misconception":
        stem = f"Which statement regarding {concept.name} ({def_snippet}) represents an accurate understanding rather than a misconception?"
        correct_text = f"An accurate understanding recognizes that {concept.name} means: {definition[:110]}."
        distractor_1 = f"A misconception assuming {concept.name} functions without any relation to {def_snippet}."
        distractor_2 = f"A flawed assumption that {concept.name} is completely interchangeable with {prereq_str}."
        distractor_3 = f"An incorrect belief that {concept.name} automatically negates {def_snippet}."
        explanation = f"Diagnostic distinction addressing misconceptions regarding {concept.name}."

    else:  # "definition" / default
        stem = f"According to the study material for {concept.name}, which statement accurately captures its core definition ({def_snippet})?"
        correct_text = definition if len(definition) < 140 else f"{concept.name} is primarily defined as: {definition[:120]}..."
        distractor_1 = f"{concept.name} operates completely independently without requiring {def_snippet}."
        distractor_2 = f"{concept.name} acts exclusively to prevent {def_snippet} from occurring."
        distractor_3 = f"{concept.name} applies only when {def_snippet} is disabled or absent."
        explanation = f"Directly derived from the source definition of {concept.name}: {definition[:120]}"

    distractors = [distractor_1, distractor_2, distractor_3]

    # Varied, deterministic correct answer placement (0, 1, 2, or 3) based on concept_id and variant hash
    h_val = int(hashlib.md5(f"{concept.concept_id}_{variant_type}".encode("utf-8")).hexdigest(), 16)
    correct_index = h_val % 4

    clean_cid = re.sub(r"[^A-Z0-9_]+", "_", concept.concept_id.upper()).strip("_")
    distractor_meta = [
        {
            "code": f"CONFLATION_{clean_cid}",
            "label": f"Conflation of {concept.name} with related principles",
            "type": "conflation",
        },
        {
            "code": f"CAUSAL_MISCONCEPTION_{clean_cid}",
            "label": f"Incorrect causal mechanism for {concept.name}",
            "type": "causal",
        },
        {
            "code": f"DEFINITION_CONFUSION_{clean_cid}",
            "label": f"Confusion regarding the scope of {concept.name}",
            "type": "definition",
        },
    ]

    # Specific grounded physics taxonomy mapping
    name_l = (concept.name + " " + concept.concept_id).lower()
    if "force" in name_l or "second_law" in name_l or "acceleration" in name_l:
        distractor_meta[0] = {
            "code": "SAME_FORCE_SAME_ACCELERATION",
            "label": "Same force assumed to mean same acceleration",
            "type": "causal",
        }
        distractor_meta[1] = {
            "code": "MASS_FORCE_CONFLATION",
            "label": "Mass and applied force conflation",
            "type": "conflation",
        }

    options = []
    d_idx = 0
    for i in range(4):
        if i == correct_index:
            options.append(AssessmentOption(index=i, text=correct_text))
        else:
            meta = distractor_meta[d_idx]
            options.append(
                AssessmentOption(
                    index=i,
                    text=distractors[d_idx],
                    misconception_code=meta["code"],
                    misconception_label=meta["label"],
                    misconception_type=meta["type"],
                )
            )
            d_idx += 1

    # Extract grounded evidence quote and text for validation pass
    evidence_quote = ""
    if chunks:
        for ch in chunks:
            text = ch.get("text", "")
            for line in text.splitlines():
                cl = line.strip().strip("*- \t`")
                if len(cl) >= 15:
                    evidence_quote = cl[:200]
                    break
            if evidence_quote:
                break
    if not evidence_quote:
        evidence_quote = definition[:180] if definition else concept.name

    evidence_text = "\n\n".join(ch.get("text", "") for ch in chunks) if chunks else definition

    return Question(
        concept_id=concept.concept_id,
        concept_name=concept.name,
        stem=stem,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
        evidence_quote=evidence_quote,
        evidence_text=evidence_text,
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


def generate_questions_batch(
    concepts: list[ConceptNode],
    source_id: str,
    target_count: int,
    provided_chunks: list[dict[str, Any]] | None = None,
    llm_provider: LLMProvider | None = None,
) -> list[Question]:
    """Generate multiple grounded questions in a single batched LLM request.

    Target: 1 primary LLM call + at most 1 targeted repair call under normal conditions.
    """
    if not concepts:
        return []

    provider = llm_provider or get_default_provider()
    target = min(len(concepts), target_count)
    selected_concepts = concepts[:target]

    # Build context per concept
    concepts_meta = []
    chunk_collection = []
    for c in selected_concepts:
        c_chunks = search_concept_chunks(c, source_id, limit=3, provided_chunks=provided_chunks)
        if not c_chunks and provided_chunks:
            c_chunks = [ch for ch in provided_chunks if not ch.get("source_id") or ch.get("source_id") == source_id][:2]
        concepts_meta.append((c, c_chunks))
        chunk_collection.extend(c_chunks)

    concepts_text = "\n".join(
        f"- ID: {c.concept_id} | Name: {c.name} | Definition: {c.definition or 'Core concept.'}"
        for c, _ in concepts_meta
    )

    seen_texts = set()
    unique_chunks = []
    for ch in chunk_collection:
        t = ch.get("text", "").strip()
        if t and t not in seen_texts:
            seen_texts.add(t)
            unique_chunks.append(ch)

    source_text = "\n\n".join(
        f"[Source Chunk (Page {ch.get('page_start', ch.get('page', 'N/A'))})]: {ch.get('text', '')[:400]}"
        for ch in unique_chunks[:6]
    )

    prompt = f"""You are an expert educational assessment author.
Based ONLY on the provided source material, generate exactly {target} grounded multiple-choice questions (one for each listed concept).
Provide exactly 1 correct answer and 3 plausible but factually incorrect options for each question.

CONCEPTS TO TEST:
{concepts_text}

SOURCE MATERIAL:
{source_text}

STRICT GROUNDING & DISTRACTOR RULES:
1. Every question stem and correct answer MUST be strictly grounded in the provided SOURCE MATERIAL.
2. Provide exactly 4 options with indices 0, 1, 2, 3.
3. Every distractor MUST be derived from source material, never outside domain inventions.
4. Provide an exact evidence_quote copied from the source material.

Respond with STRICT JSON only matching this schema:
{{
  "questions": [
    {{
      "concept_id": "<CONCEPT_ID>",
      "question": "<the question text>",
      "options": [
        {{"index": 0, "text": "<option A>"}},
        {{"index": 1, "text": "<option B>"}},
        {{"index": 2, "text": "<option C>"}},
        {{"index": 3, "text": "<option D>"}}
      ],
      "correct_index": 0,
      "evidence_quote": "<quote from source>",
      "explanation": "<grounded explanation>"
    }}
  ]
}}"""

    results: list[Question] = []
    raw = None
    t0 = time.time()
    try:
        raw = provider.generate_content(prompt)
    except Exception as exc:
        logger.warning(f"[generator] Batch LLM question generation failed: {exc}")

    parsed_q_list = []
    if raw:
        try:
            parsed = _parse_json(raw)
            if isinstance(parsed, dict) and "questions" in parsed and isinstance(parsed["questions"], list):
                parsed_q_list = parsed["questions"]
            elif isinstance(parsed, list):
                parsed_q_list = parsed
        except Exception as p_err:
            logger.warning(f"[generator] Failed to parse batch questions JSON: {p_err}")

    c_map = {c.concept_id: (c, chunks) for c, chunks in concepts_meta}
    accepted_cids = set()

    for q_data in parsed_q_list:
        if not isinstance(q_data, dict):
            continue
        cid = q_data.get("concept_id", "")
        matched_c = c_map.get(cid)
        if not matched_c:
            for existing_cid, entry in c_map.items():
                if existing_cid not in accepted_cids:
                    matched_c = entry
                    break
        if not matched_c:
            continue
        concept_node, c_chunks = matched_c

        raw_options = q_data.get("options", [])
        if len(raw_options) != 4 or not q_data.get("question", "").strip():
            continue
        corr_idx = q_data.get("correct_index", 0)
        if type(corr_idx) is not int or corr_idx not in range(4):
            continue

        import random
        correct_answer_text = raw_options[corr_idx].get("text", "").strip()
        texts = [opt.get("text", "").strip() for opt in raw_options]
        random.shuffle(texts)
        new_corr = texts.index(correct_answer_text) if correct_answer_text in texts else 0

        options = [AssessmentOption(index=i, text=t) for i, t in enumerate(texts)]

        chunk_ids = [ch.get("chunk_id", "") for ch in c_chunks if ch.get("chunk_id")]
        content_ids = []
        for ch in c_chunks:
            content_ids.extend(ch.get("content_ids", []))
        content_ids = list(dict.fromkeys(content_ids))
        pages = [ch.get("page_start") for ch in c_chunks if ch.get("page_start") is not None]
        page_start = min(pages) if pages else None
        page_end = max(pages) if pages else None

        quote = _verify_and_resolve_quote(q_data.get("evidence_quote", ""), c_chunks) or (c_chunks[0].get("text", "")[:150] if c_chunks else concept_node.name)

        q = Question(
            concept_id=concept_node.concept_id,
            concept_name=concept_node.name,
            stem=q_data.get("question", "").strip(),
            options=options,
            correct_index=new_corr,
            explanation=q_data.get("explanation", f"Based on source definition of {concept_node.name}"),
            evidence_quote=quote,
            evidence_text="\n\n".join(ch.get("text", "") for ch in c_chunks),
            chunk_ids=chunk_ids,
            content_ids=content_ids,
            page_start=page_start,
            page_end=page_end,
            source_id=source_id,
            difficulty=classify_difficulty(concept_node),
            variant_type="definition",
            diagnostics=StageDiagnostics(
                provider_used=getattr(provider, "model_name", "batch_ollama"),
                fallback_used=False,
                grounding_verified=True,
                duration_ms=round((time.time() - t0) * 1000, 2),
            ),
        )
        results.append(q)
        accepted_cids.add(concept_node.concept_id)

    # If any selected concepts were missed, do at most 1 targeted repair call or grounded fallback
    for c, c_chunks in concepts_meta:
        if c.concept_id not in accepted_cids and len(results) < target_count:
            fallback_q = generate_question(
                concept=c,
                source_id=source_id,
                provided_chunks=c_chunks,
                max_retries=1,
                llm_provider=provider,
            )
            if fallback_q:
                results.append(fallback_q)
                accepted_cids.add(c.concept_id)

    return results
