"""Video Matrix — Phase 3a: The Keyframe Vision Pipeline (The Visuals).

OpenCV grabs one frame every `frame_interval_seconds` (default 12s) from the
video. Perceptual dedupe ensures consecutive frames whose mean pixel difference
is below the similarity threshold represent the same static slide/board and are
skipped — a 1-hour lecture of writing on a board collapses efficiently.

Each kept frame is handed to `describe_frame` (Vision Engine) which transcribes
equations, bullet points and diagrams, and the result is tagged with the exact
clock time the frame was captured.
"""

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from ...core.config import settings


@dataclass
class FrameCapture:
    """One captured keyframe: when it happened + raw JPEG bytes for the API."""

    timestamp: float
    frame_bytes: bytes | None = None
    description: str = field(default="", init=False)  # filled by the pipeline


def extract_frames(video_path: Path) -> list[FrameCapture]:
    """Sample the video every N seconds, deduping near-identical frames."""
    if settings.frame_interval_seconds <= 0:
        raise ValueError("FRAME_INTERVAL_SECONDS must be positive")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if total_frames > 0 else 0.0

    captures: list[FrameCapture] = []
    prev_thumb: np.ndarray | None = None
    ts = 0.0

    while ts < duration or not captures:
        # Seek directly to the sampled time — no need to decode everything.
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * fps))
        ok, frame = cap.read()
        if not ok:
            break

        # Dedupe: compare a tiny grayscale thumbnail against the last kept one.
        thumb = cv2.resize(frame, (32, 32))
        thumb_gray = cv2.cvtColor(thumb, cv2.COLOR_BGR2GRAY)
        if prev_thumb is not None:
            diff = float(np.mean(np.abs(thumb_gray.astype(np.int16) - prev_thumb.astype(np.int16)))) / 255.0
            if diff < settings.video_frame_similarity_threshold:
                ts += settings.frame_interval_seconds
                continue
        prev_thumb = thumb_gray

        ok_enc, buf = cv2.imencode(".jpg", frame)
        if ok_enc:
            captures.append(FrameCapture(timestamp=round(ts, 1), frame_bytes=buf.tobytes()))
        ts += settings.frame_interval_seconds

    cap.release()
    return captures