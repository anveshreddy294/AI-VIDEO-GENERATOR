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

Each phase is wrapped in error handling so a failure in one phase degrades
gracefully rather than killing the entire upload.
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
        print(f"[video] Phase 1: Extracting audio from {video_path.name}...")
        try:
            extract_audio(video_path, audio_path)
        except Exception as exc:
            print(f"[video] Phase 1 FAILED (audio extraction): {exc}")
            # If we can't extract audio, we can still try the visual pipeline.
            return _visuals_only(video_path)

        # Phase 2: the speech.
        print(f"[video] Phase 2: Transcribing audio...")
        try:
            segments = transcribe_with_timestamps(audio_path)
            print(f"[video] Phase 2: Got {len(segments)} speech segments.")
        except Exception as exc:
            print(f"[video] Phase 2 FAILED (transcription): {exc}")
            segments = []

        # Phase 3: the visuals.
        print(f"[video] Phase 3: Extracting keyframes...")
        try:
            captures = extract_frames(video_path)
            print(f"[video] Phase 3: Got {len(captures)} keyframes.")
        except Exception as exc:
            print(f"[video] Phase 3 FAILED (frame extraction): {exc}")
            captures = []

        # Phase 3b: Describe each frame via Gemini Vision.
        described: list[FrameCapture] = []
        for i, cap in enumerate(captures):
            if cap.frame_bytes is not None:
                try:
                    desc = describe_frame(cap.frame_bytes, cap.timestamp)
                    cap.description = desc  # set post-init (description is init=False)
                    described.append(cap)
                except Exception as exc:
                    print(f"[video] Phase 3b FAILED for frame {i} @{cap.timestamp}s: {exc}")
                    # Keep the frame with a placeholder description
                    cap.description = f"[Frame at {cap.timestamp:.0f}s — vision description unavailable]"
                    described.append(cap)

        print(f"[video] Phase 3b: Described {len(described)}/{len(captures)} frames.")

        # Phase 4: fuse speech + visuals chronologically.
        print(f"[video] Phase 4: Fusing speech ({len(segments)} segments) + visuals ({len(described)} frames)...")
        result = fuse(segments, described)
        print(f"[video] Done. Output: {len(result)} chars.")
        return result
    finally:
        audio_path.unlink(missing_ok=True)  # the extracted track is always cleaned up


def _visuals_only(video_path: Path) -> str:
    """Fallback: extract visuals only when audio extraction fails."""
    try:
        captures = extract_frames(video_path)
        described: list[FrameCapture] = []
        for cap in captures:
            if cap.frame_bytes is not None:
                try:
                    desc = describe_frame(cap.frame_bytes, cap.timestamp)
                    cap.description = desc
                    described.append(cap)
                except Exception:
                    cap.description = f"[Frame at {cap.timestamp:.0f}s — unavailable]"
                    described.append(cap)
        return fuse([], described)  # empty speech segments
    except Exception as exc:
        return f"[Video processing error: could not extract any content from {video_path.name}: {exc}]"


def describe_frame(image_bytes: bytes, timestamp: float) -> str:
    """Small indirection so the vision call stays where the other prompts live
    (vision.py) without the pipeline importing Gemini directly."""
    from ..vision import describe_frame as _describe

    return _describe(image_bytes, source=f"frame@{timestamp}s")
