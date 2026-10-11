"""Explicit additive migrations for new canonical learning data, never remote Supabase."""
import hashlib
from pathlib import Path

from ..core import postgres

DIRECTORY = Path(__file__).with_suffix('')


def migrate():
    applied = []
    with postgres.transaction() as connection:
        for path in sorted(DIRECTORY.glob('*.sql')):
            version = 'learning/' + path.name
            source = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(source.encode()).hexdigest()
            saved = connection.execute('SELECT checksum FROM visualai_video.schema_migrations WHERE version=%s', (version,)).fetchone()
            if saved:
                if saved[0] != checksum:
                    raise postgres.VideoDatabaseError('LEARNING_DATABASE_MIGRATION_CHANGED')
                continue
            connection.execute(source)
            connection.execute('INSERT INTO visualai_video.schema_migrations(version,checksum) VALUES (%s,%s)', (version, checksum))
            applied.append(version)
    return applied


def grant_runtime(role):
    """Deployment-only: grant the named backend role, without superuser or RLS bypass."""
    from psycopg import sql
    with postgres.transaction() as connection:
        privileged = connection.execute('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=%s', (role,)).fetchone()
        if not privileged or privileged[0]:
            raise postgres.VideoDatabaseError('VIDEO_DATABASE_PRIVILEGED_ROLE')
        for statement in (
            'GRANT USAGE ON SCHEMA visualai_learning,visualai_learning_private TO {}',
            'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA visualai_learning TO {}',
            'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA visualai_learning,visualai_learning_private TO {}',
        ):
            connection.execute(sql.SQL(statement).format(sql.Identifier(role)))


def readiness():
    with postgres.transaction() as connection:
        row = connection.execute("SELECT count(*) FROM visualai_video.schema_migrations WHERE version='learning/001_learning_persistence.sql'").fetchone()
        if row[0] != 1:
            raise postgres.VideoDatabaseError('LEARNING_DATABASE_MIGRATION_REQUIRED')
        for table in ('sources','source_versions','content_units','topics','subtopics','concepts','learning_sessions','assessment_sessions','assessment_questions'):
            permitted = connection.execute("SELECT bool_and(has_table_privilege(current_user,%s,privilege)) FROM unnest(ARRAY['SELECT','INSERT','UPDATE']) AS privilege", ('visualai_learning.'+table,)).fetchone()
            if not permitted or not permitted[0]:
                raise postgres.VideoDatabaseError('LEARNING_DATABASE_PERMISSIONS_REQUIRED')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-role', required=True)
    args = parser.parse_args()
    try:
        print({'applied': migrate()})
        grant_runtime(args.runtime_role)
    except postgres.VideoDatabaseError as error:
        raise SystemExit(error.code) from None
    finally:
        postgres.close_pool()
