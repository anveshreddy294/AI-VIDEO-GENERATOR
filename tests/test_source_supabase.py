"""Source-slice contracts without network, models or mutable production storage."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
from uuid import UUID
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue, TypeAdapter

from app.core.config import settings
from app.core.processing_errors import ProcessingCode
from app.core.supabase import AuthenticatedUser, SupabaseConfig, SupabaseRuntime, SupabaseError
from app.services.repositories.factory import get_source_repository
from app.services.repositories.file_repository import FileSourceRepository
from app.services.repositories.source_repository import SourceVersion, SupabaseSourceRepository
from app.services.ingestion.failures import SourceIngestionFailed
from app.services.ingestion.source_ingestion import ingest_source, index_committed_source
from app.services.schemas import ContentUnit, SourceRecord, RichChunk

Context = tuple["Remote", SupabaseSourceRepository, Path]

OWNER = UUID('00000000-0000-4000-8000-000000000001')
OTHER = UUID('00000000-0000-4000-8000-000000000002')
JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


pytestmark = pytest.mark.usefixtures("supabase_storage_mode")


class Remote:
    """Transport fixture for the repository/RPC boundary, not a substitute for SQL tests."""
    def __init__(self) -> None:
        self.sources: list[dict[str, JsonValue]] = []
        self.versions: list[dict[str, JsonValue]] = []
        self.units: list[dict[str, JsonValue]] = []
        self.calls: list[str] = []
        self.reject_commit = False
        self.knowledge: dict[str,list[dict[str,JsonValue]]] = {t:[] for t in
            ('topics','subtopics','concepts','content_concepts','concept_relationships')}

    def request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(path)
        if request.headers.get('authorization') != 'Bearer test-token':
            return httpx.Response(401)
        if request.method == 'GET':
            table = path.rsplit('/',1)[-1]
            rows = {'profiles':[{'id':str(OWNER),'full_name':None,'learning_preferences':{}}], 'sources':self.sources, 'source_versions':self.versions, 'content_units':self.units,**self.knowledge}[table]
            filtered = [dict(row) for row in rows if all(
                not value.startswith('eq.') or str(row.get(key)) == value[3:]
                for key,value in request.url.params.items())]
            select=request.url.params.get('select','*')
            if select!='*':
                selected: list[dict[str,JsonValue]]=[]
                for row in filtered:
                    result:dict[str,JsonValue]={}
                    for field in select.split(',content:')[0].split(','):
                        alias,column=field.split(':') if ':' in field else (field,field)
                        result[alias]=row.get(column)
                    if ',content:' in select:
                        from app.services.repositories.knowledge_repository import METADATA_COLUMNS
                        unit=next(u for u in self.units if u['content_id']==row['content_id'])
                        result['content']={key:unit.get(key) for key in METADATA_COLUMNS.split(',')}
                    selected.append(result)
                filtered=selected
            return httpx.Response(200,json=filtered)
        body = JSON_OBJECT.validate_python(json.loads(request.content))
        if path.endswith('visualai_commit_knowledge_snapshot'):
            proposed=JSON_OBJECT.validate_python(body['p_payload'])
            scope={'user_id':str(OWNER),'source_id':body['p_source_id'],'source_version':body['p_source_version']}
            tables={'topics':'topics','subtopics':'subtopics','concepts':'concepts',
                    'content_concepts':'content_concepts','concept_relationships':'relationships'}
            for table,key in tables.items():
                for r in TypeAdapter(list[dict[str,JsonValue]]).validate_python(proposed[key]):
                    row=scope|r
                    if table=='concepts':
                        associations=TypeAdapter(list[dict[str,JsonValue]]).validate_python(proposed['content_concepts'])
                        row['source_content_ids']=sorted({str(e['content_id']) for e in associations if e['concept_id']==r['concept_id']})
                    self.knowledge[table].append(row)
            committed_at='2026-10-07T00:00:00Z'
            digest=hashlib.sha256(json.dumps(proposed,sort_keys=True).encode()).hexdigest()
            v=next(v for v in self.versions if v['source_id']==body['p_source_id'])
            v.update(knowledge_state='READY',knowledge_schema_version=1,knowledge_operation_id=body['p_operation_id'],
                knowledge_payload_hash=digest,knowledge_committed_at=committed_at)
            return httpx.Response(200,json={'source_id':body['p_source_id'],'source_version':body['p_source_version'],
                'knowledge_state':'READY','schema_version':1,'operation_id':body['p_operation_id'],
                'payload_hash':digest,'committed_at':committed_at})
        if path.endswith('visualai_commit_source_ingestion'):
            if self.reject_commit:
                return httpx.Response(400,json={'message':'do not log this secret test-secret'})
            source = JSON_OBJECT.validate_python(body['p_source'])
            existing = next((row for row in self.sources if row['source_id']==source['source_id']),None)
            if existing:
                return httpx.Response(200,json=existing)
            self.sources.append(source)
            self.versions.append(JSON_OBJECT.validate_python(body['p_version']))
            self.versions[-1].update(knowledge_state='LEGACY_UNMAPPED',knowledge_schema_version=None,
                knowledge_operation_id=None,knowledge_payload_hash=None,knowledge_committed_at=None)
            self.units.extend(TypeAdapter(list[dict[str, JsonValue]]).validate_python(body['p_units']))
            return httpx.Response(200,json=source)
        source = next(row for row in self.sources if row['source_id']==body['p_source_id'])
        source.update(status=body['p_status'],error_message=body['p_error'])
        return httpx.Response(200,json=source)


@pytest.fixture
def context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[tuple[Remote, SupabaseSourceRepository, Path]]:
    remote = Remote()
    runtime = SupabaseRuntime(SupabaseConfig('https://test.supabase.co','public-test-key'),
                              transport=httpx.MockTransport(remote.request))
    repo = SupabaseSourceRepository(AuthenticatedUser(OWNER,None,{}),'test-token',runtime)
    # This suite tests source transport/orchestration, not token cryptography or real RLS.
    # The separate SQL-backed and live suites retain actual tenant enforcement.
    monkeypatch.setattr(runtime,'verify_user',lambda access: repo.user)
    from app.services import structurer
    monkeypatch.setattr(structurer,'generate_educational_proposal',educational_response)
    monkeypatch.setattr(settings,'database_provider','supabase')
    monkeypatch.setattr(settings,'upload_dir',tmp_path/'uploads')
    monkeypatch.setattr(settings,'registry_dir',tmp_path/'registry')
    path = tmp_path/'fixture.txt'
    path.write_text('Photosynthesis converts light energy into chemical energy. Plants absorb sunlight using chlorophyll.\n\nChlorophyll is the green pigment in leaves that absorbs light for photosynthesis.')
    yield remote,repo,path
    runtime.close()


def educational_response(prompt: str) -> str:
    material=json.loads(prompt.split('SOURCE_DATA=',1)[1].split('\nREPAIR:',1)[0])
    unit=material[0]; quote=unit['text'].split('.')[0]+'.'
    name='Osmosis' if 'Osmosis' in quote else 'Photosynthesis'
    e={'content_id':unit['content_id'],'quote':quote,'role':'EXPLANATION'}
    return json.dumps({'topics':[{'key':'t','title':name,'evidence':[e]}],
        'subtopics':[{'key':'s','topic_key':'t','title':name,'evidence':[e]}],
        'concepts':[{'key':'c','subtopic_key':'s','name':name,'definition':quote,'evidence':[e]}],
        'prerequisites':[]})


@pytest.mark.parametrize('source_type',['pdf','txt','image','video'])
def test_source_type_roundtrip_and_owner_overwrite(context: Context, source_type: str) -> None:
    _,repo,_=context
    record=SourceRecord(filename='x',source_type=source_type,mime_type='x',file_hash='hash',file_size=1,user_id=str(OTHER))
    row=repo.encode_source(record)
    assert row['user_id']==str(OWNER)
    assert row['source_type']==source_type and 'modality' not in row
    assert repo.decode_source(row).source_type==source_type


def test_no_provider_fallback_even_without_url(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings,'supabase_url','')
    with pytest.raises(SupabaseError):
        get_source_repository()
    from app.services.registry import _load_sources_index
    with pytest.raises(RuntimeError,match='local source access is disabled'):
        _load_sources_index()


def test_commit_before_qdrant_and_no_source_json(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    remote,repo,path=context
    from app.db import vector_store
    seen: list[RichChunk] = []
    def index(chunks: list[RichChunk]) -> int:
        assert len(remote.sources)==len(remote.versions)==1 and remote.units
        assert all(chunk.user_id==str(OWNER) and chunk.source_type=='txt' and chunk.content_id in chunk.content_ids for chunk in chunks)
        seen.extend(chunks)
        return len(chunks)
    monkeypatch.setattr(vector_store,'upsert_chunks',index)
    result=ingest_source(repo,path,'fixture.txt', enrich=True)
    assert result['status']=='READY' and seen
    assert not list(settings.registry_dir.rglob('sources_index.json'))
    assert not list(settings.registry_dir.rglob('content_units.json'))
    assert not list(settings.registry_dir.rglob('source_versions.json'))
    assert repo.get_source_version(result['source_id']).file_location


def test_commit_failure_never_calls_qdrant_or_local_fallback(context: Context, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    remote,repo,path=context
    remote.reject_commit=True
    from app.db import vector_store
    def forbidden(chunks: list[RichChunk]) -> int:
        pytest.fail('Qdrant called before successful canonical commit')
    monkeypatch.setattr(vector_store,'upsert_chunks',forbidden)
    with pytest.raises(SourceIngestionFailed) as error:
        ingest_source(repo,path,'fixture.txt', enrich=True)
    assert not remote.sources and not remote.versions and not remote.units
    assert 'test-secret' not in str(error.value)+caplog.text
    assert not (settings.registry_dir/'sources_index.json').exists()


def test_qdrant_failure_and_deterministic_retry_without_extraction(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    remote,repo,path=context
    from app.db import vector_store
    def fail(chunks: list[RichChunk]) -> int:
        raise RuntimeError('secret should not appear in persisted failure')
    monkeypatch.setattr(vector_store,'upsert_chunks',fail)
    with pytest.raises(SupabaseError,match='retry this source'):
        ingest_source(repo,path,'fixture.txt', enrich=True)
    assert len(remote.sources)==len(remote.versions)==1 and remote.units
    assert remote.sources[0]['status']=='FAILED'
    assert remote.sources[0]['error_message']=='QDRANT_INDEX_FAILED:RuntimeError'
    old_ids=[row['content_id'] for row in remote.units]
    from app.services.ingestion import source_ingestion
    monkeypatch.setattr(source_ingestion,'dispatch',lambda *args,**kwargs: pytest.fail('Retry extracted again'))
    monkeypatch.setattr(vector_store,'upsert_chunks',lambda chunks:len(chunks))
    result=ingest_source(repo,path,'fixture.txt', enrich=True)
    assert result['status']=='READY'
    assert len(remote.sources)==len(remote.versions)==1
    assert old_ids==[row['content_id'] for row in remote.units]


def test_fresh_repository_reads_canonical_rows(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    remote,repo,path=context
    from app.db import vector_store
    monkeypatch.setattr(vector_store,'upsert_chunks',lambda chunks:len(chunks))
    result=ingest_source(repo,path,'fixture.txt', enrich=True)
    fresh=SupabaseSourceRepository(repo.user,'test-token',repo.runtime)
    assert fresh.get_source(result['source_id']).status=='READY'
    assert fresh.get_source_version(result['source_id']).version==1
    assert fresh.get_content_units(result['source_id'])
    other=SupabaseSourceRepository(AuthenticatedUser(OTHER,None,{}),'test-token',repo.runtime)
    assert other.get_source(result['source_id']) is None
    assert other.get_source_version(result['source_id'],1) is None
    assert other.get_content_units(result['source_id'],1)==[]


def test_explicit_file_provider_remains_available(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings,'database_provider','file')
    assert isinstance(get_source_repository(),FileSourceRepository)
    from app.services.registry import register_source,load_content_units
    _,_,path=context
    record,_=register_source(path,'fixture.txt')
    assert get_source_repository().get_source(record.source_id)


def test_supabase_source_routes_require_auth(context: Context) -> None:
    from app.main import app
    client=TestClient(app)
    assert client.get('/sources').status_code==401
    assert client.get('/sources/SRC_any').status_code==401
    assert client.post('/upload?student_id='+str(OWNER),files={'file':('fixture.txt',b'content','text/plain')}).status_code==401
    assert client.post('/pipeline/upload-and-assess?student_id='+str(OWNER),files={'file':('fixture.txt',b'content','text/plain')}).status_code==401


def test_payload_identity_cannot_override_auth_dependency(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import sources
    from app.main import app
    _,repo,_=context
    monkeypatch.setattr(sources,'get_runtime',lambda:repo.runtime)
    monkeypatch.setattr(sources,'get_current_user',lambda token,runtime:repo.user)
    from app.services.ingestion import source_ingestion
    def accepted(repository: SupabaseSourceRepository, path: Path, filename: str) -> dict[str, JsonValue]:
        assert repository.owner_id==str(OWNER)
        return {'status':'READY','source_id':'SRC_test'}
    monkeypatch.setattr(source_ingestion,'ingest_source',accepted)
    result=TestClient(app).post('/upload?student_id='+str(OTHER)+'&user_id='+str(OTHER),
        headers={'Authorization':'Bearer test-token'},files={'file':('fixture.txt',b'content','text/plain')})
    assert result.status_code==200


def test_partial_vector_count_never_ready(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    remote,repo,path=context
    from app.db import vector_store
    monkeypatch.setattr(vector_store,'upsert_chunks',lambda chunks:0)
    with pytest.raises(SupabaseError):
        ingest_source(repo,path,'fixture.txt', enrich=True)
    assert remote.sources[0]['status']=='FAILED'


def test_separate_source_or_unit_writes_rejected(context: Context) -> None:
    _,repo,_=context
    record=SourceRecord(filename='x',source_type='txt',mime_type='text/plain',file_hash='h',file_size=1)
    with pytest.raises(SupabaseError,match='atomic ingestion'):
        repo.save_source(record)
    with pytest.raises(SupabaseError,match='atomic ingestion'):
        repo.save_content_units(record.source_id,[])


def test_background_source_job_has_no_assessment_or_token_leak(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import sources, pipeline, source_jobs
    from app.services.pipeline_tracker import JobManager
    from app.main import app
    from app.db import vector_store
    remote, repo, path = context
    manager = JobManager()
    monkeypatch.setattr(pipeline, 'job_manager', manager)
    monkeypatch.setattr(source_jobs, 'job_manager', manager)
    monkeypatch.setattr(sources, 'get_runtime', lambda: repo.runtime)
    monkeypatch.setattr(sources, 'get_current_user', lambda token, runtime: repo.user if token == 'test-token' else AuthenticatedUser(OTHER, None, {}))
    monkeypatch.setattr(vector_store, 'upsert_chunks', lambda chunks: len(chunks))
    client = TestClient(app)
    response = client.post('/pipeline/upload-and-assess?student_id=attacker', headers={'Authorization': 'Bearer test-token'},
        files={'file': ('fixture.txt', path.read_bytes(), 'text/plain')})
    assert response.status_code == 200
    job_id = response.json()['job_id']
    snapshot = client.get('/pipeline/jobs/' + job_id, headers={'Authorization': 'Bearer test-token'})
    assert snapshot.json()['status'] == 'completed'
    assert snapshot.json()['current_stage'] == 'content_ready'
    assert snapshot.json()['result']['content_ready'] is True
    assert snapshot.json()['result']['downstream']['indexing'] == 'NOT_REQUESTED'
    assert 'assessment' not in snapshot.json()['result']
    assert 'test-token' not in snapshot.text and 'public-test-key' not in snapshot.text
    assert client.get('/pipeline/jobs/' + job_id, headers={'Authorization': 'Bearer other-token'}).status_code == 404
    assert len(remote.sources) == len(remote.versions) == 1


def test_graph_artifact_is_not_needed_for_canonical_ready(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.ingestion import source_ingestion
    from app.db import vector_store
    remote, repo, path = context
    def artifact_failure(source_id: str, graph: object) -> None:
        raise OSError('filesystem unavailable')
    from app.services import registry
    monkeypatch.setattr(registry, 'save_knowledge_graph', artifact_failure)
    monkeypatch.setattr(vector_store, 'upsert_chunks', lambda chunks: len(chunks))
    assert ingest_source(repo,path,'fixture.txt', enrich=True)['knowledge_state']=='READY'
    assert remote.sources[0]['status']=='READY'
    assert not list(settings.registry_dir.rglob('knowledge_graph.json'))
    record = repo.get_source(str(remote.sources[0]['source_id']))
    assert record is not None
    assert index_committed_source(repo, record)['status'] == 'READY'


def test_legacy_source_evidence_cannot_bypass_supabase(context: Context) -> None:
    from app.services.registry import load_rich_chunks, load_normalized_records, load_sanitized_records, load_quarantine_records
    with pytest.raises(RuntimeError, match='local source chunks are disabled'):
        load_rich_chunks('SRC_fixture')
    for reader in [load_normalized_records, load_sanitized_records, load_quarantine_records]:
        with pytest.raises(RuntimeError, match='local source evidence is disabled'):
            reader(str(OWNER), 'SRC_fixture', 'v1')


def test_repaired_small_txt_job_succeeds_without_vision(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from app.api import source_jobs
    from app.services import dispatcher, extractor
    from app.services.pipeline_tracker import JobManager
    from app.db import vector_store
    remote, repo, path = context
    manager = JobManager()
    monkeypatch.setattr(source_jobs, 'job_manager', manager)
    def forbidden(*args: object, **kwargs: object) -> str:
        pytest.fail('TXT invoked vision')
    monkeypatch.setattr(dispatcher, 'describe_image_file', forbidden)
    monkeypatch.setattr(extractor, 'describe_image', forbidden)
    monkeypatch.setattr(vector_store, 'upsert_chunks', lambda chunks: len(chunks))
    job = manager.create_job('source_ingestion')
    asyncio.run(source_jobs.execute_source_job(job.job_id, repo, path, 'fixture.txt', enrich=True))
    assert job.state == 'SUCCEEDED' and job.result['status'] == 'READY'
    assert len(remote.sources) == len(remote.versions) == 1 and remote.units
    assert remote.sources[0]['status'] == 'READY'


def test_structuring_timeout_fails_job_without_persisting_concepts(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from app.api import source_jobs
    from app.services import structurer
    from app.services.pipeline_tracker import JobManager
    remote, repo, path = context
    manager = JobManager()
    monkeypatch.setattr(source_jobs, 'job_manager', manager)
    def timeout(prompt: str) -> str:
        raise TimeoutError('secret password raw model prompt')
    monkeypatch.setattr(structurer, 'generate_educational_proposal', timeout)
    job = manager.create_job('source_ingestion')
    asyncio.run(source_jobs.execute_source_job(job.job_id, repo, path, 'fixture.txt', enrich=True))
    assert job.state == 'FAILED' and job.is_finished
    assert job.failure.stage == 'STRUCTURING'
    assert job.failure.code == 'MODEL_TIMEOUT' and job.failure.retryable
    assert remote.sources and remote.versions and remote.units
    assert not remote.knowledge['concepts']
    assert 'secret password' not in json.dumps(job.model_dump())


def test_large_grounded_txt_commits_all_units(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    import re
    from app.services import structurer
    from app.db import vector_store
    remote, repo, path = context
    original = path.read_text(encoding='utf-8')
    paragraphs: list[str] = []
    while len('\n\n'.join(paragraphs)) < 32000:
        paragraphs.append(f'Photosynthesis review {len(paragraphs) + 1}\n' + original +
                          ' Example: a plant receiving light can use photosynthesis to store chemical energy in glucose.')
    text = '\n\n'.join(paragraphs)
    path.write_text(text, encoding='utf-8')
    calls: list[str] = []
    def generate(prompt: str) -> str:
        calls.append(prompt)
        return educational_response(prompt)
    monkeypatch.setattr(structurer, 'generate_educational_proposal', generate)
    monkeypatch.setattr(vector_store, 'upsert_chunks', lambda chunks: len(chunks))
    result = ingest_source(repo, path, 'large_grounded.txt', enrich=True)
    assert result['status'] == 'READY' and len(calls) == 1
    assert len(remote.units) == len([part for part in text.split('\n\n') if part.strip()])
    assert all(row['text'] in text for row in remote.units)
    assert 0 < result['chunks_synced'] <= len(remote.units)
    assert result['understanding_metrics']['chunk_quality']['unassigned_content_ids']==[]
    from app.services.content_understanding import MAX_MODEL_INPUT_TOKENS
    from app.services.chunker import _token_len
    assert all(_token_len(prompt) <= MAX_MODEL_INPUT_TOKENS for prompt in calls)


@pytest.mark.parametrize('code', ['EMBEDDING_MODEL_UNAVAILABLE','EMBEDDING_FAILED','VECTOR_INDEX_FAILED'])
def test_index_failure_reason_is_durable_and_observable(context: Context, monkeypatch: pytest.MonkeyPatch, code: ProcessingCode) -> None:
    import asyncio
    from app.api import source_jobs
    from app.db import vector_store
    from app.core.processing_errors import ProcessingError
    from app.services.pipeline_tracker import JobManager
    remote, repo, path = context
    manager = JobManager()
    monkeypatch.setattr(source_jobs, 'job_manager', manager)
    def fail(chunks: list[RichChunk]) -> int:
        raise ProcessingError(code, 'Safe embedding failure')
    monkeypatch.setattr(vector_store, 'upsert_chunks', fail)
    job = manager.create_job('source_ingestion')
    asyncio.run(source_jobs.execute_source_job(job.job_id, repo, path, 'fixture.txt', enrich=True))
    assert job.state == 'FAILED' and job.failure.stage == 'INDEXING'
    assert job.failure.reason_code == code
    assert remote.sources[0]['status'] == 'FAILED' and remote.sources[0]['error_message'] == code


@pytest.mark.parametrize('code', ['MODEL_UNAVAILABLE','INVALID_MODEL_OUTPUT','NO_GROUNDED_CONCEPTS'])
def test_structuring_failure_reasons_stay_distinct(context: Context, monkeypatch: pytest.MonkeyPatch, code: ProcessingCode) -> None:
    import asyncio
    from app.api import source_jobs
    from app.services import structurer
    from app.core.processing_errors import ProcessingError
    from app.services.pipeline_tracker import JobManager
    remote, repo, path = context
    manager = JobManager()
    monkeypatch.setattr(source_jobs, 'job_manager', manager)
    def generate(prompt: str) -> str:
        if code == 'NO_GROUNDED_CONCEPTS': return '{"concepts":[]}'
        if code == 'INVALID_MODEL_OUTPUT': return 'invalid JSON'
        raise ProcessingError('MODEL_UNAVAILABLE', 'Reasoning model unavailable')
    monkeypatch.setattr(structurer, 'generate_educational_proposal', generate)
    job = manager.create_job('source_ingestion')
    asyncio.run(source_jobs.execute_source_job(job.job_id, repo, path, 'fixture.txt', enrich=True))
    assert job.state=='FAILED'
    assert (job.failure.reason_code==code if code=='MODEL_UNAVAILABLE' else job.failure.code=='INVALID_MODEL_OUTPUT')
    assert remote.sources and remote.versions and remote.units
    assert not remote.knowledge['concepts']


@pytest.mark.parametrize("hint,expected", [("complex_diagram", 200), ("arbitrary-model", 422)])
def test_visual_workload_metadata_is_validated_and_owner_comes_from_jwt(context: Context, monkeypatch: pytest.MonkeyPatch, hint: str, expected: int) -> None:
    from app.api import sources, pipeline, source_jobs
    from app.services.pipeline_tracker import JobManager
    from app.services.visual_router import VisualSignals
    from app.main import app
    _, repo, path = context
    manager = JobManager()
    monkeypatch.setattr(pipeline, "job_manager", manager)
    monkeypatch.setattr(source_jobs, "job_manager", manager)
    monkeypatch.setattr(sources, "get_runtime", lambda: repo.runtime)
    monkeypatch.setattr(sources, "get_current_user", lambda token, runtime: repo.user)
    captured: list[VisualSignals] = []
    def accepted(repository: SupabaseSourceRepository, path: Path, filename: str, *, routing_signals: VisualSignals, file_truth: object = None, enrich: bool = False) -> dict[str, JsonValue]:
        assert repository.owner_id == str(OWNER)
        captured.append(routing_signals)
        return {"source_id": "SRC_fixture", "status": "READY"}
    monkeypatch.setattr(source_jobs, "ingest_source", accepted)
    response = TestClient(app).post("/pipeline/upload-and-assess", params={"visual_workload": hint, "student_id": str(OTHER)}, headers={"Authorization": "Bearer test-token"}, files={"file": ("fixture.txt", path.read_bytes(), "text/plain")})
    assert response.status_code == expected
    if expected == 200:
        assert len(captured) == 1 and captured[0].complexity == "COMPLEX"
    else:
        assert captured == []



def test_ready_duplicate_never_reindexes_or_downgrades(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db import vector_store
    remote,repo,path=context
    monkeypatch.setattr(vector_store,"upsert_chunks",lambda chunks:len(chunks))
    initial=ingest_source(repo,path,"fixture.txt", enrich=True)
    def forbidden(chunks: list[RichChunk]) -> int:
        pytest.fail("READY retry must not write vectors")
    monkeypatch.setattr(vector_store,"upsert_chunks",forbidden)
    repeated=ingest_source(repo,path,"fixture.txt", enrich=True)
    assert initial["source_id"]==repeated["source_id"]
    assert repeated["understanding_metrics"]["qdrant_writes"]==0
    assert remote.sources[0]["status"]=="READY" and len(remote.sources)==len(remote.versions)==1


def test_source_cancel_waits_for_actual_publication(context: Context,monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import threading
    from app.api import source_jobs
    from app.services.pipeline_tracker import JobManager
    _,repo,path=context
    manager=JobManager();monkeypatch.setattr(source_jobs,"job_manager",manager)
    started=threading.Event();release=threading.Event()
    def ingest(repository: SupabaseSourceRepository, source: Path, filename: str, *, enrich: bool = False) -> dict[str,JsonValue]:
        started.set();assert release.wait(5)
        return {"source_id":"SRC_cancel","status":"READY","knowledge_state":"READY"}
    monkeypatch.setattr(source_jobs,"ingest_source",ingest)
    async def scenario() -> None:
        job,_=await manager.get_or_create_active_job("cancel",job_type="source_ingestion")
        job.metadata["source_owner"]=repo.owner_id
        task=asyncio.create_task(source_jobs.execute_source_job(job.job_id,repo,path,"fixture.txt", enrich=True))
        assert await asyncio.to_thread(started.wait,5)
        await manager.cancel_job(job.job_id)
        assert not job.is_finished
        release.set();await task
        assert job.state=="SUCCEEDED" and job.source_lifecycle=="READY" and job.error is None
    asyncio.run(scenario())


def test_lost_ready_ack_is_reconciled_without_second_index(context: Context,monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from app.api import source_jobs
    from app.services.pipeline_tracker import JobManager
    from app.db import vector_store
    from uuid import NAMESPACE_URL,uuid5
    remote,repo,path=context
    manager=JobManager();monkeypatch.setattr(source_jobs,"job_manager",manager)
    writes: list[int]=[]
    monkeypatch.setattr(vector_store,"upsert_chunks",lambda chunks:writes.append(len(chunks)) or len(chunks))
    original=repo.mark_status
    def lost(record: SourceRecord,status: str,error_message: str | None = None) -> SourceRecord:
        result=original(record,status,error_message)
        if status=="READY":raise SupabaseError("acknowledgement unavailable")
        return result
    monkeypatch.setattr(repo,"mark_status",lost)
    async def scenario() -> None:
        job,_=await manager.get_or_create_active_job("lost",job_type="source_ingestion")
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        job.metadata.update(source_owner=repo.owner_id,source_id="SRC_"+uuid5(NAMESPACE_URL,f"visualai:{repo.owner_id}:fixture.txt:{digest}").hex)
        await source_jobs.execute_source_job(job.job_id,repo,path,"fixture.txt", enrich=True)
        assert job.state=="SUCCEEDED" and remote.sources[0]["status"]=="READY"
        assert len(writes)==1
    asyncio.run(scenario())
