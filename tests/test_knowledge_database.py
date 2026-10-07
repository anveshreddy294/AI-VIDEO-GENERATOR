"""Real, disposable PostgreSQL tests; never connect to a configured Supabase DSN.

Set VISUALAI_KNOWLEDGE_TEST_PG_BIN to a local PostgreSQL 17 bin directory.
The fixture creates its own cluster, binds loopback, and stops it on completion.
Auth claims emulate PostgREST's verified identity boundary; HTTP JWT verification
remains covered by test_supabase_runtime and test_phase6a1_security.
"""
from __future__ import annotations

import copy
import json
import os
import socket
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias
from uuid import uuid4

import pytest

Json: TypeAlias = None | bool | int | float | str | list['Json'] | dict[str, 'Json']
OWNER = '00000000-0000-4000-8000-000000000001'
OTHER = '00000000-0000-4000-8000-000000000002'
ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    '20261005185233_corrected_foundation_schema.sql',
    '20261006141158_source_current_version_index.sql',
    '20261006141202_source_ingestion_transaction.sql',
    '20261007055251_canonical_knowledge_snapshot.sql',
)


def literal(value: str) -> str:
    """Quote SQL fixture values without shell interpretation."""
    return "'" + value.replace("'", "''") + "'"


def json_literal(value: Json) -> str:
    return literal(json.dumps(value)) + '::jsonb'


@dataclass(frozen=True)
class Database:
    executable: Path
    port: int
    historical_source: str | None = None

    def args(self) -> list[str]:
        return [str(self.executable), '-X', '-qAt', '-h', '127.0.0.1', '-p', str(self.port),
                '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
                '-v', 'VERBOSITY=verbose']

    def sql(self, text: str, *, owner: str | None = OWNER,
            role: str = 'authenticated', succeeds: bool = True) -> str:
        """Exercise application SQL with RLS active; admin is only fixture/catalog setup."""
        prefix = 'BEGIN;'
        if role != 'postgres':
            assert role in ('authenticated', 'anon', 'service_role')
            prefix += f'SET LOCAL ROLE {role};'
        if owner is not None:
            prefix += f'SET LOCAL "request.jwt.claim.sub" = {literal(owner)};'
        result = subprocess.run(self.args(), input=prefix + text + ';COMMIT;', text=True,
                                encoding='utf-8', capture_output=True, timeout=30,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if succeeds:
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()
        assert result.returncode != 0, 'Expected PostgreSQL to reject the operation'
        return result.stderr

    def call_sql(self, source: str, payload: Json, operation: str, version: int = 1,
                 *, internal: bool = False) -> str:
        name = ('visualai_internal.commit_knowledge_snapshot' if internal
                else 'public.visualai_commit_knowledge_snapshot')
        return f'SELECT {name}({literal(source)}, {version}, {literal(operation)}::uuid, {json_literal(payload)})'

    def commit(self, source: str, payload: Json, operation: str | None = None,
               version: int = 1, *, owner: str | None = OWNER,
               succeeds: bool = True) -> str:
        return self.sql(self.call_sql(source, payload, operation or str(uuid4()), version),
                        owner=owner, succeeds=succeeds)


@pytest.fixture(scope='module')
def database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Database]:
    """Install exact historical baseline and new migration into an ephemeral cluster."""
    configured = os.environ.get('VISUALAI_KNOWLEDGE_TEST_PG_BIN')
    if not configured:
        pytest.skip('Real PostgreSQL requires VISUALAI_KNOWLEDGE_TEST_PG_BIN; no mocked SQL fallback')
    binary = Path(configured).resolve()
    suffix = '.exe' if os.name == 'nt' else ''
    for name in ('initdb', 'pg_ctl', 'psql'):
        assert (binary / (name + suffix)).is_file(), f'Missing local PostgreSQL {name}'
    directory = tmp_path_factory.mktemp('knowledge-postgres')
    data = directory / 'data'
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    def control(name: str, *args: str) -> None:
        # Windows detached postgres can retain inherited PIPE handles. Use a file.
        log = directory / 'control.log'
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run([str(binary / (name + suffix)), *args], stdout=output,
                                    stderr=subprocess.STDOUT, timeout=45, creationflags=flags)
        assert result.returncode == 0, log.read_text(encoding='utf-8')
    control('initdb', '-D', str(data), '-U', 'postgres', '-A', 'trust',
            '--encoding=UTF8', '--no-locale')
    # Trust is confined to this disposable loopback-only test cluster.
    (data / 'pg_hba.conf').write_text('host all all 127.0.0.1/32 trust\n', encoding='utf-8')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    control('pg_ctl', '-D', str(data), '-l', str(directory / 'postgres.log'), '-w', 'start',
            '-o', f'-h 127.0.0.1 -p {port} -c max_connections=20')
    db = Database(binary / ('psql' + suffix), port)
    try:
        db.sql("""
            CREATE ROLE anon NOLOGIN;
            CREATE ROLE authenticated NOLOGIN;
            CREATE ROLE service_role NOLOGIN BYPASSRLS;
            CREATE SCHEMA auth;
            CREATE TABLE auth.users(id uuid PRIMARY KEY);
            CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
                SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
            $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role;
        """, role='postgres', owner=None)
        for filename in MIGRATIONS[:3]:
            result = subprocess.run(db.args() + ['-f', str(ROOT / 'migrations' / filename)],
                                    capture_output=True, text=True, encoding='utf-8',
                                    timeout=45, creationflags=flags)
            assert result.returncode == 0, filename + ': ' + result.stderr
        db.sql(f'INSERT INTO auth.users(id) VALUES ({literal(OWNER)}),({literal(OTHER)})',
               role='postgres', owner=None)
        # Profiles are provisioned via the actual owner-scoped INSERT policy.
        for owner in (OWNER, OTHER):
            db.sql(f'INSERT INTO public.profiles(id,full_name) VALUES ({literal(owner)},\'DB test\')', owner=owner)
        historical = seed(db)
        db.sql(f"INSERT INTO public.concepts(user_id,source_id,source_version,concept_id,name,source_content_ids) VALUES ({literal(OWNER)},{literal(historical)},1,'c1','Historical',ARRAY['u1'])", role='postgres')
        # Reproduce permissive defaults: the new migration must explicitly remove them.
        db.sql('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon,authenticated,service_role; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon,authenticated,service_role; ALTER DEFAULT PRIVILEGES IN SCHEMA visualai_internal GRANT EXECUTE ON FUNCTIONS TO anon,authenticated,service_role', role='postgres')
        result = subprocess.run(db.args() + ['-f', str(ROOT / 'migrations' / MIGRATIONS[3])],
                                capture_output=True, text=True, encoding='utf-8',
                                timeout=45, creationflags=flags)
        assert result.returncode == 0, result.stderr
        db = Database(db.executable, db.port, historical)
        yield db
    finally:
        control('pg_ctl', '-D', str(data), '-w', 'stop', '-m', 'fast')


def seed(db: Database, *, owner: str = OWNER, version: int = 1) -> str:
    """Create canonical units via the unchanged Phase 5B authenticated RPC."""
    source = 'test_' + uuid4().hex
    s: dict[str, Json] = dict(source_id=source, user_id=owner, asset_id=source,
        upload_id=source, filename='fixture.txt', source_type='txt', mime_type='text/plain',
        file_hash=source, file_size=50, version=version, source_version=f'v{version}',
        parser_version='v1', sanitization_version='v1', status='INDEXING')
    units: list[Json] = [dict(content_id=cid, source_id=source, source_version=version,
        user_id=owner, asset_id=source, layer='A', modality='txt', text='Canonical evidence for concepts.',
        sequence_index=i, page_start=1, page_end=1, heading_path=['Chapter'],
        chapter='Chapter', section='Section', extraction_method='text_parser',
        confidence_score=0.9, provenance={'parser':'original'}) for i, cid in enumerate(('u1','u2'))]
    v: dict[str, Json] = dict(user_id=owner, source_id=source, version=version,
        source_version=f'v{version}', file_hash=source, filename='fixture.txt',
        file_location='test-only/fixture.txt', provenance={}, normalized_content=units,
        sanitized_content=units, quarantined_content=[], rich_chunks=[dict(
            user_id=owner, source_id=source, asset_id=source, source_version=f'v{version}',
            source_type='txt', content_id='u1', content_ids=['u1','u2'], text='Canonical evidence.')])
    db.sql(f'SELECT public.visualai_commit_source_ingestion({json_literal(s)}, {json_literal(v)}, {json_literal(units)})', owner=owner)
    return source


def payload() -> dict[str, Json]:
    """Two topics, three subtopics and a genuinely evidenced A-depends-B graph."""
    return dict(schema_version=1,
        topics=[dict(topic_id='t1', title='First', sequence=0, provenance={}),
                dict(topic_id='t2', title='Second', sequence=1, provenance={})],
        subtopics=[dict(subtopic_id='s1', topic_id='t1', title='One', sequence=0, provenance={}),
                   dict(subtopic_id='s2', topic_id='t1', title='Two', sequence=1, provenance={}),
                   dict(subtopic_id='s3', topic_id='t2', title='Three', sequence=0, provenance={})],
        concepts=[dict(concept_id='c1', subtopic_id='s1', name='Dependent', definition='Annotation', sequence=0, provenance={}),
                  dict(concept_id='c2', subtopic_id='s2', name='Prerequisite', sequence=0, provenance={})],
        content_concepts=[dict(content_id='u1', concept_id='c1', support_kind='prerequisite_evidence',
                               char_start=0, char_end=9, extraction_confidence=0.9, provenance={'parser':'original'}),
                          dict(content_id='u2', concept_id='c1', support_kind='example', provenance={}),
                          dict(content_id='u1', concept_id='c2', support_kind='definition', provenance={})],
        relationships=[dict(concept_id='c1', related_concept_id='c2', relationship_type='prerequisite',
                            evidence_content_ids=['u1'], provenance={})])


def rows(p: dict[str, Json], key: str) -> list[dict[str, Json]]:
    value = p[key]
    assert isinstance(value, list)
    assert all(isinstance(row, dict) for row in value)
    return [row for row in value if isinstance(row, dict)]


def test_hierarchy_evidence_and_readiness(database: Database) -> None:
    db = database
    source = seed(db)
    before = db.sql(f'SELECT jsonb_agg(to_jsonb(u)) FROM public.content_units u WHERE source_id={literal(source)}')
    result = json.loads(db.commit(source, payload()))
    assert result['knowledge_state'] == 'READY'
    assert db.sql(f'SELECT string_agg(topic_id,\',\' ORDER BY sequence) FROM public.topics WHERE source_id={literal(source)}') == 't1,t2'
    assert db.sql(f'SELECT string_agg(subtopic_id,\',\' ORDER BY sequence) FROM public.subtopics WHERE source_id={literal(source)} AND topic_id=\'t1\'') == 's1,s2'
    assert db.sql(f'SELECT subtopic_id FROM public.concepts WHERE source_id={literal(source)} AND concept_id=\'c1\'') == 's1'
    assert db.sql(f'SELECT count(*) FROM public.content_concepts WHERE source_id={literal(source)} AND concept_id=\'c1\'') == '2'
    assert db.sql(f'SELECT count(*) FROM public.content_concepts WHERE source_id={literal(source)} AND content_id=\'u1\'') == '2'
    assert db.sql(f'SELECT jsonb_agg(to_jsonb(u)) FROM public.content_units u WHERE source_id={literal(source)}') == before
    assert db.sql(f'SELECT status FROM public.sources WHERE source_id={literal(source)}') == 'INDEXING'


@pytest.mark.parametrize('invalid', [
    'missing_content', 'negative_offset', 'reversed_offset', 'large_offset', 'one_offset',
    'missing_concept', 'missing_subtopic', 'missing_topic', 'no_concept_evidence',
    'missing_prerequisite', 'self_edge', 'cycle', 'unsupported_type', 'unsupported_evidence',
    'duplicate_topic', 'duplicate_sequence', 'duplicate_concept', 'duplicate_link',
    'owner_injection', 'source_injection', 'version_injection', 'student_injection',
    'fractional_sequence', 'string_sequence', 'invalid_confidence', 'invalid_row',
    'null_payload', 'unknown_payload_key', 'wrong_schema', 'empty_topics', 'too_many_topics',
    'oversized_payload', 'deep_provenance', 'null_id',
])
def test_rejects_invalid_snapshot_and_rolls_back(database: Database, invalid: str) -> None:
    db = database
    source = seed(db)
    p = payload()
    links = rows(p, 'content_concepts')
    concepts = rows(p, 'concepts')
    relationships = rows(p, 'relationships')
    topics = rows(p, 'topics')
    subtopics = rows(p, 'subtopics')
    if invalid == 'missing_content': links[0]['content_id'] = 'absent'
    elif invalid == 'negative_offset': links[0]['char_start'] = -1
    elif invalid == 'reversed_offset': links[0]['char_end'] = 0
    elif invalid == 'large_offset': links[0]['char_end'] = 999
    elif invalid == 'one_offset': del links[0]['char_end']
    elif invalid == 'missing_concept': links[0]['concept_id'] = 'absent'
    elif invalid == 'missing_subtopic': concepts[0]['subtopic_id'] = 'absent'
    elif invalid == 'missing_topic': subtopics[0]['topic_id'] = 'absent'
    elif invalid == 'no_concept_evidence': p['content_concepts'] = links[:2]
    elif invalid == 'missing_prerequisite': relationships[0]['related_concept_id'] = 'absent'
    elif invalid == 'self_edge': relationships[0]['related_concept_id'] = 'c1'
    elif invalid == 'cycle':
        links[2]['support_kind'] = 'prerequisite_evidence'
        relationships.append(dict(concept_id='c2', related_concept_id='c1', relationship_type='prerequisite', evidence_content_ids=['u1'], provenance={}))
        p['relationships'] = relationships
    elif invalid == 'unsupported_type': relationships[0]['relationship_type'] = 'next'
    elif invalid == 'unsupported_evidence': relationships[0]['evidence_content_ids'] = ['u2']
    elif invalid == 'duplicate_topic': p['topics'] = topics + [copy.deepcopy(topics[0])]
    elif invalid == 'duplicate_sequence': topics[1]['sequence'] = 0
    elif invalid == 'duplicate_concept': p['concepts'] = concepts + [copy.deepcopy(concepts[0])]
    elif invalid == 'duplicate_link': p['content_concepts'] = links + [copy.deepcopy(links[0])]
    elif invalid == 'owner_injection': topics[0]['user_id'] = OTHER
    elif invalid == 'source_injection': links[0]['source_id'] = 'other'
    elif invalid == 'version_injection': links[0]['source_version'] = 2
    elif invalid == 'student_injection': concepts[0]['student_id'] = 'admin'
    elif invalid == 'fractional_sequence': topics[0]['sequence'] = 0.5
    elif invalid == 'string_sequence': topics[0]['sequence'] = '0'
    elif invalid == 'invalid_confidence': links[0]['extraction_confidence'] = 1.1
    elif invalid == 'invalid_row': p['concepts'] = ['invalid']
    elif invalid == 'unknown_payload_key': p['owner'] = OTHER
    elif invalid == 'wrong_schema': p['schema_version'] = 2
    elif invalid == 'empty_topics': p['topics'] = []
    elif invalid == 'too_many_topics': p['topics'] = [topics[0]] * 129
    elif invalid == 'oversized_payload': topics[0]['provenance'] = {'blob':'x' * 2097152}
    elif invalid == 'deep_provenance':
        nested: Json = {}
        for _ in range(20): nested = {'nested':nested}
        topics[0]['provenance'] = nested
    elif invalid == 'null_id': concepts[0]['concept_id'] = None
    error = db.commit(source, None if invalid == 'null_payload' else p, succeeds=False)
    assert 'ERROR' in error
    for table in ('topics','subtopics','concepts','content_concepts','concept_relationships'):
        assert db.sql(f'SELECT count(*) FROM public.{table} WHERE source_id={literal(source)}') == '0'
    assert db.sql(f'SELECT knowledge_state FROM public.source_versions WHERE source_id={literal(source)}') == 'LEGACY_UNMAPPED'


def test_idempotency_canonical_hash_and_conflicts(database: Database) -> None:
    db = database
    source, operation, p = seed(db), str(uuid4()), payload()
    result = db.commit(source, p, operation)
    assert db.commit(source, p, operation) == result
    reordered = dict(reversed(list(p.items())))
    assert db.commit(source, reordered, operation) == result
    malformed_retry = copy.deepcopy(p)
    rows(malformed_retry, 'topics')[0]['sequence'] = 0.0
    assert 'KNOWLEDGE_INVALID_INTEGER' in db.commit(source, malformed_retry, operation, succeeds=False)
    # Different numeric scales in arbitrary annotations have one canonical hash.
    source2, op2, p2 = seed(db), str(uuid4()), payload()
    rows(p2, 'topics')[0]['provenance'] = {'number':1}
    result2 = db.commit(source2, p2, op2)
    rows(p2, 'topics')[0]['provenance'] = {'number':1.0}
    assert db.commit(source2, p2, op2) == result2
    rows(p, 'topics')[0]['title'] = 'Conflict'
    assert 'KNOWLEDGE_SNAPSHOT_CONFLICT' in db.commit(source, p, operation, succeeds=False)
    assert 'KNOWLEDGE_SNAPSHOT_CONFLICT' in db.commit(source, payload(), succeeds=False)
    assert '23505' in db.commit(seed(db), payload(), operation, succeeds=False)


@pytest.mark.parametrize('scope', ['foreign_owner','cross_source','cross_version','foreign_content','foreign_concept'])
def test_exact_scope_isolation(database: Database, scope: str) -> None:
    db = database
    source = seed(db)
    foreign = seed(db, owner=OTHER)
    p = payload()
    if scope == 'foreign_owner':
        assert '42501' in db.commit(source, p, owner=OTHER, succeeds=False)
    elif scope == 'cross_source':
        assert '42501' in db.commit(foreign, p, succeeds=False)
    elif scope == 'cross_version':
        assert '42501' in db.commit(source, p, version=2, succeeds=False)
    elif scope == 'foreign_content':
        # A globally identifiable evidence ID exists, but outside the caller scope.
        db.sql(f'UPDATE public.content_units SET content_id=\'foreign_unit\' WHERE source_id={literal(foreign)} AND content_id=\'u1\'', role='postgres')
        rows(p, 'content_concepts')[0]['content_id'] = 'foreign_unit'
        assert 'KNOWLEDGE_INVALID_CONTENT_EVIDENCE' in db.commit(source, p, succeeds=False)
    else:
        foreign_payload = payload()
        rows(foreign_payload, 'concepts')[1]['concept_id'] = 'foreign_concept'
        rows(foreign_payload, 'content_concepts')[2]['concept_id'] = 'foreign_concept'
        rows(foreign_payload, 'relationships')[0]['related_concept_id'] = 'foreign_concept'
        db.commit(foreign, foreign_payload, owner=OTHER)
        rows(p, 'relationships')[0]['related_concept_id'] = 'foreign_concept'
        assert 'KNOWLEDGE_INVALID_RELATIONSHIP' in db.commit(source, p, succeeds=False)


@pytest.mark.parametrize('table', ['topics','subtopics','content_concepts'])
def test_rls_and_direct_writes(database: Database, table: str) -> None:
    db = database
    source = seed(db)
    db.commit(source, payload())
    assert int(db.sql(f'SELECT count(*) FROM public.{table} WHERE source_id={literal(source)}')) > 0
    assert db.sql(f'SELECT count(*) FROM public.{table} WHERE source_id={literal(source)}', owner=OTHER) == '0'
    assert '42501' in db.sql(f'SELECT * FROM public.{table}', owner=None, role='anon', succeeds=False)
    for statement in (f'DELETE FROM public.{table}', f'UPDATE public.{table} SET user_id={literal(OTHER)}',
                      f'INSERT INTO public.{table} SELECT * FROM public.{table}'):
        assert '42501' in db.sql(statement, succeeds=False)


def test_rpc_permissions_and_search_paths(database: Database) -> None:
    db = database
    source = seed(db)
    for internal in (False, True):
        call = db.call_sql(source, payload(), str(uuid4()), internal=internal)
        assert '42501' in db.sql(call, role='anon', owner=None, succeeds=False)
        assert '42501' in db.sql(call, owner=None, succeeds=False)
        assert '42501' in db.sql(call, role='service_role', succeeds=False)
    assert '42501' in db.sql("SELECT visualai_internal.knowledge_object('{}', '{}', '{}')", succeeds=False)
    assert '42501' in db.sql("SELECT visualai_internal.knowledge_canonical_json('{}', 0)", succeeds=False)
    paths = json.loads(db.sql("""SELECT jsonb_agg(jsonb_build_object('name',p.proname,'definer',p.prosecdef,'config',p.proconfig))
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE p.proname IN ('visualai_commit_knowledge_snapshot','commit_knowledge_snapshot')""", role='postgres'))
    assert len(paths) == 2
    assert all('search_path=""' in p['config'] for p in paths)
    assert sum(p['definer'] for p in paths) == 1


def test_historical_readiness_and_source_ingestion_compatibility(database: Database) -> None:
    db = database
    source = seed(db, version=2)
    assert db.sql(f'SELECT knowledge_state FROM public.source_versions WHERE source_id={literal(source)}') == 'LEGACY_UNMAPPED'
    assert db.sql(f'SELECT source_version FROM public.source_versions WHERE source_id={literal(source)}') == 'v2'
    db.commit(source, payload(), version=2)
    # Index status remains independent from the knowledge transaction.
    db.sql(f'SELECT public.visualai_source_index_status({literal(source)}, 2, \'READY\', NULL)')
    assert db.sql(f'SELECT status FROM public.sources WHERE source_id={literal(source)}') == 'READY'
    assert db.sql(f'SELECT knowledge_state FROM public.source_versions WHERE source_id={literal(source)}') == 'READY'


def test_existing_rows_survive_additive_migration_and_map_in_place(database: Database) -> None:
    db = database
    assert db.historical_source is not None
    source = db.historical_source
    assert db.sql(f'SELECT knowledge_state FROM public.source_versions WHERE source_id={literal(source)}') == 'LEGACY_UNMAPPED'
    assert db.sql(f'SELECT name FROM public.concepts WHERE source_id={literal(source)}') == 'Historical'
    before = db.sql(f'SELECT created_at FROM public.concepts WHERE source_id={literal(source)}')
    db.commit(source, payload())
    assert db.sql(f'SELECT count(*) FROM public.concepts WHERE source_id={literal(source)}') == '2'
    assert db.sql(f'SELECT created_at FROM public.concepts WHERE source_id={literal(source)} AND concept_id=\'c1\'') == before


@pytest.mark.parametrize('state', ['PENDING','FAILED'])
def test_durable_nonready_states(database: Database, state: str) -> None:
    db = database
    source = seed(db)
    # A future scheduler writes these states; this phase only exposes the final commit.
    db.sql(f'UPDATE public.source_versions SET knowledge_state={literal(state)}, knowledge_diagnostics=\'{{"code":"test"}}\' WHERE source_id={literal(source)}', role='postgres')
    assert db.sql(f'SELECT knowledge_state FROM public.source_versions WHERE source_id={literal(source)}') == state
    db.commit(source, payload())
    assert db.sql(f'SELECT knowledge_state FROM public.source_versions WHERE source_id={literal(source)}') == 'READY'


def test_existing_rls_grants_and_phase5b_owner_checks(database: Database) -> None:
    db = database
    source = seed(db)
    db.commit(source, payload())
    for table in ('sources','source_versions','content_units','concepts','concept_relationships'):
        assert db.sql(f'SELECT count(*) FROM public.{table} WHERE source_id={literal(source)}', owner=OTHER) == '0'
        assert '42501' in db.sql(f'SELECT * FROM public.{table}', owner=None, role='anon', succeeds=False)
        assert '42501' in db.sql(f'DELETE FROM public.{table}', succeeds=False)
    assert '42501' in db.sql(f'SELECT public.visualai_source_index_status({literal(source)},1,\'READY\',NULL)', owner=OTHER, succeeds=False)
    assert '42501' in db.sql(f'INSERT INTO public.profiles(id,full_name) VALUES ({literal(OTHER)},\'forged\')', succeeds=False)


@pytest.mark.parametrize('target', ['topic','subtopic','concept_membership','content','concept','relationship'])
@pytest.mark.parametrize('scope', ['owner','source','version'])
def test_composite_foreign_keys_enforce_scope(database: Database, target: str, scope: str) -> None:
    """Trusted fixture SQL checks constraints even when RLS cannot be the guard."""
    db = database
    source = seed(db)
    other_source = seed(db, owner=OTHER)
    db.commit(source, payload())
    db.commit(other_source, payload(), owner=OTHER)
    owner = OTHER if scope == 'owner' else OWNER
    key = other_source if scope == 'source' else source
    version = 2 if scope == 'version' else 1
    s = f'{literal(owner)},{literal(key)},{version}'
    if target == 'topic':
        statement = f'INSERT INTO public.topics(user_id,source_id,source_version,topic_id,title,sequence,provenance) VALUES ({s},\'new\',\'new\',20,\'{{}}\')'
    elif target == 'subtopic':
        statement = f'INSERT INTO public.subtopics(user_id,source_id,source_version,subtopic_id,topic_id,title,sequence,provenance) VALUES ({s},\'new\',\'t1\',\'new\',20,\'{{}}\')'
    elif target == 'concept_membership':
        statement = f'INSERT INTO public.concepts(user_id,source_id,source_version,concept_id,name,subtopic_id,sequence) VALUES ({s},\'new\',\'new\',\'s1\',20)'
    elif target in ('content','concept'):
        # Genuine IDs in another scope must not satisfy either FK.
        foreign_id = 'foreign_' + uuid4().hex
        if target == 'content':
            db.sql(f'INSERT INTO public.content_units(user_id,source_id,source_version,content_id,asset_id,modality,text) VALUES ({literal(OTHER)},{literal(other_source)},1,{literal(foreign_id)},\'fixture\',\'txt\',\'evidence\')', role='postgres')
        else:
            db.sql(f'INSERT INTO public.concepts(user_id,source_id,source_version,concept_id,name) VALUES ({literal(OTHER)},{literal(other_source)},1,{literal(foreign_id)},\'foreign\')', role='postgres')
        content = foreign_id if target == 'content' else 'u1'
        concept = foreign_id if target == 'concept' else 'c1'
        statement = f'INSERT INTO public.content_concepts(user_id,source_id,source_version,content_id,concept_id,support_kind,provenance) VALUES ({s},{literal(content)},{literal(concept)},\'example\',\'{{}}\')'
    else:
        statement = f'INSERT INTO public.concept_relationships(user_id,source_id,source_version,concept_id,related_concept_id,relationship_type) VALUES ({s},\'c1\',\'c2\',\'related\')'
    assert '23503' in db.sql(statement, role='postgres', succeeds=False)


@pytest.mark.parametrize('kind', ['concept','relationship'])
def test_incomplete_historical_graph_is_not_ready(database: Database, kind: str) -> None:
    db = database
    source = seed(db)
    p = payload()
    db.sql(f"INSERT INTO public.concepts(user_id,source_id,source_version,concept_id,name) VALUES ({literal(OWNER)},{literal(source)},1,'old','Old')", role='postgres')
    if kind == 'relationship':
        db.sql(f"INSERT INTO public.concepts(user_id,source_id,source_version,concept_id,name) VALUES ({literal(OWNER)},{literal(source)},1,'old2','Old2'); INSERT INTO public.concept_relationships(user_id,source_id,source_version,concept_id,related_concept_id,relationship_type) VALUES ({literal(OWNER)},{literal(source)},1,'old','old2','related')", role='postgres')
        p['concepts'] = rows(p, 'concepts') + [dict(concept_id=cid, subtopic_id='s3', name=cid,
            sequence=i, provenance={}) for i, cid in enumerate(('old','old2'))]
        p['content_concepts'] = rows(p, 'content_concepts') + [dict(content_id='u1', concept_id=cid,
            support_kind='example', provenance={}) for cid in ('old','old2')]
    assert 'KNOWLEDGE_INCOMPLETE_LEGACY_MAPPING' in db.commit(source, p, succeeds=False)
    assert db.sql(f'SELECT subtopic_id IS NULL FROM public.concepts WHERE source_id={literal(source)} AND concept_id=\'old\'') == 't'


@pytest.mark.parametrize('retry', [False, True])
def test_concurrent_commits_lock_without_overwrite(database: Database, retry: bool) -> None:
    db = database
    source, operation = seed(db), str(uuid4())
    p = payload()
    first_sql = f'BEGIN;SET LOCAL ROLE authenticated;SET LOCAL "request.jwt.claim.sub"={literal(OWNER)};' + db.call_sql(source, p, operation) + ';'
    first = subprocess.Popen(db.args(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert first.stdin is not None and first.stdout is not None
    second: subprocess.Popen[str] | None = None
    try:
        first.stdin.write(first_sql + '\n')
        first.stdin.flush()
        result = first.stdout.readline()
        assert 'READY' in result
        conflict = copy.deepcopy(p)
        rows(conflict, 'topics')[0]['title'] = 'Concurrent replacement'
        second_sql = 'BEGIN;SET LOCAL ROLE authenticated;SET LOCAL "request.jwt.claim.sub"=' + literal(OWNER) + ';' + db.call_sql(source, p if retry else conflict, operation if retry else str(uuid4())) + ';COMMIT;'
        second = subprocess.Popen(db.args(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert second.stdin is not None
        second.stdin.write(second_sql)
        second.stdin.close()
        second.stdin = None
        # Observe an actual server lock wait instead of inferring it from timing.
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            waits = db.sql("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND query LIKE '%visualai_commit_knowledge_snapshot%'", role='postgres')
            if int(waits) > 0: break
            time.sleep(0.05)
        else: pytest.fail('Concurrent RPC did not wait on the source-version lock')
        first.stdin.write('COMMIT;\n')
        first.stdin.close()
        first.stdin = None
        first.communicate(timeout=10)
        output, error = second.communicate(timeout=10)
        if retry:
            assert second.returncode == 0, error
            assert output.strip() == result.strip()
        else:
            assert second.returncode != 0
            assert 'KNOWLEDGE_SNAPSHOT_CONFLICT' in error
        assert db.sql(f'SELECT title FROM public.topics WHERE source_id={literal(source)} AND topic_id=\'t1\'') == 'First'
    finally:
        if second is not None and second.poll() is None:
            second.kill()
            second.communicate()
        if first.poll() is None:
            first.kill()
            first.communicate()


def test_other_version_evidence_does_not_resolve(database: Database) -> None:
    db = database
    source = seed(db)
    db.sql(f"INSERT INTO public.source_versions(user_id,source_id,version,source_version,file_hash,filename,file_location) VALUES ({literal(OWNER)},{literal(source)},2,'v2','hash','fixture.txt','test-only'); INSERT INTO public.content_units(user_id,source_id,source_version,content_id,asset_id,modality,text) VALUES ({literal(OWNER)},{literal(source)},2,'version_two_only','fixture','txt','canonical v2')", role='postgres')
    p = payload()
    rows(p, 'content_concepts')[0]['content_id'] = 'version_two_only'
    assert 'KNOWLEDGE_INVALID_CONTENT_EVIDENCE' in db.commit(source, p, succeeds=False)
    assert db.sql(f'SELECT knowledge_state FROM public.source_versions WHERE source_id={literal(source)} AND version=1') == 'LEGACY_UNMAPPED'


def test_late_database_exception_rolls_back_ready_and_all_rows(database: Database) -> None:
    db = database
    source = seed(db)
    # Failure at the final readiness UPDATE, after all graph INSERTs, must unwind them.
    constraint = 'test_fail_' + uuid4().hex
    db.sql(f'ALTER TABLE public.source_versions ADD CONSTRAINT {constraint} CHECK (source_id <> {literal(source)} OR knowledge_state <> \'READY\')', role='postgres')
    try:
        assert '23514' in db.commit(source, payload(), succeeds=False)
        for table in ('topics','subtopics','concepts','content_concepts','concept_relationships'):
            assert db.sql(f'SELECT count(*) FROM public.{table} WHERE source_id={literal(source)}') == '0'
        assert db.sql(f'SELECT knowledge_operation_id IS NULL FROM public.source_versions WHERE source_id={literal(source)}') == 't'
    finally:
        db.sql(f'ALTER TABLE public.source_versions DROP CONSTRAINT {constraint}', role='postgres')


def test_maximum_concept_chain_is_bounded(database: Database) -> None:
    db = database
    source, p = seed(db), payload()
    # Exercise the declared operational limit and a worst-depth valid DAG.
    count = 1024
    p['concepts'] = [dict(concept_id=f'n{i}', subtopic_id='s1', name=f'Node {i}', sequence=i,
                          provenance={}) for i in range(count)]
    p['content_concepts'] = [dict(content_id='u1', concept_id=f'n{i}',
        support_kind='prerequisite_evidence', provenance={}) for i in range(count)]
    p['relationships'] = [dict(concept_id=f'n{i}', related_concept_id=f'n{i+1}',
        relationship_type='prerequisite', evidence_content_ids=['u1'], provenance={})
        for i in range(count-1)]
    started = time.monotonic()
    assert json.loads(db.commit(source, p))['knowledge_state'] == 'READY'
    assert time.monotonic() - started < 30
