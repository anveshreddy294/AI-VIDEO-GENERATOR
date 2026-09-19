"""Video Matrix — Phase 4: Multimodal Fusion Engine into ContentUnits.

Merges timestamped transcript segments and keyframe descriptions into
normalized ContentUnits.
"""

from ..schemas import ContentUnit
from .frame_extractor import FrameCapture
from .transcriber import Segment

_SHRUG_SECONDS = 2.0  # jitter tolerance when matching frames to segments


def fmt_timestamp(seconds: float) -> str:
    """Render 87.4 -> '01:27'."""
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def fuse_units(
    segments: list[Segment],
    frames: list[FrameCapture],
    source_id: str,
    asset_id: str,
) -> list[ContentUnit]:
    """Stitch speech + visuals into a list of normalized ContentUnits."""
    units: list[ContentUnit] = []
    seq_index = 0

    if not segments:
        for f in frames:
            unit = ContentUnit(
                source_id=source_id,
                asset_id=asset_id,
                modality="video",
                text=f"Visible on screen: {f.description}",
                visual_description=f.description,
                timestamp_start=f.timestamp,
                timestamp_end=f.timestamp + 2.0,
                frame_id=f"FRAME_{int(f.timestamp)}",
                sequence_index=seq_index,
                extraction_method="opencv_vision",
                confidence_score=0.90,
            )
            units.append(unit)
            seq_index += 1
        units.sort(key=lambda unit: unit.timestamp_start if unit.timestamp_start is not None else 0)
    for index, unit in enumerate(units):
        unit.sequence_index = index
    return units

    frames_used = [False] * len(frames)

    for seg in segments:
        visible: list[FrameCapture] = []
        for i, f in enumerate(frames):
            if (
                not frames_used[i]
                and seg.start - _SHRUG_SECONDS <= f.timestamp <= seg.end + _SHRUG_SECONDS
            ):
                frames_used[i] = True
                visible.append(f)

        vis_desc = (
            " | ".join(
                f"Visible at {fmt_timestamp(f.timestamp)}: {f.description}"
                for f in visible
            )
            if visible
            else None
        )
        full_text = f"[{fmt_timestamp(seg.start)} - {fmt_timestamp(seg.end)}] Spoken: \"{seg.text}\""
        if vis_desc:
            full_text += f"\n{vis_desc}"

        frame_id = (
            f"FRAME_{int(visible[0].timestamp)}" if visible else None
        )

        unit = ContentUnit(
            source_id=source_id,
            asset_id=asset_id,
            modality="video",
            text=full_text,
            visual_description=vis_desc,
            timestamp_start=seg.start,
            timestamp_end=seg.end,
            frame_id=frame_id,
            sequence_index=seq_index,
            extraction_method="whisper_gemini_fusion",
            confidence_score=0.95,
        )
        units.append(unit)
        seq_index += 1

    # Remaining frames outside speech segments
    for i, f in enumerate(frames):
        if not frames_used[i]:
            unit = ContentUnit(
                source_id=source_id,
                asset_id=asset_id,
                modality="video",
                text=f"[{fmt_timestamp(f.timestamp)} - {fmt_timestamp(f.timestamp)}] Visible on screen: {f.description}",
                visual_description=f.description,
                timestamp_start=f.timestamp,
                timestamp_end=f.timestamp + 2.0,
                frame_id=f"FRAME_{int(f.timestamp)}",
                sequence_index=seq_index,
                extraction_method="opencv_vision_gap",
                confidence_score=0.85,
            )
            units.append(unit)
            seq_index += 1

    units.sort(key=lambda unit: unit.timestamp_start if unit.timestamp_start is not None else 0)
    for index, unit in enumerate(units):
        unit.sequence_index = index
    return units