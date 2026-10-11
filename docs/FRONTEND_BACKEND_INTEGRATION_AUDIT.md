# VisualAI React / FastAPI Integration Audit

## Audit snapshot

| Item | Result |
| --- | --- |
| Repository | `anveshreddy294/AI-VIDEO-GENERATOR` |
| Reference commit | `9b7446cf8efaa8d3e7cf64f76530e07c4a904286` |
| Audited current HEAD | `c0e7cae54b4b659e89e1c90b86aba93be2ec9b02` |
| Integration branch | `integration/knowledge-atelier-api` |
| Frontend | `newfront/` (React 19, Vite, React Router 7) |
| Backend entry point | `app.main:app`, `run.py`, port 8000 |
| Frontend development server | Vite port 5175 |
| Protected backend files changed | None |
| Pre-existing working-tree item | `newfront/package-lock.json` (untracked; preserved) |

The current branch was preserved before frontend edits. No reset, force push, merge, or production default-route change was performed.

## Current architecture

The React app previously rendered a Knowledge Atelier shell around local constants in `src/services/atelierData.js`. Authentication selected a locally invented identity and role. The context created source records on file selection, scored assessment answers in the browser, appended template answers to ASK, and reported successful video generation/download with timers.

The backend remains the compatibility baseline. It owns Supabase identity and role, source ownership, extraction and readiness, lesson persistence, educational-content validation, assessment answer keys and grading, Qdrant/source provenance, and video generation/authorization.

## Implemented target architecture

```text
Browser :5175
  React routes + Knowledge Atelier presentation
  WorkspaceContext: UI identifiers and server-synchronized records only
  services/api/client.js: relative requests, bearer, refresh, timeout, errors
       │ Vite proxy (development only)
       ▼
FastAPI :8000
  /api/auth       Supabase session authority
  /sources        owner-scoped source registry
  /pipeline       authenticated ingestion jobs
  /educational-content  lessons, notes, diagrams, assessment, ASK, video
```

The development servers remain separate. The Vite proxy forwards API prefixes to `http://127.0.0.1:8000`; `/` is never proxied.

## Files changed

- `newfront/src/services/api/` — centralized client, auth, source, lesson, video services, adapters and error taxonomy.
- `newfront/src/context/WorkspaceContext.jsx` — real session restoration, identity, source/lesson synchronization, upload polling and UI identifiers.
- `newfront/src/App.jsx` — protected workspace routes and backend-role educator guard.
- `newfront/src/components/layout/AppLayout.jsx` — removed client role switching.
- `newfront/src/pages/public/SignInPage.jsx` — real signup/login and backend-authoritative role navigation.
- `newfront/src/pages/app/TopicExplorerPage.jsx` — topic/source lesson creation and real lesson resume.
- `newfront/src/pages/app/LearningStudioPage.jsx` — returned explanation, concepts, examples, notes, diagrams and ASK.
- `newfront/src/pages/app/LibraryPage.jsx`, `DashboardPage.jsx` — real source registry/upload jobs and neutral unsupported metrics.
- `newfront/src/pages/app/AssessmentPage.jsx` — public assessment contract and backend submission/grading.
- `newfront/src/pages/app/VideoStudioPage.jsx` — real job polling and authenticated Blob playback/download.
- `newfront/src/pages/app/ProgressPage.jsx`, `ProfilePage.jsx`, `EducatorHubPage.jsx` — supported data only and honest unavailable states.
- `newfront/vite.config.js` — development proxy.
- `newfront/src/services/atelierData.js` — removed from the operational application because no page imports it.
- `docs/` — contract, regression and live acceptance evidence.

## Mock behavior removed from operational student flows

- hardcoded Elena/Sophia/Prof. Vance sign-in and user-selected authorization role;
- fabricated source IDs, page counts, concepts, optical confidence and READY transitions;
- local topic explanations and fabricated source citations;
- browser-side answer keys, scores and mastery mutation;
- template ASK answers and local citation strings;
- timer-based video completion, replay success and download success;
- fabricated dashboard mastery, progress and educator cohort analytics.

Marketing and explicitly labeled public demo pages retain presentation content. They are not used as authenticated workspace state.

## Authentication design

`sessionStorage[visualai.auth.session]` follows the existing HTML learner contract. The client stores the backend session response, refreshes through `/api/auth/refresh` near expiry, deduplicates concurrent refreshes, retries the failed authenticated request once after a 401, then clears the session. `/api/auth/me` restores identity after reload. The browser never chooses an educator role and never sends a server-side Supabase key.

The remaining tradeoff is the backend’s existing browser bearer-token/session-storage contract. This integration does not introduce cookies or a second auth system.

## First-gate behavior

1. `/signin` performs real `/api/auth/login` or `/api/auth/signup`.
2. `/app/explore` accepts a topic such as `Binary Search Trees`.
3. `POST /educational-content` sends the exact topic-only contract.
4. The response’s `content_id` is retained as the lesson ID.
5. `/app/studio?lesson=<content_id>` renders the returned explanation.
6. Reloading the route restores the ID from session storage and fetches `GET /educational-content/{lesson_id}`.

This path is implemented but not marked live-verified until a real Supabase account and running provider-backed FastAPI instance complete it. See the acceptance guide.

## Backend protection and rollback

No `app/` file was changed. Rollback of this frontend branch is a branch switch to `success` (or the pre-integration commit); the backend routes, `/learn`, `/dashboard`, root landing page, API docs and health checks remain untouched. The new React frontend was not made the production default.
