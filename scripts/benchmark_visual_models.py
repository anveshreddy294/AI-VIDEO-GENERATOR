"""Explicit post-deployment evaluation only; never fans out in production ingestion."""

from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import TypedDict
from pydantic import JsonValue

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.visual_router import (
    CloudflareVisionProvider,
    MODELS,
    Tier,
    private_image_transport,
)
from app.services.vision import (
    _validate_vision_extraction,
    VisionExtractionFailed,
    format_vision_markdown,
)
from app.core.reasoning import ProviderFailure
from app.services.schemas import ContentUnit
from app.services.ingestion.normalizer import normalize_content_units
from app.services.security.content_sanitizer import sanitize_content_records
from scripts.visual_structure_ground_truth import (
    structure_checks,
    STRUCTURAL_WORDS_BY_FIXTURE,
    VISIBLE,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/multimodal"
EXPECTED: dict[str, tuple[str, ...]] = {
    "printed.png": ("osmosis", "water", "membrane"),
    "handwriting.png": ("force", "mass", "acceleration"),
    "flowchart.png": ("photosynthesis", "sunlight", "leaf", "chemical energy"),
    "graph.png": ("time", "distance"),
    "table.png": ("mass", "acceleration", "force", "2", "3", "6"),
    "injection.png": ("osmosis", "water", "membrane"),
    "equation.png": ("force", "mass", "acceleration"),
    "complex-diagram.png": ("sensor", "filter", "controller", "alarm", "motor"),
}



LAYOUT_WORDS = set(
    "the a an is are this shows diagram image and of to through with from text labeled label node nodes arrow arrows left right top bottom box boxes line lines points toward connects relationship relationships step steps visible uncertain unknown title heading axis units in it two three five table rows columns x y".split()
)


def score_fixture(name: str, output: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Finite known-visible assertions; unsupported-claim checks are conservative flags."""
    parsed = _validate_vision_extraction(output, name)
    text = format_vision_markdown(parsed).casefold()
    checks: dict[str, bool] = {term: term in text for term in EXPECTED[name]}
    if name in ("handwriting.png", "equation.png"):
        checks["equation_fidelity"] = any(
            re.sub(r"[\s*×]", "", formula).casefold() == "f=ma"
            for formula in parsed.formulas
        )
    if name in ("flowchart.png", "complex-diagram.png"):
        checks.update(structure_checks(name, parsed))
    if name == "graph.png":
        checks["axes"] = any(
            "time" in g.x_axis.casefold() and "distance" in g.y_axis.casefold()
            for g in parsed.graphs
        )
    if name == "table.png":
        checks["table_cells"] = any(
            len(t.headers) == 3 and ["2", "3", "6"] in t.rows for t in parsed.tables
        )
    if name == "injection.png":
        unit = ContentUnit(
            source_id="fixture",
            asset_id="fixture",
            modality="image",
            text=text,
            provenance={"visual_schema_version": "visual-v2"},
        )
        clean = sanitize_content_records(normalize_content_units([unit]))
        safe = " ".join(row.sanitized_text for row in clean if row.retrieval_allowed)
        checks["injection_quarantined"] = (
            "ignore previous instructions" not in safe
            and "reveal system prompt" not in safe
        )
    allowed_equations = (
        {"f=ma"} if name in ("handwriting.png", "equation.png") else set()
    )
    unsupported_equations = [
        f
        for f in parsed.formulas
        if re.sub(r"[\s*×]", "", f).casefold() not in allowed_equations
    ]
    evidence_lines = (
        parsed.visible_text
        + parsed.headings
        + parsed.paragraphs
        + parsed.bullet_points
        + parsed.diagram_entities
        + parsed.labels
        + parsed.relationships
        + parsed.arrows
        + parsed.handwriting_text
    )
    for table in parsed.tables:
        evidence_lines += table.headers + [cell for row in table.rows for cell in row]
    for graph in parsed.graphs:
        evidence_lines += (
            [graph.x_axis, graph.y_axis]
            + graph.legend
            + graph.trends
            + graph.visible_values
        )
    words = set(re.findall(r"[a-z]+", " ".join(evidence_lines).casefold()))
    permitted = set(re.findall(r"[a-z]+", VISIBLE[name].casefold())) | LAYOUT_WORDS
    if name in ("flowchart.png", "complex-diagram.png"):
        words.update(
            re.findall(
                r"[a-z]+",
                (
                    parsed.visual_structure + " " + " ".join(parsed.uncertain_elements)
                ).casefold(),
            )
        )
        permitted |= STRUCTURAL_WORDS_BY_FIXTURE[name]
    unknown_words = words - permitted
    checks["no_unsupported_equations"] = not unsupported_equations
    return {
        "checks": checks,
        "fixture_score": sum(checks.values()) / len(checks),
        "unsupported_equations_detected": bool(unsupported_equations),
        "unsupported_vocabulary_count": len(unknown_words),
        "unsupported_claims_flagged": bool(unknown_words or unsupported_equations),
        "unsupported_claim_check": "CONSERVATIVE_VISIBLE_VOCABULARY_NOT_EXHAUSTIVE_PROOF",
        "output_bytes": len(json.dumps(output).encode()),
        "validation_status": "PASS",
        "schema_valid": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-live",
        action="store_true",
        help="Only after approved Worker deployment; incurs hosted inference usage.",
    )
    parser.add_argument("--repeats", type=int, choices=(1, 2), default=1)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "storage/runtime/visual-benchmark.json"
    )
    parser.add_argument(
        "--tiers", nargs="+", choices=tuple(MODELS), default=list(MODELS)
    )
    args = parser.parse_args()
    rows: list[dict[str, JsonValue]] = []
    provider = CloudflareVisionProvider() if args.run_live else None
    for tier in args.tiers:
        model = MODELS[tier]
        for name in EXPECTED:
            for repeat in range(args.repeats):
                result: dict[str, JsonValue] = {
                    "tier": tier,
                    "model": model,
                    "model_requested": model,
                    "actual_model_used": None,
                    "provider_latency_ms": None,
                    "fixture": name,
                    "iteration": repeat + 1,
                    "thermal_state": "UNKNOWN",
                    "status": "NOT_RUN",
                }
                if provider:
                    started = time.perf_counter()
                    try:
                        response = provider.generate(
                            private_image_transport((FIXTURES / name).read_bytes()),
                            tier,
                            False,
                            time.monotonic() + 60,
                        )
                        result["model_requested"] = model
                        result["actual_model_used"] = response.model
                        result["provider_latency_ms"] = response.worker_latency_ms
                        result["fixture_output"] = response.output
                        result.update(score_fixture(name, response.output))
                        result["status"] = "MEASURED"
                        result["actual_model"] = response.model
                    except (ProviderFailure, VisionExtractionFailed) as error:
                        result["status"] = "FAILED"
                        result["error_category"] = (
                            error.category
                            if isinstance(error, ProviderFailure)
                            else error.error_code
                        )
                    result["total_provider_latency_ms"] = (
                        time.perf_counter() - started
                    ) * 1000
                result["request_latency_ms"] = result.get("total_provider_latency_ms")
                result["quality_gate_pass"] = (
                    result.get("fixture_score") == 1.0
                    and result.get("validation_status") == "PASS"
                    and result.get("unsupported_claims_flagged") is False
                )
                rows.append(result)
    report = {
        "policy_status": "PROVISIONAL_UNTIL_REAL_BENCHMARK",
        "graph_fixture_limit": "Axes/text fixture; no plotted graph. Does not test numerical digitization.",
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "live": args.run_live,
                "cases": len(rows),
                "output": str(args.output),
                "policy_status": "PROVISIONAL",
            }
        )
    )


if __name__ == "__main__":
    main()
