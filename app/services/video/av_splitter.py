"""Video Matrix — Phase 1: The Audio/Visual Splitter.

Uses FFmpeg (via subprocess) to rip the audio track out of the video into a
16kHz mono WAV — the exact format faster-whisper likes. The original video
file is left untouched for the visual pipeline.

Requires FFmpeg on the host:
    macOS:  brew install ffmpeg
    Ubuntu: sudo apt-get install ffmpeg
"""

import subprocess
from pathlib import Path


class FFmpegMissingError(RuntimeError):
    pass


def extract_audio(video_path: Path, out_wav: Path) -> Path:
    """Extract a 16kHz mono WAV track from the given video file."""
    if not _ffmpeg_available():
        raise FFmpegMissingError(
            "FFmpeg is not installed on this server. Install it with "
            "`brew install ffmpeg` (macOS) or `sudo apt-get install ffmpeg` (Ubuntu)."
        )

    cmd = [
        "ffmpeg",
        "-y",                      # overwrite without asking
        "-i", str(video_path),     # input
        "-vn",                     # drop the video stream — audio only
        "-acodec", "pcm_s16le",    # PCM 16-bit little-endian
        "-ar", "16000",            # 16 kHz sample rate (whisper-optimal)
        "-ac", "1",                # mono
        str(out_wav),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed on {video_path.name}: {result.stderr[-500:]}"
        )
    return out_wav


def _ffmpeg_available() -> bool:
    probe = subprocess.run(
        ["ffmpeg", "-version"], capture_output=True, text=True
    )
    return probe.returncode == 0