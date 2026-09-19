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
        gen_model = getattr(settings, "generation_model", "gemini-3.5-flash")
        if model_name is not None:
            self.model_name = model_name
        elif "gemini" in gen_model.lower():
            self.model_name = gen_model
        else:
            self.model_name = "gemini-3.5-flash"
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
    """Ollama local LLM Provider via HTTP using qwen3:8b (no external dependencies)."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
    ) -> None:
        raw_url = base_url or getattr(settings, "ollama_url", None) or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.base_url = raw_url.rstrip("/")
        self.model_name = (
            model_name
            or getattr(settings, "ollama_model", None)
            or getattr(settings, "generation_model", None)
            or os.getenv("OLLAMA_MODEL", "qwen3:8b")
        )
        self.timeout = timeout if timeout is not None else float(getattr(settings, "ollama_timeout", 120.0))

    def generate_content(self, prompt: str) -> str:
        """Generate content via Ollama /api/generate endpoint."""
        url = f"{self.base_url}/api/generate"
        is_json = "json" in prompt.lower() or "{" in prompt
        req_data = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "think": False,
        }
        if is_json:
            req_data["format"] = "json"

        payload = json.dumps(req_data).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("error") or data.get("done") is False:
                    raise RuntimeError(data.get("error") or "Incomplete Ollama response")
                raw = data.get("response", "")
                if not isinstance(raw, str) or not raw.strip():
                    raise RuntimeError("Ollama returned no text")
                # Clean markdown fences if model outputs ```json ... ```
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                return cleaned
        except Exception as exc:
            raise RuntimeError(f"Ollama generation failed ({url}, model={self.model_name}): {exc}") from exc


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
    provider_name = getattr(settings, "llm_provider", os.getenv("LLM_PROVIDER", "ollama")).lower().strip()
    if provider_name == "ollama":
        return OllamaProvider()
    elif provider_name == "gemini":
        return GeminiProvider()
    elif provider_name in ("mock", "test"):
        return MockProvider()

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider_name}")
