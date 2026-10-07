"""OpenAPI, browser contract and existing source boundary regression coverage."""
from __future__ import annotations
import inspect
from pathlib import Path
import shutil
import subprocess
from typing import get_type_hints

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


pytestmark = pytest.mark.usefixtures("supabase_storage_mode")


def test_openapi_schema_builds_and_contains_core_routes() -> None:
    app.openapi_schema = None
    schema = app.openapi()
    for path in ['/api/auth/login','/api/auth/signup','/api/auth/me','/sources','/upload',
                 '/pipeline/upload-and-assess','/api/learning/{source_id}/reassessment/generate','/video/generate']:
        assert path in schema['paths']
    assert schema['paths']['/video/generate']['post']['requestBody']['required'] is True
    assert schema['paths']['/api/learning/{source_id}/reassessment/generate']['post']['requestBody'].get('required',False) is False
    assert schema['paths']['/assessment/start']['post']['requestBody'].get('required',False) is False


def test_all_body_route_annotations_resolve() -> None:
    from app.api import learning, assessment, video
    for module in [learning,assessment,video]:
        for _, function in inspect.getmembers(module,inspect.isfunction):
            if function.__module__ == module.__name__:
                get_type_hints(function, include_extras=True)


def test_openapi_json_and_swagger_docs_succeed() -> None:
    client=TestClient(app)
    assert client.get('/openapi.json').status_code==200
    assert client.get('/docs').status_code==200


def test_supabase_dashboard_has_truthful_source_only_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings,'database_provider','supabase')
    content=TestClient(app).get('/dashboard?user_id=student_attacker').text
    assert 'data-source-provider="supabase"' in content
    assert 'Analyze Learning Material' in content
    assert 'value="student_1"' not in content
    assert 'for="studentId">Student Identifier' not in content
    assert 'My sources' in content and 'Explore your topics' in content
    assert 'Focused learning' in content
    assert 'id="notes-tab"' in content and 'aria-controls="notes-panel"' in content
    assert 'Generate Notes' in content and '/assets/notes.js' in content
    assert '/assets/learning.js' in content and '/assets/auth.js' in content
    script=TestClient(app).get('/assets/learning.js').text
    assert "Reflect.get(window, 'VisualAIAuth')" in script and 'auth.protectedFetch' in script
    assert "api('/pipeline/upload-and-assess',{method:'POST',body})" in script


def test_file_dashboard_retains_existing_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings,'database_provider','file')
    content=TestClient(app).get('/dashboard').text
    assert 'data-source-provider="file"' in content
    assert 'value="student_1"' in content
    assert 'Ingest Material &amp; Start Diagnostic Assessment' in content


def test_auth_pages_use_email_real_apis_and_no_demo_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings,'supabase_secret_key','backend-secret-must-not-render')
    monkeypatch.setattr(settings,'supabase_service_role_key','legacy-secret-must-not-render')
    client=TestClient(app)
    signup=client.get('/signup').text
    login=client.get('/login').text
    dashboard=client.get('/dashboard').text
    script=client.get('/assets/auth.js')
    assert script.status_code==200
    assert 'id="signupEmail"' in signup and 'id="loginEmail"' in login
    assert 'window.VisualAIAuth.signup' in signup and 'window.VisualAIAuth.login' in login
    assert 'quickDemoLogin' not in login
    assert 'password123' not in login and 'student123' not in signup
    assert '/api/auth/login' in script.text and '/api/auth/signup' in script.text
    for secret in ['backend-secret-must-not-render','legacy-secret-must-not-render','VISUALAI_AUTH_TEST_PASSWORD']:
        assert secret not in signup+login+dashboard+script.text


def test_browser_session_contracts_in_node() -> None:
    node=shutil.which('node')
    if node is None:
        pytest.skip('Node is required to execute browser session contract tests')
    root=Path(__file__).resolve().parent.parent
    result=subprocess.run([node,'--test',str(root/'tests/test_frontend_auth.js')],cwd=root,
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
