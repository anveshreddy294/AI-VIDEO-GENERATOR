"""Credential-free classifications shared by ingestion and source jobs."""
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel
from ...core.supabase import SupabaseResponseError
from ...core.processing_errors import ProcessingCode, ProcessingError
from ..vision import VisionErrorCode, VisionRouteFailureTrace, safe_vision_error_code

Stage = Literal['EXTRACTION', 'VERIFICATION', 'NORMALIZATION', 'STRUCTURING', 'CHUNKING', 'PERSISTENCE', 'INDEXING']


class SourceFailure(BaseModel):
    """Safe operational failure; never stores an upstream exception message."""
    stage: Stage
    code: str
    reason_code: ProcessingCode | None = None
    vision_error_code: VisionErrorCode | None = None
    vision_route_trace: VisionRouteFailureTrace | None = None
    validation_detail: Literal["REFERENCE", "QUOTE", "ROLE", "LABEL", "EDGE_ENDPOINTS", "EDGE_NAMES", "EDGE_ROLE", "EDGE_DIRECTION", "DEFINITION", "PARENT_REFERENCE", "EMPTY_REQUIRED_LEVEL", "CHILD_SUPPORT"] | None = None
    failed_object_type: Literal["TOPIC", "SUBTOPIC", "CONCEPT", "INVENTORY"] | None = None
    structural_reason: Literal["HALLUCINATED_LABEL", "WRONG_EVIDENCE_ANCHOR", "RENDERER_CAPTION_MISMATCH"] | None = None
    label_reference: str | None = None
    repair_attempted: bool | None = None
    verification_status: Literal["VERIFIED", "REJECTED", "UNCERTAIN"] | None = None
    verification_reasons: list[str] | None = None
    verified_claim_count: int | None = None
    uncertain_claim_count: int | None = None
    rejected_claim_count: int | None = None
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
        from ..visual_verifier import VisualVerificationFailed
        if isinstance(error, VisualVerificationFailed):
            from ..visual_verifier import verification_summary
            raise SourceIngestionFailed(SourceFailure(stage="VERIFICATION", code=error.code, retryable=False, **verification_summary(error.result),
                message="Independent visual verification required." if error.result.status == "UNCERTAIN" else "Visual evidence rejected; publication blocked.")) from None
        vision_error_code: VisionErrorCode | None = None
        if isinstance(error, VisionExtractionFailed):
            vision_error_code = safe_vision_error_code(error.error_code)
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
        raise SourceIngestionFailed(SourceFailure(stage=stage, code=code, reason_code=reason_code, vision_error_code=vision_error_code, vision_route_trace=error.route_trace if isinstance(error, VisionExtractionFailed) else None, retryable=True,
                                                  message=message)) from None
