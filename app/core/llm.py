"""Universal LLM Provider abstraction for AI-VIDEO-GENERATOR.
 
Decouples core reasoning (Step 1 Ingestion, Step 2 Assessment, Step 3 Video Planning)
from any specific cloud SDK or vendor.
 
Supported Providers:
- OllamaProvider: Local lightweight model (Llama 3.2 3B) via HTTP endpoint.
- MockProvider / MockLLMProvider: Deterministic responses for offline testing without internet/API keys.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Protocol, runtime_checkable

from .config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract protocol for text generation and structured reasoning."""

    def generate_content(self, prompt: str) -> str:
        """Generate text response for the provided prompt."""
        ...


class OllamaProvider:
    """Ollama local LLM Provider via HTTP (no external cloud SDKs)."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
    ) -> None:
        raw_url = (
            base_url
            or getattr(settings, "ollama_base_url", None)
            or getattr(settings, "ollama_url", None)
            or os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_URL", "http://localhost:11434")
        )
        self.base_url = raw_url.rstrip("/")
        self.model_name = (
            model_name
            or getattr(settings, "ollama_model", None)
            or getattr(settings, "generation_model", None)
            or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        )
        self.timeout = timeout if timeout is not None else float(getattr(settings, "ollama_timeout", 120.0))

    def generate(self, prompt: str, response_schema: type | None = None) -> str:
        """Generate content via Ollama /api/generate endpoint."""
        url = f"{self.base_url}/api/generate"
        is_json = (
            response_schema is not None
            or "json" in prompt.lower()
            or "{" in prompt
        )
        req_data: dict[str, Any] = {
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

                # Strip markdown code fences if the model wraps output in ```json ... ```
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                return cleaned
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama service unreachable at {self.base_url}. Ensure Ollama is running (`ollama serve`). Error: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Ollama generation failed ({url}, model={self.model_name}): {exc}"
            ) from exc

    def generate_content(self, prompt: str) -> str:
        """Alias for backward compatibility with assessment generator."""
        return self.generate(prompt)

    def health_check(self) -> dict[str, Any]:
        """Check if Ollama server is reachable and inspect loaded models."""
        url = f"{self.base_url}/api/tags"
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                latency_ms = int((time.time() - t0) * 1000)
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                model_loaded = any(self.model_name in m for m in models) if models else False
                return {
                    "provider": "ollama",
                    "configured_model": self.model_name,
                    "reachable": True,
                    "model_available": model_loaded,
                    "available_models": models,
                    "latency_ms": latency_ms,
                    "base_url": self.base_url,
                }
        except Exception as exc:
            return {
                "provider": "ollama",
                "configured_model": self.model_name,
                "reachable": False,
                "model_available": False,
                "available_models": [],
                "latency_ms": int((time.time() - t0) * 1000),
                "error": str(exc),
                "base_url": self.base_url,
            }


class MockProvider:
    """Deterministic Mock LLM Provider for offline testing and deterministic runs."""

    is_mock: bool = True

    def __init__(self, response_text: str | None = None) -> None:
        self.response_text = response_text
        self.call_count = 0
        self.last_prompt = ""
        self.is_mock = True

    def generate(self, prompt: str, response_schema: type | None = None) -> str:
        self.call_count += 1
        self.last_prompt = prompt

        if self.response_text is not None:
            return self.response_text

        # Detect prompt intent
        lower = prompt.lower()
        if "scene" in lower or "animation planner" in lower or "videoplan" in lower:
            return json.dumps({
                "concept_id": "CONCEPT_NEWTON_2",
                "concept_name": "Newton's Second Law",
                "duration_seconds": 45,
                "learning_objective": "Understand how force, mass, and acceleration relate via F = ma.",
                "key_points": [
                    "Net force accelerates mass",
                    "Greater mass requires greater force",
                    "Mathematical formula is F = ma",
                ],
                "scenes": [
                    {
                        "scene_type": "TITLE",
                        "title": "Newton's Second Law",
                        "subtitle": "Force, Mass, and Acceleration",
                        "duration_seconds": 5,
                    },
                    {
                        "scene_type": "EQUATION",
                        "equation": "F = ma",
                        "label": "Fundamental Law of Dynamics",
                        "duration_seconds": 10,
                    },
                    {
                        "scene_type": "DIAGRAM",
                        "diagram_type": "force_box",
                        "object_label": "Mass (m = 2 kg)",
                        "force_label": "Force (F = 6 N)",
                        "acceleration_label": "Acceleration (a = 3 m/s^2)",
                        "duration_seconds": 18,
                    },
                    {
                        "scene_type": "SUMMARY",
                        "summary_points": [
                            "Force causes acceleration",
                            "Mass resists acceleration",
                            "F = ma connects them all",
                        ],
                        "duration_seconds": 12,
                    },
                ],
                "narration": [
                    {
                        "scene_index": 0,
                        "text": "Welcome to this review of Newton's Second Law of Motion.",
                        "target_seconds": 5,
                    },
                    {
                        "scene_index": 1,
                        "text": "At its heart is a simple formula: Force equals mass times acceleration.",
                        "target_seconds": 10,
                    },
                    {
                        "scene_index": 2,
                        "text": "When you apply a net force to an object, it accelerates in the direction of the force.",
                        "target_seconds": 18,
                    },
                    {
                        "scene_index": 3,
                        "text": "Remember: more mass requires more force, governed strictly by F equals m a.",
                        "target_seconds": 12,
                    },
                ],
            })

        if "concept" in lower and "definition" in lower and ("curriculum" in lower or "structure" in lower):
            import re
            found_cu = re.findall(r"\[(CU_[a-zA-Z0-9_\-]+)\]", prompt)
            cu1 = found_cu[0] if found_cu else "CU_001"
            cu2 = found_cu[1] if len(found_cu) > 1 else cu1
            return json.dumps({
                "topic_name": "Classical Mechanics",
                "difficulty_level": "intermediate",
                "chapters": [
                    {
                        "id": "CH1",
                        "title": "Laws of Motion",
                        "sections": [
                            {"id": "SEC1_1", "title": "Fundamentals", "content_ids": [cu1, cu2]}
                        ],
                    }
                ],
                "concepts": [
                    {
                        "concept_id": "CONCEPT_FORCE",
                        "name": "Force",
                        "definition": "An interaction that changes an object's state of motion.",
                        "prerequisite_concept_ids": [],
                        "source_content_ids": [cu1],
                    },
                    {
                        "concept_id": "CONCEPT_NEWTON_2",
                        "name": "Newton's Second Law",
                        "definition": "Force equals mass multiplied by acceleration (F = ma).",
                        "prerequisite_concept_ids": ["CONCEPT_FORCE"],
                        "source_content_ids": [cu2],
                    },
                ],
            })

        # Default assessment question JSON - grounded dynamically if prompt contains concept or source material
        import re
        c_match = re.search(r"CONCEPT:\s*([^\n]+)", prompt)
        concept_name = c_match.group(1).strip() if c_match else "Newton's Second Law"

        angle_match = re.search(r"PEDAGOGICAL ANGLE:\s*([^\n\.]+)", prompt)
        angle = angle_match.group(1).strip() if angle_match else "Core Definition"

        # Find significant source tokens for grounding
        src = ""
        if "SOURCE MATERIAL" in prompt:
            part = prompt.split("SOURCE MATERIAL", 1)[1]
            if ":\n" in part:
                part = part.split(":\n", 1)[1]
            if "STRICT INSTRUCTIONS" in part:
                src = part.split("STRICT INSTRUCTIONS", 1)[0]
            else:
                src = part[:500]
        else:
            src = prompt

        stop_words = {
            "this", "that", "with", "from", "which", "what", "where", "when",
            "about", "according", "statement", "describes", "characterizes",
            "study", "material", "curriculum", "source", "following", "defined",
            "concept", "principle", "based", "learning", "state", "primarily", "chunk",
        }
        
        # Ground tokens relative to concept position in src to prevent cross-concept duplicate collisions
        concept_src = src
        if concept_name.lower() in src.lower():
            c_idx = src.lower().find(concept_name.lower())
            concept_src = src[c_idx:]

        concept_words = [
            w for w in re.findall(r"\b[a-zA-Z]{4,}\b", concept_src.lower())
            if w not in stop_words and w != concept_name.lower()
        ]
        if not concept_words:
            all_src_words = [
                w for w in re.findall(r"\b[a-zA-Z]{4,}\b", src.lower())
                if w not in stop_words
            ]
            concept_words = all_src_words

        sample_words = " ".join(concept_words[:4]) if concept_words else "force mass acceleration"

        return json.dumps({
            "question": f"How does {concept_name} relate to {sample_words} regarding {angle}?",
            "options": [
                {"index": 0, "text": f"The foundational principle directly establishes that {concept_name} governs {sample_words} ({angle})."},
                {"index": 1, "text": f"In terms of {angle}, {concept_name} contradicts observations of {sample_words}."},
                {"index": 2, "text": f"Under {angle}, {concept_name} operates independently of {sample_words}."},
                {"index": 3, "text": f"Analysis of {concept_name} under {angle} shows negligible effect on {sample_words}."},
            ],
            "correct_index": 0,
            "explanation": f"The study material confirms that {concept_name} relates to {sample_words}.",
        })

    def generate_content(self, prompt: str) -> str:
        return self.generate(prompt)

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": "mock",
            "configured_model": "mock-deterministic",
            "reachable": True,
            "model_available": True,
            "latency_ms": 0,
        }


# Alias for backward compatibility
MockLLMProvider = MockProvider


def get_llm_provider(provider_override: str | None = None) -> LLMProvider:
    """Factory function returning the configured LLM provider based on settings."""
    provider_name = (provider_override or getattr(settings, "llm_provider", "ollama")).lower().strip()
    if provider_name == "ollama":
        return OllamaProvider()
    elif provider_name in ("mock", "test"):
        return MockProvider()

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER: '{provider_name}'. "
        "Gemini and OmniRoute have been completely removed. Supported providers are 'ollama' and 'mock'."
    )


# Backward-compatible factory alias
get_default_provider = get_llm_provider
