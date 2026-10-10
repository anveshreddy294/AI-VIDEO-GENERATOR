# Critical repair on fixext

Implementation and evidence from 2026-10-10. These changes are local and uncommitted. No new dependency, model, endpoint, database migration, learning loop, reassignment or remediation journey was introduced. This report updates the earlier live-provider conclusions in `cloudflare-reliability.md`.

## Confirmed causes

1. **Teaching contract mismatch.** `POST /educational-content` validates generated content through `Teaching`, then adds server-owned identities and provenance. `explanation` was a string, but the normalizer did not handle structured explanations. `mathematical_notation` and `common_misconceptions` were absent from the schema. Legitimate supplemental content therefore produced `string_type` and `extra_forbidden` failures.
2. **Schema was not necessarily visible to the deployed text model.** The recovered Worker forwards JSON-schema mode only for designated structured tasks. Lesson generation uses `reasoning`. The backend system message asked for schema compliance but did not contain the schema itself. Before the compatibility fix, the live reasoning task generated string relationships, which failed the required `{subject, relation, object}` contract. Including the exact schema in model-visible system instructions made the real strict lesson check pass. The backend still sends the structured schema field for current Workers and validates all output locally.
3. **The reported upload did complete.** A read-only query of the existing SQLite job database found `JOB_3ac1e77e8aa6` completed, `content_ready`, progress 100, `is_finished=1`. Created 16:04:20 UTC; completed 16:05:11 UTC: approximately 52 seconds. The supplied polling log alone was insufficient to establish a permanently stuck worker.
4. **Completion display depended on another fallible request.** The current learner waited for `loadSources()` before publishing final upload feedback. A delayed/failed source-list refresh could obscure a successful extraction. Completion feedback now appears first; refresh failure explicitly says the material was saved.
5. **Read-side overhead.** Listing sources downloaded every document's complete ContentUnits to compute a boolean. Non-READY sources now use one selected identity with `limit=1`; READY sources skip that lookup. Owner and exact-version filters remain mandatory.
6. **Incorrect concurrency admission.** `JobManager.get_semaphore()` read Ollama concurrency even when the configured background-job limit was larger. It now uses `max_background_jobs`; local fallback retains its separate local admission gate.
7. **Polling could execute work.** GET job status could call `index_committed_source()` to reconcile a failed source. That could run model/index/persistence operations during polling. GET now only returns the authorized job snapshot. Recovery remains in the worker and explicit retry endpoints.
8. **No queue deadline or waiting heartbeat.** Source-job admission could wait indefinitely for the semaphore. Admission is now bounded by the existing job budget and queue time reduces the processing budget. Waiting workers emit stage-preserving heartbeats without advancing fake progress or restarting work.
9. **Unusable output policy.** Previously, a schema-invalid visual proposal stopped the route even with a supported fallback enabled. It is now discarded before one validated local attempt. Independent verification remains required before publication. Educational generation similarly validates the cloud proposal before declaring success or attempting supported local fallback.
10. **Secondary bounded-output failure.** A deterministic assessment fallback copied an explanation of up to 12,000 characters into a sample-answer field capped at 2,000. It now respects that field's limit. Validation exception logs for notes/diagram/assessment no longer serialize generated content.

The historical dashboard implementation also had a hard-coded ten-minute polling window and required indexed `READY` even for terminal `CONTENT_READY` results. Both were aligned with the current contract. In Supabase mode `/dashboard` already serves the shared learner page; the legacy dashboard defect is not evidence that it caused this particular user's run.

## Contract changes

Strict `extra="forbid"` remains enabled. Server-owned source IDs, user IDs, citations, provenance and readiness cannot be supplied by the model.

Canonical model output:

```json
{
  "topic": "Newton's second law",
  "explanation": "Net force equals mass times acceleration.",
  "key_concepts": [{"name": "Acceleration", "explanation": "Change of velocity over time."}],
  "examples": ["A 2 kg object accelerated at 3 m/s² needs a 6 N net force."],
  "equations": ["F = ma"],
  "relationships": [{"subject": "Net force", "relation": "produces", "object": "Acceleration"}],
  "mathematical_notation": [{"symbol": "m", "meaning": "Mass in kilograms"}],
  "common_misconceptions": [{"misconception": "Net force maintains constant velocity", "correction": "Net force changes velocity"}]
}
```

The two new optional fields accept bounded arrays of nonempty strings or the explicitly defined objects shown above. The normalizer also accepts a singleton string/object for those fields, preserving it in an array. Incorrect object keys and primitive types are rejected.

The API and frontend continue receiving `explanation` as a nonempty string. Compatibility normalization accepts a list of text paragraphs, or a strict object with `overview`, `text`, `details`, `sections` and `summary`. Sections contain optional `title` and required `content`; content can be text or a bounded text list. Known paragraphs are joined with blank lines. Unknown nested fields, numbers, empty explanations and arbitrary objects fail validation.

Examples/equations no longer stringify arbitrary dictionaries or numbers; only existing single-key text wrappers are unwrapped. Invalid key-concept entries are retained for rejection instead of silently dropped. Required `explanation` remains mandatory. The known input topic can still supply the model's missing topic, as before.

Notation and misconceptions survive lesson persistence, enter downstream teaching requests, and render with text nodes in the existing lesson workspace. No model text is inserted as HTML. Malformed output produces a safe retryable error; no invalid lesson is saved.

## Routes and complete existing workflow

Direct topic: `/dashboard` topic form → `POST /educational-content` → validated AI-enriched teaching → durable owned lesson → existing notes, diagram, assessment, video and Ask routes.

Upload: `POST /pipeline/upload-and-assess` → validated file → owned source job → background semaphore → native text/compatible vision extraction → independent evidence verification → normalization/sanitization → immutable source commit → terminal `content_ready` result → source cards → **Learn with VisualAI** → `POST /educational-content` with exact source/version → the same owned lesson workspace.

Default upload intentionally exposes reusable extraction without requiring hierarchy/indexing to succeed. It does not falsely change the database `INDEXING` checkpoint into indexed `READY`. The UI displays `CONTENT_READY` where extracted content is available. Existing optional enrichment/index retry paths remain separate. Indexed sources retain their topic explorer and canonical RAG/session routes. Generated lesson concepts remain AI-enriched teaching, rather than new canonical source claims.

Owned lesson routes are unchanged: `/{id}/notes`, `/diagram`, `/assessment`, `/assessment/submit`, `/ask`, `/video`, `/video/status`, and authenticated `/video/stream` under `/educational-content`.

## Provider routing, timeouts and trust

| Work | Primary | Supported fallback / handling |
|---|---|---|
| Explanations, lesson notes/flowcharts/grading/Ask and legacy text adapters | Configured Cloudflare Worker `/v1/generate`; general Qwen `@cf/qwen/qwen3-30b-a3b-fp8` | Configured Ollama text model; educational output validated identically |
| Content understanding, structure repair, assessment structured generation | Same Worker; Llama `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Configured text fallback, existing validation/repair boundaries |
| Image/PDF/video-frame visual extraction | General Gemma 4, deep Qwen 3.8, native multimodal image input | Enabled local vision fallback, normally `gemma3:4b` |
| Independent visual review | Different qualified Cloudflare model; cloud reviewer for local extraction | Uncertain if no independent evidence; no self-verification |
| Embeddings, transcription, narration, rendering | Existing local embedding model, faster-whisper, configured TTS, Manim/FFmpeg | Retained; the configured Worker has no compatible embedding/ASR/TTS route |

The endpoint is the configured `polished-snowflake-ecb1.speedrun3ai.workers.dev`, not an assumed third-party generation service. Live responses identified the expected Cloudflare models. Backend secrets remain backend-only. No unrelated provider was introduced.

Request budgets remain 180 seconds; combined cloud text/vision attempts share 300 seconds; full image extraction/fallback/review has 600 seconds; whole extraction 1,800 seconds; job 2,400 seconds; browser observation 3,600 seconds. Connection/write limits remain 10/30 seconds. Cloud and job concurrency default to three; local admission remains one. These are configurable starting values. Parent deadlines are not reset by retries or heartbeats. In-flight synchronous parsing/ASR/storage calls remain cooperatively bounded at safe boundaries; a Python thread cannot safely be killed while committing.

At most two cloud transports and one local proposal occur within a model route. Unusable lesson output may go directly to a supported validated local fallback; transport correlation and secret checks remain strict. Authentication/configuration/request rejection do not become successful content. Unknown/unsafe output never becomes evidence. Worker native missing-model codes 5007 and 3042 now classify as sanitized 503 model-unavailable responses, enabling the existing bounded operational fallback policy after deployment. These codes are documented in [Cloudflare's error reference](https://developers.cloudflare.com/workers-ai/platform/errors/).

## Files changed

| Files | Responsibility |
|---|---|
| `app/services/educational_content.py` | Typed supplemental fields, narrow normalization, model-visible instructions, validation before fallback, downstream context, safe diagnostics, assessment length bound |
| `app/core/reasoning.py` | Exact schema in system instructions, validated provider-routing entry point |
| `app/api/educational_content.py` | Safe actionable invalid-lesson response |
| `app/api/pipeline.py` | Read-only job polling |
| `app/api/source_jobs.py`, `app/core/inference_budget.py` | Queue budget, worker heartbeat, job correlation, terminal output counts |
| `app/services/pipeline_tracker.py` | Correct configured background concurrency |
| `app/services/repositories/source_repository.py`, `app/main.py` | Bounded owned content-availability queries |
| `app/services/visual_router.py`, `app/services/vision.py` | Validated fallback for unusable vision output and fixed failure taxonomy |
| `app/static/learning.js` | Supplemental-field rendering, truthful content badges, recent upload selection, completion before refresh, safe error feedback, valid Ask guidance, scope-checked source citation rendering |
| `app/api/dashboard.py` | Legacy polling compatibility with configured budgets and content readiness |
| Worker `src/visual.js`, `tests/reliability.test.js` | Missing-model failure mapping and regression coverage |
| `scripts/check_cloudflare_runtime.py` | Realistic-token smoke checks for both text roles, strict teaching and independently verified vision |
| `tests/test_critical_repair.py`, provider/visual budget/frontend tests | Strict contracts, fallback, persistence, queue/heartbeat, observational polling, ownership and upload-to-resource integration |

## Automated validation

```powershell
.venv\Scripts\python.exe -m pytest tests -q --disable-warnings --maxfail=5
& 'C:/Program Files/nodejs/node.exe' --test cloudflare/visualai-inference-worker/tests/*.test.js tests/test_learning_frontend.js tests/test_notes_frontend.js tests/test_practice_frontend.js tests/test_frontend_auth.js tests/test_topic_workspace_frontend.js
.venv\Scripts\python.exe -u scripts/check_cloudflare_runtime.py
git diff --check
```

Final Python result: **1,496 passed, 137 skipped, five warnings in 203.14 seconds**. Worker/frontend result after the signed-in browser fixes: **177 passed, zero failed**. Diff check passed. The final focused educational/provider/visual-budget run passed **126 tests**. Skips are not passes and do not establish unavailable integrations.

Regression coverage includes direct-topic creation, structured explanations, notation/misconceptions, invalid/missing/extra fields, malformed JSON, identical primary/fallback validation, no fallback after a valid cloud result, terminal queue timeouts, heartbeat without duplicate work, read-only polling, scoped source-list queries, and upload → terminal extraction → visible source → lesson concepts → detailed notes/diagram/standalone assessment/feedback/source citations/video-plan integration. Existing renderer, audio, protected playback, auth, source ownership, uncertainty, native-PDF and duplicate-upload regressions remain in the full suite.

## Real runtime evidence

Final synthetic Cloudflare smoke exited **0**:

| Check | Actual result | Elapsed |
|---|---|---:|
| QA / Qwen 30B | PASS | 4.688 s |
| Structured text / Llama 70B | PASS | 10.250 s |
| Strict teaching schema / Qwen 30B | PASS | 12.531 s |
| Image extraction + independent cloud review | PASS, one cloud extraction, no local fallback, four verified claims, no uncertain/rejected claims | 19.562 s |

These used synthetic text/image content and did not create live Supabase source rows. The local API health endpoint also returned HTTP 200. An earlier live image check verified eight claims, also with no local fallback.

The earlier 128-token QA probe returned HTTP 502, while realistic 2,048-token checks passed. This disproves a blanket inference-unavailable conclusion for the current endpoint. It does not prove the precise internal cause of the tiny probe's 502; that would require deployed Worker diagnostics. The smoke script now uses realistic output budgets and distinguishes transport-envelope failures from teaching-schema failures.

After the user signed in, actual browser checks passed for direct-topic Binary Search Trees creation, detailed notes selection/generation, flowchart rendering, Ask navigation/answer, standalone MCQ/descriptive submission and 100/100 feedback. Video generation completed and the protected stream loaded as an authenticated browser blob: duration 22.221497 seconds, media readyState 4, no media error.

A synthetic native-text physics PDF uploaded through the browser reached terminal extraction, displayed `CONTENT_READY`, and opened an owned upload-version-1 Newton's Second Law lesson. Its detailed notes, flowchart, standalone assessment/submission/100-percent feedback, Ask answer and video generation/load succeeded. These checks created synthetic test sources/lessons in the signed-in account and retained them. Reload restored the uploaded lesson and its generated media. Audible narration and precise subtitle timing were not established by browser metadata.

Signed-in testing uncovered two additional frontend defects now repaired: the valid lesson retained a stale no-active-session Ask message, and educational Ask responses omitted backend source citations from the rendered conversation. Source observations now render as text with matching source/version/verified checks; foreign citations reject the response. The label explicitly identifies supplemental AI explanation rather than asserting claim-level verification.

After reloading the repaired frontend, a PDF follow-up displayed its actual page-1 observation, source identity and version. The synthetic PDF's durable extraction completed in 4.71 seconds. The existing `tests/fixtures/multimodal/printed.png` fixture also uploaded through the browser and reached durable `completed/content_ready`, progress 100, `is_finished=1`, in 54.65 seconds. The UI retained the truthful `PARTIAL_VISUAL_VERIFICATION` warning and exposed the source for learning; this is usable extraction, not blanket verification of every visual claim.

Selecting **Learn with VisualAI** for that PNG opened a version-1 **Osmosis** lesson with explanation, concepts, notation and misconceptions. The verified lesson was left open. No captured browser console errors remained. A screenshot is saved at `storage/runtime/critical-repair-browser.jpg` (ignored runtime artifact).

## Remaining limits and exact browser verification

Worker missing-model mapping and the earlier Worker timer changes are not deployed. The backend schema compatibility fix works against the current live deployment. The local Wrangler deployment name still differs from the configured host; confirm the intended Worker/account before deployment. Do not claim the remote timeout policy changed merely because local source changed.

Caches, locks and SQLite remain single-process. Optional hierarchy/indexing is still optional; extraction-only completion is not proof of indexed RAG. AI-enriched source lessons use authorized sanitized observations and real observation citations; they are not a claim-by-claim canonical answer verifier. Independent visual evidence must remain uncertain when unsupported. Real audible narration/subtitle timing and the original failing upload are not established by synthetic provider checks.

Observed content-quality limits remain: the generated BST lesson defined height in edges but gave the maximum-node formula for height in levels; a generated physics MCQ offered algebraically equivalent forms of Newton's law as separate choices; mathematical text sometimes contains literal LaTeX markers or a damaged multiplication escape. Detailed notes returned successfully but were brief. Strict JSON validation prevents malformed application contracts, not these semantic/content-quality defects. Resolving them reliably requires an explicit content/assessment quality validation policy; the current repair does not claim universal factual correctness.

1. Open `http://127.0.0.1:8000/login`, sign in, then open `/dashboard`. If the development server did not reload these files, restart `python run.py`; hard-refresh the browser to reload `learning.js`.
2. Enter **Binary Search Trees** and select **Start Learning**. Require a string explanation and visible key concepts. Where present, notation and misconceptions must render as text, without raw JSON.
3. Generate detailed notes, a flowchart and a standalone assessment. Submit MCQ and descriptive answers and inspect score/feedback. No learning loop or reassignment should start.
4. Ask a follow-up question. For direct-topic content, it remains AI-enriched; it must not fabricate source citations.
5. Upload a text PDF. Watch the stage and progress feedback. At terminal extraction, require **Extracted content is available** and a `CONTENT_READY` source card. No visual inference is needed for a text-only PDF.
6. Select **Learn with VisualAI** on that source. Require the owned source/version, lesson concepts, notes, flowchart, standalone assessment and follow-up responses with citations to that source. Indexed sources may also use the existing **Explore topics** path.
7. Upload a PNG diagram and a scanned PDF, including the original problematic PNG. Require cloud first, independent review, page/image provenance and terminal status. Optional failed visuals in a mixed PDF must preserve safe native text and display a warning.
8. Generate video; wait for terminal status; verify protected playback, spoken narration and subtitle timing. Navigate away/back and confirm saved video state. Existing automated media checks use explicit test providers and do not replace this spoken browser check.
9. Retry/double-click a synthetic upload and poll repeatedly; require one active processing job. Restart after completion and inspect the durable result. Use a second signed-in user to verify sources, lessons, jobs and media remain isolated. Exercise a simulated provider/storage failure using mocks, then explicit retry; polling must never initiate recovery itself.

No commit or push was performed for this repair request.
