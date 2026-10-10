"""Offline proofs of the shared stage ceiling and reserved local fallback window."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from app.core.config import settings
from app.core.reasoning import ProviderFailure
from app.services.vision import VisionExtractionFailed, VisionRouteFailureTrace
from app.services.visual_router import VisualModelRouter, VisualSignals, Tier, Workload, CloudResult
from app.services.visual_contracts import VisionExtractionData
from app.services.ingestion.failures import ingestion_stage, SourceIngestionFailed
from tests.test_visual_model_router import FIXTURE, LocalDouble

class Clock:
    now: float = 0.0
    def __call__(self) -> float:
        return self.now

class Cloud:
    def __init__(self, clock: Clock, elapsed: list[float], failure: Exception) -> None:
        self.clock = clock
        self.elapsed = elapsed
        self.failure = failure
        self.deadlines: list[float] = []
    def generate(self, image_uri: str, tier: Tier, triage: bool, deadline: float, *, workload: Workload | None = None) -> CloudResult:
        self.deadlines.append(deadline)
        self.clock.now += self.elapsed.pop(0)
        raise self.failure

class Local(LocalDouble):
    def __init__(self, clock: Clock, duration: float, fail: bool = False) -> None:
        super().__init__()
        self.clock = clock
        self.duration = duration
        self.fail = fail
        self.remaining: float | None = None
    def generate(self, image: bytes, source: str, deadline: float) -> VisionExtractionData:
        self.remaining = deadline - self.clock.now
        self.clock.now += self.duration
        if self.fail:
            self.calls += 1
            raise VisionExtractionFailed("private upstream text", "VISION_TIMEOUT")
        return super().generate(image, source, deadline)

@pytest.fixture(autouse=True)
def budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vision_stage_timeout_seconds", 90.0)
    monkeypatch.setattr(settings, "vision_timeout_seconds", 45.0)
    monkeypatch.setattr(settings, "cloudflare_connect_timeout", 5.0)
    monkeypatch.setattr(settings, "vision_cloud_stage_timeout_seconds", 40.0)
    monkeypatch.setattr(settings, "vision_max_retries", 0)

def test_original_shared_deadline_exhausts_local_window() -> None:
    clock = Clock()
    clock.now = 45.1
    local = Local(clock, 45)
    local.generate(b"unused", "test", 90)
    assert local.remaining == pytest.approx(44.9)
    assert clock.now > 90

def test_explicit_cloud_budget_leaves_configured_local_window() -> None:
    clock = Clock()
    cloud = Cloud(clock, [40], ProviderFailure("TIMEOUT", True))
    local = Local(clock, 45)
    result = VisualModelRouter(cloud, local, clock=clock, local_fallback_enabled=True).extract(FIXTURE.read_bytes(), "test")
    assert result._actual_provider == "ollama"
    assert cloud.deadlines == [40]
    assert local.remaining == 50
    assert clock.now == 85

@pytest.mark.parametrize("duration", [45, 51])
def test_original_cloud_failure_survives_local_timeout(duration: float) -> None:
    clock = Clock()
    cloud = Cloud(clock, [40], ProviderFailure("TIMEOUT", True))
    local = Local(clock, duration, fail=duration == 45)
    with pytest.raises(SourceIngestionFailed) as caught:
        with ingestion_stage("EXTRACTION"):
            VisualModelRouter(cloud, local, clock=clock, local_fallback_enabled=True).extract(FIXTURE.read_bytes(), "test")
    trace = caught.value.failure.vision_route_trace
    assert trace == VisionRouteFailureTrace(cloud_failure_category="TIMEOUT", cloud_attempt_count=1, local_fallback_attempted=True, local_failure_code="VISION_TIMEOUT")
    assert "private" not in caught.value.failure.model_dump_json()

def test_exhausted_budget_does_not_start_short_local_attempt() -> None:
    clock = Clock()
    cloud = Cloud(clock, [45.1], ProviderFailure("NETWORK", True))
    local = Local(clock, 45)
    with pytest.raises(VisionExtractionFailed) as caught:
        VisualModelRouter(cloud, local, clock=clock, local_fallback_enabled=True).extract(FIXTURE.read_bytes(), "test")
    assert local.calls == 0
    assert caught.value.route_trace is not None
    assert caught.value.route_trace.cloud_failure_category == "NETWORK"
    assert not caught.value.route_trace.local_fallback_attempted

def test_two_cloud_attempts_share_cutoff_then_one_local(monkeypatch) -> None:
    monkeypatch.setattr(settings, "vision_max_retries", 1)
    clock = Clock()
    cloud = Cloud(clock, [10, 30], ProviderFailure("RATE_LIMIT", True))
    local = Local(clock, 45)
    VisualModelRouter(cloud, local, clock=clock, local_fallback_enabled=True).extract(FIXTURE.read_bytes(), "test", VisualSignals(contains_handwriting=True))
    assert cloud.deadlines == [40, 40]
    assert local.calls == 1 and clock.now == 85

@pytest.mark.parametrize("failure", [ProviderFailure("AUTH", False), ProviderFailure("CONFIG", False), ProviderFailure("INVALID_REQUEST", False)])
def test_nonoperational_failure_never_falls_back(failure: Exception) -> None:
    clock = Clock()
    local = Local(clock, 45)
    with pytest.raises(VisionExtractionFailed) as caught:
        VisualModelRouter(Cloud(clock, [1], failure), local, clock=clock, local_fallback_enabled=True).extract(FIXTURE.read_bytes(), "test")
    assert local.calls == 0
    assert caught.value.route_trace is not None
    assert caught.value.route_trace.cloud_attempt_count == 1

def test_trace_rejects_uncontrolled_diagnostics() -> None:
    with pytest.raises(ValidationError):
        VisionRouteFailureTrace(cloud_failure_category="Bearer secret", cloud_attempt_count=1, local_fallback_attempted=True)
    with pytest.raises(ValidationError):
        VisionRouteFailureTrace(cloud_attempt_count=3, local_fallback_attempted=False)
