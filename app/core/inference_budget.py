"""Cooperative worker budgets; browser polling never cancels processing threads."""
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
import time
from threading import BoundedSemaphore
from .config import settings

_local_slots = BoundedSemaphore(max(1, settings.ollama_max_concurrency))

_deadline: ContextVar[float | None] = ContextVar("inference_deadline", default=None)
_job_id: ContextVar[str | None] = ContextVar("inference_job_id", default=None)


def current_job_id() -> str | None:
    return _job_id.get()


def effective_deadline(deadline: float) -> float:
    parent = _deadline.get()
    return min(parent, deadline) if parent is not None else deadline


def check_budget() -> None:
    parent = _deadline.get()
    if parent is not None and time.monotonic() >= parent:
        raise TimeoutError("Processing budget exhausted")


@contextmanager
def local_inference_slot(deadline: float) -> Iterator[None]:
    if not _local_slots.acquire(timeout=max(0, effective_deadline(deadline)-time.monotonic())):
        raise TimeoutError("Local inference queue budget exhausted")
    try:
        check_budget()
        yield
    finally:
        _local_slots.release()


@contextmanager
def processing_budget(seconds: float, *, job_id: str | None = None) -> Iterator[None]:
    token = _deadline.set(effective_deadline(time.monotonic() + seconds))
    job_token = _job_id.set(job_id or _job_id.get())
    try:
        check_budget()
        yield
    finally:
        _deadline.reset(token)
        _job_id.reset(job_token)
