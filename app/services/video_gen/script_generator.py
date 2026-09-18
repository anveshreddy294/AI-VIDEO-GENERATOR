"""Targeted video script generation service for Step 3.

Transforms diagnostic VideoTargets into pedagogically structured, timed,
multi-scene scripts grounded strictly in authoritative source ContentUnits.
"""

import json
import logging
import re
import uuid
from typing import List, Optional

from ...core.config import settings
from ...services.assessment.providers import LLMProvider, get_default_provider
from ...services.assessment.schemas import VideoTarget
from ...services.registry import get_content_units
from ...services.schemas import ContentUnit
from .schemas import VideoScene, VideoScript

logger = logging.getLogger(__name__)

# Target word-per-second speaking rate (moderate, clear instructional pace)
WORDS_PER_SECOND = 2.4


def _clean_json_markdown(text: str) -> str:
    """Strip markdown code fence blocks if returned by the LLM."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


def _sanitize_text(text: Optional[str]) -> str:
    """Remove raw bracketed image/OCR tags and vision API error placeholders."""
    if not text:
        return ""
    cleaned = re.sub(r"\[IMAGE:[^\]]*\]", "", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"\[No description[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[warn[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _clean_source_text(raw_text: str) -> str:
    """Strip OCR placeholders, image tags, and vision failure notices."""
    if not raw_text:
        return ""
    lines = []
    for line in raw_text.splitlines():
        line_clean = _sanitize_text(line)
        if line_clean and "no description returned" not in line_clean.lower():
            lines.append(line_clean)
    return "\n".join(lines)


def _extract_source_context(source_id: str, target: VideoTarget) -> tuple[str, Optional[str]]:
    """Retrieve grounded text snippets and identify any diagram ContentUnit ID."""
    all_units: List[ContentUnit] = get_content_units(source_id)
    grounded_texts: List[str] = []
    diagram_cu_id: Optional[str] = None

    target_cu_ids = set(target.source_content_ids or [])

    for unit in all_units:
        # Match either explicit CU ID or if concept name is strongly present
        is_relevant = (
            unit.content_id in target_cu_ids
            or (target.concept_name.lower() in unit.text.lower())
        )
        if is_relevant:
            cleaned = _clean_source_text(unit.text)
            if cleaned:
                grounded_texts.append(cleaned)
            # Check if this unit is a diagram or visual
            if unit.modality in ["image", "video"] or getattr(unit, "image_path", None):
                if not diagram_cu_id:
                    diagram_cu_id = unit.content_id

    # Fallback to general units if no specific matches found
    if not grounded_texts and all_units:
        for u in all_units[:3]:
            cleaned = _clean_source_text(u.text)
            if cleaned:
                grounded_texts.append(cleaned)

    combined_text = "\n\n".join(grounded_texts[:5])
    return combined_text, diagram_cu_id


def _get_domain_defaults(concept: str) -> tuple[str, str, str]:
    """Provide clean, authoritative definitions and mastery rules if source lacks text."""
    c_lower = concept.lower()
    if "acceleration" in c_lower:
        defn = "Acceleration is the rate of change of an object's velocity over time."
        detail = "It occurs whenever an object speeds up, slows down, or changes its direction of travel."
        rule = "a = Δv / Δt  (Rate of velocity change)"
    elif "force" in c_lower:
        defn = "Force is an interaction that alters the state of motion of an object."
        detail = "Newton's Second Law establishes that net force directly equals mass times acceleration."
        rule = "F = m · a  (Force = Mass × Acceleration)"
    elif "inertia" in c_lower:
        defn = "Inertia is the natural resistance of any physical object to changes in its state of motion."
        detail = "An object at rest stays at rest, and an object in motion stays in uniform motion unless acted on."
        rule = "Inertia is directly proportional to mass"
    elif "momentum" in c_lower:
        defn = "Momentum represents the quantity of motion possessed by a moving body."
        detail = "In any closed or isolated system, total linear momentum is strictly conserved across interactions."
        rule = "p = m · v  (Conservation of Momentum)"
    elif "energy" in c_lower or "work" in c_lower:
        defn = "Energy is the quantitative property transferred to an object to perform work or heat it."
        detail = "Mechanical energy transitions continuously between kinetic energy of motion and stored potential energy."
        rule = "E_total = K + U  (Conservation of Energy)"
    else:
        defn = f"{concept} represents a fundamental conceptual pillar governing relationships in this domain."
        detail = f"Mastering how {concept} behaves under varying conditions is critical for accurate problem-solving."
        rule = f"Core Mastery Principle: Check governing conditions for {concept}"
    return defn, detail, rule


def _generate_deterministic_script(
    target: VideoTarget,
    student_id: str,
    source_id: str,
    source_text: str,
    diagram_cu_id: Optional[str],
) -> VideoScript:
    """Generate a high-quality, pedagogically sound fallback script without LLM."""
    duration = target.target_seconds
    concept = target.concept_name
    difficulty = target.difficulty

    # Extract clean sentences from source text
    clean_text = _clean_source_text(source_text)
    raw_sentences = [s.strip() for s in re.split(r"[.!?]\s+", clean_text) if len(s.strip()) > 15]
    valid_sentences = [
        s for s in raw_sentences
        if not s.startswith("[") and "no description" not in s.lower() and "image:" not in s.lower()
    ]

    default_def, default_detail, default_rule = _get_domain_defaults(concept)

    def_sentence = valid_sentences[0] if valid_sentences else default_def
    detail_sentence = valid_sentences[1] if len(valid_sentences) > 1 else default_detail
    highlight_rule = default_rule

    scenes: List[VideoScene] = []

    if duration <= 30:
        # 30-second Foundational Script: 3 Scenes (6s, 18s, 6s)
        scenes = [
            VideoScene(
                scene_number=1,
                scene_type="title_hook",
                title=f"Understanding {concept}",
                narration=f"Let's master {concept}. This core idea forms the foundation of what you are studying.",
                onscreen_bullets=[f"Core Concept: {concept}", "Foundational Review"],
                highlight_text=highlight_rule,
                duration_seconds=6.0,
            ),
            VideoScene(
                scene_number=2,
                scene_type="concept_breakdown",
                title="The Core Principle",
                narration=f"Notice that {def_sentence} {detail_sentence}",
                onscreen_bullets=["Key Definition", "Core Relationship", "Common Application"],
                highlight_text=highlight_rule,
                diagram_cu_id=diagram_cu_id,
                duration_seconds=18.0,
            ),
            VideoScene(
                scene_number=3,
                scene_type="summary_takeaway",
                title="Key Takeaway",
                narration=f"Remember: always identify the core relationship in {concept} before solving.",
                onscreen_bullets=["Always check core conditions", "Apply directly in quizzes"],
                highlight_text=highlight_rule,
                duration_seconds=6.0,
            ),
        ]
    elif duration <= 45:
        # 45-second Intermediate Script: 4 Scenes (7s, 20s, 11s, 7s)
        scenes = [
            VideoScene(
                scene_number=1,
                scene_type="title_hook",
                title=f"Mastering {concept}",
                narration=f"Welcome back. In this targeted session, we're dissecting {concept} step-by-step.",
                onscreen_bullets=[f"Target: {concept}", "Intermediate Remediation"],
                highlight_text=highlight_rule,
                duration_seconds=7.0,
            ),
            VideoScene(
                scene_number=2,
                scene_type="concept_breakdown",
                title="The Underlying Mechanism",
                narration=f"According to the study material, {def_sentence} This explains why the variables behave consistently.",
                onscreen_bullets=["Primary Mechanism", "Authoritative Rule", "Governing Equation"],
                highlight_text=highlight_rule,
                diagram_cu_id=diagram_cu_id,
                duration_seconds=20.0,
            ),
            VideoScene(
                scene_number=3,
                scene_type="formula_derivation" if "law" in concept.lower() or "formula" in source_text.lower() else "concept_breakdown",
                title="How to Apply It",
                narration=f"When encountering questions on this, check the boundary conditions carefully: {detail_sentence}",
                onscreen_bullets=["Step 1: Check Assumptions", "Step 2: Apply the Relationship"],
                highlight_text=highlight_rule,
                duration_seconds=11.0,
            ),
            VideoScene(
                scene_number=4,
                scene_type="summary_takeaway",
                title="Summary & Next Steps",
                narration=f"That's {concept} in a nutshell. Keep these principles in mind for your next assessment.",
                onscreen_bullets=["Clear definition locked in", "Ready for re-testing"],
                highlight_text=highlight_rule,
                duration_seconds=7.0,
            ),
        ]
    else:
        # 60-second Advanced Script: 5 Scenes (8s, 20s, 18s, 8s, 6s)
        scenes = [
            VideoScene(
                scene_number=1,
                scene_type="title_hook",
                title=f"Advanced Deep-Dive: {concept}",
                narration=f"Let's tackle advanced concepts in {concept}. We'll bridge the gap from intuition to formal mastery.",
                onscreen_bullets=[f"Advanced Focus: {concept}", "Prerequisite Gap Closure"],
                highlight_text=concept,
                duration_seconds=8.0,
            ),
            VideoScene(
                scene_number=2,
                scene_type="concept_breakdown",
                title="Theoretical Framework",
                narration=f"Fundamentally, {def_sentence}. Understanding this formal framework prevents common conceptual errors.",
                onscreen_bullets=["Formal Definition", "Theoretical Constraints"],
                highlight_text=def_sentence[:80] + "..." if len(def_sentence) > 80 else def_sentence,
                diagram_cu_id=diagram_cu_id,
                duration_seconds=20.0,
            ),
            VideoScene(
                scene_number=3,
                scene_type="diagram_focus" if diagram_cu_id else "concept_breakdown",
                title="Step-by-Step Analysis",
                narration=f"Examining the details closely: {detail_sentence}. Every parameter directly influences the final outcome.",
                onscreen_bullets=["Critical Factors", "Inter-concept Dependencies"],
                highlight_text="Detailed Analysis",
                diagram_cu_id=diagram_cu_id,
                duration_seconds=18.0,
            ),
            VideoScene(
                scene_number=4,
                scene_type="formula_derivation",
                title="Avoiding the Pitfall",
                narration="The most frequent mistake here is skipping the prerequisite relationship. Verify all conditions first.",
                onscreen_bullets=["Common Mistake Identified", "Correct Analytical Path"],
                highlight_text="Check Assumptions",
                duration_seconds=8.0,
            ),
            VideoScene(
                scene_number=5,
                scene_type="summary_takeaway",
                title="Final Summary",
                narration=f"You now have the tools to solve advanced problems involving {concept}.",
                onscreen_bullets=["Comprehensive Understanding", "Assessment Ready"],
                highlight_text="Concept Solidified",
                duration_seconds=6.0,
            ),
        ]

    total_words = sum(len(scene.narration.split()) for scene in scenes)
    video_id = f"VID_{uuid.uuid4().hex[:12]}"

    return VideoScript(
        video_id=video_id,
        student_id=student_id,
        source_id=source_id,
        concept_id=target.concept_id,
        concept_name=target.concept_name,
        difficulty=difficulty,
        target_total_seconds=duration,
        scenes=scenes,
        estimated_word_count=total_words,
        source_chunk_ids=target.chunk_ids or [],
    )


def generate_video_script(
    target: VideoTarget,
    student_id: str,
    source_id: str,
    provider: Optional[LLMProvider] = None,
) -> VideoScript:
    """Generate a structured, timed VideoScript for the given remediation target."""
    source_text, diagram_cu_id = _extract_source_context(source_id, target)
    target_seconds = target.target_seconds
    max_words = int(target_seconds * WORDS_PER_SECOND)

    if provider is None:
        try:
            provider = get_default_provider()
        except Exception:
            provider = None

    if provider is not None and not getattr(provider, "is_mock", False):
        prompt = f"""You are an expert educational video scriptwriter and instructional designer.
Create a structured, multi-scene video script to remediate a student who failed a diagnostic quiz on '{target.concept_name}'.

TARGET CONSTRAINTS:
- Concept Name: {target.concept_name}
- Concept Difficulty: {target.difficulty}
- Total Target Duration: Exactly {target_seconds} seconds.
- Total Word Budget: Approximately {max_words} words across all scenes (do NOT exceed {max_words + 15} words).
- Speaking Speed: ~2.4 words per second.

AUTHORITATIVE SOURCE TEXT (Ground all explanations strictly in this text):
\"\"\"{source_text[:2000]}\"\"\"

PEDAGOGICAL STRUCTURE (3-Act Micro-Lesson):
1. Act 1 (Hook/Context): Announce the concept clearly and state why it matters.
2. Act 2 (Breakdown/Evidence): Explain the principle step-by-step from the source text.
3. Act 3 (Takeaway): State the memorable rule or formula to prevent quiz mistakes.

Respond ONLY with a valid JSON object adhering to this exact schema:
{{
  "scenes": [
    {{
      "scene_number": 1,
      "scene_type": "title_hook",
      "title": "On-screen short title (max 50 chars)",
      "narration": "Spoken voiceover text for this scene",
      "onscreen_bullets": ["Bullet 1", "Bullet 2"],
      "highlight_text": "Key rule or formula",
      "duration_seconds": 6.0
    }}
  ]
}}
Ensure the sum of all 'duration_seconds' exactly equals {target_seconds}.0 seconds."""

        try:
            raw_response = provider.generate_content(prompt)
            clean_json = _clean_json_markdown(raw_response)
            data = json.loads(clean_json)

            scenes_data = data.get("scenes", [])
            parsed_scenes: List[VideoScene] = []

            SCENE_TYPE_MAP = {
                "breakdown": "concept_breakdown",
                "concept": "concept_breakdown",
                "intro": "title_hook",
                "hook": "title_hook",
                "title": "title_hook",
                "summary": "summary_takeaway",
                "takeaway": "summary_takeaway",
                "conclusion": "summary_takeaway",
                "formula": "formula_derivation",
                "derivation": "formula_derivation",
                "diagram": "diagram_focus",
                "visual": "diagram_focus",
            }
            VALID_SCENE_TYPES = {
                "title_hook", "concept_breakdown", "diagram_focus", "formula_derivation", "summary_takeaway"
            }
            _, _, default_rule = _get_domain_defaults(target.concept_name)

            for s in scenes_data:
                raw_st = str(s.get("scene_type", "concept_breakdown")).strip().lower()
                stype = SCENE_TYPE_MAP.get(raw_st, raw_st)
                if stype not in VALID_SCENE_TYPES:
                    stype = "concept_breakdown"

                hl_raw = s.get("highlight_text")
                hl_clean = _sanitize_text(hl_raw) if hl_raw else None
                if not hl_clean and stype == "formula_derivation":
                    hl_clean = default_rule

                bullets = [_sanitize_text(str(b)) for b in s.get("onscreen_bullets", [])]
                bullets = [b for b in bullets if b][:5]

                scene = VideoScene(
                    scene_number=int(s.get("scene_number", len(parsed_scenes) + 1)),
                    scene_type=stype,
                    title=_sanitize_text(str(s.get("title", target.concept_name)))[:100] or target.concept_name,
                    narration=_sanitize_text(str(s.get("narration", ""))),
                    onscreen_bullets=bullets,
                    highlight_text=hl_clean,
                    diagram_cu_id=diagram_cu_id,
                    duration_seconds=float(s.get("duration_seconds", target_seconds / max(1, len(scenes_data)))),
                )
                parsed_scenes.append(scene)

            if parsed_scenes:
                # Re-normalize durations so they sum to target_seconds
                current_sum = sum(sc.duration_seconds for sc in parsed_scenes)
                if abs(current_sum - target_seconds) > 0.5:
                    ratio = target_seconds / max(0.1, current_sum)
                    for sc in parsed_scenes:
                        sc.duration_seconds = round(sc.duration_seconds * ratio, 1)

                total_words = sum(len(sc.narration.split()) for sc in parsed_scenes)
                video_id = f"VID_{uuid.uuid4().hex[:12]}"

                return VideoScript(
                    video_id=video_id,
                    student_id=student_id,
                    source_id=source_id,
                    concept_id=target.concept_id,
                    concept_name=target.concept_name,
                    difficulty=target.difficulty,
                    target_total_seconds=target_seconds,
                    scenes=parsed_scenes,
                    estimated_word_count=total_words,
                    source_chunk_ids=target.chunk_ids or [],
                )
        except Exception as err:
            logger.warning(
                f"[script_generator] LLM script generation failed for '{target.concept_name}': {err}. "
                "Using deterministic grounded fallback."
            )

    # Deterministic fallback
    return _generate_deterministic_script(
        target=target,
        student_id=student_id,
        source_id=source_id,
        source_text=source_text,
        diagram_cu_id=diagram_cu_id,
    )
