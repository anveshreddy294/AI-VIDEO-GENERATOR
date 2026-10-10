"""Regression contracts for strict teaching, cloud fallback and observational polling."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import settings
from app.core.reasoning import ProviderFailure, ProviderPolicy, ReasoningProviderRouter, ReasoningResult, Telemetry
from app.services.educational_content import ContentRequest, EducationalContentService, teaching_request
from app.services.pipeline_tracker import JobManager
from tests.test_source_supabase import context, Context
from tests.test_educational_content import Provider

pytestmark = pytest.mark.usefixtures("supabase_storage_mode")


@pytest.mark.parametrize("explanation,expected", [
    ("Force is mass times acceleration.", "Force is mass times acceleration."),
    (["Force changes motion.", "F = ma."], "Force changes motion.\n\nF = ma."),
    ({"overview": "Force changes motion.", "sections": [{"title": "Equation", "content": ["F = ma."]}]},
     "Force changes motion.\n\nEquation\n\nF = ma."),
])
def test_explanation_shapes_normalize_to_canonical_string(context: Context, explanation, expected):
    _, repo, _ = context
    provider = Provider(json.dumps({"topic": "Force", "explanation": explanation}))
    content = EducationalContentService(repo, provider).generate(ContentRequest(topic="Force"))
    assert content.explanation == expected
    assert provider.requests[0].response_schema["properties"]["explanation"]["type"] == "string"


@pytest.mark.parametrize("extra", [
    {"mathematical_notation": ["F = ma", {"symbol": "m", "meaning": "Mass in kg"}]},
    {"common_misconceptions": ["Mass and weight are identical.", {"misconception": "Force maintains velocity", "correction": "Net force changes velocity"}]},
    {"mathematical_notation": "F = ma", "common_misconceptions": {"misconception": "Mass is weight", "correction": "Weight is a force"}},
])
def test_optional_teaching_fields_are_validated_and_persisted(context: Context, extra):
    _, repo, _ = context
    service = EducationalContentService(repo, Provider(json.dumps({"topic": "Force", "explanation": "F = ma", **extra})))
    content = service.generate(ContentRequest(topic="Force"))
    stored = service.get_lesson(str(content.content_id))
    assert stored and stored.content.model_dump() == content.model_dump()
    request = teaching_request(content, content.user_id, "notes")
    assert all(key in request.messages[-1].content for key in extra)


@pytest.mark.parametrize("payload", [
    {"topic": "Force"},
    {"topic": "Force", "explanation": 42},
    {"topic": "Force", "explanation": {"source_id": "forged", "text": "F = ma"}},
    {"topic": "Force", "explanation": [42]},
    {"topic": "Force", "explanation": "F = ma", "unknown": True},
    {"topic": "Force", "explanation": "F = ma", "examples": [42]},
    {"topic": "Force", "explanation": "F = ma", "key_concepts": [42]},
    {"topic": "Force", "explanation": "F = ma", "mathematical_notation": [{"symbol": "F", "source_id": "forged"}]},
    {"topic": "Force", "explanation": "F = ma", "common_misconceptions": [{"misconception": "False"}]},
])
def test_bad_teaching_is_not_coerced_or_saved(context: Context, payload):
    _, repo, _ = context
    service = EducationalContentService(repo, Provider(json.dumps(payload)))
    before = service.list_lessons()
    with pytest.raises(ValidationError):
        service.generate(ContentRequest(topic="Force"))
    assert service.list_lessons() == before


def test_malformed_model_json_has_controlled_api_error(context: Context, monkeypatch):
    from app.main import app
    from app.api.sources import source_repository
    _, repo, _ = context
    monkeypatch.setattr("app.services.educational_content.get_reasoning_router", lambda: Provider('{"explanation":broken-private-content'))
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: repo
        response = client.post('/educational-content', json={"topic": "Force"})
    assert response.status_code == 422
    assert response.json()['detail']['retryable'] is True
    assert 'broken-private-content' not in response.text


class CountingProvider:
    def __init__(self, value, provider):
        self.value, self.provider, self.calls = value, provider, 0

    def generate(self, request):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return ReasoningResult(response=self.value, telemetry=Telemetry(provider=self.provider,
            task=request.task, outcome='SUCCESS', model='test-model', transport_latency_seconds=0))


@pytest.mark.parametrize('failure', ['invalid', '502', 'valid'])
def test_lesson_router_validates_cloud_and_local_identically(context: Context, failure):
    _, repo, _ = context
    valid = json.dumps({'topic': 'Force', 'explanation': 'F = ma'})
    primary = CountingProvider(valid if failure == 'valid' else 'invalid' if failure == 'invalid' else ProviderFailure('PROVIDER_UNAVAILABLE', True), 'cloudflare')
    fallback = CountingProvider(valid, 'ollama')
    policy = ProviderPolicy('https://worker.test', SecretStr('test-secret'), retry_backoff=0)
    router = ReasoningProviderRouter(primary, fallback, policy)
    result = EducationalContentService(repo, router).generate(ContentRequest(topic='Force'))
    assert result.explanation == 'F = ma'
    assert primary.calls == (2 if failure == '502' else 1)
    assert fallback.calls == (0 if failure == 'valid' else 1)
    assert result.provenance['provider'] == ('cloudflare' if failure == 'valid' else 'ollama')


def test_invalid_fallback_cannot_publish_lesson(context: Context):
    _, repo, _ = context
    primary, fallback = CountingProvider('bad', 'cloudflare'), CountingProvider('bad', 'ollama')
    router = ReasoningProviderRouter(primary, fallback, ProviderPolicy('https://worker.test', SecretStr('test-secret')))
    service = EducationalContentService(repo, router)
    before = service.list_lessons()
    with pytest.raises(ProviderFailure, match='INVALID_RESPONSE'):
        service.generate(ContentRequest(topic='Force'))
    assert primary.calls == fallback.calls == 1 and service.list_lessons() == before


def test_polling_failed_source_never_runs_recovery(context: Context, monkeypatch):
    from app.api import pipeline
    _, repo, _ = context
    manager = JobManager()
    monkeypatch.setattr(pipeline, 'job_manager', manager)
    job = manager.create_job('source_ingestion')
    job.metadata.update(source_owner=repo.owner_id, source_id='owned-source')
    asyncio.run(manager.fail_job(job.job_id, 'INDEXING', 'Index unavailable'))
    def forbidden(*args):
        pytest.fail('Polling attempted source recovery or a database operation')
    monkeypatch.setattr(repo, 'get_source', forbidden)
    for _ in range(3):
        snapshot = asyncio.run(pipeline.get_job_status(job.job_id, repo))
        assert snapshot['status'] == 'failed' and snapshot['is_finished']


def test_job_queue_deadline_is_terminal(context: Context, monkeypatch):
    from app.api import source_jobs
    _, repo, path = context
    manager = JobManager()
    manager._semaphore = asyncio.Semaphore(0)
    monkeypatch.setattr(source_jobs, 'job_manager', manager)
    monkeypatch.setattr(settings, 'source_job_timeout_seconds', .01)
    job = manager.create_job('source_ingestion')
    job.metadata.update(source_owner=repo.owner_id)
    asyncio.run(source_jobs.execute_source_job(job.job_id, repo, path, 'fixture.txt'))
    assert job.is_finished and job.status == 'failed'
    assert job.failure.code == 'SOURCE_JOB_TIMEOUT'


def test_worker_wait_heartbeats_do_not_start_duplicate_work(context: Context, monkeypatch):
    from app.api import source_jobs
    manager = JobManager()
    monkeypatch.setattr(source_jobs, 'job_manager', manager)
    monkeypatch.setattr(source_jobs, 'SOURCE_HEARTBEAT_SECONDS', .005)
    job = manager.create_job('source_ingestion')
    calls = []
    async def work():
        calls.append(1)
        await asyncio.sleep(.03)
        return {'content_ready': True}
    async def scenario():
        import time
        result = await source_jobs.wait_for_source_worker(job.job_id, asyncio.create_task(work()), time.monotonic())
        assert result['content_ready']
    asyncio.run(scenario())
    assert calls == [1] and len(job.events) >= 1


def test_cloud_background_concurrency_is_not_ollama_limit(monkeypatch):
    monkeypatch.setattr(settings, 'max_background_jobs', 3)
    monkeypatch.setattr(settings, 'ollama_max_concurrency', 1)
    assert JobManager().get_semaphore()._value == 3


def test_source_availability_uses_bounded_owner_query(context: Context, monkeypatch):
    _, repo, path = context
    from app.services.ingestion.source_ingestion import ingest_source
    result = ingest_source(repo, path, 'fixture.txt')
    calls = []
    original = repo.runtime.user_request
    def track(method, route, **kwargs):
        calls.append(kwargs.get('params', {}))
        return original(method, route, **kwargs)
    monkeypatch.setattr(repo.runtime, 'user_request', track)
    assert repo.has_content_units(result['source_id'], 1)
    assert calls[0]['select'] == 'content_id,user_id' and calls[0]['limit'] == '1'
    assert calls[0]['user_id'] == 'eq.' + repo.owner_id
    assert calls[0]['source_version'] == 'eq.1'


def test_uploaded_material_opens_existing_learning_resources(context: Context, monkeypatch):
    from app.main import app
    from app.api.sources import source_repository
    from tests.test_educational_lesson_features import MockProvider
    _, repo, _ = context
    monkeypatch.setattr('app.services.educational_content.get_reasoning_router', lambda: MockProvider())
    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: repo
        response = client.post('/pipeline/upload-and-assess', files={
            'file': ('bst.txt', b'Binary search trees order smaller keys left and larger keys right.', 'text/plain')})
        assert response.status_code == 200
        job = client.get('/pipeline/jobs/' + response.json()['job_id']).json()
        assert job['status'] == 'completed' and job['is_finished']
        assert job['source_lifecycle'] == 'CONTENT_READY'
        source_id = job['result']['source_id']
        sources = client.get('/sources').json()['sources']
        assert any(s['source_id'] == source_id and s['content_ready'] for s in sources)
        lesson = client.post('/educational-content', json={'source_id': source_id, 'source_version': 1})
        assert lesson.status_code == 200
        assert lesson.json()['source_observations'] and lesson.json()['key_concepts']
        base = '/educational-content/' + lesson.json()['content_id']
        assert client.post(base + '/notes', json={'detail_level': 'detailed'}).json()['detail_level'] == 'detailed'
        assert client.post(base + '/diagram').status_code == 200
        assessment = client.post(base + '/assessment').json()
        assert 'correct_index' not in assessment['mcqs'][0]
        submission = client.post(base + '/assessment/submit', json={
            'mcq_answers': {q['question_id']: 0 for q in assessment['mcqs']},
            'descriptive_answer': 'Compare keys and select the correct subtree.'})
        assert submission.status_code == 200 and submission.json()['descriptive_feedback']
        answer = client.post(base + '/ask', json={'question': 'How are smaller keys searched?'})
        assert answer.status_code == 200
        assert answer.json()['citations'] and all(c['source_id'] == source_id for c in answer.json()['citations'])
        service = EducationalContentService(repo, MockProvider())
        content = service.get_lesson(lesson.json()['content_id']).content
        plan = service.create_video_plan(content)
        assert plan.narration_script and len(plan.scenes) >= 3
