"""Disposable loopback PostgreSQL, never an environment/production DSN."""
import os
from pathlib import Path
import socket
import subprocess
import time
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core import postgres
from app.core.config import settings
from app.db.video_migrations import migrate


@pytest.fixture(scope="module")
def video_cluster(tmp_path_factory):
    configured = os.getenv("VISUALAI_VIDEO_TEST_PG_BIN")
    docker_distro = os.getenv('VISUALAI_VIDEO_TEST_DOCKER_WSL')
    if not configured and not docker_distro:
        pytest.skip("Real PostgreSQL requires VISUALAI_VIDEO_TEST_PG_BIN; no SQL mock fallback")
    binary = Path(configured).resolve() if configured else None
    suffix = ".exe" if os.name == "nt" else ""
    if not docker_distro:
        for command in ("initdb", "pg_ctl"):
            assert (binary / (command+suffix)).is_file()
    directory = tmp_path_factory.mktemp("video-postgres")
    data = directory / "data"
    def control(command, *args):
        with (directory / "control.log").open("w", encoding="utf-8") as output:
            result = subprocess.run([str(binary/(command+suffix)), *args], stdout=output,
                stderr=subprocess.STDOUT, timeout=45,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        assert result.returncode == 0, (directory/"control.log").read_text(encoding="utf-8")
    if docker_distro:
        container = 'visualai-pg-test-' + uuid4().hex
        def docker(*args):
            result = subprocess.run(['wsl.exe','-d',docker_distro,'--exec','docker',*args],
                capture_output=True, text=True, timeout=60,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()
        # Explicit opt-in, disposable trust-auth database, random loopback port.
        # Never attach the application's volume or use its configured DSN.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0))
            requested_port = listener.getsockname()[1]
        docker('run','--pull=never','-d','--name',container,'-e','POSTGRES_HOST_AUTH_METHOD=trust',
               '-p',f'127.0.0.1:{requested_port}:5432','postgres:18.3')
        try:
            port = int(docker('port',container,'5432/tcp').rsplit(':',1)[1])
        except BaseException:
            docker('rm','-f','-v',container)
            raise
        def restart():
            docker('restart',container)
            # A restart command completes before SQL necessarily becomes ready.
            # Preserve the published port and wait for real host-side connectivity.
            assert int(docker('port',container,'5432/tcp').rsplit(':',1)[1]) == port
            import psycopg
            for attempt in range(40):
                try:
                    with psycopg.connect(admin, connect_timeout=1):
                        return
                except psycopg.OperationalError:
                    if attempt == 39:
                        raise
                    time.sleep(0.25)
        stop = lambda: docker('rm','-f','-v',container)
    else:
        control("initdb", "-D", str(data), "-U", "postgres", "-A", "trust", "--encoding=UTF8", "--no-locale")
        (data/"pg_hba.conf").write_text("host all all 127.0.0.1/32 trust\n", encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0))
            port = listener.getsockname()[1]
        control("pg_ctl","-D",str(data),"-l",str(directory/"postgres.log"),"-w","start",
                "-o",f"-h 127.0.0.1 -p {port} -c max_connections=20")
        restart = lambda: control('pg_ctl','-D',str(data),'-w','restart','-l',str(directory/'postgres.log'))
        stop = lambda: control('pg_ctl','-D',str(data),'-m','fast','-w','stop')
    admin = f"host=127.0.0.1 port={port} dbname=postgres user=postgres"
    try:
        import psycopg
        for attempt in range(40):
            try:
                with psycopg.connect(admin, connect_timeout=1):
                    break
            except psycopg.OperationalError:
                if attempt == 39:
                    raise
                time.sleep(0.25)
        postgres.close_pool()
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(settings,"postgres_dsn",SecretStr(admin))
            assert migrate() == ["001_video_persistence.sql", "002_source_metadata.sql"]
            assert migrate() == []
            import psycopg
            with psycopg.connect(admin, autocommit=True) as connection:
                connection.execute("CREATE ROLE video_runtime LOGIN NOSUPERUSER NOBYPASSRLS")
                connection.execute("GRANT USAGE ON SCHEMA visualai_video TO video_runtime")
                connection.execute("GRANT SELECT ON visualai_video.schema_migrations TO video_runtime")
                connection.execute("GRANT SELECT,INSERT,UPDATE ON visualai_video.lessons,visualai_video.generations,visualai_video.sources,visualai_video.source_versions TO video_runtime")
            postgres.close_pool()
        yield {"dsn":admin.replace("user=postgres","user=video_runtime"),"admin":admin,
               "restart":restart,"directory":directory}
    finally:
        postgres.close_pool()
        stop()


@pytest.fixture
def postgres_mode(video_cluster, monkeypatch):
    postgres.close_pool()
    monkeypatch.setattr(settings,"lesson_persistence_provider","postgres")
    monkeypatch.setattr(settings,"postgres_dsn",SecretStr(video_cluster["dsn"]))
    monkeypatch.setattr(settings,"postgres_timeout_seconds",3)
    postgres.readiness()
    yield video_cluster
    postgres.close_pool()
