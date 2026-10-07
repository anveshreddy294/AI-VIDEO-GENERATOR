"""Visible fixture graphs qualify exact directed structure, not word similarity."""

from __future__ import annotations
import copy
import json
from pathlib import Path
import pytest
from pydantic import JsonValue
from scripts.benchmark_visual_models import score_fixture

FLOW: dict[str, JsonValue] = {
    "visible_text": ["Photosynthesis", "Sunlight -> Leaf -> Chemical energy"],
    "diagram_entities": [
        "Sunlight",
        "Leaf",
        "Chemical energy",
        "left empty box",
        "right empty box",
    ],
    "relationships": [
        "Sunlight -> Leaf",
        "Leaf -> Chemical energy",
        "left empty box -> right empty box",
    ],
    "confidence": 0.9,
    "content_kind": "FLOWCHART",
}
COMPLEX: dict[str, JsonValue] = {
    "visible_text": [
        "Sensor control flow",
        "Sensor",
        "Filter",
        "Controller",
        "Alarm",
        "Motor",
    ],
    "diagram_entities": ["Sensor", "Filter", "Controller", "Alarm", "Motor"],
    "relationships": [
        "Sensor -> Filter",
        "Filter -> Controller",
        "Filter -> Alarm",
        "Controller -> Motor",
        "Motor -> Sensor",
    ],
    "confidence": 0.9,
    "content_kind": "DIAGRAM",
}


@pytest.mark.parametrize(
    "name,data", [("flowchart.png", FLOW), ("complex-diagram.png", COMPLEX)]
)
def test_exact_fixture_structure_passes(name: str, data: dict[str, JsonValue]) -> None:
    r = score_fixture(name, data)
    assert r["fixture_score"] == 1 and r["unsupported_claims_flagged"] is False


@pytest.mark.parametrize(
    "edges",
    [
        ["Leaf -> Sunlight", "Leaf -> Chemical energy", "left box -> right box"],
        ["Sunlight -> Chemical energy", "left box -> right box"],
        ["Sunlight -> Leaf", "Leaf -> Chemical energy", "right box -> left box"],
        [
            "Sunlight -> Leaf",
            "Leaf -> Chemical energy",
            "left box -> right box",
            "Leaf -> Oxygen",
        ],
    ],
)
def test_wrong_or_invented_flow_relationships_fail(edges: list[str]) -> None:
    data = copy.deepcopy(FLOW)
    data["relationships"] = edges
    assert score_fixture("flowchart.png", data)["fixture_score"] < 1


@pytest.mark.parametrize(
    "entity", ["Oxygen", "Chlorophyll", "Sunlight/Leaf", "third box"]
)
def test_invented_or_merged_nodes_fail(entity: str) -> None:
    data = copy.deepcopy(FLOW)
    data["diagram_entities"] = [
        "Sunlight",
        "Leaf",
        "Chemical energy",
        "left box",
        "right box",
        entity,
    ]
    assert score_fixture("flowchart.png", data)["fixture_score"] < 1


@pytest.mark.parametrize(
    "removed", ["Filter -> Alarm", "Motor -> Sensor", "Sensor -> Filter"]
)
def test_complex_missing_branches_or_feedback_fail(removed: str) -> None:
    data = copy.deepcopy(COMPLEX)
    data["relationships"] = [r for r in COMPLEX["relationships"] if r != removed]
    assert score_fixture("complex-diagram.png", data)["fixture_score"] < 1


def test_old_provider_flowcharts_are_structurally_supported() -> None:
    p = Path(__file__).parents[1] / "docs/phase7a3b_canonical_benchmark.json"
    for row in json.loads(p.read_text())["records"]:
        if row["fixture"] == "flowchart.png":
            r = score_fixture("flowchart.png", row["fixture_output"])
            assert r["fixture_score"] == 1 and r["unsupported_claims_flagged"] is False


def test_written_arrow_sequence_is_directed_evidence_without_duplicate_relationship() -> (
    None
):
    data = copy.deepcopy(FLOW)
    data["relationships"] = ["left box -> right box"]
    assert score_fixture("flowchart.png", data)["fixture_score"] == 1


def test_word_presence_cannot_invent_written_edges() -> None:
    data = copy.deepcopy(FLOW)
    data["visible_text"] = ["Photosynthesis", "Sunlight Leaf Chemical energy"]
    data["relationships"] = ["left box -> right box"]
    assert score_fixture("flowchart.png", data)["fixture_score"] < 1


def test_other_fixture_labels_do_not_become_permitted_flowchart_vocabulary() -> None:
    data = copy.deepcopy(FLOW)
    data["visible_text"] = [
        "Photosynthesis",
        "Sunlight -> Leaf -> Chemical energy",
        "Sensor",
    ]
    assert score_fixture("flowchart.png", data)["unsupported_claims_flagged"] is True


@pytest.mark.parametrize(
    "left,right",
    [
        ("unlabeled box left", "unlabeled box right"),
        ("left empty box", "right empty box"),
    ],
)
def test_positional_empty_box_descriptions_normalize_exactly(
    left: str, right: str
) -> None:
    data = copy.deepcopy(FLOW)
    data["diagram_entities"] = [left, right]
    data["relationships"] = [left + " -> " + right]
    assert score_fixture("flowchart.png", data)["fixture_score"] == 1
    data["relationships"] = [right + " -> " + left]
    assert score_fixture("flowchart.png", data)["fixture_score"] < 1


def test_component_shape_prefix_does_not_allow_wrong_feedback_direction() -> None:
    data = copy.deepcopy(COMPLEX)
    data["diagram_entities"] = [
        "box_Sensor",
        "box_Filter",
        "box_Controller",
        "box_Alarm",
        "box_Motor",
    ]
    assert score_fixture("complex-diagram.png", data)["fixture_score"] == 1
    data["relationships"] = [
        "Sensor -> Filter",
        "Filter -> Controller",
        "Filter -> Alarm",
        "Controller -> Motor",
        "Sensor -> Motor",
    ]
    assert score_fixture("complex-diagram.png", data)["fixture_score"] < 1


def test_arrowhead_geometry_determines_direction_without_following_line_order() -> None:
    from scripts.visual_structure_ground_truth import relationship, COMPLEX as TRUTH

    description = "diagonal line from top of Sensor to bottom of Motor with arrowhead at top of Sensor"
    assert relationship(description, TRUTH) == [("motor", "sensor")]
    assert (
        relationship(
            description.replace(
                "arrowhead at top of Sensor", "arrowhead at top of Filter"
            ),
            TRUTH,
        )
        is None
    )
    data = copy.deepcopy(COMPLEX)
    data["arrows"] = [
        description.replace("arrowhead at top of Sensor", "arrowhead at top of Motor")
    ]
    assert score_fixture("complex-diagram.png", data)["fixture_score"] < 1
