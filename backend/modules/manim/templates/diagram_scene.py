# modules/manim/templates/diagram_scene.py

from manim import *
import numpy as np
from ..style_config import *


class DiagramScene(Scene):

    def _normalize_nodes(self, nodes: list) -> list[str]:
        labels: list[str] = []
        for node in nodes:
            if isinstance(node, dict):
                labels.append(str(node.get("label", node.get("name", "?"))))
            else:
                labels.append(str(node))
        return labels[:8] if labels else ["A", "B", "C"]

    def build_scene(
        self,
        title_text: str,
        nodes: list,
        audio_duration: float = 0.0,
    ):
        self.camera.background_color = SLATE_BG
        labels = self._normalize_nodes(nodes)

        title = Text(
            str(title_text)[:80],
            font=TITLE_FONT,
            font_size=34,
            color=CHALK_WHITE,
            weight=BOLD,
        )
        fit_title(title, SAFE_W - 0.6)
        title.move_to(np.array([0, TITLE_BAND_Y, 0]))
        self.play(Write(title), run_time=0.8, rate_func=smooth)

        n = len(labels)
        max_span = SAFE_W - 1.5
        if n <= 4:
            positions = [
                np.array([x, CONTENT_CENTER_Y - 0.2, 0])
                for x in np.linspace(-max_span / 2, max_span / 2, n)
            ]
        else:
            cols = min(4, n)
            rows = (n + cols - 1) // cols
            positions = []
            for i in range(n):
                row, col = divmod(i, cols)
                positions.append(
                    np.array([
                        -max_span / 2 + col * (max_span / max(cols - 1, 1)),
                        0.8 - row * 1.6,
                        0,
                    ])
                )

        objects = []
        for label, pos in zip(labels, positions):
            circle = Circle(radius=0.5, color=CHALK_BLUE, stroke_width=2)
            circle.set_fill(CHALK_BLUE, opacity=0.15)
            label_mob = wrapped_text(
                str(label)[:28],
                font_size=16,
                max_w=0.9,
                color=CHALK_WHITE,
            )
            group = VGroup(circle, label_mob)
            group.move_to(pos)
            objects.append(group)

        graph = VGroup(*objects)
        fit_in_box(graph, SAFE_W - 0.5, SAFE_H - 2.0)
        graph.move_to(np.array([0, CONTENT_CENTER_Y - 0.25, 0]))

        self.play(
            LaggedStart(*[FadeIn(o, scale=0.85) for o in graph], lag_ratio=0.2),
            run_time=min(2.5, 0.45 * n + 0.5),
            rate_func=smooth,
        )

        if len(objects) >= 2:
            arrows = VGroup(*[
                Arrow(
                    objects[i].get_right(),
                    objects[i + 1].get_left(),
                    color=CHALK_YELLOW,
                    stroke_width=2,
                    buff=0.12,
                    max_tip_length_to_length_ratio=0.2,
                )
                for i in range(len(objects) - 1)
            ])
            self.play(
                LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.2),
                run_time=0.8,
                rate_func=smooth,
            )

        tail = max(0.5, audio_duration - 3.0) if audio_duration > 0 else 1.5
        self.wait(tail)
