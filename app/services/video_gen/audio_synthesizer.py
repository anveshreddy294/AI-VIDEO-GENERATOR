"""Audio synthesis engine for Step 3 Video Generation.

Synthesizes high-fidelity neural voiceover audio for each scene using edge-tts,
converts to standard PCM WAV, measures exact audio durations, and generates
concatenated master audio tracks with synchronized timing metrics.
"""

import asyncio
import logging
import math
import os
import struct
import subprocess
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    edge_tts = None
    HAS_EDGE_TTS = False

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


def get_ffmpeg_exe() -> str:
    """Safely obtain ffmpeg binary path from imageio_ffmpeg, system PATH, or fallback."""
    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"


from .schemas import VideoScene, VideoScript

logger = logging.getLogger(__name__)

# Default neural voice (warm, authoritative, educational)
DEFAULT_VOICE = "en-US-GuyNeural"


def _generate_mock_wav(output_path: Path, duration_seconds: float) -> float:
    """Generate a clean, quiet sine tone PCM WAV file for offline testing."""
    sample_rate = 16000
    total_frames = int(sample_rate * duration_seconds)
    frequency = 440.0  # A4

    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        # Generate low-amplitude sine wave
        frames = bytearray()
        for i in range(total_frames):
            t = float(i) / sample_rate
            # Fade in/out to avoid clicks
            fade = min(1.0, i / 1000.0, (total_frames - i) / 1000.0)
            value = int(500.0 * fade * math.sin(2.0 * math.pi * frequency * t))
            frames.extend(struct.pack("<h", value))

        wf.writeframes(frames)

    return duration_seconds


def get_wav_duration(wav_path: Path) -> float:
    """Accurately measure the duration of a WAV file using the standard library."""
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return round(frames / float(rate), 2)


def convert_mp3_to_wav(mp3_path: Path, wav_path: Path) -> None:
    """Convert an MP3 file to standard 16kHz mono WAV using imageio-ffmpeg."""
    ffmpeg_exe = get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(mp3_path),
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(wav_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


async def synthesize_scene_audio(
    scene: VideoScene,
    output_dir: Path,
    voice: str = DEFAULT_VOICE,
    mock_mode: bool = False,
) -> Tuple[Path, float]:
    """Synthesize voiceover audio for a single scene and measure its exact duration."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"scene_{scene.scene_number}"
    wav_path = output_dir / f"{base_name}.wav"
    mp3_path = output_dir / f"{base_name}.mp3"

    text = scene.narration.strip()
    if not text:
        text = scene.title

    if mock_mode or not HAS_EDGE_TTS:
        duration = _generate_mock_wav(wav_path, scene.duration_seconds)
        return wav_path, duration

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(mp3_path))
        convert_mp3_to_wav(mp3_path, wav_path)
        if mp3_path.exists():
            mp3_path.unlink()
        measured_duration = get_wav_duration(wav_path)
        return wav_path, measured_duration
    except Exception as err:
        logger.warning(
            f"[audio_synthesizer] Edge-TTS synthesis failed for scene {scene.scene_number}: {err}. "
            "Falling back to mock audio."
        )
        duration = _generate_mock_wav(wav_path, scene.duration_seconds)
        return wav_path, duration


def append_silence_to_wav(wav_path: Path, silence_seconds: float = 0.3) -> float:
    """Appends real silence frames directly to the audio WAV file so video and audio clocks match."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            params = wf.getparams()
            n_channels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            frames = wf.readframes(params.nframes)

        silence_frames = int(framerate * silence_seconds)
        silence_bytes = b"\x00" * (silence_frames * n_channels * sampwidth)

        with wave.open(str(wav_path), "wb") as wf:
            wf.setparams(params)
            wf.writeframes(frames + silence_bytes)

        return get_wav_duration(wav_path)
    except Exception as e:
        logger.warning(f"[audio_synthesizer] Could not append silence to {wav_path}: {e}")
        return get_wav_duration(wav_path)


def concatenate_wav_files(wav_paths: List[Path], output_path: Path) -> float:
    """Concatenate multiple WAV files sequentially into a single master audio track."""
    if not wav_paths:
        raise ValueError("No WAV files provided for concatenation.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(wav_paths[0]), "rb") as first_wf:
        params = first_wf.getparams()

    with wave.open(str(output_path), "wb") as out_wf:
        out_wf.setparams(params)
        for wp in wav_paths:
            with wave.open(str(wp), "rb") as wf:
                out_wf.writeframes(wf.readframes(wf.getnframes()))

    return get_wav_duration(output_path)


async def synthesize_script_audio(
    script: VideoScript,
    output_dir: Path,
    voice: str = DEFAULT_VOICE,
    mock_mode: bool = False,
) -> Tuple[Path, List[Path], List[float]]:
    """Synthesize audio for all scenes in a script and produce master audio.

    Returns:
        (master_wav_path, list_of_scene_wav_paths, list_of_measured_durations)
    """
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    scene_wavs: List[Path] = []
    durations: List[float] = []

    for scene in script.scenes:
        wav_path, raw_dur = await synthesize_scene_audio(
            scene=scene,
            output_dir=audio_dir,
            voice=voice,
            mock_mode=mock_mode,
        )
        # Authoritative clock: append 0.3s real silence to audio wave
        calibrated_dur = append_silence_to_wav(wav_path, silence_seconds=0.3)
        scene_wavs.append(wav_path)
        durations.append(calibrated_dur)
        # Calibrate scene duration to match measured audio length exactly
        scene.duration_seconds = calibrated_dur

    master_path = audio_dir / "master_voiceover.wav"
    master_dur = concatenate_wav_files(scene_wavs, master_path)

    return master_path, scene_wavs, durations
