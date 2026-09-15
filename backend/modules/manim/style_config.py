# modules/manim/style_config.py
from manim import *

# CHALKBOARD STYLE (matching your reference images 1 & 2)
CHALK_CONFIG = {
    "background_color": "#1C1C1E",      # dark slate, not pure black
    "frame_rate": 30,
    "pixel_height": 1080,
    "pixel_width": 1920,
}

# Color palette
CHALK_WHITE   = "#F0EFE8"
CHALK_PINK    = "#E8A0A0"
CHALK_BLUE    = "#7BA7C2"
CHALK_YELLOW  = "#E8D87A"
CHALK_GREEN   = "#7AC2A0"
SLATE_BG      = "#1C1C1E"
CARD_BG       = "#252530"
CARD_BORDER   = "#3A3A4A"

# Typography
TITLE_FONT    = "Montserrat"
BODY_FONT     = "Outfit"
MONO_FONT     = "JetBrains Mono"

# ---------------------------------------------------------------------------
# Safe-area layout (Manim default frame ≈ 14.22 × 8.0)
# ---------------------------------------------------------------------------
FRAME_W = 14.22
FRAME_H = 8.0
MARGIN = 0.6
SAFE_W = FRAME_W - 2 * MARGIN
SAFE_H = FRAME_H - 2 * MARGIN
TITLE_BAND_Y = FRAME_H / 2 - MARGIN - 0.35
CONTENT_CENTER_Y = 0.0
CAPTION_BAND_Y = -FRAME_H / 2 + MARGIN + 0.45


def chalk_text(content, size=36, color=CHALK_WHITE, font=BODY_FONT):
    return Text(content, font=font, font_size=size, color=color)


def chalk_title(content, color=CHALK_WHITE):
    return Text(content, font=TITLE_FONT, font_size=48,
                color=color, weight=BOLD)


def fit_width(mob, max_w):
    """Scale mobject down only so its width fits within max_w."""
    if mob.width > max_w:
        mob.scale(max_w / mob.width)
    return mob


def fit_in_box(mob, max_w, max_h):
    """Scale mobject down only so it fits inside max_w × max_h."""
    if mob.width > max_w:
        mob.scale(max_w / mob.width)
    if mob.height > max_h:
        mob.scale(max_h / mob.height)
    return mob


def fit_title(text_mob, max_w=SAFE_W):
    """Fit a title mobject to the safe width."""
    return fit_width(text_mob, max_w)


def wrapped_text(
    content,
    font_size=18,
    max_w=4.0,
    color=CHALK_WHITE,
    font=BODY_FONT,
    line_spacing=1.3,
    weight=NORMAL,
):
    """Return Text with automatic line wrapping to max_w."""
    return Text(
        str(content),
        font=font,
        font_size=font_size,
        color=color,
        line_spacing=line_spacing,
        weight=weight,
        width=max_w,
    )


def clamp_into_frame(mob, max_w=SAFE_W, max_h=SAFE_H):
    """Nudge mobject inside the safe area if it overflows."""
    half_w = mob.width / 2
    half_h = mob.height / 2
    cx, cy, _ = mob.get_center()
    left_lim = -max_w / 2 + half_w
    right_lim = max_w / 2 - half_w
    bottom_lim = -max_h / 2 + half_h
    top_lim = max_h / 2 - half_h
    if left_lim > right_lim:
        cx = 0
    else:
        cx = max(left_lim, min(right_lim, cx))
    if bottom_lim > top_lim:
        cy = 0
    else:
        cy = max(bottom_lim, min(top_lim, cy))
    mob.move_to(np.array([cx, cy, 0]))
    return mob
