"""Audio-Visual Multiplexer and Subtitle Generator for Step 3.

Combines rendered visual clips and synthesized voiceovers into standard MP4 files
(H.264/AAC) using imageio-ffmpeg, and creates synchronized WebVTT subtitle files.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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


def _format_vtt_timestamp(seconds: float) -> str:
    """Format seconds into WebVTT timestamp: HH:MM:SS.mmm."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def generate_webvtt_subtitles(
    script: VideoScript,
    scene_durations: List[float],
    output_path: Path,
) -> Path:
    """Generate a clean WebVTT subtitle file for HTML5 video player integration."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = ["WEBVTT", ""]

    current_time = 0.0
    for idx, (scene, dur) in enumerate(zip(script.scenes, scene_durations), start=1):
        start_str = _format_vtt_timestamp(current_time)
        end_time = current_time + dur
        end_str = _format_vtt_timestamp(end_time)

        lines.append(str(idx))
        lines.append(f"{start_str} --> {end_str}")
        # Clean narration text for subtitles
        lines.append(scene.narration.strip())
        lines.append("")

        current_time = end_time

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def concatenate_video_clips(clip_paths: List[Path], output_path: Path) -> Path:
    """Concatenate multiple scene video files into a single unified video stream."""
    if not clip_paths:
        raise ValueError("No video clips provided for concatenation.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = get_ffmpeg_exe()

    # Create a concat list file
    concat_list_file = output_path.parent / "concat_list.txt"
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for p in clip_paths:
            # Escape path for ffmpeg concat
            f.write(f"file '{p.resolve().as_posix()}'\n")

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_file),
        "-c",
        "copy",
        str(output_path),
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    finally:
        if concat_list_file.exists():
            concat_list_file.unlink()

    return output_path


def probe_media_duration(file_path: Path) -> float:
    """Probe exact media file duration using ffmpeg/ffprobe or wav header."""
    if not file_path.exists():
        return 0.0
    if file_path.suffix.lower() == ".wav":
        try:
            import wave
            with wave.open(str(file_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return round(frames / float(rate), 3)
        except Exception:
            return 0.0

    try:
        ffmpeg_exe = get_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-i", str(file_path)]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in result.stderr.splitlines():
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = parts.split(":")
                return round(int(h) * 3600 + int(m) * 60 + float(s), 3)
    except Exception as e:
        logger.warning(f"[muxer] Failed to probe duration for {file_path}: {e}")
    return 0.0


def mux_audio_and_video(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> Path:
    """Mux a video stream and audio track into a standard H.264/AAC MP4 file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = get_ffmpeg_exe()

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_path),
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"[muxer] FFmpeg muxing failed: {result.stderr}")
        raise RuntimeError(f"FFmpeg muxing failed: {result.stderr[:200]}")

    return output_path

