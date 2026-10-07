"""Bounded explicit live retest; fixture output only, never canonical application writes."""

from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from pydantic import JsonValue

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.reasoning import ProviderFailure
from app.core.config import settings
from app.services.visual_router import (
    CloudflareVisionProvider,
    MODELS,
    Tier,
    Workload,
    private_image_transport,
)
from app.services.vision import VisionExtractionFailed
from scripts.benchmark_visual_models import score_fixture

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/phase7a3c_structure_retests.json"
    )
    parser.add_argument("--tier", choices=("general", "deep"))
    parser.add_argument("--workload", choices=("flowchart", "complex_diagram"))
    parser.add_argument("--attempts", type=int, choices=range(1, 6))
    args = parser.parse_args()
    rows: list[dict[str, JsonValue]] = []
    provider = CloudflareVisionProvider() if args.run_live else None
    for tier in ("general", "deep"):
        if args.tier and tier != args.tier:
            continue
        typed_tier: Tier = "general" if tier == "general" else "deep"
        for name, workload, attempts in (
            ("flowchart.png", "flowchart", 3),
            ("complex-diagram.png", "complex_diagram", 2),
        ):
            if args.workload and workload != args.workload:
                continue
            typed_workload: Workload = (
                "flowchart" if workload == "flowchart" else "complex_diagram"
            )
            image = private_image_transport(
                (ROOT / "tests/fixtures/multimodal" / name).read_bytes()
            )
            for attempt in range(args.attempts or attempts):
                row: dict[str, JsonValue] = {
                    "tier": tier,
                    "fixture": name,
                    "workload": workload,
                    "attempt": attempt + 1,
                    "model_requested": MODELS[typed_tier],
                    "actual_model_used": None,
                    "thermal_state": "UNKNOWN",
                    "status": "NOT_RUN",
                    "provider_latency_ms": None,
                    "ollama_calls": 0,
                }
                if provider:
                    start = time.perf_counter()
                    try:
                        r = provider.generate(
                            image,
                            typed_tier,
                            False,
                            time.monotonic() + settings.vision_stage_timeout_seconds,
                            workload=typed_workload,
                        )
                        row.update(
                            actual_model_used=r.model,
                            provider_latency_ms=r.worker_latency_ms,
                            usage=r.usage,
                            fixture_output=r.output,
                        )
                        row.update(score_fixture(name, r.output))
                        row["status"] = (
                            "PASS"
                            if row.get("fixture_score") == 1
                            and row.get("unsupported_claims_flagged") is False
                            else "QUALITY_FAIL"
                        )
                    except (ProviderFailure, VisionExtractionFailed) as error:
                        row["status"] = "FAILED"
                        row["error_category"] = (
                            error.category
                            if isinstance(error, ProviderFailure)
                            else error.error_code
                        )
                        row["timeout_context_type"] = (
                            type(error.__context__).__name__
                            if error.__context__
                            else None
                        )
                    row["request_latency_ms"] = (time.perf_counter() - start) * 1000
                rows.append(row)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps({"live": args.run_live, "records": rows}, indent=2)
                    + "\n"
                )
                print(
                    json.dumps(
                        {
                            key: value
                            for key, value in row.items()
                            if key != "fixture_output"
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
