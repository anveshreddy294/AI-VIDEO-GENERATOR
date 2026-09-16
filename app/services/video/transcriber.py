"""Video Matrix — Phase 2: The Audio Transcription Pipeline (The Speech).

faster-whisper (CTranslate2-backed Whisper) runs fully offline on CPU and
returns *segment-level timestamps* — every spoken segment gets an exact
[start, end] window. That temporal fidelity is what makes the RAG capable of
pointing a student at the exact 30-second window of the lecture.

Uses `large-v3` by default for maximum accuracy. Post-processing cleans up
common Whisper hallucinations and formatting artifacts.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel

from ...core.config import settings


@dataclass
class Segment:
    """One contiguous spoken phrase with its clock times (seconds)."""

    start: float
    end: float
    text: str


# Common Whisper hallucinations / artifacts to strip
_HALLUCINATION_PATTERNS = [
    re.compile(r"^(?:thank you|thanks for watching|subscribe|please subscribe|"
               r"like and subscribe|click the bell|see you next time|"
               r"bye[\s,.]*|goodbye[\s,.]*|okay[\s,.]*|so[\s,.]*|"
               r"um[\s,.]*|uh[\s,.]*)$", re.IGNORECASE),
    # Repeated word patterns like "the the the"
    re.compile(r"\b(\w+)(\s+\1){2,}\b", re.IGNORECASE),
]


def transcribe_with_timestamps(audio_path: Path) -> list[Segment]:
    """Transcribe the WAV back into timestamped spoken segments.

    Uses the configured whisper model size (default: large-v3 for best accuracy).
    Falls back to base if large-v3 fails to load (e.g. insufficient memory).
    """
    model = _load_model()
    segments, _info = model.transcribe(
        str(audio_path),
        vad_filter=True,       # drop silence so timestamps hug actual speech
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
        beam_size=5,            # wider beam = more accurate transcription
        best_of=5,              # sample 5 candidates, pick best
        temperature=0.0,        # greedy decoding for consistency
        word_timestamps=True,   # word-level timestamps for precision
        initial_prompt="This is an educational lecture about science, technology, engineering, and mathematics.",  # bias toward academic content
    )

    results: list[Segment] = []
    for seg in segments:
        text = _post_process(seg.text)
        if text:
            results.append(
                Segment(start=round(seg.start, 1), end=round(seg.end, 1), text=text)
            )

    return results


def _load_model() -> WhisperModel:
    """Load the whisper model, falling back to smaller models on failure."""
    sizes_to_try = [settings.whisper_model_size, "base", "tiny"]
    # Deduplicate while preserving order
    seen = set()
    ordered_sizes = []
    for s in sizes_to_try:
        if s not in seen:
            seen.add(s)
            ordered_sizes.append(s)

    for size in ordered_sizes:
        try:
            print(f"[info] Loading whisper model '{size}'...")
            model = WhisperModel(
                size,
                device="cpu",
                compute_type="int8",  # fast on CPU, negligible quality loss
            )
            print(f"[info] Whisper model '{size}' loaded successfully.")
            return model
        except Exception as exc:
            print(f"[warn] Failed to load whisper model '{size}': {exc}")
            continue

    raise RuntimeError("Could not load any whisper model. Check your installation.")


def _post_process(text: str) -> str:
    """Clean up common whisper artifacts and formatting issues."""
    text = text.strip()

    # Remove leading/trailing punctuation noise
    text = text.strip(".,;:!? ")

    # Strip known hallucination patterns
    for pattern in _HALLUCINATION_PATTERNS:
        text = pattern.sub("", text).strip()

    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)

    # Capitalize first letter
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text.strip()
