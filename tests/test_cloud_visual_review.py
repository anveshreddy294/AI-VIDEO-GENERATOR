"""Independent cloud review and fail-fast production routes, entirely offline."""
from __future__ import annotations
import json
import time
import pytest
from pydantic import JsonValue
from app.services.independent_visual_verifier import CloudflareIndependentVisualVerifier
from app.services.visual_contracts import VisionExtractionData
from app.services.visual_verifier import VerificationCheck, VisualEvidenceVerifier
from app.services.visual_router import MODELS, VisualModelRouter, private_image_transport
from app.services.vision import VisionExtractionFailed, _validate_vision_extraction
from app.core.reasoning import ProviderFailure
from tests.test_visual_model_router import DATA, FIXTURE, CloudDouble, LocalDouble

class Transport:
    def __init__(self, status: str = "SUPPORTED", *, foreign: bool = False, missing: bool = False) -> None:
        self.status = status
        self.foreign = foreign
        self.missing = missing
        self.calls: list[dict[str, JsonValue]] = []
        self.deadline: float | None = None
    def fetch_payload(self, payload: dict[str, JsonValue], deadline: float) -> bytes:
        self.calls.append(payload)
        self.deadline = deadline
        decisions = [] if self.missing else [{"claim_id": "claim:0", "status": self.status, "visible_support": "Water", "reason": "Visible label"}]
        return json.dumps({"ok": True, "task": "vision_verify", "request_id": "review", "model": MODELS["general"] if self.foreign else MODELS["deep"],
            "model_requested": MODELS["deep"], "response": json.dumps({"claims": decisions}), "usage": None, "latency_ms": 1.0}).encode()

def extraction() -> VisionExtractionData:
    data = _validate_vision_extraction(DATA, "image")
    data._actual_provider = "cloudflare"
    data._actual_model = MODELS["general"]
    return data

CLAIM = VerificationCheck(claim_id="claim:0", claim_type="labels", claim="Water", status="UNCERTAIN", reason="No independent anchor")

@pytest.mark.parametrize("status,expected", [("SUPPORTED", "VERIFIED"), ("CONTRADICTED", "REJECTED"), ("UNCERTAIN", "UNCERTAIN")])
def test_cloud_pixel_review_is_independent_and_typed(status: str, expected: str) -> None:
    transport = Transport(status)
    deadline = time.monotonic() + 10
    result = CloudflareIndependentVisualVerifier(transport=transport, deadline=deadline).verify(FIXTURE.read_bytes(), (CLAIM,), extraction())
    assert result.status == expected
    assert transport.calls[0]["tier"] == "deep"
    assert transport.calls[0]["task"] == "vision_verify"
    assert transport.deadline == deadline

@pytest.mark.parametrize("options", [{"foreign": True}, {"missing": True}])
def test_bad_or_same_model_review_cannot_publish(options: dict[str, bool]) -> None:
    result = CloudflareIndependentVisualVerifier(transport=Transport(**options)).verify(FIXTURE.read_bytes(), (CLAIM,), extraction())
    assert result.status == "UNCERTAIN"

def test_expired_shared_deadline_does_not_call_review() -> None:
    transport = Transport()
    result = CloudflareIndependentVisualVerifier(transport=transport, deadline=time.monotonic()-1).verify(FIXTURE.read_bytes(), (CLAIM,), extraction())
    assert result.status == "UNCERTAIN" and not transport.calls

def test_default_production_route_never_burns_local_timeout() -> None:
    local = LocalDouble()
    cloud = CloudDouble([ProviderFailure("TIMEOUT", True), ProviderFailure("TIMEOUT", True)])
    with pytest.raises(VisionExtractionFailed) as caught:
        VisualModelRouter(cloud, local).extract(FIXTURE.read_bytes(), "image")
    assert local.calls == 0 and len(cloud.calls) == 2
    assert caught.value.error_code == "VISION_TIMEOUT"
    assert caught.value.route_trace is not None and not caught.value.route_trace.local_fallback_attempted

def test_literal_duplicates_review_once_and_restore_every_claim() -> None:
    transport = Transport()
    duplicate = CLAIM.model_copy(update={"claim_id": "claim:1", "claim_type": "handwriting_text"})
    result = CloudflareIndependentVisualVerifier(transport=transport).verify(FIXTURE.read_bytes(), (CLAIM, duplicate), extraction())
    assert result.status == "VERIFIED" and len(result.checks) == 2
    prompt = str(transport.calls[0]["prompt"])
    claims = json.loads(prompt.split("CLAIM_DATA=", 1)[1].split("\nJSON_SCHEMA=", 1)[0])["claims"]
    assert len(claims) == 1


@pytest.mark.parametrize("category,reason",[("TIMEOUT","INDEPENDENT_VERIFIER_TIMEOUT"),("RATE_LIMIT","INDEPENDENT_VERIFIER_RATE_LIMIT"),("PROVIDER_UNAVAILABLE","INDEPENDENT_VERIFIER_UNAVAILABLE")])
def test_cloud_review_failure_preserves_safe_category(category: str, reason: str) -> None:
    class Failing:
        def fetch_payload(self, payload: dict[str,JsonValue], deadline: float) -> bytes:
            raise ProviderFailure(category, True)
    result=CloudflareIndependentVisualVerifier(transport=Failing()).verify(FIXTURE.read_bytes(),(CLAIM,),extraction())
    assert result.status=="UNCERTAIN" and result.reasons==[reason]


@pytest.mark.parametrize("count", [17, 145, 385])
def test_dense_claims_are_bounded_without_global_rejection(count: int) -> None:
    class Batched:
        def __init__(self) -> None:
            self.sizes: list[int] = []
        def fetch_payload(self, payload: dict[str, JsonValue], deadline: float) -> bytes:
            claims=json.loads(str(payload["prompt"]).split("CLAIM_DATA=",1)[1].split("\nJSON_SCHEMA=",1)[0])["claims"]
            self.sizes.append(len(claims))
            return json.dumps({"ok":True,"task":"vision_verify","request_id":"review","model":MODELS["deep"],
                "response":{"claims":[{"claim_id":c["claim_id"],"status":"SUPPORTED","visible_support":c["claim"],"reason":"Visible"} for c in claims]},"usage":None,"latency_ms":1.0}).encode()
    transport=Batched()
    claims=tuple(CLAIM.model_copy(update={"claim_id":str(i),"claim":f"Visible label {i}"}) for i in range(count))
    result=CloudflareIndependentVisualVerifier(transport=transport).verify(FIXTURE.read_bytes(),claims,extraction())
    assert max(transport.sizes)<=16 and len(transport.sizes)<=24
    assert sum(c.status=="VERIFIED" for c in result.checks)==min(count,384)
    assert result.status == ("VERIFIED" if count<=384 else "UNCERTAIN")
    assert len(result.checks)==count


def test_production_verifier_has_no_fixture_hash_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.visual_fixture_oracle import REAL_SOURCE_CHECKS
    monkeypatch.setattr(VisualEvidenceVerifier,"_source_checks",REAL_SOURCE_CHECKS)
    assert VisualEvidenceVerifier().verify(FIXTURE.read_bytes(),extraction()).status=="UNCERTAIN"
