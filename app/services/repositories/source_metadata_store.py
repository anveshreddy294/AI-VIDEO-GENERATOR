"""Owned metadata copies, never a substitute for canonical Supabase authorization."""
from ...core import postgres

VERSION_FIELDS = {'user_id', 'source_id', 'version', 'source_version', 'file_hash',
                  'sha256', 'filename', 'file_location', 'provenance'}


def copy_source(owner, record):
    if not postgres.enabled():
        return
    if record.user_id != str(owner):
        raise ValueError('Source metadata ownership mismatch')
    from psycopg.types.json import Jsonb
    try:
        with postgres.transaction() as connection:
            connection.execute("SELECT set_config('visualai.owner_id', %s, true)", (str(owner),))
            connection.execute("""INSERT INTO visualai_video.sources(owner_id,source_id,version,document)
                VALUES (%s,%s,%s,%s) ON CONFLICT (owner_id,source_id) DO UPDATE SET
                version=EXCLUDED.version,document=EXCLUDED.document,copied_at=now()
                WHERE visualai_video.sources.version < EXCLUDED.version
                   OR (visualai_video.sources.version = EXCLUDED.version
                       AND (visualai_video.sources.document->>'updated_at')::timestamptz
                           <= (EXCLUDED.document->>'updated_at')::timestamptz)""",
                (owner, record.source_id, record.version, Jsonb(record.model_dump(mode='json'))))
    except postgres.VideoDatabaseError:
        raise postgres.VideoDatabaseError('SOURCE_METADATA_COPY_PENDING') from None


def copy_version(owner, version):
    if not postgres.enabled():
        return
    if str(version.user_id) != str(owner):
        raise ValueError('Source metadata ownership mismatch')
    from psycopg.types.json import Jsonb
    try:
        with postgres.transaction() as connection:
            connection.execute("SELECT set_config('visualai.owner_id', %s, true)", (str(owner),))
            connection.execute("""INSERT INTO visualai_video.source_versions(owner_id,source_id,version,document)
                VALUES (%s,%s,%s,%s) ON CONFLICT (owner_id,source_id,version) DO UPDATE SET
                document=EXCLUDED.document,copied_at=now()""",
                (owner, version.source_id, version.version,
                 Jsonb(version.model_dump(mode='json', include=VERSION_FIELDS))))
    except postgres.VideoDatabaseError:
        raise postgres.VideoDatabaseError('SOURCE_METADATA_COPY_PENDING') from None
