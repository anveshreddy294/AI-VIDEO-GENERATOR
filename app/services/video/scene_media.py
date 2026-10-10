"""Scene media operations used by the existing video engine.

Each scene owns its narration audio. Media boundaries are measured after
composition; no speech-recognition or planned-duration claim is substituted.
"""
from __future__ import annotations

import asyncio
import math
from pathlib import Path
from collections.abc import Callable

from ...core.config import settings
from .manim_renderer import render_video_plan
from .scene_schema import VideoPlan, SceneTimelineEntry
from .video_compositor import _resolve_binary, run_subprocess_bounded, probe_media, validate_video_artifact
from .whisper_alignment import _format_vtt_timestamp


async def assemble_scene_media(plan: VideoPlan, job_id: str, tts, progress: Callable) -> dict:
    ffmpeg = _resolve_binary("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFMPEG_UNAVAILABLE")
    for directory in (settings.renders_dir, settings.audio_dir, settings.captions_dir):
        directory.mkdir(parents=True, exist_ok=True)
    parts = []
    timeline = []
    cursor = 0.0
    fps = max(1, settings.video_default_fps)
    for index, scene in enumerate(plan.scenes):
        progress("GENERATING_AUDIO", f"Narrating scene {index+1}/{len(plan.scenes)}", 25+int(index/len(plan.scenes)*55))
        narration = " ".join(s.text for s in plan.narration if s.scene_index == index).strip()
        if not narration:
            raise ValueError("SCENE_NARRATION_MISSING")
        audio = settings.audio_dir / f"{job_id}_{index}.wav"
        await asyncio.wait_for(tts.generate_audio(narration, audio, target_seconds=scene.duration_seconds),
                               timeout=settings.video_timeout)
        info = await asyncio.to_thread(probe_media, audio)
        audio_duration = float(info.get("format", {}).get("duration", 0))
        if not math.isfinite(audio_duration) or audio_duration <= 0 or not any(
                s.get("codec_type") == "audio" for s in info.get("streams", [])):
            raise ValueError("SCENE_AUDIO_INVALID")
        duration = math.ceil(max(scene.duration_seconds, audio_duration)*fps)/fps
        if duration > 120 or cursor+duration > 600:
            raise ValueError("VIDEO_DURATION_LIMIT")
        single = plan.model_copy(deep=True)
        selected = scene.model_copy(deep=True, update={"scene_index": 0, "duration_seconds": duration})
        single.scenes = [selected]
        single.narration = [s.model_copy(update={"scene_index": 0}) for s in plan.narration if s.scene_index == index]
        single.duration_seconds = math.ceil(duration)
        raw = settings.renders_dir / f"{job_id}_{index}_visual.mp4"
        progress("RENDERING", f"Animating scene {index+1}/{len(plan.scenes)}", 30+int(index/len(plan.scenes)*55))
        await asyncio.to_thread(render_video_plan, single, raw)
        part = settings.renders_dir / f"{job_id}_{index}_scene.mp4"
        command = [ffmpeg,"-y","-i",str(raw),"-i",str(audio),"-map","0:v:0","-map","1:a:0",
                   "-vf",f"tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},setpts=PTS-STARTPTS",
                   "-af",f"apad,atrim=duration={duration},asetpts=PTS-STARTPTS", "-r",str(fps),
                   "-c:v","libx264","-preset",settings.ffmpeg_preset,"-pix_fmt","yuv420p",
                   "-c:a","aac","-ar","44100","-ac","2","-movflags","+faststart",str(part)]
        code, _, _ = await run_subprocess_bounded(command, timeout=settings.video_timeout,
                                                  output_path=part, log_prefix="[scene-media]")
        if code:
            raise RuntimeError("SCENE_COMPOSITION_FAILED")
        measured = await asyncio.to_thread(validate_video_artifact, part, True)
        seconds = float(measured["duration"])
        if not math.isfinite(seconds) or abs(seconds-duration) > 0.15:
            raise ValueError("SCENE_TIMING_INVALID")
        timeline.append(SceneTimelineEntry(scene_id=scene.scene_id, scene_index=index,
            start_seconds=cursor, end_seconds=cursor+seconds, duration_seconds=seconds))
        cursor += seconds
        parts.append(part)
    progress("COMPOSITING", "Assembling measured scene timeline", 90)
    manifest = settings.renders_dir / f"{job_id}_concat.txt"
    manifest.write_text("\n".join("file '" + str(p.resolve()).replace("\\", "/").replace("'", "'\\''") + "'" for p in parts), encoding="utf-8")
    final = settings.renders_dir / f"{job_id}.mp4"
    code, _, _ = await run_subprocess_bounded(
        [ffmpeg,"-y","-f","concat","-safe","0","-i",str(manifest),"-c","copy","-movflags","+faststart",str(final)],
        timeout=settings.video_timeout, output_path=final, log_prefix="[scene-concat]")
    if code:
        raise RuntimeError("VIDEO_COMPOSITION_FAILED")
    validation = await asyncio.to_thread(validate_video_artifact, final, True)
    final_duration = float(validation["duration"])
    if not math.isfinite(final_duration) or abs(final_duration-cursor) > 0.15:
        raise ValueError("FINAL_TIMELINE_MISMATCH")
    timeline[-1].end_seconds = final_duration
    timeline[-1].duration_seconds = final_duration-timeline[-1].start_seconds
    if timeline[-1].duration_seconds <= 0:
        raise ValueError("FINAL_TIMELINE_MISMATCH")
    vtt = settings.captions_dir / f"{job_id}.vtt"
    cues = ["WEBVTT", ""]
    for entry, scene in zip(timeline, plan.scenes):
        text = " ".join(s.text for s in plan.narration if s.scene_index == scene.scene_index)
        cues.extend([f"{_format_vtt_timestamp(entry.start_seconds)} --> {_format_vtt_timestamp(entry.end_seconds)}",
                     text.replace("-->", "→").replace("<", "&lt;").replace(">", "&gt;"), ""])
    vtt.write_text("\n".join(cues), encoding="utf-8")
    return {"video_path":str(final), "subtitle_path":str(vtt), "duration":final_duration,
            "timeline":timeline, "validation":validation}
