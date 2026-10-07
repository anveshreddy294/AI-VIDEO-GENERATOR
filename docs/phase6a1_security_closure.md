# Phase 6A.1 — Verified identity and source-version security closure

Date: 7 October 2026 (Asia/Calcutta). Workspace: `C:\Users\ANVESH\Desktop\AI-VIDEO-GENERATOR`. Branch: `stabilization-python312`.

Outcome: **fixed by enforcing authorization and failing closed for unsupported Supabase consumers**. This is not an implementation of canonical learning persistence or centralized RAG.

## Baseline and evidence

The required `docs/phase6a_knowledge_architecture.md` was read before editing. Initial Git status contained only that untracked architecture document; it was preserved unchanged. Existing authentication verifies tokens through Supabase GoTrue and validates issuer, audience, expiry and UUID subject. Source APIs use the caller token and canonical Supabase repository.

The audit followed actual router registration in `app/main.py`, request DTOs, caller-provided identity fields, repository factories, direct local stores, artifact lookups, QA traces and all retrieval consumers. A separate read-only security investigation and one independent candidate review challenged sibling paths. Review identified direct assessment retrieval outside `vector_store`; that path was confirmed and guarded before supplied chunks or Qdrant access.

## Endpoint-level inventory

The following **33 route/method pairs** now have the shared verified boundary in the registered application. In Supabase mode, anonymous requests receive 401; valid tokens receive 409 `SUPABASE_LEARNING_NOT_INTEGRATED` before handlers run. A foreign identity in an existing path receives generic 404 after authentication. Missing and present resource IDs produce the same unsupported response; local stores are not probed.

| Method / endpoint | Concrete pre-fix risk or compatibility issue |
|---|---|
| POST `/assessment/start` | Caller student/source identifiers and local assessment state; no canonical request ownership boundary. |
| POST `/assessment/handoff` | Caller identity and local source/graph handoff. |
| POST `/assessment/submit` | Session lookup and scoring write before verified tenant authorization. |
| GET `/assessment/profile/{student_id}/{source_id}` | Caller path identity reads local profiles. |
| GET `/assessment/status/{session_id}` | Session ID lookup lacks canonical owner verification. |
| GET `/assessment/session/{session_id}` | Same issue, exposing session data. |
| GET `/assessment/video-target/{student_id}/{source_id}` | Caller identity selects local target matrix. |
| GET `/instructor/` | Static legacy portal, not a private-record exposure; included in router compatibility boundary. |
| GET `/instructor/api/overview` | Shared operator key and global local profile analytics, not verified tenant/role scope. |
| POST `/instructor/api/reset-mastery` | Shared key/global reset semantics lack canonical multi-user authorization. |
| GET `/instructor/alerts` | Local analytics and alerts without canonical scoped persistence. |
| GET `/instructor/analytics` | Local cohort data and shared-key semantics. |
| POST `/instructor/alerts/{alert_id}/resolve` | Alert mutation lacks canonical owned record/role enforcement. |
| POST `/instructor/mastery/{student_id}/{source_id}/{concept_id}/reset` | Caller path identity controls local progression state. |
| POST `/video/generate` | Caller student/source identity; local target and job state. |
| GET `/video/status/{job_id}` | Global memory/disk job lookup lacks owner check. |
| GET `/video/{job_id}` | Unowned artifact lookup. |
| GET `/video/{job_id}/stream` | Unowned artifact/file streaming. |
| GET `/video/{job_id}/metadata` | Unowned metadata lookup. |
| GET `/video/{job_id}/captions` | Unowned generated captions. |
| GET `/video/{job_id}/subtitles` | Unowned generated subtitles. |
| GET `/video/health/check` | Engine metadata, not private learner data; included in router compatibility boundary. |
| POST `/qa/answer` | Request `user_id`, vector owner defaults, optional version and payload-only evidence trust. |
| GET `/qa/traces/{user_id}/{source_id}` | Caller identity selects disk traces. |
| GET `/api/learning/{source_id}/state` | Query `user_id` defaults to `student_default`; local graph and memory state. |
| GET `/api/learning/{source_id}/roadmap` | Same identity/default problem; local prerequisite graph. |
| GET `/api/learning/{source_id}/next-action` | Caller-selected progression state. |
| POST `/api/learning/{source_id}/assessment/submit` | Caller identity can select learning mutation context. |
| POST `/api/learning/{source_id}/reassessment/generate` | Unverified context can reach retrieval/model generation. |
| POST `/api/learning/{source_id}/remediation` | Unverified context can create learning/generation work. |
| GET `/api/learning/{source_id}/remediation/{job_id}` | Memory job ownership compares caller labels, not verified UUID. |
| GET `/debug/qdrant` | With debug enabled, direct unscoped search exposed source IDs and text previews. |
| POST `/api/models/switch` | Unauthenticated global generation-model/fallback mutation affects all users; no per-user role model exists. |

These are endpoint risks, not claims that every handler could successfully read canonical data before this patch. Some source consumers already failed incidentally because the local source registry is disabled in Supabase mode. Incidental errors and unavailable local records are not an authorization contract.

### Supported boundaries retained

| Existing endpoint | Verified disposition |
|---|---|
| `/api/auth/signup`, `/login`, `/refresh`, `/me`, `/logout` under `/api/auth` | Public registration/login/session flow unchanged; existing verified identity/profile provisioning retained. |
| GET `/sources` | Caller-scoped canonical repository; no legacy list fallback in Supabase mode. |
| GET `/sources/{source_id}` | Caller-token owner-scoped lookup, generic 404 for foreign records. |
| GET `/sources/{source_id}/versions/{version}` | Strengthened with strict canonical scope and token/owner binding. |
| GET `/sources/{source_id}/content-units` | Existing owner-scoped content reads retained. Optional version here is a source browsing contract, not permission for unpinned learning retrieval. |
| POST `/sources/{source_id}/retry-index` | Existing owned durable index retry retained. |
| POST `/upload` | Existing authenticated source ingestion retained, no automatic assessment. |
| POST `/pipeline/upload-and-assess` | Existing Supabase source-only branch retained; supplied student labels never own source jobs. |
| POST `/pipeline/assess-existing` | Already verifies source context and rejects unsupported Supabase assessment with 409. |
| GET `/pipeline/jobs/{job_id}` and `/events` | Existing authenticated owner metadata checks retained. |
| POST `/pipeline/jobs/{job_id}/retry` and `/cancel` | Existing owner checks retained; no legacy job fallback in Supabase mode. |
| GET `/openapi.json`, `/health` | Public operational contracts remain available. |
| GET `/api/models` and `/api/models/` | Status remains available; global model mutation is guarded separately. |

## Fixes implemented

1. `legacy_learning_boundary` explicitly selects file/local compatibility or Supabase verification. Unknown providers fail with safe 503. In Supabase mode it reuses the existing runtime's `verify_user`, records the verified user in request state, rejects mismatched path identities, then denies unsupported consumers before storage/model/job handlers. It never provisions a profile merely to reject a legacy call.
2. The registered assessment, QA, video, learning and instructor routers use this dependency. Debug retrieval and model switching use it explicitly. No second identity provider, service-role read, default owner or administrative confirmation was introduced.
3. `require_local_learning_storage` guards factories and direct legacy assessment/profile/matrix, QA trace, video artifact/job, adaptive-learning and Supabase-named file adapters. Direct instantiation cannot silently substitute a file adapter in Supabase mode. Cached local adaptive services also reject use after a provider change. Removed unnecessary privileged-key selection from the legacy adapters.
4. All four legacy vector retrieval entry points reject Supabase/unknown providers **outside broad exception handlers and before Qdrant or embedding access**. Consequently they cannot broaden to `student_default`, omit owner/version, return unverified payloads or turn a provider outage into successful empty Supabase evidence. Direct `assessment.generator.search_concept_chunks` is guarded before both supplied-evidence and direct vector paths.
5. `SourceScope` is immutable, strict and extra-field rejecting: server UUID, validated source ID and positive PostgreSQL integer version. `vector_version` and `relational_version` are the explicit tested `2 <-> v2` mapping. They reject booleans, floats, numeric strings in the relational contract, noncanonical labels, latest aliases and overflow beyond PostgreSQL integer range.
6. `require_source_scope` re-verifies the existing repository token, checks owner binding, looks up owned canonical source and the **specified** version, then validates returned owner/source/integer/display fields. It never falls back to latest. The existing pinned version endpoint now uses it; the Phase 5B repository implementation and ID/version lineage were not rewritten.

Caller body/query identities cannot authorize any disabled handler because execution stops at the verified boundary. Existing identity-bearing paths receive 404 on mismatch. File/local identity labels remain development compatibility semantics; they are not a production multi-user authentication system.

## Compatibility and deferred work

Supabase learning, QA, assessment, videos, instructor analytics, traces, debug evidence and global model switching are intentionally unavailable rather than insecurely functional. This is an explicit compatibility restriction permitted by Phase 6A.1. Unknown sources, foreign sessions or forged artifact IDs do not cause local resource inspection.

File/local workflows retain their existing algorithms and response contracts. Existing scoring, generation architecture, source ingestion, schema, migrations, Auth/RLS settings, object storage, notes and agents were not redesigned. No centralized RetrievalService was introduced. Genuine Qdrant indexing/upserts remain supported for Phase 5B.

Re-enablement requires canonical owner/version repositories and artifact/session bindings; QA/retrieval additionally requires Phase 6C canonical evidence hydration. Existing local graphs and in-memory learning state cannot be promoted to canonical by removing a guard. Instructor operations and global model switching need an explicit verified role/capability design before production enablement. Direct SQL/RLS policies were not changed or exhaustively re-audited in this implementation phase.

The existing duplicate dashboard OpenAPI operation-ID warning, unregistered `e2e` mark and `audioop` deprecation remain. Collection and explicit schema regeneration can emit the duplicate-ID warning twice; they are three existing warning categories, not new authorization failures.

## Verification

### Automated evidence

New `tests/test_phase6a1_security.py` covers every one of the 33 guarded method/path pairs with anonymous and transport-verified contexts. It uses real authentication dependencies and `SupabaseRuntime.verify_user`; only GoTrue/Data API transport is doubled. It does not override authorization with a fabricated accepted user. The transport checks caller JWT/public key and rejects another subject's token.

Additional negative tests cover forged path identities, foreign and incorrect pinned versions, forged repository owner objects, strict mapper variants, unsafe direct retrieval, supplied assessment evidence, missing context, cached local services, seeded foreign session/video files, auth failures, canonical database outages with a local snapshot present, file/local compatibility and public OpenAPI/health. The earlier endpoint discovery was corrected to use actual registered OpenAPI routes, because this FastAPI version lazily includes routers.

Commands:

- `.venv\Scripts\python.exe -m pytest -q tests/test_phase6a1_security.py tests/test_supabase_runtime.py tests/test_signup_registration.py tests/test_source_supabase.py tests/test_supabase_repository.py tests/test_secure_rag_qa.py tests/test_runtime_frontend.py`: **204 passed**, two emissions of the existing OpenAPI warning.
- `node --test tests/test_frontend_auth.js`: **14 passed**.
- `.venv\Scripts\python.exe -m pytest -q`: **680 passed, 1 skipped, 4 warnings**, 54.55 seconds. The skip is the existing opt-in live E2E test; live acceptance above was run separately.
- `app.openapi()`, TestClient GET `/openapi.json`, GET `/health`: passed; live endpoints also returned 200.
- `git diff --check`: passed; only Git line-ending notices were emitted. Deployed migration files have no diff.

### Live evidence and restart

Used the two already existing dedicated identities and an existing owned source. No new accounts, uploads or canonical application records were created. Credentials and tokens remained in memory/ignored configuration and are absent from this report.

| Live check | Result |
|---|---|
| Existing and dedicated new-account login | Both 200 |
| Owner canonical source and exact version read | Both 200 |
| Other user's exact-version request | 404 |
| Anonymous learning request | 401 |
| Authenticated unsupported learning and foreign video request | 409 |
| Debug retrieval with valid user | 409 |
| Direct Data API GET for the owned source using public key + owner JWT | 200, one visible row |
| Same direct Data API query with the other identity's JWT | 200, empty rows |
| Live OpenAPI and health | Both 200 |

Repeated these checks after an actual verified VisualAI process restart while preserving its runtime configuration; the same results passed. This proves the tested source RLS boundary live, not every deployed policy. Unsupported legacy sessions/artifacts are denied at the application boundary; their canonical RLS and eventual successful owner-access workflows are **not** claimed implemented or tested live.

Phase 5A signup/confirmation/refresh cases and Phase 5B ingestion/commit/index-retry cases passed automated regressions. A new live signup/upload was not attempted in this phase. Live existing-login/source reads and restart isolation passed.

## Final delivery boundary

The original unsafe HTTP paths now stop before their handlers, and the reviewed direct assessment/vector/local-storage paths reject Supabase use. Legitimate local algorithms and supported Auth/source contracts passed regressions. Proceed to Phase 6A.2 knowledge implementation with these guards intact; production learning feature enablement remains a later gated task.

No commit or push was performed. The prior architecture document remains unrelated untracked work and was not overwritten.

### Files changed in this phase

- `app/main.py` — registered router/debug boundary.
- `app/api/models.py` — global model-switch boundary.
- `app/api/sources.py` — canonical pinned-version validation.
- `app/db/vector_store.py` — unsupported retrieval preflight.
- `app/services/security/legacy_boundary.py` — shared identity and compatibility guard.
- `app/services/security/source_scope.py` — strict canonical scope and version mapper.
- `app/services/repositories/factory.py` — no Supabase file fallback.
- `app/services/repositories/supabase_repository.py` — guarded legacy adapters, removed privileged-key selection.
- `app/services/assessment/generator.py` — direct retrieval preflight.
- `app/services/assessment/profile.py` — local profile access guard.
- `app/services/assessment/session_store.py` — local session access guard.
- `app/services/assessment/video_target.py` — local matrix access guard.
- `app/services/mastery/application_service.py` — constructor and cached-service guards.
- `app/services/qa/grounded_answer.py` — QA/trace service guards.
- `app/services/video/artifact_store.py` — artifact storage guard.
- `app/services/video/engine.py` — job lookup/persistence/generation guards.
- `tests/test_phase6a1_security.py` — 95 new security/scope cases.
- `docs/phase6a1_security_closure.md` — this report.
