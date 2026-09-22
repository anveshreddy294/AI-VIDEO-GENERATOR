"""API routes for Model Management, Runtime Switching, and Fallback Routing."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.model_manager import model_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["Model Management"])


class SwitchModelRequest(BaseModel):
    model: str = Field(description="Target model identifier to activate, e.g. 'llama3.2:3b', 'mock'")
    provider: str = Field(default="ollama", description="Provider type: 'ollama' or 'mock'")
    fallback_models: list[str] | None = Field(
        default=None,
        description="Optional ordered list of fallback models if active model fails",
    )
    enable_fallback: bool | None = Field(
        default=None,
        description="Whether automatic fallback is enabled",
    )


class ModelStatusResponse(BaseModel):
    active_model: str
    active_provider: str
    enable_fallback: bool
    fallback_chain: list[dict[str, str]]
    available_models: list[dict[str, Any]]


@router.get("", response_model=ModelStatusResponse)
@router.get("/", response_model=ModelStatusResponse)
def get_models_status() -> dict[str, Any]:
    """Retrieve currently active model, available local models, and fallback chain."""
    return model_manager.get_status()


@router.post("/switch", response_model=ModelStatusResponse)
def switch_active_model(req: SwitchModelRequest) -> dict[str, Any]:
    """Switch active model and configure fallback chain in runtime."""
    try:
        updated = model_manager.switch_model(
            model_name=req.model,
            provider=req.provider,
            fallback_models=req.fallback_models,
            enable_fallback=req.enable_fallback,
        )
        return updated
    except Exception as exc:
        logger.error("[models_api] Failed to switch model: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
