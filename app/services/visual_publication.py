"""Explicit independently verified subset publication, without promoting uncertainty."""
from __future__ import annotations
import re
from .visual_contracts import VisionExtractionData
from .visual_verifier import VisualVerificationResult, combine_checks, extraction_claims

# Two independent substantive lines and 80 alphanumeric characters avoid publishing
# a lone title, toolbar label, or incidental fragment as a learning source.
MIN_VERIFIED_LINES = 2
MIN_VERIFIED_CHARACTERS = 80
LITERAL_FIELDS = ("visible_text", "headings", "paragraphs", "bullet_points", "labels", "handwriting_text")
CHROME = re.compile(r"(?:powered by wps office|wps office|wps presentation|(?:edit|share|save)\s*[|/]+\s*(?:edit|share|save))", re.I)

def remove_chrome(data: VisionExtractionData) -> tuple[VisionExtractionData, int]:
    """Exclude only exact known application branding/combined toolbar strings."""
    clean = data.model_copy(deep=True)
    removed = 0
    for field in LITERAL_FIELDS:
        original: list[str] = getattr(clean, field)
        kept = [line for line in original if not CHROME.fullmatch(line.strip())]
        removed += len(original) - len(kept)
        setattr(clean, field, kept)
    return clean, removed

def verified_subset(data: VisionExtractionData, result: VisualVerificationResult
                    ) -> tuple[VisionExtractionData, VisualVerificationResult] | None:
    """Subset only independently reviewed claims; scope/integrity failures forbid salvage.

    Fixture and native-anchor gates retain their existing whole-extraction contract.
    Tables and graphs are atomic: every constituent claim must be supported.
    """
    if result.strategy != "INDEPENDENT_REVIEW_REQUIRED" or not result.checks:
        return None
    allowed = {"INDEPENDENT_VISUAL_SUPPORTED", "INDEPENDENT_VISUAL_CONTRADICTED", "INDEPENDENT_VISUAL_UNCERTAIN", "INDEPENDENT_VERIFIER_TIMEOUT", "INDEPENDENT_VERIFIER_RATE_LIMIT", "INDEPENDENT_VERIFIER_UNAVAILABLE", "INDEPENDENT_REVIEW_BUDGET_LIMIT"}
    if any(check.reason not in allowed for check in result.checks):
        return None
    verified = {(c.claim_type, c.claim) for c in result.checks if c.status == "VERIFIED"}
    clean = data.model_copy(deep=True)
    for field in LITERAL_FIELDS + ("units", "diagram_entities", "arrows", "relationships", "formulas"):
        kind = "equation_symbols" if field == "formulas" else field
        setattr(clean, field, [line for line in getattr(clean, field) if (kind, line) in verified])
    clean.tables = [t for t in clean.tables if ("table_headers", " | ".join(t.headers)) in verified
                    and all(("table_cells", " | ".join(row)) in verified for row in t.rows)]
    clean.graphs = [g for g in clean.graphs if all(pair in verified for pair in
                    [("graph_axis", g.x_axis), ("graph_axis", g.y_axis)]
                    + [("graph_units", u) for u in (g.x_unit, g.y_unit) if u is not None]
                    + [("graph_claim", v) for v in g.legend + g.trends + g.visible_values])]
    if ("visual_structure", clean.visual_structure) not in verified:
        clean.visual_structure = ""
    clean.uncertain_elements = []
    lines = {" ".join(line.casefold().split()) for field in LITERAL_FIELDS for line in getattr(clean, field)}
    if len(lines) < MIN_VERIFIED_LINES or sum(sum(c.isalnum() for c in line) for line in lines) < MIN_VERIFIED_CHARACTERS:
        return None
    retained = set(extraction_claims(clean))
    checks = [c for c in result.checks if (c.claim_type, c.claim) in retained]
    if not retained or any(pair not in verified for pair in retained):
        return None
    published = combine_checks(checks, result.strategy)
    return (clean, published) if published.status == "VERIFIED" else None
