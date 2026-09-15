"""Semantic motion effect code-generators.

Each function returns a Python code string (un-indented) representing one
semantic animation. The template caller adds 8-space indentation.

Motion semantics:
  resist_motion  → inertia feel: micro-jitter then stillness
  apply_force    → arrow grows toward object
  impact_pulse   → object scales up/down on collision
  accelerate     → progressive_displacement steps of increasing length
  slide          → constant-speed shift
  decelerate     → progressive slowing steps
  introduce      → FadeIn with slight scale-up
  place          → FadeIn at position
  hold           → self.wait() for stillness emphasis
  fade_out_group → FadeOut a VGroup
  draw_arc       → draws a curved trajectory
"""
from __future__ import annotations


def resist_motion(obj_var: str, run_time: float = 0.9) -> str:
    """Object resists motion: micro-jitter then stays still (inertia feel)."""
    jt = round(run_time * 0.14, 3)
    wt = round(run_time * 0.72, 3)
    return (
        f"self.play({obj_var}.animate.shift(RIGHT*0.05), run_time={jt})\n"
        f"self.play({obj_var}.animate.shift(LEFT*0.05), run_time={jt})\n"
        f"self.wait({wt})  # stillness emphasis\n"
    )


def apply_force(force_var: str, run_time: float = 0.7) -> str:
    """Force arrow grows into view."""
    return f"self.play(GrowArrow({force_var}_arrow), run_time={run_time:.3f})\n"


def impact_pulse(obj_var: str, run_time: float = 0.55) -> str:
    """Object pulses on force impact — scale up then restore."""
    ht = round(run_time * 0.5, 3)
    return (
        f"self.play({obj_var}.animate.scale(1.18), run_time={ht})\n"
        f"self.play({obj_var}.animate.scale(1/1.18), run_time={ht})\n"
    )


def accelerate(obj_var: str, run_time: float = 1.8, steps: int = 4,
               direction: str = "RIGHT") -> str:
    """Progressive displacement: each step covers more distance than the last."""
    total_dist = 3.5  # units
    weights = [i + 1 for i in range(steps)]
    weight_sum = sum(weights)
    lines = []
    for i, w in enumerate(weights):
        dist = round(total_dist * w / weight_sum, 3)
        rt = round(run_time * w / weight_sum, 3)
        lines.append(
            f"self.play({obj_var}.animate.shift({direction}*{dist}), run_time={rt})"
        )
    return "\n".join(lines) + "\n"


def slide(obj_var: str, distance: float = 2.5, run_time: float = 1.2,
          direction: str = "RIGHT") -> str:
    """Constant-speed slide."""
    return f"self.play({obj_var}.animate.shift({direction}*{distance:.2f}), run_time={run_time:.3f})\n"


def decelerate(obj_var: str, run_time: float = 1.5, steps: int = 4,
               direction: str = "RIGHT") -> str:
    """Decelerating motion: each step shorter than the previous."""
    total_dist = 2.5
    weights = [steps - i for i in range(steps)]
    weight_sum = sum(weights)
    lines = []
    for w in weights:
        dist = round(total_dist * w / weight_sum, 3)
        rt = round(run_time * w / weight_sum, 3)
        lines.append(
            f"self.play({obj_var}.animate.shift({direction}*{dist}), run_time={rt})"
        )
    return "\n".join(lines) + "\n"


def introduce(obj_var: str, run_time: float = 0.7) -> str:
    """Fade in an object with slight scale emphasis."""
    return (
        f"self.play(FadeIn({obj_var}, scale=0.85), run_time={run_time:.3f})\n"
    )


def place(obj_var: str, run_time: float = 0.6) -> str:
    """Simple FadeIn at current position."""
    return f"self.play(FadeIn({obj_var}), run_time={run_time:.3f})\n"


def hold(duration: float = 1.2) -> str:
    """Explicit wait for stillness/emphasis."""
    return f"self.wait({duration:.3f})  # stillness / emphasis hold\n"


def fade_out_group(group_var: str, run_time: float = 0.4) -> str:
    return f"self.play(FadeOut({group_var}), run_time={run_time:.3f})\n"


def draw_arc(arc_var: str, run_time: float = 1.5) -> str:
    """Draw a pre-created VMobject arc (trajectory)."""
    return f"self.play(Create({arc_var}), run_time={run_time:.3f})\n"


def indicate_object(obj_var: str, run_time: float = 0.5) -> str:
    return f"self.play(Indicate({obj_var}, scale_factor=1.25), run_time={run_time:.3f})\n"


def flash_object(obj_var: str, color: str = "#ff7a59", run_time: float = 0.4) -> str:
    return f"self.play(Flash({obj_var}, color='{color}', flash_radius=0.45), run_time={run_time:.3f})\n"
