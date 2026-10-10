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


def test_grounded_visual_name_can_repair_a_wrong_local_anchor() -> None:
    from app.services.evidence_anchors import AnchoredStructureProposal, bind_verified_visual_labels
    from app.services.content_understanding import label_supported
    units, body = accepted("SIMPLE")
    anchors = build_anchors(SCOPE, units)
    body["concepts"][0]["name"] = "Water Movement"
    body["concepts"][0]["evidence"] = [{"anchor_id": anchors[1].anchor_id}]
    original = AnchoredStructureProposal.model_validate_json(json.dumps(body))
    repaired, changes = bind_verified_visual_labels(SCOPE, units, original)
    concept = repaired.concepts[0]
    lookup = {anchor.anchor_id: anchor for anchor in anchors}
    assert "grounded_name_anchor:c1" in changes
    assert all(reference.anchor_id in lookup for reference in concept.evidence)
    assert label_supported(concept.name, " ".join(lookup[reference.anchor_id].text for reference in concept.evidence), derived=True)
    result = understand_content(SCOPE, units, lambda _: json.dumps(body))
    assert any(concept.name == "Water Movement" for concept in result.snapshot.concepts)


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


def test_visual_request_preserves_full_resource_bounds_without_label_enums(
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
    expected = AnchoredStructureProposal.model_json_schema()
    for name in ("AnchoredTopic", "AnchoredSubtopic", "AnchoredConcept"):
        required = expected["$defs"][name].setdefault("required", [])
        if "evidence" not in required:
            required.append("evidence")
        expected["$defs"][name]["properties"]["evidence"]["minItems"] = 1
    assert schema == expected
    assert schema["properties"]["concepts"]["maxItems"] > 1
    assert "enum" not in schema["$defs"]["AnchoredConcept"]["properties"]["name"]


def test_verified_handwriting_is_a_literal_visual_hierarchy_label() -> None:
    units, body = accepted("SIMPLE")
    label = "Osmosis"
    provenance = copy.deepcopy(units[0].content.provenance)
    visual = provenance["extraction"]
    visual.update(visible_text=[], headings=[], labels=[], diagram_entities=[], handwriting_text=[label])
    content = units[0].content.model_copy(update={"provenance": provenance})
    units = [units[0].model_copy(update={"content": content, "provenance": provenance})]
    def model(prompt: str) -> str:
        assert "SOURCE_VISUAL_LABEL" not in prompt
        assert "Osmosis" in prompt
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
        provenance["extraction"].update(headings=[label],visible_text=[label],paragraphs=[],bullet_points=[],handwriting_text=[],labels=[],diagram_entities=[],relationships=[],arrows=[])
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



def test_one_verified_image_retains_distinct_grounded_concepts() -> None:
    units, body = accepted("SIMPLE")
    provenance = copy.deepcopy(units[0].content.provenance)
    provenance["visual_verification"] = {"status":"VERIFIED"}
    visual = provenance["extraction"]
    visual["headings"] = ["Osmosis"]
    visual["labels"] = ["Water", "Cell membrane", "Cell"]
    content = units[0].content.model_copy(update={"provenance":provenance})
    units = [units[0].model_copy(update={"content":content,"provenance":provenance})]
    anchors = build_anchors(SCOPE,units)
    body["concepts"] = [{"key":f"c{i}","subtopic_key":"s1","name":name,"definition":None,
        "evidence":[{"anchor_id":next(a.anchor_id for a in anchors if name in a.text)}]}
        for i,name in enumerate(("Water","Cell membrane","Cell"))]
    def model(prompt: str) -> str:
        assert "exactly one topic" not in prompt and "single concept" not in prompt
        return json.dumps(body)
    result = understand_content(SCOPE,units,model)
    assert {c.name for c in result.snapshot.concepts} == {"Water","Cell membrane","Cell"}
    assert len(result.snapshot.content_concepts) == 3
    assert not result.snapshot.relationships


def test_numbered_visual_headings_keep_literal_children_without_word_reordering():
    from app.services.content_understanding import visual_literal_supported
    assert visual_literal_supported("Data Processing & Storage",["2. DATA PROCESSING & STORAGE"])
    assert visual_literal_supported("Solar Panels",["Solar Panels, Wind Turbines"])
    assert not visual_literal_supported("Storage Processing",["2. DATA PROCESSING & STORAGE"])
    assert not visual_literal_supported("Nuclear Reactor",["Solar Panels, Wind Turbines"])


def test_verified_literal_rebinding_never_repairs_invention_or_foreign_reference():
    from app.services.evidence_anchors import bind_verified_visual_labels,AnchoredStructureProposal,AnchorReference
    units,body=accepted("SIMPLE")
    provenance=copy.deepcopy(units[0].provenance);provenance["visual_verification"]={"status":"VERIFIED"}
    content=units[0].content.model_copy(update={"provenance":provenance})
    units=[units[0].model_copy(update={"content":content,"provenance":provenance})]
    proposal=AnchoredStructureProposal.model_validate_json(json.dumps(body))
    foreign=proposal.topics[0].model_copy(update={"evidence":[AnchorReference(anchor_id="EA_foreign")]})
    result,repairs=bind_verified_visual_labels(SCOPE,units,proposal.model_copy(update={"topics":[foreign]}))
    assert result.topics[0]==foreign and not repairs
    invented=proposal.topics[0].model_copy(update={"title":"Nuclear Reactor"})
    result,repairs=bind_verified_visual_labels(SCOPE,units,proposal.model_copy(update={"topics":[invented]}))
    assert result.topics[0]==invented and not repairs


def test_omitted_verified_component_inventory_is_retained_without_new_claims() -> None:
    units, body = accepted("SIMPLE")
    provenance = copy.deepcopy(units[0].content.provenance)
    provenance["visual_verification"] = {"status": "VERIFIED"}
    visual = provenance["extraction"]
    visual.update(headings=["Osmosis"], labels=["Water", "Cell membrane", "Cell"],
                  diagram_entities=[], visible_text=["Osmosis", "Water", "Cell membrane", "Cell"])
    content = units[0].content.model_copy(update={"provenance": provenance})
    units = [units[0].model_copy(update={"content": content, "provenance": provenance})]
    result = understand_content(SCOPE, units, lambda _prompt: json.dumps(body))
    names = {c.name for c in result.snapshot.concepts}
    assert {"Water", "Cell membrane", "Cell"} <= names
    assert all(c.definition is None for c in result.snapshot.concepts if c.name != "Osmosis")
    assert not result.snapshot.relationships
