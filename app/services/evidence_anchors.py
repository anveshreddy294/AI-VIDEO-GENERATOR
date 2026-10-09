"""Scope-bound mechanical evidence references; models never calculate canonical offsets."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator
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


from typing import Literal

AnchorEvidence = Annotated[list[AnchorReference], Field(max_length=64)]


class AnchoredTopic(Contract):
    key: Identifier
    title: Annotated[str, Field(min_length=2, max_length=120)]
    evidence: AnchorEvidence = Field(default_factory=list)
    provenance_kind: Literal["SOURCE_GROUNDED", "AI_ENRICHED"] = "SOURCE_GROUNDED"

    @model_validator(mode="after")
    def require_evidence_if_source_grounded(self) -> AnchoredTopic:
        if self.provenance_kind == "SOURCE_GROUNDED" and not self.evidence:
            raise ValueError("SOURCE_GROUNDED topics must cite at least one evidence anchor")
        return self


class AnchoredSubtopic(AnchoredTopic):
    topic_key: Identifier


class AnchoredConcept(Contract):
    key: Identifier
    subtopic_key: Identifier
    name: Annotated[str, Field(min_length=2, max_length=120)]
    definition: Annotated[str, Field(min_length=1, max_length=16384)] | None = None
    evidence: AnchorEvidence = Field(default_factory=list)
    provenance_kind: Literal["SOURCE_GROUNDED", "AI_ENRICHED"] = "SOURCE_GROUNDED"

    @model_validator(mode="after")
    def require_evidence_if_source_grounded(self) -> AnchoredConcept:
        if self.provenance_kind == "SOURCE_GROUNDED" and not self.evidence:
            raise ValueError("SOURCE_GROUNDED concepts must cite at least one evidence anchor")
        return self


class AnchoredRelationship(Contract):
    dependent_key: Identifier = Field(
        description="Exact temporary concept.key of the concept that depends on another, e.g. c2; never a name or subtopic key"
    )
    prerequisite_key: Identifier = Field(
        description="Exact temporary concept.key of the required concept, e.g. c1; never a name or subtopic key"
    )
    evidence: AnchorEvidence = Field(default_factory=list)
    provenance_kind: Literal["SOURCE_GROUNDED", "AI_ENRICHED"] = "SOURCE_GROUNDED"


class AnchoredStructureProposal(Contract):
    topics: Annotated[list[AnchoredTopic], Field(min_length=1, max_length=128)]
    subtopics: Annotated[list[AnchoredSubtopic], Field(min_length=1, max_length=512)]
    concepts: Annotated[list[AnchoredConcept], Field(min_length=1, max_length=1024)]
    prerequisites: Annotated[list[AnchoredRelationship], Field(max_length=4096)]
    provenance_kind: Literal["SOURCE_GROUNDED", "AI_ENRICHED"] = "SOURCE_GROUNDED"


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
    from .verified_inventory import verified_inventory
    existing = {(a.content_id, a.char_start, a.char_end) for a in result}
    for entry in verified_inventory(scope, units):
        span = (entry.content_id, entry.char_start, entry.char_end)
        if span in existing:
            continue
        piece = next(u.content.text[entry.char_start:entry.char_end] for u in units if u.content_id == entry.content_id)
        if len(piece) > MAX_ANCHOR_CHARACTERS:
            raise UnderstandingError("SOURCE_TOO_LARGE")
        identity = f"{scope.user_id}:{scope.source_id}:{scope.source_version}:{entry.content_id}:{entry.char_start}:{entry.char_end}:{piece}:{ANCHOR_POLICY_VERSION}"
        result.append(EvidenceAnchor(anchor_id="EA_" + uuid5(NAMESPACE_URL, identity).hex,
            content_id=entry.content_id, char_start=entry.char_start, char_end=entry.char_end, text=piece))
        existing.add(span)
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
            TopicProposal(
                key=t.key,
                title=t.title,
                evidence=evidence(t.evidence),
                provenance_kind=getattr(t, "provenance_kind", "SOURCE_GROUNDED"),
            )
            for t in proposal.topics
        ],
        subtopics=[
            SubtopicProposal(
                key=s.key,
                title=s.title,
                topic_key=s.topic_key,
                evidence=evidence(s.evidence),
                provenance_kind=getattr(s, "provenance_kind", "SOURCE_GROUNDED"),
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
                provenance_kind=getattr(c, "provenance_kind", "SOURCE_GROUNDED"),
            )
            for c in proposal.concepts
        ],
        prerequisites=[
            RelationshipProposal(
                dependent_key=r.dependent_key,
                prerequisite_key=r.prerequisite_key,
                evidence=evidence(r.evidence),
                provenance_kind=getattr(r, "provenance_kind", "SOURCE_GROUNDED"),
            )
            for r in proposal.prerequisites
        ],
        provenance_kind=getattr(proposal, "provenance_kind", "SOURCE_GROUNDED"),
    )


def bind_verified_visual_labels(
    scope: SourceScope, units: list[ScopedContentUnit], proposal: AnchoredStructureProposal,
) -> tuple[AnchoredStructureProposal,list[str]]:
    """Rebind a literal independently verified label to its exact owned source anchor."""
    from .content_understanding import visual_literal_supported
    from .visual_contracts import VisionExtractionData
    anchors=build_anchors(scope,units)
    lookup={anchor.anchor_id:anchor for anchor in anchors}
    labels: dict[str,list[str]]={}
    from .verified_inventory import verified_inventory
    for entry in verified_inventory(scope, units):
        labels.setdefault(entry.content_id, []).append(entry.label)
    repaired=[]
    def rebind(node: AnchoredTopic | AnchoredSubtopic | AnchoredConcept) -> AnchoredTopic | AnchoredSubtopic | AnchoredConcept:
        name=node.name if isinstance(node,AnchoredConcept) else node.title
        definition=node.definition if isinstance(node,AnchoredConcept) else None
        if any(ref.anchor_id not in lookup for ref in node.evidence):
            return node
        if any(visual_literal_supported(name,[lookup[ref.anchor_id].text]) and (definition is None or definition in lookup[ref.anchor_id].text) for ref in node.evidence):
            return node
        candidates=[a for a in anchors if a.content_id in labels and visual_literal_supported(name,labels[a.content_id])
            and visual_literal_supported(name,[a.text]) and (definition is None or definition in a.text)]
        from .verified_inventory import display_label
        shortest = min((len(a.text) for a in candidates), default=0)
        precise = [a for a in candidates if len(a.text) == shortest]
        if candidates:
            if not precise or len({(a.content_id, display_label(a.text)) for a in precise}) != 1:
                return node
            chosen=min(precise,key=lambda a:(a.char_start,a.anchor_id))
            repaired.append("verified_literal_anchor:"+node.key)
            return node.model_copy(update={"evidence":[AnchorReference(anchor_id=chosen.anchor_id)]})
        from .content_understanding import label_supported
        ev_text = " ".join(lookup[ref.anchor_id].text for ref in node.evidence)
        if not label_supported(name, ev_text, derived=True):
            grounding_cands = [a for a in anchors if label_supported(name, a.text, derived=True)]
            if grounding_cands:
                same_unit = [a for a in grounding_cands if any(lookup[ref.anchor_id].content_id == a.content_id for ref in node.evidence)]
                pool = same_unit if same_unit else (grounding_cands if len(units) == 1 else [])
                if pool and len({a.content_id for a in pool}) == 1:
                    chosen = min(pool, key=lambda a: (len(a.text), a.char_start))
                    if not any(ref.anchor_id == chosen.anchor_id for ref in node.evidence):
                        repaired.append("grounded_name_anchor:" + node.key)
                        return node.model_copy(update={"evidence": list(node.evidence) + [AnchorReference(anchor_id=chosen.anchor_id)]})
        return node
    return proposal.model_copy(update={
        "topics":[rebind(t) for t in proposal.topics],
        "subtopics":[rebind(s) for s in proposal.subtopics],
        "concepts":[rebind(c) for c in proposal.concepts],
    }),repaired


def retain_verified_visual_labels(
    scope: SourceScope, units: list[ScopedContentUnit], proposal: AnchoredStructureProposal,
) -> tuple[AnchoredStructureProposal,list[str]]:
    """Retain omitted literal components; organizational placement asserts no dependency."""
    from .content_understanding import visual_literal_supported
    from .visual_contracts import VisionExtractionData
    anchors=build_anchors(scope,units)
    lookup={a.anchor_id:a for a in anchors}
    concepts=list(proposal.concepts)
    names=[t.title for t in proposal.topics]+[s.title for s in proposal.subtopics]+[c.name for c in concepts]
    retained=[]
    visual_primitives={"box","node","component","label","container","shape"}
    def already_named(label: str) -> bool:
        words=set(re.findall(r"\w+",label.casefold()))
        for name in names:
            existing=set(re.findall(r"\w+",name.casefold()))
            if visual_literal_supported(name,[label]) and (words-existing)<=visual_primitives:
                return True
        return False
    from .verified_inventory import verified_inventory, display_label
    inventory = verified_inventory(scope, units)
    for unit in units:
        verification=unit.provenance.get("visual_verification")
        if unit.provenance.get("visual_schema_version")!="visual-v2" or not isinstance(verification,dict) or verification.get("status")!="VERIFIED":
            continue
        visual=VisionExtractionData.model_validate(unit.provenance.get("extraction"))
        literal=[entry.label for entry in inventory if entry.content_id == unit.content_id]
        parents=[s for s in proposal.subtopics if visual_literal_supported(s.title,literal)
            and any(ref.anchor_id in lookup and lookup[ref.anchor_id].content_id==unit.content_id for ref in s.evidence)]
        for literal_label in dict.fromkeys(entry.label for entry in inventory if entry.content_id == unit.content_id and entry.required_label):
            label=display_label(literal_label)
            if not 2<=len(label)<=120 or already_named(label):
                continue
            candidates=[a for a in anchors if a.content_id==unit.content_id and visual_literal_supported(label,[a.text])]
            if not candidates:
                raise UnderstandingError("UNSUPPORTED_EVIDENCE","LABEL")
            if not parents:
                raise UnderstandingError("INVALID_HIERARCHY","CHILD_SUPPORT")
            # A source-visible overall heading is preferred to a narrower grouping.
            first_heading=visual.headings[0] if visual.headings else ""
            parent=min(parents,key=lambda s:(not (visual_literal_supported(s.title,[first_heading]) and visual_literal_supported(first_heading,[s.title])),s.key))
            anchor=min(candidates,key=lambda a:(len(a.text),a.char_start,a.anchor_id))
            identity=f"{scope.user_id}:{scope.source_id}:{scope.source_version}:{unit.content_id}:{label}"
            key="c_visual_"+uuid5(NAMESPACE_URL,identity).hex
            concepts.append(AnchoredConcept(key=key,subtopic_key=parent.key,name=label,definition=None,evidence=[AnchorReference(anchor_id=anchor.anchor_id)]))
            names.append(label);retained.append("verified_literal_retained:"+key)
    result=proposal.model_copy(update={"concepts":concepts})
    # Reapply resource bounds after deterministic inventory expansion.
    return AnchoredStructureProposal.model_validate_json(result.model_dump_json()),retained
