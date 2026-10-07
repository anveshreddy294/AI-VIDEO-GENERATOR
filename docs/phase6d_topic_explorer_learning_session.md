# Phase 6D: Topic Explorer and focused learning sessions

## Deployment boundary

Implementation is ready for review. **The new migration has not been applied remotely.**
Supabase project `hqszkkvuxwdedhegqbec` has no `public.learning_sessions` table.
Its four existing migrations are unchanged. Session APIs fail explicitly with
503 `SESSION_STORAGE_UNAVAILABLE`; there is no file or memory fallback.

Review and explicitly approve only `migrations/20261007110254_focused_learning_sessions.sql`.
SHA256: `8eb9da73416c8c838e66c388ca4aabf55d70c235f9d08873b97b6556d5075267`.
After approval, apply this single migration through Supabase MCP, refresh the
Data API schema cache if needed, verify grants and history, then perform the
pending two-identity live session acceptance. Do not bulk-push migration history.
The previously deployed canonical snapshot migration is unchanged (local SHA256
`15f6871070288d1d0fc180cd7aa433a58985f88d60a4f2330810ed125f6b2e21`).

## Product flow and frontend

Login -> My Sources -> Topic Explorer -> select topic/subtopic -> focused session.
Supabase-mode `/dashboard` and `/learn` serve a lightweight static learner UI,
using the existing verified Auth helper for every private API request. File-mode
dashboard behavior is retained. Sources upload uses the existing source-only
pipeline and never starts assessment automatically.

The existing exact-version knowledge endpoint supplies canonical ordered topic,
subtopic, concept, prerequisite and evidence metadata. No inference generates UI
topics. READY displays the hierarchy; PENDING shows processing; LEGACY_UNMAPPED
explains mapping absence; FAILED exposes a safe explicit retry. Empty/loading/error
states, keyboard controls, labels, responsive layout and text-only DOM rendering
are included. Internal IDs are not displayed as learner content.

Session ASK uses canonical QA. LEARN displays canonical definitions, prerequisites
and citation locations without another model call. Notes, Practice and Visualize
are disabled with truthful future labels. Frontend calls only VisualAI APIs;
no provider secrets, service-role keys or browser Worker inference endpoints.

## Durable contract and security

`learning_sessions` stores UUID session/verified owner, exact source/version,
topic, optional subtopic, resolved concept IDs, state, created/updated/last-active
timestamps. Composite FKs bind topic/subtopic to the same owner/source/version.
The bounded concept array contains 1..64 IDs. Session listing is capped at 50
newest active timestamps; pagination is a future extension.

RLS permits authenticated owner SELECT only. Direct mutations are revoked.
`visualai_mutate_learning_session` invokes a private bounded SECURITY DEFINER
function with empty search_path, restricted execution and `auth.uid()` ownership.
It independently checks READY source/version, topic/subtopic parentage and exact
canonical concept membership. Advisory transaction locking makes UUID retries
idempotent; owner-filtered row locking serializes transitions. No admin identity
establishes browser ownership. Anonymous API requests return 401; unavailable
foreign sessions return the same 404 as nonexistent sessions after deployment.

`LearningSessionRepository` uses authenticated Data API/RPC only.
`LearningSessionService` validates selection through KnowledgeService, without
direct Qdrant access. Create starts ACTIVE. Explicit selection changes may change
topic/subtopic only within the pinned source/version. Resume requires ACTIVE;
complete/abandon are terminal, with matching terminal retries idempotent.
Terminal sessions cannot silently reactivate. Source updates never retarget a
session; UI can indicate a newer version while retaining the original scope.

## QA scope

Canonical `/qa` optionally accepts `session_id`, question and a concept subset.
The server loads the owned ACTIVE row and resolves source/version/topic/subtopic/
concepts. Contradictory explicit selectors are rejected before generation;
concept selectors may only narrow the stored scope. RetrievalService retains
canonical validation, mandatory vector filters and evidence/answer validation.
Qdrant remains the semantic index; Supabase remains domain authority.

## Verification and acceptance

Disposable PostgreSQL 17 migration tests exercise real FKs, RLS, grants, role
separation, cross-user rejection, concept membership, retries, pinned versions
and state transitions: 15 passed. Six API/service tests use authenticated
transport doubles with real disposable PostgreSQL, including session QA and
selector broadening. These are not claimed as remote live session proof.
Existing targeted runtime/retrieval/security tests: 133 passed.
Frontend Auth/learning tests: 20 passed. Strict JavaScript TypeScript checking
and syntax checks passed. Full Python suite: 936 passed, 1 optional real E2E
skipped, 4 existing warnings (duplicate dashboard operation ID, unregistered
E2E marker and audioop deprecation). Formatting and diff whitespace checked.

Both dedicated identities authenticated through real Supabase Auth. Owner
source list returned 200 in 2.552 s; accepted version-one knowledge returned
200 in 2.351 s with 2 topics, 2 subtopics and 4 concepts. Foreign knowledge
returned 404; anonymous sessions returned 401; owner sessions returned truthful
503 pending deployment. No accepted snapshot was rewritten or indexed.
After one verified VisualAI process restart, both identities authenticated again:
source list 200 in 2.155 s, knowledge map 200 in 1.943 s (same 2/2/4 hierarchy),
foreign knowledge 404, anonymous sessions 401, pending session storage 503.
The in-app browser also verified an unauthenticated dashboard redirects to login.

Pending after explicit deployment approval: create Biology/Cell Biology session,
verify Cell Membranes/Osmosis resolution, grounded osmosis answer and Algebra
scope refusal; second-user read/resume/selection/QA equal-missing rejection;
restart and reload the same persisted UUID/scope without duplication. Session
create/load and session QA timings cannot be measured before deployment.
Phase 6C previously recorded warm QA 9.052 s and post-restart cold QA 14.505 s;
these are historical foundation measurements, not new session measurements.

## Remaining risks

Remote session deployment and live acceptance are intentionally pending. Local
tests verify durable rows survive repository/client recreation, but remote
process-restart acceptance remains outstanding. New learner layout has automated
contract/accessibility assertions; authenticated visual demo review remains
recommended. Notes, assessment, video, mastery, roadmap and infrastructure
migrations were not implemented. No commit or push was performed.

## Changed files

- `app/api/dashboard.py`, `app/api/qa.py`, `app/main.py`: learner shell routing,
  session-scoped QA and source version metadata.
- `app/api/learner.py`, `app/api/learning_sessions.py`: static learner assets
  and verified owner session API.
- `app/services/learning_session.py`: typed contracts, repository and service.
- `app/static/learning.html`, `app/static/learning.css`, `app/static/learning.js`:
  Sources, Topic Explorer, focused session and Learn/Ask views.
- `migrations/20261007110254_focused_learning_sessions.sql`: additive pending migration.
- `tests/test_learning_session_database.py`, `tests/test_learning_session_service.py`,
  `tests/test_learning_frontend.js`, `tests/test_runtime_frontend.py`: validation.
- `docs/phase6d_topic_explorer_learning_session.md`: this deployment/acceptance record.
