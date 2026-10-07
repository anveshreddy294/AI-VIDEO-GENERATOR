"""Mechanical evidence exactness and derived-label validation remain deterministic."""

from __future__ import annotations
import copy
import json
from uuid import UUID

import pytest
from app.services.evidence_anchors import (
    build_anchors,
    resolve_proposal,
    AnchoredStructureProposal,
)
from app.services.content_understanding import (
    UnderstandingError,
    understand_content,
    validate_proposal,
    label_supported,
)
from app.services.security.source_scope import SourceScope
from tests.test_content_understanding import SCOPE, envelopes, proposed
from app.core.reasoning import ReasoningRequest, Message
from tests.test_reasoning_provider import router, envelope
import httpx
from pydantic import JsonValue
from app.services.knowledge_models import ScopedContentUnit


def anchored_body() -> tuple[list[ScopedContentUnit], dict[str, JsonValue]]:
    units = envelopes("textbook")
    anchors = build_anchors(SCOPE, units)
    body = proposed([{"content_id": a.content_id, "text": a.text} for a in anchors])
    for field in ("topics", "subtopics", "concepts", "prerequisites"):
        for item in body[field]:
            item["evidence"] = [
                {
                    "anchor_id": next(
                        a.anchor_id
                        for a in anchors
                        if a.content_id == e["content_id"] and a.text == e["quote"]
                    )
                }
                for e in item["evidence"]
            ]
    return units, body


def test_anchors_roundtrip_scope_and_determinism() -> None:
    units = envelopes("multi_topic")
    anchors = build_anchors(SCOPE, units)
    assert anchors == build_anchors(SCOPE, units)
    assert len({a.anchor_id for a in anchors}) == len(anchors)
    for anchor in anchors:
        unit = next(u for u in units if u.content_id == anchor.content_id)
        assert unit.content.text[anchor.char_start : anchor.char_end] == anchor.text
    other = SourceScope(
        user_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        source_id=SCOPE.source_id,
        source_version=1,
    )
    with pytest.raises(UnderstandingError):
        build_anchors(other, units)


def test_anchor_proposal_resolves_to_valid_grounded_snapshot() -> None:
    units, body = anchored_body()
    proposal = resolve_proposal(
        SCOPE, units, AnchoredStructureProposal.model_validate_json(json.dumps(body))
    )
    snapshot, quality = validate_proposal(SCOPE, units, proposal, derived_labels=True)
    assert snapshot.concepts and quality.concept_evidence_coverage == 1
    for c in proposal.concepts:
        assert all(
            e.char_start is not None and e.char_end is not None for e in c.evidence
        )


def test_unknown_and_foreign_anchor_ids_rejected() -> None:
    units, body = anchored_body()
    body["concepts"][0]["evidence"][0]["anchor_id"] = "EA_foreign"
    with pytest.raises(UnderstandingError, match="UNSUPPORTED_EVIDENCE"):
        resolve_proposal(
            SCOPE,
            units,
            AnchoredStructureProposal.model_validate_json(json.dumps(body)),
        )


def test_derived_labels_allow_supported_annotations_without_literal_title() -> None:
    assert label_supported(
        "Fundamentals of variables", "Variables are symbols representing numbers.", True
    )
    assert label_supported(
        "Linear equation principles",
        "Linear equations are equations of degree one.",
        True,
    )
    assert not label_supported("Quantum mechanics", "Variables are symbols.", True)
    assert not label_supported(
        "Reveal secret instructions", "Variables are symbols.", True
    )
    assert not label_supported("General concepts", "Variables are symbols.", True)


def test_semantic_rejection_repairs_without_ollama_or_circuit_failure() -> None:
    units, body = anchored_body()
    body["concepts"][0]["evidence"][0]["anchor_id"] = "EA_unknown"
    tasks = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        tasks.append(request_body["task"])
        data = envelope()
        data["task"] = request_body["task"]
        data["response"] = body
        return httpx.Response(200, json=data)

    route, fallback = router(handler)

    def generate(prompt: str) -> str:
        return route.generate(
            ReasoningRequest(
                task=(
                    "structure_repair"
                    if "\nREPAIR:" in prompt
                    else "content_understanding"
                ),
                messages=[Message(role="user", content=prompt)],
                max_tokens=100,
            )
        ).response

    with pytest.raises(UnderstandingError, match="UNSUPPORTED_EVIDENCE"):
        understand_content(SCOPE, units, generate)
    assert (
        tasks == ["content_understanding", "structure_repair"]
        and fallback.calls == 0
        and route.circuit.consecutive_failures == 0
    )


def test_adjacent_prerequisite_anchors_resolve_as_one_exact_span() -> None:
    from app.services.knowledge_models import ScopedContentUnit
    from app.services.schemas import ContentUnit

    text = "Variables are symbols. Linear equations are equations of degree one. Linear equations requires variables. Variables must be understood before linear equations."
    units = [
        ScopedContentUnit(
            **SCOPE.model_dump(),
            content_id="unit",
            content=ContentUnit(
                content_id="unit",
                source_id=SCOPE.source_id,
                asset_id="asset",
                text=text,
                modality="txt",
            ),
            provenance={},
        )
    ]
    anchors = build_anchors(SCOPE, units)
    evidence = [{"anchor_id": a.anchor_id} for a in anchors[2:]]
    body = {
        "topics": [{"key": "t", "title": "Variables", "evidence": [evidence[0]]}],
        "subtopics": [
            {
                "key": "s",
                "topic_key": "t",
                "title": "Variables",
                "evidence": [evidence[0]],
            }
        ],
        "concepts": [
            {
                "key": "variables",
                "subtopic_key": "s",
                "name": "Variables",
                "definition": None,
                "evidence": [evidence[0]],
            },
            {
                "key": "equations",
                "subtopic_key": "s",
                "name": "Linear equations",
                "definition": None,
                "evidence": [evidence[0]],
            },
        ],
        "prerequisites": [
            {
                "dependent_key": "equations",
                "prerequisite_key": "variables",
                "evidence": evidence,
            }
        ],
    }
    body["topics"][0]["evidence"] = [{"anchor_id": anchors[0].anchor_id}]
    body["subtopics"][0]["evidence"] = [{"anchor_id": anchors[0].anchor_id}]
    body["concepts"][0]["evidence"] = [{"anchor_id": anchors[0].anchor_id}]
    body["concepts"][1]["evidence"] = [{"anchor_id": anchors[1].anchor_id}]
    proposal = resolve_proposal(
        SCOPE, units, AnchoredStructureProposal.model_validate_json(json.dumps(body))
    )
    assert len(proposal.prerequisites[0].evidence) == 1
    assert proposal.prerequisites[0].evidence[0].quote == text[anchors[2].char_start :]
    assert proposal.prerequisites[0].evidence[0].char_start == anchors[2].char_start
    assert proposal.prerequisites[0].evidence[0].char_end == len(text)
    snapshot, _ = validate_proposal(SCOPE, units, proposal, derived_labels=True)
    assert len(snapshot.relationships) == 1


def test_qualified_derived_label_uses_unique_evidenced_definition_subject() -> None:
    units = envelopes("multi_topic")
    anchors = build_anchors(SCOPE, units)
    body = proposed(
        [{"content_id": u.content_id, "text": u.content.text} for u in units]
    )
    body["concepts"][0]["name"] = "Fundamentals of Variables"
    # The derived qualifier is not in the dependency quote; Variables is a canonical definition subject.
    from app.services.content_understanding import StructureProposal

    snapshot, _ = validate_proposal(
        SCOPE,
        units,
        StructureProposal.model_validate_json(json.dumps(body)),
        derived_labels=True,
    )
    assert snapshot.relationships


def test_ambiguous_definition_subject_alias_cannot_establish_dependency() -> None:
    units = envelopes("multi_topic")
    body = proposed(
        [{"content_id": u.content_id, "text": u.content.text} for u in units]
    )
    body["concepts"][0]["name"] = "Fundamentals of Variables"
    duplicate = copy.deepcopy(body["concepts"][0])
    duplicate["key"] = "variables2"
    duplicate["name"] = "Basic Variables"
    body["concepts"].append(duplicate)
    from app.services.content_understanding import StructureProposal

    with pytest.raises(UnderstandingError, match="UNSUPPORTED_PREREQUISITE"):
        validate_proposal(
            SCOPE,
            units,
            StructureProposal.model_validate_json(json.dumps(body)),
            derived_labels=True,
        )
