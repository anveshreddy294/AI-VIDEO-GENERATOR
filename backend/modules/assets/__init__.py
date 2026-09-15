"""Educational mechanics asset registry."""
from __future__ import annotations

from modules.assets.mechanics import ASSET_IDS, get_code, get_position_hint

ASSET_REGISTRY: dict[str, str] = dict(ASSET_IDS)

__all__ = ["ASSET_REGISTRY", "get_code", "get_position_hint"]
