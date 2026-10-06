# Supabase source persistence slice

The source provider changes only when `DATABASE_PROVIDER=supabase`. The checked-in
configuration and ignored `.env` provider were not globally switched. In that mode,
use a Supabase bearer session with `/upload`, `/pipeline/upload-and-assess`, `/sources`,
and the source read/retry routes. File/local mode retains the existing workflow.

## Inspected flow and bypasses

Before this slice both `app/api/upload.py` and `app/api/pipeline.py` called
`app/services/registry.py` directly, bypassing `get_source_repository()`:

| State | Previous access | Supabase-mode access |
|---|---|---|
| Source registration/status/list/read | `register_source`, `save_source_record`, `update_source_status`, `get_source_record`, `_load_sources_index`; `sources_index.json` | Authenticated source factory; owner-filtered REST reads; ingestion/status RPCs |
| Version registration | `_record_source_version`; `source_versions.json` | Same atomic ingestion RPC; owner-filtered version reads |
| Content units | `save_content_units`, `load_content_units`; per-source `content_units.json`, fixture/legacy fallbacks | Same atomic ingestion RPC; owner-filtered version-scoped unit reads |
| Normalized/sanitized/quarantined evidence | Partitioned JSON helper writes in both upload paths | Existing JSONB columns on `source_versions`, committed with the aggregate |
| Rich chunks | Local `rich_chunks.json` writes | Existing `source_versions.rich_chunks`; deterministic retry reads this durable payload |
| Knowledge graph/concepts | Local knowledge-graph JSON | Remains local, unchanged domain architecture |
| Uploaded binaries | Owner/source filesystem directory plus legacy copy | Owner/source filesystem directory; durable `file_location` in Supabase |

Legacy canonical source JSON functions now fail explicitly in Supabase mode, so an
unconverted caller cannot accidentally read stale local source state or report a
successful local write. Existing assessment/video routes using those functions are
not integrated with Supabase sources in this phase. No other domain stores changed.

## Commit and retry

1. Verify the user with `get_current_user`; create its repository through the factory.
2. Validate and preserve the binary; extract, normalize, sanitize, structure and chunk.
3. Commit source, version, content units and version evidence in one PostgreSQL RPC.
4. Read committed chunks and index the existing Qdrant implementation.
5. Record `READY`, or retain the aggregate and record `FAILED` with an error class.

The deployed source tables grant authenticated users SELECT only. The new private
`visualai_internal` functions therefore use SECURITY DEFINER with empty search_path,
explicit `auth.uid()` ownership/provenance checks, an aggregate advisory lock and
restricted EXECUTE privileges. Public wrappers use SECURITY INVOKER. Existing RLS
and direct table-write permissions remain unchanged. Any insert constraint failure
rolls back the complete RPC, including the source/current-version deferred FK.

IDs derive from verified owner, filename and binary hash. Repeating an upload or
retrying `/sources/{source_id}/retry-index` reuses the immutable aggregate and stored
chunk IDs. Changed content retains the existing application's new-source/per-upload
version semantics, including parent linkage; this is not a new source-version model.

The legacy background Qdrant fallback, including temporary in-memory Qdrant, is not
used by the Supabase path. Qdrant remains the semantic index. Index failures cannot
produce READY. A cancelled job may leave a running thread; its input remains until
the thread finishes, and durable source state can be queried/retried independently.
Job telemetry is owner-scoped and never stores bearer tokens. Jobs themselves remain
in-memory, so after restart retry by durable source ID or repeat the same upload.

`/pipeline/upload-and-assess` queues source-only work in Supabase mode. Automatic
assessment handoff and assess-existing return an explicit unsupported response until
their source read boundary is integrated. Frontend files were not rewritten.

## Verification

- Targeted tests cover mapping, verified ownership, spoofed caller identity, one RPC,
  no local fallback, commit-before-index ordering, indexing failure, deterministic
  retries, canonical reads, file compatibility, secrets and background job ownership.
- One retained TXT acceptance aggregate: `SRC_ab3f8ac69bda5da4b545b05afa4ac3ce`.
  It has one source, one version and two content units; current-version linkage is valid.
- The same aggregate first failed a late content constraint and fully rolled back.
  A controlled Qdrant outage then preserved the committed aggregate as FAILED; normal
  indexing retry reached READY without duplicates.
- Owner reads, anonymous denial, fresh Python/FastAPI-process reads, and database RLS
  checks under a different existing authenticated UUID passed. A cross-owner status
  RPC was also denied.
- Live acceptance used the normal configured Supabase account and deterministic
  extraction/structure/embedding test mode, with the existing persistent Qdrant index.
  It does not certify external model quality or production model-provider availability.
- `sources_current_version_fk` is covered by the new four-column index. Assessment FK
  indexing is deferred and existing unused indexes remain intact.
- Security advisor: [leaked-password protection is disabled](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
  Auth settings were not changed.

Only the two new migrations may be deployed for this slice. Do not apply historical
`001_supabase_initial_schema.sql` or redeploy the corrected foundation to this project.
