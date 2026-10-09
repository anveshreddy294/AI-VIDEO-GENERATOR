"""Exercise real HTTP authorization dependencies; transport doubles are not live RLS proof."""
from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterator
from uuid import UUID
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import settings
from app.core.supabase import AuthenticatedUser, SupabaseConfig, SupabaseConfigurationError, SupabaseRuntime
from app.main import app
from app.services.repositories.source_repository import SupabaseSourceRepository
from app.services.security.source_scope import SourceScope, relational_version, require_source_scope, vector_version

OWNER = UUID('00000000-0000-4000-8000-000000000001')
OTHER = UUID('00000000-0000-4000-8000-000000000002')
URL = 'https://security.supabase.co'
TEST_TOKEN_EXPIRY = int(time.time()) + 300
PREFIXES = ('/assessment/', '/qa/', '/video/', '/api/learning/', '/instructor/')
ROUTES = [(method.upper(), path) for path, operations in app.openapi()['paths'].items()
          if (path.startswith(PREFIXES) or path in {'/debug/qdrant', '/api/models/switch'})
          and path != '/api/learning/explain'
          for method in operations if method in {'get', 'post', 'put', 'patch', 'delete', 'head'}]
assert all(any(path.startswith(prefix) for _, path in ROUTES) for prefix in PREFIXES), \
    'Endpoint inventory must include every registered domain router'


def token_for(owner: UUID) -> str:
    claims = {'sub': str(owner), 'iss': URL + '/auth/v1', 'aud': 'authenticated',
              'role': 'authenticated', 'exp': TEST_TOKEN_EXPIRY}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return 'header.' + payload + '.accepted-test-signature'


def route_url(path: str) -> str:
    import re
    return re.sub(r'\{([^}]+)\}', lambda match: str(OWNER) if match[1] in {'user_id', 'student_id'}
                  else 'SRC_foreign' if match[1] == 'source_id' else 'foreign-resource', path)


@pytest.fixture
def boundary_runtime(monkeypatch: pytest.MonkeyPatch, supabase_storage_mode: None) -> Iterator[tuple[SupabaseRuntime, list[str]]]:
    from app.services.security import auth
    from app.api import sources
    calls: list[str] = []
    owner_token = token_for(OWNER)

    def remote(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers['apikey'] == 'public-test-key'
        if request.headers.get('authorization') != 'Bearer ' + owner_token:
            return httpx.Response(401, json={'message': 'secret-never-expose'})
        if request.url.path == '/auth/v1/user':
            return httpx.Response(200, json={'id': str(OWNER)})
        if request.url.path == '/rest/v1/profiles':
            return httpx.Response(200, json=[{'id': str(OWNER), 'role': 'student',
                                             'created_at': 'now', 'updated_at': 'now'}])
        assert request.method == 'GET'
        assert request.url.params['user_id'] == 'eq.' + str(OWNER)
        if request.url.params.get('source_id') != 'eq.SRC_owned':
            return httpx.Response(200, json=[])
        if request.url.path == '/rest/v1/sources':
            return httpx.Response(200, json=[{'source_id': 'SRC_owned', 'user_id': str(OWNER),
                'filename': 'owned.txt', 'source_type': 'txt', 'mime_type': 'text/plain',
                'file_hash': 'hash', 'file_size': 1, 'version': 2, 'source_version': 'v2'}])
        if request.url.path == '/rest/v1/source_versions':
            if request.url.params['version'] != 'eq.2':
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[{'user_id': str(OWNER), 'source_id': 'SRC_owned',
                'version': 2, 'source_version': 'v2', 'filename': 'owned.txt',
                'file_hash': 'hash', 'file_location': 'owned-original.txt'}])
        raise AssertionError('Unexpected canonical operation')

    runtime = SupabaseRuntime(SupabaseConfig(URL, 'public-test-key', 'secret-never-use'),
                              transport=httpx.MockTransport(remote))
    monkeypatch.setattr(auth, 'get_supabase_runtime', lambda: runtime)
    monkeypatch.setattr(sources, 'get_runtime', lambda: runtime)
    yield runtime, calls
    runtime.close()


@pytest.mark.parametrize('method,path', ROUTES)
def test_every_legacy_route_rejects_anonymous_before_storage(
    boundary_runtime: tuple[SupabaseRuntime, list[str]], method: str, path: str,
) -> None:
    response = TestClient(app).request(method, route_url(path), json={})
    assert response.status_code == 401, (method, path, response.text)
    assert boundary_runtime[1] == []


@pytest.mark.parametrize('method,path', ROUTES)
def test_every_legacy_route_authenticates_then_fails_closed(
    boundary_runtime: tuple[SupabaseRuntime, list[str]], method: str, path: str,
) -> None:
    response = TestClient(app).request(method, route_url(path), headers={'Authorization': 'Bearer ' + token_for(OWNER)},
                                      json={'user_id': str(OTHER), 'student_id': str(OTHER)})
    if path in {'/qa/answer', '/qa/evidence'}:
        assert response.status_code == 422, (method, path, response.text)
        assert response.json()['detail']['code'] == 'INVALID_SCOPE'
    else:
        assert response.status_code == 409, (method, path, response.text)
        assert response.json()['detail']['code'] == 'SUPABASE_LEARNING_NOT_INTEGRATED'
    assert boundary_runtime[1] == ['/auth/v1/user']
    assert 'secret-never-use' not in response.text


def test_forged_token_and_foreign_trace_label_do_not_reach_stores(
    boundary_runtime: tuple[SupabaseRuntime, list[str]],
) -> None:
    client = TestClient(app)
    assert client.get('/api/learning/SRC_owned/state', headers={'Authorization': 'Bearer ' + token_for(OTHER)}).status_code == 401
    response = client.get(f'/qa/traces/{OTHER}/SRC_owned', headers={'Authorization': 'Bearer ' + token_for(OWNER)})
    assert response.status_code == 404


def test_source_scope_is_owned_explicit_and_persistent_across_clients(
    boundary_runtime: tuple[SupabaseRuntime, list[str]],
) -> None:
    headers = {'Authorization': 'Bearer ' + token_for(OWNER)}
    for client in (TestClient(app), TestClient(app)):
        assert client.get('/sources/SRC_owned/versions/2', headers=headers).status_code == 200
        assert client.get('/sources/SRC_foreign/versions/2', headers=headers).status_code == 404
        assert client.get('/sources/SRC_owned/versions/1', headers=headers).status_code == 404
        assert client.get('/sources/SRC_owned/versions/0', headers=headers).status_code == 422
        assert client.get('/sources/SRC_owned/versions/v2', headers=headers).status_code == 422


def test_forged_repository_owner_cannot_create_scope(boundary_runtime: tuple[SupabaseRuntime, list[str]]) -> None:
    repository = SupabaseSourceRepository(AuthenticatedUser(OTHER, None, {}), token_for(OWNER), boundary_runtime[0])
    with pytest.raises(HTTPException) as error:
        require_source_scope(repository, 'SRC_owned', 2)
    assert error.value.status_code == 404
    assert boundary_runtime[1] == ['/auth/v1/user']


@pytest.mark.parametrize('version', [0, -1, True, '2', 2.0, None, 2**31])
def test_relational_version_is_strict(version: object) -> None:
    with pytest.raises(ValueError):
        vector_version(version)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        SourceScope(user_id=OWNER, source_id='SRC_owned', source_version=version)


@pytest.mark.parametrize('label', ['latest', '2', 'v0', 'v02', ' v2', 'v2 ', 'V2', 'v-2'])
def test_display_version_aliases_rejected(label: str) -> None:
    with pytest.raises(ValueError):
        relational_version(label)


def test_version_mapper_roundtrip_and_scope_immutability() -> None:
    assert relational_version(vector_version(2)) == 2
    scope = SourceScope(user_id=OWNER, source_id='SRC_owned', source_version=2)
    with pytest.raises(ValidationError):
        scope.source_version = 3


def test_retrieval_cannot_omit_owner_or_broaden_version(
    monkeypatch: pytest.MonkeyPatch, supabase_storage_mode: None,
) -> None:
    from app.db import vector_store
    def forbidden() -> None:
        pytest.fail('Unsafe retrieval reached Qdrant')
    monkeypatch.setattr(vector_store, 'get_client', forbidden)
    operations = [lambda: vector_store.search_layer_a('query'),
                  lambda: vector_store.search_source_chunks('', 'SRC_owned', 'query'),
                  lambda: vector_store.search_source_chunks(str(OWNER), 'SRC_owned', 'query', source_version='v1'),
                  lambda: vector_store.retrieve_exact_chunks(source_id='SRC_owned'),
                  lambda: vector_store.retrieve_layer_b_scene(str(OWNER), 'SRC_owned')]
    for operation in operations:
        with pytest.raises(vector_store.RetrievalUnavailable):
            operation()


def test_repository_and_service_fallbacks_disabled(supabase_storage_mode: None) -> None:
    from app.services.repositories.factory import get_assessment_repository, get_learning_profile_repository
    from app.services.repositories.supabase_repository import SupabaseAssessmentRepository, SupabaseLearningProfileRepository
    from app.services.mastery.application_service import AdaptiveLearningService
    from app.services.assessment.session_store import load_session
    from app.services.assessment.profile import load_profile
    from app.services.video.engine import get_video_job
    from app.services.qa.grounded_answer import list_answer_traces
    for operation in [get_assessment_repository, get_learning_profile_repository,
                      SupabaseAssessmentRepository, SupabaseLearningProfileRepository, AdaptiveLearningService,
                      lambda: load_session('foreign-session'), lambda: load_profile(str(OTHER), 'SRC_owned'),
                      lambda: get_video_job('foreign-video'), lambda: list_answer_traces(str(OTHER), 'SRC_owned')]:
        with pytest.raises(SupabaseConfigurationError):
            operation()


def test_cached_local_service_cannot_be_reused_as_supabase_context(
    monkeypatch: pytest.MonkeyPatch, file_storage_mode: None,
) -> None:
    from app.services.mastery.application_service import AdaptiveLearningService
    service = AdaptiveLearningService()
    monkeypatch.setattr(settings, 'database_provider', 'supabase')
    with pytest.raises(SupabaseConfigurationError):
        service.get_remediation_status(str(OTHER), 'SRC_foreign', 'foreign-job')
    with pytest.raises(SupabaseConfigurationError):
        service.get_roadmap(str(OTHER), 'SRC_foreign')


def test_assessment_direct_retrieval_cannot_bypass_guard(
    monkeypatch: pytest.MonkeyPatch, supabase_storage_mode: None,
) -> None:
    from app.services.assessment import generator
    from app.services.schemas import ConceptNode
    def forbidden() -> None:
        pytest.fail('Direct assessment retrieval reached Qdrant')
    monkeypatch.setattr(generator, 'get_client', forbidden)
    concept = ConceptNode(concept_id='concept', name='Concept', source_content_ids=['CU_foreign'])
    for chunks in (None, [{'source_id': 'SRC_foreign', 'text': 'Concept', 'concept_ids': ['concept']}]):
        with pytest.raises(SupabaseConfigurationError):
            generator.search_concept_chunks(concept, 'SRC_foreign', provided_chunks=chunks)


def test_auth_outage_never_becomes_local_fallback(
    boundary_runtime: tuple[SupabaseRuntime, list[str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.security import auth
    def unavailable() -> SupabaseRuntime:
        raise SupabaseConfigurationError('secret-never-expose')
    monkeypatch.setattr(auth, 'get_supabase_runtime', unavailable)
    response = TestClient(app).get('/video/foreign-video', headers={'Authorization': 'Bearer ' + token_for(OWNER)})
    assert response.status_code == 503
    assert 'secret-never-expose' not in response.text


def test_seeded_foreign_artifacts_do_not_survive_as_access_paths(
    boundary_runtime: tuple[SupabaseRuntime, list[str]], tmp_path: Path,
) -> None:
    marker = 'foreign-private-learning-record'
    settings.assessment_dir.joinpath('foreign-session.json').write_text(json.dumps({'private': marker}))
    settings.renders_dir.joinpath('foreign-video_artifact.json').write_text(json.dumps({'private': marker}))
    headers = {'Authorization': 'Bearer ' + token_for(OWNER)}
    for client in (TestClient(app), TestClient(app)):
        for path in ('/assessment/session/foreign-session', '/video/foreign-video',
                     f'/qa/traces/{OTHER}/SRC_foreign'):
            response = client.get(path, headers=headers)
            assert response.status_code in {404, 409} and marker not in response.text


def test_canonical_database_outage_cannot_read_local_snapshot(
    boundary_runtime: tuple[SupabaseRuntime, list[str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import sources
    from app.services.security import auth
    calls: list[str] = []
    def remote(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == '/auth/v1/user':
            return httpx.Response(200, json={'id': str(OWNER)})
        if request.url.path == '/rest/v1/profiles':
            return httpx.Response(200, json=[{'id': str(OWNER), 'role': 'student',
                                             'created_at': 'now', 'updated_at': 'now'}])
        return httpx.Response(500, json={'message': 'secret-never-expose'})
    settings.registry_dir.joinpath('sources_index.json').write_text(json.dumps({'SRC_owned': {'private': 'local-data'}}))
    runtime = SupabaseRuntime(SupabaseConfig(URL, 'public-test-key'), transport=httpx.MockTransport(remote))
    monkeypatch.setattr(auth, 'get_supabase_runtime', lambda: runtime)
    monkeypatch.setattr(sources, 'get_runtime', lambda: runtime)
    try:
        response = TestClient(app).get('/sources/SRC_owned/versions/2', headers={'Authorization': 'Bearer ' + token_for(OWNER)})
        assert response.status_code == 503 and 'local-data' not in response.text
        assert 'secret-never-expose' not in response.text
        assert calls[-1] == '/rest/v1/sources'
    finally:
        runtime.close()


@pytest.mark.parametrize('provider', ['file', 'local'])
def test_explicit_local_compatibility(provider: str, monkeypatch: pytest.MonkeyPatch, file_storage_mode: None) -> None:
    from app.services.repositories.factory import get_assessment_repository
    from app.services.repositories.file_repository import FileAssessmentRepository
    monkeypatch.setattr(settings, 'database_provider', provider)
    assert isinstance(get_assessment_repository(), FileAssessmentRepository)
    response = TestClient(app).get('/qa/traces/student_default/SRC_test')
    assert response.status_code == 200 and response.json() == []


def test_openapi_and_health(supabase_storage_mode: None) -> None:
    assert '/sources/{source_id}/versions/{version}' in app.openapi()['paths']
    client = TestClient(app)
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/health').status_code == 200
