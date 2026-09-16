"""Strict Pydantic schemas (the "blanket structure" the LLM must obey).

Two chunk varieties share the `layer: "A"` security tag but are structurally
distinct — a discriminated union on `type` means a document chunk *cannot* be
built with video metadata and vice versa. This is the schema-level guarantee
that Layer A ground truth stays unambiguous.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class TopicBlueprint(BaseModel):
    """The master blueprint the Learning Agent will use to build quizzes/videos."""

    topic_name: str = Field(description="Short title of what the document teaches")
    key_concepts: list[str] = Field(
        description="The core terms a student must know to master this topic"
    )
    prerequisites: list[str] = Field(
        description="Concepts the student should already know before starting"
    )
    difficulty_level: Literal["beginner", "intermediate", "advanced"] = Field(
        description="Rough difficulty of the material for an average student"
    )


class AuthoritativeSourceChunk(BaseModel):
    """A text/image/TXT chunk — located by *page* in a document."""

    layer: Literal["A"] = "A"
    type: Literal["authoritative_source"] = "authoritative_source"
    document_name: str
    text: str
    page: int | None = Field(default=None, description="Source page in the PDF")


class AuthoritativeVideoChunk(BaseModel):
    """A lecture chunk — located by *wall-clock time* in a video.

    The temporal metadata lets retrieval answer "show me where this was
    taught" with the exact 30-second window of the source recording.
    """

    layer: Literal["A"] = "A"
    type: Literal["authoritative_video"] = "authoritative_video"
    video_name: str
    start_timestamp: str = Field(description="Clock time 'MM:SS' where the chunk begins")
    end_timestamp: str = Field(description="Clock time 'MM:SS' where the chunk ends")
    text: str


# The tagged payload that goes into the vector DB. Validated by `type`.
LayerAChunk = Annotated[
    Union[AuthoritativeSourceChunk, AuthoritativeVideoChunk],
    Field(discriminator="type"),
]