"""Tests for Step 2 Hardening Phase 3: LLM Provider Abstraction.

Tests:
A. test_mock_provider_generates_question
B. test_generator_accepts_injected_provider
C. test_generator_does_not_require_gemini_when_mock_provider_used
D. test_gemini_provider_isolated_from_generator
E. test_provider_failure_reaches_grounded_fallback
F. test_provider_selection_from_settings
G. test_ollama_provider_if_implemented
"""

import io
import json
import os
import sys
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services.assessment.generator import generate_question
from app.services.assessment.providers import (
    LLMProvider,
    MockProvider,
    OllamaProvider,
    get_default_provider,
)
from app.services.schemas import ConceptNode


def _sample_concept(cid="CONCEPT_INERTIA", name="Inertia", definition="Tendency to resist changes in motion."):
    return ConceptNode(
        concept_id=cid,
        name=name,
        definition=definition,
        prerequisite_concept_ids=[],
        source_content_ids=["CU_001"],
    )


def test_mock_provider_generates_question():
    print("\n--- Running Test A: test_mock_provider_generates_question ---")
    mock = MockProvider()
    raw = mock.generate_content("Sample Prompt")
    data = json.loads(raw)

    assert "question" in data, "Mock JSON must have 'question'"
    assert len(data.get("options", [])) == 4, "Mock JSON must provide exactly 4 options"
    assert "correct_index" in data, "Mock JSON must specify correct_index"

    concept = _sample_concept()
    q = generate_question(concept=concept, source_id="SRC_TEST", llm_provider=mock)

    assert q is not None, "generate_question with MockProvider must return a Question"
    assert len(q.options) == 4, f"Expected 4 options, got {len(q.options)}"
    assert mock.call_count >= 1, "MockProvider must have been called"
    print(f"   [PASS] MockProvider generated valid question: '{q.stem[:50]}...' (calls={mock.call_count})")


def test_generator_accepts_injected_provider():
    print("\n--- Running Test B: test_generator_accepts_injected_provider ---")

    class CustomInjectedProvider:
        def __init__(self):
            self.invoked = False

        def generate_content(self, prompt: str) -> str:
            self.invoked = True
            return json.dumps({
                "question": "What is the primary characteristic of inertia in classical mechanics?",
                "options": [
                    {"index": 0, "text": "Resistance to change in velocity."},
                    {"index": 1, "text": "Instantaneous acceleration without force."},
                    {"index": 2, "text": "Complete absorption of kinetic energy."},
                    {"index": 3, "text": "Spontaneous creation of momentum."},
                ],
                "correct_index": 0,
                "explanation": "Inertia quantifies resistance to acceleration.",
            })

    custom = CustomInjectedProvider()
    assert isinstance(custom, LLMProvider), "Custom provider must conform to LLMProvider protocol"

    concept = _sample_concept()
    q = generate_question(concept=concept, source_id="SRC_TEST", llm_provider=custom)

    assert q is not None
    assert custom.invoked, "Injected provider must be invoked"
    assert "inertia in classical mechanics" in q.stem
    print(f"   [PASS] Generator correctly accepted and executed injected provider: stem='{q.stem}'")


def test_generator_does_not_require_cloud_when_mock_provider_used():
    print("\n--- Running Test C: test_generator_does_not_require_cloud_when_mock_provider_used ---")
    mock = MockProvider()
    concept = _sample_concept()
    q = generate_question(concept=concept, source_id="SRC_TEST", llm_provider=mock)
    assert q is not None, "Question should generate successfully with MockProvider"
    assert len(q.options) == 4
    print("   [PASS] Question generated successfully offline when MockProvider used.")


def test_gemini_provider_strictly_removed():
    print("\n--- Running Test D: test_gemini_provider_strictly_removed ---")
    import app.services.assessment.providers as prov_mod
    import app.core.llm as llm_mod

    # Assert GeminiProvider is completely absent
    assert not hasattr(prov_mod, "GeminiProvider"), "GeminiProvider must not exist in providers.py"
    assert not hasattr(llm_mod, "GeminiProvider"), "GeminiProvider must not exist in llm.py"
    print("   [PASS] GeminiProvider is completely deleted from the codebase.")


def test_provider_failure_reaches_grounded_fallback():
    print("\n--- Running Test E: test_provider_failure_reaches_grounded_fallback ---")

    class CrashingProvider:
        def generate_content(self, prompt: str) -> str:
            raise RuntimeError("Provider service completely unreachable (HTTP 503 / Quota 429)")

    crashing = CrashingProvider()
    concept = _sample_concept(definition="Inertia is resistance of physical object to velocity change.")
    q = generate_question(
        concept=concept,
        source_id="SRC_TEST",
        llm_provider=crashing,
        max_retries=1,
    )

    assert q is not None, "Generator must not crash on provider failure; must invoke grounded fallback"
    assert len(q.options) == 4
    assert 0 <= q.correct_index <= 3
    assert "Directly derived from the source definition" in q.explanation
    print(f"   [PASS] Provider exception safely caught and routed to deterministic grounded fallback: '{q.stem}'")


def test_provider_selection_from_settings():
    print("\n--- Running Test F: test_provider_selection_from_settings ---")
    orig_prov = getattr(settings, "llm_provider", "gemini")

    try:
        settings.llm_provider = "mock"
        p_mock = get_default_provider()
        assert isinstance(p_mock, MockProvider), f"Expected MockProvider, got {type(p_mock)}"

        settings.llm_provider = "ollama"
        p_ollama = get_default_provider()
        assert isinstance(p_ollama, OllamaProvider), f"Expected OllamaProvider, got {type(p_ollama)}"

        settings.llm_provider = "gemini"
        try:
            get_default_provider()
            assert False, "Should raise RuntimeError when gemini is requested"
        except RuntimeError as exc:
            assert "completely removed" in str(exc) or "Unsupported" in str(exc)

        settings.llm_provider = "unsupported_provider_xyz"
        try:
            get_default_provider()
            assert False, "Should raise RuntimeError on unsupported provider"
        except RuntimeError:
            pass

        print("   [PASS] Provider factory properly selects MockProvider and OllamaProvider, strictly rejecting gemini/unknown.")
    finally:
        settings.llm_provider = orig_prov


def test_ollama_provider_if_implemented():
    print("\n--- Running Test G: test_ollama_provider_if_implemented ---")
    ollama = OllamaProvider(base_url="http://localhost:11434", model_name="llama3.2")

    mock_ollama_response = {
        "model": "llama3.2",
        "response": json.dumps({
            "question": "What is momentum in Newtonian mechanics?",
            "options": [
                {"index": 0, "text": "The product of the mass and velocity of an object."},
                {"index": 1, "text": "The rate of change of potential energy."},
                {"index": 2, "text": "The frictional coefficient between two bodies."},
                {"index": 3, "text": "The gravitational force exerted on an object at rest."},
            ],
            "correct_index": 0,
            "explanation": "Linear momentum is defined as p = mv.",
        }),
        "done": True,
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_ollama_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        concept = _sample_concept(cid="CONCEPT_MOMENTUM", name="Momentum", definition="Product of mass and velocity.")
        q = generate_question(concept=concept, source_id="SRC_TEST", llm_provider=ollama)

        assert q is not None, "Ollama provider must produce valid Question"
        assert q.stem == "What is momentum in Newtonian mechanics?"
        assert len(q.options) == 4
        assert 0 <= q.correct_index < len(q.options)
        assert "product of the mass and velocity" in q.options[q.correct_index].text.lower()
        assert mock_urlopen.called, "urllib.request.urlopen should have been called"

    print("   [PASS] OllamaProvider successfully communicated with adapter endpoint and generated question.")


def main():
    print("=================================================================")
    print("  TESTING STEP 2 HARDENING: LLM PROVIDER ABSTRACTION (PHASE 3)   ")
    print("=================================================================")

    test_mock_provider_generates_question()
    test_generator_accepts_injected_provider()
    test_generator_does_not_require_cloud_when_mock_provider_used()
    test_gemini_provider_strictly_removed()
    test_provider_failure_reaches_grounded_fallback()
    test_provider_selection_from_settings()
    test_ollama_provider_if_implemented()

    print("\n=================================================================")
    print("   ALL PHASE 3 LLM PROVIDER ABSTRACTION TESTS PASSED!            ")
    print("=================================================================")


if __name__ == "__main__":
    main()
