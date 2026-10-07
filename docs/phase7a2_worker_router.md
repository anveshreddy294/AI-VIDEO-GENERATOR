# Phase 7A.2 local Worker extension and candidate visual router

## Verified baseline and import

Correct root and stabilization-python312 branch; initial clean working tree and Phase 7A commit 849abcf verified. Authoritative recovered Worker imported exactly before changes. The immutable reference fixture matches attachment SHA256 d4a45c898b1e1477bd608dd6869653d5115fe62da1d48dc6496060f0505509a8. All 22 baseline tests passed before extension. The local extension now passes the same baseline against recovered and current implementations.

Worker project: `cloudflare/visualai-inference-worker/`. Existing text models/tasks and endpoints are preserved. Local typed visual adapters are a module of this same Worker, not another Worker or inference service. Wrangler project name comes from the existing configured workers.dev hostname; AI binding is declared. Actual existing account/routes/compatibility settings need review because only the deployed code, not its original Wrangler configuration, was supplied.

## Router and inference boundary

Production/default and auto mode choose Cloudflare. Explicit local/offline mode remains VISION_PROVIDER=ollama; gemma3:4b remains supported. Embedding provider remains unchanged. Reasoning/QA keep the existing Cloudflare-primary text router and existing bounded local fallback.

Candidate policy only, NOT a measured final mapping:

| Signals | Tier | Cloud model | Operational alternatives |
|---|---|---|---|
| Explicit simple content / validated simple triage | fast | @cf/moondream/moondream3.1-9B-A2B | general -> Ollama |
| Handwriting, equations, tables, normal graphs, mixed material, multiple regions | general | @cf/google/gemma-4-26b-a4b-it | deep -> Ollama |
| Explicit COMPLEX / candidate dense relationship signal | deep | @cf/qwen/qwen3.8-27b | general -> Ollama |

Signals are typed internal metadata; no frontend model selection is exposed. PDF region count/native-text metadata comes from the existing parser. Unknown content uses one bounded fast triage call. A complete validated simple extraction candidate is accepted from that call; there is no duplicate fast invocation. Triage flags cannot demote handwriting/equations/tables/graphs present in its extraction candidate. The candidate relationship threshold of 8 is explicitly provisional, not a confidence calibration or benchmark winner.

The selected operational chain has at most two distinct cloud models and one local invocation. Successful triage can add one preliminary call, so maximum total calls are four; normal operation is one or two calls. A failed fast triage never retries fast. All inference shares the existing visual stage deadline; local fallback has one attempt and the remaining deadline. There is no provider ping-pong. Timeouts/network/429/5xx permit alternatives; authentication/configuration/request rejection and schema/evidence failures fail closed. No quality repair agent was added.

All providers return the same visual-v2 data; existing normalization/sanitization, knowledge structuring, canonical Supabase commit, Qdrant index and RetrievalService remain authoritative. Shared CloudflareProvider.fetch_payload reuses the existing authenticated HTTPS, safe endpoint validation, bounded streaming and cancellation transport. Existing text reasoning behavior passed regression tests.

Transport preprocessing follows Phase 7A image validation; private oriented metadata-free PNG/JPEG is bounded to 2048 longest-side pixels and 2 MiB. Worker envelope is capped at 3 MiB; text remains capped at 256 KiB with strengthened actual-byte enforcement. Compression is a transport policy, not a claim of OCR fidelity at every image size; benchmarks must measure fidelity. No public student image URLs or object storage were introduced. See Worker README for native adapter parameters and official provider references.

## Provenance, timing and caching

Canonical visual provenance gains routing metadata only: requested/used provider and model, complexity/tier, candidate policy/reasons, attempts, fallback classification, request ID, preprocessing/routing/triage/provider/validation timers and cache state. Secrets, URLs, image bytes and prompts do not enter domain provenance or vector payloads.

Canonical cache keys include authenticated owner, source, exact version, original image hash, signals and contract/policy versions. Cached objects are deep copied and bounded to 128 entries; cache hits report zero current provider attempts/time. Local extraction retains unscoped compatibility keys for explicit legacy use, while canonical scopes are included in local cache keys. Scope is established by verified source ingestion, never client UUID overrides.

Timing additions separate image preprocessing, routing, triage, visual provider/validation, knowledge structuring, source/knowledge Supabase commits, embedding and Qdrant write/verification. Total ingestion includes other overhead; these component timings are not presented as an exhaustive sum. Existing QA trace gains retrieval/generation/answer-validation/total milliseconds without changing QA behavior. Reindex keeps canonical ownership/order and does not change embedding models or vectors.

## Benchmark preparation

`python scripts/benchmark_visual_models.py --output <PATH>` writes a no-network manifest of 24 model/fixture cases. `--run-live` is explicitly required for hosted inference, and is deferred until approved Worker deployment. Optional repeats retain individual records; provider cold/warm state remains UNKNOWN rather than invented.

Existing six fixtures plus small equation and complex-diagram fixtures cover required terms, flow/relationship ordering, table cells, axes, equation fidelity, schema validation, injection quarantine, output size and conservative unsupported-vocabulary/equation flags. Scores use deterministic fixture assertions, not another LLM. Conservative vocabulary flags are not exhaustive contradiction detection and can flag benign paraphrases. The original graph fixture contains axis text, not a plotted chart; numerical digitization is not claimed. The existing whole-unit injection quarantine is preserved, including discarding otherwise educational text in an injected unit.

No benchmark winners, cloud latency or speedup over the 78.354-second local baseline have been measured in this preparation task.

## Deployment approval boundary

Required: AI Workers AI binding; existing API_KEY Worker secret. Backend continues CLOUDFLARE_WORKER_URL/CLOUDFLARE_WORKER_SECRET. No secret was copied or exposed. From the Worker directory the deployment command WOULD be `npx wrangler deploy --config wrangler.jsonc`; only the --dry-run variant was executed. Bundle inspection succeeded. Check the signed-in account and existing routes/compatibility metadata before approving. The proposed configuration has no production credential values.

The currently deployed Worker remains text-only. New cloud vision calls require deployment; rejection of unsupported vision is a configuration/request failure and cannot silently switch to local inference. Explicit local development mode remains available. Do not claim cloud runtime acceptance before deployment and the live benchmark.

## Validation

Worker: 43 Node tests; frontend: 21 Node tests. Strict TypeScript check of both Worker source modules passed. Wrangler dry-run bundle passed; pinned development dependencies audit clean after a scoped sharp 0.35.5 override. Targeted Python suite: 174 passed. Full Python suite: 1005 passed, 1 optional live E2E skipped, 4 pre-existing warnings, 220.45 seconds. git diff --check passed. No migration, remote deployment, domain writes, commit or push was performed.

## Known structural limits

The recovered text normalizer permits arbitrary role strings and legacy compatibility shapes; that behavior was deliberately preserved. Its immutable reference remains untyped source, while current Worker modules pass strict checked-JS typing. Canonical cache/concurrency/circuit state is process-local. Worker response timeout cannot cancel already dispatched Workers AI computation. Advanced quality repair, calibrated routing thresholds and independent visual truth verification remain outside this phase.

## Files changed

- `.env.example`
- `app/core/config.py`
- `app/core/reasoning.py`
- `app/db/vector_store.py`
- `app/services/extractor.py`
- `app/services/ingestion/knowledge_publication.py`
- `app/services/ingestion/source_ingestion.py`
- `app/services/qa/canonical_answer.py`
- `app/services/vision.py`
- `app/services/visual_contracts.py`
- `app/services/visual_evidence.py`
- `app/services/visual_router.py`
- `cloudflare/visualai-inference-worker/.gitignore`
- `cloudflare/visualai-inference-worker/README.md`
- `cloudflare/visualai-inference-worker/package-lock.json`
- `cloudflare/visualai-inference-worker/package.json`
- `cloudflare/visualai-inference-worker/src/index.js`
- `cloudflare/visualai-inference-worker/src/visual.js`
- `cloudflare/visualai-inference-worker/tests/fixtures/deployed-worker.js`
- `cloudflare/visualai-inference-worker/tests/text.test.js`
- `cloudflare/visualai-inference-worker/tests/visual.test.js`
- `cloudflare/visualai-inference-worker/wrangler.jsonc`
- `docs/phase7a2_worker_router.md`
- `scripts/benchmark_visual_models.py`
- `tests/conftest.py`
- `tests/fixtures/multimodal/complex-diagram.png`
- `tests/fixtures/multimodal/equation.png`
- `tests/test_visual_model_router.py`
