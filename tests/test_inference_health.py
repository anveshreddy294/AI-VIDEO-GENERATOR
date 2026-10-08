"""Health is credential-safe and makes only a bounded unauthenticated GET."""
from __future__ import annotations
import httpx
import pytest
from pydantic import SecretStr
from app.core.config import settings
from app.core import inference_health as health

@pytest.mark.parametrize("status,expected",[(200,True),(401,False),(503,False)])
def test_health_no_inference_and_no_secret(monkeypatch: pytest.MonkeyPatch,status: int,expected: bool) -> None:
    calls: list[httpx.Request]=[]
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status,json={"status":"ok","service":"visualai-cloudflare-inference"})
    original=httpx.Client
    monkeypatch.setattr(settings,"cloudflare_worker_url","https://worker.test/v1/generate")
    monkeypatch.setattr(settings,"cloudflare_worker_secret",SecretStr("private-test-secret"))
    monkeypatch.setattr(health.httpx,"Client",lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    result=health.inference_health()
    assert result.worker_reachable is expected and result.configured
    assert len(calls)==1 and calls[0].method=="GET" and calls[0].url.path=="/health"
    assert "authorization" not in calls[0].headers
    assert "private-test-secret" not in result.model_dump_json() and "worker.test" not in result.model_dump_json()

def test_unconfigured_does_not_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings,"cloudflare_worker_secret",SecretStr(""))
    monkeypatch.setattr(health.httpx,"Client",lambda **kwargs:pytest.fail("Unexpected network"))
    assert not health.inference_health().configured


@pytest.mark.parametrize("body",[b'not-json',b'x'*5000,b'{"status":"ok","service":"unrelated"}'])
def test_health_rejects_untrusted_or_oversized_body(monkeypatch: pytest.MonkeyPatch,body: bytes) -> None:
    original=httpx.Client
    monkeypatch.setattr(settings,"cloudflare_worker_url","https://worker.test/v1/generate")
    monkeypatch.setattr(settings,"cloudflare_worker_secret",SecretStr("test-only"))
    monkeypatch.setattr(health.httpx,"Client",lambda **kwargs:original(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=body)),**kwargs))
    assert not health.inference_health().worker_reachable
