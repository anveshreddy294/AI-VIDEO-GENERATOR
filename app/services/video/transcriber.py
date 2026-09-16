"""Video Matrix — Phase 2: The Audio Transcription Pipeline (The Speech).

faster-whisper (CTranslate2-backed Whisper) runs fully offline on CPU and
returns *segment-level timestamps* — every spoken segment gets an exact
[start, end] window. That temporal fidelity is what makes the RAG capable of
pointing a student at the exact 30-second window of the lecture.
"""

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


def transcribe_with_timestamps(audio_path: Path) -> list[Segment]:
    """Transcribe the WAV back into timestamped spoken segments."""
    model = WhisperModel(
        settings.whisper_model_size,
        device="cpu",
        compute_type="int8",  # fast on CPU, negligible quality loss
    )
    segments, _info = model.transcribe(
        str(audio_path),
        vad_filter=True,  # drop silence so timestamps hug actual speech
    )

    return [
        Segment(start=round(seg.start, 1), end=round(seg.end, 1), text=seg.text.strip())
        for seg in segments
        if seg.text.strip()
    ]