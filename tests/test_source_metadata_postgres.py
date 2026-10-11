"""Real PostgreSQL owner isolation, reconciliation and dual-store failure boundaries."""
import pytest
from uuid import uuid4

from app.core import postgres
from app.services.ingestion.source_ingestion import ingest_source
from app.services.ingestion.failures import SourceIngestionFailed
from app.services.repositories.source_metadata_store import copy_source, copy_version
from tests.video_postgres_fixture import video_cluster, postgres_mode
from tests.test_source_supabase import context, OWNER, OTHER


@pytest.fixture(autouse=True)
def unique_input(context):
    # Source IDs are content-derived; keep tests independent in the shared cluster.
    path = context[2]
    path.write_text(path.read_text() + '\nDocument reference ' + uuid4().hex)


def owned_rows(table, owner=OWNER):
    assert table in {'sources', 'source_versions'}
    with postgres.transaction() as connection:
        connection.execute("SELECT set_config('visualai.owner_id',%s,true)", (str(owner),))
        return connection.execute('SELECT document FROM visualai_video.' + table).fetchall()


def test_ingestion_copies_metadata_and_versions_without_content(postgres_mode, context):
    remote, repo, path = context
    result = ingest_source(repo, path, 'fixture.txt', enrich=False)
    source = next(row[0] for row in owned_rows('sources') if row[0]['source_id'] == result['source_id'])
    version = next(row[0] for row in owned_rows('source_versions') if row[0]['source_id'] == result['source_id'])
    assert source['filename'] == 'fixture.txt' and source['user_id'] == str(OWNER)
    assert version['file_location'] and version['file_hash'] == remote.versions[0]['file_hash']
    assert not {'rich_chunks','normalized_content','sanitized_content','quarantined_content',
                'topic_blueprint','knowledge_diagnostics'} & version.keys()
    assert remote.versions[0]['rich_chunks']  # Canonical content remains untouched.
    repo.mark_status(repo.get_source(result['source_id']), 'READY')
    assert repo.get_source(result['source_id']).status == 'READY'
    saved = next(row[0] for row in owned_rows('sources') if row[0]['source_id'] == result['source_id'])
    assert saved['status'] == 'READY'
    postgres.close_pool()
    assert any(row[0] == version for row in owned_rows('source_versions'))
    assert repo.sync_metadata() == {'sources':1,'source_versions':1}
    assert repo.sync_metadata() == {'sources':1,'source_versions':1}


def test_source_metadata_rls_and_mismatched_owner_rejected(postgres_mode, context):
    _, repo, path = context
    result = ingest_source(repo, path, 'fixture.txt', enrich=False)
    assert not owned_rows('sources', OTHER) and not owned_rows('source_versions', OTHER)
    with postgres.transaction() as connection:
        # Transaction-local owner setting must never leak from pooled connections.
        assert connection.execute('SELECT source_id FROM visualai_video.sources').fetchall() == []
    with pytest.raises(ValueError, match='ownership'):
        copy_source(OTHER, repo.get_source(result['source_id']))
    with pytest.raises(ValueError, match='ownership'):
        copy_version(OTHER, repo.get_source_version(result['source_id']))


def test_metadata_copy_failure_keeps_canonical_commit_and_read_repairs(postgres_mode, context, monkeypatch):
    remote, repo, path = context
    from app.services.repositories import source_repository
    original = source_repository.copy_source
    def fail(*args):
        raise postgres.VideoDatabaseError('SOURCE_METADATA_COPY_PENDING')
    monkeypatch.setattr(source_repository, 'copy_source', fail)
    with pytest.raises(SourceIngestionFailed) as error:
        ingest_source(repo, path, 'fixture.txt', enrich=False)
    assert error.value.failure.code == 'SOURCE_METADATA_COPY_PENDING'
    assert 'Canonical source' in error.value.failure.message
    assert len(remote.sources) == len(remote.versions) == 1 and remote.units
    source_id = remote.sources[0]['source_id']
    assert all(row[0]['source_id'] != source_id for row in owned_rows('sources'))
    monkeypatch.setattr(source_repository, 'copy_source', original)
    assert repo.get_source_version(source_id).source_id == source_id
    assert any(row[0]['source_id'] == source_id for row in owned_rows('sources'))
    assert any(row[0]['source_id'] == source_id for row in owned_rows('source_versions'))


def test_all_version_reconciliation_and_stale_latest_protection(postgres_mode, context):
    remote, repo, path = context
    result = ingest_source(repo, path, 'fixture.txt', enrich=False)
    old = repo.get_source(result['source_id'])
    remote.sources[0].update(version=2, source_version='v2')
    remote.versions.append(dict(remote.versions[0], version=2, source_version='v2'))
    assert repo.sync_metadata() == {'sources':1,'source_versions':2}
    copy_source(OWNER, old)
    saved = next(row[0] for row in owned_rows('sources') if row[0]['source_id'] == result['source_id'])
    assert saved['version'] == 2
    assert {row[0]['version'] for row in owned_rows('source_versions')
            if row[0]['source_id'] == result['source_id']} == {1,2}
    assert repo.get_source_version(result['source_id'],1).version == 1


def test_missing_metadata_permissions_fail_readiness(postgres_mode, monkeypatch):
    import psycopg
    # Only change disposable test-role permissions, restore even on failure.
    postgres.close_pool()
    with psycopg.connect(postgres_mode['admin'], autocommit=True) as admin:
        admin.execute('REVOKE UPDATE ON visualai_video.sources FROM video_runtime')
        try:
            with pytest.raises(postgres.VideoDatabaseError, match='VIDEO_DATABASE_PERMISSIONS_REQUIRED'):
                postgres.readiness()
        finally:
            postgres.close_pool()
            admin.execute('GRANT UPDATE ON visualai_video.sources TO video_runtime')


def test_stale_status_cannot_replace_newer_canonical_metadata(postgres_mode, context):
    remote, repo, path = context
    result = ingest_source(repo, path, 'fixture.txt', enrich=False)
    old = repo.get_source(result['source_id'])
    remote.sources[0].update(status='READY', updated_at='2099-01-01T00:00:00Z')
    assert repo.get_source(result['source_id']).status == 'READY'
    copy_source(OWNER, old)
    saved = next(row[0] for row in owned_rows('sources') if row[0]['source_id'] == result['source_id'])
    assert saved['status'] == 'READY'


def test_source_metadata_sql_write_policy_rejects_foreign_owner(postgres_mode, context):
    from psycopg.types.json import Jsonb
    _, repo, path = context
    result = ingest_source(repo, path, 'fixture.txt', enrich=False)
    document = repo.get_source(result['source_id']).model_dump(mode='json')
    with pytest.raises(postgres.VideoDatabaseError):
        with postgres.transaction() as connection:
            connection.execute("SELECT set_config('visualai.owner_id',%s,true)",(str(OTHER),))
            connection.execute('INSERT INTO visualai_video.sources(owner_id,source_id,version,document) VALUES (%s,%s,%s,%s)',
                (OWNER,document['source_id'],document['version'],Jsonb(document)))
    assert not owned_rows('sources',OTHER)
