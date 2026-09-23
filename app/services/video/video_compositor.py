"""Audio/Video Compositor — Merges rendered video, synthesized TTS audio, and subtitles.

Combines:
- Manim MP4 (visual animation stream)
- TTS WAV (synthesized voice narration)
- SRT captions (Whisper-aligned timestamps)
Produces the final synchronized remedial MP4 video.
"""

from __future__ import annotations

import asyncio
import json
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


def _resolve_binary(name: str) -> str | None:
    """Resolve executable path from PATH or imageio_ffmpeg fallback."""
    bin_path = shutil.which(name)
    if not bin_path and name == "ffmpeg":
        try:
            import imageio_ffmpeg
            bin_path = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            bin_path = None
    return bin_path


def probe_media(file_path: Path) -> dict[str, Any]:
    """Inspect media file streams, duration, and codecs using ffprobe."""
    ffprobe_bin = _resolve_binary("ffprobe")
    if not ffprobe_bin:
        raise RuntimeError("ffprobe executable not found on system PATH")

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name:stream=index,codec_type,codec_name,width,height,duration",
        "-of",
        "json",
        str(file_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed (code {res.returncode}): {res.stderr.strip()}")
    try:
        return json.loads(res.stdout)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse ffprobe JSON output: {exc}") from exc


def validate_video_artifact(mp4_path: Path, expect_audio: bool = True) -> dict[str, Any]:
    """Validate MP4 video artifact integrity using ffprobe."""
    if not mp4_path.exists():
        raise FileNotFoundError(f"Final MP4 does not exist: {mp4_path}")
    size = mp4_path.stat().st_size
    if size == 0:
        raise ValueError(f"Final MP4 is 0 bytes: {mp4_path}")

    info = probe_media(mp4_path)
    streams = info.get("streams", [])
    format_info = info.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not video_streams:
        raise ValueError(f"Final MP4 contains no video stream: {mp4_path}")

    v_stream = video_streams[0]
    v_codec = v_stream.get("codec_name")
    if not v_codec:
        raise ValueError(f"Final MP4 video stream has unknown codec: {mp4_path}")

    try:
        dur = float(format_info.get("duration", 0) or 0)
    except (ValueError, TypeError):
        dur = 0.0

    if dur <= 0:
        raise ValueError(f"Final MP4 duration is <= 0 ({dur}s): {mp4_path}")

    a_codec = None
    if expect_audio:
        if not audio_streams:
            raise ValueError(f"Final MP4 is missing required audio stream: {mp4_path}")
        a_codec = audio_streams[0].get("codec_name")
        if not a_codec:
            raise ValueError(f"Final MP4 audio stream has unknown codec: {mp4_path}")

    return {
        "path": str(mp4_path),
        "size": size,
        "duration": dur,
        "video_codec": v_codec,
        "audio_codec": a_codec,
        "streams_count": len(streams),
    }


def _format_diagnostics(
    video_mp4: Path,
    audio_wav: Path,
    output_mp4: Path,
    ffmpeg_bin: str | None,
    ffprobe_bin: str | None,
    returncode: int | None = None,
    stderr: str | None = None,
    exc: Exception | None = None,
) -> dict[str, Any]:
    """Compile diagnostic information safely without exposing sensitive secrets."""
    return {
        "exception_class": type(exc).__name__ if exc else None,
        "exception_message": str(exc) if exc else None,
        "returncode": returncode,
        "ffmpeg_executable": ffmpeg_bin,
        "ffprobe_executable": ffprobe_bin,
        "input_video_path": str(video_mp4),
        "input_video_exists": video_mp4.exists(),
        "input_video_size": video_mp4.stat().st_size if video_mp4.exists() else 0,
        "input_audio_path": str(audio_wav),
        "input_audio_exists": audio_wav.exists(),
        "input_audio_size": audio_wav.stat().st_size if audio_wav.exists() else 0,
        "output_path": str(output_mp4),
        "output_dir_exists": output_mp4.parent.exists(),
        "stderr_sample": (stderr or "")[-4096:] if stderr else None,
    }


def _run_subprocess_sync(
    cmd: list[str],
    timeout: float,
    log_prefix: str,
) -> tuple[int, bytes, bytes]:
    """Execute a subprocess synchronously with strict timeout, clean termination, and bounded stderr.

    Using standard subprocess.Popen inside a worker thread avoids Windows event loop
    incompatibilities (such as NotImplementedError under SelectorEventLoop).
    """
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        _, stderr = proc.communicate(timeout=timeout)
        bounded_stderr = (stderr or b"")[-32768:]
        return proc.returncode, b"", bounded_stderr
    except subprocess.TimeoutExpired as to_err:
        logger.error(
            "%s Process PID %s timed out after %.1fs; terminating...",
            log_prefix,
            proc.pid,
            timeout,
        )
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "%s Process PID %s did not terminate cleanly; killing...",
                    log_prefix,
                    proc.pid,
                )
                proc.kill()
                proc.wait()
        except ProcessLookupError:
            pass
        raise FFmpegTimeoutError(
            f"Process '{cmd[0]}' timed out after {timeout:.1f}s"
        ) from to_err


async def run_subprocess_bounded(
    cmd: list[str],
    timeout: float,
    output_path: Path | None = None,
    log_prefix: str = "[subprocess]",
) -> tuple[int, bytes, bytes]:
    """Execute a subprocess asynchronously via worker thread with bounded timeout."""
    try:
        return await asyncio.to_thread(_run_subprocess_sync, cmd, timeout, log_prefix)
    except FFmpegTimeoutError:
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
        raise


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
    ffmpeg_bin = _resolve_binary("ffmpeg")
    ffprobe_bin = _resolve_binary("ffprobe")

    if not ffmpeg_bin:
        diag = _format_diagnostics(
            video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
            exc=FileNotFoundError("ffmpeg binary not found on PATH or environment")
        )
        logger.error("[compositor] FFmpeg binary unavailable: %s", diag)
        raise FileNotFoundError(f"FFmpeg binary not found on PATH: {diag}")

    if not ffprobe_bin:
        diag = _format_diagnostics(
            video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
            exc=FileNotFoundError("ffprobe binary not found on PATH or environment")
        )
        logger.error("[compositor] FFprobe binary unavailable: %s", diag)
        raise FileNotFoundError(f"FFprobe binary not found on PATH: {diag}")

    # Validate input assets before starting composition
    if not video_mp4.exists() or video_mp4.stat().st_size == 0:
        diag = _format_diagnostics(
            video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
            exc=FileNotFoundError(f"Input visual video missing or 0 bytes: {video_mp4}")
        )
        logger.error("[compositor] Input visual video invalid: %s", diag)
        raise FileNotFoundError(f"Input visual video missing or 0 bytes: {video_mp4}")

    if not audio_wav.exists() or audio_wav.stat().st_size == 0:
        diag = _format_diagnostics(
            video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
            exc=FileNotFoundError(f"Input narration audio missing or 0 bytes: {audio_wav}")
        )
        logger.error("[compositor] Input narration audio invalid: %s", diag)
        raise FileNotFoundError(f"Input narration audio missing or 0 bytes: {audio_wav}")

    has_subtitles = bool(
        subtitles_srt
        and Path(subtitles_srt).exists()
        and Path(subtitles_srt).stat().st_size > 0
    )

    # 1. Primary composition: H.264 (yuv420p) + AAC (44.1kHz) + embedded subtitles (mov_text)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-nostdin",
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

    primary_err = None
    try:
        returncode, _, stderr = await run_subprocess_bounded(
            cmd,
            timeout=video_timeout,
            output_path=output_mp4,
            log_prefix="[compositor][primary]",
        )
        if returncode == 0 and output_mp4.exists() and output_mp4.stat().st_size > 0:
            # Validate output artifact streams
            validation = validate_video_artifact(output_mp4, expect_audio=True)
            logger.info(
                "[compositor] Successfully composited video with H.264/AAC (subtitles=%s, duration=%.2fs): %s",
                has_subtitles,
                validation["duration"],
                output_mp4,
            )
            return output_mp4
        else:
            primary_err = stderr.decode(errors="replace")
            diag = _format_diagnostics(
                video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
                returncode=returncode, stderr=primary_err
            )
            logger.warning("[compositor] Primary composition attempt failed. Diagnostics: %s", diag)
    except FFmpegTimeoutError:
        logger.error("[compositor] Primary composition exceeded timeout of %.1fs", video_timeout)
        raise
    except Exception as exc:
        diag = _format_diagnostics(
            video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
            exc=exc
        )
        logger.warning("[compositor] Primary composition attempt failed with exception: %s", diag)
        primary_err = str(exc)

    # 2. Fallback attempt: composite without subtitle stream (pure audio + video)
    fallback_cmd = [
        ffmpeg_bin,
        "-y",
        "-nostdin",
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

    fallback_err = None
    try:
        returncode2, _, stderr2 = await run_subprocess_bounded(
            fallback_cmd,
            timeout=video_timeout,
            output_path=output_mp4,
            log_prefix="[compositor][fallback]",
        )
        if returncode2 == 0 and output_mp4.exists() and output_mp4.stat().st_size > 0:
            validation = validate_video_artifact(output_mp4, expect_audio=True)
            logger.info(
                "[compositor] Successfully composited video via fallback (duration=%.2fs): %s",
                validation["duration"],
                output_mp4,
            )
            return output_mp4
        else:
            fallback_err = stderr2.decode(errors="replace")
            diag = _format_diagnostics(
                video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
                returncode=returncode2, stderr=fallback_err
            )
            logger.warning("[compositor] Fallback composition failed. Diagnostics: %s", diag)
    except FFmpegTimeoutError:
        logger.error("[compositor] Fallback composition exceeded timeout of %.1fs", video_timeout)
        raise
    except Exception as exc:
        diag = _format_diagnostics(
            video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
            exc=exc
        )
        logger.warning("[compositor] Fallback composition failed with exception: %s", diag)
        fallback_err = str(exc)

    # Do not silently copy the video track without audio to fake success
    total_diag = _format_diagnostics(
        video_mp4, audio_wav, output_mp4, ffmpeg_bin, ffprobe_bin,
        stderr=f"Primary: {primary_err} | Fallback: {fallback_err}"
    )
    logger.error("[compositor] All composition attempts failed. Diagnostics: %s", total_diag)
    raise RuntimeError(
        f"Video composition failed for primary and fallback. "
        f"Primary error: {primary_err}. Fallback error: {fallback_err}. "
        f"Diagnostics: {total_diag}"
    )


def composite_remedial_video_sync(
    video_mp4: Path,
    audio_wav: Path,
    output_mp4: Path,
    subtitles_srt: Path | None = None,
) -> Path:
    """Synchronous wrapper for composite_remedial_video."""
    return asyncio.run(composite_remedial_video(video_mp4, audio_wav, output_mp4, subtitles_srt))

