"""Deterministic Worker transport, retry budgets, circuit and secret boundary tests."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.reasoning import (
    CloudflareProvider,
    ProviderPolicy,
    ProviderFailure,
    ReasoningRequest,
    Message,
    ReasoningResult,
    ReasoningProviderRouter,
    Telemetry,
    reset_telemetry,
    get_telemetry,
)

POLICY = ProviderPolicy(
    "https://worker.example/v1/generate", SecretStr("worker-test-secret")
)
REQUEST = ReasoningRequest(
    task="content_understanding",
    messages=[Message(role="user", content="Untrusted controlled text")],
    max_tokens=100,
)


def envelope() -> dict[str, object]:
    return {
        "ok": True,
        "request_id": "test-request",
        "task": "content_understanding",
        "model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "response": {"ready": True},
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "prompt_tokens_details": {"cached_tokens": 0},
            "neurons": 2.5,
        },
        "latency_ms": 100,
    }


class Fallback:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        self.calls += 1
        return ReasoningResult(
            response="{}",
            telemetry=Telemetry(
                provider="ollama",
                task=request.task,
                outcome="SUCCESS",
                model="local-model",
                transport_latency_seconds=0.1,
            ),
        )


def router(
    handler: Callable[[httpx.Request], httpx.Response], policy: ProviderPolicy = POLICY
) -> tuple[ReasoningProviderRouter, Fallback]:
    fallback = Fallback()
    return (
        ReasoningProviderRouter(
            CloudflareProvider(policy, httpx.MockTransport(handler)), fallback, policy
        ),
        fallback,
    )


def test_worker_request_schema_and_primary_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer worker-test-secret"
        body = json.loads(request.content)
        assert set(body) == {
            "task",
            "messages",
            "max_tokens",
            "temperature",
            "response_schema",
        }
        assert "model" not in body
        assert body["response_schema"] == {"type": "object"}
        return httpx.Response(200, json=envelope())

    route, fallback = router(handler)
    result = route.generate(
        REQUEST.model_copy(update={"response_schema": {"type": "object"}})
    )
    assert json.loads(result.response) == {"ready": True} and fallback.calls == 0
    assert result.telemetry.usage and result.telemetry.usage.neurons == 2.5


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_retryable_http_has_one_retry_then_one_fallback(status: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    route, fallback = router(handler)
    route.generate(REQUEST)
    assert calls == 2 and fallback.calls == 1


@pytest.mark.parametrize(
    "error", [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout]
)
def test_retryable_transport_failure(error: type[httpx.RequestError]) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise error("upstream must not be logged", request=request)

    route, fallback = router(handler)
    route.generate(REQUEST)
    assert calls == 2 and fallback.calls == 1


@pytest.mark.parametrize("status", [401, 403, 400, 404, 422, 302])
def test_security_and_request_rejection_never_fall_back(
    status: int, caplog: pytest.LogCaptureFixture
) -> None:
    route, fallback = router(
        lambda _: httpx.Response(
            status, text="worker-test-secret untrusted upstream body"
        )
    )
    with caplog.at_level("INFO"), pytest.raises(ProviderFailure):
        route.generate(REQUEST)
    assert fallback.calls == 0 and route.circuit.consecutive_failures == 0
    assert (
        "worker-test-secret" not in caplog.text
        and "untrusted upstream body" not in caplog.text
    )


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "wrong_task", "wrong_usage", "secret", "empty", "invalid_json"],
)
def test_invalid_worker_response_never_falls_back(mutation: str) -> None:
    body = envelope()
    if mutation == "unknown":
        body["unexpected"] = "value"
    if mutation == "wrong_task":
        body["task"] = "qa"
    if mutation == "wrong_usage":
        body["usage"] = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 9}
    if mutation == "secret":
        body["response"] = "worker-test-secret"
    if mutation == "empty":
        body["response"] = " "
    route, fallback = router(
        lambda _: (
            httpx.Response(200, json=body)
            if mutation != "invalid_json"
            else httpx.Response(200, text="not JSON")
        )
    )
    with pytest.raises(ProviderFailure, match="INVALID_RESPONSE"):
        route.generate(REQUEST)
    assert fallback.calls == 0


@pytest.mark.parametrize(
    "code", ["provider_unavailable", "unsupported_task", "unauthorized"]
)
def test_typed_worker_level_failure(code: str) -> None:
    route, fallback = router(
        lambda _: httpx.Response(
            200,
            json={
                "ok": False,
                "error": {"code": code, "message": "private upstream data"},
            },
        )
    )
    if code == "provider_unavailable":
        route.generate(REQUEST)
        assert fallback.calls == 1
    else:
        with pytest.raises(ProviderFailure):
            route.generate(REQUEST)
        assert fallback.calls == 0


def test_invalid_task_and_model_override_rejected_before_transport() -> None:
    with pytest.raises(ValidationError):
        ReasoningRequest(task="unsupported", messages=REQUEST.messages, max_tokens=100)
    with pytest.raises(ValidationError):
        ReasoningRequest.model_validate(
            {
                "task": "content_understanding",
                "messages": [{"role": "user", "content": "text"}],
                "max_tokens": 100,
                "model": "browser-selected",
            }
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://worker.example",
        "https://user:password@worker.example/v1/generate",
        "https://worker.example/v1/generate?key=value",
        "https://worker.example/wrong",
    ],
)
def test_invalid_configuration_never_falls_back(url: str) -> None:
    policy = ProviderPolicy(url, SecretStr("worker-test-secret"))
    route, fallback = router(lambda _: pytest.fail("Invalid endpoint called"), policy)
    with pytest.raises(ProviderFailure, match="CONFIGURATION"):
        route.generate(REQUEST)
    assert fallback.calls == 0


def test_bounded_circuit_opens_cools_down_and_recovers() -> None:
    clock = [0.0]
    attempts = 0
    success = False

    class Primary:
        def generate(self, request: ReasoningRequest) -> ReasoningResult:
            nonlocal attempts
            attempts += 1
            if not success:
                raise ProviderFailure("PROVIDER_UNAVAILABLE", True)
            return ReasoningResult(
                response="{}",
                telemetry=Telemetry(
                    provider="cloudflare",
                    task=request.task,
                    outcome="SUCCESS",
                    transport_latency_seconds=0.1,
                ),
            )

    fallback = Fallback()
    route = ReasoningProviderRouter(Primary(), fallback, POLICY, lambda: clock[0])
    for _ in range(3):
        route.generate(REQUEST)
    assert (
        attempts == 6
        and route.circuit.consecutive_failures == 3
        and route.circuit.open_until == 60
    )
    route.generate(REQUEST)
    assert attempts == 6 and fallback.calls == 4
    clock[0] = 60
    success = True
    route.generate(REQUEST)
    assert (
        attempts == 7
        and route.circuit.open_until == 0
        and route.circuit.consecutive_failures == 0
    )


def test_overall_budget_prevents_second_transport_after_long_failure() -> None:
    clock = [0.0]
    attempts = 0

    class SlowPrimary:
        def generate(self, request: ReasoningRequest) -> ReasoningResult:
            nonlocal attempts
            attempts += 1
            clock[0] += 30
            raise ProviderFailure("TIMEOUT", True)

    fallback = Fallback()
    route = ReasoningProviderRouter(SlowPrimary(), fallback, POLICY, lambda: clock[0])
    route.generate(REQUEST)
    assert attempts == 1 and fallback.calls == 1


def test_programming_errors_do_not_trigger_fallback() -> None:
    route, fallback = router(
        lambda _: (_ for _ in ()).throw(RuntimeError("application defect"))
    )
    with pytest.raises(RuntimeError):
        route.generate(REQUEST)
    assert fallback.calls == 0


def test_telemetry_has_no_prompts_credentials_or_outputs() -> None:
    reset_telemetry()
    route, _ = router(lambda _: httpx.Response(200, json=envelope()))
    route.generate(REQUEST)
    payload = json.dumps(get_telemetry())
    assert (
        "worker-test-secret" not in payload
        and "Untrusted controlled text" not in payload
        and "response" not in payload
    )
    assert "worker-test-secret" not in repr(
        POLICY
    ) and "Untrusted controlled text" not in repr(REQUEST)


def test_overall_deadline_cancels_trickling_response() -> None:
    import asyncio
    import time

    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(20):
                await asyncio.sleep(0.005)
                yield b" "

    policy = ProviderPolicy(
        "https://worker.example/v1/generate",
        SecretStr("worker-test-secret"),
        connect_timeout=0.001,
        read_timeout=0.05,
        overall_timeout=0.1,
    )
    provider = CloudflareProvider(
        policy, httpx.MockTransport(lambda _: httpx.Response(200, stream=Trickle()))
    )
    started = time.monotonic()
    with pytest.raises(ProviderFailure, match="TIMEOUT"):
        provider.generate_with_deadline(REQUEST, started + 0.02)
    assert time.monotonic() - started < 0.1


def test_local_reasoning_preserves_native_message_roles_and_schema(monkeypatch):
    from app.core.model_manager import ModelManager
    import urllib.request
    manager = ModelManager()
    manager.active_provider = "ollama"
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({"done": True, "message": {"role": "assistant", "content": '{"ok":true}'}}).encode()
    def transport(request, timeout):
        captured.append((request.full_url, json.loads(request.data)))
        return Response()
    monkeypatch.setattr(urllib.request, "urlopen", transport)
    messages = [{"role":"system","content":"Exact source quotes only"},{"role":"user","content":"Untrusted evidence"}]
    text, model = manager.generate_with_fallback("legacy prompt", reasoning_only=True, messages=messages,
        json_schema={"type":"object"}, max_output_tokens=512, context_tokens=32768)
    assert text == '{"ok":true}' and model == "llama3.2:3b"
    url, body = captured[0]
    assert url.endswith("/api/chat") and "prompt" not in body
    assert body["messages"] == messages and body["format"] == {"type":"object"}
    assert body["options"]["num_ctx"] == 32768


@pytest.mark.parametrize("status,code", [(429,3036),(429,4006),(400,4006)])
def test_daily_quota_terminates_primary_retries_and_executes_fallback(status: int, code: int) -> None:
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"errors":[{"code":code,"message":"private provider text"}]})
    route, fallback = router(handler)
    res = route.generate(REQUEST)
    assert calls == 1
    assert fallback.calls == 1
    assert res.telemetry.provider == "ollama"


def test_daily_quota_fails_cleanly_if_fallback_fails() -> None:
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"errors":[{"code":4006,"message":"private provider text"}]})
    route, fallback = router(handler)
    def failing_fallback(req: ReasoningRequest) -> ReasoningResult:
        raise ProviderFailure("PROVIDER_UNAVAILABLE")
    fallback.generate = failing_fallback
    with pytest.raises(ProviderFailure) as caught:
        route.generate(REQUEST)
    assert caught.value.category == "PROVIDER_UNAVAILABLE"
    assert calls == 1

