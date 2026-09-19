"""Video Matrix — orchestrator returning normalized ContentUnits.

Chains FFmpeg audio extraction, Whisper ASR, OpenCV keyframes, Gemini Vision,
and multimodal fusion into normalized ContentUnits.
"""

import logging
from pathlib import Path

from ...core.config import settings
from ..schemas import ContentUnit
from .av_splitter import extract_audio
from .frame_extractor import FrameCapture, extract_frames
from .fusion import fuse_units
from .transcriber import transcribe_with_timestamps

logger = logging.getLogger(__name__)


def process_video_units(
    video_path: Path, source_id: str, asset_id: str
) -> list[ContentUnit]:
    """Extract and fuse video content into normalized ContentUnits."""
    audio_path = settings.processed_dir / f"{video_path.stem}_audio.wav"
    try:
        # Phase 1: Split audio track
        logger.info("[video] Phase 1: Extracting audio from %s...", video_path.name)
        try:
            extract_audio(video_path, audio_path)
        except Exception as exc:
            logger.warning("[video] Phase 1 FAILED (audio extraction): %s", exc)
            return _visuals_only_units(video_path, source_id, asset_id)

        # Phase 2: Transcribe speech
        logger.info("[video] Phase 2: Transcribing audio...")
        try:
            segments = transcribe_with_timestamps(audio_path)
            logger.info("[video] Phase 2: Got %d speech segments.", len(segments))
        except Exception as exc:
            logger.warning("[video] Phase 2 FAILED (transcription): %s", exc)
            segments = []

        # Phase 3: Keyframe extraction
        logger.info("[video] Phase 3: Extracting keyframes...")
        try:
            captures = extract_frames(video_path)
            logger.info("[video] Phase 3: Got %d keyframes.", len(captures))
        except Exception as exc:
            logger.warning("[video] Phase 3 FAILED (frame extraction): %s", exc)
            captures = []

        # Phase 3b: Describe keyframes via Gemini Vision
        described: list[FrameCapture] = []
        for i, cap in enumerate(captures):
            if cap.frame_bytes is not None:
                try:
                    desc = describe_frame(cap.frame_bytes, cap.timestamp)
                    cap.description = desc
                    described.append(cap)
                except Exception as exc:
                    logger.warning("[video] Phase 3b FAILED for frame %d @%ss: %s", i, cap.timestamp, exc)
                    cap.description = (
                        f"[Frame at {cap.timestamp:.0f}s — vision description unavailable]"
                    )
                    described.append(cap)

        # Phase 4: Multimodal fusion into ContentUnits
        return fuse_units(segments, described, source_id=source_id, asset_id=asset_id)

    finally:
        audio_path.unlink(missing_ok=True)


def _visuals_only_units(
    video_path: Path, source_id: str, asset_id: str
) -> list[ContentUnit]:
    try:
        captures = extract_frames(video_path)
        described: list[FrameCapture] = []
        for cap in captures:
            if cap.frame_bytes is not None:
                try:
                    desc = describe_frame(cap.frame_bytes, cap.timestamp)
                    cap.description = desc
                    described.append(cap)
                except Exception as exc:
                    logger.warning("[video] Frame description failed @%ss: %s", cap.timestamp, exc)
                    cap.description = f"[Frame at {cap.timestamp:.0f}s — unavailable]"
                    described.append(cap)
        return fuse_units([], described, source_id=source_id, asset_id=asset_id)
    except Exception as exc:
        logger.error("[video] _visuals_only_units failed: %s", exc)
        return [
            ContentUnit(
                source_id=source_id,
                asset_id=asset_id,
                modality="video",
                text=f"[Video processing error: {exc}]",
                sequence_index=0,
                extraction_method="video_error",
                confidence_score=0.0,
            )
        ]


def process_video(video_path: Path) -> str:
    """Legacy helper returning plain authoritative text string."""
    units = process_video_units(
        video_path, source_id="SRC_LEGACY", asset_id="AST_LEGACY"
    )
    return "\n\n".join(u.text for u in units)


def describe_frame(image_bytes: bytes, timestamp: float) -> str:
    from ..vision import describe_frame as _describe

    return _describe(image_bytes, source=f"frame@{timestamp}s")
