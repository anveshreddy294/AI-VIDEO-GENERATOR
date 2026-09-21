import os
import pytest

# Ensure all automated test runs use fast, deterministic mock LLM & local storage
os.environ["LLM_PROVIDER"] = "mock"
os.environ["INCLUDE_FIXTURE_SOURCES"] = "false"
os.environ["QDRANT_URL"] = ""


@pytest.fixture(autouse=True)
def default_test_environment(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_provider", "mock")
