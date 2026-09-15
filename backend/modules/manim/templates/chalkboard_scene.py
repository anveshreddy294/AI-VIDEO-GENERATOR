# modules/manim/templates/chalkboard_scene.py

from manim import *
from ..style_config import *


class ChalkboardScene(Scene):
    """
    Base chalkboard template.

    Used by:
    - Momentum
    - Force
    - Inertia
    - Friction
    - Gravity
    - Diagram scenes
    - Educational explanations
    """

    def setup_chalkboard(self):
        """Standard chalkboard background with safe-area frame."""
        self.camera.background_color = "#1C1C1E"

        self.board_frame = Rectangle(
            width=SAFE_W,
            height=SAFE_H,
            color="#4A6080",
            stroke_width=2,
        )
        self.board_frame.set_fill(opacity=0)
        self.add(self.board_frame)

    def content_region(self):
        """Approximate center band for main visuals (below title)."""
        return {
            "center": np.array([0, CONTENT_CENTER_Y - 0.15, 0]),
            "max_w": SAFE_W - 0.4,
            "max_h": SAFE_H - 1.8,
        }

    def caption_region(self):
        """Bottom band for captions / config text."""
        return {
            "anchor": np.array([0, CAPTION_BAND_Y, 0]),
            "max_w": SAFE_W - 0.6,
        }

    def add_title(self, text, font_size=38, color=CHALK_WHITE):
        """Create a title fitted to the safe width in the title band."""
        title = Text(
            str(text)[:80],
            font_size=font_size,
            weight=BOLD,
            color=color,
        )
        fit_title(title, SAFE_W - 0.4)
        title.move_to(np.array([0, TITLE_BAND_Y, 0]))
        return title

    def place_safe(self, mob, region=None):
        """Fit mob into region and clamp inside safe area."""
        region = region or self.content_region()
        fit_in_box(mob, region["max_w"], region["max_h"])
        mob.move_to(region["center"])
        clamp_into_frame(mob)
        return mob

    def chalk_title(self, text):
        """Standard chalk-style title (legacy alias)."""
        return self.add_title(text)

    def chalk_stroke(self, mobject, color=CHALK_WHITE):
        """Convert any object into chalk style."""
        mobject.set_stroke(
            color=color,
            width=2.5,
            opacity=0.9,
        )
        mobject.set_fill(opacity=0)
        return mobject

    def draw_label_arrow(
        self,
        label_text,
        target_point,
        label_position,
        color=CHALK_WHITE,
    ):
        """Creates chalk-style annotation arrow (Arrow CE-compatible)."""
        label = Text(
            label_text,
            font=MONO_FONT,
            font_size=20,
            color=color,
        )
        label.move_to(label_position)
        fit_width(label, 2.8)

        arrow = Arrow(
            label.get_bottom(),
            target_point,
            color=color,
            stroke_width=1.5,
            buff=0.08,
            max_tip_length_to_length_ratio=0.25,
        )
        return VGroup(label, arrow)

    def build_anatomy_scene(
        self,
        shapes: list,
        labels: list | None = None,
    ):
        """Generic chalkboard anatomy renderer."""
        self.setup_chalkboard()

        for shape_data in shapes:
            shape = self.chalk_stroke(
                Rectangle(
                    width=2,
                    height=1,
                ),
                color=shape_data.get(
                    "color",
                    CHALK_WHITE,
                ),
            )

            label = self.draw_label_arrow(
                shape_data.get("label", ""),
                shape.get_center(),
                shape.get_top() + UP * 0.4,
            )

            self.play(
                Create(shape),
                run_time=shape_data.get(
                    "draw_time",
                    0.8,
                ),
            )

            self.play(
                FadeIn(label),
                run_time=0.4,
            )
