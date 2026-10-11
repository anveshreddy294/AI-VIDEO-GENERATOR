# PostgreSQL canonical learning persistence

## Baseline, 2026-10-11

Branch: `postgre-implementation`, HEAD `5f89ff6c7fa01f37f66a03d1d709e981819c8b73`.
The working tree already contained the Qdrant and source-preparation repairs;
those changes and the user's untracked audit were preserved. No Git mutations.

Targeted baseline: **85 passed, 8 skipped, 1 warning** (`test_source_supabase`,
`test_source_metadata_postgres`, `test_content_understanding`). The real database
fixture was not enabled for this baseline invocation; skipped tests are not proof
of persistence. The preceding broader baseline was 1656 passed, 139 skipped.

Before this change, canonical source content and knowledge lived in Supabase.
Docker PostgreSQL held lesson/video documents and metadata-only source copies.
Simply changing a provider would break session/assessment foreign keys and RPCs.
The user explicitly selected moving dependent session and assessment storage too,
while retaining Supabase Auth and Qdrant and leaving historical sources in place.

Inspection found deployed schema drift: knowledge extension/rebuild and
remediation-video functions exist in Supabase but have no repository migration.
The new SQL is a **structural snapshot only**, obtained from PostgreSQL catalogs
on 2026-10-11. No user rows, tokens or credentials were exported. It preserves
the actual deployed constraints, triggers, snapshot validation and assessment
transactions rather than replaying incomplete historical migrations.

## Storage boundaries

- New source/version records, normalized and sanitized extraction, quarantined
  extraction, rich chunks, topics/subtopics/concepts, evidence and relationships:
  `visualai_learning` in the configured Docker PostgreSQL database.
- Sessions, assessments/questions/attempts and their existing progress/remediation
  dependencies for those new sources: the same private schema.
- Lessons, video status/history/version documents and scene/caption metadata:
  existing `visualai_video` tables.
- Media bytes: existing persistent filesystem; embeddings: existing Qdrant.
- Identity verification and existing learner-profile preferences: Supabase.
- Historical sources and sessions: read and mutate through their original
  Supabase repositories. No bulk backfill or automatic data deletion.
  Existing upload deduplication is preserved: matching an old source reuses that
  source; a genuinely new source aggregate is written to PostgreSQL.

## Implementation and activation

The existing repository request/response contracts remain unchanged.
`learning_storage.py` accepts only bounded, allowlisted domain reads and RPCs,
using parameterized direct PostgreSQL statements. It is not an HTTP endpoint.
Repositories verify Supabase identity before binding the storage adapter.
RPCs with a user argument require that exact verified owner both in Python and
SQL. The database runtime has neither superuser nor BYPASSRLS. All local tables
force owner RLS; all functions use invoker permissions. No local Auth replacement
or service-role identity impersonation is introduced.

`SOURCE_PERSISTENCE_PROVIDER=supabase` preserves existing behavior by default.
The `postgres` setting requires the existing PostgreSQL lesson provider and
Supabase authentication mode. Apply the separate checksummed additive learning
migration with a deployment role, grant the existing nonprivileged runtime role,
verify readiness, and only then activate the setting. The app never applies DDL
on startup. Database failure cannot redirect a new-source write into Supabase.

Cross-store lists are merged before pagination and reject duplicate identities.
They have an explicit 10,000-row bound per store; larger datasets require a
dedicated pagination contract rather than silent truncation.

## Acceptance checks

Use a disposable PostgreSQL instance first: migrations and repeat application;
owner isolation; atomic source/version/content commit; canonical evidence and
snapshot idempotency; session selection/pinning; assessment create/submit;
restart persistence; historical routing; explicit database-failure behavior.
Then apply only to the identified local Docker database and verify a new upload
through normal authenticated browser/API requests. Existing media and historical
records must remain accessible. Report live and simulated checks separately.

## Executed verification and local deployment

- Targeted real PostgreSQL regressions: **44 passed, 1 warning**, including
  **12 new learning-store tests**. They cover a disposable database restart,
  actual extraction/knowledge commits, atomic rejection, repeat commits,
  session creation, assessment creation/submission/idempotency, owner isolation,
  SQL injection rejection, historical routing, and no write fallback on failure.
  AI structure proposals and vector writes are mocked in these tests; SQL is real.
- Full backend regression: **1668 passed, 139 skipped, 5 warnings**, 235.86 seconds.
  Optional skipped suites were not executed and are not counted as verified.
- Frontend regression: **118 passed, 0 failures**, 252.15 ms.
- `git diff --check` passed. Existing unrelated changes were preserved.
- Existing local database verified: loopback port 5433, database `visualai`,
  runtime role `visualai_app`, container `ai-video-generator-postgres-1`, existing
  volume `ai-video-generator_video_postgres_data`. PostgreSQL and Qdrant healthy.
- Before local DDL, created an ignored custom-format PostgreSQL backup:
  `storage/runtime/backups/postgres-learning-20261011T030131Z.dump`, 92,814 bytes,
  SHA256 `38dbd052ec2d806d80902a8a23400f69aa7c3e81c28136aabea45679cca4ae41`.
- Applied `learning/001_learning_persistence.sql` to **local Docker only**,
  granted the existing restricted runtime role, and passed readiness. No hosted
  migration or old-source backfill. Enabled the single new local `.env` setting
  `SOURCE_PERSISTENCE_PROVIDER=postgres` and restarted the owned local API.
  Credentials and existing provider/model settings were not changed.
- Normal authenticated dashboard upload: `postgres-storage-20261011.txt`,
  source `SRC_abe71ecc0c7f5e15a6033cdf7e854e31`, version 1. PostgreSQL inspection
  confirmed 7 content units and 7 normalized, sanitized and rich-chunk records.
  A separate read-only hosted query confirmed **zero** Supabase source rows for
  this new source. The dashboard restored all 25 older sources and displayed
  26 sources after upload.
- Live knowledge preparation failed with **STRUCTURING / MODEL_TIMEOUT**.
  The new upload's canonical extraction remained stored in PostgreSQL. No live
  topics/concepts or browser session/assessment were created for this upload.
  Those SQL transactions passed the isolated tests, with the AI response mocked;
  live verification remains blocked on the configured provider returning valid
  content. No provider change or relaxed evidence validation was used.
- Restarted the local API after this upload and verified all 7 normalized,
  sanitized and chunk records remained intact. The new material reappeared in
  the authenticated dashboard. All 12 existing generation metadata records
  remained readable in `visualai_video`; no historical artifacts were replaced.

No commit, push, hosted migration, package installation or agent system was
added for this storage change. The local server was left running.

Activation is a storage change, not a model change. Rollback of activation uses
`SOURCE_PERSISTENCE_PROVIDER=supabase`; it does **not** migrate new local rows
back to Supabase, so those rows require reactivation to be accessible. Leave
the additive tables and backup intact. Do not drop schemas as a rollback.
