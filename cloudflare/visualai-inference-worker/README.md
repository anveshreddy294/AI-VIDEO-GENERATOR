# VisualAI inference Worker (local preparation only)

The authoritative recovered source was imported without edits and passed 22 baseline Node tests before extension. The exact deployed-source bytes remain in `tests/fixtures/deployed-worker.js`; SHA256 `d4a45c898b1e1477bd608dd6869653d5115fe62da1d48dc6496060f0505509a8` matches the supplied attachment. `src/index.js` now delegates only the new `vision_extract` family to `src/visual.js`. No replacement Worker or external deployment was created.

## Existing contract

GET `/health`; POST `/v1/generate` and `/`; backend Bearer authentication against Worker secret `API_KEY`. Existing Llama tasks: content_understanding, structure_repair, assessment_structured -> `@cf/meta/llama-3.3-70b-instruct-fp8-fast`. Existing Qwen tasks: reasoning, qa, notes, roadmap -> `@cf/qwen/qwen3-30b-a3b-fp8`. Message normalization, 64-message maximum, clamps, structured task schema handling and successful response fields remain unchanged. Existing provider failure responses stay sanitized.

Text task lookup now explicitly rejects inherited prototype keys; supported text task behavior is unchanged. Request-size enforcement is intentionally strengthened: the actual streamed text body is limited to 256 KiB even without Content-Length. Previously only that header was checked. The shared reader temporarily permits a bounded 3 MiB envelope for visual classification, then enforces the task-specific bound. Malformed JSON retains the recovered text error behavior.

## New visual contract

Authenticated `vision_extract` requests contain only `task`, `tier`, `image`, `prompt`, `schema_version`, optional `purpose` and `response_schema`. Tier is fast/general/deep, schema_version is visual-v2. Arbitrary model IDs, URLs, unsupported tiers and unknown fields are rejected. The existing successful envelope stays `ok, request_id, task, model, response, usage, latency_ms`.

Server allowlist (candidate roles, not measured winners):

- fast: `@cf/moondream/moondream3.1-9B-A2B`
- general: `@cf/google/gemma-4-26b-a4b-it`
- deep: `@cf/qwen/qwen3.8-27b`

Moondream uses native `task=query`, inline image data URI, question, reasoning=false and max_tokens. Gemma/Qwen use multimodal messages with text/image_url parts and max_completion_tokens; Qwen uses low reasoning effort. Native adapters normalize Moondream answer and chat choices into the same envelope. No common fictional image parameter is forced onto every model.

Official references: [Moondream](https://developers.cloudflare.com/workers-ai/models/moondream3.1-9B-A2B/), [Gemma](https://developers.cloudflare.com/workers-ai/models/gemma-4-26b-a4b-it/), [Qwen](https://developers.cloudflare.com/workers-ai/models/qwen3.8-27b/), [Workers AI API](https://developers.cloudflare.com/api/resources/ai/methods/run/), [Worker limits](https://developers.cloudflare.com/workers/platform/limits/).

Every profile treats image instructions as untrusted source data and limits extraction to visible evidence. Worker inference is not canonical educational authority: backend visual-v2 and existing sanitizer/educational validation still decide acceptance. Provider invocation failures return 502; invalid provider envelopes/output return 422 so they cannot masquerade as operational outages.

## Private image bounds

The backend reuses Phase 7A 8 MiB/pixel/frame validation once, removes image metadata, normalizes orientation, bounds longest side to 2048 pixels and encodes PNG where possible. JPEG quality 85 is used only if PNG exceeds the 2 MiB transport budget. Remaining oversize input fails explicitly; no repeated lossy repair loop exists. Inline base64 PNG/JPEG is private backend-to-Worker transport, not a public student image URL. Visual envelope max is 3 MiB; decoded image max is 2 MiB; prompt max is 32,000 characters; output max is 256 KiB; one Worker invocation per request is bounded to 45 seconds. A Worker timeout bounds the response; it cannot guarantee cancellation of already dispatched Workers AI computation. Native model constraints and small-text accuracy still require the approved live benchmark.

## Local commands

From this project directory:

```powershell
npm ci --ignore-scripts
npm test
npx wrangler deploy --dry-run --outdir <LOCAL_BUNDLE_DIRECTORY>
```

Dry-run was executed; no deployment occurred. Wrangler 4.148.0 is pinned. A scoped dev-only sharp 0.35.5 override removes the upstream Miniflare dependency advisory; npm audit reports zero vulnerabilities. No remote Workers AI invocation was made, including via local `wrangler dev`.

## Deployment boundary — explicit approval required

The command that WOULD deploy, from this directory, is:

```powershell
npx wrangler deploy --config wrangler.jsonc
```

It has NOT been executed without `--dry-run`. Wrangler name is derived from the configured existing workers.dev hostname. Confirm the signed-in Cloudflare account, existing deployment settings/routes and proposed compatibility date before approval; the recovered source did not include original deployment metadata. This project does not configure a new account or copy API tokens.

Required binding: `AI` (Workers AI). Required existing Worker secret: `API_KEY`. VisualAI backend continues using `CLOUDFLARE_WORKER_URL` and `CLOUDFLARE_WORKER_SECRET`; no new secret names are needed and no secret value belongs in config/source.

Keep the existing production text path unchanged. New backend default/auto vision mode selects Cloudflare and requires this visual extension; the currently deployed text-only Worker is expected to reject the new task, without silent local substitution. Explicit offline/development mode remains `VISION_PROVIDER=ollama`; do not present it as normal cloud production routing.

After deployment approval: run `python scripts/benchmark_visual_models.py --run-live --repeats 2 --output <REPORT_PATH>` from the repository root. This is evaluation-only fan-out (24 fixture/model combinations per repeat), incurs provider usage and creates no domain records. Without --run-live the command writes a manifest and makes no network calls. Model winners and routing thresholds remain provisional until actual measurements. Cold/warm state is UNKNOWN unless separately observed; first versus subsequent iterations are reported, never silently averaged.
