"""Backend-only typed reasoning with bounded infrastructure failover and safe telemetry."""

from __future__ import annotations

import json
import asyncio
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock
from typing import Annotated, Literal, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr, ValidationError

from .config import settings

logger = logging.getLogger(__name__)
Task = Literal[
    "content_understanding",
    "structure_repair",
    "reasoning",
    "qa",
    "notes",
    "roadmap",
    "assessment_structured",
]
FailureCategory = Literal[
    "NETWORK",
    "TIMEOUT",
    "RATE_LIMIT",
    "QUOTA_EXHAUSTED",
    "PROVIDER_UNAVAILABLE",
    "AUTH_REJECTED",
    "REQUEST_REJECTED",
    "INVALID_RESPONSE",
    "CONFIGURATION",
    "CIRCUIT_OPEN",
]
MAX_RESPONSE_BYTES = 1_048_576
MAX_PROVIDER_CALLS_PER_PROPOSAL = 3  # Two Cloudflare transports and one local fallback.


class StrictDTO(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Message(StrictDTO):
    role: Literal["system", "user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=200000, repr=False)]


class ReasoningRequest(StrictDTO):
    task: Task
    messages: Annotated[list[Message], Field(min_length=1, max_length=4, repr=False)]
    max_tokens: Annotated[int, Field(ge=1, le=8192)]
    temperature: Annotated[float, Field(ge=0, le=1)] = 0.0
    response_schema: dict[str, JsonValue] | None = Field(default=None, repr=False)


class TokenDetails(StrictDTO):
    cached_tokens: Annotated[int, Field(ge=0)]


class Usage(StrictDTO):
    prompt_tokens: Annotated[int, Field(ge=0)]
    completion_tokens: Annotated[int, Field(ge=0)]
    total_tokens: Annotated[int, Field(ge=0)]
    prompt_tokens_details: TokenDetails | None = None
    neurons: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None


class WorkerSuccess(StrictDTO):
    ok: Literal[True]
    request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    task: Task
    model: Annotated[str, Field(pattern=r"^@[a-z]+/[A-Za-z0-9_./:-]{1,128}$")]
    response: str | dict[str, JsonValue] = Field(repr=False)
    usage: Usage | None
    latency_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]


class WorkerError(StrictDTO):
    code: Literal[
        "provider_unavailable",
        "PROVIDER_UNAVAILABLE",
        "unsupported_task",
        "invalid_request",
        "unauthorized",
        "forbidden",
    ]
    message: str | None = Field(default=None, repr=False)


class WorkerFailure(StrictDTO):
    ok: Literal[False]
    error: WorkerError
    request_id: str | None = None
    task: Task | None = None


class Telemetry(StrictDTO):
    provider: Literal["cloudflare", "ollama"]
    task: Task
    outcome: Literal["SUCCESS", "RETRYABLE_FAILURE", "REJECTED", "FAILED"]
    request_id: str | None = None
    model: str | None = None
    usage: Usage | None = None
    worker_latency_ms: float | None = None
    transport_latency_seconds: float
    reason: FailureCategory | None = None


class ReasoningResult(StrictDTO):
    response: str = Field(repr=False)
    telemetry: Telemetry


class ProviderFailure(RuntimeError):
    """Allowlisted category only: no upstream body, request, key or student text."""

    def __init__(self, category: FailureCategory, retryable: bool = False) -> None:
        self.category = category
        self.retryable = retryable
        super().__init__(category)


class ReasoningProvider(Protocol):
    def generate(self, request: ReasoningRequest) -> ReasoningResult: ...


_events: ContextVar[tuple[Telemetry, ...]] = ContextVar("reasoning_events", default=())


def reset_telemetry() -> None:
    _events.set(())


def get_telemetry() -> list[dict[str, JsonValue]]:
    return [event.model_dump(mode="json") for event in _events.get()]


def record(event: Telemetry) -> None:
    _events.set(_events.get() + (event,))


@dataclass(frozen=True)
class ProviderPolicy:
    url: str
    secret: SecretStr = field(repr=False)
    connect_timeout: float = 5.0
    read_timeout: float = 45.0
    overall_timeout: float = 60.0
    max_retries: int = 1
    circuit_threshold: int = 3
    circuit_cooldown: float = 60.0

    def __post_init__(self) -> None:
        if type(self.max_retries) is not int or not (
            0 < self.connect_timeout <= self.read_timeout <= self.overall_timeout <= 120
            and self.max_retries in (0, 1)
            and 1 <= self.circuit_threshold <= 10
            and 1 <= self.circuit_cooldown <= 600
        ):
            raise ProviderFailure("CONFIGURATION")


class CloudflareProvider:
    def __init__(
        self,
        policy: ProviderPolicy,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy, self.transport, self.clock = policy, transport, clock

    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        return self.generate_with_deadline(
            request, self.clock() + self.policy.overall_timeout
        )

    def generate_with_deadline(
        self, request: ReasoningRequest, deadline: float
    ) -> ReasoningResult:
        policy = self.policy
        started = self.clock()
        try:
            body = self.fetch_payload(
                request.model_dump(mode="json", exclude_none=True), deadline
            )
            if policy.secret.get_secret_value().encode() in body:
                raise ProviderFailure("INVALID_RESPONSE")
            try:
                data = json.loads(body)
                if isinstance(data, dict) and data.get("ok") is False:
                    failure = WorkerFailure.model_validate(data)
                    if failure.error.code.casefold() == "provider_unavailable":
                        raise ProviderFailure("PROVIDER_UNAVAILABLE", True)
                    raise ProviderFailure("REQUEST_REJECTED")
                result = WorkerSuccess.model_validate(data)
                if result.task != request.task or (
                    result.usage
                    and result.usage.total_tokens
                    != result.usage.prompt_tokens + result.usage.completion_tokens
                ):
                    raise ProviderFailure("INVALID_RESPONSE")
            except (ValueError, ValidationError):
                raise ProviderFailure("INVALID_RESPONSE") from None
            text = (
                result.response
                if isinstance(result.response, str)
                else json.dumps(result.response, separators=(",", ":"))
            )
            if not text.strip():
                raise ProviderFailure("INVALID_RESPONSE")
            return ReasoningResult(
                response=text,
                telemetry=Telemetry(
                    provider="cloudflare",
                    task=request.task,
                    outcome="SUCCESS",
                    request_id=result.request_id,
                    model=result.model,
                    usage=result.usage,
                    worker_latency_ms=result.latency_ms,
                    transport_latency_seconds=self.clock() - started,
                ),
            )
        except (httpx.TimeoutException, TimeoutError):
            raise ProviderFailure("TIMEOUT", True) from None
        except (httpx.NetworkError, httpx.RemoteProtocolError):
            raise ProviderFailure("NETWORK", True) from None

    def fetch_payload(self, payload: dict[str, JsonValue], deadline: float) -> bytes:
        """Reuse the authenticated bounded Worker transport for typed task families."""
        policy = self.policy
        parsed = urlsplit(policy.url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in ("", "/v1/generate")
            or not policy.secret.get_secret_value()
        ):
            raise ProviderFailure("CONFIGURATION")
        url = policy.url.rstrip("/")
        if not url.endswith("/v1/generate"):
            url += "/v1/generate"
        remaining = deadline - self.clock()
        if remaining <= 2 * policy.connect_timeout:
            raise ProviderFailure("TIMEOUT", True)
        timeout = httpx.Timeout(
            min(policy.read_timeout, remaining - 2 * policy.connect_timeout),
            connect=policy.connect_timeout,
            write=policy.connect_timeout,
            pool=policy.connect_timeout,
        )
        try:
            return asyncio.run(self._fetch(url, payload, timeout, remaining))
        except (httpx.TimeoutException, TimeoutError):
            raise ProviderFailure("TIMEOUT", True) from None
        except (httpx.NetworkError, httpx.RemoteProtocolError):
            raise ProviderFailure("NETWORK", True) from None

    async def _fetch(
        self,
        url: str,
        payload: dict[str, JsonValue],
        timeout: httpx.Timeout,
        remaining: float,
    ) -> bytes:
        """A real overall cancellation deadline also bounds a trickling response body."""
        async with asyncio.timeout(remaining):
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers={
                        "Authorization": "Bearer "
                        + self.policy.secret.get_secret_value(),
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status_code in (401, 403):
                        raise ProviderFailure("AUTH_REJECTED")
                    if response.status_code in (400, 429):
                        bounded = bytearray()
                        async for chunk in response.aiter_bytes():
                            bounded.extend(chunk)
                            if len(bounded) > MAX_RESPONSE_BYTES:
                                raise ProviderFailure("INVALID_RESPONSE")
                        try:
                            failure = json.loads(bounded)
                        except (ValueError, UnicodeDecodeError):
                            failure = None
                        codes: list[object] = []
                        if isinstance(failure, dict):
                            codes.append(failure.get("code"))
                            error = failure.get("error")
                            if isinstance(error, dict):
                                codes.append(error.get("code"))
                            errors = failure.get("errors")
                            if isinstance(errors, list):
                                codes.extend(item.get("code") for item in errors if isinstance(item, dict))
                        if any(str(code) in {"4006", "3036"} for code in codes):
                            raise ProviderFailure("QUOTA_EXHAUSTED")
                        raise ProviderFailure("RATE_LIMIT", True) if response.status_code == 429 else ProviderFailure("REQUEST_REJECTED")
                    if 500 <= response.status_code <= 599:
                        if (
                            payload.get("task") == "vision_extract"
                            and response.status_code == 502
                        ):
                            bounded = bytearray()
                            async for chunk in response.aiter_bytes():
                                bounded.extend(chunk)
                                if len(bounded) > MAX_RESPONSE_BYTES:
                                    raise ProviderFailure("INVALID_RESPONSE")
                            try:
                                failure = json.loads(bounded)
                            except (ValueError, UnicodeDecodeError):
                                raise ProviderFailure(
                                    "PROVIDER_UNAVAILABLE", True
                                ) from None
                            if (
                                isinstance(failure, dict)
                                and failure.get("error") == "AI_PROVIDER_TIMEOUT"
                            ):
                                raise ProviderFailure("TIMEOUT", True)
                        raise ProviderFailure("PROVIDER_UNAVAILABLE", True)
                    if response.status_code != 200:
                        raise ProviderFailure("REQUEST_REJECTED")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise ProviderFailure("INVALID_RESPONSE")
                    return bytes(body)


class OllamaReasoningProvider:
    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        from .model_manager import model_manager

        from .processing_errors import ProcessingError

        if model_manager.active_provider == "mock":
            raise ProviderFailure("CONFIGURATION")
        started = time.monotonic()
        try:
            response, model = model_manager.generate_with_fallback(
                json.dumps([m.model_dump() for m in request.messages]),
                reasoning_only=True,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                is_json=True,
                json_schema=request.response_schema,
                max_output_tokens=request.max_tokens,
                timeout=settings.ollama_timeout,
                context_tokens=32768,
            )
        except TimeoutError:
            raise ProviderFailure("TIMEOUT", True) from None
        except ProcessingError as error:
            raise ProviderFailure(
                "PROVIDER_UNAVAILABLE"
                if error.code == "MODEL_UNAVAILABLE"
                else "INVALID_RESPONSE"
            ) from None

        if model == "mock":
            raise ProviderFailure("CONFIGURATION")
        return ReasoningResult(
            response=response,
            telemetry=Telemetry(
                provider="ollama",
                task=request.task,
                outcome="SUCCESS",
                model=model,
                transport_latency_seconds=time.monotonic() - started,
            ),
        )


class CircuitBreaker:
    def __init__(
        self,
        threshold: int,
        cooldown: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.threshold, self.cooldown, self.clock = threshold, cooldown, clock
        self.consecutive_failures = 0
        self.open_until = 0.0
        self.last_failure: FailureCategory | None = None
        self.probe_inflight = False
        self.lock = Lock()

    def permit(self) -> bool:
        with self.lock:
            if self.open_until:
                if self.clock() < self.open_until or self.probe_inflight:
                    return False
                self.probe_inflight = True
            return True

    def succeeded(self) -> None:
        with self.lock:
            self.consecutive_failures, self.open_until, self.probe_inflight = (
                0,
                0.0,
                False,
            )
            self.last_failure = None

    def cancel_probe(self) -> None:
        with self.lock:
            self.probe_inflight = False

    def failed(self, reason: FailureCategory) -> None:
        with self.lock:
            self.consecutive_failures += 1
            self.last_failure, self.probe_inflight = reason, False
            if self.consecutive_failures >= self.threshold:
                self.open_until = self.clock() + self.cooldown


class ReasoningProviderRouter:
    def __init__(
        self,
        primary: ReasoningProvider,
        fallback: ReasoningProvider,
        policy: ProviderPolicy,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.primary, self.fallback, self.policy, self.clock = (
            primary,
            fallback,
            policy,
            clock,
        )
        self.circuit = CircuitBreaker(
            policy.circuit_threshold, policy.circuit_cooldown, clock
        )

    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        if not isinstance(request, ReasoningRequest):
            raise ProviderFailure("REQUEST_REJECTED")
        reason: FailureCategory = "CIRCUIT_OPEN"
        if self.circuit.permit():
            started = self.clock()
            for attempt in range(self.policy.max_retries + 1):
                logger.info(
                    "AI_PRIMARY_STARTED",
                    extra={
                        "provider": "cloudflare",
                        "task": request.task,
                        "attempt": attempt,
                    },
                )
                call_started = self.clock()
                try:
                    result = (
                        self.primary.generate_with_deadline(
                            request, started + self.policy.overall_timeout
                        )
                        if isinstance(self.primary, CloudflareProvider)
                        else self.primary.generate(request)
                    )
                    self.circuit.succeeded()
                    record(result.telemetry)
                    logger.info(
                        "AI_PRIMARY_SUCCEEDED",
                        extra=result.telemetry.model_dump(
                            mode="json", exclude_none=True
                        ),
                    )
                    return result
                except ProviderFailure as error:
                    reason = error.category
                    record(
                        Telemetry(
                            provider="cloudflare",
                            task=request.task,
                            outcome=(
                                "RETRYABLE_FAILURE" if error.retryable else "REJECTED"
                            ),
                            reason=reason,
                            transport_latency_seconds=self.clock() - call_started,
                        )
                    )
                    logger.info(
                        (
                            "AI_PRIMARY_RETRYABLE_FAILURE"
                            if error.retryable
                            else "AI_PRIMARY_REJECTED"
                        ),
                        extra={
                            "provider": "cloudflare",
                            "task": request.task,
                            "reason_code": reason,
                        },
                    )
                    if not error.retryable:
                        if error.category == "QUOTA_EXHAUSTED":
                            self.circuit.failed(reason)
                            break
                        self.circuit.succeeded()
                        raise
                    if (
                        self.clock() - started + self.policy.read_timeout
                        > self.policy.overall_timeout
                    ):
                        break
                except Exception:
                    self.circuit.cancel_probe()
                    raise
            self.circuit.failed(reason)
        logger.info(
            "AI_FALLBACK_STARTED",
            extra={"provider": "ollama", "task": request.task, "reason_code": reason},
        )
        fallback_started = self.clock()
        try:
            result = self.fallback.generate(request)
            record(result.telemetry)
            logger.info(
                "AI_FALLBACK_SUCCEEDED",
                extra=result.telemetry.model_dump(mode="json", exclude_none=True),
            )
            return result
        except ProviderFailure as error:
            record(
                Telemetry(
                    provider="ollama",
                    task=request.task,
                    outcome="FAILED",
                    reason=error.category,
                    transport_latency_seconds=self.clock() - fallback_started,
                )
            )
            logger.info(
                "AI_FALLBACK_FAILED",
                extra={
                    "provider": "ollama",
                    "task": request.task,
                    "reason_code": error.category,
                },
            )
            raise


_router: ReasoningProviderRouter | None = None
_router_lock = Lock()


def get_reasoning_router() -> ReasoningProvider:
    # Text routing is independent of visual routing. Explicit Ollama mode never
    # sends teaching or student answers to a cloud text provider.
    if settings.reasoning_provider == "ollama":
        return OllamaReasoningProvider()
    if settings.reasoning_provider not in {"cloudflare", "mock", "test"}:
        raise ProviderFailure("CONFIGURATION")
    return get_cloud_reasoning_router()


def get_cloud_reasoning_router() -> ReasoningProviderRouter:
    """Cloud transport policy, also used by the independently configured vision route."""
    global _router
    with _router_lock:
        if _router is None:
            policy = ProviderPolicy(
                settings.cloudflare_worker_url,
                settings.cloudflare_worker_secret,
                settings.cloudflare_connect_timeout,
                settings.cloudflare_read_timeout,
                settings.cloudflare_overall_timeout,
                settings.cloudflare_max_retries,
                settings.cloudflare_circuit_threshold,
                settings.cloudflare_circuit_cooldown,
            )
            _router = ReasoningProviderRouter(
                CloudflareProvider(policy), OllamaReasoningProvider(), policy
            )
        return _router
