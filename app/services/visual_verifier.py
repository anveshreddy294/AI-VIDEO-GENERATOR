"""Provider-independent verification against independently reviewed, hash-bound fixtures.

Unknown assets remain uncertain: schema validity or agreement between provider fields
cannot establish pixel truth. No model calls, repair, confidence scores or filename trust.
"""

from __future__ import annotations
import hashlib
import re
from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .visual_contracts import VisionExtractionData
from scripts.visual_structure_ground_truth import (
    GROUND_TRUTH,
    GroundTruth,
    VISIBLE,
    node,
    relationship,
)

Status = Literal["VERIFIED", "REJECTED", "UNCERTAIN"]
VERIFICATION_VERSION = "visual-strategies-v2"
Strategy = Literal[
    "FIXTURE_GROUND_TRUTH", "SOURCE_ANCHOR", "INDEPENDENT_REVIEW_REQUIRED"
]
FIXTURE_HASHES: dict[str, str] = {
    "97108f224cb99e81209301852c749db3a2756f6ad79ca871d8e4ab1cff43914f": "blank.png",
    "1ded51a7a6e0a55b2eba4bfc999c50c63ed5dd77f93c3df5c6688772704af4e5": "complex-diagram.png",
    "c4f45c8c1609877246f57c4a90ad8477e10096b6cdbee40a9236e38e2a6dd291": "corrupted.png",
    "b7e03a5a8a58cbf20b4adf5e90ad07e9f1f918132874fb7913a102357cd3c14d": "equation.png",
    "9f5adfacbe020cf1f2fe3e6d917b91c12986d207b0948c23812efa064abeaa13": "flowchart.png",
    "295322a2bac5cf9ea0793298bbedd2657da06ec46b36336965e8f66370610216": "graph.png",
    "3567c5b29419d556bf5e037c2370ef2984eb5f17906ded06f3a46c97fccf753a": "handwriting.png",
    "f466d320737420b7c848f13b4e17b4af2ca963b5fa44067101f917265bcc6633": "injection.png",
    "6fa3f9f8c1c5568a2b12ef84cf3fb3ce8f9b3ed1134ded8345739c46c50276da": "printed.png",
    "118e120987dfac7f5829b0cc84e46c366c6407636aa388ca293e1176c90315ff": "table.png",
}

PRINTED = GroundTruth(
    frozenset({"water", "cell membrane", "cell"}),
    frozenset({("water", "cell membrane"), ("cell membrane", "cell")}),
    "osmosis",
)


def normalized(value: str) -> str:
    """Presentation-only normalization; no synonyms or semantic paraphrase."""
    value = re.sub(r"(?<=\d)\.(?=\d)", "decimalpoint", value.casefold())
    return " ".join(re.sub(r"[^\w/=+*×−%]+", " ", value).split())


class VerificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    visible_support: str = ""
    claim_id: str = ""
    claim_type: str
    claim: str
    status: Status
    reason: str


class VisualVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Status
    strategy: Strategy = "FIXTURE_GROUND_TRUTH"
    checks: list[VerificationCheck] = Field(default_factory=list)
    rejected_claims: list[str] = Field(default_factory=list)
    uncertain_claims: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    verification_version: str = VERIFICATION_VERSION


class VisualSourceContext(BaseModel):
    """Internal parser scope; never derived from provider text or client identity fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    source_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_number: int | None = Field(default=None, ge=1)
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def region(self) -> VisualSourceContext:
        import math

        if self.bbox is not None and (
            not all(math.isfinite(v) for v in self.bbox)
            or self.bbox[0] >= self.bbox[2]
            or self.bbox[1] >= self.bbox[3]
        ):
            raise ValueError("Invalid source region")
        return self


class SourceAnchor(BaseModel):
    """Only trusted internal native-parser adapters may supply independent anchors.

    A ContentUnit or provenance dictionary alone is not proof of independence.
    No automatic conversion from provider ContentUnits is supported.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    origin: Literal[
        "pdf_native", "native_caption", "trusted_native_content", "model_generated"
    ]
    context: VisualSourceContext
    text: str = Field(min_length=1)


class IndependentVisualVerifier(Protocol):
    def verify(
        self,
        image: bytes,
        unresolved_claims: tuple[VerificationCheck, ...],
        extraction: VisionExtractionData,
        provenance: VisualSourceContext | None,
    ) -> VisualVerificationResult:
        """Return claim-ID-correlated decisions only for the supplied unresolved claims."""
        ...


def combine_checks(
    checks: list[VerificationCheck], strategy: Strategy
) -> VisualVerificationResult:
    rejected = [c.claim for c in checks if c.status == "REJECTED"]
    uncertain = [c.claim for c in checks if c.status == "UNCERTAIN"]
    return VisualVerificationResult(
        status=(
            "REJECTED"
            if rejected
            else "UNCERTAIN" if uncertain or not checks else "VERIFIED"
        ),
        strategy=strategy,
        checks=checks,
        rejected_claims=rejected,
        uncertain_claims=uncertain,
        reasons=sorted({c.reason for c in checks if c.status != "VERIFIED"}),
    )


def literal_supported(claim: str, text: str, equation: bool) -> bool:
    # Equations retain case and every operator/symbol; only whitespace is normalized.
    if equation:
        if not re.search(r"[=<>≤≥]", claim):
            return False
        pattern = r"\s*".join(re.escape(char) for char in claim if not char.isspace())
        return re.search(r"(?<!\w)" + pattern + r"(?!\w)", text) is not None
    canonical = lambda value: " ".join(value.casefold().split())
    return (
        re.search(r"(?<!\w)" + re.escape(canonical(claim)) + r"(?!\w)", canonical(text))
        is not None
    )


def extraction_claims(data: VisionExtractionData) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []
    for field in (
        "visible_text",
        "headings",
        "paragraphs",
        "bullet_points",
        "labels",
        "handwriting_text",
        "units",
        "diagram_entities",
        "arrows",
        "relationships",
        "formulas",
        "uncertain_elements",
    ):
        kind = "equation_symbols" if field == "formulas" else field
        claims.extend((kind, c) for c in getattr(data, field))
    for table in data.tables:
        claims.append(("table_headers", " | ".join(table.headers)))
        claims.extend(("table_cells", " | ".join(row)) for row in table.rows)
    for graph in data.graphs:
        claims.extend((("graph_axis", graph.x_axis), ("graph_axis", graph.y_axis)))
        claims.extend(
            ("graph_units", v) for v in (graph.x_unit, graph.y_unit) if v is not None
        )
        claims.extend(
            ("graph_claim", v)
            for v in graph.legend + graph.trends + graph.visible_values
        )
    if data.visual_structure:
        claims.append(("visual_structure", data.visual_structure))
    return claims


class VisualEvidenceVerifier:
    """Check every populated claim field against trusted evidence for these exact pixels."""

    def __init__(self, independent: IndependentVisualVerifier | None = None) -> None:
        self.independent = independent

    def verify(
        self,
        image_bytes: bytes,
        data: VisionExtractionData,
        *,
        context: VisualSourceContext | None = None,
        anchors: tuple[SourceAnchor, ...] = (),
    ) -> VisualVerificationResult:
        digest = hashlib.sha256(image_bytes).hexdigest()
        name = FIXTURE_HASHES.get(digest)
        if name not in VISIBLE:
            result = self._source_checks(data, context, anchors, digest)
        else:
            result = self._fixture_checks(name, data)
        checks = [
            c.model_copy(update={"claim_id": c.claim_id or f"claim:{i}"})
            for i, c in enumerate(result.checks)
        ]
        unresolved = tuple(
            c for c in checks if c.status == "UNCERTAIN" and c.claim_type != "evidence"
        )
        if self.independent is not None and unresolved:
            # Copies prevent an injected implementation from mutating deterministic evidence.
            try:
                reviewed = self.independent.verify(
                    image_bytes, unresolved, data.model_copy(deep=True), context
                )
                received = {c.claim_id: c for c in reviewed.checks}
                allowed = {c.claim_id for c in unresolved}
                valid = (
                    len(received) == len(reviewed.checks)
                    and set(received) <= allowed
                    and reviewed.status
                    == combine_checks(reviewed.checks, reviewed.strategy).status
                )
                if valid:
                    checks = [
                        (
                            received[c.claim_id]
                            if c.status == "UNCERTAIN"
                            and c.claim_id in received
                            and received[c.claim_id].claim == c.claim
                            and received[c.claim_id].claim_type == c.claim_type
                            else c
                        )
                        for c in checks
                    ]
            except Exception:
                # An unavailable reviewer cannot authorize publication; preserve uncertainty.
                checks = [
                    (
                        c.model_copy(update={"reason": "INDEPENDENT_REVIEW_FAILED"})
                        if c.status == "UNCERTAIN"
                        else c
                    )
                    for c in checks
                ]
        return combine_checks(checks, result.strategy)

    def _source_checks(
        self,
        data: VisionExtractionData,
        context: VisualSourceContext | None,
        anchors: tuple[SourceAnchor, ...],
        digest: str,
    ) -> VisualVerificationResult:
        strategy: Strategy = (
            "SOURCE_ANCHOR" if anchors else "INDEPENDENT_REVIEW_REQUIRED"
        )
        checks: list[VerificationCheck] = []
        usable: list[SourceAnchor] = []
        for index, anchor in enumerate(anchors):
            valid_scope = (
                context is not None
                and context.image_sha256 == digest
                and anchor.context == context
            )
            if not valid_scope:
                checks.append(
                    VerificationCheck(
                        claim_id=f"anchor:{index}",
                        claim_type="source_scope",
                        claim="page/region identity",
                        status="REJECTED",
                        reason="SOURCE_ANCHOR_SCOPE_MISMATCH",
                    )
                )
            elif anchor.origin == "model_generated":
                checks.append(
                    VerificationCheck(
                        claim_id=f"anchor:{index}",
                        claim_type="source_anchor",
                        claim="model-generated anchor",
                        status="REJECTED",
                        reason="SELF_VERIFICATION_FORBIDDEN",
                    )
                )
            else:
                usable.append(anchor)
        for index, (kind, claim) in enumerate(extraction_claims(data)):
            literal_kind = kind in {
                "visible_text",
                "headings",
                "paragraphs",
                "bullet_points",
                "labels",
                "handwriting_text",
                "units",
                "equation_symbols",
            }
            accepted = literal_kind and any(
                literal_supported(claim, a.text, kind == "equation_symbols")
                for a in usable
            )
            checks.append(
                VerificationCheck(
                    claim_id=f"claim:{index}",
                    claim_type=kind,
                    claim=claim,
                    status="VERIFIED" if accepted else "UNCERTAIN",
                    reason=(
                        "NATIVE_LITERAL_ANCHOR"
                        if accepted
                        else (
                            "NO_INDEPENDENT_VISUAL_ANCHOR"
                            if not usable
                            else "CLAIM_NOT_SUPPORTED_BY_NATIVE_ANCHOR"
                        )
                    ),
                )
            )
        if not checks:
            checks.append(
                VerificationCheck(
                    claim_id="empty",
                    claim_type="evidence",
                    claim="empty",
                    status="UNCERTAIN",
                    reason="NO_VERIFIABLE_CLAIMS",
                )
            )
        return combine_checks(checks, strategy)

    def _fixture_checks(
        self, name: str, data: VisionExtractionData
    ) -> VisualVerificationResult:
        checks: list[VerificationCheck] = []

        def check(kind: str, claim: str, status: Status, reason: str) -> None:
            checks.append(
                VerificationCheck(
                    claim_type=kind, claim=claim, status=status, reason=reason
                )
            )

        def exact(kind: str, claim: str, accepted: bool) -> None:
            check(
                kind,
                claim,
                "VERIFIED" if accepted else "REJECTED",
                (
                    "MATCHES_TRUSTED_EVIDENCE"
                    if accepted
                    else "CONTRADICTS_TRUSTED_EVIDENCE"
                ),
            )

        truth = GROUND_TRUTH.get(name, PRINTED if name == "printed.png" else None)

        def edge(claim: str) -> None:
            if truth is None:
                exact("directed_relationship", claim, False)
                return
            parsed = relationship(claim, truth)
            if parsed is None and re.fullmatch(
                r"[\w ]+(?:\s*(?:->|→)\s*[\w ]+)+", claim
            ):
                exact("directed_relationship", claim, False)
            elif parsed is None:
                # Unparseable prose is not silently declared equivalent to a known edge.
                check(
                    "directed_relationship",
                    claim,
                    "UNCERTAIN",
                    "RELATIONSHIP_NOT_DETERMINISTICALLY_PARSEABLE",
                )
            else:
                exact(
                    "directed_relationship",
                    claim,
                    bool(parsed) and set(parsed) <= truth.edges,
                )

        for field in (
            "visible_text",
            "headings",
            "paragraphs",
            "bullet_points",
            "labels",
            "handwriting_text",
            "units",
        ):
            for claim in getattr(data, field):
                if "->" in claim or "→" in claim:
                    edge(claim)
                elif re.fullmatch(r"\s*[Ff]\s*=.*", claim):
                    formula = re.sub(r"[\s*×]", "", claim).casefold()
                    exact(
                        "equation_symbols",
                        claim,
                        name in ("equation.png", "handwriting.png")
                        and formula == "f=ma",
                    )
                else:
                    literal = normalized(claim)
                    exact(
                        field,
                        claim,
                        bool(literal)
                        and (" " + literal + " ")
                        in (" " + normalized(VISIBLE[name]) + " "),
                    )
        for claim in data.diagram_entities:
            exact(
                "diagram_component",
                claim,
                truth is not None and node(claim, truth) is not None,
            )
        for claim in data.arrows + data.relationships:
            edge(claim)
        for formula in data.formulas:
            canonical = re.sub(r"[\s*×]", "", formula).casefold()
            exact(
                "equation_symbols",
                formula,
                name in ("equation.png", "handwriting.png") and canonical == "f=ma",
            )
        for table in data.tables:
            exact(
                "table_headers",
                " | ".join(table.headers),
                name == "table.png"
                and [normalized(h) for h in table.headers]
                == ["mass kg", "acceleration m/s2", "force n"],
            )
            exact(
                "table_cells",
                str(table.rows),
                name == "table.png" and table.rows == [["2", "3", "6"]],
            )
        for graph in data.graphs:
            exact(
                "graph_axes",
                graph.x_axis + " | " + graph.y_axis,
                name == "graph.png"
                and normalized(graph.x_axis) in ("time", "time s")
                and normalized(graph.y_axis) in ("distance", "distance m"),
            )
            for value, expected in ((graph.x_unit, "s"), (graph.y_unit, "m")):
                if value is not None:
                    exact(
                        "graph_units", value, name == "graph.png" and value == expected
                    )
            for value in graph.legend + graph.visible_values:
                exact("graph_value_or_legend", value, False)
            for value in graph.trends:
                exact(
                    "graph_trend",
                    value,
                    name == "graph.png"
                    and normalized(value) == "distance increases with time",
                )
        if data.visual_structure:
            check(
                "visual_structure",
                data.visual_structure,
                "UNCERTAIN",
                "FREE_FORM_LAYOUT_NOT_VERIFIED",
            )
        for claim in data.uncertain_elements:
            check(
                "provider_uncertainty",
                claim,
                "UNCERTAIN",
                "PROVIDER_REPORTED_UNCERTAINTY",
            )
        if not checks:
            check("evidence", "empty", "UNCERTAIN", "NO_VERIFIABLE_CLAIMS")
        rejected = [c.claim for c in checks if c.status == "REJECTED"]
        uncertain = [c.claim for c in checks if c.status == "UNCERTAIN"]
        return VisualVerificationResult(
            status="REJECTED" if rejected else "UNCERTAIN" if uncertain else "VERIFIED",
            checks=checks,
            rejected_claims=rejected,
            uncertain_claims=uncertain,
            reasons=sorted({c.reason for c in checks if c.status != "VERIFIED"}),
        )


from .vision import VisionExtractionFailed


class VisualVerificationFailed(VisionExtractionFailed):
    """Safe typed gate failure, distinct from provider extraction failure."""

    def __init__(self, result: VisualVerificationResult) -> None:
        self.result = result
        self.code = (
            "VERIFICATION_REQUIRED"
            if result.status == "UNCERTAIN"
            else "VISUAL_EVIDENCE_REJECTED"
        )
        super().__init__("Visual evidence verification " + result.status.lower())
