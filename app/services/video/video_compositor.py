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

from ...core.config import settings

logger = logging.getLogger(__name__)


class FFmpegTimeoutError(TimeoutError):
    """Raised when an FFmpeg process exceeds its configured timeout."""
    pass


async def run_subprocess_bounded(
    cmd: list[str],
    timeout: float,
    output_path: Path | None = None,
    log_prefix: str = "[subprocess]",
) -> tuple[int, bytes, bytes]:
    """Execute a subprocess with strict timeout, clean termination, and bounded stderr.

    On timeout:
    1. Log error with PID and timeout duration
    2. proc.terminate()
    3. wait up to 3.0s for graceful shutdown
    4. proc.kill() if still running
    5. proc.wait() to reap zombie process
    6. remove partial output file if requested
    7. raise FFmpegTimeoutError
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        bounded_stderr = (stderr or b"")[-32768:]
        return proc.returncode, b"", bounded_stderr
    except (asyncio.TimeoutError, TimeoutError) as to_err:
        logger.error(
            "%s Process PID %s timed out after %.1fs; terminating...",
            log_prefix,
            proc.pid,
            timeout,
        )
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning(
                    "%s Process PID %s did not terminate cleanly; killing...",
                    log_prefix,
                    proc.pid,
                )
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass

        if output_path and output_path.exists():
            try:
                output_path.unlink(missing_ok=True)
            except Exception as clean_err:
                logger.warning(
                    "%s Could not remove partial output %s: %s",
                    log_prefix,
                    output_path,
                    clean_err,
                )

        raise FFmpegTimeoutError(
            f"Process '{cmd[0]}' timed out after {timeout:.1f}s"
        ) from to_err


async def composite_remedial_video(
    video_mp4: Path,
    audio_wav: Path,
    output_mp4: Path,
    subtitles_srt: Path | None = None,
    timeout: float | None = None,
) -> Path:
    """Merge video, audio, and optional subtitles using ffmpeg into a production MP4."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    video_timeout = timeout or float(getattr(settings, "video_timeout", 120.0))
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
        "-nostats",
        "-loglevel",
        "error",
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
        getattr(settings, "ffmpeg_preset", "fast"),
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
        returncode, _, stderr = await run_subprocess_bounded(
            cmd,
            timeout=video_timeout,
            output_path=output_mp4,
            log_prefix="[compositor][primary]",
        )
        if returncode == 0 and output_mp4.exists() and output_mp4.stat().st_size > 0:
            logger.info(
                "[compositor] Successfully composited video with H.264/AAC (subtitles=%s): %s",
                has_subtitles,
                output_mp4,
            )
            return output_mp4
        else:
            logger.warning(
                "[compositor] Primary composition failed (code %d); attempting fallback: %s",
                returncode,
                stderr.decode(errors="replace")[:300],
            )
    except FFmpegTimeoutError:
        logger.error("[compositor] Primary composition exceeded timeout of %.1fs", video_timeout)
        raise
    except Exception as exc:
        logger.warning("[compositor] Primary composition attempt failed: %s", exc)

    # Fallback attempt: composite without subtitle stream (pure audio + video)
    fallback_cmd = [
        ffmpeg_bin,
        "-y",
        "-nostats",
        "-loglevel",
        "error",
        "-i",
        str(video_mp4),
        "-i",
        str(audio_wav),
        "-c:v",
        "libx264",
        "-preset",
        getattr(settings, "ffmpeg_preset", "fast"),
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
        returncode2, _, stderr2 = await run_subprocess_bounded(
            fallback_cmd,
            timeout=video_timeout,
            output_path=output_mp4,
            log_prefix="[compositor][fallback]",
        )
        if returncode2 == 0 and output_mp4.exists() and output_mp4.stat().st_size > 0:
            logger.info("[compositor] Successfully composited video via fallback: %s", output_mp4)
            return output_mp4
        else:
            logger.warning(
                "[compositor] Fallback composition failed (code %d): %s",
                returncode2,
                stderr2.decode(errors="replace")[:300],
            )
    except FFmpegTimeoutError:
        logger.error("[compositor] Fallback composition exceeded timeout of %.1fs", video_timeout)
        raise
    except Exception as exc:
        logger.warning("[compositor] Fallback composition failed: %s", exc)

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
