"""Offline core acceptance: no hierarchy, vectors, fake sources or forged provenance."""
from __future__ import annotations

import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.reasoning import ReasoningRequest, ReasoningResult, Telemetry
from app.services.educational_content import (
    ContentRequest, EducationalContentService, Purpose, compact_context, teaching_request,
)
from app.services.ingestion.source_ingestion import ingest_source, index_committed_source
from app.services.ingestion.failures import SourceIngestionFailed, SourceIndexFailed
from tests.test_source_supabase import context, Context, OWNER, OTHER

pytestmark = pytest.mark.usefixtures("supabase_storage_mode")


class Provider:
    def __init__(self, raw: str | None = None) -> None:
        self.requests: list[ReasoningRequest] = []
        self.raw = raw or json.dumps({"topic": "Newton's second law", "explanation":
            "Force is mass times acceleration; F = ma.", "key_concepts": [
                {"name": "Acceleration", "explanation": "Rate of change of velocity."}],
            "examples": ["A 2 kg object at 3 m/s² needs 6 N."], "equations": ["F = ma"],
            "relationships": []})

    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        self.requests.append(request)
        return ReasoningResult(response=self.raw, telemetry=Telemetry(provider="ollama",
            task=request.task, outcome="SUCCESS", model="offline-test", transport_latency_seconds=0))


def test_typed_topic_no_source_or_storage(context: Context) -> None:
    remote, repo, _ = context
    provider = Provider()
    result = EducationalContentService(repo, provider).generate(ContentRequest(topic="Newton's laws"))
    assert result.user_id == OWNER and result.status == "READY"
    assert result.source_id is None and result.source_version is None and not result.source_observations
    assert result.provenance_kind == "AI_ENRICHED" and result.equations == ["F = ma"]
    assert not remote.sources and not remote.versions and not remote.calls
    assert len(provider.requests) == 1


def test_optional_structure_and_vectors_not_called(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    remote, repo, path = context
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Optional structure/vector operation entered critical path")
    monkeypatch.setattr("app.services.ingestion.source_ingestion.prepare_knowledge_index", forbidden)
    monkeypatch.setattr("app.db.vector_store.upsert_chunks", forbidden)
    result = ingest_source(repo, path, "fixture.txt")
    assert result["content_ready"] is True and result["chunks_synced"] == 0
    assert result["status"] == "INDEXING"  # Existing DB enum is not redefined as indexed READY.
    assert result["downstream"] == {"knowledge": "NOT_REQUESTED", "indexing": "NOT_REQUESTED"}
    content = EducationalContentService(repo, Provider()).generate(ContentRequest(
        source_id=str(result["source_id"]), source_version=1))
    assert content.source_observations and content.source_version == 1
    assert not any("knowledge_snapshot" in call for call in remote.calls)


def test_default_upload_job_reports_content_ready_not_indexed(context: Context,
        monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from app.api import source_jobs
    from app.services.pipeline_tracker import JobManager
    _, repo, path = context
    manager = JobManager()
    monkeypatch.setattr(source_jobs, "job_manager", manager)
    job = manager.create_job("source_ingestion")
    job.metadata["source_owner"] = repo.owner_id
    asyncio.run(source_jobs.execute_source_job(job.job_id, repo, path, "fixture.txt"))
    assert job.state == "SUCCEEDED" and job.source_lifecycle == "CONTENT_READY"
    assert job.result is not None and job.result["content_ready"] is True


@pytest.mark.parametrize("failure", ["structure", "vectors"])
def test_optional_failure_leaves_extracted_content_usable(context: Context,
        monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    _, repo, path = context
    path.write_text("Newton's second law\n\nF = ma\n\nForce is mass times acceleration.", encoding="utf-8")
    result = ingest_source(repo, path, "physics.txt")
    record = repo.get_source(str(result["source_id"]))
    assert record is not None
    if failure == "structure":
        from app.services.content_understanding import UnderstandingError
        def bad_structure(*args: object) -> None:
            raise UnderstandingError("UNSUPPORTED_EVIDENCE", "LABEL")
        monkeypatch.setattr("app.services.ingestion.source_ingestion.prepare_knowledge_index", bad_structure)
        expected = SourceIngestionFailed
    else:
        from app.services.schemas import RichChunk
        version = repo.get_source_version(record.source_id, 1)
        assert version is not None
        monkeypatch.setattr("app.services.ingestion.source_ingestion.prepare_knowledge_index",
            lambda *args: ([RichChunk.model_validate(r) for r in version.rich_chunks], {}))
        def bad_vectors(*args: object) -> None:
            raise RuntimeError("offline index failure")
        monkeypatch.setattr("app.db.vector_store.upsert_chunks", bad_vectors)
        expected = SourceIndexFailed
    with pytest.raises(expected):
        index_committed_source(repo, record)
    saved = repo.get_source(record.source_id)
    assert saved is not None and saved.status != "FAILED"
    import asyncio
    from app.api import source_jobs
    from app.services.pipeline_tracker import JobManager
    manager = JobManager()
    monkeypatch.setattr(source_jobs, "job_manager", manager)
    job = manager.create_job("source_ingestion")
    job.metadata.update(source_owner=repo.owner_id, source_id=record.source_id)
    asyncio.run(source_jobs.execute_source_job(job.job_id, repo, None, record.filename, record))
    assert job.state == "FAILED"  # Failed optional job, not failed extracted content.
    saved = repo.get_source(record.source_id)
    assert saved is not None and saved.status != "FAILED"
    content = EducationalContentService(repo, Provider()).generate(ContentRequest(
        source_id=record.source_id, source_version=1))
    assert any("F = ma" in o.text for o in content.source_observations)
    assert all(o.source_id == record.source_id and o.source_version == 1 for o in content.source_observations)
    assert content.equations == ["F = ma"]


@pytest.mark.parametrize("purpose", ["notes", "ask", "flowchart", "assessment", "video_plan"])
def test_downstream_shared_inputs(context: Context, purpose: Purpose) -> None:
    _, repo, _ = context
    content = EducationalContentService(repo, Provider()).generate(ContentRequest(topic="Physics"))
    request = teaching_request(content, OWNER, purpose, question="Explain force" if purpose == "ask" else None)
    assert "F = ma" in request.messages[-1].content
    assert "AI_ENRICHED" in request.messages[0].content
    assert "INPUT_DATA" in request.messages[0].content
    with pytest.raises(PermissionError):
        teaching_request(content, OTHER, purpose)


def test_compact_context_deduplicates_without_altering_math() -> None:
    text, omitted = compact_context(["F = ma\n\nE = mc²", "F = ma\n\nE = mc²"])
    assert text == "F = ma\n\nE = mc²" and omitted == 0
    bounded, omitted = compact_context(["F = ma", "a" * 40], budget=12)
    assert bounded == "F = ma" and omitted == 1


def test_model_cannot_supply_source_provenance_or_fake_ready(context: Context) -> None:
    _, repo, _ = context
    with pytest.raises(ValidationError):
        EducationalContentService(repo, Provider('{"topic":"x","explanation":"x","source_id":"fake"}')).generate(
            ContentRequest(topic="Physics"))
    with pytest.raises(ValidationError):
        EducationalContentService(repo, Provider("provider failure text")).generate(ContentRequest(topic="Physics"))


def test_source_scope_foreign_and_exact_version(context: Context) -> None:
    _, repo, _ = context
    from fastapi import HTTPException
    provider = Provider()
    for source_id, version in [("foreign", 1), ("missing", 2)]:
        with pytest.raises(HTTPException) as error:
            EducationalContentService(repo, provider).generate(ContentRequest(source_id=source_id, source_version=version))
        assert error.value.status_code == 404
    assert not provider.requests
    with pytest.raises(ValidationError):
        ContentRequest(source_id="source")
    with pytest.raises(ValidationError):
        ContentRequest(topic="Physics", user_id=str(OTHER))


def test_real_owned_fixture_is_hidden_from_other_repository(context: Context,
        monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from fastapi import HTTPException
    from app.core.supabase import AuthenticatedUser, SupabaseConfig, SupabaseRuntime
    from app.services.repositories.source_repository import SupabaseSourceRepository
    remote, repo, path = context
    saved = ingest_source(repo, path, "fixture.txt")
    provider = Provider()
    runtime = SupabaseRuntime(SupabaseConfig("https://test.supabase.co", "public-test-key"),
                              transport=httpx.MockTransport(remote.request))
    try:
        user = AuthenticatedUser(OTHER, None, {})
        monkeypatch.setattr(runtime, "verify_user", lambda token: user)
        foreign = SupabaseSourceRepository(user, "test-token", runtime)
        with pytest.raises(HTTPException) as denied:
            EducationalContentService(foreign, provider).generate(ContentRequest(
                source_id=str(saved["source_id"]), source_version=1))
        assert denied.value.status_code == 404
    finally:
        runtime.close()
    with pytest.raises(HTTPException) as missing:
        EducationalContentService(repo, provider).generate(ContentRequest(
            source_id=str(saved["source_id"]), source_version=2))
    assert missing.value.status_code == 404 and not provider.requests


def test_previously_failed_source_can_teach_without_rewriting_it(context: Context) -> None:
    remote, repo, path = context
    result = ingest_source(repo, path, "fixture.txt")
    record = repo.get_source(str(result["source_id"]))
    assert record is not None
    repo.mark_status(record, "FAILED", "CONTENT_UNDERSTANDING_FAILED:UNSUPPORTED_EVIDENCE")
    before = json.dumps([remote.sources, remote.versions, remote.units], sort_keys=True)
    content = EducationalContentService(repo, Provider()).generate(ContentRequest(
        source_id=record.source_id, source_version=1))
    assert content.status == "READY" and content.source_observations
    assert json.dumps([remote.sources, remote.versions, remote.units], sort_keys=True) == before


def test_authenticated_api_and_no_forged_owner(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app
    from app.api.sources import source_repository
    _, repo, _ = context
    provider = Provider()
    monkeypatch.setattr("app.services.educational_content.get_reasoning_router", lambda: provider)
    with TestClient(app) as client:
        assert client.post("/educational-content", json={"topic": "Physics"}).status_code == 401
        app.dependency_overrides[source_repository] = lambda: repo
        response = client.post("/educational-content", json={"topic": "Physics"})
        assert response.status_code == 200 and UUID(response.json()["user_id"]) == OWNER
        assert response.json()["source_id"] is None
        assert client.post("/educational-content", json={"topic":"Physics", "user_id":str(OTHER)}).status_code == 422

