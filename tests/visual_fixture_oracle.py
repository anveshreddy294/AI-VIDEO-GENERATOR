"""Explicit test-only oracle; production contains no filename/hash shortcuts."""
from __future__ import annotations
import re
from app.services.visual_verifier import VisualEvidenceVerifier,VisualVerificationResult,VerificationCheck,VisualSourceContext,SourceAnchor,Status,normalized
from app.services.visual_contracts import VisionExtractionData
from scripts.visual_structure_ground_truth import GROUND_TRUTH,GroundTruth,VISIBLE,node,relationship
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


class FixtureOracle:
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


REAL_SOURCE_CHECKS = VisualEvidenceVerifier._source_checks

def fixture_checks(self: VisualEvidenceVerifier, data: VisionExtractionData, context: VisualSourceContext | None, anchors: tuple[SourceAnchor,...], digest: str) -> VisualVerificationResult:
    name=FIXTURE_HASHES.get(digest)
    if name in VISIBLE:
        return FixtureOracle()._fixture_checks(name,data)
    return REAL_SOURCE_CHECKS(self,data,context,anchors,digest)
