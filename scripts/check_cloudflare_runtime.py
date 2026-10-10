r"""Small real-provider smoke check; no user documents, credentials or database writes.

Run from the repository: .venv\Scripts\python.exe scripts/check_cloudflare_runtime.py
The deployed Worker may differ from the checked-in source until it is redeployed.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import io
import json
import time
from urllib.parse import urlsplit
from PIL import Image, ImageDraw
from app.core.config import settings
from app.core.reasoning import Message, ReasoningRequest, ProviderFailure, get_cloud_reasoning_router
from app.services.visual_router import CloudflareVisionProvider, VisualModelRouter, VisualSignals
from app.services.vision import VisionExtractionFailed
from app.services.independent_visual_verifier import CloudflareIndependentVisualVerifier
from app.services.visual_verifier import VisualEvidenceVerifier, verification_summary
from app.services.educational_content import Teaching, normalize_teaching_json
from pydantic import ValidationError


def check_text_task(task: str, *, teaching: bool = False) -> bool:
    started = time.monotonic()
    phase = "transport_envelope"
    try:
        instruction = ('Return strict JSON teaching about binary search trees. explanation must be a string. '
                       'Include topic, explanation, key_concepts, examples, equations, relationships. '
                       'Keep the explanation to two sentences.' if teaching else
                       'Return only JSON: {"answer":"A binary search tree orders smaller keys to the left and larger keys to the right."}')
        # Reasoning models may spend their output budget before visible answer
        # content. Use a realistic budget instead of treating a 128-token probe
        # as equivalent to the application's lesson workload.
        result = get_cloud_reasoning_router().primary.generate(ReasoningRequest(task=task,
            messages=[Message(role="user", content=instruction)], max_tokens=2048,
            response_schema=Teaching.model_json_schema() if teaching else None))
        if teaching:
            phase = "lesson_contract"
            Teaching.model_validate(normalize_teaching_json(result.response))
        else:
            parsed = json.loads(result.response)
            assert isinstance(parsed.get("answer"), str) and parsed["answer"].strip()
        print(json.dumps({"task": task, "status": "PASS", "provider": result.telemetry.provider,
            "model": result.telemetry.model, "elapsed_seconds": round(time.monotonic()-started, 3)}))
        return True
    except (ProviderFailure, ValueError, AssertionError) as error:
        print(json.dumps({"task": task, "status": "FAIL", "category": error.category if isinstance(error, ProviderFailure) else "INVALID_RESPONSE",
            "phase": phase, "validation_errors": [{"field": item['loc'][0] if item['loc'] and item['loc'][0] in Teaching.model_fields else "unknown", "type": item['type']} for item in error.errors(include_input=False)] if isinstance(error, ValidationError) else [],
            "elapsed_seconds": round(time.monotonic()-started, 3)}))
        return False


def main() -> int:
    print(json.dumps({"endpoint_host":urlsplit(settings.cloudflare_worker_url).hostname,
        "text_primary":settings.reasoning_provider,"vision_primary":settings.vision_provider,
        "text_request_seconds":settings.cloudflare_read_timeout,
        "text_stage_seconds":settings.cloudflare_overall_timeout,
        "vision_request_seconds":settings.vision_cloud_timeout_seconds,
        "vision_stage_seconds":settings.vision_stage_timeout_seconds}))
    if not settings.cloudflare_worker_url or not settings.cloudflare_worker_secret.get_secret_value():
        print(json.dumps({"status":"NOT_RUN", "reason":"Missing Cloudflare credentials"}))
        return 2
    failures = 0
    for task in ("qa", "content_understanding", "reasoning"):
        if not check_text_task(task, teaching=task == "reasoning"):
            failures += 1
    image = Image.new("RGB",(800,300),"white")
    ImageDraw.Draw(image).text((40,50),"Binary Search Tree\nRoot: 10\nLeft child: 5\nRight child: 15",fill="black",font_size=28)
    buffer = io.BytesIO()
    image.save(buffer,format="PNG")
    started = time.monotonic()
    try:
        data = VisualModelRouter(CloudflareVisionProvider(),local_fallback_enabled=False).extract(buffer.getvalue(),"synthetic-smoke",VisualSignals(semantic_kind="TEXT"))
        review = VisualEvidenceVerifier(CloudflareIndependentVisualVerifier()).verify(buffer.getvalue(),data)
        print(json.dumps({"task":"vision","status":"PASS","provider":data._actual_provider,"model":data._actual_model,
            "attempts":data._routing_provenance["attempt_count"], "fallback_used":False,
            "verification":verification_summary(review),"elapsed_seconds":round(time.monotonic()-started,3)}))
        if review.status != "VERIFIED":
            failures += 1
    except VisionExtractionFailed as error:
        failures += 1
        print(json.dumps({"task":"vision","status":"FAIL","category":error.error_code,
            "trace":error.route_trace.model_dump() if error.route_trace else None,
            "elapsed_seconds":round(time.monotonic()-started,3)}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
