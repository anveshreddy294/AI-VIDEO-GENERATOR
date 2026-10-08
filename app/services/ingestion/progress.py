"""Fixed coarse ingestion stages; callbacks contain no provider or source content."""
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

IngestionStage = Literal["EXTRACTING_SOURCE", "PERSISTING_SOURCE", "PREPARING_IMAGE", "UNDERSTANDING_IMAGE", "VALIDATING_VISUAL_EVIDENCE", "BUILDING_LEARNING_STRUCTURE", "INDEXING_SOURCE"]
_callback: ContextVar[Callable[[IngestionStage], None] | None] = ContextVar("ingestion_progress", default=None)

@contextmanager
def source_progress(callback: Callable[[IngestionStage], None]) -> Iterator[None]:
    token = _callback.set(callback)
    try:
        yield
    finally:
        _callback.reset(token)

def report(stage: IngestionStage) -> None:
    callback = _callback.get()
    if callback is not None:
        callback(stage)
