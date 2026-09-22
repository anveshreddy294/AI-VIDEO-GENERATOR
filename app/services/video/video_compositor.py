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

    # Build primary ffmpeg composition command with H.264 (yuv420p), AAC (44.1kHz), and embedded subtitles
    has_subtitles = bool(
        subtitles_srt
        and Path(subtitles_srt).exists()
        and Path(subtitles_srt).stat().st_size > 0
    )

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_mp4),
        "-i",
        str(audio_wav),
    ]

    if has_subtitles:
        cmd.extend(["-i", str(subtitles_srt)])

    cmd.extend([
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "44100",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
    ])

    if has_subtitles:
        cmd.extend([
            "-c:s",
            "mov_text",
            "-map",
            "2:s:0",
            "-metadata:s:s:0",
            "language=eng",
        ])

    cmd.extend([
        "-shortest",
        str(output_mp4),
    ])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0 and output_mp4.exists() and output_mp4.stat().st_size > 0:
            logger.info(f"[compositor] Successfully composited video with H.264/AAC (subtitles={has_subtitles}): {output_mp4}")
            return output_mp4
        else:
            logger.warning(
                f"[compositor] Primary composition failed (code {proc.returncode}); attempting without subtitle stream: "
                f"{stderr.decode()[:300]}"
            )
    except Exception as exc:
        logger.warning(f"[compositor] Primary composition attempt failed: {exc}")

    # Fallback attempt: composite without subtitle stream (pure audio + video)
    fallback_cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_mp4),
        "-i",
        str(audio_wav),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "44100",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        str(output_mp4),
    ]
    try:
        proc2 = await asyncio.create_subprocess_exec(
            *fallback_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()
        if output_mp4.exists() and output_mp4.stat().st_size > 0:
            logger.info(f"[compositor] Successfully composited video via fallback: {output_mp4}")
            return output_mp4
    except Exception as exc:
        logger.warning(f"[compositor] Fallback composition failed: {exc}")

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
