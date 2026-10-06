"""Safe classifications for model, embedding, and vector processing failures."""
from typing import Literal

ProcessingCode = Literal['MODEL_TIMEOUT', 'MODEL_UNAVAILABLE', 'INVALID_MODEL_OUTPUT',
                         'NO_GROUNDED_CONCEPTS', 'EMBEDDING_MODEL_UNAVAILABLE',
                         'EMBEDDING_FAILED', 'VECTOR_INDEX_FAILED']


class ProcessingError(RuntimeError):
    """A stable classification with a fixed public message and no upstream body."""
    def __init__(self, code: ProcessingCode, message: str) -> None:
        self.code = code
        super().__init__(message)
