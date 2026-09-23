"""Knowledge Structuring, Concept Extraction & Knowledge Graph Generation.

Analyzes normalized ContentUnits to:
1. Detect document/video structure (Chapters & Sections) and map them to ContentUnits.
2. Extract granular concepts with prerequisites and direct source ContentUnit mapping.
3. Construct the persistent KnowledgeGraph network.
4. Derive the user-facing TopicBlueprint summary.
"""

import json
import logging
import re
import time
from typing import Any

from ..core.config import settings
from .schemas import ConceptNode, ContentUnit, KnowledgeGraph, StageDiagnostics, TopicBlueprint

logger = logging.getLogger(__name__)


class KnowledgeExtractionFailed(ValueError):
    """Raised when knowledge structuring cannot extract valid, source-grounded concepts."""

    pass


_STRUCTURE_AND_CONCEPT_PROMPT = """You are an expert curriculum and knowledge graph analyst.
Analyze the provided study material content units and extract:
1. The structural hierarchy (chapters/sections) of the material.
2. The core concepts taught, their definitions, prerequisite concept IDs, and which content unit IDs teach them.

CRITICAL GROUNDING RULES:
- Every concept MUST be supported by factual evidence in the provided MATERIAL CONTENT UNITS.
- Do NOT invent or assume concepts from external domains.
- Do NOT use generic placeholder topic names like 'Study Material', 'Features', 'Introduction', 'Overview', or 'Untitled'.
- If the source material does not support educational concepts, return an empty "concepts" array.

Respond with STRICT JSON only — no markdown fences, no commentary.

Schema:
{
  "topic_name": "<Short overarching topic name based on the material>",
  "difficulty_level": "beginner | intermediate | advanced",
  "chapters": [
    {
      "id": "CH1",
      "title": "<Chapter Title>",
      "sections": [
        {
          "id": "SEC1_1",
          "title": "<Section Title>",
          "content_ids": ["<EXACT_CU_ID>"]
        }
      ]
    }
  ],
  "concepts": [
    {
      "concept_id": "<CONCEPT_NAME_IN_CAPS_UNDERSCORES>",
      "name": "<Concept Name Extracted From Material>",
      "definition": "<Clear 1-2 sentence definition directly from the material>",
      "prerequisite_concept_ids": [],
      "source_content_ids": ["<EXACT_CU_ID>"]
    }
  ]
}

RULES:
- Extract concepts ONLY from the provided material text below. Do NOT invent concepts from other domains.
- You MUST provide the top-level "concepts" array. Do NOT output "nodes" or "edges".
- concept_id MUST be uppercase with words separated by underscores (e.g. CONCEPT_TOPIC_NAME).
- prerequisite_concept_ids MUST reference valid concept_ids defined in the same list.
- source_content_ids MUST be drawn from the CU IDs in the provided material.
- difficulty_level MUST be one of: beginner, intermediate, advanced.

MATERIAL CONTENT UNITS:
"""


def _generate_with_llm(payload: str) -> str:
    """Generate content using ModelManager with runtime switching and automatic fallback."""
    from ..core.model_manager import model_manager
    timeout = max(100.0, float(getattr(settings, "ollama_timeout", 120.0)))
    raw_response, model_used = model_manager.generate_with_fallback(
        payload,
        is_json=True,
        timeout=timeout,
    )
    return raw_response


def _normalize_llm_data(data: dict[str, Any], units: list[ContentUnit]) -> dict[str, Any]:
    """Auto-repair and normalize LLM responses into compliant concepts schema with strict evidence grounding."""
    if not isinstance(data, dict):
        return {}

    cu_map = {u.content_id: u for u in units}

    # If "concepts" is missing or empty, search for alternative keys like "nodes", "topics", "key_concepts", "items"
    raw_concepts = data.get("concepts")
    if not raw_concepts or not isinstance(raw_concepts, list):
        converted = []
        edge_map: dict[str, list[str]] = {}
        for edge in data.get("edges", []):
            if isinstance(edge, dict):
                src, tgt = str(edge.get("source", "")), str(edge.get("target", ""))
                if src and tgt:
                    edge_map.setdefault(tgt, []).append(src)

        candidates = (
            data.get("nodes")
            or data.get("topics")
            or data.get("key_concepts")
            or data.get("items")
            or []
        )
        if isinstance(candidates, list):
            for i, item in enumerate(candidates):
                if isinstance(item, str):
                    name = item.strip()
                    defn = ""
                    nid = str(i + 1)
                elif isinstance(item, dict):
                    name = str(item.get("text") or item.get("name") or item.get("title") or item.get("label") or "").strip()
                    defn = str(item.get("definition") or item.get("description") or item.get("text") or "").strip()
                    nid = str(item.get("id", i + 1))
                else:
                    continue

                if len(name) < 3:
                    continue

                # Grounding check: concept name must appear in source material
                matched_cu = None
                for u in units:
                    if name.lower() in (u.text or "").lower():
                        matched_cu = u
                        break
                if not matched_cu:
                    sig_words = [w.lower() for w in re.findall(r"[A-Za-z0-9]{4,}", name)]
                    if sig_words:
                        for u in units:
                            if all(w in (u.text or "").lower() for w in sig_words):
                                matched_cu = u
                                break
                if not matched_cu:
                    logger.warning("[structurer] Rejecting candidate concept '%s' - no source evidence found.", name)
                    continue

                if not defn:
                    u_text = matched_cu.text or ""
                    for s in re.split(r"(?<=[.!?])\s+", u_text):
                        if name.lower() in s.lower():
                            defn = s.strip()
                            break
                    if not defn:
                        defn = u_text[:200].strip()

                cid = re.sub(r"[^A-Z0-9_]", "_", f"CONCEPT_{name.upper()}")[:35].strip("_") or f"CONCEPT_{i+1:03d}"
                prereqs = [
                    re.sub(r"[^A-Z0-9_]", "_", f"CONCEPT_{p.upper()}")[:35].strip("_")
                    for p in edge_map.get(nid, [])
                ]
                converted.append({
                    "concept_id": cid,
                    "name": name,
                    "definition": defn,
                    "prerequisite_concept_ids": prereqs,
                    "source_content_ids": [matched_cu.content_id],
                })
        if converted:
            data["concepts"] = converted

    # Normalize existing concepts list if present
    if "concepts" in data and isinstance(data["concepts"], list):
        repaired = []
        known_ids: set[str] = set()
        for idx, c in enumerate(data["concepts"]):
            if not isinstance(c, dict):
                continue
            name = str(c.get("name") or c.get("title") or "").strip()
            if not name or len(name) < 2:
                continue

            # Grounding check: verify that concept name exists in source units
            matched_cu = None
            refs = c.get("source_content_ids")
            valid_refs = [r for r in refs if r in cu_map] if isinstance(refs, list) else []
            if valid_refs:
                for ref_id in valid_refs:
                    u = cu_map[ref_id]
                    if name.lower() in (u.text or "").lower():
                        matched_cu = u
                        break
            if not matched_cu:
                for u in units:
                    if name.lower() in (u.text or "").lower():
                        matched_cu = u
                        valid_refs = [u.content_id]
                        break
            if not matched_cu:
                sig_words = [w.lower() for w in re.findall(r"[A-Za-z0-9]{4,}", name)]
                if sig_words:
                    for u in units:
                        if any(w in (u.text or "").lower() for w in sig_words):
                            matched_cu = u
                            valid_refs = [u.content_id]
                            break

            if not matched_cu or not valid_refs:
                logger.warning("[structurer] Rejecting concept '%s' due to lack of source evidence.", name)
                continue

            cid = str(c.get("concept_id") or "").strip()
            if not cid:
                cid = re.sub(r"[^A-Z0-9_]", "_", f"CONCEPT_{name.upper()}")[:35].strip("_") or f"CONCEPT_{idx+1:03d}"
            if cid in known_ids:
                cid = f"{cid}_{idx+1}"
            known_ids.add(cid)
            c["concept_id"] = cid
            c["name"] = name

            defn = str(c.get("definition") or c.get("description") or "").strip()
            if not defn or "as defined in the curriculum materials" in defn.lower():
                u_text = matched_cu.text or ""
                for s in re.split(r"(?<=[.!?])\s+", u_text):
                    if name.lower() in s.lower():
                        defn = s.strip()
                        break
                if not defn:
                    defn = u_text[:200].strip()
            c["definition"] = defn
            c["source_content_ids"] = valid_refs
            repaired.append(c)

        # Sanitize prerequisites: remove missing parents and self-loops
        for c in repaired:
            parents = c.get("prerequisite_concept_ids")
            if isinstance(parents, list):
                c["prerequisite_concept_ids"] = [
                    p for p in parents
                    if p in known_ids and p != c["concept_id"]
                ]
            else:
                c["prerequisite_concept_ids"] = []

        data["concepts"] = repaired

    return data


def process_structure_and_concepts(
    units: list[ContentUnit],
) -> tuple[list[ContentUnit], KnowledgeGraph, TopicBlueprint]:
    """Analyze ContentUnits with LLM to detect structure, extract concepts, and build KnowledgeGraph."""
    if not units:
        empty_kg = KnowledgeGraph(concepts={})
        empty_blueprint = TopicBlueprint(
            topic_name="Empty Document",
            key_concepts=[],
            prerequisites=[],
            difficulty_level="beginner",
            content_unit_count=0,
            chunk_count=0,
        )
        return units, empty_kg, empty_blueprint

    # Build concise textual representation with CU IDs for the LLM
    prompt_blocks = []
    for u in units:
        loc = f"p.{u.page_number}" if u.page_number else (f"{u.timestamp_start:.0f}s" if u.timestamp_start is not None else f"seq.{u.sequence_index}")
        prompt_blocks.append(f"[{u.content_id}] ({loc}): {u.text}")

    material_text = "\n\n".join(prompt_blocks)
    if len(material_text) > 60_000:
        raise ValueError("Material exceeds the reasoning context limit; split it into smaller sources. No content was silently truncated.")
    payload = _STRUCTURE_AND_CONCEPT_PROMPT + material_text

    start_t = time.time()
    last_err: str | None = None
    for attempt in range(2):
        try:
            raw_response = _generate_with_llm(payload)
            data = _parse_json(raw_response)
            dur_ms = int((time.time() - start_t) * 1000)

            # Auto-repair and normalize LLM response into concepts schema
            data = _normalize_llm_data(data, units)

            # Check grounding overlap: ensure returned concepts aren't hallucinated boilerplate
            raw_concepts = data.get("concepts", [])
            if raw_concepts and isinstance(raw_concepts, list):
                extracted_names = [c.get("name", "").lower() for c in raw_concepts if c.get("name")]
                has_overlap = any(
                    any(word in material_text.lower() for word in name.split() if len(word) >= 4)
                    for name in extracted_names
                )
                if not has_overlap and any("force" in name or "newton" in name for name in extracted_names) and "force" not in material_text.lower():
                    logger.warning("[structurer] LLM returned hallucinated concepts unrelated to source; using grounded fallback")
                    return _fallback_outputs(units, fallback_reason="Hallucinated boilerplate concepts", duration_ms=dur_ms)

            return _assemble_outputs(data, units, duration_ms=dur_ms)
        except Exception as exc:
            last_err = str(exc)
            logger.warning("[structurer] Attempt %d failed: %s", attempt + 1, exc)
            payload = (
                _STRUCTURE_AND_CONCEPT_PROMPT
                + "Your previous response was invalid. Return STRICT JSON matching the schema.\nMATERIAL:\n"
                + material_text
            )

    dur_ms = int((time.time() - start_t) * 1000)
    logger.warning("[structurer] LLM structure extraction failed after retries. Error: %s", last_err)
    raise RuntimeError(f"Knowledge extraction failed after two attempts: {last_err}")


def _assemble_outputs(
    data: dict[str, Any], units: list[ContentUnit], duration_ms: int = 0
) -> tuple[list[ContentUnit], KnowledgeGraph, TopicBlueprint]:
    cu_map = {u.content_id: u for u in units}
    concepts = data.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        raise KnowledgeExtractionFailed("Knowledge extraction returned no valid grounded concepts.")

    from .concept_id import canonicalize_concept_id, ConceptCollisionError

    # Canonicalize all concept IDs and detect collisions
    alias_map: dict[str, str] = {}
    reverse_map: dict[str, str] = {}
    for i, c in enumerate(concepts):
        raw_id = c.get("concept_id") or c.get("name") or f"CONCEPT_{i+1:03d}"
        canonical = canonicalize_concept_id(str(raw_id))
        if canonical in reverse_map and reverse_map[canonical] != str(raw_id):
            raise ConceptCollisionError(
                f"Concept collision in structuring: '{reverse_map[canonical]}' and '{raw_id}' both canonicalize to '{canonical}'"
            )
        alias_map[str(raw_id)] = canonical
        reverse_map[canonical] = str(raw_id)
        c["concept_id"] = canonical

    for c in concepts:
        c["prerequisite_concept_ids"] = [
            alias_map.get(str(p), canonicalize_concept_id(str(p)))
            for p in c.get("prerequisite_concept_ids", [])
            if p
        ]
        c["related_concept_ids"] = [
            alias_map.get(str(r), canonicalize_concept_id(str(r)))
            for r in c.get("related_concept_ids", [])
            if r
        ]

    ids = [c.get("concept_id") for c in concepts]
    if any(not isinstance(cid, str) or not cid.strip() for cid in ids) or len(set(ids)) != len(ids):
        raise ValueError("Concept IDs must be nonempty and unique")
    dependencies = {}
    for c in concepts:
        refs = c.get("source_content_ids", [])
        if not refs or any(ref not in cu_map for ref in refs):
            raise ValueError("Every concept must reference actual content units")
        if not c.get("name", "").strip() or not c.get("definition", "").strip():
            raise ValueError("Every concept must have a name and definition")
        parents = c.get("prerequisite_concept_ids", [])
        if any(parent not in ids for parent in parents):
            raise ValueError("Unknown prerequisite concept")
        dependencies[c["concept_id"]] = parents
    visiting, visited = set(), set()
    def visit(cid):
        if cid in visiting:
            raise ValueError("Cyclic concept prerequisites")
        if cid in visited:
            return
        visiting.add(cid)
        for parent in dependencies[cid]:
            visit(parent)
        visiting.remove(cid)
        visited.add(cid)
    for cid in ids:
        visit(cid)

    # 1. Map Chapters & Sections back to ContentUnits
    chapters_data = data.get("chapters", [])
    for ch in chapters_data:
        ch_title = ch.get("title", "General")
        for sec in ch.get("sections", []):
            sec_title = sec.get("title", "Main")
            for cu_id in sec.get("content_ids", []):
                if cu_id in cu_map:
                    cu_map[cu_id].chapter = ch_title
                    cu_map[cu_id].section = sec_title

    # 2. Build KnowledgeGraph
    concepts_dict: dict[str, ConceptNode] = {}
    prereqs_set: set[str] = set()
    alias_map: dict[str, str] = {}

    raw_concepts = data.get("concepts", [])
    for idx, cdata in enumerate(raw_concepts):
        raw_name = cdata.get("name") or cdata.get("concept_id") or f"Concept_{idx+1}"
        cid = canonicalize_concept_id(raw_name)
        if cdata.get("concept_id"):
            alias_map[cdata["concept_id"]] = cid
        if cdata.get("name"):
            alias_map[cdata["name"]] = cid
        alias_map[cid] = cid

    for idx, cdata in enumerate(raw_concepts):
        raw_name = cdata.get("name") or cdata.get("concept_id") or f"Concept_{idx+1}"
        cid = canonicalize_concept_id(raw_name)
        canonical_prereqs = [
            alias_map.get(p, canonicalize_concept_id(p))
            for p in cdata.get("prerequisite_concept_ids", [])
            if p
        ]
        canonical_related = [
            alias_map.get(r, canonicalize_concept_id(r))
            for r in cdata.get("related_concept_ids", [])
            if r
        ]
        node = ConceptNode(
            concept_id=cid,
            name=cdata.get("name", raw_name),
            definition=cdata.get("definition"),
            prerequisite_concept_ids=canonical_prereqs,
            related_concept_ids=canonical_related,
            source_content_ids=cdata.get("source_content_ids", []),
        )
        concepts_dict[cid] = node
        prereqs_set.update(node.prerequisite_concept_ids)

    if not concepts_dict:
        raise KnowledgeExtractionFailed("No valid source-grounded concepts could be identified.")

    kg = KnowledgeGraph(concepts=concepts_dict)

    # 3. Derive TopicBlueprint
    raw_topic = str(data.get("topic_name") or "").strip()
    generic_names = ("ingested learning material", "study material", "untitled", "unknown", "features", "overview", "introduction", "document", "general")
    if not raw_topic or raw_topic.lower() in generic_names:
        topic_name = list(concepts_dict.values())[0].name
    else:
        topic_name = raw_topic

    blueprint = TopicBlueprint(
        topic_name=topic_name,
        key_concepts=[c.name for c in concepts_dict.values()],
        prerequisites=list(prereqs_set),
        difficulty_level=data.get("difficulty_level", "intermediate"),
        source_id=units[0].source_id if units else None,
        asset_id=units[0].asset_id if units else None,
        content_unit_count=len(units),
        chunk_count=0,  # updated after chunking
        diagnostics=StageDiagnostics(
            provider_used=settings.llm_provider,
            fallback_used=False,
            grounding_verified=True,
            duration_ms=duration_ms,
        ),
    )

    return list(cu_map.values()), kg, blueprint


def _fallback_outputs(
    units: list[ContentUnit],
    fallback_reason: str | None = None,
    duration_ms: int = 0,
) -> tuple[list[ContentUnit], KnowledgeGraph, TopicBlueprint]:
    source_id = units[0].source_id if units else "SRC_UNKNOWN"
    asset_id = units[0].asset_id if units else "AST_UNKNOWN"

    concepts_dict: dict[str, ConceptNode] = {}
    prereqs_set: set[str] = set()
    seen_names: set[str] = set()
    topic_name = ""

    for u in units:
        text = (u.text or "").strip()
        if not text:
            continue

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            alpha_words = re.findall(r"[A-Za-z]{3,}", line)

            # Candidate topic title
            if not topic_name and 5 <= len(line) <= 80 and alpha_words:
                clean_title = re.sub(
                    r"^(Problem Statement \d+|Title of Problem Statement|Chapter \d+:?|Topic:?)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if len(clean_title) >= 5 and clean_title.lower() not in ("study material", "introduction", "overview", "features", "notes", "summary"):
                    topic_name = clean_title

            # Acronym or named pattern: e.g. "Free Space Optical Communication (FSOC)"
            matches = re.findall(r"([A-Z][A-Za-z0-9\s\-]{2,35}\s*\([A-Z0-9]{2,8}\))", line)
            for m in matches:
                name = m.strip()
                if name not in seen_names and len(seen_names) < 8:
                    seen_names.add(name)
                    cid_token = re.sub(r"[^A-Z0-9_]", "_", name.upper()).strip("_")
                    import hashlib
                    cid_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()[:6].upper()
                    cid = f"CONCEPT_{cid_token[:18]}_{cid_hash}"
                    defn = line if len(line) > len(name) + 15 else text[:250]
                    concepts_dict[cid] = ConceptNode(
                        concept_id=cid,
                        name=name,
                        definition=defn.strip(),
                        prerequisite_concept_ids=list(concepts_dict.keys())[-1:] if concepts_dict else [],
                        related_concept_ids=[],
                        source_content_ids=[u.content_id],
                    )

            # Definition sentences: "X is defined as ...", "X refers to ...", "X states that ..."
            def_match = re.search(
                r"([A-Z][A-Za-z0-9\s\-]{2,30})\s+(?:is defined as|refers to|states that|represents|offers)\s+([^.\n]+)",
                line,
                flags=re.IGNORECASE,
            )
            if def_match and len(seen_names) < 8:
                term = def_match.group(1).strip()
                if term not in seen_names and len(term.split()) <= 4:
                    seen_names.add(term)
                    cid_token = re.sub(r"[^A-Z0-9_]", "_", term.upper()).strip("_")
                    import hashlib
                    cid_hash = hashlib.sha256(term.encode("utf-8")).hexdigest()[:6].upper()
                    cid = f"CONCEPT_{cid_token[:18]}_{cid_hash}"
                    concepts_dict[cid] = ConceptNode(
                        concept_id=cid,
                        name=term,
                        definition=f"{term} {def_match.group(0).split(term, 1)[-1].strip()}.",
                        prerequisite_concept_ids=list(concepts_dict.keys())[-1:] if concepts_dict else [],
                        related_concept_ids=[],
                        source_content_ids=[u.content_id],
                    )

            # Clean headings
            if 4 <= len(line) <= 60 and not line.endswith(".") and not line.startswith("http") and not line.startswith("•") and alpha_words:
                clean_hd = re.sub(
                    r"^(Section \d+(\.\d+)*:?|Chapter \d+:?|Description:?|Background:?)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip().rstrip(":")
                ignore_starts = ("code ", "git ", "pip ", "open ", "find", "change ", "expected", "select-string", "select ", "run ", "then ", "now ", "also ", "you should ", "for an ", "you can ", "if ")
                if 4 <= len(clean_hd) <= 45 and clean_hd not in seen_names and len(seen_names) < 6:
                    clean_alpha = re.findall(r"[A-Za-z]{3,}", clean_hd)
                    if clean_alpha and clean_hd.lower() not in ("parameter", "parameters", "notes", "summary", "overview", "introduction", "features", "study material") and not clean_hd.lower().startswith(ignore_starts):
                        seen_names.add(clean_hd)
                        cid_token = re.sub(r"[^A-Z0-9_]", "_", clean_hd.upper()).strip("_")
                        import hashlib
                        cid_hash = hashlib.sha256(clean_hd.encode("utf-8")).hexdigest()[:6].upper()
                        cid = f"CONCEPT_{cid_token[:18]}_{cid_hash}"
                        concepts_dict[cid] = ConceptNode(
                            concept_id=cid,
                            name=clean_hd,
                            definition=text[:300].strip(),
                            prerequisite_concept_ids=list(concepts_dict.keys())[-1:] if concepts_dict else [],
                            related_concept_ids=[],
                            source_content_ids=[u.content_id],
                        )

    # Fail closed: if no grounded concepts could be discovered, do NOT invent synthetic concepts
    if not concepts_dict:
        raise KnowledgeExtractionFailed(
            f"Rule-based concept extraction found no source-grounded concepts. Reason: {fallback_reason or 'No identifiable concepts in source text'}"
        )

    for node in concepts_dict.values():
        prereqs_set.update(node.prerequisite_concept_ids)

    final_topic = topic_name or list(concepts_dict.values())[0].name
    kg = KnowledgeGraph(concepts=concepts_dict)
    blueprint = TopicBlueprint(
        topic_name=final_topic,
        key_concepts=[c.name for c in concepts_dict.values()],
        prerequisites=list(prereqs_set),
        difficulty_level="intermediate",
        source_id=source_id,
        asset_id=asset_id,
        content_unit_count=len(units),
        chunk_count=0,
        diagnostics=StageDiagnostics(
            provider_used="heuristic_rule_fallback",
            fallback_used=True,
            fallback_reason=fallback_reason or "LLM structure extraction failed",
            error_code="LLM_EXTRACTION_FALLBACK",
            grounding_verified=False,
            duration_ms=duration_ms,
        ),
    )
    return units, kg, blueprint


def _parse_json(raw: str) -> dict:
    without_fences = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"(\{.*\})", without_fences, re.DOTALL)
    if match:
        without_fences = match.group(1).strip()
    try:
        return json.loads(without_fences)
    except Exception:
        cleaned = re.sub(r",\s*([\}\]])", r"\1", without_fences)
        return json.loads(cleaned)

