"""Storage mode isolation and authenticated business-route preconditions."""
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv
from app.core.config import settings
from app.core.supabase import SupabaseConfigurationError
from app.services.repositories.factory import get_source_repository


def test_file_mode_has_isolated_canonical_store(file_storage_mode: None, tmp_path: Path) -> None:
    from app.services.registry import register_source
    path=tmp_path/'definition.txt'
    path.write_text('Osmosis is the movement of water across a membrane.',encoding='utf-8')
    record, _=register_source(path,path.name)
    assert settings.database_provider=='file'
    assert settings.registry_dir.is_relative_to(tmp_path)
    assert record.source_id


def test_supabase_mode_still_blocks_registry(supabase_storage_mode: None) -> None:
    from app.services.registry import load_content_units
    assert settings.database_provider=='supabase'
    with pytest.raises(RuntimeError,match='local source access is disabled'):
        load_content_units('SRC_untrusted')
    with pytest.raises(SupabaseConfigurationError,match='Verified user context'):
        get_source_repository()


def test_supabase_protected_route_requires_bearer(supabase_storage_mode: None) -> None:
    from app.main import app
    assert TestClient(app).get('/pipeline/jobs/JOB_missing').status_code==401


def test_authenticated_missing_job_reaches_404(authenticated_client: TestClient) -> None:
    assert settings.database_provider=='supabase'
    assert authenticated_client.get('/pipeline/jobs/JOB_missing').status_code==404


def test_authenticated_admission_reaches_429(authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import pipeline
    monkeypatch.setattr(pipeline.job_manager,'can_accept_job',lambda:False)
    response=authenticated_client.post('/pipeline/upload-and-assess',
        files={'file':('definition.txt',b'Source evidence.','text/plain')})
    assert response.status_code==429


def test_authenticated_jobs_preserve_owner_isolation(authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import pipeline
    from app.services.pipeline_tracker import JobManager
    manager=JobManager()
    monkeypatch.setattr(pipeline,'job_manager',manager)
    own=manager.create_job('source_ingestion')
    own.metadata['source_owner']='00000000-0000-4000-8000-000000000001'
    other=manager.create_job('source_ingestion')
    other.metadata['source_owner']='00000000-0000-4000-8000-000000000002'
    assert authenticated_client.get('/pipeline/jobs/'+own.job_id).status_code==200
    assert authenticated_client.get('/pipeline/jobs/'+other.job_id).status_code==404


def test_authenticated_override_does_not_leak(supabase_storage_mode: None) -> None:
    from app.main import app
    from app.api.sources import source_repository
    from app.services.security.auth import get_current_user
    assert source_repository not in app.dependency_overrides
    assert get_current_user not in app.dependency_overrides
    assert TestClient(app).get('/sources').status_code==401


def test_dotenv_loading_disabled_in_pytest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    monkeypatch.delenv('VISUALAI_ISOLATION_SENTINEL',raising=False)
    path=tmp_path/'.env'
    path.write_text('VISUALAI_ISOLATION_SENTINEL=developer-machine-value\n',encoding='utf-8')
    assert not load_dotenv(path)
    assert 'VISUALAI_ISOLATION_SENTINEL' not in os.environ
