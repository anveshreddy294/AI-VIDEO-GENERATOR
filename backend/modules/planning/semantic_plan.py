"""Semantic plan generator.

For each storyboard entry, the LLM fills the template's slot schema:
  - which assets to use (from ASSET_REGISTRY)
  - which event types (from the template's ALLOWED_EVENTS)
  - anchor_phrases that MUST later appear verbatim in the narration

Strict validation:
  - asset_ids must be in ASSET_REGISTRY
  - event types must be in the template's ALLOWED_EVENTS
  - anchor_phrases are recorded (the narration writer will embed them)
"""
from __future__ import annotations

import json
from typing import Any

from modules.assets import ASSET_REGISTRY
from modules.config import NVIDIA_PLANNER_MODEL, PATHS, get_logger
from modules.llm.nvidia_client import NvidiaClient
from modules.planning.asset_registry import get_registry
from modules.planning.profile_context import format_learner_context
from modules.templates import TEMPLATES
from modules.templates.explain import EXPLAIN_TEMPLATE_IDS
from modules.templates.explain._base import merge_content
from modules.templates.chemistry import CHEMISTRY_TEMPLATE_IDS

logger = get_logger(__name__)

SEMANTIC_PLAN_SYSTEM = """You are an educational animation director.
You assign physics assets and event sequences to scenes.
NEVER include run_time, duration, seconds, or timing fields.
Respond ONLY with valid JSON. No markdown fences."""

SEMANTIC_PLAN_EXPLAIN_PROMPT = """Fill the semantic plan for this CHALKBOARD EXPLANATION scene.

CURRICULUM CONTEXT:
{curriculum_context}
Use the curriculum context as the primary source of truth.
Use terminology, formulas, labels, and concepts from the curriculum context whenever possible.
Do not invent unsupported facts.

{learner_context}

STORYBOARD ENTRY:
{storyboard_entry}

TEMPLATE: {template_id}
TEMPLATE ALLOWED EVENTS: {allowed_events}

CONTENT SCHEMA (fill the "content" object exactly in this shape):
{content_schema}

For "equation" fields use simple LaTeX with DOUBLE backslashes in JSON (e.g. "W = F \\\\cdot d").

RULES:
1. Return a "content" object matching CONTENT SCHEMA — all strings must be specific to this
   topic and anchor_example (not generic placeholders).
2. "assets" must be an empty array [].
3. Provide 2-4 "events" using only ALLOWED EVENTS; each needs an anchor_phrase (3-7 words)
   that will appear VERBATIM in the narration later.
4. If Prerequisites are listed in the curriculum context, include a brief recap phrase in one
   event's anchor_phrase when the scene builds on a prior concept.
5. "phase" is "before", "on", or "after"; "importance" is 1-5.

Return ONLY this JSON shape:
{{
  "scene_id": {scene_id},
  "concept_template": "{template_id}",
  "title": "<short scene title>",
  "anchor_example": "{anchor_example}",
  "content": <object matching CONTENT SCHEMA>,
  "assets": [],
  "events": [
    {{
      "id": "e0",
      "type": "<from ALLOWED EVENTS>",
      "targets": [],
      "anchor_phrase": "<3-7 verbatim words for narration>",
      "phase": "on",
      "importance": 3
    }}
  ]
}}"""

SEMANTIC_PLAN_CHEMISTRY_PROMPT = """Fill the semantic plan for this CHEMISTRY ANIMATION scene.

CURRICULUM CONTEXT:
{curriculum_context}
Use the curriculum context as the PRIMARY source of truth.
Use textbook terminology, element symbols, formulas, and model names from the curriculum context.
Do not invent unsupported chemical facts.

{learner_context}

STORYBOARD ENTRY:
{storyboard_entry}

TEMPLATE: {template_id}
TEMPLATE ALLOWED EVENTS: {allowed_events}

CONTENT SCHEMA — fill the "content" object exactly in this shape:
{content_schema}

CRITICAL RULES:
1. "content" must match the CONTENT SCHEMA exactly — use real element symbols, correct atomic numbers, and accurate electron shell counts from the curriculum context.
2. "assets" must be an empty array [].
3. Provide 3-5 "events" using only ALLOWED EVENTS; each event needs an anchor_phrase (3-7 words) that will appear VERBATIM in the narration.
4. For atomic_structure: shells must be a list of integers (e.g. [2, 8, 1] for sodium).
5. "phase" is "before", "on", or "after"; "importance" is 1-5 (5 = most critical visual beat).
6. Do NOT use physics assets like block, hockey_puck, or car — these are chemistry scenes.
7. If Prerequisites are listed in the curriculum context, weave a brief recap into one event's
   anchor_phrase when the scene depends on prior knowledge (e.g. "recall Rutherford's nucleus").

Return ONLY this JSON shape:
{{
  "scene_id": {scene_id},
  "concept_template": "{template_id}",
  "title": "<specific scene title from curriculum>",
  "anchor_example": "{anchor_example}",
  "content": <object matching CONTENT SCHEMA>,
  "assets": [],
  "events": [
    {{
      "id": "e0",
      "type": "<from ALLOWED EVENTS>",
      "targets": [],
      "anchor_phrase": "<3-7 verbatim words that will appear in narration>",
      "phase": "on",
      "importance": 4
    }}
  ]
}}"""

SEMANTIC_PLAN_PROMPT = """Fill the semantic plan for this scene.

CURRICULUM CONTEXT:
{curriculum_context}
Use the curriculum context as the primary source of truth.
Use textbook terminology whenever available.

{learner_context}

STORYBOARD ENTRY:
{storyboard_entry}

TEMPLATE: {template_id}
TEMPLATE ALLOWED EVENTS: {allowed_events}

AVAILABLE ASSET IDs: {asset_ids}

RULES:
1. Fill the "assets" array using only asset_ids from the AVAILABLE list.
2. Each event "type" must be from ALLOWED EVENTS.
3. Each event "anchor_phrase" must be 3-7 words that will appear VERBATIM
   in the narration script later. Choose clear, descriptive phrases.
4. "phase" must be "before", "on", or "after" (when relative to the phrase).
5. "importance" is 1-5 (5 = most critical, gets longest animation time).
6. instance_id must be unique snake_case (e.g. "puck_a", "ice_surface").
7. Do NOT invent asset_ids — only use those listed.

Return ONLY this JSON shape:
{{
  "scene_id": {scene_id},
  "concept_template": "{template_id}",
  "title": "<short scene title>",
  "anchor_example": "{anchor_example}",
  "assets": [
    {{
      "role": "<slot role matching template>",
      "asset_id": "<from AVAILABLE list>",
      "instance_id": "<unique snake_case>",
      "params": {{<asset-specific params like label, color, direction>}}
    }}
  ],
  "events": [
    {{
      "id": "e0",
      "type": "<from ALLOWED EVENTS>",
      "targets": ["<instance_id>"],
      "anchor_phrase": "<3-7 verbatim words for narration>",
      "phase": "on",
      "importance": 3
    }}
  ]
}}"""


def build_semantic_plan(
    storyboard_entry: dict[str, Any],
    curriculum_context: str = "",
    curriculum_sections: list | None = None,
    learner_profile: dict[str, Any] | None = None,
    topic: str = "",
    subject: str = "Physics",
) -> dict[str, Any]:
    """Generate and validate a semantic plan for one storyboard entry."""
    scene_id = storyboard_entry["scene_id"]
    template_id = storyboard_entry["concept_template"]
    logger.info("Building semantic plan for scene %d (template=%s)", scene_id, template_id)

    template_cls = TEMPLATES.get(template_id)
    if template_cls is None:
        raise ValueError(f"Unknown template '{template_id}'")

    allowed_events = sorted(getattr(template_cls, "ALLOWED_EVENTS", set()))
    asset_ids = sorted(ASSET_REGISTRY.keys())
    anchor_example = storyboard_entry.get("anchor_example", "")
    learner_context = format_learner_context(
        learner_profile, topic or storyboard_entry.get("title", ""), subject
    )
    content_schema = getattr(template_cls, "CONTENT_SCHEMA", None)
    is_explain = template_id in EXPLAIN_TEMPLATE_IDS
    is_chemistry = template_id in CHEMISTRY_TEMPLATE_IDS

    # Build visual metadata block from curriculum sections
    sections_visual_metadata = ""
    if curriculum_sections:
        from modules.retrieval.pageindex_retriever import format_sections_for_prompt
        sections_visual_metadata = format_sections_for_prompt(curriculum_sections)

    # Enrich curriculum context with visual metadata for planners
    enriched_context = curriculum_context
    if sections_visual_metadata:
        enriched_context = f"{sections_visual_metadata}\n\n{curriculum_context}"

    client = NvidiaClient()
    if is_chemistry and content_schema:
        prompt = SEMANTIC_PLAN_CHEMISTRY_PROMPT.format(
            curriculum_context=enriched_context,
            storyboard_entry=json.dumps(storyboard_entry, indent=2),
            template_id=template_id,
            allowed_events=", ".join(allowed_events),
            content_schema=content_schema,
            scene_id=scene_id,
            anchor_example=anchor_example,
            learner_context=learner_context,
        )
    elif is_explain and content_schema:
        prompt = SEMANTIC_PLAN_EXPLAIN_PROMPT.format(
            curriculum_context=enriched_context,
            storyboard_entry=json.dumps(storyboard_entry, indent=2),
            template_id=template_id,
            allowed_events=", ".join(allowed_events),
            content_schema=content_schema,
            scene_id=scene_id,
            anchor_example=anchor_example,
            learner_context=learner_context,
        )
    else:
        prompt = SEMANTIC_PLAN_PROMPT.format(
            curriculum_context=enriched_context,
            storyboard_entry=json.dumps(storyboard_entry, indent=2),
            template_id=template_id,
            allowed_events=", ".join(allowed_events),
            asset_ids=", ".join(asset_ids),
            scene_id=scene_id,
            anchor_example=anchor_example,
            learner_context=learner_context,
        )
    messages = [
        {"role": "system", "content": SEMANTIC_PLAN_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = client.chat_json(NVIDIA_PLANNER_MODEL, messages, temperature=0.3, max_tokens=4096)
    except (json.JSONDecodeError, ValueError) as exc:
        if is_explain:
            logger.warning(
                "Scene %d explain plan JSON failed (%s); using fallback content",
                scene_id, exc,
            )
            raw = _fallback_explain_raw(storyboard_entry, template_id, scene_id)
        else:
            raise
    plan = _validate_plan(
        raw, scene_id, template_id, allowed_events, storyboard_entry=storyboard_entry
    )

    for field in ("subtitle", "key_term", "summary_points", "learning_goal"):
        if field in storyboard_entry and field not in plan:
            plan[field] = storyboard_entry[field]

    plan["_learner_context"] = learner_context

    # Register all assets in the global registry
    registry = get_registry()
    for asset in plan.get("assets", []):
        registry.register(
            instance_id=asset["instance_id"],
            asset_id=asset["asset_id"],
            params=asset.get("params", {}),
            scene_id=scene_id,
        )

    out = PATHS["json"] / f"semantic_plan_{scene_id}.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Semantic plan saved: %s (%d assets, %d events)",
        out, len(plan.get("assets", [])), len(plan.get("events", []))
    )
    return plan


def build_all_semantic_plans(
    storyboard: list[dict[str, Any]],
    curriculum_context: str = "",
    curriculum_sections: list | None = None,
    learner_profile: dict[str, Any] | None = None,
    topic: str = "",
    subject: str = "Physics",
) -> list[dict[str, Any]]:
    return [
        build_semantic_plan(
            entry,
            curriculum_context=curriculum_context,
            curriculum_sections=curriculum_sections,
            learner_profile=learner_profile,
            topic=topic,
            subject=subject,
        )
        for entry in storyboard
    ]


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------


def _fallback_explain_raw(
    storyboard_entry: dict[str, Any],
    template_id: str,
    scene_id: int,
) -> dict[str, Any]:
    """Deterministic plan when LLM JSON is invalid (e.g. LaTeX backslashes)."""
    base = {
        "scene_id": scene_id,
        "concept_template": template_id,
        "title": storyboard_entry.get("title", f"Scene {scene_id}"),
        "anchor_example": storyboard_entry.get("anchor_example", ""),
        "learning_goal": storyboard_entry.get("learning_goal", ""),
        "assets": [],
        "content": merge_content(storyboard_entry, template_id),
        "events": [
            {
                "id": "e0",
                "type": "place_title",
                "targets": [],
                "anchor_phrase": "let us begin",
                "phase": "on",
                "importance": 3,
            },
            {
                "id": "e1",
                "type": "reveal",
                "targets": [],
                "anchor_phrase": "the key idea",
                "phase": "on",
                "importance": 4,
            },
            {
                "id": "e2",
                "type": "hold",
                "targets": [],
                "anchor_phrase": "in summary",
                "phase": "on",
                "importance": 2,
            },
        ],
    }
    return base


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_plan(
    raw: Any,
    scene_id: int,
    template_id: str,
    allowed_events: list[str],
    storyboard_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Semantic plan must be a dict, got {type(raw)}")

    # Normalise scene_id
    plan = dict(raw)
    plan["scene_id"] = scene_id
    plan["concept_template"] = template_id

    # Validate assets
    assets = plan.get("assets", [])
    if not isinstance(assets, list):
        plan["assets"] = []
        assets = []

    seen_instances: set[str] = set()
    valid_assets = []
    for asset in assets:
        asset_id = asset.get("asset_id", "")
        if asset_id not in ASSET_REGISTRY:
            logger.warning("Dropping asset with unknown asset_id '%s'", asset_id)
            continue
        iid = str(asset.get("instance_id", f"{asset_id}_{scene_id}"))
        if iid in seen_instances:
            iid = f"{iid}_{len(seen_instances)}"
        seen_instances.add(iid)
        valid_assets.append({
            "role": str(asset.get("role", asset_id)),
            "asset_id": asset_id,
            "instance_id": iid,
            "params": dict(asset.get("params", {})),
        })
    plan["assets"] = valid_assets

    # Validate events
    events = plan.get("events", [])
    if not isinstance(events, list):
        plan["events"] = []
        events = []

    valid_events = []
    for i, ev in enumerate(events):
        etype = str(ev.get("type", ""))
        if allowed_events and etype not in allowed_events:
            logger.warning(
                "Scene %d event '%s' has invalid type '%s' (allowed: %s); dropping",
                scene_id, ev.get("id", i), etype, allowed_events
            )
            continue
        valid_events.append({
            "id": str(ev.get("id", f"e{i}")),
            "type": etype,
            "targets": list(ev.get("targets", [])),
            "anchor_phrase": str(ev.get("anchor_phrase", "")),
            "phase": str(ev.get("phase", "on")),
            "importance": max(1, min(5, int(ev.get("importance", 3)))),
        })
    plan["events"] = valid_events

    # Ensure title
    if "title" not in plan or not plan["title"]:
        plan["title"] = str(raw.get("anchor_example", f"Scene {scene_id}"))

    if template_id in EXPLAIN_TEMPLATE_IDS:
        plan["assets"] = []
        base_entry = dict(storyboard_entry or {})
        base_entry.update({
            "title": plan.get("title", base_entry.get("title", "")),
            "learning_goal": plan.get("learning_goal", base_entry.get("learning_goal", "")),
            "anchor_example": plan.get("anchor_example", base_entry.get("anchor_example", "")),
        })
        if isinstance(plan.get("content"), dict):
            base_entry["content"] = plan["content"]
        plan["content"] = merge_content(base_entry, template_id)

    elif template_id in CHEMISTRY_TEMPLATE_IDS:
        # Chemistry templates never use physics assets; preserve LLM-filled content dict.
        plan["assets"] = []
        if not isinstance(plan.get("content"), dict):
            plan["content"] = {}

    return plan
