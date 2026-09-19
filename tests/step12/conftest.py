"""Isolated storage for Step 1–2 regression tests; never use real artifacts."""
import os
import tempfile
from pathlib import Path

import pytest

_storage = tempfile.TemporaryDirectory(prefix="visualai-step12-")
_root = Path(_storage.name)
for name in ("STORAGE_DIR", "RUNTIME_DIR", "REGISTRY_DIR", "UPLOAD_DIR", "PROCESSED_DIR", "VIDEO_TARGETS_DIR", "ASSESSMENT_DIR", "LEARNING_PROFILES_DIR", "QDRANT_PATH", "FIXTURES_DIR"):
    os.environ[name] = str(_root / name.lower())
os.environ["INCLUDE_FIXTURE_SOURCES"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["QDRANT_URL"] = ""


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services.assessment import profile, session_store
    from app.db import vector_store
    for name in ("runtime_dir", "registry_dir", "upload_dir", "processed_dir", "video_targets_dir", "assessment_dir", "learning_profiles_dir", "qdrant_path", "fixtures_dir"):
        directory = tmp_path / name
        directory.mkdir()
        monkeypatch.setattr(settings, name, directory)
    monkeypatch.setattr(profile, "PROFILES_DIR", settings.learning_profiles_dir)
    monkeypatch.setattr(profile, "LEGACY_PROFILES_DIR", tmp_path / "no_legacy_profiles")
    monkeypatch.setattr(session_store, "SESSIONS_DIR", settings.assessment_dir)
    monkeypatch.setattr(session_store, "LEGACY_SESSIONS_DIR", tmp_path / "no_legacy_sessions")
    monkeypatch.setattr(vector_store, "_client_instance", None)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    yield
    if vector_store._client_instance is not None:
        vector_store._client_instance.close()
