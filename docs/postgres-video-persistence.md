# Local PostgreSQL integration for educational lessons and videos

For the newer, separately activated canonical upload and dependent learning
storage, see [PostgreSQL learning persistence](postgres-learning-persistence.md).
The original scope below describes the video-only integration baseline.

## Baseline and scope

Branch `video-generation`, initial commit `b098de7`. Before edits, the targeted
Video API baseline passed **61 tests**, one Starlette deprecation warning,
10.85 seconds. Existing unrelated untracked files `LEARNING_PIPELINE_AUDIT.md`
and `newfront/package-lock.json` were preserved.

The application already has synchronous Supabase HTTP repositories, SQL migrations,
Supabase authentication, Qdrant, an SQLite ingestion/pipeline job tracker, atomic
owner-scoped lesson JSON, generation history and cross-process execution locks.
No ORM or PostgreSQL Python driver was installed. Existing Compose already runs
the API and Qdrant. These implementations are reused, not replaced.

This change adds an **explicit PostgreSQL backend for educational lessons and
their video jobs/history**, through the existing save/load functions. It does
not migrate Supabase sources, source versions, knowledge, profiles, assessment
RPCs or remediation RPCs. Those remain canonical in Supabase; source IDs and
versions in the local lesson database are references, not duplicate source tables.
The existing ingestion SQLite tracker and legacy local Video API remain unchanged.
There is no cross-database transaction spanning Supabase, Qdrant, files and PostgreSQL.

## Architecture and preservation

- `LESSON_PERSISTENCE_PROVIDER=file` preserves existing explicit JSON mode.
  `postgres` selects PostgreSQL; failures never fall back to JSON or memory.
  `DATABASE_PROVIDER` remains the existing source/authentication setting; do not
  set it to `postgres`.
- `app/core/postgres.py` owns a bounded synchronous Psycopg pool, safe errors,
  transactions and readiness. Startup checks the database and migration, but
  runs no DDL. Shutdown cancels educational tasks on its own event loop before
  closing the pool. Existing lazy recovery uses the real job execution lock.
- `app/services/repositories/lesson_store.py` is the persistence seam. The existing
  merge logic, public schemas, API URLs and renderer remain in place. Both
  owner-scoped lesson listing and reverse source-to-scene lookup use this seam.
- `visualai_video.lessons` stores owner/lesson/source/version/timestamps and the
  structured lesson document, excluding generation history.
- `visualai_video.generations` stores each job's status/stage/progress/errors,
  indexing state, timestamps, predecessor, stable history order and generation
  JSONB containing the plan, narration, scene timing, evidence and artifact references.
  Composite primary/foreign keys prevent cross-owner/cross-lesson predecessors.
- One transaction commits the lesson and all generation changes. Existing
  OS/thread locks are preserved; a transaction-scoped PostgreSQL advisory lock
  serializes cooperating processes, including deduplication and stale updates.
  The lock is deliberately coarse. Execution ownership still requires the
  existing **shared local runtime filesystem**: this is not a multi-host worker queue.
- Verified Supabase identity remains the HTTP authority. Every data query filters
  owner ID, and private tables enforce/force RLS using transaction-local identity.
  The API must connect as a restricted backend role; readiness rejects superuser
  and BYPASSRLS roles. The identity setting is for a trusted backend connection,
  not a substitute for user JWT verification or safe client-side SQL access.
- MP4/WAV/VTT and intermediate files remain in existing storage directories.
  New completed artifact paths must exist and stay inside approved media roots.
  Previously stored metadata survives later media loss; playback reports missing
  files, and unrelated metadata updates remain possible. No automatic media deletion.
- Qdrant remains independent. Failed indexing is persisted without changing a
  completed video's status or preventing playback.

## Required software and configuration

Use Docker Desktop with Compose v2, the repository's Python virtual environment,
and existing media tools. Install only the added dependencies if the rest of the
environment is already installed:

```powershell
Set-Location 'D:\ai video generator\AI-VIDEO-GENERATOR'
.\.venv\Scripts\python.exe -m pip install 'psycopg[binary]==3.3.6' 'psycopg-pool==3.3.3'
```

Configure privately in the existing `.env`; this integration never overwrites it:

| Variable | Purpose |
| --- | --- |
| `POSTGRES_DB` | Local database name, for example `visualai` |
| `POSTGRES_USER` | Bootstrap/migration administrator, for example `visualai_admin` |
| `POSTGRES_PASSWORD` | Strong private bootstrap password, no default |
| `POSTGRES_PORT` | Host port; defaults to `5433` |
| `POSTGRES_DSN` | Private backend connection string with host, database and user |
| `POSTGRES_POOL_SIZE` | 1–32 connections per process; default 4 |
| `POSTGRES_TIMEOUT_SECONDS` | Connection/acquisition/query/lock bound; default 10, maximum 60 |
| `LESSON_PERSISTENCE_PROVIDER` | `file` or `postgres`; switch after migration/import |

Host FastAPI uses host `127.0.0.1`, port `5433`. An example DSN shape is
`postgresql://visualai_app:<URL-encoded-password>@127.0.0.1:5433/visualai`.
This is a placeholder, not a credential. Require appropriate TLS when using a
non-local database. Keep bootstrap and runtime credentials separate.

## Start PostgreSQL and migrate explicitly

```powershell
docker compose --env-file .env -f compose.postgres.yml up -d postgres
docker compose --env-file .env -f compose.postgres.yml ps
docker compose --env-file .env -f compose.postgres.yml exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

The service uses PostgreSQL 18.3, a named volume mounted at `/var/lib/postgresql`
as required by the PostgreSQL 18 image, loopback-only host binding, a health check
and `unless-stopped`. It does not start the API or Qdrant. Do not use `down -v`.
Changing bootstrap environment values after initialization does not change existing
database users/passwords; manage existing roles explicitly.

Stop FastAPI and other generation workers before import/cutover. Back up JSON and
media first. Temporarily configure `POSTGRES_DSN` with the local migration
administrator credential through your private environment, then run:

```powershell
.\.venv\Scripts\python.exe -m app.db.video_migrations
```

The runner applies only `app/db/video_migrations/*.sql`, not historical Supabase
migrations. It uses one transaction, a schema migration ledger and checksums;
rerunning unchanged migrations is a no-op. Changed historical migration checksums
fail. No reset, drop or automatic startup migration is performed.

Create the restricted runtime role interactively (replace names if configured
differently):

```powershell
docker compose --env-file .env -f compose.postgres.yml exec postgres psql -U visualai_admin -d visualai
```

```sql
CREATE ROLE visualai_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
\password visualai_app
GRANT USAGE ON SCHEMA visualai_video TO visualai_app;
GRANT SELECT ON visualai_video.schema_migrations TO visualai_app;
GRANT SELECT, INSERT, UPDATE ON visualai_video.lessons, visualai_video.generations,
    visualai_video.sources, visualai_video.source_versions TO visualai_app;
\q
```

The `\password` command prompts privately; no password appears in the commands.
If this role already exists, review it rather than recreating it. Do not give the
runtime role CREATE, DELETE, SUPERUSER or BYPASSRLS privileges. Configure
`POSTGRES_DSN` with this restricted role, and set
`LESSON_PERSISTENCE_PROVIDER=postgres` before importing.

## Source metadata copies (October 11 update)

The baseline for this update was branch `postgre-implementation`, commit `7430cc0`,
with only the unrelated untracked `LEARNING_PIPELINE_AUDIT.md`; that file is preserved.
The targeted existing baseline passed 79 tests, one existing Starlette warning.
Live Docker PostgreSQL 18.3 was healthy, published only on `127.0.0.1:5433`, with
the existing named volume mounted at `/var/lib/postgresql`. The configured
restricted runtime role connected successfully. Lessons and generation JSONB
already persisted plans, narration, caption paths, history and versions.
Source metadata was the confirmed missing storage category.

The approved design keeps Supabase as the canonical source/content/knowledge
transaction boundary and adds durable **metadata copies**, not a second canonical
ingestion engine. Apply the additive `002_source_metadata.sql` through the same
explicit migration runner and grant the runtime role access to the two new tables
as above. Startup now checks both migrations and SELECT/INSERT/UPDATE privileges.
There is no automatic DDL and no destructive migration.

- `visualai_video.sources`: owner, source ID, latest version, source metadata JSONB
  (filename, type, hashes, status, timestamps, etc.) and copy timestamp.
- `visualai_video.source_versions`: owner/source/version key and version metadata
  (hashes, filename, file location, provenance), with copy timestamp.
- Both tables enable and force owner RLS. No credentials, binary media, extracted
  content arrays, rich chunks, topic blueprints or knowledge diagnostics are copied.
- Authenticated canonical source reads, successful ingestion RPC results and
  indexing status updates refresh copies. Version reads refresh the selected
  version; reading an older version cannot roll back the latest version number.
- Supabase and local PostgreSQL cannot share a transaction. A failed local copy
  returns a safe retryable `SOURCE_METADATA_COPY_PENDING` error (503 for HTTP),
  explicitly stating that canonical data remains in Supabase. It never rolls back
  or deletes a successful remote commit. Retry an owned source/version read or
  source indexing after PostgreSQL recovers to repair the copy.

Existing sources are copied lazily as authenticated users access them. To reconcile
all versions for one user, run this explicit command and enter that user's valid
Supabase access token at the hidden local prompt (never paste it in chat, shell
arguments, logs or Git):

```powershell
.\.venv\Scripts\python.exe -m app.db.sync_source_metadata
```

The command verifies the user through Supabase Auth, reads only that user's rows
using their JWT and RLS, and prints aggregate counts only. It is idempotent and
can repair partially copied batches. Repeat per user when a complete historical
backfill is required; it has no admin bypass. Remote reads remain necessary for
authorization and canonical content: these copies do not provide offline source
access. External Supabase edits are reflected on the next canonical read or
explicit reconciliation, not through a continuous replication service.

Docker-backed tests can opt in without touching the developer DSN or real volume:

```powershell
$env:VISUALAI_VIDEO_TEST_DOCKER_WSL = 'Ubuntu'
.\.venv\Scripts\python.exe -B -m pytest tests/test_source_metadata_postgres.py tests/test_video_postgres.py -q -p no:cacheprovider
```

The fixture uses the already available `postgres:18.3` image, a unique disposable
container and volume, and an explicitly reserved loopback port. It removes only
its own container and anonymous volume. Existing local-binary test mode remains
available through `VISUALAI_VIDEO_TEST_PG_BIN`.

### Verification of the update

The additive migration was applied to the user's local Docker database, and the
existing restricted runtime role received only SELECT/INSERT/UPDATE on the two
new tables. `/health/database` returned `ready`; PostgreSQL and its existing named
volume were not restarted, reset or replaced. All four application tables have
both RLS flags enabled. Aggregate live inspection found 32 existing lessons and
8 completed video generations, all with scene plans; 7 contain caption paths
(legacy records are allowed to lack captions). Authenticated dashboard listing
created 24 source metadata copies, and opening an uploaded source created a
source-version copy. This does not assert a complete historical backfill for all
users or versions.

The signed-in browser loaded an existing Binary Search Trees lesson and its
saved generation. Authenticated stream, scene metadata and captions requests
returned HTTP 200. The video reached readyState 4 without a media error, with
duration 35.356575 seconds, one caption track and five scene-navigation buttons.
Clicking the worked-example scene updated the selected scene evidence. This
checks existing saved media; it is not a claim that a new live AI render or all
providers were verified.

The first Docker test run exposed test-fixture issues: content-derived source IDs
collided across cases, and an automatically published port changed on container
restart. Tests now use unique source content and explicitly reserve the published
port, waiting for SQL readiness after restart. The final focused Docker run passed
32 tests, one existing Starlette deprecation warning. This includes actual SQL/RLS,
copy-failure repair, stale-metadata protection, reconciliation, database restart,
process termination/recovery and the existing real-renderer completion test with
synthetic test narration/provider doubles.

The final combined regression command (source metadata, video PostgreSQL,
Supabase source orchestration, educational content/lesson features, generation
foundation, video reliability/process recovery/enhancements and canonical
retrieval) passed **172 tests**, one existing Starlette warning, in 107.23 seconds.
FastAPI was restarted with the final code; PostgreSQL readiness remained `ready`,
Supabase Auth remained connected and the new uploaded-material lesson restored
successfully after the application restart. `git diff --check` passed. No commit,
push, environment-file edit or modification of the unrelated audit file was made.

Qdrant's API remained connected, but its existing running container reports
unhealthy because an older health check invokes unavailable `wget`. Repository
Compose already has a replacement health check. The running Qdrant service was
not recreated as part of the PostgreSQL changes. The saved video also reports an
unavailable embedding model; playback remains available, and indexing/search
verification requires that model to be restored separately.

## Preserve existing JSON lessons/history

With workers stopped and the original artifact paths available:

```powershell
.\.venv\Scripts\python.exe -m app.db.import_video_lessons --directory storage/runtime/educational_lessons
.\.venv\Scripts\python.exe -m app.db.import_video_lessons --directory storage/runtime/educational_lessons --apply
```

First command only validates. Import validates owner-directory/lesson identity and
completed media references. It never changes JSON or media. Identical records are
skipped; a conflict rejects the whole transaction. Keep your original files and
backup. If switching between host/container paths, preserve their meaning or plan
an explicit reviewed path conversion; do not silently rewrite provenance. Starting
PostgreSQL mode without an import shows only PostgreSQL lessons; it does not read
JSON as a fallback. Rollback to JSON mode requires a deliberate plan for records
created since cutover; there is no automatic bidirectional sync.

## Start and verify the actual job lifecycle

```powershell
.\.venv\Scripts\python.exe -m app.main
Invoke-RestMethod http://127.0.0.1:8000/health/database
Invoke-RestMethod http://127.0.0.1:8000/health/qdrant
```

Database readiness returns `ready`, or a safe 503 code. `/health` stays application
liveness. Sign in normally, open an owned lesson, generate a video through the
existing `POST /educational-content/{lesson_id}/video` route, and poll the existing
`GET /educational-content/{lesson_id}/video/status`. Verify measured captions,
scene navigation and private playback as before. Generate a second version and
confirm the original generation still plays using its `generation_id`.

Inspect records privately as the administrator, without dumping lesson documents:

```sql
SELECT owner_id, lesson_id, job_id, prior_job_id, status, stage, progress,
       error_code, indexing_status, created_at, completed_at
FROM visualai_video.generations ORDER BY created_at DESC LIMIT 20;
```

Restart only the database:

```powershell
docker compose --env-file .env -f compose.postgres.yml restart postgres
Invoke-RestMethod http://127.0.0.1:8000/health/database
```

Confirm saved rows/history and media still exist. Restart FastAPI and load a saved
lesson. A nonterminal job without a held execution lock becomes
`FAILED / VIDEO_JOB_INTERRUPTED`; retry creates a new generation. A live lock
prevents false interruption. A database outage causes safe failure, not an
unpersisted successful response. Work interrupted during an outage is reconciled
on the next lesson read once the database returns; unfinished renders are not resumed.

For the already-containerized API, combine the files when you intentionally want
one network: `docker compose -f docker-compose.yml -f compose.postgres.yml ...`.
Set its DSN host to `postgres`, port `5432`, retain `./storage:/app/storage`, and
recreate the API only after migration/import review. Merely starting the standalone
database does not reconfigure an existing API container.

## Backup and restore separately

Back up PostgreSQL, media/JSON/SQLite under `storage`, and Qdrant independently.
Pause generation for a consistent application snapshot; database backup alone
cannot restore media. Use a native PostgreSQL custom-format dump inside the
container, then copy it out to avoid PowerShell binary-redirection corruption:

```powershell
docker compose --env-file .env -f compose.postgres.yml exec postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/visualai.dump'
$pgContainer = docker compose --env-file .env -f compose.postgres.yml ps -q postgres
docker cp "${pgContainer}:/tmp/visualai.dump" .\visualai.dump
```

Keep the dump private and outside Git. Back up the named volume/storage using your
existing backup tool, and use Qdrant snapshots for vectors. Restore into a **new,
empty database**, never reset the current database:

```powershell
docker cp .\visualai.dump "${pgContainer}:/tmp/visualai-restore.dump"
docker compose --env-file .env -f compose.postgres.yml exec postgres createdb -U visualai_admin visualai_restore
docker compose --env-file .env -f compose.postgres.yml exec postgres pg_restore -U visualai_admin -d visualai_restore --exit-on-error /tmp/visualai-restore.dump
```

Roles are cluster-wide and not included by `pg_dump`; provision the reviewed
runtime role/grants on a new cluster. Restore matching media paths and compatible
Qdrant snapshots before pointing the application at the restored database.

## Tests and operational limitations

Real database tests use a new disposable loopback-only cluster and a restricted
runtime role. They never read a production DSN or mutate the existing database.

```powershell
$env:VISUALAI_VIDEO_TEST_PG_BIN='C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe -B -m pytest tests/test_video_postgres.py -q -p no:cacheprovider
```

Actual results on 2026-10-11:

| Executed check | Result |
| --- | --- |
| Pre-change Video API baseline | 61 passed, one warning, 10.85 s |
| Initial PostgreSQL lifecycle suite | 17 passed, one warning, 18.88 s |
| PostgreSQL suite including real rendering/failure | 19 passed, one warning, 33.28 s |
| Broad PostgreSQL/video/retrieval/lesson/personalization/Supabase-runtime regression | 256 passed, two warnings, 154.89 s |
| Follow-up PostgreSQL suite including traceability/corrupted captions | 24 passed, one warning, 36.85 s |
| Final required-completion-write failure injection | 1 passed, one warning, 7.83 s |
| Frontend topic workspace/learning/profile regression | 65 passed, zero failures, 205.536 ms |
| Compose YAML parse and loopback/volume/required-password assertions | Passed; not a Docker Compose execution |
| `git diff --check` | Passed |

These runs overlap; do not sum them as distinct tests. The real cluster uses
installed **PostgreSQL 18.6**, not a Docker container. Tests verified fresh migration,
idempotency, checksum rejection, nonprivileged RLS, transaction rollback, real
generation completion, failed jobs, authenticated streaming/captions, missing media,
regeneration/history order, real concurrent child processes and forced termination,
fresh-process recovery, PostgreSQL restart persistence, import dry run/idempotency/
whole-batch conflict rollback, traceability and indexing failure isolation.
The final injected required completion-write failure produced a persisted failed
generation, never a completed one. Connection failure prevents startup and health
returns a safe 503 without secrets or a fallback.

One regression during development exposed cross-event-loop task cancellation on
shutdown; the implementation now cancels only tasks belonging to its own loop,
and the original test passes. An initial database test run also had seven fixture
setup errors because the imported service fixture's `context` dependency was not
registered in the new test module; the fixture import was corrected. Tests were
not weakened to make these cases pass.

Synthetic test narration and mocked Supabase HTTP transports are distinct from actual SQL/rendering tests.
Live Supabase RLS, a production import, Docker volume restart, and real embedding
search are not established by those tests.

Common errors: missing DSN/invalid provider (configuration),
`VIDEO_DATABASE_MIGRATION_REQUIRED` (run the explicit migration with administrator),
`VIDEO_DATABASE_PRIVILEGED_ROLE` (use restricted runtime role),
`VIDEO_DATABASE_UNAVAILABLE` (server, network, grants or transaction failure),
`VIDEO_ARTIFACT_REFERENCE_INVALID` (new completed media missing/outside approved
storage), and `IMPORT_VALIDATION_FAILED` (owner/path/conflict/JSON/media issue).
Health responses never include credentials or a DSN. Consult private server logs
for detailed connection diagnosis; do not paste secrets into public reports.

Docker CLI/Desktop was unavailable in this environment. Docker image pull,
Compose health, named-volume restart and container API checks remain blocked.
Locally installed PostgreSQL enables independent real SQL/restart verification.
No existing `.env`, production database, Supabase migration or media was changed.
No AI agents, learning loop, new ORM or queue infrastructure was introduced.

## Changed files and final boundary

| Files | Responsibility |
| --- | --- |
| `compose.postgres.yml`, `.env.example`, `.gitignore` | Independent local database, placeholder configuration, private dump/env exclusions |
| `requirements.txt`, `app/core/config.py`, `app/core/postgres.py` | Pinned driver/pool dependencies, validated configuration, pool/transaction/readiness lifecycle |
| `app/db/video_migrations.py`, `app/db/video_migrations/001_video_persistence.sql` | Explicit checksummed migration and private lesson/generation schema |
| `app/db/import_video_lessons.py` | Non-destructive validated legacy import |
| `app/services/repositories/lesson_store.py` | File/PostgreSQL persistence seam, transaction-local ownership, artifact validation |
| `app/services/educational_content.py`, `app/services/video/educational_video.py` | Existing save/load/list/traceability paths use the selected backend |
| `app/main.py` | Startup readiness, safe error/health response and bounded shutdown |
| `tests/conftest.py`, `tests/video_postgres_fixture.py`, `tests/test_video_postgres.py` | Production-DSN isolation and real PostgreSQL/lifecycle/failure coverage |
| `docs/postgres-video-persistence.md` | Baseline, architecture, setup, verification, backup/restore and limitations |

The PostgreSQL integration is delivered on `postgre-implementation`, branched
from `video-generation`. Unrelated untracked files are excluded from this change.
The next deployment step is to make Docker available, configure private local
credentials, start the standalone Compose service, apply the migration with an
administrator, provision the restricted runtime role, and dry-run/import existing
lessons with workers stopped. Acceptance: container health is healthy; database
readiness is ready under the restricted role; imported version/history counts and
media match; a newly generated video remains accessible after container and API
restarts; owner isolation and indexing failure behavior still hold. Container
backup/restore and authenticated live browser verification also remain manual.

Implementation references: [official PostgreSQL image](https://hub.docker.com/_/postgres)
and [Psycopg connection pooling](https://www.psycopg.org/psycopg3/docs/advanced/pool.html).
