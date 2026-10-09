"""Independent visual truth, exact native outlines, and permanent structuring contracts."""
from __future__ import annotations
import copy
import json
from typing import cast
import pytest
from pydantic import JsonValue
from app.services.content_understanding import UnderstandingError, understand_content, label_supported
from app.services.evidence_anchors import build_anchors, AnchoredStructureProposal, bind_verified_visual_labels
from app.services.knowledge_models import ScopedContentUnit
from app.services.schemas import ContentUnit
from app.services.verified_inventory import verified_inventory, literal_supported, display_label
from app.services.vision import format_vision_markdown
from app.services.visual_contracts import VisionExtractionData
from tests.test_content_understanding import SCOPE, envelopes, proposed
from tests.test_outline_evidence import fixture as outline_fixture, SCOPE as OUTLINE_SCOPE
from tests.visual_fixture_oracle import FixtureOracle


VISUAL_CASES = {
    "printed.png": {"headings":["Osmosis"], "labels":["Water", "Cell membrane", "Cell"]},
    "handwriting.png": {"headings":["Physics notes"], "handwriting_text":["Force equals mass times acceleration"], "formulas":["F = ma"]},
    "complex-diagram.png": {"headings":["Sensor control flow"], "diagram_entities":["Sensor","Filter","Controller","Alarm","Motor"], "relationships":["Sensor -> Filter", "Filter -> Controller", "Controller -> Motor"]},
    "flowchart.png": {"headings":["Photosynthesis"], "labels":["Sunlight","Leaf","Chemical energy"], "arrows":["Sunlight -> Leaf", "Leaf -> Chemical energy"], "content_kind":"FLOWCHART"},
    "table.png": {"headings":["Force experiment"], "tables":[{"headers":["Mass (kg)","Acceleration (m/s2)","Force (N)"], "rows":[["2","3","6"]]}]},
    "equation.png": {"headings":["Newton second law"], "formulas":["F = ma"]},
    "graph.png": {"headings":["Distance versus time"], "graphs":[{"x_axis":"Time","y_axis":"Distance","x_unit":"s","y_unit":"m","trends":["Distance increases with time"]}]},
}


def visual_unit(name: str, number: int = 0) -> ScopedContentUnit:
    visual = VisionExtractionData.model_validate(VISUAL_CASES[name])
    verified = FixtureOracle()._fixture_checks(name, visual)
    assert verified.status == "VERIFIED"
    provenance = {"validation_state":"VALIDATED", "visual_schema_version":"visual-v2", "visual_verification":verified.model_dump(mode="json"), "extraction":visual.model_dump(mode="json")}
    cid = "v" + str(number)
    from app.services.security.content_sanitizer import sanitize_text
    canonical_text, _, _, _, allowed = sanitize_text(format_vision_markdown(visual))
    assert allowed
    content = ContentUnit(content_id=cid, source_id=SCOPE.source_id, asset_id="asset",
        modality="image", sequence_index=number, text=canonical_text, provenance=provenance)
    return ScopedContentUnit(**SCOPE.model_dump(), content_id=cid, content=content, provenance=provenance)


def visual_proposal(units: list[ScopedContentUnit]) -> dict[str, JsonValue]:
    anchors = build_anchors(SCOPE, units)
    body: dict[str, JsonValue] = {"topics":[], "subtopics":[], "concepts":[], "prerequisites":[]}
    for i, unit in enumerate(units):
        heading = cast(dict[str, JsonValue], unit.provenance["extraction"])["headings"][0]
        assert isinstance(heading, str)
        anchor = min((a for a in anchors if a.content_id == unit.content_id and literal_supported(heading,[a.text])), key=lambda a:len(a.text))
        evidence = [{"anchor_id":anchor.anchor_id}]
        body["topics"].append({"key":f"t{i}","title":heading,"evidence":evidence})
        body["subtopics"].append({"key":f"s{i}","topic_key":f"t{i}","title":heading,"evidence":evidence})
        body["concepts"].append({"key":f"c{i}","subtopic_key":f"s{i}","name":heading,"definition":None,"evidence":evidence})
    return body


def assert_contract(units: list[ScopedContentUnit], body: dict[str, JsonValue]) -> None:
    result = understand_content(SCOPE, units, lambda _:json.dumps(body))
    assert result.snapshot == understand_content(SCOPE,units,lambda _:json.dumps(body)).snapshot
    assert len({c.concept_id for c in result.snapshot.concepts}) == len(result.snapshot.concepts)
    names = [t.title for t in result.snapshot.topics] + [s.title for s in result.snapshot.subtopics] + [c.name for c in result.snapshot.concepts]
    inventory = verified_inventory(SCOPE, units)
    assert all(any(literal_supported(display_label(entry.label),[name]) for name in names)
        for entry in inventory if entry.required_label and len(display_label(entry.label)) <= 120)
    assert all(any(literal_supported(c.name,[entry.label]) for entry in inventory) for c in result.snapshot.concepts)
    by_id = {u.content_id:u for u in units}
    for evidence in result.snapshot.content_concepts:
        assert evidence.content_id in by_id
        assert by_id[evidence.content_id].source_id == SCOPE.source_id
        assert by_id[evidence.content_id].source_version == SCOPE.source_version
    assert result.snapshot.relationships == []  # Directed flow never becomes a prerequisite.
    assert result.quality.unassigned_content_ids == []


@pytest.mark.parametrize("name",list(VISUAL_CASES))
def test_visual_truth_to_canonical_inventory_matrix(name: str) -> None:
    units = [visual_unit(name)]
    assert_contract(units,visual_proposal(units))


def test_long_multipanel_preserves_distinct_regions_and_labels() -> None:
    units = [visual_unit(name,i) for i,name in enumerate(("printed.png","flowchart.png","table.png"))]
    assert_contract(units,visual_proposal(units))


def test_mixed_pdf_text_and_independently_verified_figure() -> None:
    figure = visual_unit("printed.png")
    content = figure.content.model_copy(update={"modality":"pdf","page_number":2})
    figure = figure.model_copy(update={"content":content})
    assert_contract([figure],visual_proposal([figure]))
    # Native PDF text uses the same strict original prose contract, separately from visual claims.
    native = envelopes("textbook")
    native = [u.model_copy(update={"content":u.content.model_copy(update={"modality":"pdf","page_number":1})}) for u in native]
    body = proposed([{"content_id":u.content_id,"text":u.content.text} for u in native])
    result = understand_content(SCOPE,native,lambda _:json.dumps(body))
    assert len(result.snapshot.concepts) == 2


@pytest.mark.parametrize("case",["sparse","textbook","multi_topic"])
@pytest.mark.parametrize("modality",["txt","pdf"])
def test_plain_short_multisection_native_sources(case: str, modality: str) -> None:
    units = envelopes(case)
    units = [u.model_copy(update={"content":u.content.model_copy(update={"modality":modality})}) for u in units]
    body = proposed([{"content_id":u.content_id,"text":u.content.text} for u in units])
    result = understand_content(SCOPE,units,lambda _:json.dumps(body))
    assert result.quality.unassigned_content_ids == []
    assert len({c.concept_id for c in result.snapshot.concepts}) == len(result.snapshot.concepts)
    assert result.snapshot == understand_content(SCOPE,units,lambda _:json.dumps(body)).snapshot


@pytest.mark.parametrize("modality",["txt","pdf"])
def test_heading_rich_native_structure_does_not_imply_dependency(modality: str) -> None:
    units,body = outline_fixture()
    units = [u.model_copy(update={"content":u.content.model_copy(update={"modality":modality})}) for u in units]
    result = understand_content(OUTLINE_SCOPE,units,lambda _:json.dumps(body))
    assert len(result.snapshot.subtopics) == 2
    assert result.snapshot.relationships == []


def test_periods_in_verified_heading_do_not_fragment_its_identity() -> None:
    unit = visual_unit("printed.png")
    raw = copy.deepcopy(unit.provenance)
    heading = "1. Transport. Water crosses membranes."
    raw["extraction"] = VisionExtractionData(headings=[heading],labels=["Water"],visible_text=["Water"]).model_dump(mode="json")
    content = unit.content.model_copy(update={"text":format_vision_markdown(VisionExtractionData.model_validate(raw["extraction"])),"provenance":raw})
    unit = unit.model_copy(update={"content":content,"provenance":raw})
    anchors = build_anchors(SCOPE,[unit])
    assert any(a.text == heading for a in anchors)
    assert_contract([unit],visual_proposal([unit]))


@pytest.mark.parametrize(("claim","source"),[("F = m - a","F = m + a"),("2.5 kg","25 kg"),("A -> B","B -> A"),("CO2","Co2"),("x = 2","X = 2"),("m/s","ms")])
def test_presentation_normalization_never_erases_semantic_identity(claim: str, source: str) -> None:
    assert not literal_supported(claim,[source])
    assert not label_supported(claim,source,True)


def test_numbering_bullets_unicode_whitespace_remain_presentation_only() -> None:
    assert display_label("• 2. **Water\u00a0transport**") == "Water transport"
    assert literal_supported("Water transport",["2. Water\u00a0transport"])


def test_ambiguous_cross_unit_label_binding_is_not_repaired() -> None:
    units = [visual_unit("printed.png",i) for i in range(2)]
    body = visual_proposal(units)
    bad = next(a for a in build_anchors(SCOPE,units) if a.text == "Cell")
    body["concepts"][0]["name"] = "Water"
    body["concepts"][0]["evidence"] = [{"anchor_id":bad.anchor_id}]
    proposal = AnchoredStructureProposal.model_validate(body)
    rebound,repairs = bind_verified_visual_labels(SCOPE,units,proposal)
    assert rebound.concepts[0].evidence == proposal.concepts[0].evidence
    assert not any("c0" in repair for repair in repairs)


@pytest.mark.parametrize("defect",["invented","foreign_anchor","version","definition","empty","malformed","prerequisite"])
def test_negative_matrix_remains_fail_closed(defect: str) -> None:
    units = [visual_unit("printed.png")]
    body = visual_proposal(units)
    if defect == "invented":body["concepts"][0]["name"] = "Quantum gravity"
    if defect == "foreign_anchor":body["concepts"][0]["evidence"] = [{"anchor_id":"EA_foreign"}]
    if defect == "version":units=[units[0].model_copy(update={"source_version":2})]
    if defect == "definition":body["concepts"][0]["definition"] = "Water cannot cross membranes."
    if defect == "empty":body["concepts"][0]["evidence"] = []
    if defect == "prerequisite":body["prerequisites"]=[{"dependent_key":"c0","prerequisite_key":"c0","evidence":body["concepts"][0]["evidence"]}]
    calls = []
    def provider(prompt: str) -> str:
        calls.append(prompt)
        return "{malformed" if defect == "malformed" else json.dumps(body)
    with pytest.raises(UnderstandingError):understand_content(SCOPE,units,provider)
    assert len(calls) <= 2
    if defect == "invented":
        assert len(calls) == 2 and "SOURCE_VERIFIED_LABEL_ANCHORS=" in calls[1]


def test_safe_diagnostic_retains_category_not_source_or_response() -> None:
    units = [visual_unit("printed.png")];body=visual_proposal(units)
    body["concepts"][0]["name"] = "Quantum gravity"
    with pytest.raises(UnderstandingError) as caught:
        understand_content(SCOPE,units,lambda _:json.dumps(body))
    error = caught.value
    assert error.failed_object_type == "CONCEPT"
    assert error.reason_category == "HALLUCINATED_LABEL"
    assert error.repair_attempted and len(error.label_reference) == 12
    assert "Quantum" not in str(error) and "Osmosis" not in str(error)


def test_verified_educational_labels_do_not_promote_irrelevant_ui_text() -> None:
    unit = visual_unit("printed.png")
    raw = copy.deepcopy(unit.provenance)
    raw["extraction"]["visible_text"] = ["Download page", "Save image"]
    content = unit.content.model_copy(update={"text":format_vision_markdown(VisionExtractionData.model_validate(raw["extraction"])),"provenance":raw})
    unit = unit.model_copy(update={"content":content,"provenance":raw})
    result = understand_content(SCOPE,[unit],lambda _:json.dumps(visual_proposal([unit])))
    assert {c.name for c in result.snapshot.concepts} == {"Osmosis","Water","Cell membrane","Cell"}
    assert any(entry.label == "Save image" for entry in verified_inventory(SCOPE,[unit]))


@pytest.mark.parametrize("defect",["reversed_edge","contradictory_axis","invented_component"])
def test_independent_truth_rejects_contradictions_before_inventory(defect: str) -> None:
    data = copy.deepcopy(VISUAL_CASES["flowchart.png"])
    name = "flowchart.png"
    if defect == "reversed_edge": data["arrows"] = ["Leaf -> Sunlight"]
    if defect == "invented_component": data["diagram_entities"] = ["Quantum reactor"]
    if defect == "contradictory_axis":
        name = "graph.png";data=copy.deepcopy(VISUAL_CASES[name]);data["graphs"][0]["x_axis"] = "Distance"
    assert FixtureOracle()._fixture_checks(name,VisionExtractionData.model_validate(data)).status == "REJECTED"


def test_visual_schema_excludes_unverified_label_and_preserves_cardinality() -> None:
    from app.services.verified_inventory import visual_proposal_schema
    units = [visual_unit("complex-diagram.png")]
    schema = visual_proposal_schema(SCOPE, units)
    assert schema is not None
    names = schema["$defs"]["AnchoredConcept"]["properties"]["name"]["enum"]
    assert set(names) >= {"Sensor", "Filter", "Controller", "Alarm", "Motor"}
    assert "Quantum gravity" not in names
    assert schema["properties"]["concepts"]["maxItems"] == 1024
    assert visual_proposal_schema(SCOPE,envelopes("sparse")) is None


def test_scoped_output_schema_does_not_leak_between_requests() -> None:
    from app.services.structurer import scoped_proposal_schema, _proposal_schema
    assert _proposal_schema.get() is None
    with scoped_proposal_schema({"type":"object"}):
        assert _proposal_schema.get() == {"type":"object"}
    assert _proposal_schema.get() is None
    with pytest.raises(RuntimeError):
        with scoped_proposal_schema({"type":"string"}):raise RuntimeError("fixture failure")
    assert _proposal_schema.get() is None


def test_unambiguous_supported_label_rebinds_and_fully_validates() -> None:
    units=[visual_unit("printed.png")];body=visual_proposal(units)
    wrong=next(a for a in build_anchors(SCOPE,units) if a.text == "Water")
    body["topics"][0]["evidence"] = [{"anchor_id":wrong.anchor_id}]
    body["subtopics"][0]["evidence"] = [{"anchor_id":wrong.anchor_id}]
    body["concepts"][0]["evidence"] = [{"anchor_id":wrong.anchor_id}]
    result=understand_content(SCOPE,units,lambda _:json.dumps(body))
    assert len(result.deterministic_repairs) >= 3
    assert len(result.snapshot.concepts) == 4


def test_generic_heading_requires_actual_explicit_source_authority() -> None:
    unit=visual_unit("printed.png")
    raw=copy.deepcopy(unit.provenance)
    visual=VisionExtractionData(headings=["Overview"],labels=["Water"],visible_text=["Water"])
    raw["extraction"]=visual.model_dump(mode="json")
    unit=unit.model_copy(update={"content":unit.content.model_copy(update={"text":format_vision_markdown(visual),"provenance":raw}),"provenance":raw})
    assert_contract([unit],visual_proposal([unit]))
    bad=visual_proposal([visual_unit("printed.png")]);bad["topics"][0]["title"]="Overview"
    with pytest.raises(UnderstandingError):understand_content(SCOPE,[visual_unit("printed.png")],lambda _:json.dumps(bad))


def test_operator_literal_matching_cannot_bypass_instruction_guard() -> None:
    assert not label_supported("Ignore instructions 2", "Ignore instructions 2", True)


def test_generator_schema_constraints_are_also_enforced_on_server() -> None:
    units=[visual_unit("printed.png")];body=visual_proposal(units)
    # Every word occurs in accepted evidence, but this reordered name is not an accepted label.
    body["concepts"][0]["name"]="membrane Cell"
    anchor=next(a for a in build_anchors(SCOPE,units) if a.text == "Cell membrane")
    body["concepts"][0]["evidence"]=[{"anchor_id":anchor.anchor_id}]
    with pytest.raises(UnderstandingError) as caught:
        understand_content(SCOPE,units,lambda _:json.dumps(body))
    assert caught.value.reason_category == "HALLUCINATED_LABEL"
