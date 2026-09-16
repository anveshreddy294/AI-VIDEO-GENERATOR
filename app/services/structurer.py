"""Knowledge Structuring, Concept Extraction & Knowledge Graph Generation.

Analyzes normalized ContentUnits to:
1. Detect document/video structure (Chapters & Sections) and map them to ContentUnits.
2. Extract granular concepts with prerequisites and direct source ContentUnit mapping.
3. Construct the persistent KnowledgeGraph network.
4. Derive the user-facing TopicBlueprint summary.
"""

import json
import re
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel

from ..core.config import settings
from .schemas import ConceptNode, ContentUnit, KnowledgeGraph, TopicBlueprint

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


def _client() -> genai.GenerativeModel:
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.generation_model)


def process_structure_and_concepts(
    units: list[ContentUnit],
) -> tuple[list[ContentUnit], KnowledgeGraph, TopicBlueprint]:
    """Analyze ContentUnits with Gemini to detect structure, extract concepts, and build KnowledgeGraph."""
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
        prompt_blocks.append(f"[{u.content_id}] ({loc}): {u.text[:400]}")

    material_text = "\n\n".join(prompt_blocks)[:60_000]
    payload = _STRUCTURE_AND_CONCEPT_PROMPT + material_text

    raw_response = ""
    for attempt in range(2):
        try:
            response = _client().generate_content(payload)
            raw_response = response.text or ""
            data = _parse_json(raw_response)
            return _assemble_outputs(data, units)
        except Exception as exc:
            print(f"[structurer] Attempt {attempt + 1} failed: {exc}")
            payload = (
                _STRUCTURE_AND_CONCEPT_PROMPT
                + "Your previous response was invalid. Return STRICT JSON matching the schema.\nMATERIAL:\n"
                + material_text
            )

    # Fallback if LLM fails
    return _fallback_outputs(units)


def _assemble_outputs(
    data: dict[str, Any], units: list[ContentUnit]
) -> tuple[list[ContentUnit], KnowledgeGraph, TopicBlueprint]:
    cu_map = {u.content_id: u for u in units}

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
    )

    return list(cu_map.values()), kg, blueprint


def _fallback_outputs(
    units: list[ContentUnit],
) -> tuple[list[ContentUnit], KnowledgeGraph, TopicBlueprint]:
    source_id = units[0].source_id if units else "SRC_UNKNOWN"
    asset_id = units[0].asset_id if units else "AST_UNKNOWN"

    kg = KnowledgeGraph(concepts={})
    blueprint = TopicBlueprint(
        topic_name="Extracted Material",
        key_concepts=["Study Material"],
        prerequisites=[],
        difficulty_level="intermediate",
        source_id=source_id,
        asset_id=asset_id,
        content_unit_count=len(units),
        chunk_count=0,
    )
    return units, kg, blueprint


def _parse_json(raw: str) -> dict:
    without_fences = re.sub(r"```(?:json)?", "", raw).strip()
    return json.loads(without_fences)