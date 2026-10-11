"""Explicit, checksummed additive SQL migrations for the private video database."""
import hashlib
from pathlib import Path

from ..core import postgres

DIRECTORY = Path(__file__).with_suffix("")


def migrate():
    applied = []
    with postgres.transaction() as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS visualai_video")
        connection.execute("REVOKE ALL ON SCHEMA visualai_video FROM PUBLIC")
        connection.execute("""CREATE TABLE IF NOT EXISTS visualai_video.schema_migrations
            (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())""")
        for path in sorted(DIRECTORY.glob("*.sql")):
            source = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(source.encode()).hexdigest()
            saved = connection.execute("SELECT checksum FROM visualai_video.schema_migrations WHERE version=%s", (path.name,)).fetchone()
            if saved:
                if saved[0] != checksum:
                    raise postgres.VideoDatabaseError("VIDEO_DATABASE_MIGRATION_CHANGED")
                continue
            connection.execute(source)
            connection.execute("INSERT INTO visualai_video.schema_migrations(version,checksum) VALUES (%s,%s)", (path.name,checksum))
            applied.append(path.name)
    return applied


if __name__ == "__main__":
    try:
        print({"applied": migrate()})
    except postgres.VideoDatabaseError as error:
        raise SystemExit(error.code) from None
    finally:
        postgres.close_pool()
