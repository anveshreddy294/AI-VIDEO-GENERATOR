"""Bounded source-only visual evidence, compatible with the existing vision contract."""

from __future__ import annotations
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator, JsonValue

VisualText = Annotated[str, Field(min_length=1, max_length=4096)]
VisualLines = Annotated[list[VisualText], Field(max_length=128)]
VisualKind = Literal[
    "TEXT",
    "HANDWRITING",
    "DIAGRAM",
    "FLOWCHART",
    "GRAPH",
    "TABLE",
    "EQUATION",
    "FIGURE",
    "MIXED",
]


class VisualTable(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    headers: Annotated[list[VisualText], Field(min_length=1, max_length=32)]
    rows: Annotated[
        list[Annotated[list[VisualText], Field(max_length=32)]], Field(max_length=128)
    ]

    @model_validator(mode="after")
    def rectangular(self) -> VisualTable:
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Table dimensions mismatch")
        return self


class VisualGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x_axis: VisualText
    y_axis: VisualText
    x_unit: VisualText | None = None
    y_unit: VisualText | None = None
    legend: VisualLines = Field(default_factory=list)
    trends: VisualLines = Field(default_factory=list)
    visible_values: VisualLines = Field(default_factory=list)


class VisionExtractionData(BaseModel):
    """Provider claims are data; actual routing provenance is set by the transport."""

    model_config = ConfigDict(extra="forbid", strict=True)
    visible_text: VisualLines = Field(default_factory=list)
    headings: VisualLines = Field(default_factory=list)
    paragraphs: VisualLines = Field(default_factory=list)
    bullet_points: VisualLines = Field(default_factory=list)
    diagram_entities: VisualLines = Field(default_factory=list)
    labels: VisualLines = Field(default_factory=list)
    arrows: VisualLines = Field(default_factory=list)
    relationships: VisualLines = Field(default_factory=list)
    tables: Annotated[list[VisualTable], Field(max_length=8)] = Field(
        default_factory=list
    )
    formulas: VisualLines = Field(default_factory=list)
    units: VisualLines = Field(default_factory=list)
    visual_structure: Annotated[str, Field(max_length=4096)] = ""
    uncertain_elements: VisualLines = Field(default_factory=list)
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = 0.0
    content_kind: VisualKind = "MIXED"
    handwriting_text: VisualLines = Field(default_factory=list)
    graphs: Annotated[list[VisualGraph], Field(max_length=8)] = Field(
        default_factory=list
    )
    _actual_provider: str = PrivateAttr(default="")
    _actual_model: str = PrivateAttr(default="")
    _routing_provenance: dict[str, JsonValue] = PrivateAttr(default_factory=dict)
