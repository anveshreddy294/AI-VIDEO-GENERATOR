"""Shared helpers for chemistry concept template code-generators.

Mirrors the structure of modules/templates/mechanics/_base.py so that
chemistry templates can be dropped into the same pipeline without changes
to the orchestration layer.
"""
from __future__ import annotations

from typing import Any

# ------------------------------------------------------------------
# Manim scene header / footer  (identical boilerplate to mechanics)
# ------------------------------------------------------------------

_HEADER = """\
from manim import *
import numpy as np

from modules.manim.templates.chalkboard_scene import ChalkboardScene


class GeneratedScene(ChalkboardScene):
    def construct(self):

        self.setup_chalkboard()
"""

_FOOTER = """\
        self.play(FadeOut(*self.mobjects), run_time=0.40)
"""

# ------------------------------------------------------------------
# Theme Colors
# ------------------------------------------------------------------

BG = "#0f1117"

TITLE_COLOR   = "#e0e6f0"
TEXT_COLOR    = "#c8d3e6"
LABEL_COLOR   = "#aab8d0"

# General accents
ACCENT1 = "#4f8ef7"   # blue  – structural / bonds
ACCENT2 = "#41d4a8"   # teal  – labels / annotations
ACCENT3 = "#f7c948"   # gold  – highlights / energy

# Chemistry-specific palette
NUCLEUS_COLOR    = "#ff7a59"   # orange-red  – nucleus / protons
NEUTRON_COLOR    = "#909090"   # grey        – neutrons
ELECTRON_COLOR   = "#4fc3f7"   # sky-blue    – electrons / orbitals
SHELL_COLOR      = "#2a3550"   # dark navy   – electron shells (filled area)
BOND_COLOR       = "#4f8ef7"   # blue        – covalent bonds
IONIC_COLOR      = "#f7c948"   # gold        – ionic charge / lattice
ENERGY_COLOR     = "#ff5c8a"   # pink-red    – energy arrows / exo/endo
PRODUCT_COLOR    = "#41d4a8"   # teal        – products
REACTANT_COLOR   = "#4fc3f7"   # blue        – reactants
EQUILIBRIUM_COLOR = "#f7c948"  # gold        – equilibrium arrows
ACID_COLOR       = "#ff7a59"   # orange      – acid / H⁺
BASE_COLOR       = "#41d4a8"   # teal        – base / OH⁻
ORBITAL_COLOR    = "#7c5cbf"   # purple      – orbitals / lobes

# Element color map (CPK-inspired, abbreviated)
ELEMENT_COLORS: dict[str, str] = {
    "H":  "#ffffff",
    "C":  "#909090",
    "N":  "#4f8ef7",
    "O":  "#ff5c5c",
    "F":  "#41d4a8",
    "Cl": "#41d4a8",
    "S":  "#f7c948",
    "P":  "#ff9933",
    "Na": "#aa44ff",
    "K":  "#aa44ff",
    "Ca": "#808080",
    "Mg": "#228b22",
    "Fe": "#cc6633",
    "Cu": "#cc6633",
    "Zn": "#808080",
    "Br": "#a52a2a",
    "I":  "#940094",
}


def element_color(symbol: str) -> str:
    """Return CPK-style color for element symbol."""
    return ELEMENT_COLORS.get(symbol, "#cccccc")


# ------------------------------------------------------------------
# Timeline Helpers  (identical API to mechanics/_base.py)
# ------------------------------------------------------------------

def get_event(
    timeline: dict[str, Any],
    event_id: str,
) -> dict[str, Any] | None:
    """Look up event by ID."""
    for ev in timeline.get("events", []):
        if ev["id"] == event_id:
            return ev
    return None


def get_event_by_type(
    timeline: dict[str, Any],
    plan_events: list[dict[str, Any]],
    event_type: str,
    fallback_id: str | None = None,
) -> dict[str, Any] | None:
    """Find first timeline event corresponding to semantic event type."""
    for plan_ev in plan_events:
        if plan_ev.get("type") == event_type:
            found = get_event(timeline, plan_ev["id"])
            if found:
                return found
    if fallback_id:
        return get_event(timeline, fallback_id)
    return None


def event_rt(
    timeline: dict[str, Any],
    event_id: str,
    default: float = 0.7,
) -> float:
    """Get run_time for event."""
    ev = get_event(timeline, event_id)
    if ev is None:
        return default
    rt = float(ev.get("run_time", default))
    return rt if rt >= 0.1 else default


def event_rt_type(
    timeline: dict[str, Any],
    plan_events: list[dict[str, Any]],
    event_type: str,
    fallback_id: str | None = None,
    default: float = 0.7,
) -> float:
    """Get run_time by semantic event type."""
    ev = get_event_by_type(timeline, plan_events, event_type, fallback_id)
    if ev is None:
        return default
    rt = float(ev.get("run_time", default))
    return rt if rt >= 0.1 else default


def event_hold(
    timeline: dict[str, Any],
    event_id: str,
    default: float = 0.0,
) -> float:
    """Get hold_after for event."""
    ev = get_event(timeline, event_id)
    if ev is None:
        return default
    return float(ev.get("hold_after", default))


def event_hold_type(
    timeline: dict[str, Any],
    plan_events: list[dict[str, Any]],
    event_type: str = "hold",
    default: float = 1.2,
) -> float:
    """Get hold duration using event type."""
    ev = get_event_by_type(timeline, plan_events, event_type)
    if ev is None:
        return default
    hold = float(ev.get("hold_after", 0.0))
    return hold if hold >= 0.3 else default


def event_start(
    timeline: dict[str, Any],
    event_id: str,
    default: float = 0.0,
) -> float:
    """Get start time."""
    ev = get_event(timeline, event_id)
    if ev is None:
        return default
    return float(ev.get("start", default))


# ------------------------------------------------------------------
# Scene Assembly Helpers
# ------------------------------------------------------------------

def build_sequential(
    blocks: list[tuple[str, float]],
    audio_duration: float,
    outro_time: float = 0.40,
) -> str:
    """Concatenate animation blocks and pad remaining audio time."""
    lines: list[str] = []
    elapsed = 0.0
    for code, duration in blocks:
        lines.append(code)
        elapsed += duration
    tail = audio_duration - elapsed - outro_time
    if tail > 0.05:
        lines.append(f"        self.wait({tail:.3f})\n")
    return "".join(lines)


def indent(code: str, spaces: int = 8) -> str:
    """Indent generated code block."""
    pad = " " * spaces
    result = []
    for line in code.splitlines():
        if line.strip():
            result.append(pad + line)
        else:
            result.append("")
    return "\n".join(result)


# ------------------------------------------------------------------
# Asset Helpers
# ------------------------------------------------------------------

def asset_param(
    plan: dict[str, Any],
    role: str,
    key: str,
    default: Any = "",
) -> Any:
    """Get asset parameter by role."""
    for asset in plan.get("assets", []):
        if asset["role"] == role:
            return asset.get("params", {}).get(key, default)
    return default


def asset_instance(
    plan: dict[str, Any],
    role: str,
) -> str | None:
    """Get instance ID for asset role."""
    for asset in plan.get("assets", []):
        if asset["role"] == role:
            return asset.get("instance_id")
    return None


# ------------------------------------------------------------------
# Chemistry-specific mini helpers
# ------------------------------------------------------------------

def _aid(plan: dict, role: str, default: str) -> str:
    for a in plan.get("assets", []):
        if a["role"] == role:
            return a.get("asset_id", default)
    return default


def _aparams(plan: dict, role: str) -> dict:
    for a in plan.get("assets", []):
        if a["role"] == role:
            return dict(a.get("params", {}))
    return {}


def _indent(code: str, spaces: int = 8) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else "" for line in code.splitlines())


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")