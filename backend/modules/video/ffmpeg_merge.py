"""FFmpeg pipeline: per-scene audio/video sync padding, concat, mux."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from modules.config import FINAL_VIDEO, PATHS, RenderWorkspace, get_logger

logger = get_logger(__name__)


def _workdir(workspace: RenderWorkspace | None) -> Path:
    if workspace is not None:
        workspace.tmp_dir.mkdir(parents=True, exist_ok=True)
        return workspace.tmp_dir
    return PATHS["renders"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _probe_duration(path: Path) -> float:
    """Return media duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr}")
    return float(json.loads(result.stdout)["format"]["duration"])


def _pad_video_to_duration(video: Path, target_seconds: float, out: Path) -> Path:
    """Pad video to target duration by freezing the last frame (no audio touched)."""
    cur = _probe_duration(video)
    if abs(cur - target_seconds) < 0.05:
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                   "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an", str(out),
        ]
    elif cur < target_seconds:
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"tpad=stop_mode=clone:stop_duration={(target_seconds - cur):.3f}",
            "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an", str(out),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-t", f"{target_seconds:.3f}",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                   "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an", str(out),
        ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg pad failed: {result.stderr[:500]}")
    return out


def sync_scene_av(
    video: Path,
    audio: Path,
    workdir: Path | None = None,
) -> Path:
    """Produce a per-scene MP4 where video duration == audio duration."""
    workdir = workdir or PATHS["renders"]
    workdir.mkdir(parents=True, exist_ok=True)
    audio_dur = _probe_duration(audio)
    synced = workdir / f"{video.stem}_synced.mp4"
    _pad_video_to_duration(video, audio_dur, synced)
    final = workdir / f"{video.stem}_av.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(synced), "-i", str(audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(final),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg mux per-scene failed: {result.stderr[:500]}")
    synced.unlink(missing_ok=True)
    return final


# ---------------------------------------------------------------------------
# Concat + final
# ---------------------------------------------------------------------------


def _concat_scenes(
    scene_files: list[Path],
    output: Path,
    workdir: Path | None = None,
) -> Path:
    """Concatenate per-scene AV MP4s into the final video."""
    workdir = workdir or PATHS["renders"]
    workdir.mkdir(parents=True, exist_ok=True)
    list_file = workdir / "concat_list.txt"
    with open(list_file, "w") as f:
        for sf in scene_files:
            f.write(f"file '{sf.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]
    logger.info("Concatenating %d AV scenes into %s", len(scene_files), output)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr[:500]}")
    list_file.unlink(missing_ok=True)
    return output


def merge(
    scene_mp4s: list[Path],
    scene_wavs: list[Path],
    output: Path | None = None,
    workspace: RenderWorkspace | None = None,
) -> Path:
    """Sync each scene's audio to its video, then concat into the final MP4."""
    output = output or FINAL_VIDEO
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = _workdir(workspace)

    if not scene_mp4s:
        raise ValueError("No scene videos to merge")
    if len(scene_mp4s) != len(scene_wavs):
        raise ValueError("Mismatched scene mp4 and wav counts")

    synced_scenes: list[Path] = []
    for mp4, wav in zip(scene_mp4s, scene_wavs):
        v_dur = _probe_duration(mp4)
        a_dur = _probe_duration(wav)
        logger.info(
            "Syncing %s (video=%.2fs -> audio=%.2fs) workdir=%s",
            mp4.name, v_dur, a_dur, tmp,
        )
        synced_scenes.append(sync_scene_av(mp4, wav, workdir=tmp))

    final = _concat_scenes(synced_scenes, output, workdir=tmp)
    logger.info("Final video duration: %.2fs", _probe_duration(final))
    for sf in synced_scenes:
        sf.unlink(missing_ok=True)

    logger.info("Final video: %s", final)
    return final
