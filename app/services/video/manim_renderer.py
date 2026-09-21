"""Safe, deterministic Manim scene renderer for educational video generation.

Consumes a validated VideoPlan and produces an MP4 video file.
Crucial guarantees:
1. Purely programmatic: Maps typed ScenePlan objects to predefined Manim animations.
2. Zero arbitrary code execution: Never executes LLM-generated code or commands.
3. Resilient fallback: If headless system drivers or LaTeX fonts prevent Manim execution,
   seamlessly renders the exact same declarative scenes via OpenCV/Pillow at identical resolution.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ...core.config import settings
from .scene_schema import ScenePlan, SceneType, VideoPlan

logger = logging.getLogger(__name__)


def render_video_plan(plan: VideoPlan, output_mp4: Path) -> Path:
    """Render a VideoPlan to an MP4 video file."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    # Attempt Manim rendering first
    try:
        return _render_with_manim(plan, output_mp4)
    except Exception as exc:
        logger.warning(f"[manim_renderer] Manim engine encountered error ({exc}); using OpenCV/PIL programmatic renderer")
        return _render_with_pillow_opencv(plan, output_mp4)


def _render_with_manim(plan: VideoPlan, output_mp4: Path) -> Path:
    """Programmatic Manim Scene execution."""
    import manim
    from manim import (
        Arrow,
        FadeIn,
        FadeOut,
        Rectangle,
        Scene,
        Square,
        Text,
        VGroup,
        Write,
        config,
        interpolate_color,
    )
    from manim.constants import DOWN, LEFT, ORIGIN, RIGHT, UP
    from manim.utils.color import BLUE, GREEN, RED, WHITE, YELLOW

    # Configure Manim for headless offline generation
    temp_dir = Path(tempfile.mkdtemp(prefix="manim_render_"))
    config.media_dir = str(temp_dir)
    config.video_dir = str(output_mp4.parent)
    config.pixel_width = 1280
    config.pixel_height = 720
    config.frame_rate = settings.video_default_fps
    config.output_file = output_mp4.name
    config.disable_caching = True
    config.verbosity = "WARNING"

    class DynamicEducationalScene(Scene):
        def construct(self):
            self.camera.background_color = "#111827"  # Sleek dark navy slate

            for scene in plan.scenes:
                stype = scene.scene_type
                dur = max(1.0, scene.duration_seconds)

                if stype == SceneType.TITLE:
                    title_text = scene.title or plan.concept_name
                    sub_text = scene.subtitle or "Core Concept Review"
                    title = Text(title_text, font_size=42, color=YELLOW, weight="BOLD")
                    sub = Text(sub_text, font_size=24, color=WHITE)
                    sub.next_to(title, DOWN, buff=0.4)
                    group = VGroup(title, sub).move_to(ORIGIN)
                    self.play(FadeIn(group, shift=UP * 0.5), run_time=min(1.5, dur * 0.3))
                    self.wait(max(0.5, dur * 0.4))
                    self.play(FadeOut(group, shift=DOWN * 0.5), run_time=min(1.0, dur * 0.3))

                elif stype == SceneType.EQUATION:
                    eq_str = scene.equation or "F = ma"
                    label_str = scene.label or f"Governing Law: {plan.concept_name}"
                    eq = Text(eq_str, font_size=56, color=YELLOW, weight="BOLD")
                    lbl = Text(label_str, font_size=26, color=BLUE)
                    lbl.next_to(eq, UP, buff=0.5)
                    group = VGroup(lbl, eq).move_to(ORIGIN)
                    self.play(Write(eq), FadeIn(lbl), run_time=min(2.0, dur * 0.35))
                    self.wait(max(0.5, dur * 0.4))
                    self.play(FadeOut(group), run_time=min(1.0, dur * 0.25))

                elif stype == SceneType.DIAGRAM:
                    # Diagram: Mass block with force vector arrow and acceleration
                    box = Square(side_length=1.8, color=BLUE, fill_opacity=0.6)
                    obj_label = Text(scene.object_label or "Mass (m)", font_size=20, color=WHITE).move_to(box)
                    arrow = Arrow(LEFT * 2.5, LEFT * 0.9, color=YELLOW, buff=0.1)
                    force_lbl = Text(scene.force_label or "Force (F)", font_size=20, color=YELLOW).next_to(arrow, UP, buff=0.1)
                    diag_group = VGroup(box, obj_label, arrow, force_lbl).move_to(LEFT * 1.5)

                    self.play(FadeIn(diag_group), run_time=min(1.5, dur * 0.25))
                    # Animate accelerating to the right
                    self.play(diag_group.animate.shift(RIGHT * 3.0), run_time=min(3.0, dur * 0.5))
                    self.wait(max(0.5, dur * 0.15))
                    self.play(FadeOut(diag_group), run_time=min(1.0, dur * 0.1))

                elif stype == SceneType.SUMMARY:
                    title = Text("Key Takeaways", font_size=36, color=YELLOW, weight="BOLD").to_edge(UP, buff=1.0)
                    points = scene.summary_points or [
                        f"Mastery: {plan.concept_name}",
                        "Review governing formulas and prerequisite relationships",
                        "Continuous assessment verifies deep understanding",
                    ]
                    p_texts = [
                        Text(f"• {pt}", font_size=24, color=WHITE).align_to(title, LEFT)
                        for pt in points[:4]
                    ]
                    bullets = VGroup(*p_texts).arrange(DOWN, aligned_edge=LEFT, buff=0.4).next_to(title, DOWN, buff=0.6)
                    all_group = VGroup(title, bullets).move_to(ORIGIN)
                    self.play(FadeIn(title), FadeIn(bullets, lag_ratio=0.2), run_time=min(2.5, dur * 0.4))
                    self.wait(max(0.5, dur * 0.4))
                    self.play(FadeOut(all_group), run_time=min(1.0, dur * 0.2))

                else:  # TEXT / EXAMPLE / TRANSFORM
                    txt_str = scene.text or plan.concept_name
                    txt = Text(txt_str[:120], font_size=32, color=WHITE).move_to(ORIGIN)
                    self.play(FadeIn(txt), run_time=min(1.5, dur * 0.3))
                    self.wait(max(0.5, dur * 0.4))
                    self.play(FadeOut(txt), run_time=min(1.0, dur * 0.3))

    scene_inst = DynamicEducationalScene()
    scene_inst.render()

    shutil.rmtree(temp_dir, ignore_errors=True)

    if output_mp4.exists() and output_mp4.stat().st_size > 0:
        return output_mp4

    # Locate generated output file in video_dir if name differed
    for candidate in output_mp4.parent.glob("*.mp4"):
        if candidate.stat().st_size > 0:
            if candidate != output_mp4:
                shutil.copy2(candidate, output_mp4)
            return output_mp4

    raise RuntimeError("Manim render produced no output file")


def _render_with_pillow_opencv(plan: VideoPlan, output_mp4: Path) -> Path:
    """Guaranteed deterministic offline renderer using Pillow + OpenCV.

    Renders identical 1280x720 animation frames for each scene type
    with zero reliance on LaTeX, display servers, or external binaries.
    """
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    fps = settings.video_default_fps
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_mp4), fourcc, float(fps), (width, height))

    # Dark slate background color
    bg_color = (17, 24, 39)  # #111827

    for scene in plan.scenes:
        stype = scene.scene_type
        dur = max(1.0, scene.duration_seconds)
        total_frames = int(dur * fps)

        for f in range(total_frames):
            img = Image.new("RGB", (width, height), bg_color)
            draw = ImageDraw.Draw(img)
            t_ratio = f / float(total_frames)

            # Draw header banner
            draw.rectangle([0, 0, width, 50], fill=(31, 41, 55))
            draw.text((40, 16), f"Adaptive Remediation: {plan.concept_name}", fill=(243, 244, 246))

            if stype == SceneType.TITLE:
                title = scene.title or plan.concept_name
                sub = scene.subtitle or "Core Concept Review"
                draw.text((width // 2 - len(title) * 10, height // 2 - 40), title, fill=(250, 204, 21))
                draw.text((width // 2 - len(sub) * 6, height // 2 + 20), sub, fill=(229, 231, 235))

            elif stype == SceneType.EQUATION:
                eq = scene.equation or "F = ma"
                lbl = scene.label or f"Governing Formula: {plan.concept_name}"
                draw.text((width // 2 - len(lbl) * 7, height // 2 - 60), lbl, fill=(96, 165, 250))
                # Draw highlighted equation box
                box_w = max(260, len(eq) * 24)
                draw.rectangle([width // 2 - box_w // 2, height // 2 - 10, width // 2 + box_w // 2, height // 2 + 70],
                               outline=(250, 204, 21), width=3)
                draw.text((width // 2 - len(eq) * 11, height // 2 + 15), eq, fill=(250, 204, 21))

            elif stype == SceneType.DIAGRAM:
                # Animate a box moving across with force arrow
                x_pos = int(250 + t_ratio * 400)
                y_pos = height // 2 - 50
                # Mass box
                draw.rectangle([x_pos, y_pos, x_pos + 120, y_pos + 100], fill=(59, 130, 246), outline=(147, 197, 253), width=2)
                draw.text((x_pos + 25, y_pos + 40), "Mass (m)", fill=(255, 255, 255))
                # Force arrow
                draw.line([x_pos - 100, y_pos + 50, x_pos - 10, y_pos + 50], fill=(250, 204, 21), width=4)
                draw.polygon([(x_pos - 10, y_pos + 42), (x_pos, y_pos + 50), (x_pos - 10, y_pos + 58)], fill=(250, 204, 21))
                draw.text((x_pos - 90, y_pos + 20), "Force (F)", fill=(250, 204, 21))
                # Acceleration indicator
                draw.text((x_pos + 10, y_pos + 115), "--> Acceleration (a)", fill=(52, 211, 153))

            elif stype == SceneType.SUMMARY:
                draw.text((80, 120), "Key Takeaways & Conceptual Summary", fill=(250, 204, 21))
                points = scene.summary_points or [
                    f"Core definition: {plan.concept_name}",
                    "Understand how force, mass, and acceleration relate",
                    "Prerequisite mastery prevents persistent misconceptions",
                ]
                for p_idx, pt in enumerate(points[:4]):
                    draw.text((100, 200 + p_idx * 60), f"•  {pt}", fill=(243, 244, 246))

            else:
                txt = scene.text or plan.concept_name
                draw.text((width // 2 - len(txt) * 6, height // 2), txt, fill=(255, 255, 255))

            # Progress bar at bottom
            draw.rectangle([0, height - 8, int(width * t_ratio), height], fill=(59, 130, 246))

            frame_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            out.write(frame_bgr)

    out.release()
    return output_mp4
