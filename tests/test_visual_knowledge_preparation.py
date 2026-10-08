"""Accepted visual evidence, minimal canonical hierarchy, and strict structurer boundaries."""

from __future__ import annotations
import copy
import json
from pathlib import Path
from typing import Literal

import pytest
from pydantic import JsonValue, TypeAdapter
from app.services.content_understanding import understand_content, UnderstandingError
from app.services.evidence_anchors import build_anchors
from app.services.knowledge_models import ScopedContentUnit
from app.services.schemas import ContentUnit
from tests.test_content_understanding import SCOPE

OBJECT = TypeAdapter(dict[str, JsonValue])
ROOT = Path(__file__).parents[1]


def accepted(
    case: Literal["SIMPLE", "STANDARD"]
) -> tuple[list[ScopedContentUnit], dict[str, JsonValue]]:
    records = json.loads(
        (ROOT / "docs/phase7a3d_structuring_before.json").read_text(encoding="utf-8")
    )["records"]
    record = next(r for r in records if r["case"] == case)
    raw = dict(record["canonical_evidence"][0])
    raw.update(source_id=SCOPE.source_id, content_id="visual_unit")
    unit = ContentUnit.model_validate(raw)
    units = [
        ScopedContentUnit(
            **SCOPE.model_dump(),
            content_id=unit.content_id,
            content=unit,
            provenance=unit.provenance,
        )
    ]
    label = "Osmosis" if case == "SIMPLE" else "Photosynthesis"
    ref = {"anchor_id": build_anchors(SCOPE, units)[0].anchor_id}
    body: dict[str, JsonValue] = {
        "topics": [{"key": "t1", "title": label, "evidence": [ref]}],
        "subtopics": [
            {"key": "s1", "topic_key": "t1", "title": label, "evidence": [ref]}
        ],
        "concepts": [
            {
                "key": "c1",
                "subtopic_key": "s1",
                "name": label,
                "definition": None,
                "evidence": [ref],
            }
        ],
        "prerequisites": [],
    }
    return units, body


@pytest.mark.parametrize("case", ["SIMPLE", "STANDARD"])
def test_accepted_visual_prepares_minimal_evidenced_hierarchy(
    case: Literal["SIMPLE", "STANDARD"]
) -> None:
    units, body = accepted(case)
    result = understand_content(SCOPE, units, lambda _: json.dumps(body))
    assert (
        len(result.snapshot.topics)
        == len(result.snapshot.subtopics)
        == len(result.snapshot.concepts)
        == 1
    )
    assert (
        result.snapshot.topics[0].title
        == result.snapshot.subtopics[0].title
        == result.snapshot.concepts[0].name
    )
    assert (
        result.snapshot.topics[0].provenance["evidence"]
        and result.snapshot.subtopics[0].provenance["evidence"]
    )
    assert result.snapshot.content_concepts[0].content_id == units[0].content_id
    assert all(value >= 0 for value in result.stage_timings.values())
    assert result.repair_model_calls == 0
    assert (
        result.snapshot
        == understand_content(SCOPE, units, lambda _: json.dumps(body)).snapshot
    )


@pytest.mark.parametrize(
    "defect",
    [
        "definition",
        "parent",
        "orphan",
        "fake_label",
        "wrong_evidence",
        "foreign_anchor",
    ],
)
def test_unsupported_content_and_membership_fail_after_bounded_model_repair(
    defect: str,
) -> None:
    units, original = accepted("SIMPLE")
    body = copy.deepcopy(original)
    if defect == "definition":
        body["concepts"][0][
            "definition"
        ] = "Mitochondria generate ATP by oxidative phosphorylation."
    elif defect == "parent":
        body["subtopics"][0]["topic_key"] = "foreign"
    elif defect == "orphan":
        body["concepts"][0]["subtopic_key"] = "foreign"
    elif defect == "fake_label":
        body["topics"][0]["title"] = "Main Topic"
    elif defect == "wrong_evidence":
        body["concepts"][0]["name"] = "Water Movement"
        body["concepts"][0]["evidence"] = [
            {"anchor_id": build_anchors(SCOPE, units)[1].anchor_id}
        ]
    else:
        body["concepts"][0]["evidence"] = [{"anchor_id": "EA_foreign"}]
    calls: list[str] = []

    def model(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps(body)

    with pytest.raises(UnderstandingError):
        understand_content(SCOPE, units, model)
    assert len(calls) == 2


def test_visual_identity_grouping_requires_accepted_visual_provenance() -> None:
    units, body = accepted("STANDARD")
    altered = units[0].content.model_copy(update={"provenance": {}})
    units = [units[0].model_copy(update={"content": altered, "provenance": {}})]
    with pytest.raises(UnderstandingError, match="INVALID_HIERARCHY|NO_SAFE_CONTENT"):
        understand_content(SCOPE, units, lambda _: json.dumps(body))


@pytest.mark.parametrize("invent", [False, True])
def test_one_syntax_repair_is_fully_revalidated(invent: bool) -> None:
    units, body = accepted("STANDARD")
    if invent:
        body["concepts"][0]["definition"] = "Plants create glucose by carbon fixation."
    calls: list[str] = []

    def model(prompt: str) -> str:
        calls.append(prompt)
        return "broken JSON" if len(calls) == 1 else json.dumps(body)

    if invent:
        with pytest.raises(UnderstandingError, match="UNSUPPORTED_EVIDENCE"):
            understand_content(SCOPE, units, model)
    else:
        result = understand_content(SCOPE, units, model)
        assert result.repair_model_calls == 1
    assert len(calls) == 2 and "\nREPAIR:" in calls[1]
    assert "SOURCE_DATA=" in calls[1] and "PREVIOUS_PROPOSAL_DATA=" in calls[1]


def test_formatter_subtopic_caption_normalizes_only_explicit_visual_parent() -> None:
    from app.services.content_understanding import normalize_visual_presentation
    from app.services.evidence_anchors import (
        resolve_proposal,
        AnchoredStructureProposal,
    )

    units, body = accepted("STANDARD")
    body["subtopics"][0]["title"] = "Visible Content & Transcription"
    proposal = resolve_proposal(
        SCOPE, units, AnchoredStructureProposal.model_validate_json(json.dumps(body))
    )
    repaired, rules = normalize_visual_presentation(SCOPE, units, proposal)
    assert repaired.subtopics[0].title == proposal.topics[0].title
    assert repaired.concepts == proposal.concepts and repaired.topics == proposal.topics
    assert repaired.subtopics[0].evidence == proposal.subtopics[0].evidence and rules
    result = understand_content(SCOPE, units, lambda _: json.dumps(body))
    assert result.deterministic_repairs == rules and result.repair_model_calls == 0
    body["concepts"][0]["definition"] = "Invented educational explanation."
    with pytest.raises(UnderstandingError, match="UNSUPPORTED_EVIDENCE"):
        understand_content(SCOPE, units, lambda _: json.dumps(body))


def test_single_visual_request_constrains_literal_label_without_changing_canonical_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import reasoning
    from app.services.structurer import generate_educational_proposal
    from app.services.evidence_anchors import AnchoredStructureProposal
    from app.core.reasoning import ReasoningRequest, ReasoningResult, Telemetry
    import httpx
    from tests.test_reasoning_provider import router

    captured: list[ReasoningRequest] = []
    route, _ = router(lambda _: httpx.Response(500))

    def generate(request: ReasoningRequest) -> ReasoningResult:
        captured.append(request)
        return ReasoningResult(
            response="{}",
            telemetry=Telemetry(
                provider="cloudflare",
                task=request.task,
                outcome="SUCCESS",
                transport_latency_seconds=0.0,
            ),
        )

    monkeypatch.setattr(route, "generate", generate)
    monkeypatch.setattr(reasoning, "get_reasoning_router", lambda: route)
    generate_educational_proposal(
        'Classify.\nSOURCE_VISUAL_LABEL="Photosynthesis"\nSOURCE_DATA=[]'
    )
    schema = captured[0].response_schema
    assert schema is not None
    assert schema["properties"]["concepts"]["maxItems"] == 1
    assert schema["$defs"]["AnchoredConcept"]["properties"]["name"]["enum"] == [
        "Photosynthesis"
    ]
    assert schema["$defs"]["AnchoredConcept"]["properties"]["definition"]["enum"] == [
        None
    ]
    assert (
        "enum"
        not in AnchoredStructureProposal.model_json_schema()["$defs"][
            "AnchoredConcept"
        ]["properties"]["name"]
    )


def test_verified_handwriting_is_a_literal_visual_hierarchy_label() -> None:
    units, body = accepted("SIMPLE")
    label = "Osmosis"
    provenance = copy.deepcopy(units[0].content.provenance)
    visual = provenance["extraction"]
    visual.update(visible_text=[], headings=[], labels=[], diagram_entities=[], handwriting_text=[label])
    content = units[0].content.model_copy(update={"provenance": provenance})
    units = [units[0].model_copy(update={"content": content, "provenance": provenance})]
    def model(prompt: str) -> str:
        assert 'SOURCE_VISUAL_LABEL="Osmosis"' in prompt
        return json.dumps(body)
    result = understand_content(SCOPE, units, model)
    assert result.snapshot.topics[0].title == label
    assert result.snapshot.subtopics[0].title == label
    assert result.snapshot.concepts[0].name == label


def test_verified_slide_regions_keep_separate_literal_topics() -> None:
    units,base=accepted("SIMPLE")
    source=units[0]
    labels=["Feasibility and viability","Impact and benefits","Implementation roadmap"]
    regions=[]
    for i,label in enumerate(labels):
        provenance=copy.deepcopy(source.content.provenance)
        provenance.update(region_policy="repeated-slide-footers-v1",visual_verification={"status":"VERIFIED"})
        provenance["extraction"].update(headings=[label],visible_text=[label],labels=[],diagram_entities=[],relationships=[])
        content=source.content.model_copy(update={"content_id":"region"+str(i),"text":label,"provenance":provenance,"sequence_index":i})
        regions.append(source.model_copy(update={"content_id":content.content_id,"content":content,"provenance":provenance}))
    anchors=build_anchors(SCOPE,regions)
    body={"topics":[],"subtopics":[],"concepts":[],"prerequisites":[]}
    for i,label in enumerate(labels):
        ref={"anchor_id":next(a.anchor_id for a in anchors if a.content_id=="region"+str(i))}
        body["topics"].append({"key":"t"+str(i),"title":label,"evidence":[ref]})
        body["subtopics"].append({"key":"s"+str(i),"topic_key":"t"+str(i),"title":label,"evidence":[ref]})
        body["concepts"].append({"key":"c"+str(i),"subtopic_key":"s"+str(i),"name":label,"definition":None,"evidence":[ref]})
    def model(prompt: str) -> str:
        assert "SOURCE_VISUAL_REGIONS=" in prompt
        return json.dumps(body)
    result=understand_content(SCOPE,regions,model)
    assert {t.title for t in result.snapshot.topics}==set(labels)
    assert len(result.snapshot.content_concepts)==3
