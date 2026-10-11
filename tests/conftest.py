"""Explicit offline test modes; never inherit developer .env or mutable runtime stores."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from functools import lru_cache
from fastapi.testclient import TestClient
from uuid import UUID

import httpx
import pytest

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
# Import-time defaults are test-only. Supabase suites explicitly select their own mode.
os.environ['DATABASE_PROVIDER'] = 'file'
os.environ['LESSON_PERSISTENCE_PROVIDER'] = 'file'
os.environ.pop('POSTGRES_DSN', None)
os.environ['LLM_PROVIDER'] = 'mock'
os.environ['EMBEDDING_PROVIDER'] = 'mock'
os.environ['INCLUDE_FIXTURE_SOURCES'] = 'false'
os.environ['QDRANT_URL'] = ''
for key in list(os.environ):
    if key.startswith(('SUPABASE_', 'VISUALAI_AUTH_TEST_')):
        os.environ.pop(key)

_STORAGE = tempfile.TemporaryDirectory(prefix='visualai-pytest-')
_STORAGE_ATTRIBUTES = (
    'storage_dir', 'runtime_dir', 'registry_dir', 'upload_dir', 'processed_dir',
    'video_targets_dir', 'assessment_dir', 'learning_profiles_dir', 'qdrant_path',
    'fixtures_dir', 'video_plans_dir', 'renders_dir', 'audio_dir', 'captions_dir',
)
for attribute in _STORAGE_ATTRIBUTES:
    os.environ[attribute.upper()] = str(Path(_STORAGE.name) / attribute)


@pytest.fixture
def isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[Path]:
    """Isolate mutable stores and imported legacy path aliases for every test."""
    from app.core.config import settings
    from app.db import vector_store
    from app.services.assessment import profile, session_store
    from app.services.instructor import analytics
    for attribute in _STORAGE_ATTRIBUTES:
        directory = tmp_path / attribute
        directory.mkdir(exist_ok=True)
        monkeypatch.setattr(settings, attribute, directory)
    monkeypatch.setattr(profile, 'PROFILES_DIR', settings.learning_profiles_dir)
    monkeypatch.setattr(profile, 'LEGACY_PROFILES_DIR', tmp_path / 'no_legacy_profiles')
    monkeypatch.setattr(analytics, 'PROFILES_DIR', settings.learning_profiles_dir)
    if hasattr(request.module, 'PROFILES_DIR'):
        monkeypatch.setattr(request.module, 'PROFILES_DIR', settings.learning_profiles_dir)
    monkeypatch.setattr(session_store, 'SESSIONS_DIR', settings.assessment_dir)
    monkeypatch.setattr(session_store, 'LEGACY_SESSIONS_DIR', tmp_path / 'no_legacy_sessions')
    monkeypatch.setattr(vector_store, '_client_instance', None)
    yield tmp_path
    vector_store.close_client()


@pytest.fixture(autouse=True)
def default_test_environment(monkeypatch: pytest.MonkeyPatch, isolated_storage: Path) -> Iterator[None]:
    """Use offline models and restore dependency overrides without selecting a storage mode."""
    from app.core.config import settings
    from app.main import app
    monkeypatch.setattr(settings, 'vision_provider', 'ollama')
    monkeypatch.setattr(settings, 'llm_provider', 'mock')
    monkeypatch.setattr(settings, 'reasoning_provider', 'ollama')
    monkeypatch.setattr(settings, 'cloudflare_retry_backoff', 0.0)
    monkeypatch.setattr(settings, 'embedding_provider', 'mock')
    monkeypatch.setattr(settings, 'qdrant_url', '')
    before = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(before)


@pytest.fixture
def file_storage_mode(monkeypatch: pytest.MonkeyPatch, isolated_storage: Path) -> None:
    """Legacy algorithms and file contracts explicitly opt into isolated file storage."""
    from app.core.config import settings
    monkeypatch.setattr(settings, 'database_provider', 'file')
    monkeypatch.setenv('DATABASE_PROVIDER', 'file')


@pytest.fixture
def supabase_storage_mode(monkeypatch: pytest.MonkeyPatch, isolated_storage: Path) -> Iterator[None]:
    """Keep production source guards active with a rejecting offline transport by default."""
    from app.core.config import settings
    from app.core.supabase import SupabaseConfig, SupabaseRuntime
    from app.services.security import auth
    from app.api import sources
    import app.core.supabase as supabase
    runtime = SupabaseRuntime(SupabaseConfig('https://test.supabase.co', 'public-test-key'),
        transport=httpx.MockTransport(lambda request: httpx.Response(401)))
    monkeypatch.setattr(settings, 'database_provider', 'supabase')
    monkeypatch.setenv('DATABASE_PROVIDER', 'supabase')
    monkeypatch.setattr(settings, 'supabase_url', 'https://test.supabase.co')
    monkeypatch.setattr(settings, 'supabase_publishable_key', 'public-test-key')
    monkeypatch.setattr(auth, 'get_supabase_runtime', lambda: runtime)
    cached_runtime = lru_cache(maxsize=1)(lambda: runtime)
    monkeypatch.setattr(supabase, 'get_supabase_runtime', cached_runtime)
    monkeypatch.setattr(sources, 'get_runtime', lambda: runtime)
    yield
    cached_runtime.cache_clear()
    runtime.close()


@pytest.fixture
def authenticated_client(supabase_storage_mode: None) -> Iterator[TestClient]:
    """Override only test dependencies with a deterministic, owner-scoped repository."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.sources import source_repository
    from app.core.supabase import AuthenticatedUser, SupabaseConfig, SupabaseRuntime
    from app.services.repositories.source_repository import SupabaseSourceRepository
    from app.services.security.auth import get_current_user
    user = AuthenticatedUser(UUID('00000000-0000-4000-8000-000000000001'), None, {})
    runtime = SupabaseRuntime(SupabaseConfig('https://test.supabase.co', 'public-test-key'),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])))
    repo = SupabaseSourceRepository(user, 'test-only-token', runtime)
    overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[source_repository] = lambda: repo
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
        runtime.close()


@pytest.fixture(autouse=True)
def explicit_fixture_visual_ground_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline fixture expectations are injected only by the test harness."""
    from app.services.visual_verifier import VisualEvidenceVerifier
    from tests.visual_fixture_oracle import fixture_checks
    monkeypatch.setattr(VisualEvidenceVerifier,"_source_checks",fixture_checks)
