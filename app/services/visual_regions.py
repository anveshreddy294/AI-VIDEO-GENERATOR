"""Conservative repeated-slide footer segmentation; uncertain layouts stay whole."""
from __future__ import annotations
from dataclasses import dataclass
import io
from PIL import Image, ImageOps

MIN_PANELS = 2
MAX_PANELS = 8
MAX_REGION_PARALLELISM = 3
MIN_BAND_COVERAGE = 0.50
MIN_COLOR_SPREAD = 35
MAX_SPACING_DEVIATION = 0.04
MIN_SLIDE_ASPECT = 1.55
MAX_SLIDE_ASPECT = 1.95
EXTERIOR_DARK_LEVEL = 100
MAX_ANALYSIS_WIDTH = 240
SIDE_PROBE_FRACTION = .1
MIN_TALL_ASPECT = 1.7
MIN_BAND_HEIGHT = 8
MAX_BAND_HEIGHT = 32
EXTERIOR_MARGIN = 32
EXTERIOR_PROBE_OFFSET = 20
MAX_FOOTER_COLOR_DEVIATION = 20

@dataclass(frozen=True)
class VisualRegion:
    image: bytes
    bbox: tuple[int, int, int, int]

def slide_regions(image_bytes: bytes) -> tuple[VisualRegion, ...]:
    """Require repeated colored footer bands, slide aspect, and dark exterior UI.

    Footer geometry is accepted only when both inferred outer edges abut dark
    non-slide regions. No OCR, arbitrary prose boundaries, or model guesses.
    """
    with Image.open(io.BytesIO(image_bytes)) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
    width, height = image.size
    if height < width * MIN_TALL_ASPECT:
        return ()
    probe = image.resize((min(width, MAX_ANALYSIS_WIDTH), height))
    left, right = int(probe.width * SIDE_PROBE_FRACTION), int(probe.width * (1 - SIDE_PROBE_FRACTION))
    bands: list[tuple[int, int]] = []
    start: int | None = None
    pixels = probe.load()
    for y in range(height):
        colored = sum(max(pixels[x, y]) - min(pixels[x, y]) >= MIN_COLOR_SPREAD
                      for x in range(left, right))
        active = colored / (right - left) >= MIN_BAND_COVERAGE
        if active and start is None:
            start = y
        if not active and start is not None:
            if MIN_BAND_HEIGHT <= y - start <= MAX_BAND_HEIGHT:
                bands.append((start, y))
            start = None
    if not MIN_PANELS <= len(bands) <= MAX_PANELS:
        return ()
    colors = [tuple(sorted(pixels[x, (a+b)//2][channel] for x in range(left,right))[(right-left)//2]
                    for channel in range(3)) for a,b in bands]
    if any(max(abs(a-b) for a,b in zip(colors[0],color)) > MAX_FOOTER_COLOR_DEVIATION for color in colors[1:]):
        return ()
    spacing = (bands[-1][1] - bands[0][1]) / (len(bands) - 1)
    if not MIN_SLIDE_ASPECT <= width / spacing <= MAX_SLIDE_ASPECT:
        return ()
    if any(abs((b[1] - a[1]) / spacing - 1) > MAX_SPACING_DEVIATION
           for a, b in zip(bands, bands[1:])):
        return ()
    top = round(bands[0][1] - spacing)
    bottom = bands[-1][1]
    if top < EXTERIOR_MARGIN or bottom + EXTERIOR_MARGIN > height:
        return ()
    def dark(y: int) -> bool:
        values = sorted(sum(pixels[x, y]) / 3 for x in range(left, right))
        return values[len(values) // 2] < EXTERIOR_DARK_LEVEL
    if not dark(top - EXTERIOR_PROBE_OFFSET) or not dark(bottom + EXTERIOR_PROBE_OFFSET):
        return ()
    regions: list[VisualRegion] = []
    for end in (band[1] for band in bands):
        bbox = (0, top, width, end)
        buffer = io.BytesIO()
        image.crop(bbox).save(buffer, format="JPEG", quality=95)
        regions.append(VisualRegion(buffer.getvalue(), bbox))
        top = end
    return tuple(regions)
