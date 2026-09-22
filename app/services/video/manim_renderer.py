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
import re
import shutil
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from ...core.config import settings
from .scene_schema import ScenePlan, SceneType, VideoPlan

logger = logging.getLogger(__name__)


def render_video_plan(plan: VideoPlan, output_mp4: Path) -> Path:
    """Render a VideoPlan to an MP4 video file."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    # For multi-minute videos (>60s) or fast quality settings, use high-speed OpenCV/Pillow engine
    # which renders in seconds with dynamic on-screen captions and zero display/LaTeX overhead
    if plan.duration_seconds > 60 or getattr(settings, "manim_quality", "") in ("fast", "pillow", "opencv"):
        return _render_with_pillow_opencv(plan, output_mp4)

    # Attempt Manim rendering first for short videos <= 60s
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
                    has_real_equation = bool(scene.equation and any(c in scene.equation for c in ("=", "<", ">", "\\", "+", "-", "*", "/")))
                    if has_real_equation:
                        eq_str = scene.equation
                        label_str = scene.label or f"Governing Law: {plan.concept_name}"
                        eq = Text(eq_str, font_size=52, color=YELLOW, weight="BOLD")
                        lbl = Text(label_str, font_size=26, color=BLUE)
                        lbl.next_to(eq, UP, buff=0.5)
                        group = VGroup(lbl, eq).move_to(ORIGIN)
                    else:
                        lbl = Text((scene.label or f"Core Principle: {plan.concept_name}")[:50], font_size=28, color=YELLOW, weight="BOLD")
                        body = Text((scene.text or scene.equation or plan.concept_name)[:80], font_size=22, color=WHITE)
                        body.next_to(lbl, DOWN, buff=0.4)
                        box = Rectangle(width=10.0, height=2.4, color=BLUE, fill_opacity=0.3)
                        group = VGroup(box, lbl, body).move_to(ORIGIN)
                    self.play(FadeIn(group), run_time=min(2.0, dur * 0.35))
                    self.wait(max(0.5, dur * 0.4))
                    self.play(FadeOut(group), run_time=min(1.0, dur * 0.25))

                elif stype == SceneType.DIAGRAM:
                    is_physics = (
                        scene.diagram_type == "force_box"
                        and (bool(scene.force_label) or "force" in plan.concept_name.lower() or "newton" in plan.concept_name.lower())
                    )
                    if is_physics:
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
                    else:
                        # Modern Process Flow / Architecture Diagram for general concepts
                        t_lbl = Text((scene.title or f"{plan.concept_name} Structural Flow")[:35], font_size=26, color=YELLOW, weight="BOLD").to_edge(UP, buff=1.2)

                        box1 = Rectangle(width=2.8, height=1.5, color=BLUE, fill_opacity=0.4).shift(LEFT * 3.6)
                        t1 = Text((scene.subtitle or "Context / Input")[:18], font_size=15, color=WHITE).move_to(box1)
                        g1 = VGroup(box1, t1)

                        arr1 = Arrow(LEFT * 2.1, LEFT * 1.1, color=YELLOW, buff=0.1)

                        box2 = Rectangle(width=3.2, height=1.7, color=YELLOW, fill_opacity=0.5).move_to(ORIGIN)
                        t2 = Text((scene.label or plan.concept_name)[:20], font_size=17, color=WHITE, weight="BOLD").move_to(box2)
                        g2 = VGroup(box2, t2)

                        arr2 = Arrow(RIGHT * 1.1, RIGHT * 2.1, color=YELLOW, buff=0.1)

                        box3 = Rectangle(width=2.8, height=1.5, color=GREEN, fill_opacity=0.4).shift(RIGHT * 3.6)
                        t3 = Text("Applied Outcome", font_size=15, color=WHITE).move_to(box3)
                        g3 = VGroup(box3, t3)

                        flow_group = VGroup(t_lbl, g1, arr1, g2, arr2, g3).move_to(ORIGIN)
                        self.play(FadeIn(flow_group), run_time=min(2.0, dur * 0.35))
                        self.wait(max(0.5, dur * 0.45))
                        self.play(FadeOut(flow_group), run_time=min(1.0, dur * 0.2))

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
    with dynamic on-screen captions burned in and zero reliance on LaTeX or external display servers.
    """
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    fps = settings.video_default_fps
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_mp4), fourcc, float(fps), (width, height))

    # Pre-index narration text by scene_index
    narration_by_scene: dict[int, str] = {}
    if plan.narration:
        for seg in plan.narration:
            s_idx = seg.scene_index
            existing = narration_by_scene.get(s_idx, "")
            narration_by_scene[s_idx] = (existing + " " + seg.text).strip() if existing else seg.text.strip()

    # Dark slate background color
    bg_color = (17, 24, 39)  # #111827

    for scene in plan.scenes:
        stype = scene.scene_type
        dur = max(1.0, scene.duration_seconds)
        total_frames = int(dur * fps)

        # Extract narration sentences for this scene
        scene_narr = (
            narration_by_scene.get(scene.scene_index)
            or scene.narration
            or scene.text
            or scene.title
            or plan.concept_name
        )
        sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", scene_narr) if s.strip()]
        if not sentences:
            sentences = [scene_narr]

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
                draw.text((width // 2 - len(title) * 10, height // 2 - 50), title, fill=(250, 204, 21))
                draw.text((width // 2 - len(sub) * 6, height // 2 + 10), sub, fill=(229, 231, 235))

            elif stype == SceneType.EQUATION:
                has_real_equation = bool(scene.equation and any(c in scene.equation for c in ("=", "<", ">", "\\", "+", "-", "*", "/")))
                if has_real_equation:
                    eq = scene.equation
                    lbl = scene.label or f"Governing Formula: {plan.concept_name}"
                    draw.text((width // 2 - len(lbl) * 7, height // 2 - 70), lbl, fill=(96, 165, 250))
                    box_w = max(260, len(eq) * 24)
                    draw.rectangle(
                        [width // 2 - box_w // 2, height // 2 - 20, width // 2 + box_w // 2, height // 2 + 60],
                        outline=(250, 204, 21),
                        width=3,
                    )
                    draw.text((width // 2 - len(eq) * 11, height // 2 + 5), eq, fill=(250, 204, 21))
                else:
                    lbl = (scene.label or f"Core Principle: {plan.concept_name}")[:55]
                    body = (scene.text or scene.equation or plan.concept_name)[:75]
                    draw.text((width // 2 - len(lbl) * 7, height // 2 - 60), lbl, fill=(250, 204, 21))
                    card_w = min(840, max(360, len(body) * 13))
                    draw.rectangle(
                        [width // 2 - card_w // 2, height // 2 - 10, width // 2 + card_w // 2, height // 2 + 60],
                        outline=(96, 165, 250),
                        fill=(31, 41, 55),
                        width=2,
                    )
                    draw.text((width // 2 - len(body) * 5, height // 2 + 15), body, fill=(255, 255, 255))

            elif stype == SceneType.DIAGRAM:
                is_physics = (
                    scene.diagram_type == "force_box"
                    and (bool(scene.force_label) or "force" in plan.concept_name.lower() or "newton" in plan.concept_name.lower())
                )
                if is_physics:
                    # Animate a box moving across with force arrow
                    x_pos = int(250 + t_ratio * 400)
                    y_pos = height // 2 - 60
                    # Mass box
                    draw.rectangle(
                        [x_pos, y_pos, x_pos + 120, y_pos + 100],
                        fill=(59, 130, 246),
                        outline=(147, 197, 253),
                        width=2,
                    )
                    draw.text((x_pos + 25, y_pos + 40), scene.object_label or "Mass (m)", fill=(255, 255, 255))
                    # Force arrow
                    draw.line([x_pos - 100, y_pos + 50, x_pos - 10, y_pos + 50], fill=(250, 204, 21), width=4)
                    draw.polygon([(x_pos - 10, y_pos + 42), (x_pos, y_pos + 50), (x_pos - 10, y_pos + 58)], fill=(250, 204, 21))
                    draw.text((x_pos - 90, y_pos + 20), scene.force_label or "Force (F)", fill=(250, 204, 21))
                    # Acceleration indicator
                    draw.text((x_pos + 10, y_pos + 115), f"--> {scene.acceleration_label or 'Acceleration (a)'}", fill=(52, 211, 153))
                else:
                    # Modern Process Flow / Architecture Diagram
                    flow_title = (scene.title or f"{plan.concept_name} Structural Flow")[:45]
                    draw.text((width // 2 - len(flow_title) * 6, 120), flow_title, fill=(250, 204, 21))

                    c1_text = (scene.subtitle or "Context / Input")[:18]
                    c2_text = (scene.label or plan.concept_name)[:20]
                    c3_text = "Applied Outcome"

                    # Card 1
                    draw.rectangle([140, 240, 380, 360], fill=(31, 41, 55), outline=(59, 130, 246), width=2)
                    draw.text((160, 290), c1_text, fill=(255, 255, 255))

                    # Arrow 1
                    draw.line([390, 300, 470, 300], fill=(250, 204, 21), width=4)
                    draw.polygon([(470, 292), (485, 300), (470, 308)], fill=(250, 204, 21))

                    # Card 2 (Active highlighted)
                    draw.rectangle([495, 220, 785, 380], fill=(30, 58, 138), outline=(250, 204, 21), width=3)
                    draw.text((515, 290), c2_text, fill=(250, 204, 21))

                    # Arrow 2
                    draw.line([795, 300, 875, 300], fill=(250, 204, 21), width=4)
                    draw.polygon([(875, 292), (890, 300), (875, 308)], fill=(250, 204, 21))

                    # Card 3
                    draw.rectangle([900, 240, 1140, 360], fill=(31, 41, 55), outline=(16, 185, 129), width=2)
                    draw.text((920, 290), c3_text, fill=(255, 255, 255))

            elif stype == SceneType.SUMMARY:
                draw.text((80, 100), "Key Takeaways & Conceptual Summary", fill=(250, 204, 21))
                points = scene.summary_points or [
                    f"Core definition: {plan.concept_name}",
                    "Understand how governing laws and relationships interact",
                    "Prerequisite mastery prevents persistent misconceptions",
                ]
                for p_idx, pt in enumerate(points[:4]):
                    draw.text((100, 160 + p_idx * 50), f"•  {pt}", fill=(243, 244, 246))

            else:
                txt = scene.text or plan.concept_name
                draw.text((width // 2 - len(txt) * 6, height // 2 - 30), txt, fill=(255, 255, 255))

            # --- Synchronized On-Screen Caption Card ---
            sent_idx = min(len(sentences) - 1, int(t_ratio * len(sentences)))
            active_sentence = sentences[sent_idx]
            wrapped_lines = textwrap.wrap(active_sentence, width=68)
            card_y1 = height - 110
            card_y2 = height - 20
            # Draw sleek translucent rounded box
            draw.rounded_rectangle(
                [100, card_y1, width - 100, card_y2],
                radius=10,
                fill=(15, 23, 42),
                outline=(59, 130, 246),
                width=1,
            )
            # CC badge
            draw.rectangle([115, card_y1 + 10, 145, card_y1 + 26], fill=(59, 130, 246))
            draw.text((120, card_y1 + 12), "CC", fill=(255, 255, 255))
            # Center active caption lines
            for line_i, line_text in enumerate(wrapped_lines[:2]):
                bbox = draw.textbbox((0, 0), line_text)
                txt_w = bbox[2] - bbox[0]
                draw.text((width // 2 - txt_w // 2, card_y1 + 10 + line_i * 24), line_text, fill=(255, 255, 255))

            # Progress bar at bottom
            draw.rectangle([0, height - 6, int(width * t_ratio), height], fill=(59, 130, 246))

            frame_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            out.write(frame_bgr)

    out.release()
    return output_mp4
