"""OpenAPI, browser contract and existing source boundary regression coverage."""
from __future__ import annotations
import inspect
import re
from html.parser import HTMLParser
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
    assert "api('/pipeline/upload-and-assess',{method:'POST',body})" in re.sub(r"\s+", "", script)


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


def test_notes_asset_serves_existing_script_without_credentials() -> None:
    response = TestClient(app).get("/assets/notes.js")
    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] == "application/javascript"
    expected = Path(__file__).resolve().parent.parent / "app/static/notes.js"
    assert response.content == expected.read_bytes()
    assert "VisualAINotes" in response.text


def test_learner_shell_local_asset_dependencies_resolve() -> None:
    class AssetDependencies(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.paths: set[str] = set()

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            for name, value in attrs:
                if name in {"src", "href"} and value and value.startswith("/assets/"):
                    self.paths.add(value)

    client = TestClient(app)
    page = client.get("/learn")
    assert page.status_code == 200
    dependencies = AssetDependencies()
    dependencies.feed(page.text)
    assert {"/assets/auth.js", "/assets/notes.js", "/assets/learning.js", "/assets/learning.css"} <= dependencies.paths
    for path in sorted(dependencies.paths):
        assert client.get(path).status_code == 200, path


@pytest.mark.parametrize("path", ["/assets/learning.js", "/assets/learning.css", "/assets/notes.js"])
def test_learner_assets_require_cache_revalidation(path: str) -> None:
    response = TestClient(app).get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_learner_upload_guidance_matches_authoritative_backend_extensions() -> None:
    from html.parser import HTMLParser
    from app.services.visual_evidence import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS
    class Picker(HTMLParser):
        accept: str = ""
        def handle_starttag(self, tag: str, attrs: list[tuple[str,str|None]]) -> None:
            values=dict(attrs)
            if tag=="input" and values.get("id")=="upload-file":
                self.accept=values.get("accept") or ""
                assert values.get("aria-describedby")=="upload-help"
    page=TestClient(app).get("/learn").text
    picker=Picker();picker.feed(page)
    assert {v.removeprefix(".") for v in picker.accept.split(",")}==settings.allowed_extensions
    assert picker.accept==".pdf,.txt,.png,.jpg,.jpeg,.webp,.mp4,.mov,.mkv"
    assert "PDF, TXT, PNG, JPG, JPEG, WEBP, MP4, MOV, MKV" in page
    assert "original PDF instead of one long phone screenshot" in page
    assert "production processing is not qualified" in page
    assert MAX_IMAGE_BYTES==8*1024*1024 and MAX_IMAGE_PIXELS==16_000_000
    assert "max 8 MB, max 16 megapixels" in page


def test_long_upload_guidance_is_collapsed_while_limits_remain_visible() -> None:
    page=TestClient(app).get("/learn").text
    assert '<details class="upload-guidance"><summary>Best results and video support</summary>' in page
    assert '<details class="upload-guidance" open' not in page
    before=page.split('<details class="upload-guidance">')[0]
    assert "PDF, TXT, PNG, JPG, JPEG, WEBP, MP4, MOV, MKV" in before
    assert "max 8 MB, max 16 megapixels" in before
    assert "Video processing: experimental" in before
