"""Text-to-Speech (TTS) abstraction and provider implementations.

Provides:
- TTSProvider Protocol
- EdgeTTSProvider (high-quality neural voice via edge-tts)
- LocalTTSProvider (offline local synthesis via macOS `say` or python wave)
- MockTTSProvider (instant deterministic WAV generation for unit testing)
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from typing import Protocol, runtime_checkable

from ...core.config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class TTSProvider(Protocol):
    """Abstract interface for audio narration synthesis."""

    async def generate_audio(self, text: str, output_path: Path, target_seconds: float = 0.0) -> Path:
        """Synthesize spoken audio to WAV or MP3."""
        ...


def _generate_synthetic_wav(output_path: Path, duration_seconds: float = 5.0, sample_rate: int = 24000) -> Path:
    """Generate a valid, non-empty WAV file with a pleasant soft tone for testing/offline."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * max(1.0, duration_seconds))
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        # Generate a gentle audible tone so media players & Whisper can process it
        frames = bytearray()
        for i in range(num_frames):
            t = float(i) / sample_rate
            # 220Hz pleasant A3 tone with gentle decay
            val = int(4000.0 * math.sin(2.0 * math.pi * 220.0 * t))
            frames.extend(struct.pack("<h", val))
        wav_file.writeframes(frames)
    return output_path


class MockTTSProvider:
    """Deterministic Mock TTS Provider for fast offline testing."""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate

    async def generate_audio(self, text: str, output_path: Path, target_seconds: float = 0.0) -> Path:
        # Estimate duration if target_seconds not given (~3 words per second)
        words = len(text.split())
        dur = target_seconds if target_seconds > 0 else max(2.0, words / 2.8)
        return _generate_synthetic_wav(output_path, duration_seconds=dur, sample_rate=self.sample_rate)


class LocalTTSProvider:
    """Local offline TTS provider using macOS `say` or python wave fallback."""

    def __init__(self) -> None:
        self._say_bin = shutil.which("say")

    async def generate_audio(self, text: str, output_path: Path, target_seconds: float = 0.0) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self._say_bin and not text.strip().startswith("[mock]"):
            try:
                from .video_compositor import run_subprocess_bounded
                # Use macOS `say` to render uncompressed AIFF/WAV
                tmp_aiff = output_path.with_suffix(".aiff")
                await run_subprocess_bounded(
                    [self._say_bin, "-o", str(tmp_aiff), text],
                    timeout=30.0,
                    output_path=tmp_aiff,
                    log_prefix="[tts][say]",
                )
                if tmp_aiff.exists() and tmp_aiff.stat().st_size > 0:
                    # Convert AIFF to WAV via ffmpeg if ffmpeg is available
                    ffmpeg_bin = shutil.which("ffmpeg")
                    if ffmpeg_bin:
                        await run_subprocess_bounded(
                            [
                                ffmpeg_bin,
                                "-y",
                                "-nostats",
                                "-loglevel",
                                "error",
                                "-i",
                                str(tmp_aiff),
                                "-ar",
                                "24000",
                                "-ac",
                                "1",
                                str(output_path),
                            ],
                            timeout=30.0,
                            output_path=output_path,
                            log_prefix="[tts][ffmpeg_convert]",
                        )
                        tmp_aiff.unlink(missing_ok=True)
                        if output_path.exists() and output_path.stat().st_size > 0:
                            return output_path
                    else:
                        # Rename if ffmpeg unavailable
                        tmp_aiff.rename(output_path)
                        return output_path
            except Exception as exc:
                logger.warning(f"[tts] Local 'say' synthesis failed ({exc}); using synthetic audio")

        words = len(text.split())
        dur = target_seconds if target_seconds > 0 else max(2.0, words / 2.8)
        return _generate_synthetic_wav(output_path, duration_seconds=dur)


class EdgeTTSProvider:
    """High-quality Microsoft Edge neural voice synthesis."""

    def __init__(self, voice: str = "en-US-ChristopherNeural") -> None:
        self.voice = voice
        self.fallback = LocalTTSProvider()

    async def generate_audio(self, text: str, output_path: Path, target_seconds: float = 0.0) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            tmp_mp3 = output_path.with_suffix(".mp3")
            await communicate.save(str(tmp_mp3))
            if tmp_mp3.exists() and tmp_mp3.stat().st_size > 0:
                # Transcode MP3 to WAV using ffmpeg for predictable Whisper/Manim alignment
                ffmpeg_bin = shutil.which("ffmpeg")
                if ffmpeg_bin:
                    from .video_compositor import run_subprocess_bounded
                    await run_subprocess_bounded(
                        [
                            ffmpeg_bin,
                            "-y",
                            "-nostats",
                            "-loglevel",
                            "error",
                            "-i",
                            str(tmp_mp3),
                            "-ar",
                            "24000",
                            "-ac",
                            "1",
                            str(output_path),
                        ],
                        timeout=30.0,
                        output_path=output_path,
                        log_prefix="[tts][edge_ffmpeg]",
                    )
                    tmp_mp3.unlink(missing_ok=True)
                    if output_path.exists() and output_path.stat().st_size > 0:
                        return output_path
                else:
                    return tmp_mp3
        except Exception as exc:
            logger.warning(f"[tts] EdgeTTS generation failed ({exc}); falling back to local TTS")

        return await self.fallback.generate_audio(text, output_path, target_seconds=target_seconds)


def get_tts_provider(provider_name: str | None = None) -> TTSProvider:
    """Factory to get the configured TTS provider."""
    name = (provider_name or getattr(settings, "tts_provider", "edge_tts")).lower().strip()
    if name in ("mock", "test"):
        return MockTTSProvider()
    elif name in ("local", "say"):
        return LocalTTSProvider()
    elif name == "edge_tts":
        return EdgeTTSProvider()
    return LocalTTSProvider()
