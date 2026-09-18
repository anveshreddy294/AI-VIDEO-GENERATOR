"""Visual composition and frame rendering engine for Step 3.

Renders 1080p (1920x1080) educational video cards using Pillow and OpenCV,
featuring modern dark-mode aesthetics, dynamic typography, source diagram embedding,
and smooth animated progress bars.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ...core.config import settings
from ...services.registry import get_content_units
from ...services.schemas import ContentUnit
from .schemas import VideoScene, VideoScript

logger = logging.getLogger(__name__)

# Video Dimensions
WIDTH = 1920
HEIGHT = 1080
FPS = 24

# Color Palette (Deep Space Navy, Indigo, Cyan, Slate)
COLOR_BG_DARK = (15, 23, 42)         # #0F172A
COLOR_CARD_BG = (30, 41, 59)         # #1E293B
COLOR_CARD_BORDER = (51, 65, 85)     # #334155
COLOR_TEXT_PRIMARY = (248, 250, 252) # #F8FAFC
COLOR_TEXT_MUTED = (148, 163, 184)   # #94A3B8
COLOR_ACCENT_BLUE = (59, 130, 246)   # #3B82F6
COLOR_ACCENT_INDIGO = (99, 102, 241) # #6366F1
COLOR_ACCENT_CYAN = (6, 182, 212)    # #06B6D4
COLOR_ACCENT_AMBER = (245, 158, 11)  # #F59E0B
COLOR_ACCENT_GREEN = (16, 185, 129)  # #10B981


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a clean system font (Segoe UI or Arial) with safe default fallback."""
    font_candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for p in font_candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _draw_rounded_rectangle(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int, int, int],
    radius: int,
    fill: Tuple[int, int, int],
    outline: Optional[Tuple[int, int, int]] = None,
    width: int = 1,
) -> None:
    """Draw a smooth rounded rectangle on Pillow ImageDraw."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _resolve_diagram_path(source_id: str, diagram_cu_id: Optional[str]) -> Optional[Path]:
    """Find the local disk path of an embedded diagram if referenced."""
    if not diagram_cu_id:
        return None

    units = get_content_units(source_id)
    for u in units:
        if u.content_id == diagram_cu_id:
            img_path = getattr(u, "image_path", None)
            if img_path:
                p = Path(img_path)
                if p.exists():
                    return p
            break
    return None


def render_scene_frame(
    scene: VideoScene,
    concept_name: str,
    difficulty: str,
    scene_idx: int,
    total_scenes: int,
    source_id: str,
    progress_ratio: float = 0.0,
) -> Image.Image:
    """Render a 1080p still frame for a given scene with high-contrast typography."""
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG_DARK)
    draw = ImageDraw.Draw(img)

    # 1. Top Gradient Accent Bar
    for y in range(8):
        interp = y / 8.0
        r = int(COLOR_ACCENT_INDIGO[0] * (1 - interp) + COLOR_ACCENT_CYAN[0] * interp)
        g = int(COLOR_ACCENT_INDIGO[1] * (1 - interp) + COLOR_ACCENT_CYAN[1] * interp)
        b = int(COLOR_ACCENT_INDIGO[2] * (1 - interp) + COLOR_ACCENT_CYAN[2] * interp)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # 2. Header Badges
    font_badge = _get_font(20, bold=True)
    font_title = _get_font(44, bold=True)
    font_body = _get_font(28, bold=False)
    font_highlight = _get_font(30, bold=True)
    font_small = _get_font(18, bold=False)

    badge_text = f"TARGETED REMEDIATION • {difficulty.upper()} • SCENE {scene_idx}/{total_scenes}"
    _draw_rounded_rectangle(draw, (80, 45, 80 + len(badge_text) * 12 + 30, 85), radius=8, fill=(30, 58, 138), outline=COLOR_ACCENT_BLUE)
    draw.text((95, 52), badge_text, font=font_badge, fill=COLOR_ACCENT_CYAN)

    # Concept Label & Scene Title
    concept_label = f"Concept: {concept_name}"
    draw.text((WIDTH - 80 - len(concept_label) * 13, 52), concept_label, font=font_badge, fill=COLOR_TEXT_MUTED)

    draw.text((80, 110), scene.title, font=font_title, fill=COLOR_TEXT_PRIMARY)

    # 3. Check for diagram asset
    diagram_path = _resolve_diagram_path(source_id, scene.diagram_cu_id)
    has_diagram = diagram_path is not None and diagram_path.exists()

    # Layout dimensions
    content_width = 1060 if has_diagram else 1760

    # 4. Main Content Card (Left Column)
    card_top = 190
    card_bottom = 980
    _draw_rounded_rectangle(
        draw,
        (80, card_top, 80 + content_width, card_bottom),
        radius=16,
        fill=COLOR_CARD_BG,
        outline=COLOR_CARD_BORDER,
        width=2,
    )

    # 5. Render Bullet Points inside Card
    bullet_y = card_top + 45
    for i, bullet in enumerate(scene.onscreen_bullets):
        if bullet_y > card_bottom - 220:
            break
        # Bullet indicator icon (circle)
        draw.ellipse([(120, bullet_y + 8), (136, bullet_y + 24)], fill=COLOR_ACCENT_BLUE)
        # Bullet text
        draw.text((155, bullet_y), bullet, font=font_body, fill=COLOR_TEXT_PRIMARY)
        bullet_y += 65

    # 6. Emphasized Highlight Card / Formula Callout
    if scene.highlight_text:
        callout_top = max(bullet_y + 25, card_bottom - 210)
        callout_bottom = card_bottom - 35
        _draw_rounded_rectangle(
            draw,
            (115, callout_top, 80 + content_width - 35, callout_bottom),
            radius=12,
            fill=(24, 38, 66),
            outline=COLOR_ACCENT_INDIGO,
            width=2,
        )
        # Accent left line
        draw.line([(120, callout_top + 10), (120, callout_bottom - 10)], fill=COLOR_ACCENT_CYAN, width=4)
        draw.text((140, callout_top + 15), "KEY MASTERY RULE:", font=font_small, fill=COLOR_ACCENT_AMBER)
        draw.text((140, callout_top + 45), scene.highlight_text, font=font_highlight, fill=COLOR_TEXT_PRIMARY)

    # 7. Diagram Column (Right Column if present)
    if has_diagram:
        diagram_box_left = 80 + content_width + 40
        diagram_box_right = WIDTH - 80
        _draw_rounded_rectangle(
            draw,
            (diagram_box_left, card_top, diagram_box_right, card_bottom),
            radius=16,
            fill=COLOR_CARD_BG,
            outline=COLOR_CARD_BORDER,
            width=2,
        )
        draw.text((diagram_box_left + 30, card_top + 25), "SOURCE MATERIAL DIAGRAM", font=font_badge, fill=COLOR_TEXT_MUTED)

        try:
            with Image.open(diagram_path) as diag_img:
                diag_img = diag_img.convert("RGB")
                max_w = diagram_box_right - diagram_box_left - 60
                max_h = card_bottom - card_top - 100
                diag_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                paste_x = diagram_box_left + (diagram_box_right - diagram_box_left - diag_img.width) // 2
                paste_y = card_top + 70 + (max_h - diag_img.height) // 2
                img.paste(diag_img, (paste_x, paste_y))
        except Exception as err:
            logger.warning(f"[visual_renderer] Failed embedding diagram: {err}")

    # 8. Bottom Progress Bar
    bar_y = HEIGHT - 20
    bar_height = 8
    draw.rectangle([(0, bar_y), (WIDTH, bar_y + bar_height)], fill=(30, 41, 59))
    active_width = int(WIDTH * max(0.0, min(1.0, progress_ratio)))
    if active_width > 0:
        draw.rectangle([(0, bar_y), (active_width, bar_y + bar_height)], fill=COLOR_ACCENT_CYAN)

    return img


def render_scene_to_video_clip(
    scene: VideoScene,
    duration_seconds: float,
    output_path: Path,
    concept_name: str,
    difficulty: str,
    scene_idx: int,
    total_scenes: int,
    source_id: str,
    start_progress: float,
    end_progress: float,
    fps: int = FPS,
) -> Path:
    """Render an MP4 video clip for a single scene with animated progress bar and fade-in."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = max(1, int(duration_seconds * fps))

    # Pre-render start and end keyframes
    start_frame = render_scene_frame(
        scene=scene,
        concept_name=concept_name,
        difficulty=difficulty,
        scene_idx=scene_idx,
        total_scenes=total_scenes,
        source_id=source_id,
        progress_ratio=start_progress,
    )
    base_frame_bgr = cv2.cvtColor(np.array(start_frame), cv2.COLOR_RGB2BGR)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (WIDTH, HEIGHT))

    fade_frames = min(fps // 2, total_frames // 4)

    for i in range(total_frames):
        current_progress = start_progress + (end_progress - start_progress) * (i / max(1, total_frames - 1))

        # Re-render frame every few ticks to update progress bar smoothly
        if i % (fps // 2) == 0:
            frame_pil = render_scene_frame(
                scene=scene,
                concept_name=concept_name,
                difficulty=difficulty,
                scene_idx=scene_idx,
                total_scenes=total_scenes,
                source_id=source_id,
                progress_ratio=current_progress,
            )
            base_frame_bgr = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)

        frame = base_frame_bgr.copy()

        # Fade in transition for first half second
        if i < fade_frames and scene_idx > 1:
            alpha = float(i) / fade_frames
            frame = (frame * alpha).astype(np.uint8)

        writer.write(frame)

    writer.release()
    return output_path
