# Frontend / Backend Regression Report

## Baseline before integration

Recorded on the current HEAD before frontend edits. No external provider, Supabase, Qdrant, Cloudflare, OpenRouter or Ollama call was made.

### Backend

- Offline collection excluding the opt-in live HTTP E2E and PostgreSQL fixture: `1583 tests collected`.
- Full protected offline run under network-deny/repository-write-deny sandbox: `1505 passed, 63 skipped, 15 failed, 8 warnings`.
- The 15 failures attempted direct writes below the intentionally denied repository paths (`storage/runtime` or `storage/videos`). They were isolated, not silently skipped, and are retained as known environment failures.
- Functional offline run with those 15 write-boundary cases explicitly deselected: `1505 passed, 138 skipped, 15 deselected, 8 warnings`.
- Targeted auth and educational contract suites: `197 passed, 7 warnings`.
- PostgreSQL suite: `75 skipped` because `VISUALAI_KNOWLEDGE_TEST_PG_BIN` and PostgreSQL tools are unavailable.

### Frontend

- Baseline Vite build: passed (`vite build`, 69 modules transformed).
- Frontend had no test script and no browser E2E suite in `newfront/package.json`.
- Existing untracked `newfront/package-lock.json` was preserved.

## After integration checks

- `npm run build` from `newfront/`: passed (`vite build`, 75 modules transformed).
- `git diff --check`: passed.
- No backend path under `app/` was modified.
- No production same-origin serving change was made.
- No live calls were performed; therefore no live success is claimed.

## Scope of offline verification

The build verifies module resolution, JSX compilation, route composition, and the API integration layer’s production bundle. Static review verified:

- requests are centralized under `newfront/src/services/api/`;
- FormData requests do not set `Content-Type` manually;
- unsafe POST operations have no general automatic retry;
- 401 refresh is single-flight and bounded to one request retry;
- browser role controls do not grant instructor access;
- assessment public rendering reads no answer key before server submission;
- video completion/download notifications require a completed backend status and a fetched MP4 Blob;
- unsupported aggregate/educator data is rendered as unavailable.

## Not yet verified

- Real Supabase signup, login, refresh, logout and cross-user denial.
- A live topic generation request with a provider-backed FastAPI server.
- Real source uploads and provider/Qdrant readiness transitions.
- Real notes, diagram, assessment, ASK and video rendering.
- Safari browser execution and authenticated Blob playback.

These are intentionally not represented as passed. Run the gated procedure in `FRONTEND_LIVE_ACCEPTANCE_GUIDE.md` only with explicit live-environment approval.

## Known pre-existing backend environment failures

The repository-write-deny baseline failures are video/pipeline tests that write into protected repository storage. They are not frontend regressions. The database suite requires a configured disposable PostgreSQL installation. Existing warnings include AnyIO/Starlette deprecations, SWIG deprecations and a duplicate FastAPI dashboard operation ID.

## Rollback

Frontend-only rollback is a branch switch to `success` or the pre-integration commit. Do not revert backend files because none were changed for this integration.
