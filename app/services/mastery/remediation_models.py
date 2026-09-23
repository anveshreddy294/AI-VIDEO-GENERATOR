"""Step 5D Domain Models — Remediation Job Entity and Lifecycle Statuses.

Defines the explicit domain representation for personalized video remediation jobs,
including execution tracking, idempotency keys, and failure attribution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator

from .models import DomainInvariantViolation


class RemediationJobStatus(str, Enum):
    """Constrained lifecycle statuses for a remediation job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    READY = "READY"
    FAILED = "FAILED"


class RemediationJob(BaseModel):
    """Domain entity representing a single grounded remedial video execution."""

    remediation_job_id: str
    user_id: str
    source_id: str
    session_id: str | None = None
    concept_id: str

    status: RemediationJobStatus = Field(default=RemediationJobStatus.PENDING)
    video_job_id: str | None = None
    video_path: str | None = None
    duration_seconds: float | None = None

    attempt_number: int = Field(default=1, ge=1, description="Educational remediation attempt cycle (1-3)")
    idempotency_key: str
    strategy_used: str | None = Field(default=None, description="Pedagogical strategy applied for this video generation")
    misconception_code: str | None = Field(default=None, description="Diagnostic misconception code addressed by this remediation")
    evidence_attempt_ids: list[str] = Field(default_factory=list, description="IDs of learner attempts evidencing this gap")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None

    failure_code: str | None = None
    failure_message: str | None = None
    is_infrastructure_failure: bool = Field(
        default=False,
        description="True if failure was caused by technical infrastructure (FFmpeg/TTS/disk), preserving educational attempt budget.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        if "job_id" in data and "remediation_job_id" not in data:
            data["remediation_job_id"] = data.pop("job_id")
        if "idempotency_key" not in data or not data["idempotency_key"]:
            u = data.get("user_id", "user")
            c = data.get("concept_id", "concept")
            att = data.get("attempt_number", 1)
            data["idempotency_key"] = f"IDEMP_{u}_{c}_{att}"
        try:
            super().__init__(**data)
        except Exception as err:
            if isinstance(err, DomainInvariantViolation):
                raise
            from pydantic import ValidationError
            if isinstance(err, ValidationError):
                first_msg = err.errors()[0].get("msg", str(err)) if err.errors() else str(err)
                raise DomainInvariantViolation(first_msg) from err
            raise

    @field_validator("remediation_job_id", "user_id", "source_id", "concept_id", "idempotency_key")
    @classmethod
    def _validate_non_empty_strings(cls, v: str, info: Any) -> str:
        if not v or not v.strip():
            raise DomainInvariantViolation(
                f"Field '{info.field_name}' cannot be empty or whitespace only."
            )
        return v.strip()

    @property
    def job_id(self) -> str:
        return self.remediation_job_id
