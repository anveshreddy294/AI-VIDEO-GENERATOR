"""Self-service registration uses only public Auth and verified caller-scoped profiles."""
from __future__ import annotations
import base64,json,time
from collections.abc import Callable
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.auth import router
from app.core.supabase import SupabaseConfig,SupabaseRuntime
from app.services.security.auth import get_runtime

pytestmark=pytest.mark.usefixtures('supabase_storage_mode')
OWNER=UUID('00000000-0000-4000-8000-000000000003')
OTHER=UUID('00000000-0000-4000-8000-000000000004')
URL='https://signup.supabase.co'


def client_for(handler: Callable[[httpx.Request],httpx.Response]) -> tuple[TestClient,SupabaseRuntime]:
    runtime=SupabaseRuntime(SupabaseConfig(URL,'public-test-key','backend-secret-never-use'),transport=httpx.MockTransport(handler))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_runtime]=lambda:runtime
    return TestClient(app),runtime


@pytest.mark.parametrize('code,status',[
 ('email_address_not_authorized',400),('over_email_send_rate_limit',429),
 ('signup_disabled',400),('email_provider_disabled',400),('weak_password',400),
 ('user_already_exists',400),('email_exists',400),('unexpected_failure',500),
 ('over_request_rate_limit',429)])
def test_signup_error_category_is_preserved_without_raw_message(code: str,status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path=='/auth/v1/signup'
        assert request.headers['apikey']=='public-test-key'
        assert request.headers.get('authorization') is None
        assert 'admin' not in request.url.path
        body=json.loads(request.content)
        assert body['email']=='registration@example.test' and body['password']=='Strong-test-password1!'
        return httpx.Response(status,json={'code':code,'msg':'backend-secret-never-use password credential-token'})
    client,runtime=client_for(handler)
    try:
        response=client.post('/api/auth/signup',json={'email':'registration@example.test','password':'Strong-test-password1!'})
        assert response.status_code==(503 if status>=500 else status)
        assert response.json()['detail']['code']==code
        assert not any(value in response.text for value in ['backend-secret-never-use','credential-token','Strong-test-password1!'])
    finally:runtime.close()


def test_pending_confirmation_has_no_session_or_profile_write() -> None:
    paths: list[str]=[]
    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200,json={'id':str(OWNER),'email':'registration@example.test'})
    client,runtime=client_for(handler)
    try:
        response=client.post('/api/auth/signup',json={'email':'registration@example.test','password':'Strong-test-password1!'})
        assert response.status_code==200
        assert response.json()=={'confirmation_required':True,'session':None,'user_id':None,'profile':None}
        assert paths==['/auth/v1/signup']
    finally:runtime.close()


def test_invalid_password_rejected_before_provider_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError('Invalid password must not reach Supabase')
    client,runtime=client_for(handler)
    try:
        response=client.post('/api/auth/signup',json={'email':'registration@example.test','password':'bad'})
        assert response.status_code==422 and '"bad"' not in response.text
    finally:runtime.close()


def test_malformed_signup_success_not_confirmation_success() -> None:
    client,runtime=client_for(lambda request:httpx.Response(200,json={}))
    try:assert client.post('/api/auth/signup',json={'email':'registration@example.test','password':'Strong-test-password1!'}).status_code==502
    finally:runtime.close()


@pytest.mark.parametrize('route',['signup','login'])
def test_authenticated_signup_and_confirmed_login_provision_verified_profile(route: str) -> None:
    claims={'sub':str(OWNER),'iss':URL+'/auth/v1','aud':'authenticated','role':'authenticated','exp':int(time.time())+300}
    token='header.'+base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')+'.test-signature'
    profile={'id':str(OWNER),'role':'student','created_at':'2026-10-07T00:00:00Z','updated_at':'2026-10-07T00:00:00Z'}
    inserted=False;paths: list[str]=[]
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal inserted
        assert request.headers['apikey']=='public-test-key'
        paths.append(request.url.path)
        if request.url.path in {'/auth/v1/signup','/auth/v1/token'}:
            return httpx.Response(200,json={'access_token':token,'refresh_token':'test-refresh','token_type':'bearer','expires_in':3600})
        assert request.headers['authorization']=='Bearer '+token
        if request.url.path=='/auth/v1/user':return httpx.Response(200,json={'id':str(OWNER)})
        assert request.url.path=='/rest/v1/profiles'
        if request.method=='POST':
            assert json.loads(request.content)=={'id':str(OWNER)}
            inserted=True;return httpx.Response(201)
        assert request.url.params['id']=='eq.'+str(OWNER)
        return httpx.Response(200,json=[profile] if inserted else [])
    client,runtime=client_for(handler)
    try:
        response=client.post('/api/auth/'+route,json={'email':'registration@example.test','password':'Strong-test-password1!'})
        assert response.status_code==200 and response.json()['user_id']==str(OWNER)
        assert not response.json()['confirmation_required'] and inserted
        assert paths.index('/auth/v1/user')<paths.index('/rest/v1/profiles')
    finally:runtime.close()


def test_login_pending_confirmation_reports_provider_category() -> None:
    client,runtime=client_for(lambda request:httpx.Response(400,json={'code':'email_not_confirmed','msg':'secret'}))
    try:
        response=client.post('/api/auth/login',json={'email':'registration@example.test','password':'Strong-test-password1!'})
        assert response.status_code==401 and response.json()['detail']['code']=='email_not_confirmed'
    finally:runtime.close()


def test_untrusted_error_code_cannot_leak_response_secrets() -> None:
    client,runtime=client_for(lambda request:httpx.Response(400,json={'code':'<secret token>','msg':'password-secret'}))
    try:
        response=client.post('/api/auth/signup',json={'email':'registration@example.test','password':'Strong-test-password1!'})
        assert response.json()['detail']['code']=='auth_request_failed'
        assert 'secret' not in response.text
    finally:runtime.close()


def test_signup_uses_configured_confirmation_redirect_only() -> None:
    observed: list[str]=[]
    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(str(request.url.params.get('redirect_to')))
        return httpx.Response(200,json={'id':str(OWNER)})
    runtime=SupabaseRuntime(SupabaseConfig(URL,'public-test-key',confirmation_redirect_url='http://127.0.0.1:8000/login'),transport=httpx.MockTransport(handler))
    try:
        runtime.signup('registration@example.test','Strong-test-password1!')
        assert observed==['http://127.0.0.1:8000/login']
    finally:runtime.close()


@pytest.mark.parametrize('redirect',['http://outside.example/login','https://user:secret@example.test/login','https://example.test/login?next=https://outside.example','https://example.test/dashboard'])
def test_unsafe_confirmation_redirect_configuration_rejected(redirect: str) -> None:
    from app.core.supabase import SupabaseConfigurationError
    with pytest.raises(SupabaseConfigurationError):
        SupabaseConfig(URL,'public-test-key',confirmation_redirect_url=redirect).validate()


def test_profile_owner_mismatch_blocks_session_success() -> None:
    claims={'sub':str(OWNER),'iss':URL+'/auth/v1','aud':'authenticated','role':'authenticated','exp':int(time.time())+300}
    token='header.'+base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')+'.test-signature'
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path=='/auth/v1/signup':return httpx.Response(200,json={'access_token':token,'refresh_token':'test-refresh','token_type':'bearer','expires_in':3600})
        if request.url.path=='/auth/v1/user':return httpx.Response(200,json={'id':str(OWNER)})
        return httpx.Response(200,json=[{'id':str(OTHER),'role':'student','created_at':'2026-10-07T00:00:00Z','updated_at':'2026-10-07T00:00:00Z'}])
    client,runtime=client_for(handler)
    try:assert client.post('/api/auth/signup',json={'email':'registration@example.test','password':'Strong-test-password1!'}).status_code==502
    finally:runtime.close()
