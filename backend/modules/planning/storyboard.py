"""Storyboard planner: generates the conceptual arc for a topic.

Outputs an ordered list of 5 scenes, each with a concept_template and
anchor_example, forming a progressive educational narrative:
  Scene 1: intro (overview + key term)
  Scenes 2-4: core concept templates (mechanics)
  Scene 5: summary

Scene 2-4 templates and anchor examples MUST all differ — enforced both via
prompt rules and post-validation that rewrites duplicates to "freeform".
"""
from __future__ import annotations

import json
from typing import Any

from modules.config import NVIDIA_PLANNER_MODEL, PATHS, get_logger
from modules.llm.nvidia_client import NvidiaClient
from modules.planning.profile_context import format_learner_context
from modules.templates import (
    EXPLAIN_TEMPLATE_IDS,
    MECHANICS_TEMPLATE_IDS,
    VALID_TEMPLATE_IDS,
)
from modules.planning.chemistry_router import (
    CHEMISTRY_TEMPLATE_IDS,
    route_chemistry_template,
)
from modules.retrieval.pageindex_retriever import (
    format_prerequisites_for_prompt,
    format_sections_for_prompt,
)

logger = get_logger(__name__)

STORYBOARD_SYSTEM = """You are an expert educational video director.
You design 5-scene progressive lesson arcs that teach a topic through DISTINCT, varied examples.
NEVER include run_time, duration, seconds, or timing fields.
Respond ONLY with a valid JSON array. No markdown fences, no commentary."""

STORYBOARD_PROMPT = """Design a 5-scene educational video arc for this topic: {topic}

CURRICULUM CONTEXT:
{curriculum_context}

{prerequisite_block}

IMPORTANT:

- Use the curriculum context as the PRIMARY source of truth.

- Base scene titles, examples, explanations, formulas, and learning goals on the curriculum context whenever possible.

- Do not invent concepts that are not supported by the curriculum context.

- If prerequisite topics are listed above, order scenes so prerequisites are taught BEFORE dependent concepts
  (e.g. explain Rutherford scattering before Bohr's model; discharge tube experiments before atomic models).
  When a scene builds on a prerequisite, reference that prior concept briefly in the scene title or learning_goal.

- If the curriculum context is empty, fall back to general educational knowledge.
{learner_context}

TEMPLATE FAMILIES — pick the best family per scene:

A) PHYSICS SIMULATION (animated motion on chalkboard) — use when the scene shows a physical
   process, forces, or motion that is best taught with moving objects:
   {mechanics_list}

B) CHALKBOARD EXPLANATION (conceptual layouts, no physics assets) — use when the scene is
   about ideas, definitions, formulas, comparisons, or structure:
   - concept_card: break a concept into 2-4 labeled parts/cards
   - comparison: contrast two ideas side-by-side (e.g. scalar vs vector, static vs kinetic)
   - equation: present or derive a key formula with a short explanation
   - timeline: ordered steps, history, or procedure (3-5 labels on a timeline)
   - diagram: relationships between parts (nodes in a flow or system)

C) CHEMISTRY (animated atomic / molecular / reaction visuals) — use ONLY when the topic is
   chemistry. These templates render proper nucleus Dot clusters, concentric orbit Circles,
   electron transfer animations, and periodic table grids — never cubes or generic rectangles
   for subatomic particles:
   - atomic_structure: Bohr / Rutherford / Thomson atomic models, electron shells, element badge
   - periodic_trends: periodic table grid with trend arrows (atomic radius, electronegativity, etc.)
   - ionic_bonding: electron dot transfer from donor to acceptor atom with charge labels
   - covalent_bonding: shared electron pair between atoms with bond order labels
   - molecular_geometry: VSEPR molecule shape with bond angles
   - chemical_equilibrium: forward/reverse reaction arrows with Le Chatelier stress animation
   - acid_base: proton transfer with pH scale and indicator color change
   - reaction_energy: energy profile diagram (activation energy, exo/endo annotations)

D) FALLBACK: freeform — only if no other family fits.

Also available: intro (scene 1 only), summary (scene 5 only).

SELECTION GUIDANCE:
- For chemistry topics, ALWAYS prefer family C templates over generic explanation (B) or freeform (D).
- Mix families across scenes 2-4: e.g. for atomic structure → atomic_structure (visual) + equation (formal) + timeline (history).
- Prefer simulation (A) when motion/forces are central; prefer explanation (B) for formulas and contrasts.
- If NO template fits, use "freeform".

PEDAGOGICAL SCENE ROLES — every scene must have a scene_role from this ordered arc:
  Scene 1: "hook"           — introduce the topic with a surprising fact or relatable analogy
  Scene 2: "visual_intuition" — show the key visual / phenomenon intuitively
  Scene 3: "formal_concept"  — present the formal definition, equation, or model
  Scene 4: "worked_example"  — apply the concept to a concrete example or calculation
  Scene 5: "summary"         — consolidate learning with 3 key takeaways

REQUIREMENTS:
- Scene 1: always use "intro" template, scene_role "hook"
- Scene 5: always use "summary" template, scene_role "summary"
- Scenes 2-4: choose from families A/B/C/D; use scene_roles visual_intuition/formal_concept/worked_example in that order.
- Scenes 2, 3, and 4 MUST have THREE DIFFERENT concept_templates AND THREE DIFFERENT anchor_examples.
- Each scene's learning_goal must be a unique sentence.
- anchor_example: a concrete real-world object, scenario, or numerical setup, different per scene.
- subtitle (scene 1 only): short tagline for the intro
- key_term (scene 1 only): the central term to highlight
- summary_points (scene 5 only): list of 3 key takeaways

Return a JSON array of exactly 5 objects:
[
  {{
    "scene_id": 1,
    "concept_template": "intro",
    "scene_role": "hook",
    "title": "<topic> — Overview",
    "anchor_example": "<short hook>",
    "learning_goal": "introduce the concept",
    "subtitle": "<one-line tagline>",
    "key_term": "<central term>"
  }},
  {{
    "scene_id": 2,
    "concept_template": "<one of: {template_ids}>",
    "scene_role": "visual_intuition",
    "title": "...",
    "anchor_example": "<DISTINCT scenario A>",
    "learning_goal": "<unique goal A>"
  }},
  {{
    "scene_id": 3,
    "concept_template": "<DIFFERENT template>",
    "scene_role": "formal_concept",
    "title": "...",
    "anchor_example": "<DISTINCT scenario B>",
    "learning_goal": "<unique goal B>"
  }},
  {{
    "scene_id": 4,
    "concept_template": "<DIFFERENT template>",
    "scene_role": "worked_example",
    "title": "...",
    "anchor_example": "<DISTINCT scenario C>",
    "learning_goal": "<unique goal C>"
  }},
  {{
    "scene_id": 5,
    "concept_template": "summary",
    "scene_role": "summary",
    "title": "Key Takeaways",
    "anchor_example": "all scenarios",
    "learning_goal": "consolidate learning",
    "summary_points": ["...", "...", "..."]
  }}
]

Return ONLY the JSON array."""


def _build_curriculum_anchor(curriculum_context: str, curriculum_sections: list | None) -> str:
    """Prepend a rich visual metadata block for tighter LLM alignment.

    Uses format_sections_for_prompt to include semantic_tags,
    visualizable_elements, and prerequisites so the LLM can select
    chemistry-appropriate templates and order scenes pedagogically.
    """
    if not curriculum_sections:
        return curriculum_context
    visual_block = format_sections_for_prompt(curriculum_sections)
    prereq_block = format_prerequisites_for_prompt(curriculum_sections)
    parts = [visual_block]
    if prereq_block:
        parts.append(prereq_block)
    header = "\n\n".join(parts)
    if curriculum_context:
        return f"{header}\n\nDETAILED CONTEXT:\n{curriculum_context}"
    return header


def build_storyboard(
    topic: str,
    curriculum_context: str = "",
    curriculum_sections: list | None = None,
    learner_profile: dict[str, Any] | None = None,
    subject: str = "Physics",
) -> list[dict[str, Any]]:
    """Generate a 5-scene storyboard arc for the given topic."""
    logger.info("Building storyboard for topic: %s", topic)
    client = NvidiaClient()

    enriched_context = _build_curriculum_anchor(curriculum_context, curriculum_sections)
    prerequisite_block = format_prerequisites_for_prompt(curriculum_sections or [])
    if not prerequisite_block:
        prerequisite_block = "(No prerequisite ordering data available.)"

    mechanics_middle = [
        t for t in MECHANICS_TEMPLATE_IDS if t not in ("intro", "summary")
    ]
    mechanics_list = "\n".join(f"   - {t}" for t in mechanics_middle)
    explain_list = "\n".join(f"   - {t}" for t in EXPLAIN_TEMPLATE_IDS)
    template_ids = ", ".join(
        mechanics_middle + EXPLAIN_TEMPLATE_IDS + CHEMISTRY_TEMPLATE_IDS + ["freeform"]
    )
    learner_context = format_learner_context(learner_profile, topic, subject)
    prompt = STORYBOARD_PROMPT.format(
        topic=topic,
        curriculum_context=enriched_context,
        prerequisite_block=prerequisite_block,
        learner_context=learner_context,
        mechanics_list=mechanics_list,
        explain_list=explain_list,
        template_ids=template_ids,
    )
    messages = [
        {"role": "system", "content": STORYBOARD_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    raw = client.chat_json(NVIDIA_PLANNER_MODEL, messages, temperature=0.55, max_tokens=4096)

    if isinstance(raw, dict) and "scenes" in raw:
        raw = raw["scenes"]
    if not isinstance(raw, list):
        raise ValueError(f"Storyboard LLM returned {type(raw)}, expected list")

    validated = [
        _validate_entry(entry, idx, topic=topic, curriculum_sections=curriculum_sections)
        for idx, entry in enumerate(raw, start=1)
    ]
    validated[0]["concept_template"] = "intro"
    validated[0]["scene_role"] = "hook"
    validated[-1]["concept_template"] = "summary"
    validated[-1]["scene_role"] = "summary"
    validated = _enforce_scene_roles(validated)
    validated = _enforce_distinct_middle(validated)

    out = PATHS["json"] / "storyboard.json"
    out.write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Storyboard saved: %s (%d scenes)", out, len(validated))
    return validated


_VALID_SCENE_ROLES = frozenset({
    "hook", "visual_intuition", "formal_concept", "worked_example", "summary",
})

_MIDDLE_ROLE_ORDER = ["visual_intuition", "formal_concept", "worked_example"]


def _validate_entry(
    entry: dict[str, Any],
    default_id: int,
    topic: str = "",
    curriculum_sections: list | None = None,
) -> dict[str, Any]:
    scene_id = int(entry.get("scene_id", default_id))
    template = str(entry.get("concept_template", "intro"))

    # Accept chemistry templates even if not in VALID_TEMPLATE_IDS yet (registered later)
    all_known = set(VALID_TEMPLATE_IDS) | set(CHEMISTRY_TEMPLATE_IDS)
    if template not in all_known:
        logger.warning(
            "Scene %d has unknown template '%s'; falling back to 'freeform'",
            scene_id, template,
        )
        template = "freeform"

    # Chemistry router override: if topic/tags suggest chemistry and template is generic,
    # replace with the most appropriate chemistry template.
    scene_role = str(entry.get("scene_role", ""))
    if template not in ("intro", "summary") and template not in CHEMISTRY_TEMPLATE_IDS:
        top_section = (curriculum_sections or [{}])[0] if curriculum_sections else {}
        chem_override = route_chemistry_template(
            topic=topic,
            scene_role=scene_role,
            semantic_tags=top_section.get("semantic_tags", []),
            visualizable_elements=top_section.get("visualizable_elements", []),
        )
        if chem_override:
            logger.info(
                "Scene %d: chemistry router overrides template '%s' → '%s'",
                scene_id, template, chem_override,
            )
            template = chem_override

    result: dict[str, Any] = {
        "scene_id": scene_id,
        "concept_template": template,
        "title": str(entry.get("title", entry.get("anchor_example", f"Scene {scene_id}"))),
        "anchor_example": str(entry.get("anchor_example", "")),
        "learning_goal": str(entry.get("learning_goal", "")),
    }

    # Preserve scene_role if LLM provided a valid one
    if scene_role in _VALID_SCENE_ROLES:
        result["scene_role"] = scene_role

    if "subtitle" in entry:
        result["subtitle"] = str(entry["subtitle"])
    if "key_term" in entry:
        result["key_term"] = str(entry["key_term"])
    if "summary_points" in entry and isinstance(entry["summary_points"], list):
        result["summary_points"] = [str(p) for p in entry["summary_points"][:4]]
    return result


def _enforce_scene_roles(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enforce pedagogical role ordering.

    Scene 1 → hook, scene 5 → summary.
    Scenes 2–4 must be visual_intuition, formal_concept, worked_example in that order.
    """
    if not scenes:
        return scenes
    scenes[0]["scene_role"] = "hook"
    if len(scenes) >= 5:
        scenes[-1]["scene_role"] = "summary"
    for i, scene in enumerate(scenes[1:-1], start=0):
        assigned = scene.get("scene_role", "")
        if assigned not in _VALID_SCENE_ROLES or assigned in ("hook", "summary"):
            scene["scene_role"] = _MIDDLE_ROLE_ORDER[i] if i < len(_MIDDLE_ROLE_ORDER) else "formal_concept"
    return scenes


def _enforce_distinct_middle(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure scenes 2-4 have distinct templates AND distinct anchor examples.

    Duplicates are rewritten to use the freeform template so the LLM generates
    a unique visual for that scene instead of replaying the same animation.
    """
    seen_templates: set[str] = set()
    seen_anchors: set[str] = set()
    for s in scenes[1:-1]:
        tpl = s.get("concept_template", "freeform")
        anchor_key = s.get("anchor_example", "").strip().lower()
        if tpl in seen_templates or tpl in ("intro", "summary"):
            logger.warning(
                "Scene %d duplicated template '%s'; rewriting to 'freeform'",
                s["scene_id"], tpl,
            )
            s["concept_template"] = "freeform"
            tpl = "freeform"
        seen_templates.add(tpl)
        if anchor_key and anchor_key in seen_anchors:
            logger.warning(
                "Scene %d duplicated anchor_example '%s'; rewriting to freeform",
                s["scene_id"], anchor_key,
            )
            s["concept_template"] = "freeform"
            s["anchor_example"] = f"{s['anchor_example']} (alternate framing)"
        seen_anchors.add(s.get("anchor_example", "").strip().lower())
    return scenes
