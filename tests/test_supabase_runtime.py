"""Offline Auth boundary checks use HTTP transport doubles, never Supabase."""
from __future__ import annotations

import base64
import json
from collections.abc import Callable
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router
from app.core.supabase import (
    SupabaseAuthenticationError, SupabaseConfig, SupabaseConfigurationError,
    SupabaseResponseError, SupabaseRuntime, SupabaseUnavailable,
)
from app.services.security import auth

OWNER = UUID('00000000-0000-0000-0000-000000000001')
OTHER = UUID('00000000-0000-0000-0000-000000000002')
PROJECT_URL = 'https://unit-test.supabase.co'
NOW = 2_000_000_000
PROFILE: dict[str, str | None] = {
    'id': str(OWNER), 'full_name': None, 'role': 'student',
    'created_at': '2030-01-01T00:00:00Z', 'updated_at': '2030-01-01T00:00:00Z',
}


def access_token(**overrides: object) -> str:
    """Synthetic token: mock GoTrue acceptance is the test signature boundary."""
    claims: dict[str, object] = {'sub': str(OWNER), 'iss': PROJECT_URL + '/auth/v1',
                                 'aud': 'authenticated', 'exp': NOW + 60, 'role': 'authenticated'}
    claims.update(overrides)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return f'header.{payload}.mock-signature'


def runtime(handler: Callable[[httpx.Request], httpx.Response], *, admin_key: str = '') -> SupabaseRuntime:
    return SupabaseRuntime(SupabaseConfig(PROJECT_URL, 'sb_publishable_test', admin_key),
                           transport=httpx.MockTransport(handler), clock=lambda: NOW)


def verified_user_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={'id': str(OWNER), 'email': 'owner@example.test'})


@pytest.mark.parametrize('url,key', [('', ''), (PROJECT_URL, ''), ('http://remote.example', 'public'),
                                   ('https://name:password@example.test', 'public'),
                                   ('https://[invalid', 'public'),
                                   (PROJECT_URL, 'sb_secret_must_not_be_public')])
def test_missing_or_invalid_configuration(url: str, key: str) -> None:
    with pytest.raises(SupabaseConfigurationError):
        SupabaseConfig(url, key).validate()


def test_valid_configuration_and_secret_repr() -> None:
    config = SupabaseConfig(PROJECT_URL, 'public-test-key', 'backend-test-secret')
    config.validate()
    assert 'public-test-key' not in repr(config)
    assert 'backend-test-secret' not in repr(config)


def test_invalid_signature_rejected_by_auth_server_before_claim_parsing() -> None:
    rt = runtime(lambda request: httpx.Response(401, json={'message': 'bad signature'}))
    with pytest.raises(SupabaseAuthenticationError):
        rt.verify_user(access_token())
    rt.close()


@pytest.mark.parametrize('claims', [
    {'exp': NOW - 1}, {'iss': 'https://another-project.supabase.co/auth/v1'},
    {'aud': 'admin'}, {'sub': 'student_1'}, {'sub': str(OTHER)}, {'nbf': NOW + 60},
    {'role': 'service_role'}, {'exp': True},
])
def test_expiration_issuer_audience_and_uuid_rejection(claims: dict[str, object]) -> None:
    rt = runtime(verified_user_response)
    with pytest.raises(SupabaseAuthenticationError):
        rt.verify_user(access_token(**claims))
    rt.close()


def test_verified_uuid_and_server_email() -> None:
    rt = runtime(verified_user_response)
    user = rt.verify_user(access_token())
    assert user.user_id == OWNER
    assert isinstance(user.user_id, UUID)
    assert user.email == 'owner@example.test'
    rt.close()


def test_profile_provisioning_idempotency_and_public_scoped_headers() -> None:
    exists = False
    inserts = 0
    token = access_token()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal exists, inserts
        assert request.headers['apikey'] == 'sb_publishable_test'
        assert request.headers['authorization'] == f'Bearer {token}'
        if request.url.path == '/auth/v1/user':
            return verified_user_response(request)
        if request.method == 'POST':
            assert json.loads(request.content) == {'id': str(OWNER)}
            assert request.url.params['on_conflict'] == 'id'
            assert 'resolution=ignore-duplicates' in request.headers['prefer']
            exists = True
            inserts += 1
            return httpx.Response(201)
        assert request.url.params['id'] == f'eq.{OWNER}'
        return httpx.Response(200, json=[PROFILE] if exists else [])

    rt = runtime(handler, admin_key='backend-must-not-be-used')
    user = rt.verify_user(token)
    assert rt.ensure_profile(user, token).id == OWNER
    assert rt.ensure_profile(user, token).id == OWNER
    assert inserts == 1
    rt.close()


def test_wrong_profile_owner_is_rejected() -> None:
    rt = runtime(lambda request: verified_user_response(request) if request.url.path == '/auth/v1/user'
                 else httpx.Response(200, json=[{**PROFILE, 'id': str(OTHER)}]))
    with pytest.raises(SupabaseResponseError):
        rt.ensure_profile(rt.verify_user(access_token()), access_token())
    rt.close()


def test_student_id_cannot_override_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    rt = runtime(lambda request: verified_user_response(request) if request.url.path == '/auth/v1/user'
                 else httpx.Response(200, json=[PROFILE]))
    monkeypatch.setattr(auth, 'get_supabase_runtime', lambda: rt)
    assert auth.extract_authenticated_user_id('Bearer ' + access_token(), 'student_attacker') == str(OWNER)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth.get_runtime] = lambda: rt
    with TestClient(app) as client:
        response = client.get('/api/auth/me?student_id=student_attacker&user_id=student_attacker',
                              headers={'Authorization': 'Bearer ' + access_token()})
        assert response.status_code == 200
        assert response.json()['user_id'] == str(OWNER)
        assert client.get('/api/auth/me?student_id=' + str(OWNER)).status_code == 401
    rt.close()


def test_secret_free_health_and_explicit_connection_failure() -> None:
    def disconnected(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('backend-secret-value', request=request)
    rt = runtime(disconnected, admin_key='backend-secret-value')
    assert rt.health() == {'configured': True, 'reachable': False, 'status': 'unreachable'}
    assert 'backend-secret-value' not in json.dumps(rt.health())
    with pytest.raises(SupabaseUnavailable) as error:
        rt.verify_user(access_token())
    assert 'backend-secret-value' not in str(error.value)
    rt.close()


def test_reachable_health() -> None:
    rt = runtime(lambda request: httpx.Response(200, json={'version': 'test'}))
    assert rt.health() == {'configured': True, 'reachable': True, 'status': 'connected'}
    rt.close()


def test_user_tokens_do_not_stick_on_shared_client() -> None:
    observed: list[str | None] = []
    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.headers.get('authorization'))
        return httpx.Response(200, json=[])
    rt = runtime(handler)
    rt.user_request('GET', '/rest/v1/profiles', token='first')
    rt.user_request('GET', '/rest/v1/profiles', token='second')
    rt.health()
    assert observed == ['Bearer first', 'Bearer second', None]
    rt.close()


def test_backend_requires_backend_key() -> None:
    rt = runtime(verified_user_response)
    with pytest.raises(SupabaseConfigurationError):
        rt.admin_request('GET', '/rest/v1/profiles')
    rt.close()


def test_signup_confirmation_and_generic_login_failure() -> None:
    rt = runtime(lambda request: httpx.Response(200, json={'id': str(OWNER)}) if request.url.path.endswith('/signup')
                 else httpx.Response(400, json={'message': 'credential-do-not-expose'}))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth.get_runtime] = lambda: rt
    with TestClient(app) as client:
        response = client.post('/api/auth/signup', json={'email':'owner@example.test','password':'secure-password'})
        assert response.status_code == 200
        assert response.json()['confirmation_required'] is True
        assert response.json()['session'] is None
        response = client.post('/api/auth/login', json={'email':'owner@example.test','password':'secure-password'})
        assert response.status_code == 401
        assert 'credential-do-not-expose' not in response.text
    rt.close()


def test_configuration_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    monkeypatch.setattr(settings, 'supabase_url', PROJECT_URL)
    monkeypatch.setattr(settings, 'supabase_publishable_key', '')
    monkeypatch.setattr(settings, 'supabase_secret_key', '')
    monkeypatch.setattr(settings, 'supabase_anon_key', 'legacy-public')
    monkeypatch.setattr(settings, 'supabase_service_role_key', 'legacy-backend')
    config = SupabaseConfig.from_settings(settings)
    assert config.public_key == 'legacy-public'
    assert config.admin_key == 'legacy-backend'
    monkeypatch.setattr(settings, 'supabase_publishable_key', 'modern-public')
    monkeypatch.setattr(settings, 'supabase_secret_key', 'modern-backend')
    config = SupabaseConfig.from_settings(settings)
    assert config.public_key == 'modern-public'
    assert config.admin_key == 'modern-backend'


def test_health_endpoint_missing_configuration_and_no_secret_response(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main
    def unconfigured() -> SupabaseRuntime:
        raise SupabaseConfigurationError('backend-do-not-expose')
    monkeypatch.setattr(main, 'get_supabase_runtime', unconfigured)
    with TestClient(main.app) as client:
        response = client.get('/health/supabase')
        assert response.status_code == 503
        assert response.json() == {'supabase': {'configured': False, 'reachable': False, 'status': 'not_configured'}}
        assert 'backend-do-not-expose' not in response.text


def test_login_session_verified_and_cache_disabled() -> None:
    token = access_token()
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/auth/v1/token':
            return httpx.Response(200, json={'access_token': token, 'refresh_token': 'refresh-test',
                                           'token_type': 'bearer', 'expires_in': 60})
        if request.url.path == '/auth/v1/user':
            return verified_user_response(request)
        return httpx.Response(200, json=[PROFILE])
    rt = runtime(handler)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth.get_runtime] = lambda: rt
    with TestClient(app) as client:
        response = client.post('/api/auth/login', json={'email': 'owner@example.test', 'password': 'secure-password'})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        assert response.json()['user_id'] == str(OWNER)
        response = client.post('/api/auth/refresh', json={'refresh_token': 'refresh-test'})
        assert response.status_code == 200
        assert response.json()['user_id'] == str(OWNER)
    rt.close()


def test_validation_errors_never_echo_credentials() -> None:
    rt = runtime(verified_user_response)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth.get_runtime] = lambda: rt
    with TestClient(app) as client:
        response = client.post('/api/auth/login', json={'email': 'invalid', 'password': 'SECRET', 'extra': 'SHOULD_NOT_APPEAR'})
        assert response.status_code == 422
        assert 'SECRET' not in response.text
        assert 'SHOULD_NOT_APPEAR' not in response.text
        assert all('input' not in issue for issue in response.json()['detail'])
    rt.close()
