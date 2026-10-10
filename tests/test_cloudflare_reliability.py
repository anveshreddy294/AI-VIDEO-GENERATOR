"""Production routing, budgets, independent fallback review, cache and durable state."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
import time

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.reasoning import CloudflareProvider, ProviderPolicy, ProviderFailure, ReasoningProviderRouter
from app.services.visual_router import VisualModelRouter, VisualScope, visual_scope, MODELS, CloudflareVisionProvider
from app.services.independent_visual_verifier import CloudflareIndependentVisualVerifier
from app.services.pipeline_tracker import DurableJobStore, PipelineJob
from app.services.ingestion.failures import SourceFailure
from tests.test_reasoning_provider import REQUEST, Fallback, envelope
from tests.test_visual_model_router import FIXTURE, DATA, CloudDouble, LocalDouble
from tests.test_cloud_visual_review import CLAIM, extraction


def test_cloud_has_full_budget_and_success_never_calls_gemma(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(settings, "vision_stage_timeout_seconds", 600.0)
    monkeypatch.setattr(settings, "vision_cloud_stage_timeout_seconds", 300.0)
    monkeypatch.setattr(settings, "vision_timeout_seconds", 120.0)
    class SlowCloud(CloudDouble):
        def generate(self, image_uri, tier, triage, deadline, **kwargs):
            assert deadline == 300.0
            now[0] += 179.0
            return super().generate(image_uri, tier, triage, deadline, **kwargs)
    local = LocalDouble()
    result = VisualModelRouter(SlowCloud(), local, clock=lambda: now[0], local_fallback_enabled=True).extract(FIXTURE.read_bytes(), "fixture")
    assert result._actual_provider == "cloudflare" and local.calls == 0


@pytest.mark.parametrize("status", [502, 503, 429])
def test_actual_vision_transport_retries_then_falls_back(status, monkeypatch):
    monkeypatch.setattr(settings, "vision_max_retries", 1)
    calls = []
    transport = CloudflareProvider(ProviderPolicy("https://worker.test", SecretStr("test-secret")),
        httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(status)))
    local = LocalDouble()
    result = VisualModelRouter(CloudflareVisionProvider(transport), local, local_fallback_enabled=True).extract(FIXTURE.read_bytes(), "fixture")
    assert len(calls) == 2 and local.calls == 1
    assert result._routing_provenance["provider_used"] == "ollama"
    assert result._routing_provenance["attempt_count"] == 3


def test_retry_after_is_respected_and_retry_count_bounded(monkeypatch):
    sleeps, calls = [], []
    monkeypatch.setattr("app.core.reasoning.time.sleep", lambda seconds: sleeps.append(seconds))
    policy = ProviderPolicy("https://worker.test", SecretStr("test-secret"), retry_backoff=0)
    primary = CloudflareProvider(policy, httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(429, headers={"Retry-After":"7"})))
    fallback = Fallback()
    ReasoningProviderRouter(primary, fallback, policy).generate(REQUEST)
    assert sleeps == [7] and len(calls) == 2 and fallback.calls == 1


def test_retry_after_beyond_budget_does_not_retry_early(monkeypatch):
    calls = []
    policy = ProviderPolicy("https://worker.test", SecretStr("test-secret"))
    primary = CloudflareProvider(policy, httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(429, headers={"Retry-After":"3600"})))
    fallback = Fallback()
    ReasoningProviderRouter(primary, fallback, policy).generate(REQUEST)
    assert len(calls) == 1 and fallback.calls == 1


def test_text_fallback_can_be_disabled():
    policy = ProviderPolicy("https://worker.test", SecretStr("test-secret"), max_retries=0)
    route = ReasoningProviderRouter(CloudflareProvider(policy, httpx.MockTransport(lambda _: httpx.Response(502))), None, policy)
    with pytest.raises(ProviderFailure, match="PROVIDER_UNAVAILABLE"):
        route.generate(REQUEST)


def test_local_extraction_can_be_independently_reviewed_by_cloud():
    data = extraction()
    data._actual_provider, data._actual_model = "ollama", "gemma3:4b"
    class Review:
        def fetch_payload(self, payload, deadline):
            assert payload["tier"] == "general"
            return json.dumps({"ok":True,"task":"vision_verify","request_id":"review",
                "model":MODELS["general"],"usage":None,"latency_ms":1.0,
                "response":{"claims":[{"claim_id":CLAIM.claim_id,"status":"SUPPORTED","visible_support":"Water","reason":"Visible"}]}}).encode()
    result = CloudflareIndependentVisualVerifier(transport=Review()).verify(FIXTURE.read_bytes(), (CLAIM,), data)
    assert result.status == "VERIFIED"


def test_identical_inflight_scoped_images_run_once():
    class SlowCloud(CloudDouble):
        def generate(self, *args, **kwargs):
            time.sleep(.03)
            return super().generate(*args, **kwargs)
    cloud = SlowCloud()
    router = VisualModelRouter(cloud, LocalDouble())
    with visual_scope(VisualScope(user_id="owner", source_id="source", source_version=1)):
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(copy_context().run, router.extract, FIXTURE.read_bytes(), "fixture") for _ in range(3)]
            results = [f.result() for f in futures]
    assert len(cloud.calls) == 1
    assert sum(r._routing_provenance["cache_hit"] for r in results) == 2


def test_cache_invalidates_processing_configuration_and_expires(monkeypatch):
    now = [1.0]
    cloud = CloudDouble()
    router = VisualModelRouter(cloud, LocalDouble(), clock=lambda: now[0])
    monkeypatch.setattr(settings, "vision_cache_ttl_seconds", 10)
    with visual_scope(VisualScope(user_id="owner", source_id="source", source_version=1)):
        router.extract(FIXTURE.read_bytes(), "fixture")
        router.extract(FIXTURE.read_bytes(), "fixture")
        monkeypatch.setattr(settings, "pipeline_config_version", "changed")
        router.extract(FIXTURE.read_bytes(), "fixture")
        now[0] = 12
        router.extract(FIXTURE.read_bytes(), "fixture")
    assert len(cloud.calls) == 3


def test_durable_job_keeps_result_failure_and_owner_after_restart(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = DurableJobStore(db_path=path)
    job = PipelineJob(job_id="source-job", job_type="source_ingestion", status="completed", is_finished=True,
        metadata={"source_owner":"owner"}, result={"source_id":"source", "content_ready":True})
    store.save_job(job)
    loaded = DurableJobStore(db_path=path).load_job(job.job_id)
    assert loaded.result == job.result and loaded.source_lifecycle == "CONTENT_READY"
    job.status = "failed"
    job.failure = SourceFailure(stage="INDEXING",code="QDRANT_INDEX_FAILED",retryable=True,message="Retry indexing")
    store.save_job(job)
    assert DurableJobStore(db_path=path).load_job(job.job_id).failure == job.failure


def test_legacy_text_entrypoints_use_cloud_router(monkeypatch):
    from app.core.llm import get_llm_provider, RoutedTextProvider
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "reasoning_provider", "cloudflare")
    assert isinstance(get_llm_provider(), RoutedTextProvider)


def test_configured_long_read_timeout_is_preserved():
    requests = []
    policy = ProviderPolicy("https://worker.test", SecretStr("test-secret"), read_timeout=180, overall_timeout=300)
    result = CloudflareProvider(policy,httpx.MockTransport(lambda req: requests.append(req) or httpx.Response(200,json=envelope()))).generate(REQUEST)
    assert requests[0].extensions["timeout"]["read"] == 180
    assert result.telemetry.provider == "cloudflare"


def test_native_text_on_later_page_survives_first_page_vision_failure(tmp_path, monkeypatch):
    import pymupdf as fitz
    from app.services.extractor import extract_from_pdf
    from app.services.vision import VisionExtractionFailed
    document = fitz.open()
    document.new_page().insert_image(fitz.Rect(40,40,540,240),stream=FIXTURE.read_bytes())
    document.new_page().insert_text((40,40),"Osmosis is the movement of water through a selectively permeable membrane.")
    path = tmp_path / "scan-then-text.pdf"
    document.save(path)
    document.close()
    def fail(*args, **kwargs):
        raise VisionExtractionFailed("private error", "VISION_TIMEOUT")
    monkeypatch.setattr("app.services.visual_evidence.visual_content_unit",fail)
    units = extract_from_pdf(path,"source","asset")
    assert units and units[0].page_number == 2
    assert units[0].provenance["missing_visual_content"][0]["page_number"] == 1
    assert "private" not in json.dumps(units[0].provenance)


def test_independent_review_cache_is_scoped_and_avoids_duplicate_calls(monkeypatch):
    from app.services.independent_visual_verifier import _review_cache
    _review_cache.clear()
    class Review:
        calls = 0
        def fetch_payload(self, payload, deadline):
            self.calls += 1
            return json.dumps({"ok":True,"task":"vision_verify","request_id":"review",
                "model":MODELS["deep"],"usage":None,"latency_ms":1.0,
                "response":{"claims":[{"claim_id":CLAIM.claim_id,"status":"SUPPORTED","visible_support":"Water","reason":"Visible"}]}}).encode()
    transport = Review()
    for user in ["A","A","B"]:
        with visual_scope(VisualScope(user_id=user,source_id="review-cache-source",source_version=1)):
            result = CloudflareIndependentVisualVerifier(transport=transport).verify(FIXTURE.read_bytes(),(CLAIM,),extraction())
            assert result.status == "VERIFIED"
    assert transport.calls == 2


def test_worker_native_quota_does_not_retry_before_local_fallback():
    calls = []
    policy = ProviderPolicy("https://worker.test", SecretStr("test-secret"))
    transport = CloudflareProvider(policy,httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(429,json={"ok":False,"error":"AI_QUOTA_EXCEEDED","native_code":3036})))
    local = LocalDouble()
    result = VisualModelRouter(CloudflareVisionProvider(transport),local,local_fallback_enabled=True).extract(FIXTURE.read_bytes(),"fixture")
    assert len(calls) == 1 and local.calls == 1
    assert result._routing_provenance["fallback_reason"] == "QUOTA_EXHAUSTED"


def test_shared_job_budget_prevents_new_request_after_expiry():
    from app.core.inference_budget import processing_budget
    from app.core import inference_budget
    from unittest.mock import patch
    now = [100.0]
    with patch.object(inference_budget.time,"monotonic",lambda:now[0]):
        with processing_budget(10):
            now[0] = 111.0
            with pytest.raises(TimeoutError):
                inference_budget.check_budget()


def test_video_fusion_preserves_spoken_segments_and_frame_timestamps():
    from app.services.video.fusion import fuse_units
    from app.services.video.frame_extractor import FrameCapture
    from app.services.video.transcriber import Segment
    frame = FrameCapture(timestamp=3.0)
    frame.description = "Root 10; left child 5; right child 15."
    units = fuse_units([Segment(start=1,end=5,text="Smaller keys are on the left.")], [frame], "source", "asset")
    assert len(units) == 1 and "Smaller keys" in units[0].text
    assert units[0].timestamp_start == 1 and units[0].timestamp_end == 5
    assert "Root 10" in units[0].visual_description
