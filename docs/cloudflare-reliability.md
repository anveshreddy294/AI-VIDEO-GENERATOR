# Cloudflare-first reliability implementation — fixext

This records repository changes and actual checks on 2026-10-10. The implementation is local and uncommitted. No Worker deployment, package installation, schema change in Supabase, or new learning loop was performed. A reliable live Cloudflare upload journey is **not yet accepted**: the configured deployed Worker responds to health checks but rejects real inference with HTTP 502.

**1. Confirmed root causes and unresolved upstream failure**

- `REASONING_PROVIDER` previously inherited `LLM_PROVIDER=ollama`. Canonical text generation therefore bypassed Cloudflare by default. Legacy assessment, video planning and QA used an Ollama-only factory; the older structurer directly selected local reasoning.
- The default image stage was 90 seconds. With fallback enabled, its cloud deadline was reduced by the entire 45-second local window plus connection headroom, leaving only 40 seconds for Cloudflare. Configured longer HTTP timeouts could not overcome that cutoff.
- Complex visual extraction replaced the HTTP policy with hard-coded 60/75-second budgets. Independent review also replaced configured values. The Worker separately returned visual timeouts after 45–55 seconds.
- The general visual route had only one qualified tier and did not retry a transient error. The new route permits at most two cloud transports and then one local call. Quality, authentication and configuration failures remain fail-closed.
- Cloud review only recognized extraction model identities from its two cloud tiers. An extraction produced by Ollama fell through to `VERIFIER_NOT_INDEPENDENT`, even though a cloud pixel reviewer would be a different model. Local Gemma reviewing its own extraction is still prohibited.
- The learner stopped upload polling after 120 two-second intervals. This did not cancel processing, but it made a healthy longer job appear unavailable.
- SQLite saved job state/ownership but omitted `result` and `failure`. Completed jobs could lose their source/result/readiness information after restart. Additive local columns now preserve both.
- PDF parsing interleaved native text and vision. Failure on an early scanned page could discard native text on later pages. Native text is now collected first; optional failed images retain page-specific uncertainty metadata.
- Video fusion had an unconditional early return before speech handling. Videos with transcript segments could produce no content. This is fixed, with a speech/frame regression test. Cloud video frames now use verified visual extraction and retain frame timestamps/provenance; failed frames are omitted rather than replaced with generic assertions.
- Legacy asynchronous QA called a synchronous provider on the event loop. It now uses the existing thread-pool boundary, which also makes the cloud client's synchronous bridge safe there.

Live evidence: the configured `polished-snowflake-ecb1.speedrun3ai.workers.dev` returned HTTP 200 from `/health`, with the expected `visualai-cloudflare-inference` service identity. A tiny authenticated `qa` request returned HTTP 502, `ok:false`, `AI_PROVIDER_ERROR`, with a request ID and no native error code. Both cloud visual attempts also failed with provider-unavailable classifications. The failure occurred within seconds, not near the configured timeout. Successful Supabase requests establish neither inference success nor independent verification. Billing, model access, AI binding configuration and deployed code must be checked in that Worker's account logs; the generic response cannot distinguish them.

**2. Files and responsibilities**

| Files | Change |
|---|---|
| `app/core/config.py`, `.env.example` | Cloud-first defaults, task budgets, bounded concurrency/cache settings, validation, safe effective configuration |
| `app/core/inference_budget.py` | Cooperative job/extraction budgets and bounded local fallback admission |
| `app/core/reasoning.py` | Shared authenticated transport, cloud admission, retry/backoff, Retry-After, native quota classification, optional local fallback |
| `app/core/llm.py`, `app/core/model_manager.py` | Legacy text compatibility adapter; fallback honors configured Ollama text model |
| `app/services/structurer.py`, `app/services/qa/grounded_answer.py` | Cloud routing for legacy structuring and nonblocking QA |
| `app/services/visual_router.py` | Full cloud budget, bounded retry chain, scoped/configuration-aware extraction cache and duplicate suppression |
| `app/services/independent_visual_verifier.py` | Independent review of local extraction, configured review budget, bounded retries, scoped review caching |
| `app/services/visual_evidence.py`, `app/services/vision.py` | Shared deadlines, unpublished claim diagnostics, cloud-compatible legacy vision/frame paths |
| `app/services/extractor.py` | Native PDF parsing first; safe partial results and page provenance |
| `app/services/ingestion/source_ingestion.py`, `app/api/source_jobs.py` | Extraction/job budgets, stage timing, progress and partial-result warnings |
| `app/services/pipeline_tracker.py` | Durable results and structured failures, compatible with older local job databases |
| `app/services/video/{frame_extractor,fusion,pipeline}.py` | Speech fusion repair, frame provenance, removal of failed-frame placeholders |
| `app/api/learner.py`, `app/static/{learning.html,learning.js}` | Environment-driven polling budget, terminal-stop behavior and content/partial readiness feedback |
| `cloudflare/visualai-inference-worker/src/{index,visual}.js`, `wrangler.jsonc` | Worker task budgets and text model configuration, schema forwarding, bounded output, privacy-safe visual diagnostics |
| `tests/test_cloudflare_reliability.py`, existing provider/route tests, frontend and Worker tests | Routing, budgets, recovery, cache isolation, independent review and longer polling regressions |
| `scripts/benchmark_cloudflare_pipeline.py`, `scripts/check_cloudflare_runtime.py` | Reproducible synthetic benchmark and real-provider smoke check |

The ignored local `.env` was updated only for the two existing nonsecret timeout settings: read 90→180 and cloud overall 110→300 seconds. Credentials were preserved. Reload/restart the active server to load the effective settings; changing `.env` alone does not update an already imported Settings object.

**3. Provider routing and model/API inventory**

All cloud requests use the configured HTTPS `CLOUDFLARE_WORKER_URL` at `/v1/generate`, authenticated with the backend-only Worker secret. Its `AI` binding selects the Cloudflare account; the application does not introduce a separate direct account API or third-party provider.

| Task / callers | Before | After / configured model | Fallback |
|---|---|---|---|
| Canonical understanding, repair, concept/prerequisite metadata (`structurer`, `content_understanding`) | Local by default | Cloud `content_understanding` / `structure_repair`: `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Configured `OLLAMA_MODEL`, normally `llama3.2:3b` |
| Canonical question generation (`assessment/generator`) | Local by default | Cloud `assessment_structured`: same Llama 70B model | Same configured local text model |
| Explanations, grading, flowcharts and other educational reasoning (`educational_content`, `ai_explanation`) | Local by default | Cloud `reasoning` / task-specific schema: `@cf/qwen/qwen3-30b-a3b-fp8` | Same configured local text model |
| Grounded notes and QA (`grounded_notes`, `qa/canonical_answer`) | Local by default | Cloud `notes` / `qa`: Qwen 30B | Same configured local text model |
| Legacy QA, assessment and generated video plans | Ollama-only factory | Shared cloud text adapter, `reasoning`: Qwen 30B | Same configured local text model |
| Images, scanned PDF pages, embedded images, video frames | Cloud tier with short budget; legacy frame helper did not support cloud | General `@cf/google/gemma-4-26b-a4b-it`, deep `@cf/qwen/qwen3.8-27b`, using native multimodal messages and image data URIs | Enabled local vision, normally `gemma3:4b` |
| Independent visual review | Different cloud tier, but rejected local extraction | Different approved cloud model for cloud extraction; general cloud tier for local extraction | Uncertain if independent evidence is unavailable; no fabricated verification |
| Embeddings (`db/vector_store`) | Configured Ollama `/api/embed`, `embeddinggemma` | Retained: batched semantic embeddings and idempotent Qdrant point IDs | Existing explicit compatible embedding fallback; no hash vectors in production |
| Speech transcription, TTS, rendering | Local faster-whisper; configured Edge TTS; Manim/FFmpeg | Retained: the configured Worker exposes no ASR, embedding or TTS task | Existing configured behavior; no unrelated provider replacement |
| Gap scoring, mastery rules, source validation, hashing, database operations | Deterministic | Retained deterministic operations; no extra inference calls | Explicit errors where required |

Cloud text model variables live in the Worker (`TEXT_GENERAL_MODEL`, `TEXT_STRUCTURED_MODEL`) and accept the existing supported identifiers. Backend visual model variables retain the measured, distinct tier identities; unqualified replacements fail configuration validation. Secrets never enter frontend configuration. Explicit offline `REASONING_PROVIDER=ollama` remains available; the current runtime defaults to cloud. `LLM_PROVIDER=mock` is an explicit test mode, not a production fallback.

**4. Effective timeout and concurrency policy**

| Setting | Current default / local effective value | Purpose |
|---|---:|---|
| `CLOUDFLARE_CONNECT_TIMEOUT` | 10 s | Connection and pool admission |
| `CLOUDFLARE_WRITE_TIMEOUT` | 30 s | Image/prompt upload |
| `CLOUDFLARE_READ_TIMEOUT` | 180 s | Text response wait |
| `CLOUDFLARE_OVERALL_TIMEOUT` | 300 s | Combined cloud text attempts, including transport/queue time |
| `VISION_CLOUD_TIMEOUT_SECONDS` | 180 s | Visual response wait |
| `VISION_CLOUD_STAGE_TIMEOUT_SECONDS` | 300 s | Combined cloud visual attempts; local fallback does not subtract from it |
| `VISION_TIMEOUT_SECONDS` | 120 s | Local vision request budget |
| `VISION_VERIFICATION_TIMEOUT_SECONDS` | 180 s | Bounded independent review batches |
| `VISION_STAGE_TIMEOUT_SECONDS` | 600 s | Image stage, including extraction/fallback/review |
| `EXTRACTION_STAGE_TIMEOUT_SECONDS` | 1800 s | Whole document/video extraction |
| `SOURCE_JOB_TIMEOUT_SECONDS` | 2400 s | Cooperative background job budget |
| `FRONTEND_JOB_POLL_TIMEOUT_SECONDS` | 3600 s | Browser observation window; expiry never cancels the backend job |
| Worker text/general/complex/review timers | 180000 ms | Configured separately in Worker vars; deployment required |
| Cloud transport concurrency | 3/process | Backpressure across text, extraction and review |
| Independent review concurrency | 3/process | Existing bounded reviewer pool |
| Local fallback concurrency | 1/process | Protects the local machine during a cloud outage |

These are generous starting budgets, not measured optimal Cloudflare latency. An image can consume 300 seconds of cloud work, 120 seconds of local fallback and 180 seconds of review. Each nested operation uses the remaining parent deadline. Retries share one deadline; they do not restart it. There is at most one retry with exponential backoff; valid Retry-After values defer retry, and a delay beyond the remaining budget skips another cloud call instead of retrying early. Quota exhaustion skips futile cloud retries. Missing configuration/authentication and invalid evidence do not silently enable local inference.

The repository has no configured reverse proxy imposing a shorter request timeout. Uvicorn's keep-alive setting is not a model execution deadline. External ingress/proxy and provider-specific inference limits must still be checked for the actual deployment. Cloudflare's [HTTP Worker duration documentation](https://developers.cloudflare.com/workers/platform/limits/#duration) distinguishes connection lifetime from CPU limits; [Workers AI limits](https://developers.cloudflare.com/workers-ai/platform/limits/) document account/model rate limits. Neither establishes that any particular model will run successfully for 180 seconds. Client settings cannot extend a server-side execution limit.

**5. Algorithm and correctness changes**

Native PDF parsing now precedes optional vision; text-only PDFs make zero visual calls. Repeated image extraction uses content hashes, source owner/version, routing signals, model/prompt/configuration identity and a bounded TTL. Fixed lock stripes suppress simultaneous identical work without accumulating unbounded per-document locks. Verified review batches are also cached by owner/source/version/pixels/claims/model/configuration; uncertain failures are not cached as verified. Thread-pool context propagation preserves owner scope in reviewer batches.

The existing one-image Worker contract is retained. Scanned pages remain individually bounded, and embedded-image/page limits remain enforced. This avoids assuming unsupported multi-image limits. No speculative multi-image request format was introduced. Review retains 16-claim batches, a maximum of 24 batches and bounded parallelism; excess claims remain uncertain. Required source grounding, claim correlation, schema validation, quarantine and video code-safety gates remain intact.

Uploaded source extraction commits are reused on identical retries. Committed canonical knowledge is reused on index retries; READY sources skip embedding/index writes. Embeddings were already batched and point IDs deterministic, so those implementations were retained. Document embedding caching across restarts and automatic resume of an interrupted uncommitted extraction were not added.

Only verified visual subsets enter retrieval. Original unpublished verification details remain in provenance for audit, outside the accepted text. Usable native PDF text survives optional vision failure, and the UI warns of incomplete visual coverage. `CONTENT_READY` means reusable extraction is available. `READY` still requires the established indexing/knowledge criteria. Source/database/index failures are not converted into successful completion. Polling reads job state and does not invoke inference, extraction or indexing.

**6. Automated validation**

Run from the repository using existing dependencies:

```powershell
.venv\Scripts\python.exe -m pytest tests -q --disable-warnings --maxfail=5
& 'C:/Program Files/nodejs/node.exe' --test cloudflare/visualai-inference-worker/tests/*.test.js tests/test_learning_frontend.js tests/test_notes_frontend.js tests/test_practice_frontend.js tests/test_frontend_auth.js tests/test_topic_workspace_frontend.js
.venv\Scripts\python.exe scripts/benchmark_cloudflare_pipeline.py
git diff --check
```

Python regression suite: **1,472 passed, 137 skipped, 5 warnings in 195.68 seconds**. Skipped tests are not counted as successful runtime checks. Node/Worker/frontend validation: **170 passed, 0 failed**. This includes a frontend polling harness continuing beyond the old 120-poll cutoff, stopping at completion and issuing only one upload request. `git diff --check` passed.

Synthetic offline benchmark (mocked provider responses, local parsing/cache overhead only):

| Case | Elapsed ms | Cloud extraction calls | Local calls | Result |
|---|---:|---:|---:|---|
| Small native-text PDF | 24.246 | 0 | 0 | 1 unit, page 1 |
| Scanned PDF | 92.527 | 1 | 0 | 1 unit, page 1 |
| Simple diagram | 28.648 | 1 | 0 | 1 unit |
| Complex routing case | 14.108 | 1 | 0 | 1 unit |
| Three-page PDF with repeated embedded image | 95.343 | 1 | 0 | 6 units, all 3 pages, 2 extraction cache hits |
| Simulated provider timeout | 16.194 | 2 | 1 | Local fallback result after bounded cloud retry |

These numbers are **not** real inference latency or an extraction-quality benchmark. No live before/after throughput improvement is claimed. The benchmark isolates orchestration behavior; its reviewer is mocked. Independent review correctness, scoped review caching, uncertainty, persistence errors, security boundaries, Ask and video behavior are covered separately by the regression tests.

**7. Real Cloudflare checks**

```powershell
.venv\Scripts\python.exe -u scripts/check_cloudflare_runtime.py
```

Actual result: **failed**, exit 1. Cloud text failed in 1.703 seconds; cloud-only visual extraction exhausted two attempts in 3.859 seconds. The smoke script deliberately disables local vision substitution and directly checks the primary text provider, so a local result cannot be reported as a cloud pass. Public health returned 200; a separate 16-token inference diagnostic returned the Worker's generic 502 `AI_PROVIDER_ERROR`. No private uploaded document was sent and no source/database rows were created by these checks.

**8. Remaining operational limitations**

- The checked-in Worker changes have not been deployed. `wrangler.jsonc` names `speedrun`, while the configured runtime hostname identifies a different deployment. Confirm the intended Worker/account and AI binding before deploying; do not assume the local Wrangler target updates that hostname.
- The deployed Worker's generic inference error needs its account logs/model-access/billing diagnostics. A successful end-to-end real cloud upload is still required.
- Review may remain uncertain when Cloudflare is unavailable after local extraction. Same-model self-review stays blocked. Native text can be retained; unsupported visual claims cannot be promoted to evidence.
- Jobs/locks/caches remain single-process. SQLite recovery marks interrupted jobs failed and allows explicit retries; this is not a distributed durable worker queue. In-flight synchronous parsing, ASR, rendering and database calls cannot be forcibly stopped safely; budgets are cooperative at stage/model boundaries.
- Extraction caches are bounded process memory, not a new shared cache service. Source commits and knowledge snapshots remain the durable recovery checkpoints. A process crash before extraction commit still requires repeating extraction.
- The existing explicit `/sources/{id}/retry-index` compatibility endpoint is synchronous. Large enrichment/index operations should use the existing background job path when available; browser disconnect does not supply a safe cancellation mechanism.
- Embeddings remain local because this configured Worker has no embedding task. No unsupported cloud embedding model, ASR or TTS route was invented. Real narrated video playback, subtitle synchronization and the user's original failed PNG still require browser verification.
- Supabase schema, authentication and RLS were not changed. Required writes remain user-scoped; regression coverage checks authentication/isolation/citations and code-safety behavior.

**9. Manual browser acceptance steps**

1. In Cloudflare, identify the Worker behind the configured hostname. Check the `AI` binding and model access/account quota. Inspect the failing request ID in Worker logs. Deploy the reviewed source/configuration to that intended Worker, preserving its existing authentication secret. Do not deploy blindly to the local `speedrun` name.
2. Restart the local application with `.venv\Scripts\python.exe run.py` (or rebuild/restart the API container for Docker). Verify startup logs show cloud text/vision primary and the effective budgets, without credentials. Keep the configured Qdrant instance available.
3. Run `scripts/check_cloudflare_runtime.py` again. Require a real cloud text response, real cloud vision response and independent verification; investigate any remaining generic 502 rather than increasing timeouts again.
4. Open `/dashboard`, sign in, and upload a small text PDF. Verify no vision call was needed, the upload returns a job ID and polling ends at content availability. Double-click/retry the same upload and confirm one active job/reused source.
5. Upload a PNG diagram and a scanned PDF. Watch cloud attempts/model identities and independent review diagnostics. Require the correct page/source provenance. Test the original PNG that previously failed. An uncertain visual-only result must remain uncertain rather than falsely READY.
6. Upload a multipage PDF with native text and repeated images. Check page coverage, cache hits and partial-visual warnings. Simulate transient failures with mocks/test configuration; never corrupt live credentials to test fallback. Confirm failed optional images preserve native text.
7. Generate explanations, concise/standard/detailed notes, flowcharts and a standalone assessment. Submit both MCQ and descriptive answers, check scoring/feedback, and ask a follow-up question. Check source citations stay within the signed-in user's selected source/version.
8. Generate a video, wait for terminal status, play its protected stream, and verify spoken narration/subtitles. Navigate away/back during generation and confirm restored progress/playback. Upload a lecture video and verify spoken content and frame timestamps survive extraction.
9. Restart after a completed job and check the job result/source link still exists. Test owned-source index retry after a simulated storage outage; it must fail accurately, recover from committed content and avoid another extraction. Sign in as a second user and verify sources, jobs, caches and protected media remain isolated.

Do not add mastery loops, reassignment or new remediation journeys during these checks.
