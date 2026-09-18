"""Audio-Visual Multiplexer and Subtitle Generator for Step 3.

Combines rendered visual clips and synthesized voiceovers into standard MP4 files
(H.264/AAC) using imageio-ffmpeg, and creates synchronized WebVTT subtitle files.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Tuple

import imageio_ffmpeg

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
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

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


def mux_audio_and_video(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> Path:
    """Mux a video stream and audio track into a standard H.264/AAC MP4 file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

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
        "-shortest",
        str(output_path),
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"[muxer] FFmpeg muxing failed: {result.stderr}")
        raise RuntimeError(f"FFmpeg muxing failed: {result.stderr[:200]}")

    return output_path
