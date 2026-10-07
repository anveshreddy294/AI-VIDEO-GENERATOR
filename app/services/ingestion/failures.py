"""Credential-free classifications shared by ingestion and source jobs."""
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel
from ...core.supabase import SupabaseResponseError
from ...core.processing_errors import ProcessingCode, ProcessingError

Stage = Literal['EXTRACTION', 'NORMALIZATION', 'STRUCTURING', 'CHUNKING', 'PERSISTENCE', 'INDEXING']


class SourceFailure(BaseModel):
    """Safe operational failure; never stores an upstream exception message."""
    stage: Stage
    code: str
    reason_code: ProcessingCode | None = None
    retryable: bool
    message: str


class SourceIngestionFailed(RuntimeError):
    """Carries a safe failure boundary without serializing prompts or credentials."""
    def __init__(self, failure: SourceFailure) -> None:
        self.failure = failure
        super().__init__(failure.message)


class SourceIndexFailed(SupabaseResponseError):
    """Keep the storage exception contract while exposing the actual failing stage."""
    def __init__(self, reason_code: ProcessingCode = 'VECTOR_INDEX_FAILED') -> None:
        self.failure = SourceFailure(stage='INDEXING', code='QDRANT_INDEX_FAILED', retryable=True,
                                     reason_code=reason_code,
                                     message='Source committed; vector indexing failed; retry this source')
        super().__init__(self.failure.message)


@contextmanager
def ingestion_stage(stage: Stage) -> Iterator[None]:
    """Classify upstream errors at the active processing boundary."""
    try:
        yield
    except SourceIngestionFailed:
        raise
    except Exception as error:
        from ..vision import VisionExtractionFailed
        if isinstance(error, VisionExtractionFailed):
            code = 'VISION_EXTRACTION_FAILED'
            message = 'Visual evidence extraction failed; no fabricated content was accepted.'
        elif stage == 'STRUCTURING':
            code = 'STRUCTURE_TIMEOUT' if isinstance(error, TimeoutError) else 'STRUCTURE_EXTRACTION_FAILED'
            message = 'Could not extract grounded concepts from the source.'
        else:
            code = stage + '_FAILED'
            message = 'Source processing failed during ' + stage.lower() + '.'
        reason_code: ProcessingCode | None = ('MODEL_TIMEOUT' if isinstance(error, TimeoutError) else
                                             error.code if isinstance(error, ProcessingError) else None)
        raise SourceIngestionFailed(SourceFailure(stage=stage, code=code, reason_code=reason_code, retryable=True,
                                                  message=message)) from None
