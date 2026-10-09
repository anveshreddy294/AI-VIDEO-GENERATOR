"""Scoped literal inventory from accepted visual claims and explicit document headings."""
from __future__ import annotations

import re
import unicodedata
from typing import Literal
from uuid import NAMESPACE_URL, uuid5, UUID
from pydantic import Field
from .knowledge_models import Contract, ScopedContentUnit
from .security.source_scope import SourceScope
from .visual_contracts import VisionExtractionData

ClaimKind = Literal["HEADING", "LITERAL_TEXT", "COMPONENT", "FLOWCHART_LABEL",
    "TABLE_HEADER", "TABLE_CELL", "GRAPH_AXIS", "GRAPH_LEGEND", "EQUATION", "SYMBOL", "RELATIONSHIP"]


class VerifiedLabel(Contract):
    """Identity and literal span are server-derived; no model claim enters this inventory."""
    inventory_id: str
    user_id: UUID
    content_id: str
    source_id: str
    source_version: int = Field(ge=1)
    kind: ClaimKind
    label: str
    char_start: int
    char_end: int
    required_label: bool = False


def display_label(value: str) -> str:
    """Remove presentation prefixes only; preserve signs, decimals, formulas and arrows."""
    value = unicodedata.normalize("NFC", value).strip()
    value = re.sub(r"^#{1,6}\s+", "", value)
    value = re.sub(r"^(?:[-*•]\s+)?(?:\d+[.)]\s+)?", "", value)
    if value.startswith("**") and value.endswith("**"):
        value = value[2:-2]
    return " ".join(value.split()).strip()


def literal_supported(label: str, values: list[str]) -> bool:
    """Match an ordered literal phrase without discarding semantic punctuation."""
    semantic_case = bool(re.search(r"[=+×−∑∫≈→←<>]|->|<-|\d", label) or re.fullmatch(r"(?:[A-Z][a-z]?){2,}", label))
    needle = display_label(label)
    if not semantic_case:
        needle = needle.casefold()
    if not needle:
        return False
    return any(re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)",
                        (display_label(value) if semantic_case else display_label(value).casefold())) is not None for value in values)


def verified_inventory(scope: SourceScope, units: list[ScopedContentUnit]) -> list[VerifiedLabel]:
    """Bounded accepted claims must retain a literal span in their owned canonical unit."""
    from .content_understanding import UnderstandingError
    if not units or len({u.content_id for u in units}) != len(units) or any(
        (u.user_id, u.source_id, u.source_version) != (scope.user_id, scope.source_id, scope.source_version)
        for u in units
    ):
        raise UnderstandingError("NO_SAFE_CONTENT")
    result: list[VerifiedLabel] = []
    seen: set[tuple[str, ClaimKind, str, int]] = set()
    scanned: set[tuple[str, ClaimKind, str]] = set()
    def add(unit: ScopedContentUnit, kind: ClaimKind, value: str, required: bool = False) -> None:
        # Spans always reference exact persisted characters; display normalization never rewrites evidence.
        value_key = (unit.content_id, kind, value)
        if not value.strip() or value_key in scanned:
            return
        scanned.add(value_key)
        text = unit.content.text
        pattern = re.escape(value)
        pattern = re.sub(r"(?:\\[ \t\n])+", r"\\s+", pattern)
        matches = list(re.finditer(pattern, text))
        if not matches:
            raise UnderstandingError("UNSUPPORTED_EVIDENCE", "LABEL",
                failed_object_type="INVENTORY", reason_category="RENDERER_CAPTION_MISMATCH", label=value)
        for match in matches:
            identity = (unit.content_id, kind, value, match.start())
            if identity in seen:
                continue
            seen.add(identity)
            result.append(VerifiedLabel(inventory_id="VI_" + uuid5(NAMESPACE_URL,
                f"{scope.user_id}:{scope.source_id}:{scope.source_version}:{identity}").hex,
                content_id=unit.content_id, user_id=scope.user_id, source_id=scope.source_id, source_version=scope.source_version,
                kind=kind, label=value, char_start=match.start(), char_end=match.end(), required_label=required))
            from .evidence_anchors import MAX_ANCHORS
            if len(result) > MAX_ANCHORS:
                raise UnderstandingError("SOURCE_TOO_LARGE")
    for unit in units:
        provenance = unit.provenance
        verification = provenance.get("visual_verification")
        if provenance.get("visual_schema_version") != "visual-v2" or not isinstance(verification, dict) or verification.get("status") != "VERIFIED":
            continue
        visual = VisionExtractionData.model_validate(provenance.get("extraction"))
        for label in visual.headings:
            add(unit, "HEADING", label, True)
        for label in visual.visible_text + visual.handwriting_text + visual.paragraphs + visual.bullet_points:
            add(unit, "LITERAL_TEXT", label)
        for label in visual.labels + visual.diagram_entities:
            add(unit, "FLOWCHART_LABEL" if visual.content_kind == "FLOWCHART" else "COMPONENT", label, True)
        for table in visual.tables:
            for label in table.headers:
                add(unit, "TABLE_HEADER", label, True)
            for row in table.rows:
                for cell in row:
                    add(unit, "TABLE_CELL", cell)
        for graph in visual.graphs:
            for label in (graph.x_axis, graph.y_axis):
                add(unit, "GRAPH_AXIS", label, True)
            for label in graph.legend:
                add(unit, "GRAPH_LEGEND", label)
            for label in (graph.x_unit, graph.y_unit):
                if label:
                    add(unit, "SYMBOL", label)
            for label in graph.trends + graph.visible_values:
                add(unit, "LITERAL_TEXT", label)
        for label in visual.formulas:
            add(unit, "EQUATION", label, True)
        for label in visual.units:
            add(unit, "SYMBOL", label)
        for label in visual.arrows + visual.relationships:
            add(unit, "RELATIONSHIP", label)
    from .outline_evidence import detect_outline
    by_id = {u.content_id: u for u in units}
    for heading in detect_outline(scope, units):
        add(by_id[heading.content_id], "HEADING", heading.label, True)
    return result


def visual_proposal_schema(scope: SourceScope, units: list[ScopedContentUnit]) -> dict[str, object] | None:
    """Closed literal label vocabulary for entirely independently verified visual sources."""
    if not all(unit.provenance.get("visual_schema_version") == "visual-v2"
        and isinstance(unit.provenance.get("visual_verification"), dict)
        and unit.provenance["visual_verification"].get("status") == "VERIFIED"
        and unit.provenance.get("extraction", {}).get("content_kind") != "TEXT" for unit in units):
        return None
    from .evidence_anchors import AnchoredStructureProposal
    vocabulary = sorted({display_label(entry.label) for entry in verified_inventory(scope, units)
        if entry.kind not in {"TABLE_CELL", "RELATIONSHIP", "SYMBOL"} and 2 <= len(display_label(entry.label)) <= 120})
    if not vocabulary:
        return None
    schema = AnchoredStructureProposal.model_json_schema()
    for name, field in (("AnchoredTopic", "title"), ("AnchoredSubtopic", "title"), ("AnchoredConcept", "name")):
        schema["$defs"][name]["properties"][field]["enum"] = vocabulary
        schema["$defs"][name].setdefault("required", [])
        if "evidence" not in schema["$defs"][name]["required"]:
            schema["$defs"][name]["required"].append("evidence")
        schema["$defs"][name]["properties"]["evidence"]["minItems"] = 1
    return schema
