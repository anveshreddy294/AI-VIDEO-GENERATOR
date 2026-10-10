# Personalized learning profile

Implementation branch: `fixpers`, created from fetched `origin/fixextra` at `25d2fa5`. The user authorized committing and publishing these updates on `fixpers`.

## Account flow and storage

The authenticated dashboard checks `/api/learning-profile` before loading learning resources. Incomplete accounts go to `/profile`; completed accounts proceed normally. A failed profile check displays a retry action rather than bypassing setup. The Learning profile navigation link allows editing later. Profile setup itself uses the existing authenticated fetch, refresh and sign-out behavior.

Required fields are education level and at least one valid interested domain. The form supports multiple domains, an optional display name, an optional learning goal, and a bounded custom entry when Other is selected. English is the application's currently supported learning language. A checkbox disables interest-based examples for future generations. No age, gender, address or other sensitive personal fields are collected.

`public.profiles.learning_preferences` is an additive JSONB column with `{}` as the incomplete-account default. The existing `full_name` column is reused; name is not duplicated in the preferences object. Completion is derived from validated preferences, rather than a client-supplied complete flag. Database constraints reject incomplete nonempty preference objects and empty interest selections. Application validation also rejects duplicate/unknown domains, unsupported languages, invalid custom entries and client owner/role fields.

Migration `20261010190948_learning_preferences.sql` was applied to the connected Supabase project `hqszkkvuxwdedhegqbec`. The existing profiles owner SELECT/INSERT/UPDATE policies remain in place. Authenticated users received UPDATE permission only on the new preferences column; UPDATE(role) remains forbidden. Read/update requests use the verified user UUID, an explicit owner filter and the caller's token/public key. No service key or local file fallback is used for profile storage.

The Supabase CLI is not installed. The migration was tested against disposable local PostgreSQL 18, applied using the Supabase migration tool, and saved with the version returned by Supabase's migration history. No CLI or dependency was installed.

## APIs

| Endpoint | Purpose |
| --- | --- |
| `GET /api/learning-profile` | Read the authenticated account's profile and derived completion state. |
| `PUT /api/learning-profile` | Validate and save only that account's preferences and optional existing display-name field. |
| `GET /api/learning-profile/options` | Public, nonsensitive domain/language options. |
| `GET /profile` | Static setup/edit shell; private data loads through authenticated APIs. |

Private profile responses are no-store. Existing login and `/api/auth/me` contracts are unchanged. Profile storage failure blocks the onboarding UI with a retry; presentation-preference lookup failure inside an established generation service falls back to conventional teaching without changing source authorization.

## Relevance and resource integration

`interest_personalization.py` builds a structured presentation context containing selected interests, learner level, language, learning goal, relevant connections, examples, visual scenarios, appropriateness and an explanation of the decision. A deterministic topic/subject rule set handles supported connections, such as Sports with Newtonian mechanics, Dance with symmetry/patterns, Gaming with algorithms and Music with frequency. Incidental hobby mentions in source text do not themselves trigger a match. At most two supported themes are suggested. Unknown or unrelated topics receive conventional examples; custom interests are accepted as preferences but do not invent new relevance rules.

The context is kept separate from source observations, retrieval scope, source claims and answer keys. It contains no user UUID, display name, authentication claims or secrets. Shared presentation instructions require unchanged definitions, equations, assumptions, citations, concept relationships and grading requirements; analogies are illustrative rather than attributed to sources. These instructions guide a probabilistic model and do not constitute a formal factual-correctness proof.

| Existing resource | Integration |
| --- | --- |
| Educational explanations | Shared presentation context is appended to the existing teaching request. Uploaded entry uses the owned filename as a conservative topic hint until a generated lesson topic exists. |
| Notes | Existing notes request gets current preferences. Saved notes remain unchanged on page load. Explicit Generate Notes requests can regenerate using updated preferences. |
| Flowcharts / concept maps / relationship maps | The existing structured diagram request gets the same context. Existing validation and renderer remain; instructions limit themes to examples/supporting labels. Explicit diagram generation can regenerate; saved diagrams are restored unchanged. |
| Standalone educational assessments | Question generation gets presentation context with explicit no-hobby-knowledge and fixed-difficulty requirements. Private answer-key serialization and grading are unchanged; grading prompts receive no personalization context. |
| Educational videos | The existing validated video plan may receive one labeled illustrative scene after factual explanation/equation scenes. Existing completed/running videos remain cached. Renderer, TTS, playback authorization and model routing are unchanged. |
| Ask VisualAI | Educational lesson Ask uses current level/interests while keeping its existing citation/provenance behavior. Canonical RAG Ask personalizes only its permitted AI supplemental branch; verbatim evidence claims remain unchanged. |
| Focused-session notes | AI-enriched notes/examples use the shared service. Strict extractive notes stay extractive. Supplemental notes/Ask cache identities include current preferences so another request does not reuse a previous preference set. |
| Roadmaps | The existing deterministic roadmap engine accepts an optional validated profile and returns example themes separately from concept ordering, prerequisite gates and mastery evidence. No learning loop, reassessment flow or roadmap UI is enabled. Its legacy API is still subject to its existing provider boundary. |

## Files changed

- `app/services/learning_profile.py`: request/response validation, owned profile transport and request-local preference loading.
- `app/services/interest_personalization.py`: reusable relevance rules, context and reasoning-request adapter.
- `app/api/learning_profile.py`: profile read/update/options endpoints.
- `app/core/supabase.py`: PATCH support on the existing caller-scoped transport.
- `app/main.py`: profile router registration.
- `app/api/learner.py`, `app/static/learning-profile.html`, `learning-profile.js`: setup/edit page and assets.
- `app/static/learning.html`, `learning.js`, `learning.css`: dashboard gate, profile link/summary, explicit resource regeneration and responsive styling.
- `app/services/educational_content.py`, `app/api/educational_content.py`: existing lesson/resource integration and opt-in regeneration flags.
- `app/services/ai_explanation.py`, `grounded_notes.py`, `qa/canonical_answer.py`: supplemental presentation context and preference-aware cache identities.
- `app/services/mastery/personalization_service.py`, `roadmap_models.py`: separate optional roadmap example themes without ordering changes.
- `migrations/20261010190948_learning_preferences.sql`: additive column, shape constraint and column-limited grant.
- New tests: `test_interest_personalization.py`, `test_learning_profile_database.py`, `test_learning_profile_frontend.js`.
- Updated tests: owned transport fixtures, typed-topic preference-read expectations, dashboard onboarding behavior, roadmap ordering invariants, and an older database test that incorrectly expected optional indexing to run during upload. Authorization-boundary fixtures use a fixed clock so their tokens do not expire during a long full-suite run. Production authentication and ingestion implementations were not changed.

## Verification

- Full JavaScript/Worker/frontend suite: **197 passed, 0 failed**.
- Full Python suite: **1,658 passed, 1 skipped, 5 warnings** in 305.84 seconds. Tests use the existing disposable PostgreSQL fixture, not the connected Supabase database, for mutation/isolation scenarios.
- Focused authorization-boundary suite: **103 passed**, including the corrected deterministic token-clock fixtures.
- Focused final regression check: **23 passed**, including real PostgreSQL profile constraints/RLS, the corrected optional-index publication test, notes HTTP behavior and shared profile-resource integration.
- Live schema query confirmed JSONB/default `{}`, RLS enabled, three existing account policies, preferences UPDATE allowed and role UPDATE denied.
- Supabase security advisors found no new profile-table finding. The project has an existing warning that leaked-password protection is disabled; authentication settings were not changed. Reference: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection
- Browser: the signed-in incomplete account redirected to setup; Save was blocked with “Choose at least one interested domain.” Narrow and desktop layouts had no page overflow, and all 12 interest choices rendered. The real account profile was not modified because its education/interests were not supplied. A complete live logout/login and edited-profile save cycle therefore remains a manual check; persistence and owner isolation are covered by transport and actual PostgreSQL tests.
- Live configured Cloudflare model, using a synthetic account context and Sports preferences: Newton's Second Law lesson produced soccer/tennis/cricket examples; notes produced hockey/volleyball/shot-put examples. The existing video-plan validator accepted an added labeled Sports scene. Synthetic account context is not a test of production authentication; real profile authorization is verified separately.
- A second live Cloudflare check used Dance preferences: symmetry/transformations produced mirrored choreography, rotation and translation examples. DNA replication received conventional biological examples without Dance analogies, matching the relevance gate.
- Browser screenshot: ignored local artifact `storage/runtime/personalized-profile-browser.jpg`. Synthetic live model outputs are in ignored `profile-live-check.json` and `profile-live-relevance.json` under the same directory.

## Manual acceptance checks and limits

1. Sign in with an incomplete account, choose an education level and at least one domain, save, sign out, and sign in again. The dashboard should load directly; preferences should persist.
2. Edit interests through Learning profile. Existing saved lesson resources must remain unchanged. Generate a fresh topic, or explicitly regenerate notes/diagram, and compare the new examples.
3. Test Sports with Newton's Second Law, Dance with symmetry, and Dance with DNA replication. The first two may use relevant illustrations; the third should use conventional teaching.
4. Disable interest-based examples and generate a fresh resource. Confirm standard explanations and unchanged equations, citations and assessment grading.
5. Check another account cannot read/update your profile, source jobs, lesson resources or answer keys. Automated tests cover the profile SQL ownership and API identity boundary; a second live browser account was not used.

Relevance rules are deliberately conservative, English is the only exposed supported language, and custom-interest inference is not automatic. The existing fixed video renderer uses its existing example scene type rather than introducing a new animation engine. Model-based examples still need normal educational review. No new learning loop, reassignment/reassessment workflow, provider routing, timeout budgets, ingestion logic or dependency installation was introduced.
