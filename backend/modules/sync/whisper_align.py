"""WhisperX forced alignment with uniform fallback."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from modules.config import (
    USE_WHISPERX,
    WHISPERX_COMPUTE_TYPE,
    WHISPERX_DEVICE,
    WHISPERX_MODEL,
    get_logger,
)

logger = get_logger(__name__)

_whisperx_available: bool | None = None


def _check_whisperx() -> bool:
    global _whisperx_available
    if _whisperx_available is not None:
        return _whisperx_available
    if not USE_WHISPERX:
        _whisperx_available = False
        logger.info("WhisperX disabled (USE_WHISPERX=false); using uniform alignment")
        return False
    try:
        import whisperx  # noqa: F401

        _whisperx_available = True
    except Exception as exc:
        # Catch ALL import-time failures (ImportError, RuntimeError from torch/numpy
        # ABI mismatches, SystemExit from broken transformers, etc.). The pipeline
        # must never crash here — uniform alignment is a perfectly valid fallback.
        _whisperx_available = False
        logger.warning(
            "WhisperX unavailable (%s: %s); using uniform alignment fallback",
            type(exc).__name__, exc,
        )
    return _whisperx_available


def align(wav_path: Path, transcript: str) -> list[dict[str, Any]]:
    """Align transcript to audio and return word-level timestamps."""
    logger.info("Aligning audio: %s", wav_path.name)
    if _check_whisperx():
        try:
            return _align_whisperx(wav_path, transcript)
        except Exception as exc:
            logger.warning("WhisperX alignment failed: %s — using fallback", exc)
    return _align_uniform(wav_path, transcript)


def _align_whisperx(wav_path: Path, transcript: str) -> list[dict[str, Any]]:
    """Run WhisperX forced alignment."""
    import whisperx

    audio = whisperx.load_audio(str(wav_path))
    model = whisperx.load_model(
        WHISPERX_MODEL, WHISPERX_DEVICE, compute_type=WHISPERX_COMPUTE_TYPE
    )
    result = model.transcribe(audio, batch_size=8)
    language = result.get("language", "en")
    align_model, metadata = whisperx.load_align_model(
        language_code=language, device=WHISPERX_DEVICE
    )
    aligned = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        WHISPERX_DEVICE,
        return_char_alignments=False,
    )
    words = []
    for segment in aligned.get("segments", []):
        for word_info in segment.get("words", []):
            word = word_info.get("word", "").strip()
            start = word_info.get("start")
            end = word_info.get("end")
            if word and start is not None and end is not None:
                words.append({"word": word, "start": float(start), "end": float(end)})
    if words:
        logger.info("WhisperX aligned %d words", len(words))
        return words
    return _align_uniform(wav_path, transcript)


def _align_uniform(wav_path: Path, transcript: str) -> list[dict[str, Any]]:
    """Uniform proportional timestamps when WhisperX is unavailable.

    This is the expected code path when USE_WHISPERX=false (the default).
    Timing sync will be approximate but the video will still render correctly.
    Enable WhisperX for frame-accurate word-level alignment.
    """
    from modules.tts.piper_tts import get_audio_duration

    duration = get_audio_duration(wav_path)
    tokens = re.findall(r"\S+", transcript)
    if not tokens:
        return []
    slot = duration / len(tokens)
    words = []
    for i, token in enumerate(tokens):
        words.append({
            "word": token,
            "start": round(i * slot, 3),
            "end": round((i + 1) * slot, 3),
        })
    logger.info(
        "Uniform alignment: %d words over %.2fs "
        "(set USE_WHISPERX=true for frame-accurate sync)",
        len(words), duration,
    )
    return words
