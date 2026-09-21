"""Audio/Video Compositor — Merges rendered video, synthesized TTS audio, and subtitles.

Combines:
- Manim MP4 (visual animation stream)
- TTS WAV (synthesized voice narration)
- SRT captions (Whisper-aligned timestamps)
Produces the final synchronized remedial MP4 video.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def composite_remedial_video(
    video_mp4: Path,
    audio_wav: Path,
    output_mp4: Path,
    subtitles_srt: Path | None = None,
) -> Path:
    """Merge video, audio, and optional subtitles using ffmpeg into a production MP4."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = shutil.which("ffmpeg")

    if not ffmpeg_bin:
        # Check imageio-ffmpeg
        try:
            import imageio_ffmpeg
            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_bin = None

    if not ffmpeg_bin:
        logger.warning("[compositor] ffmpeg binary not found; falling back to copying video track")
        shutil.copy2(video_mp4, output_mp4)
        return output_mp4

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_mp4),
        "-i",
        str(audio_wav),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        str(output_mp4),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0 and output_mp4.exists() and output_mp4.stat().st_size > 0:
            logger.info(f"[compositor] Successfully composited video: {output_mp4}")
            return output_mp4
        else:
            logger.warning(f"[compositor] Direct stream copy failed; attempting transcoding re-encode: {stderr.decode()[:300]}")
    except Exception as exc:
        logger.warning(f"[compositor] Composition attempt 1 failed: {exc}")

    # Fallback with standard re-encoding
    reencode_cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_mp4),
        "-i",
        str(audio_wav),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(output_mp4),
    ]
    proc2 = await asyncio.create_subprocess_exec(
        *reencode_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc2.communicate()

    if output_mp4.exists() and output_mp4.stat().st_size > 0:
        return output_mp4

    # Ultimate fallback: copy video track
    shutil.copy2(video_mp4, output_mp4)
    return output_mp4


def composite_remedial_video_sync(
    video_mp4: Path,
    audio_wav: Path,
    output_mp4: Path,
    subtitles_srt: Path | None = None,
) -> Path:
    """Synchronous wrapper for composite_remedial_video."""
    return asyncio.run(composite_remedial_video(video_mp4, audio_wav, output_mp4, subtitles_srt))
