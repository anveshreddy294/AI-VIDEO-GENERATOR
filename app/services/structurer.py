"""Knowledge Structuring — turns the Authoritative Source string into a
TopicBlueprint JSON object for the backend state.

A copy of the massive text string is sent to the LLM (Gemini 1.5 Pro) with a
restrictive prompt. We ask for JSON in the exact Pydantic shape, then parse and
validate it. On any deviation we retry once before falling back to a heuristic
parse, so a hallucinated field never crashes the ingestion pipeline.
"""

import json
import re

import google.generativeai as genai
from pydantic import ValidationError

from ..core.config import settings
from .schemas import TopicBlueprint

_STRUCTURE_PROMPT = """You are a curriculum analyst. Read the provided study
material and extract its knowledge skeleton. Respond with STRICT JSON only — no
markdown fences, no commentary, no keys outside this exact list.

Schema (all fields required):
{
  "topic_name": "<short title>",
  "key_concepts": ["<term 1>", "<term 2>"],
  "prerequisites": ["<concept the student must already know>"],
  "difficulty_level": "beginner | intermediate | advanced"
}

Rules:
- key_concepts: every genuinely important term used and defined in the text.
- prerequisites: what a student must understand BEFORE this material. Leave
  empty list if nothing assumed.
- difficulty_level: exactly one of the three allowed values.
- Do not invent concepts that are absent from the text.

MATERIAL:
"""


def _client() -> genai.GenerativeModel:
    settings.require_gemini()
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.generation_model)


def structure_topic(authoritative_text: str) -> TopicBlueprint:
    """Send the copy of the source text and parse a TopicBlueprint back."""
    payload = _STRUCTURE_PROMPT + authoritative_text[:50_000]  # cap context window

    # Two-shot: first raw, then (if parse/validation fails) schema-forced retry.
    for attempt in range(2):
        response = _client().generate_content(payload)
        raw = response.text or ""
        try:
            data = _parse_json(raw)
            return TopicBlueprint.model_validate(data)
        except ValidationError as exc:
            print(f"[attempt {attempt + 1}] blueprint didn't validate: {exc}")
            payload = _STRUCTURE_PROMPT + (
                "Your previous answer did not conform to the schema. Return "
                "valid JSON exactly matching the schema. MATERIAL:\n"
                + authoritative_text[:50_000]
            )
    raise RuntimeError("LLM failed to produce a valid TopicBlueprint after retries.")


def _parse_json(raw: str) -> dict:
    """Extract a JSON object from LLM output, tolerating ```json fences."""
    without_fences = re.sub(r"```(?:json)?", "", raw).strip()
    return json.loads(without_fences)