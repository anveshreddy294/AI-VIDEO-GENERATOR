"""Generate Scene JSON master plan via NVIDIA NIM."""

from __future__ import annotations

import json
from typing import Any

from modules.config import NVIDIA_PLANNER_MODEL, PATHS, get_logger
from modules.llm.nvidia_client import NvidiaClient

logger = get_logger(__name__)

SCENE_JSON_SYSTEM = """You are an expert educational video scriptwriter.
You create structured scene plans for animated explainer videos.
NEVER include timing, duration, run_time, or seconds in your output.
Respond ONLY with a JSON array. No prose, no markdown fences."""

SCENE_JSON_PROMPT = """Create an educational video plan for this topic: {topic}

REQUIREMENTS:
- Create EXACTLY 5 scenes that build progressively (intro -> 3 mid -> outro)
- Each scene narration: 35-55 words, conversational and clear
- Each scene must have EXACTLY 3 beats
- Each beat.phrase MUST be a verbatim contiguous substring of narration (3-8 words)
- The 3 beats together should cover the narration in order
- beats[i].visual describes what to show DURING that phrase
- Match the language of the topic
- NO timing fields anywhere (no run_time, duration, seconds)

OUTPUT: A JSON array. Each element:
{{
  "scene_id": 1,
  "concept": "short concept name",
  "anchor_example": "concrete real-world example",
  "narration": "spoken text, 40-70 words",
  "visual_instruction": "high-level visual direction for the whole scene",
  "beats": [
    {{"phrase": "exact words from narration", "visual": "what to animate"}}
  ]
}}

Return ONLY the JSON array."""


def build_scene_plan(topic: str) -> list[dict[str, Any]]:
    """Generate Scene JSON array from a user topic via NVIDIA NIM."""
    logger.info("Building scene plan for topic: %s", topic)
    client = NvidiaClient()
    prompt = SCENE_JSON_PROMPT.format(topic=topic)
    messages = [
        {"role": "system", "content": SCENE_JSON_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    scenes = client.chat_json(
        NVIDIA_PLANNER_MODEL, messages, temperature=0.4, max_tokens=8192
    )

    if isinstance(scenes, dict) and "scenes" in scenes:
        scenes = scenes["scenes"]
    if not isinstance(scenes, list):
        raise ValueError(f"Expected list of scenes, got {type(scenes)}")

    validated = [_validate_scene(s, idx) for idx, s in enumerate(scenes, start=1)]
    out_path = PATHS["json"] / "scenes.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)
    logger.info("Scene plan saved to %s (%d scenes)", out_path, len(validated))
    return validated


def _validate_scene(scene: dict[str, Any], default_id: int) -> dict[str, Any]:
    """Validate and normalize a single scene dict."""
    forbidden = {"run_time", "duration", "seconds", "timing", "start", "end"}
    for key in scene:
        if key.lower() in forbidden:
            raise ValueError(f"Scene contains forbidden timing field: {key}")

    scene_id = scene.get("scene_id", default_id)
    required = ["concept", "anchor_example", "narration", "visual_instruction", "beats"]
    for field in required:
        if field not in scene:
            raise ValueError(f"Scene {scene_id} missing required field: {field}")

    beats = scene["beats"]
    if not isinstance(beats, list) or len(beats) < 1:
        raise ValueError(f"Scene {scene_id} must have at least one beat")

    for beat in beats:
        if "phrase" not in beat or "visual" not in beat:
            raise ValueError(f"Beat in scene {scene_id} missing phrase or visual")
        for key in beat:
            if key.lower() in forbidden:
                raise ValueError(f"Beat contains forbidden timing field: {key}")

    return {
        "scene_id": scene_id,
        "concept": scene["concept"],
        "anchor_example": scene["anchor_example"],
        "narration": scene["narration"],
        "visual_instruction": scene["visual_instruction"],
        "beats": beats,
    }
