"""Video Matrix — the orchestrator.

Chains the five phases into one `process_video()` entry point that the Phase 1
Dispatcher routes `.mp4/.mov/.mkv` uploads to:

    Phase 1  av_splitter      FFmpeg: rip the audio track
    Phase 2  transcriber      faster-whisper: timestamped transcript
    Phase 3  frame_extractor  OpenCV keyframes -> Gemini Vision descriptions
    Phase 4  fusion           chronological merge of speech + visuals
    Phase 5  (upstream)       chunker + vector_store tag it as Layer A video

Returns the single massive, temporally-synced string that Phase 5 chunking
turns into ground truth.
"""

from pathlib import Path

from ...core.config import settings
from .av_splitter import extract_audio
from .frame_extractor import FrameCapture, extract_frames
from .fusion import fuse
from .transcriber import transcribe_with_timestamps


def process_video(video_path: Path) -> str:
    """Extract, transcribe, describe and fuse a video into authoritative text."""
    audio_path = settings.processed_dir / f"{video_path.stem}_audio.wav"
    try:
        # Phase 1: split the tracks.
        extract_audio(video_path, audio_path)

        # Phase 2: the speech.
        segments = transcribe_with_timestamps(audio_path)

        # Phase 3: the visuals.
        captures = extract_frames(video_path)
        described: list[FrameCapture] = []
        for cap in captures:
            if cap.frame_bytes is not None:
                desc = describe_frame(cap.frame_bytes, cap.timestamp)
                described.append(FrameCapture(timestamp=cap.timestamp, description=desc))

        # Phase 4: fuse speech + visuals chronologically.
        return fuse(segments, described)
    finally:
        audio_path.unlink(missing_ok=True)  # the extracted track is always cleaned up


def describe_frame(image_bytes: bytes, timestamp: float) -> str:
    """Small indirection so the vision call stays where the other prompts live
    (vision.py) without the pipeline importing Gemini directly."""
    from ..vision import describe_frame as _describe

    return _describe(image_bytes, source=f"frame@{timestamp}s")