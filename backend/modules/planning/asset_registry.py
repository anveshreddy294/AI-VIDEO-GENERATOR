"""Asset registry: tracks instance_id → asset info across scenes for continuity.

When a scene introduces an asset (e.g. puck_a), the registry records its
last known position so a later scene can re-use the same instance, giving
visual continuity to the viewer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.config import PATHS, get_logger

logger = get_logger(__name__)

_REGISTRY_PATH = PATHS["json"] / "asset_registry.json"


class AssetRegistry:
    """Persistent in-memory + file-backed asset registry."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        instance_id: str,
        asset_id: str,
        params: dict[str, Any],
        scene_id: int,
        position: list[float] | None = None,
    ) -> None:
        """Register or update an asset instance."""
        self._data[instance_id] = {
            "asset_id": asset_id,
            "params": params,
            "scene_id": scene_id,
            "last_position": position or [0.0, 0.0, 0.0],
        }
        self._save()

    def get(self, instance_id: str) -> dict[str, Any] | None:
        return self._data.get(instance_id)

    def exists(self, instance_id: str) -> bool:
        return instance_id in self._data

    def update_position(self, instance_id: str, position: list[float]) -> None:
        if instance_id in self._data:
            self._data[instance_id]["last_position"] = position
            self._save()

    def all_instances(self) -> dict[str, dict[str, Any]]:
        return dict(self._data)

    def reset(self) -> None:
        self._data = {}
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if _REGISTRY_PATH.exists():
            try:
                self._data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
                logger.debug("Asset registry loaded: %d instances", len(self._data))
            except Exception as exc:
                logger.warning("Failed to load asset registry: %s — starting fresh", exc)
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        _REGISTRY_PATH.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# Module-level singleton for convenience
_registry: AssetRegistry | None = None


def get_registry() -> AssetRegistry:
    global _registry
    if _registry is None:
        _registry = AssetRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = AssetRegistry()
    _registry.reset()
