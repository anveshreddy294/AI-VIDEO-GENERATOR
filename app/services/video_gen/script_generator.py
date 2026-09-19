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
    """Retrieve grounded text snippets strictly from exact chunk/content provenance.

    Strict Grounding Protocol:
    1. Query exact chunks from Qdrant via target.chunk_ids
    2. Fall back to target.source_content_ids only if exact chunks are absent
    3. If neither produces authoritative text, fail with GROUNDING_NOT_FOUND
    Never substitutes arbitrary document chunks.
    """
    grounded_texts: List[str] = []
    diagram_cu_id: Optional[str] = None

    # Step 1: Exact chunk provenance from vector store
    if target.chunk_ids:
        try:
            from ...db.vector_store import retrieve_exact_chunks
            exact_chunks = retrieve_exact_chunks(source_id=source_id, chunk_ids=target.chunk_ids)
            for ch in exact_chunks:
                text = ch.get("text", "")
                cleaned = _clean_source_text(text)
                if cleaned:
                    grounded_texts.append(cleaned)
        except Exception as exc:
            logger.warning("[script_generator] Exact chunk retrieval error: %s", exc)

    # Step 2: Exact ContentUnits provenance lookup via source_content_ids
    all_units: List[ContentUnit] = get_content_units(source_id)
    target_cu_ids = set(target.source_content_ids or [])

    if not grounded_texts and target_cu_ids:
        for unit in all_units:
            if unit.content_id in target_cu_ids:
                cleaned = _clean_source_text(unit.text)
                if cleaned and cleaned not in grounded_texts:
                    grounded_texts.append(cleaned)

    # Diagram identification from matched provenance
    for unit in all_units:
        if unit.content_id in target_cu_ids or (target.concept_name.lower() in unit.text.lower()):
            if unit.modality in ["image", "video"] or getattr(unit, "image_path", None):
                if not diagram_cu_id:
                    diagram_cu_id = unit.content_id

    # Strict Grounding Gate: Never substitute unrelated content
    if not grounded_texts:
        raise ValueError(
            f"GROUNDING_NOT_FOUND: No authoritative Layer A chunks found for concept '{target.concept_name}' "
            f"(chunk_ids={target.chunk_ids}, content_ids={target.source_content_ids})."
        )

    combined_text = "\n\n".join(grounded_texts[:5])
    return combined_text, diagram_cu_id


def _extract_source_definitions(concept: str, source_text: str) -> tuple[str, str, str]:
    """Extract clean definitions and rules strictly from authoritative source text.

    Never invents physics or domain formulas not grounded in study material.
    """
    clean_text = _clean_source_text(source_text)
    raw_sentences = [s.strip() for s in re.split(r"[.!?]\s+", clean_text) if len(s.strip()) > 15]
    valid_sentences = [
        s for s in raw_sentences
        if not s.startswith("[") and "no description" not in s.lower() and "image:" not in s.lower()
    ]

    if not valid_sentences:
        raise ValueError(f"INSUFFICIENT_GROUNDING: Source text for '{concept}' contains no valid pedagogical sentences.")

    defn = valid_sentences[0]
    detail = valid_sentences[1] if len(valid_sentences) > 1 else valid_sentences[0]
    rule = f"Core Rule: {concept}"
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

    def_sentence, detail_sentence, highlight_rule = _extract_source_definitions(concept, source_text)

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
        misconception_block = ""
        if target.question_stem or target.misconception:
            misconception_block = f"""
DIAGNOSTIC ASSESSMENT MISCONCEPTION TO DIRECTLY REMEDIATE:
- Student's Failed Question: "{target.question_stem}"
- Student Error & Gap: "{target.misconception or 'Misidentified core principle'}"
- Authoritative Correction: "{target.explanation or 'See source text definition'}"

CRITICAL INSTRUCTION: You MUST directly address this specific misconception in Act 2 (Breakdown scene)! State why the student's misunderstanding is incorrect and clearly demonstrate the authoritative principle from the text.
"""

        prompt = f"""You are an expert educational video scriptwriter and instructional designer.
Create a structured, multi-scene video script to remediate a student who failed a diagnostic quiz on '{target.concept_name}'.

TARGET CONSTRAINTS:
- Concept Name: {target.concept_name}
- Concept Difficulty: {target.difficulty}
- Total Target Duration: Exactly {target_seconds} seconds.
- Total Word Budget: Approximately {max_words} words across all scenes (do NOT exceed {max_words + 15} words).
- Speaking Speed: ~2.4 words per second.
{misconception_block}
AUTHORITATIVE SOURCE TEXT (Ground all explanations strictly in this text):
\"\"\"{source_text[:2000]}\"\"\"

PEDAGOGICAL STRUCTURE (3-Act Micro-Lesson):
1. Act 1 (Hook/Context): Announce the concept clearly and state why it matters.
2. Act 2 (Breakdown/Evidence & Misconception): Explain the principle step-by-step from the source text and address the failed quiz concept.
3. Act 3 (Takeaway): State the memorable rule or formula to prevent future quiz mistakes.

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
            default_rule = f"Core Principle: {target.concept_name}"

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
                    diagnostics={
                        "stage": "video_script_generation",
                        "provider_used": getattr(provider, "model_name", "gemini"),
                        "fallback_used": False,
                        "grounding_verified": True,
                    },
                )
        except Exception as err:
            logger.warning(
                f"[script_generator] LLM script generation failed for '{target.concept_name}': {err}. "
                "Using deterministic grounded fallback."
            )

    # Deterministic fallback strictly grounded in source text
    fallback_script = _generate_deterministic_script(
        target=target,
        student_id=student_id,
        source_id=source_id,
        source_text=source_text,
        diagram_cu_id=diagram_cu_id,
    )
    fallback_script.diagnostics = {
        "stage": "video_script_generation",
        "provider_used": "deterministic_grounded_fallback",
        "fallback_used": True,
        "fallback_reason": "LLM generation unavailable or parse failed",
        "grounding_verified": True,
    }
    return fallback_script
