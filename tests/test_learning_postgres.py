"""Real disposable PostgreSQL for the canonical new-source storage boundary."""
import copy
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core import postgres
from app.core.config import settings
from app.core.supabase import AuthenticatedUser, SupabaseConfig, SupabaseRuntime, SupabaseAuthenticationError, SupabaseConflict, SupabaseUnavailable, SupabaseResponseError
from app.db.learning_migrations import migrate, grant_runtime
from app.services.ingestion.source_ingestion import ingest_source
from app.services.repositories.source_repository import SupabaseSourceRepository
from app.services.repositories.knowledge_repository import KnowledgeRepository
from app.services.learning_session import LearningSessionService, CreateLearningSession
from tests.video_postgres_fixture import video_cluster, postgres_mode
from tests.test_source_supabase import Remote, OWNER, OTHER, educational_response


@pytest.fixture(scope='module')
def learning_cluster(video_cluster):
    postgres.close_pool()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings,'postgres_dsn',SecretStr(video_cluster['admin']))
        try:
            applied = migrate()
        except postgres.VideoDatabaseError as error:
            pytest.fail('Disposable migration: '+str(error.__context__))
        assert applied == ['learning/001_learning_persistence.sql']
        assert migrate() == []
        grant_runtime('video_runtime')
        postgres.close_pool()
    return video_cluster


@pytest.fixture
def storage(learning_cluster, postgres_mode, monkeypatch, tmp_path):
    monkeypatch.setattr(settings,'source_persistence_provider','postgres')
    monkeypatch.setattr(settings,'database_provider','supabase')
    monkeypatch.setattr(settings,'upload_dir',tmp_path/'uploads')
    monkeypatch.setattr(settings,'registry_dir',tmp_path/'registry')
    postgres.readiness()
    remote = Remote()
    runtime = SupabaseRuntime(SupabaseConfig('https://test.supabase.co','public-test-key'),transport=httpx.MockTransport(remote.request))
    user = AuthenticatedUser(OWNER,None,{})
    monkeypatch.setattr(runtime,'verify_user',lambda token:user)
    repo = SupabaseSourceRepository(user,'test-token',runtime)
    from app.services import structurer
    from app.db import vector_store
    monkeypatch.setattr(structurer,'generate_educational_proposal',educational_response)
    indexed = []
    def index(chunks):
        context = KnowledgeRepository(user,'test-token',repo.runtime)
        assert context.get_knowledge_state(context.scope(chunks[0].source_id,1)).knowledge_state=='READY'
        indexed.extend(chunks)
        return len(chunks)
    monkeypatch.setattr(vector_store,'upsert_chunks',index)
    path = tmp_path/'input.txt'
    path.write_text('Photosynthesis converts light energy into chemical energy. Plants absorb sunlight using chlorophyll.\n\nChlorophyll is the green pigment in leaves that absorbs light for photosynthesis.\nReference '+uuid4().hex)
    yield remote,repo,path,indexed
    runtime.close()


def ready(storage):
    _,repo,path,_ = storage
    result = ingest_source(repo,path,'fixture-'+uuid4().hex+'.txt',enrich=True)
    context = KnowledgeRepository(repo.user,repo._token,repo.runtime)
    scope = context.scope(result['source_id'],1)
    mapping = context.get_complete_knowledge_map(scope)
    return repo,context,scope,mapping


def test_new_upload_content_knowledge_and_index_use_postgres(storage):
    remote = storage[0]
    repo,context,scope,mapping = ready(storage)
    assert not remote.sources and not remote.versions and not remote.units
    assert not any(path.startswith('/rest/v1/rpc/') for path in remote.calls)
    assert mapping.readiness.knowledge_state=='READY' and mapping.topics and mapping.concepts and mapping.evidence
    version = repo.get_source_version(scope.source_id)
    assert version.normalized_content and version.sanitized_content and version.rich_chunks
    assert repo.get_content_units(scope.source_id) and storage[3]
    assert repo.list_sources()[0].source_id==scope.source_id
    assert context.list_concepts(scope,topic_id=mapping.topics[0].topic_id)
    assert context.list_concept_evidence(scope,mapping.concepts[0].concept_id)


def test_session_assessment_submission_and_reconnect(storage):
    repo,context,scope,mapping = ready(storage)
    service = LearningSessionService(context)
    sid = uuid4()
    request = CreateLearningSession(session_id=sid,source_id=scope.source_id,source_version=1,topic_id=mapping.topics[0].topic_id)
    view = service.create(request)
    assert service.create(request).session_id == sid
    cid = mapping.concepts[0].concept_id
    key = 'ASSESS_'+uuid4().hex
    question = dict(question_id='Q_'+uuid4().hex,source_id=scope.source_id,source_version=1,concept_id=cid,
        concept_name='Photosynthesis',stem='What captures light?',options=[{'index':i,'text':str(i)} for i in range(4)],
        correct_index=0,explanation='Evidence',difficulty='foundational',evidence_quote='Evidence',evidence_text='Evidence',
        chunk_ids=[],content_ids=[],evidence_ids=['saved-evidence'],page_start=None,page_end=None,timestamp_start=None,timestamp_end=None)
    payload = dict(session_id=key,student_id=str(OWNER),source_id=scope.source_id,source_version=1,
                   learning_session_id=str(sid),request_hash='a'*64,concept_queue=[cid],questions=[question])
    def transaction(action,payload):
        return repo.runtime.admin_request('POST','/rest/v1/rpc/visualai_assessment_transaction',body={
            'p_action':action,'p_user_id':str(OWNER),'p_assessment_id':key,'p_payload':payload})
    created = transaction('create',payload)
    assert created['learning_session_id']==str(sid)
    assert transaction('create',payload)==created
    submitted = transaction('submit',{'answers':{question['question_id']:0}})
    assert submitted['submission_response']['overall_score']==100
    assert transaction('submit',{'answers':{question['question_id']:0}})==submitted
    with pytest.raises(SupabaseConflict):
        transaction('submit',{'answers':{question['question_id']:1}})
    postgres.close_pool()
    assert transaction('load',{})==submitted
    assert service.repository.get(sid).source_id==scope.source_id
    # Existing progress load uses the local canonical session too.
    progress = repo.runtime.admin_request('POST','/rest/v1/rpc/visualai_learning_transaction',body={
        'p_action':'load','p_user_id':str(OWNER),'p_learning_session_id':str(sid),'p_payload':{}})
    assert progress['revision']==0


def test_rls_and_rpc_reject_foreign_owner(storage):
    repo,context,scope,mapping = ready(storage)
    with postgres.transaction() as connection:
        connection.execute("SELECT set_config('visualai.owner_id',%s,true)",(str(OTHER),))
        assert connection.execute('SELECT source_id FROM visualai_learning.sources WHERE source_id=%s',(scope.source_id,)).fetchall()==[]
    with postgres.transaction() as connection:
        assert connection.execute('SELECT source_id FROM visualai_learning.sources').fetchall()==[]
    with pytest.raises(SupabaseAuthenticationError):
        repo.runtime.admin_request('POST','/rest/v1/rpc/visualai_assessment_transaction',body={
            'p_action':'load','p_user_id':str(OTHER),'p_assessment_id':'foreign','p_payload':{}})
    # Owner check must exist inside SQL as well as the adapter.
    with pytest.raises(postgres.VideoDatabaseError):
        with postgres.transaction() as connection:
            connection.execute("SELECT set_config('visualai.owner_id',%s,true)",(str(OWNER),))
            connection.execute("SELECT visualai_learning.visualai_assessment_transaction('load',%s,'foreign','{}')",(OTHER,))


def test_invalid_ingestion_is_atomic_and_never_falls_back(storage):
    remote,repo,_,_ = storage
    name='bad_'+uuid4().hex
    with pytest.raises(SupabaseResponseError):
        repo.runtime.user_request('POST','/rest/v1/rpc/visualai_commit_source_ingestion',token=repo._token,
            body={'p_source':{'source_id':name,'user_id':str(OWNER)},'p_version':{},'p_units':[]})
    assert not remote.sources and not any('/rpc/' in path for path in remote.calls)
    with postgres.transaction() as connection:
        connection.execute("SELECT set_config('visualai.owner_id',%s,true)",(str(OWNER),))
        assert connection.execute('SELECT source_id FROM visualai_learning.sources WHERE source_id=%s',(name,)).fetchall()==[]


def test_database_failure_does_not_redirect_writes(storage,monkeypatch):
    remote,repo,_,_ = storage
    def fail():
        raise postgres.VideoDatabaseError()
    monkeypatch.setattr(postgres,'get_pool',fail)
    with pytest.raises(SupabaseUnavailable):
        repo.runtime.user_request('POST','/rest/v1/rpc/visualai_commit_source_ingestion',token=repo._token,
            body={'p_source':{},'p_version':{},'p_units':[]})
    assert not remote.calls


def test_canonical_rows_survive_database_restart(storage,learning_cluster):
    repo,context,scope,mapping = ready(storage)
    before = repo.get_source_version(scope.source_id).model_dump(mode='json')
    postgres.close_pool()
    learning_cluster['restart']()
    assert repo.get_source_version(scope.source_id).model_dump(mode='json')==before
    assert context.get_complete_knowledge_map(scope)==mapping


def test_historical_sources_remain_remote(storage):
    remote,repo,_,_ = storage
    new_repo,_,scope,_ = ready(storage)
    record = copy.deepcopy(new_repo.get_source(scope.source_id).model_dump(mode='json'))
    record['source_id']='legacy_'+uuid4().hex
    remote.sources.append(record)
    assert repo.get_source(record['source_id']).source_id==record['source_id']
    assert {r.source_id for r in repo.list_sources()} >= {record['source_id'],scope.source_id}


def test_private_schema_has_no_definers_or_public_access(storage):
    with postgres.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('visualai_learning','visualai_learning_private') AND p.prosecdef").fetchone()[0]==0
        assert connection.execute("SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='visualai_learning' AND c.relkind='r'").fetchone()[0]


def test_invalid_snapshot_preserves_existing_knowledge(storage):
    repo,context,scope,mapping = ready(storage)
    before = mapping.model_dump(mode='json')
    with pytest.raises(SupabaseResponseError):
        repo.runtime.user_request('POST','/rest/v1/rpc/visualai_commit_knowledge_snapshot',token=repo._token,
            body={'p_source_id':scope.source_id,'p_source_version':1,'p_operation_id':str(uuid4()),'p_payload':{'schema_version':1,'topics':[]}})
    assert context.get_complete_knowledge_map(scope).model_dump(mode='json')==before


def test_historical_session_and_assessment_route_without_copying(storage,monkeypatch):
    repo = storage[1]
    observed = []
    sid = str(uuid4())
    def user_request(method,path,**kwargs):
        observed.append(path)
        return []
    def admin_request(method,path,**kwargs):
        observed.append(path)
        return None
    monkeypatch.setattr(repo.runtime.auth,'user_request',user_request)
    monkeypatch.setattr(repo.runtime.auth,'admin_request',admin_request)
    assert repo.runtime.user_request('GET','/rest/v1/learning_sessions',token=repo._token,
        params={'session_id':'eq.'+sid,'select':'*'})==[]
    assert repo.runtime.admin_request('POST','/rest/v1/rpc/visualai_assessment_transaction',body={
        'p_action':'load','p_user_id':str(OWNER),'p_assessment_id':'old-assessment','p_payload':{}}) is None
    assert observed==['/rest/v1/learning_sessions','/rest/v1/rpc/visualai_assessment_transaction']


def test_same_source_commit_is_idempotent(storage):
    repo,_,scope,_ = ready(storage)
    record = repo.get_source(scope.source_id)
    version = repo.get_source_version(scope.source_id)
    units = repo.get_content_units(scope.source_id)
    assert repo.commit_ingestion(record.model_copy(update={'status':'INDEXING'}),version,units)==record


def test_filters_and_token_cannot_escape_owner_scope(storage):
    repo,_,scope,_ = ready(storage)
    assert repo.runtime.user_request('GET','/rest/v1/sources',token=repo._token,
        params={'source_id':'eq.'+scope.source_id,'user_id':'eq.'+str(OTHER),'select':'*'})==[]
    with pytest.raises(SupabaseAuthenticationError):
        repo.runtime.user_request('GET','/rest/v1/sources',token='foreign-token',params={})
    with pytest.raises(SupabaseResponseError):
        repo.runtime.user_request('GET','/rest/v1/sources',token=repo._token,
            params={'source_id':'eq.'+scope.source_id,'order':'source_id; DROP TABLE sources'})
