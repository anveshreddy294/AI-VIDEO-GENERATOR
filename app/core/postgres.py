"""Bounded synchronous PostgreSQL pool; no import-time connections or fallback."""
from contextlib import contextmanager
import threading

from .config import settings


class VideoDatabaseError(RuntimeError):
    def __init__(self, code="VIDEO_DATABASE_UNAVAILABLE"):
        self.code = code
        super().__init__(code)  # Never expose a DSN or driver exception.


_pool = None
_guard = threading.RLock()
_local = threading.local()


def enabled():
    return settings.lesson_persistence_provider == "postgres"


def connection_options():
    try:
        from psycopg.conninfo import conninfo_to_dict
        options = conninfo_to_dict(settings.postgres_dsn.get_secret_value())
        if not all(options.get(key) for key in ("host", "dbname", "user")):
            raise ValueError()
        return {**options, "connect_timeout": max(1, int(settings.postgres_timeout_seconds)),
                "application_name": "visualai_video", "autocommit": True,
                "options": f"-c statement_timeout={int(settings.postgres_timeout_seconds*1000)} -c lock_timeout={int(settings.postgres_timeout_seconds*1000)}"}
    except Exception:
        # Driver parsing may include the original secret string in its message.
        raise VideoDatabaseError("VIDEO_DATABASE_CONFIGURATION_INVALID") from None


def get_pool():
    global _pool
    with _guard:
        if _pool is None:
            try:
                from psycopg_pool import ConnectionPool
                options = connection_options()
                candidate = ConnectionPool(conninfo="", kwargs=options, min_size=1,
                    max_size=settings.postgres_pool_size, timeout=settings.postgres_timeout_seconds,
                    max_waiting=32, open=False, name="visualai-video",
                    check=ConnectionPool.check_connection)
                try:
                    candidate.open(wait=True, timeout=settings.postgres_timeout_seconds)
                except Exception:
                    candidate.close()
                    raise
                _pool = candidate
            except VideoDatabaseError:
                raise
            except Exception:
                raise VideoDatabaseError() from None
        return _pool


def close_pool():
    global _pool
    with _guard:
        if _pool is not None:
            _pool.close()
            _pool = None


@contextmanager
def transaction():
    """Nested lesson calls share one transaction and cross-process advisory lock."""
    current = getattr(_local, "connection", None)
    if current is not None:
        yield current
        return
    # Import errors are classified by get_pool before importing driver types.
    pool = get_pool()
    from psycopg import Error
    from psycopg_pool import PoolTimeout, TooManyRequests
    try:
        with pool.connection() as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(861925761)")
            _local.connection = connection
            try:
                yield connection
            finally:
                _local.connection = None
    except (Error, PoolTimeout, TooManyRequests):
        raise VideoDatabaseError() from None


def readiness():
    """Check connectivity and explicit migration version, without applying DDL."""
    with transaction() as connection:
        privileged = connection.execute("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        if privileged and privileged[0]:
            raise VideoDatabaseError("VIDEO_DATABASE_PRIVILEGED_ROLE")
        row = connection.execute("SELECT to_regclass('visualai_video.schema_migrations')").fetchone()
        if not row or row[0] is None:
            raise VideoDatabaseError("VIDEO_DATABASE_MIGRATION_REQUIRED")
        if connection.execute("SELECT count(*) FROM visualai_video.schema_migrations WHERE version IN ('001_video_persistence.sql','002_source_metadata.sql')").fetchone()[0] != 2:
            raise VideoDatabaseError("VIDEO_DATABASE_MIGRATION_REQUIRED")
        for table in ('lessons', 'generations', 'sources', 'source_versions'):
            permitted = connection.execute("SELECT bool_and(has_table_privilege(current_user,%s,privilege)) FROM unnest(ARRAY['SELECT','INSERT','UPDATE']) AS privilege",
                ('visualai_video.' + table,)).fetchone()
            if not permitted or not permitted[0]:
                raise VideoDatabaseError('VIDEO_DATABASE_PERMISSIONS_REQUIRED')
