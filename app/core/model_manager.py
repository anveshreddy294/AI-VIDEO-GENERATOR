"""Central Model Management and Fallback Routing Engine.

Provides:
- Dynamic model switching at runtime without restart
- Automatic fallback chain: if the active model fails or does not support vision,
  subsequent models in the fallback chain are automatically invoked
- Discovers available models from local Ollama tags and registered providers
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages active model state, available models, and automatic fallback execution."""

    def __init__(self) -> None:
        self.active_provider: str = getattr(settings, "llm_provider", "ollama").lower().strip()
        self.active_model: str = getattr(settings, "ollama_model", "llama3.2:3b")
        self.fallback_chain: list[dict[str, str]] = [
            {"model": self.active_model, "provider": self.active_provider},
        ]
        # NON-NEGOTIABLE: Mock model must NEVER be part of normal runtime fallback chain.
        # Permitted only under explicit test configuration (VISUALAI_ALLOW_MOCK_FALLBACK=true).
        if os.getenv("VISUALAI_ALLOW_MOCK_FALLBACK", "").lower() in ("1", "true", "yes"):
            if self.active_model != "mock":
                self.fallback_chain.append({"model": "mock", "provider": "mock"})
        self.enable_fallback: bool = True

    def get_base_url(self) -> str:
        raw_url = (
            getattr(settings, "ollama_base_url", None)
            or getattr(settings, "ollama_url", None)
            or os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_URL", "http://localhost:11434")
        )
        return raw_url.rstrip("/")

    def get_available_models(self) -> list[dict[str, Any]]:
        """Query Ollama /api/tags to discover installed local models plus mock/cloud options."""
        models: list[dict[str, Any]] = []
        base_url = self.get_base_url()
        try:
            req = urllib.request.Request(f"{base_url}/api/tags", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for m in data.get("models", []):
                    name = m.get("name", "")
                    # Skip embedding models that cannot do text or vision completion
                    if any(emb in name.lower() for emb in ("embed", "bge-", "minilm")):
                        continue
                    caps = m.get("capabilities", [])
                    if caps and "completion" not in caps and "tools" not in caps:
                        continue
                    size_mb = round(m.get("size", 0) / (1024 * 1024), 1)
                    is_vision = any(v in name.lower() for v in ("vision", "llava", "minicpm", "gemma3"))
                    models.append({
                        "name": name,
                        "provider": "ollama",
                        "size_mb": size_mb,
                        "supports_vision": is_vision,
                        "is_active": name == self.active_model,
                    })
        except Exception as exc:
            logger.info("[model_manager] Could not fetch Ollama models (%s)", exc)

        # Ensure active model is at least present in the list
        if not any(m["name"] == self.active_model for m in models):
            models.append({
                "name": self.active_model,
                "provider": self.active_provider,
                "size_mb": 0,
                "supports_vision": "vision" in self.active_model.lower(),
                "is_active": True,
            })

        # Add mock deterministic provider option if not already present
        if not any(m["name"] == "mock" for m in models):
            models.append({
                "name": "mock",
                "provider": "mock",
                "size_mb": 0,
                "supports_vision": True,
                "is_active": self.active_model == "mock",
            })
        else:
            for m in models:
                if m["name"] == "mock":
                    m["is_active"] = self.active_model == "mock"
                    m["supports_vision"] = True

        return models

    def switch_model(
        self,
        model_name: str,
        provider: str = "ollama",
        fallback_models: list[str] | None = None,
        enable_fallback: bool | None = None,
    ) -> dict[str, Any]:
        """Switch the active generation model and configure fallback chain."""
        clean_name = model_name.strip()
        clean_provider = provider.strip().lower()
        if clean_name == "mock":
            clean_provider = "mock"

        logger.info(
            "[model_manager] Switching active model from %s (%s) to %s (%s)",
            self.active_model, self.active_provider, clean_name, clean_provider
        )

        self.active_model = clean_name
        self.active_provider = clean_provider
        if enable_fallback is not None:
            self.enable_fallback = enable_fallback

        # Update global settings so all legacy callers see the new model immediately
        settings.generation_model = clean_name
        settings.ollama_model = clean_name
        settings.llm_provider = clean_provider

        # Rebuild fallback chain
        new_chain = [{"model": clean_name, "provider": clean_provider}]
        if fallback_models:
            for fb in fallback_models:
                fb_clean = fb.strip()
                fb_provider = "mock" if fb_clean == "mock" else "ollama"
                if fb_clean != clean_name:
                    new_chain.append({"model": fb_clean, "provider": fb_provider})
        else:
            if clean_name != "llama3.2:3b":
                new_chain.append({"model": "llama3.2:3b", "provider": "ollama"})
            if os.getenv("VISUALAI_ALLOW_MOCK_FALLBACK", "").lower() in ("1", "true", "yes"):
                if clean_name != "mock":
                    new_chain.append({"model": "mock", "provider": "mock"})

        self.fallback_chain = new_chain
        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        """Return comprehensive status of active model, available models, and fallbacks."""
        available = self.get_available_models()
        return {
            "active_model": self.active_model,
            "active_provider": self.active_provider,
            "enable_fallback": self.enable_fallback,
            "fallback_chain": self.fallback_chain,
            "available_models": available,
        }

    def generate_with_fallback(
        self,
        prompt: str,
        images: list[str] | None = None,
        is_json: bool = True,
        timeout: float = 30.0,
    ) -> tuple[str, str]:
        """Attempt generation using active model; automatically falls back through chain if failure occurs.

        Returns:
            tuple of (response_text, model_name_used)
        """
        chain = self.fallback_chain if self.enable_fallback else [{"model": self.active_model, "provider": self.active_provider}]
        last_err: Exception | None = None

        for candidate in chain:
            m_name = candidate["model"]
            m_provider = candidate["provider"]

            try:
                logger.info("[model_manager] Attempting generation with model=%s provider=%s", m_name, m_provider)
                if m_provider == "mock" or m_name == "mock":
                    from .llm import MockProvider
                    mock_p = MockProvider()
                    resp = mock_p.generate(prompt)
                    if resp and resp.strip():
                        return resp.strip(), "mock"

                elif m_provider == "ollama":
                    base_url = self.get_base_url()
                    url = f"{base_url}/api/generate"
                    req_data: dict[str, Any] = {
                        "model": m_name,
                        "prompt": prompt,
                        "stream": False,
                        "think": False,
                    }
                    if is_json:
                        req_data["format"] = "json"
                    if images:
                        req_data["images"] = images

                    payload = json.dumps(req_data).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        if data.get("error"):
                            raise RuntimeError(data.get("error"))
                        raw = data.get("response", "")
                        if raw and raw.strip():
                            return raw.strip(), m_name
                        raise ValueError(f"Model {m_name} returned empty response")

            except Exception as exc:
                last_err = exc
                logger.warning(
                    "[model_manager] Model '%s' (%s) failed: %s. Trying next model in fallback chain...",
                    m_name, m_provider, exc
                )

        # If everything in the chain failed, raise
        raise RuntimeError(f"All models in fallback chain failed. Last error: {last_err}")


# Global singleton
model_manager = ModelManager()
