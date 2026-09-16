"""Video Matrix — Phase 4: The Multimodal Fusion Engine.

Merges the timestamped transcript (what the professor *said*) with the
timestamped keyframe descriptions (what they *showed*) into unified,
chronological blocks:

    [01:15 - 01:30] Spoken: "Notice the equation here..."
    Visible at 01:2X: "Diagram of a block on an incline with F=ma written next to it."

Frames are attached to the spoken segment that was happening at their capture
time (with a ±2s shrug window for ASR/seek jitter), and each frame is consumed
once so a static slide doesn't repeat next to every segment it spans.
"""

from .frame_extractor import FrameCapture
from .transcriber import Segment

_SHRUG_SECONDS = 2.0  # jitter tolerance when matching frames to segments


def fmt_timestamp(seconds: float) -> str:
    """Render 87.4 -> '01:27'."""
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def fuse(segments: list[Segment], frames: list[FrameCapture]) -> str:
    """Stitch speech + visuals into one authoritative, timestamped string."""
    if not segments:
        # Lecture with no speech (e.g. a silent animation) — visuals alone.
        return "\n\n".join(
            f"[{fmt_timestamp(f.timestamp)} - {fmt_timestamp(f.timestamp)}] "
            f"Visible on screen: {f.description}"
            for f in frames
        )

    frames_used = [False] * len(frames)
    blocks: list[str] = []

    for seg in segments:
        # Attach every unused frame captured within this segment's window.
        visible: list[FrameCapture] = []
        for i, f in enumerate(frames):
            if not frames_used[i] and seg.start - _SHRUG_SECONDS <= f.timestamp <= seg.end + _SHRUG_SECONDS:
                frames_used[i] = True
                visible.append(f)

        line = f"[{fmt_timestamp(seg.start)} - {fmt_timestamp(seg.end)}] Spoken: \"{seg.text}\""
        if visible:
            visuals = " | ".join(
                f"Visible at {fmt_timestamp(f.timestamp)}: {f.description}" for f in visible
            )
            line += f"\n{visuals}"
        blocks.append(line)

    # Frames captured in silence gaps / after the final segment still matter.
    for i, f in enumerate(frames):
        if not frames_used[i]:
            blocks.append(
                f"[{fmt_timestamp(f.timestamp)} - {fmt_timestamp(f.timestamp)}] "
                f"Visible on screen: {f.description}"
            )

    return "\n\n".join(blocks)