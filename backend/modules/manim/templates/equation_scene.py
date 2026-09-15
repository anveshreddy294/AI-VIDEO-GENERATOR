# modules/manim/templates/equation_scene.py

from manim import *
from ..style_config import *


class EquationScene(Scene):

    def build_scene(
        self,
        title_text: str,
        equation_text: str,
        explanation: str = "",
        audio_duration: float = 0.0,
    ):
        self.camera.background_color = SLATE_BG

        title = Text(
            str(title_text)[:80],
            font=TITLE_FONT,
            font_size=36,
            color=CHALK_WHITE,
            weight=BOLD,
        )
        fit_title(title, SAFE_W - 0.6)
        title.move_to(np.array([0, TITLE_BAND_Y, 0]))

        eq_str = str(equation_text).strip() or r"E = mc^2"
        try:
            equation = MathTex(eq_str, color=CHALK_YELLOW).scale(1.3)
            fit_width(equation, SAFE_W - 1.5)
        except Exception:
            equation = Text(eq_str, font=MONO_FONT, font_size=34, color=CHALK_YELLOW)
            fit_width(equation, SAFE_W - 1.5)

        equation.move_to(np.array([0, CONTENT_CENTER_Y + 0.3, 0]))

        explanation_text = None
        if explanation:
            explanation_text = wrapped_text(
                str(explanation)[:240],
                font_size=20,
                max_w=SAFE_W - 1.2,
                color=CHALK_WHITE,
                line_spacing=1.3,
            )
            explanation_text.next_to(equation, DOWN, buff=0.55)
            clamp_into_frame(explanation_text)

        self.play(Write(title), run_time=0.8, rate_func=smooth)
        self.play(Write(equation), run_time=1.0, rate_func=smooth)
        if explanation_text is not None:
            self.play(FadeIn(explanation_text), run_time=0.7, rate_func=smooth)

        tail = max(0.5, audio_duration - 3.0) if audio_duration > 0 else 1.5
        self.wait(tail)
