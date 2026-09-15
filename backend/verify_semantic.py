"""Quota-free component verification; curated plan, not live LLM end-to-end."""
import json
from pathlib import Path
from uuid import uuid4

from modules.config import RenderWorkspace
from modules.retrieval.pageindex_retriever import retrieve_curriculum
from modules.planning.grounding_validator import validate_storyboard_grounding
from modules.manim.semantic_compiler import semantic_compile_all
from modules.manim.renderer import render
from modules.sync.sync_engine import synchronize_all
from modules.tts.piper_tts import synthesize
from modules.video.ffmpeg_merge import merge


def main():
    workspace = RenderWorkspace.make("verified_work_energy_" + uuid4().hex[:8])
    curriculum = retrieve_curriculum("work energy kinetic energy", subject="Physics")
    assert curriculum["matched"]
    narration = ("Work transfers energy. When a constant force moves an object in the "
                 "direction of the force, work equals force times displacement. "
                 "The net work done on the object equals its change in kinetic energy.")
    plan = {"scene_id": 1, "concept_template": "work_energy", "title": "Work and Energy",
            "narration": narration, "events": [], "anchor_example": "work and kinetic energy"}
    assert not validate_storyboard_grounding([plan], curriculum["sections"], strict=True)
    wav, _ = synthesize(narration, workspace.audio_dir / "scene_1.wav")
    from pydub import AudioSegment
    assert AudioSegment.from_wav(wav).rms > 0, "Silent TTS fallback is not acceptable"
    timelines = synchronize_all([plan], {1: wav}, workspace=workspace)
    files = semantic_compile_all([plan], timelines, workspace=workspace, allow_fallback=False)
    videos = [render(path, workspace=workspace, allow_fallback=False) for path, _ in files]
    final = merge(videos, [wav], workspace=workspace, output=workspace.root / "work_energy.mp4")
    report = {"video": str(final), "scene_mode": "REAL_SEMANTIC_SCENE",
              "stub_fallback": False, "template_fallback": False,
              "planning": "curated deterministic fixture; live LLM NOT VERIFIED",
              "retrieval_mode": curriculum["retrieval_mode"],
              "sources": [{"document_id": s["document_id"], "pages": s["page_numbers"],
                           "excerpt": s["content"]} for s in curriculum["sections"]],
              "grounding_validation": "lexical overlap; not factual entailment",
              "tts_non_silent": True}
    (workspace.root / "verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"video": str(final), "verification": str(workspace.root / "verification.json")}))


if __name__ == "__main__":
    main()
