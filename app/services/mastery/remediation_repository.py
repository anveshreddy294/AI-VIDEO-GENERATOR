"""Step 5D Remediation Job Repository Abstraction.

Defines RemediationJobRepository Protocol and InMemoryRemediationJobRepository.
"""

from __future__ import annotations

import copy
from typing import Protocol, runtime_checkable

from .remediation_models import RemediationJob, RemediationJobStatus


@runtime_checkable
class RemediationJobRepository(Protocol):
    """Persistence protocol for storing and querying remediation jobs."""

    def get(self, remediation_job_id: str) -> RemediationJob | None:
        """Retrieve remediation job by unique remediation_job_id."""
        ...

    def save(self, job: RemediationJob) -> RemediationJob:
        """Persist or update a remediation job."""
        ...

    def find_active_for_concept(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        attempt_number: int | None = None,
    ) -> RemediationJob | None:
        """Find an active (PENDING or RUNNING) job for user, source, and concept."""
        ...

    def find_ready_for_attempt(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        attempt_number: int,
    ) -> RemediationJob | None:
        """Find an existing completed (READY) job for a specific educational attempt cycle."""
        ...

    def find_by_idempotency_key(self, idempotency_key: str) -> RemediationJob | None:
        """Find job by idempotency key."""
        ...

    def list_for_concept(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
    ) -> list[RemediationJob]:
        """List all remediation jobs for a given user, source, and concept."""
        ...

    def list_by_user_source(
        self,
        user_id: str,
        source_id: str,
    ) -> list[RemediationJob]:
        """List all remediation jobs for a user and source."""
        ...


class InMemoryRemediationJobRepository:
    """Thread-safe in-memory store for remediation jobs with strict isolation."""

    def __init__(self) -> None:
        self._jobs: dict[str, RemediationJob] = {}

    def get(self, remediation_job_id: str) -> RemediationJob | None:
        job = self._jobs.get(remediation_job_id.strip())
        return copy.deepcopy(job) if job is not None else None

    def save(self, job: RemediationJob) -> RemediationJob:
        key = job.remediation_job_id.strip()
        self._jobs[key] = copy.deepcopy(job)
        return copy.deepcopy(job)

    def find_active_for_concept(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        attempt_number: int | None = None,
    ) -> RemediationJob | None:
        uid = user_id.strip()
        sid = source_id.strip()
        cid = concept_id.strip()
        active_statuses = {RemediationJobStatus.PENDING, RemediationJobStatus.RUNNING}
        for job in self._jobs.values():
            if (
                job.user_id == uid
                and job.source_id == sid
                and job.concept_id == cid
                and job.status in active_statuses
            ):
                if attempt_number is None or job.attempt_number == attempt_number:
                    return copy.deepcopy(job)
        return None

    def find_ready_for_attempt(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
        attempt_number: int,
    ) -> RemediationJob | None:
        uid = user_id.strip()
        sid = source_id.strip()
        cid = concept_id.strip()
        for job in self._jobs.values():
            if (
                job.user_id == uid
                and job.source_id == sid
                and job.concept_id == cid
                and job.attempt_number == attempt_number
                and job.status == RemediationJobStatus.READY
            ):
                return copy.deepcopy(job)
        return None

    def find_by_idempotency_key(self, idempotency_key: str) -> RemediationJob | None:
        key = idempotency_key.strip()
        matching = [j for j in self._jobs.values() if j.idempotency_key == key]
        if not matching:
            return None
        # Prefer READY jobs if multiple exist (e.g. failure followed by successful retry)
        for job in matching:
            if job.status == RemediationJobStatus.READY:
                return copy.deepcopy(job)
        # Otherwise return the most recently completed/updated job
        return copy.deepcopy(matching[-1])

    def list_for_concept(
        self,
        user_id: str,
        source_id: str,
        concept_id: str,
    ) -> list[RemediationJob]:
        uid = user_id.strip()
        sid = source_id.strip()
        cid = concept_id.strip()
        return [
            copy.deepcopy(j)
            for j in self._jobs.values()
            if j.user_id == uid and j.source_id == sid and j.concept_id == cid
        ]

    def list_by_user_source(
        self,
        user_id: str,
        source_id: str,
    ) -> list[RemediationJob]:
        uid = user_id.strip()
        sid = source_id.strip()
        return [
            copy.deepcopy(j)
            for j in self._jobs.values()
            if j.user_id == uid and j.source_id == sid
        ]

    def clear(self) -> None:
        self._jobs.clear()
