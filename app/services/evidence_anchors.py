"""Scope-bound mechanical evidence references; models never calculate canonical offsets."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field
from .knowledge_models import Contract, Identifier, ScopedContentUnit
from .security.source_scope import SourceScope
from .content_understanding import (
    StructureProposal,
    UnderstandingError,
    TopicProposal,
    SubtopicProposal,
    ConceptProposal,
    RelationshipProposal,
    EvidenceProposal,
)

ANCHOR_POLICY_VERSION = "evidence-sentences-v1"
MAX_ANCHORS = 4096
MAX_ANCHOR_CHARACTERS = 16384


class EvidenceAnchor(Contract):
    anchor_id: Identifier
    content_id: Identifier
    char_start: int
    char_end: int
    text: Annotated[str, Field(min_length=1, max_length=MAX_ANCHOR_CHARACTERS)]


class AnchorReference(Contract):
    anchor_id: Identifier


AnchorEvidence = Annotated[list[AnchorReference], Field(min_length=1, max_length=64)]


class AnchoredTopic(Contract):
    key: Identifier
    title: Annotated[str, Field(min_length=2, max_length=120)]
    evidence: AnchorEvidence


class AnchoredSubtopic(AnchoredTopic):
    topic_key: Identifier


class AnchoredConcept(Contract):
    key: Identifier
    subtopic_key: Identifier
    name: Annotated[str, Field(min_length=2, max_length=120)]
    definition: Annotated[str, Field(min_length=1, max_length=16384)] | None = None
    evidence: AnchorEvidence


class AnchoredRelationship(Contract):
    dependent_key: Identifier = Field(
        description="Exact temporary concept.key of the concept that depends on another, e.g. c2; never a name or subtopic key"
    )
    prerequisite_key: Identifier = Field(
        description="Exact temporary concept.key of the required concept, e.g. c1; never a name or subtopic key"
    )
    evidence: AnchorEvidence


class AnchoredStructureProposal(Contract):
    topics: Annotated[list[AnchoredTopic], Field(min_length=1, max_length=128)]
    subtopics: Annotated[list[AnchoredSubtopic], Field(min_length=1, max_length=512)]
    concepts: Annotated[list[AnchoredConcept], Field(min_length=1, max_length=1024)]
    prerequisites: Annotated[list[AnchoredRelationship], Field(max_length=4096)]


def build_anchors(
    scope: SourceScope, units: list[ScopedContentUnit]
) -> list[EvidenceAnchor]:
    """Sentence anchors preserve headings and exact characters; oversized spans are bounded."""
    if (
        not units
        or len({u.content_id for u in units}) != len(units)
        or any(
            (u.user_id, u.source_id, u.source_version)
            != (scope.user_id, scope.source_id, scope.source_version)
            for u in units
        )
    ):
        raise UnderstandingError("NO_SAFE_CONTENT")
    result: list[EvidenceAnchor] = []
    for unit in units:
        text = unit.content.text
        for match in re.finditer(r"\S[\s\S]*?(?:[.!?](?=\s|$)|$)", text):
            for start in range(match.start(), match.end(), MAX_ANCHOR_CHARACTERS):
                end = min(start + MAX_ANCHOR_CHARACTERS, match.end())
                piece = text[start:end]
                identity = f"{scope.user_id}:{scope.source_id}:{scope.source_version}:{unit.content_id}:{start}:{end}:{piece}:{ANCHOR_POLICY_VERSION}"
                result.append(
                    EvidenceAnchor(
                        anchor_id="EA_" + uuid5(NAMESPACE_URL, identity).hex,
                        content_id=unit.content_id,
                        char_start=start,
                        char_end=end,
                        text=piece,
                    )
                )
                if len(result) > MAX_ANCHORS:
                    raise UnderstandingError("SOURCE_TOO_LARGE")
    if not result:
        raise UnderstandingError("NO_SAFE_CONTENT")
    return result


def resolve_proposal(
    scope: SourceScope,
    units: list[ScopedContentUnit],
    proposal: AnchoredStructureProposal,
) -> StructureProposal:
    """Resolve only freshly regenerated scope-bound anchors; no caller-controlled span table."""
    from .educational_chunker import classify_content_role

    anchors = {a.anchor_id: a for a in build_anchors(scope, units)}
    content = {u.content_id: u.content.text for u in units}

    def evidence(refs: list[AnchorReference]) -> list[EvidenceProposal]:
        if len({r.anchor_id for r in refs}) != len(refs):
            raise UnderstandingError("DUPLICATE_IDENTITY")
        values: list[EvidenceProposal] = []
        for ref in refs:
            anchor = anchors.get(ref.anchor_id)
            if anchor is None:
                raise UnderstandingError("UNSUPPORTED_EVIDENCE", "REFERENCE")
            values.append(
                EvidenceProposal(
                    content_id=anchor.content_id,
                    quote=anchor.text,
                    char_start=anchor.char_start,
                    char_end=anchor.char_end,
                    role=classify_content_role(anchor.text),
                )
            )
        # The deployed association key permits one span per content/concept/support kind.
        # Adjacent selected sentences of the same role form one exact canonical span.
        ordered = sorted(values, key=lambda e: (e.content_id, e.char_start or 0))
        merged: list[EvidenceProposal] = []
        for item in ordered:
            prior = merged[-1] if merged else None
            if (
                prior is not None
                and prior.content_id == item.content_id
                and prior.role == item.role
                and prior.char_end is not None
                and item.char_start is not None
                and item.char_start >= prior.char_end
                and not content[item.content_id][
                    prior.char_end : item.char_start
                ].strip()
            ):
                assert prior.char_start is not None and item.char_end is not None
                merged[-1] = EvidenceProposal(
                    content_id=item.content_id,
                    char_start=prior.char_start,
                    char_end=item.char_end,
                    quote=content[item.content_id][prior.char_start : item.char_end],
                    role=item.role,
                )
            else:
                merged.append(item)
        return merged

    return StructureProposal(
        topics=[
            TopicProposal(key=t.key, title=t.title, evidence=evidence(t.evidence))
            for t in proposal.topics
        ],
        subtopics=[
            SubtopicProposal(
                key=s.key,
                title=s.title,
                topic_key=s.topic_key,
                evidence=evidence(s.evidence),
            )
            for s in proposal.subtopics
        ],
        concepts=[
            ConceptProposal(
                key=c.key,
                subtopic_key=c.subtopic_key,
                name=c.name,
                definition=c.definition,
                evidence=evidence(c.evidence),
            )
            for c in proposal.concepts
        ],
        prerequisites=[
            RelationshipProposal(
                dependent_key=r.dependent_key,
                prerequisite_key=r.prerequisite_key,
                evidence=evidence(r.evidence),
            )
            for r in proposal.prerequisites
        ],
    )
