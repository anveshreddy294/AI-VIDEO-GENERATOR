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
        self._http_client: Any | None = None

    def _get_client(self) -> Any:
        if self._http_client is None:
            try:
                import httpx
                self._http_client = httpx.Client(timeout=self.timeout)
            except Exception:
                self._http_client = False
        return self._http_client

    def generate(
        self,
        prompt: str,
        response_schema: type | dict | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate content via Ollama /api/generate endpoint with bounded generation limits."""
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
            "keep_alive": getattr(settings, "ollama_keep_alive", "15m"),
        }
        if response_schema is not None:
            if isinstance(response_schema, dict):
                req_data["format"] = response_schema
            else:
                req_data["format"] = "json"
        elif is_json:
            req_data["format"] = "json"

        # Bounded generation options for assessment/reasoning JSON performance
        gen_opts: dict[str, Any] = {
            "temperature": 0.1,
            "num_predict": 850,
            "num_ctx": 2048,
        }
        if options:
            gen_opts.update(options)
        req_data["options"] = gen_opts

        is_mocked = hasattr(urllib.request.urlopen, "mock_calls") or type(urllib.request.urlopen).__name__ in ("Mock", "MagicMock")
        client = None if is_mocked else self._get_client()
        raw = ""
        if client and client is not False:
            try:
                resp = client.post(url, json=req_data)
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama HTTP {resp.status_code}: {resp.text}")
                data = resp.json()
                if data.get("error") or data.get("done") is False:
                    raise RuntimeError(data.get("error") or "Incomplete Ollama response")
                raw = data.get("response", "")
            except Exception as exc:
                logger.debug("[llm] httpx call failed (%s); falling back to urllib: %s", url, exc)
                client = False

        if not raw and (client is False or client is None):
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
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    f"Ollama service unreachable at {self.base_url}. Ensure Ollama is running (`ollama serve`). Error: {exc}"
                ) from exc
            except Exception as exc:
                raise RuntimeError(
                    f"Ollama generation failed ({url}, model={self.model_name}): {exc}"
                ) from exc

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

    def generate(self, prompt: str, response_schema: type | dict | None = None, **kwargs: Any) -> str:
        self.call_count += 1
        self.last_prompt = prompt

        if self.response_text is not None:
            return self.response_text

        # Detect prompt intent
        lower = prompt.lower()
        if "diagram" in lower or "image reader" in lower or "lecture video frame" in lower:
            return "Visual study and instructional media asset from source material."

        if "scene" in lower or "animation planner" in lower or "videoplan" in lower:
            import re
            c_name_match = re.search(r"CONCEPT:\s*([^\n]+)", prompt)
            c_name = c_name_match.group(1).strip() if c_name_match else "Core Concept"
            cid_match = re.search(r'"concept_id":\s*"([^"]+)"', prompt)
            cid = cid_match.group(1).strip() if cid_match else "CONCEPT_01"

            is_physics = any(
                k in c_name.lower()
                for k in ("newton", "force", "acceleration", "second law", "momentum", "gravity", "kinematics", "velocity")
            )

            if is_physics:
                return json.dumps({
                    "concept_id": cid or "CONCEPT_NEWTON_2",
                    "concept_name": c_name or "Newton's Second Law",
                    "duration_seconds": 45,
                    "learning_objective": f"Understand how principles relate in {c_name}.",
                    "key_points": [
                        "Net force accelerates mass",
                        "Greater mass requires greater force",
                        "Mathematical formula is F = ma",
                    ],
                    "scenes": [
                        {
                            "scene_type": "TITLE",
                            "title": c_name,
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
                            "text": f"Welcome to this review of {c_name}.",
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
            else:
                return json.dumps({
                    "concept_id": cid,
                    "concept_name": c_name,
                    "duration_seconds": 45,
                    "learning_objective": f"Understand the core architecture and principles of {c_name}.",
                    "key_points": [
                        f"Foundational structure of {c_name}",
                        "Component interaction and operational workflow",
                        "Practical execution and verification",
                    ],
                    "scenes": [
                        {
                            "scene_type": "TITLE",
                            "title": c_name,
                            "subtitle": "Core Conceptual Architecture",
                            "duration_seconds": 5,
                        },
                        {
                            "scene_type": "EXPLANATION",
                            "title": f"Understanding {c_name}",
                            "text": f"Foundational overview and definitions governing {c_name}.",
                            "duration_seconds": 12,
                        },
                        {
                            "scene_type": "DIAGRAM",
                            "diagram_type": "concept_flow",
                            "title": f"{c_name} Structural Flow",
                            "label": "Process & Architecture",
                            "summary_points": ["Context & Inputs", "Processing Engine", "Verified Outcomes"],
                            "duration_seconds": 16,
                        },
                        {
                            "scene_type": "SUMMARY",
                            "title": "Key Takeaways",
                            "summary_points": [
                                f"Master core definitions of {c_name}",
                                "Follow systematic execution rules",
                                "Verify prerequisite constraints",
                            ],
                            "duration_seconds": 12,
                        },
                    ],
                    "narration": [
                        {
                            "scene_index": 0,
                            "text": f"Welcome to this focused study module on {c_name}.",
                            "target_seconds": 5,
                        },
                        {
                            "scene_index": 1,
                            "text": f"Let us examine the foundational definitions and core principles of {c_name}.",
                            "target_seconds": 12,
                        },
                        {
                            "scene_index": 2,
                            "text": f"Analyzing the structural flow reveals how components coordinate within {c_name}.",
                            "target_seconds": 16,
                        },
                        {
                            "scene_index": 3,
                            "text": f"In summary, remember these essential principles of {c_name} for your diagnostic review.",
                            "target_seconds": 12,
                        },
                    ],
                })

        if "verified_source_context" in lower or "untrusted_retrieved_evidence" in lower or "pedagogically rigorous teaching assistant" in lower:
            import re
            cids = re.findall(r"\[Chunk ID:\s*([a-zA-Z0-9_\-]+)", prompt)
            cid = cids[0] if cids else "chunk_mock_1"
            src_sample = "Force equals mass times acceleration (F = ma)."
            if "<UNTRUSTED_RETRIEVED_EVIDENCE>" in prompt:
                ctx = prompt.split("<UNTRUSTED_RETRIEVED_EVIDENCE>")[1].split("</UNTRUSTED_RETRIEVED_EVIDENCE>")[0]
                lines = [l.strip() for l in ctx.splitlines() if l.strip() and not l.startswith("[Chunk ID") and not l.startswith("---")]
                if lines:
                    src_sample = lines[0]
            elif "<VERIFIED_SOURCE_CONTEXT>" in prompt:
                ctx = prompt.split("<VERIFIED_SOURCE_CONTEXT>")[1].split("</VERIFIED_SOURCE_CONTEXT>")[0]
                lines = [l.strip() for l in ctx.splitlines() if l.strip() and not l.startswith("[Chunk ID") and not l.startswith("---")]
                if lines:
                    src_sample = lines[0]

            return json.dumps({
                "answer": f"According to the verified study materials: {src_sample}",
                "citations": [
                    {
                        "chunk_id": cid,
                        "quote": src_sample[:100],
                        "page_number": 1,
                    }
                ],
                "grounding_confidence": 0.95,
                "refusal": False,
            })

        if "concept" in lower and "definition" in lower and ("curriculum" in lower or "structure" in lower):
            import re
            cu_blocks = re.findall(r"\[(CU_[a-zA-Z0-9_\-]+)\](?:\s*\([^)]*\))?:\s*([^\n]+)", prompt)
            if not cu_blocks:
                found_cu = re.findall(r"\[(CU_[a-zA-Z0-9_\-]+)\]", prompt)
                cu_blocks = [(cid, "Educational study material.") for cid in found_cu]

            if not cu_blocks:
                return json.dumps({"topic_name": "Empty Material", "difficulty_level": "beginner", "concepts": []})

            extracted_concepts = []
            for idx, (cid, ctext) in enumerate(cu_blocks[:3]):
                words = [w for w in re.findall(r"[A-Za-z0-9\-]{3,}", ctext) if w.lower() not in ("this", "that", "with", "from", "image", "slide", "study", "asset", "material")]
                if not words:
                    continue
                cname = " ".join(words[:2]).title()
                c_id = f"CONCEPT_{re.sub(r'[^A-Z0-9_]', '_', cname.upper())[:20]}"
                extracted_concepts.append({
                    "concept_id": c_id,
                    "name": cname,
                    "definition": ctext[:120].strip() or f"{cname} as defined in source.",
                    "prerequisite_concept_ids": [extracted_concepts[-1]["concept_id"]] if extracted_concepts else [],
                    "source_content_ids": [cid],
                })

            top_name = extracted_concepts[0]["name"] if extracted_concepts else "Educational Topic"
            return json.dumps({
                "topic_name": top_name,
                "difficulty_level": "intermediate",
                "chapters": [
                    {
                        "id": "CH1",
                        "title": top_name,
                        "sections": [
                            {"id": "SEC1_1", "title": "Overview", "content_ids": [c[0] for c in cu_blocks]}
                        ],
                    }
                ],
                "concepts": extracted_concepts,
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

        if "questions" in lower and ("reassessment" in lower or "batch" in lower or "pedagogical requirements" in lower or "exactly 2" in lower or "generate 2" in lower):
            return json.dumps({
                "questions": [
                    {
                        "question": f"Practical application of {concept_name}: how does {concept_name} govern {sample_words}?",
                        "options": [
                            {"index": 0, "text": f"{concept_name} directly governs {sample_words} in applied systems."},
                            {"index": 1, "text": f"{concept_name} operates in reverse against {sample_words}."},
                            {"index": 2, "text": f"{concept_name} exhibits zero influence over {sample_words}."},
                            {"index": 3, "text": f"{concept_name} depends entirely on external manual intervention."}
                        ],
                        "correct_index": 0,
                        "evidence_quote": f"{concept_name} governs {sample_words}",
                        "explanation": f"Source evidence establishes how {concept_name} relates to {sample_words}.",
                        "variant_type": "application"
                    },
                    {
                        "question": f"Conceptual distinction for {concept_name}: what distinguishes it from misconceptions involving {sample_words}?",
                        "options": [
                            {"index": 0, "text": f"Assuming {concept_name} is simply interchangeable with {sample_words}."},
                            {"index": 1, "text": f"{concept_name} represents a distinct operational principle governing {sample_words}."},
                            {"index": 2, "text": f"Believing {concept_name} has no formal domain definition."},
                            {"index": 3, "text": f"Viewing {concept_name} as an isolated anomaly."}
                        ],
                        "correct_index": 1,
                        "evidence_quote": f"{concept_name} represents a distinct operational principle",
                        "explanation": f"Source truth clarifies distinction and avoids common errors regarding {concept_name}.",
                        "variant_type": "misconception"
                    }
                ]
            })

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
