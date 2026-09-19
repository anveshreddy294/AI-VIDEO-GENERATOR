"""LLM Provider abstraction for Step 2 Assessment Question Generation.

Decouples assessment question generation from any specific LLM SDK, providing:
1. LLMProvider interface (Protocol)
2. GeminiProvider (encapsulates google.generativeai)
3. OllamaProvider (local HTTP endpoint adapter)
4. MockProvider (offline, deterministic testing without API keys)
5. get_default_provider() factory function
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

from ...core.config import settings


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract interface for LLM content generation."""

    def generate_content(self, prompt: str) -> str:
        """Generate raw text response for the provided prompt."""
        ...


class GeminiProvider:
    """Google Gemini LLM Provider encapsulating SDK configuration and model calls."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model_name = model_name if model_name is not None else settings.generation_model
        self._model = None

    def _init_client(self):
        if self._model is not None:
            return self._model
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)
        return self._model

    def generate_content(self, prompt: str) -> str:
        """Generate content via Gemini API."""
        model = self._init_client()
        response = model.generate_content(prompt)
        return response.text or ""


class OllamaProvider:
    """Ollama local LLM Provider via HTTP (no external dependencies)."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        raw_url = base_url or getattr(settings, "ollama_url", None) or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.base_url = raw_url.rstrip("/")
        self.model_name = model_name or getattr(settings, "ollama_model", None) or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.timeout = timeout

    def generate_content(self, prompt: str) -> str:
        """Generate content via Ollama /api/generate endpoint."""
        url = f"{self.base_url}/api/generate"
        payload = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")
        except Exception as exc:
            raise RuntimeError(f"Ollama generation failed ({url}, model={self.model_name}): {exc}") from exc


class OmniRouteProvider:
    """OmniRoute LLM Provider via OpenAI-compatible HTTP interface."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "omniroute_api_key", "") or os.getenv("OMNIROUTE_API_KEY", "")
        self.base_url = (base_url or getattr(settings, "omniroute_base_url", "http://localhost:20128/v1") or "http://localhost:20128/v1").rstrip("/")
        self.model_name = model_name or getattr(settings, "omniroute_model", "static-best-reasoning") or "static-best-reasoning"

    def generate_content(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OMNIROUTE_API_KEY is not set.")
        url = f"{self.base_url}/chat/completions"
        payload = json.dumps({
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"OmniRoute generation failed ({url}): {exc}") from exc


class MockProvider:
    """Deterministic Mock LLM Provider for testing without API keys or internet."""

    is_mock: bool = True

    def __init__(self, response_text: str | None = None) -> None:
        self.response_text = response_text
        self.call_count = 0
        self.last_prompt = ""
        self.is_mock = True

    def generate_content(self, prompt: str) -> str:
        """Generate deterministic mock question JSON."""
        self.call_count += 1
        self.last_prompt = prompt

        if self.response_text is not None:
            return self.response_text

        return json.dumps({
            "question": "Which statement best characterizes the core principle of this concept?",
            "options": [
                {"index": 0, "text": "It serves as the primary governing law within the system."},
                {"index": 1, "text": "It operates in reverse, negating any structural relationship."},
                {"index": 2, "text": "It functions solely as an arbitrary cache layer without impact."},
                {"index": 3, "text": "It is strictly deprecated in modern system architectures."},
            ],
            "correct_index": 0,
            "explanation": "Directly grounded in the authoritative study material definition.",
        })


def get_default_provider() -> LLMProvider:
    """Factory function returning the configured LLM provider based on settings.

    Fails immediately on unsupported or missing provider configurations rather than
    silently swapping the AI backend.
    """
    provider_name = getattr(settings, "llm_provider", os.getenv("LLM_PROVIDER", "gemini")).lower().strip()
    if provider_name == "gemini":
        return GeminiProvider()
    elif provider_name == "omniroute":
        return OmniRouteProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    elif provider_name in ("mock", "test"):
        return MockProvider()

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider_name}")
