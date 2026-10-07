# Phase 6A.2 — Canonical knowledge database

Date: 7 October 2026. Workspace: `C:\Users\ANVESH\Desktop\AI-VIDEO-GENERATOR`.
Branch: `stabilization-python312`. Initial working tree was clean.

**Authoring and isolated validation only. No live migration has been applied.**
Supabase remains canonical application storage. Qdrant remains a rebuildable
semantic index. This phase introduces no retrieval, frontend or ingestion wiring.
The Phase 6A.1 fail-closed guards remain intact.

## Verified remote baseline and migration mapping

Read-only inspection through the official Supabase MCP against
`hqszkkvuxwdedhegqbec` found PostgreSQL 17.6, the existing 15 public domain
tables, owner-scoped SELECT policies, and authenticated SELECT-only grants on
sources, versions, content, concepts and relationships. Their anonymous grants
are absent. Profiles retain their owner-only provisioning policies.

| Deployed migration | Local artifact |
|---|---|
| `20261005190025 corrected_foundation_schema` | `migrations/20261005185233_corrected_foundation_schema.sql` |
| `20261006142045 source_current_version_index` | `migrations/20261006141158_source_current_version_index.sql` |
| `20261006142056 source_ingestion_transaction` | `migrations/20261006141202_source_ingestion_transaction.sql` |
| Not deployed: `canonical_knowledge_snapshot` | **`migrations/20261007055251_canonical_knowledge_snapshot.sql`** |

`001_supabase_initial_schema.sql` is historical and must never be replayed.
The new filename was generated using Supabase CLI 2.119.0 `migration new`, then
moved from the CLI's `supabase/migrations` directory into the existing repository
`migrations` convention. Historical SQL files are unchanged. Remote timestamps
and local filenames must not be treated as interchangeable deployment history.

Existing source ingestion and index status functions retain their invoker
wrappers, internal definers, empty search paths and UUID owner checks. Their
bodies, ACLs and source status semantics are unchanged.

## Schema and exact scope relationships

Every new domain row uses `(user_id UUID, source_id TEXT, source_version INTEGER)`.
The integer references `source_versions.version`; the existing text display
label, such as `v2`, is not a relational key. Changed uploads can have a new source
ID and lineage; the RPC always requires an explicit ID and integer version.

| Object | Key / additions | Exact foreign keys |
|---|---|---|
| `topics` | PK `(user_id,source_id,source_version,topic_id)`; title, description, sequence, provenance | `(user_id,source_id,source_version)` → `source_versions(user_id,source_id,version)` |
| `subtopics` | PK `(user_id,source_id,source_version,subtopic_id)`; topic, title, description, sequence, provenance | `(user_id,source_id,source_version,topic_id)` → `topics` matching owner/source/version/topic |
| `concepts` (existing) | Nullable `subtopic_id`, `sequence`; object `provenance` | `(user_id,source_id,source_version,subtopic_id)` → `subtopics` matching scope/subtopic; deferred NO ACTION |
| `content_concepts` | PK `(user_id,source_id,source_version,content_id,concept_id,support_kind)`; offsets, extraction confidence, provenance | Scoped content key → existing `content_units(user_id,source_id,source_version,content_id)`; scoped concept key → existing `concepts(user_id,source_id,source_version,concept_id)` |
| `concept_relationships` (existing) | Object `provenance`, `evidence_content_ids TEXT[]` | Existing composite FKs to source version and both concept endpoints remain intact |
| `source_versions` (existing) | Knowledge state, schema version, operation UUID, payload hash, committed timestamp, diagnostics | Existing source/owner/lineage constraints remain intact |

New aggregate FKs use CASCADE on explicit parent deletion, consistent with the
foundation's source and profile lifecycle. Concept primary membership uses
deferred NO ACTION so a source aggregate cascade can complete while isolated
deletion of a referenced subtopic cannot orphan a concept. This migration itself
deletes no data.

Sequence values are nonnegative integers, unique within each parent scope.
Topics order within a version; subtopics within a topic; concepts within their
primary subtopic. Gaps are allowed. There is no implied prerequisite from order.
Multiple concepts can cite a unit and multiple units can support a concept.
Different support kinds can associate the same pair; each kind has at most one
optional span for that pair in this initial schema.

Support kinds: `definition`, `explanation`, `example`, `prerequisite_evidence`.
Offsets are **zero-based, half-open character positions within canonical
`content_units.text`**, not bytes or document-global positions. Both offsets are
present or absent; when present `0 <= start < end <= char_length(text)`.
Extraction confidence is optional and must be numeric in `[0,1]`.

Original content text, page/slide/time, chapter/section, heading path, extraction
method and provenance are never updated by the knowledge RPC. Associations join
the same canonical unit and scope. Generated definitions remain annotations.
`concepts.source_content_ids` is a sorted distinct compatibility projection of
the canonical association table, written in the same transaction; callers cannot
submit an independent evidence-ID array for concepts.

### Indexes

Primary and UNIQUE indexes cover owner/scoped IDs and hierarchical order:

- Topics: scoped PK and unique `(owner,source,version,sequence)`.
- Subtopics: scoped PK and unique `(owner,source,version,topic,sequence)`.
- Concepts: new partial unique `(owner,source,version,subtopic,sequence)` for
  mapped records; historical NULL membership remains valid.
- Associations: scoped content-first PK; reverse
  `(owner,source,version,concept,content)` index supports concept evidence/FKs.
- Versions: partial unique `(user_id,knowledge_operation_id)` when present.

Existing scope and concept endpoint indexes are reused. No indexes are removed.

## Readiness and historical compatibility

`source_versions.knowledge_state` has `PENDING`, `READY`, `FAILED`,
`LEGACY_UNMAPPED`; default `LEGACY_UNMAPPED`. Existing rows receive that state,
and the unchanged Phase 5B writer continues to receive the same default.
Historical concepts/relationships remain readable with nullable membership and
empty added metadata. No automatic backfill or historical deletion occurs.

Only a successful knowledge commit changes a version to READY. A CHECK requires
schema version 1, operation UUID, hash and timestamp together in READY, and NULL
commit metadata otherwise. Diagnostics are an object. PENDING/FAILED are durable
states reserved for a future scheduler; this phase does not expose another
status setter or change existing ingestion.

Knowledge READY is separate from `sources.status` / vector-index readiness.
Future orchestration must commit knowledge before indexing Qdrant and advertise
complete readiness only after both succeed. The database foundation alone does
not enable the Topic Explorer or existing blocked learning APIs.

## Atomic commit contract

Public RPC:

```sql
public.visualai_commit_knowledge_snapshot(
  p_source_id text, p_source_version integer,
  p_operation_id uuid, p_payload jsonb
) returns jsonb
```

No owner, student ID, latest-version alias or admin identity is accepted. The
internal definer obtains `auth.uid()` from the verified Supabase/PostgREST
identity, then locks exactly that caller's `source_versions` row FOR UPDATE.
Missing and foreign scopes return the same `42501 Source version unavailable`.

The payload requires exactly `schema_version: 1` and five arrays: `topics`,
`subtopics`, `concepts`, `content_concepts`, `relationships`. The first four are
nonempty; relationships may be empty. Every row rejects unknown fields and wrong
JSON types. IDs are nonempty bounded ASCII identifiers; source IDs match the
existing SourceScope contract. Sequences/offsets must be integers, not strings or
fractional values. Every record requires object provenance.

Row fields:

- Topic: `topic_id,title,sequence,provenance`; optional `description`.
- Subtopic: `subtopic_id,topic_id,title,sequence,provenance`; optional `description`.
- Concept: `concept_id,subtopic_id,name,sequence,provenance`; optional `definition`.
- Association: `content_id,concept_id,support_kind,provenance`; optional
  `char_start,char_end,extraction_confidence`.
- Relationship: `concept_id,related_concept_id,relationship_type,
  evidence_content_ids,provenance`.

All concepts need at least one genuine canonical evidence association. All
references resolve in the exact caller/source/version scope. A mapping of
historical data must retain every existing concept and edge; incomplete mappings
fail and leave old data intact. Historical concept rows are mapped in place,
preserving their IDs and creation timestamps. No duplicate taxonomy is created.

For each relationship, evidence IDs must refer to canonical associations for the
dependent/source concept. A prerequisite specifically requires
`prerequisite_evidence` support. Unsupported relationship types, self edges,
missing endpoints and unsupported evidence fail. For A → B, **A depends on B**.
Bounded sink removal validates the complete prerequisite DAG without enumerating
all recursive paths; `related` edges do not participate in cycle detection.

Topics, subtopics, mapped concepts, links and edges are persisted together, then
readiness and commit metadata are updated last. There are no caught-and-ignored
exceptions or partial success paths. Any error rolls back the whole call. A
deferred FK error at transaction commit likewise prevents any HTTP success or
visibility to other transactions.

### Idempotency and concurrency

The server hashes normalized JSON using built-in SHA-256. Object order,
whitespace and numeric scale are normalized; array order remains meaningful.
Arbitrary annotation nesting is bounded. The client cannot supply the stored
hash. Commit result includes source/version, READY, schema version, operation ID,
hash and original timestamp.

- Same scope, operation and canonical payload returns the identical stored
  success result, with no writes.
- Changed payload or operation for an already READY version fails with
  `23505 KNOWLEDGE_SNAPSHOT_CONFLICT`; READY snapshots cannot be replaced.
- Reusing an owner's operation UUID on another version fails the unique index
  and rolls back the entire second graph.
- Competing commits serialize on the version row. The loser observes the
  committed snapshot and retries identically or fails instead of overwriting.
- Row-lock waits have a five-second limit (`55P03` timeout). Retry the same
  operation/payload after a transient wait; no failure is converted to success.

Initial operational caps are named constants in the SQL: 2 MiB serialized JSON,
128 topics, 512 subtopics, 1024 concepts, 8192 associations, 4096 edges,
64 evidence IDs per edge, 16 JSON nesting levels and 16,384 characters per string.
These are resource limits, not educational thresholds. Changing them requires a
new reviewed migration and renewed maximum-payload/load tests. Data API request
and statement timeouts can impose smaller effective limits.

## RLS, grants and privileged boundary

All three new tables enable RLS with authenticated SELECT-only policies:
`(select auth.uid()) = user_id`. PUBLIC, anon, authenticated and service_role
default privileges are revoked, then authenticated SELECT is explicitly granted.
There are no direct application INSERT/UPDATE/DELETE grants or write policies.
Existing table privileges and RLS are untouched.

The public wrapper is SECURITY INVOKER; the single internal commit is SECURITY
DEFINER, with fixed empty search_path and fully qualified application, Auth and
catalog references. Helpers are private invokers and cannot be executed by
application roles. Both commit functions revoke PUBLIC/anon/service_role
execution and explicitly grant authenticated execution only. An authenticated
call without a UUID is rejected inside the definer. Calling the internal function
directly has the same checks and bounds; it is not an alternative bypass.

The internal schema is already unexposed under the Phase 5B design. Do not expose
it as a Data API schema. No arbitrary SQL, file access, service-role key, admin
Auth capability or agent mutation API is introduced. New table grants are
explicit because current Supabase Data API defaults need not expose new tables
automatically ([official change](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically)).
The migration uses no extensions affected by the PostgreSQL 17.11 minor update
([official notes](https://supabase.com/changelog/postgres-15-19-17-11-breaking-changes)).

## Reproducible validation

`tests/test_knowledge_database.py` creates a fresh disposable PostgreSQL cluster,
binds only `127.0.0.1`, installs the three historical migrations (never 001), seeds
historical rows, then installs the new migration. It never reads a production
DSN, `.env`, secret or hosted database URL. The temporary server stops in fixture
teardown. Set `VISUALAI_KNOWLEDGE_TEST_PG_BIN` to a local PostgreSQL bin directory.
Absent local binaries, those tests explicitly skip; they do not substitute mocks.

Validation used official EDB portable PostgreSQL 17.11 binaries outside the
repository; no Windows service or global PostgreSQL installation was created.
The remote baseline is 17.6; both are PostgreSQL major version 17. Docker Desktop
was unavailable, so no container results are claimed.

Tests invoke real RPCs and SELECTs as `authenticated`/`anon`, with RLS active.
The test-only `auth.uid()` shim represents PostgREST-provided verified UUID
claims, not a live GoTrue/JWT verification. Fixture creation/catalog inspection
and explicit composite-constraint probes use the local administrator; these are
not claimed as authorized application requests. Existing HTTP Auth tests retain
their real application verification boundaries with mocked upstream transports.
No live account or application data was created for this phase.

Validation commands (PowerShell; point the bin variable at your own local binaries):

```powershell
$env:VISUALAI_KNOWLEDGE_TEST_PG_BIN = '<local PostgreSQL 17 bin directory>'
& .\.venv\Scripts\python.exe -m pytest tests/test_knowledge_database.py -q
& .\.venv\Scripts\python.exe -m pytest tests/test_supabase_repository.py tests/test_supabase_runtime.py tests/test_source_supabase.py tests/test_phase6a1_security.py tests/test_runtime_frontend.py -q
node --test tests/test_frontend_auth.js
& .\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Results: **75 real PostgreSQL tests passed** (44.72 seconds after the final
retry-validation change), **162 targeted schema/Auth/source/security/OpenAPI
regressions passed**, and **14 frontend Auth tests passed**. The maximum-depth
1024-concept prerequisite chain completed in 1.55 seconds in the measured run.
The database tests cover all 22 requested categories, including a forced failure
at the final readiness UPDATE, observed row-lock waits on separate connections,
exact retries, conflicting payloads/operation IDs, actual cross-scope composite
FK violations and default-grant revocation. This is real local PostgreSQL SQL
execution, not mocked SQL and not a hosted deployment.

The final full suite passed: **755 passed, 1 skipped, 4 warnings in 98.84 seconds**.
The skipped test is the existing opt-in legacy file-mode E2E acceptance
(`VISUALAI_RUN_LEGACY_E2E`), not one of the 75 PostgreSQL tests. The four warnings
are existing emissions from three categories:
duplicate dashboard OpenAPI operation ID (twice), unregistered e2e marker and
audioop deprecation. Whitespace checks
include `git diff --check` and `git diff --no-index --check -- NUL <new-file>`
for each untracked deliverable; no whitespace errors were reported (Windows Git
only emitted its existing LF-to-CRLF conversion warnings). No tracked application
file, historical migration, dependency file, Auth setting or Qdrant integration
was changed. Final official MCP inspection still returned exactly the three
deployed migration versions and no new tables/RPC.

## Controlled deployment procedure — approval required

1. Review the exact new SQL and this document. Obtain explicit approval to apply
   **this one migration** to `hqszkkvuxwdedhegqbec`. Do not bulk push local files.
2. Re-read remote history, constraints, grants and RPCs. Confirm the three mapped
   deployments and that this new name/objects are absent; stop on drift.
3. Check current source/version data against the additive constraints; take the
   project's approved backup/snapshot. Schedule the DDL window: ALTER TABLE needs
   locks, new unique indexes scan existing rows, and the migration is transactional.
4. Apply only the reviewed file through official MCP `apply_migration` with name
   `canonical_knowledge_snapshot` and its exact SQL. Record the actual remote
   timestamp returned; do not infer it from the local filename.
5. Read back migration history, three new tables, composite FKs, indexes, readiness
   defaults, RLS, ACLs and empty-search-path function definitions. Verify existing
   Phase 5B function definitions/grants have not changed and schema cache exposes
   the public wrapper. Do not change Auth or exposed-schema settings automatically.
6. Run a separately authorized dedicated-identity live acceptance: owner commit,
   same-operation retry, cross-user read/commit denial, anon/direct-write denial,
   and an unchanged source-ingestion/indexing round trip. Verify through the Data
   API with real verified JWTs, not service-role credentials.

No automatic destructive rollback is proposed. An application regression can
leave the additive foundation unused with existing fail-closed APIs intact.
Any database correction requires a further forward migration; never edit the
deployed file or remove historical data to force deployment.

## Remaining limits and risks

- Remote deployment and live Data API acceptance are intentionally pending.
- CI must provide the local PostgreSQL toolchain; otherwise the database suite
  explicitly skips. Require a real database run before future migration approvals.
- Extraction-to-snapshot orchestration, scheduler PENDING/FAILED writes, canonical
  DTOs, topic reads and retrieval hydration belong to later phases.
- Existing privileged operators can mutate existing tables outside the RPC;
  trusted administration must preserve READY snapshot invariants. Normal clients
  cannot perform those writes. No claim is made against a database owner who can
  alter constraints or function bodies.
- Legacy graphs lacking evidence or containing cycles remain LEGACY_UNMAPPED
  until a complete supported mapping can be supplied. The migration does not
  fabricate evidence or silently repair prerequisites.
- Identifier/size limits can reject oversized legacy annotations; callers must
  produce a supported bounded snapshot rather than silently truncate it.
- One span per support kind is an explicit initial model limit. Future multiple
  spans require an additive evidence identity design, not duplicate concept rows.
- Existing test warnings (OpenAPI duplicate operation ID, unregistered e2e mark,
  deprecated audioop) predate this migration and are outside this phase.
