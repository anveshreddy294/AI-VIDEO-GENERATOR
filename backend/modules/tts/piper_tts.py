"""Piper TTS synthesis with fallbacks."""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional

from modules.config import PATHS, PIPER_MODEL, get_logger

logger = get_logger(__name__)

PIPER_VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"


def _ensure_piper_model() -> tuple[Path, Path]:
    """Download Piper voice model if missing."""
    model_dir = PATHS["piper_models"]
    model_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = model_dir / f"{PIPER_MODEL}.onnx"
    json_path = model_dir / f"{PIPER_MODEL}.onnx.json"

    if not onnx_path.exists() or not json_path.exists():
        logger.info("Downloading Piper voice model: %s", PIPER_MODEL)
        import urllib.request

        base = f"{PIPER_VOICE_BASE}/{PIPER_MODEL}"
        urllib.request.urlretrieve(f"{base}.onnx", onnx_path)
        urllib.request.urlretrieve(f"{base}.onnx.json", json_path)
        logger.info("Piper model downloaded to %s", model_dir)

    return onnx_path, json_path


def _piper_cli_available() -> bool:
    return shutil.which("piper") is not None


def _synthesize_piper_cli(text: str, out_wav: Path) -> bool:
    """Synthesize using piper CLI."""
    try:
        onnx_path, _ = _ensure_piper_model()
        proc = subprocess.run(
            ["piper", "--model", str(onnx_path), "--output_file", str(out_wav)],
            input=text,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if proc.returncode == 0 and out_wav.exists():
            return True
        logger.warning("Piper CLI failed: %s", proc.stderr)
    except Exception as exc:
        logger.warning("Piper CLI error: %s", exc)
    return False


def _synthesize_piper_python(text: str, out_wav: Path) -> bool:
    """Synthesize using piper-tts Python package."""
    try:
        from piper import PiperVoice

        onnx_path, json_path = _ensure_piper_model()
        voice = PiperVoice.load(str(onnx_path), config_path=str(json_path))
        with wave.open(str(out_wav), "wb") as wav_file:
            voice.synthesize(text, wav_file)
        return out_wav.exists()
    except Exception as exc:
        logger.warning("Piper Python API error: %s", exc)
    return False


def _synthesize_pyttsx3(text: str, out_wav: Path) -> bool:
    """Fallback: system TTS via pyttsx3."""
    try:
        import pyttsx3
        from pydub import AudioSegment

        tmp_aiff = out_wav.with_suffix(".aiff")
        engine = pyttsx3.init()
        engine.save_to_file(text, str(tmp_aiff))
        engine.runAndWait()
        if tmp_aiff.exists():
            audio = AudioSegment.from_file(str(tmp_aiff))
            audio.export(str(out_wav), format="wav")
            tmp_aiff.unlink(missing_ok=True)
            return out_wav.exists()
    except Exception as exc:
        logger.warning("pyttsx3 fallback error: %s", exc)
    return False


def _synthesize_gtts(text: str, out_wav: Path) -> bool:
    """Synthesize using gTTS (Google Text-to-Speech) and convert to WAV via FFmpeg."""
    try:
        from gtts import gTTS
        tmp_mp3 = out_wav.with_suffix(".mp3")
        tts = gTTS(text=text, lang="en", tld="com")
        tts.save(str(tmp_mp3))
        
        if tmp_mp3.exists():
            import subprocess
            # Convert mp3 to wav using ffmpeg (since ffmpeg is fully verified to be Available!)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(tmp_mp3), str(out_wav)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            tmp_mp3.unlink(missing_ok=True)
            return out_wav.exists()
    except Exception as exc:
        logger.warning("gTTS fallback error: %s", exc)
    return False


def _synthesize_silent(text: str, out_wav: Path) -> Path:
    """Fallback: silent WAV with estimated duration from word count."""
    word_count = len(text.split())
    duration_sec = max(word_count / 2.5, 2.0)
    sample_rate = 22050
    n_frames = int(sample_rate * duration_sec)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
    logger.warning(
        "Using silent audio fallback (%.1fs) for: %s", duration_sec, out_wav.name
    )
    return out_wav


def synthesize(text: str, out_wav: Path, allow_silent: bool = True) -> tuple[Path, float]:
    """Synthesize speech to WAV and return path + duration in seconds."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Synthesizing audio: %s", out_wav.name)

    success = False
    provider = "piper_cli"
    if _piper_cli_available():
        success = _synthesize_piper_cli(text, out_wav)
    if not success:
        provider = "piper_python"
        success = _synthesize_piper_python(text, out_wav)
    if not success:
        provider = "gtts"
        success = _synthesize_gtts(text, out_wav)
    if not success:
        provider = "pyttsx3"
        logger.warning("gTTS/Piper unavailable, trying pyttsx3 fallback")
        success = _synthesize_pyttsx3(text, out_wav)
    if not success:
        if not allow_silent:
            raise RuntimeError("TTS failed; strict generation rejects silent audio")
        provider = "silent"
        _synthesize_silent(text, out_wav)

    duration = get_audio_duration(out_wav)
    import json
    from pydub import AudioSegment
    silent = AudioSegment.from_file(out_wav).rms == 0
    if silent and not allow_silent:
        raise RuntimeError("Strict generation rejects silent audio")
    out_wav.with_suffix(".tts.json").write_text(json.dumps({
        "tts_provider": provider, "tts_fallback_used": provider not in ("piper_cli", "piper_python"),
        "silent": silent, "duration": duration}), encoding="utf-8")
    logger.info("Audio synthesized: %s (%.2fs)", out_wav, duration)
    return out_wav, duration



def get_audio_duration(wav_path: Path) -> float:
    """Return audio duration in seconds."""
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(str(wav_path))
        return len(audio) / 1000.0
    except Exception:
        with wave.open(str(wav_path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
