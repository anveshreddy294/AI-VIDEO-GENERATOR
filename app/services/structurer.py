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

_STRUCTURE_AND_CONCEPT_PROMPT = """You are an expert curriculum and knowledge graph analyst.
Analyze the provided study material content units and extract:
1. The structural hierarchy (chapters/sections) of the material.
2. The core concepts taught, their definitions, prerequisite concept IDs, and which content unit IDs teach them.

Respond with STRICT JSON only — no markdown fences, no commentary.

Schema:
{
  "topic_name": "<short overall title>",
  "difficulty_level": "beginner | intermediate | advanced",
  "chapters": [
    {
      "id": "CH1",
      "title": "<Chapter Title>",
      "sections": [
        {
          "id": "SEC1_1",
          "title": "<Section Title>",
          "content_ids": ["<CU_ID_1>", "<CU_ID_2>"]
        }
      ]
    }
  ],
  "concepts": [
    {
      "concept_id": "CONCEPT_FORCE",
      "name": "Force",
      "definition": "...",
      "prerequisite_concept_ids": [],
      "source_content_ids": ["<CU_ID_1>"]
    },
    {
      "concept_id": "CONCEPT_NEWTON_2",
      "name": "Newton's Second Law",
      "definition": "...",
      "prerequisite_concept_ids": ["CONCEPT_FORCE"],
      "source_content_ids": ["<CU_ID_1>", "<CU_ID_2>"]
    }
  ]
}

RULES:
- concept_id MUST be uppercase with words separated by underscores (e.g. CONCEPT_NEWTON_SECOND_LAW).
- prerequisite_concept_ids MUST reference valid concept_ids defined in the same list.
- source_content_ids MUST be drawn from the CU IDs in the provided material.
- difficulty_level MUST be one of: beginner, intermediate, advanced.

MATERIAL CONTENT UNITS:
"""


def _generate_with_llm(payload: str) -> str:
    """Generate content using the active LLM provider (Gemini or local adapter)."""
    from .assessment.providers import get_default_provider
    provider = get_default_provider()
    return provider.generate_content(payload)


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
    logger.warning("[structurer] LLM structure extraction failed after retries. Ingestion stopped. Error: %s", last_err)
    # Fallback if LLM fails
    raise RuntimeError(f"Knowledge extraction failed after two attempts: {last_err}")


def _assemble_outputs(
    data: dict[str, Any], units: list[ContentUnit], duration_ms: int = 0
) -> tuple[list[ContentUnit], KnowledgeGraph, TopicBlueprint]:
    cu_map = {u.content_id: u for u in units}
    concepts = data.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        raise ValueError("Knowledge extraction returned no concepts")
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

    for cdata in data.get("concepts", []):
        cid = cdata.get("concept_id") or f"CONCEPT_{len(concepts_dict)+1:03d}"
        node = ConceptNode(
            concept_id=cid,
            name=cdata.get("name", cid),
            definition=cdata.get("definition"),
            prerequisite_concept_ids=cdata.get("prerequisite_concept_ids", []),
            related_concept_ids=cdata.get("related_concept_ids", []),
            source_content_ids=cdata.get("source_content_ids", []),
        )
        concepts_dict[cid] = node
        prereqs_set.update(node.prerequisite_concept_ids)

    kg = KnowledgeGraph(concepts=concepts_dict)

    # 3. Derive TopicBlueprint
    blueprint = TopicBlueprint(
        topic_name=data.get("topic_name", "Ingested Learning Material"),
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
    topic_name = "Study Material"

    for u in units:
        text = (u.text or "").strip()
        if not text:
            continue

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            # Candidate topic title
            if topic_name == "Study Material" and 5 <= len(line) <= 80:
                clean_title = re.sub(
                    r"^(Problem Statement \d+|Title of Problem Statement|Chapter \d+:?|Topic:?)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if len(clean_title) >= 5:
                    topic_name = clean_title

            # Acronym or named pattern: e.g. "Free Space Optical Communication (FSOC)"
            matches = re.findall(r"([A-Z][A-Za-z0-9\s\-]{2,35}\s*\([A-Z0-9]{2,8}\))", line)
            for m in matches:
                name = m.strip()
                if name not in seen_names and len(seen_names) < 8:
                    seen_names.add(name)
                    cid_token = re.sub(r"[^A-Z0-9_]", "_", name.upper()).strip("_")
                    cid = f"CONCEPT_{cid_token[:24]}"
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
                    cid = f"CONCEPT_{cid_token[:24]}"
                    concepts_dict[cid] = ConceptNode(
                        concept_id=cid,
                        name=term,
                        definition=f"{term} {def_match.group(0).split(term, 1)[-1].strip()}.",
                        prerequisite_concept_ids=list(concepts_dict.keys())[-1:] if concepts_dict else [],
                        related_concept_ids=[],
                        source_content_ids=[u.content_id],
                    )

            # Clean headings
            if 4 <= len(line) <= 50 and not line.endswith(".") and not line.startswith("http") and not line.startswith("•"):
                clean_hd = re.sub(
                    r"^(Section \d+(\.\d+)*:?|Chapter \d+:?|Description:?|Background:?)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if 4 <= len(clean_hd) <= 40 and clean_hd not in seen_names and len(seen_names) < 8:
                    if clean_hd.lower() not in ("parameter", "parameters", "notes", "summary", "overview", "introduction"):
                        seen_names.add(clean_hd)
                        cid_token = re.sub(r"[^A-Z0-9_]", "_", clean_hd.upper()).strip("_")
                        cid = f"CONCEPT_{cid_token[:24]}"
                        concepts_dict[cid] = ConceptNode(
                            concept_id=cid,
                            name=clean_hd,
                            definition=text[:300].strip(),
                            prerequisite_concept_ids=list(concepts_dict.keys())[-1:] if concepts_dict else [],
                            related_concept_ids=[],
                            source_content_ids=[u.content_id],
                        )

    # Fallback to general concepts if nothing was matched
    if not concepts_dict and units:
        for idx, u in enumerate(units[:4]):
            cid = f"CONCEPT_{idx+1:03d}"
            snippet = (u.text or "")[:120].strip()
            name = snippet.split("\n")[0][:40] or f"Concept {idx+1}"
            concepts_dict[cid] = ConceptNode(
                concept_id=cid,
                name=name,
                definition=(u.text or "")[:250].strip() or f"Foundational knowledge for {name}.",
                prerequisite_concept_ids=list(concepts_dict.keys())[-1:] if concepts_dict else [],
                related_concept_ids=[],
                source_content_ids=[u.content_id],
            )

    for node in concepts_dict.values():
        prereqs_set.update(node.prerequisite_concept_ids)

    kg = KnowledgeGraph(concepts=concepts_dict)
    blueprint = TopicBlueprint(
        topic_name=topic_name,
        key_concepts=[c.name for c in concepts_dict.values()] or ["Study Material"],
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
    return json.loads(without_fences)
