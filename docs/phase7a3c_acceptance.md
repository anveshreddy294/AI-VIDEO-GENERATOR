# Phase 7A.3C acceptance

**Not ready to commit or advance.** Fixture extraction coverage is calibrated, but all three canonical live cases failed. No success latency, pipeline speedup, or QA timing is claimed.

## Exact structural evidence

Ground truth was read from the fixture pixels: flowchart contains a written Sunlight -> Leaf -> Chemical energy sequence and two separate empty boxes connected left -> right. Nearby text never labels those boxes. Complex diagram contains Sensor -> Filter, Filter -> Controller, Filter -> Alarm, Controller -> Motor, Motor -> Sensor.

Original flowchart failures for both models were benign structural vocabulary false positives (F/G). Deterministic finite label aliases and exact directed graph comparison now distinguish node, edge, direction, branch, and absent-content failures. Geometry descriptions use the explicit arrowhead endpoint; reversed or invented edges remain rejected. Vocabulary flags remain bounded review signals, not universal hallucination proof.

Gemma flowchart: 3/3 completed PASS, provider 1.574/4.460/5.139s; request 2.223/5.073/5.573s. Qwen: 3/3 completed PASS, provider 9.402/10.172/8.363s; request 9.888/10.550/9.022s. Gemma wins.

Gemma complex: 0/2 PASS; both reverse Motor -> Sensor and one also describes an unsupported Sensor -> Controller connection. These failures remain rejected. Qwen: three completed exact-structure PASS (provider 38.121/40.390/37.419s; request 38.669/40.969/38.398s), one timeout. Qwen is the fixture-qualified complex model, with material latency/reliability limitations. Failures are retained individually, not averaged away. No alternate model was added; current models passed the fixture quality gate.

## Request diagnosis and deployment

Complex fixture is 800x440, five components/five directed edges, 10,492 PNG bytes, 14,014 encoded transport characters, approximately 145 visible label/title characters per megapixel. Post-preprocessing remains 800x440 because reducing this small image would risk labels. Compact extraction prompt is 1,075 characters including common instructions. No educational teaching prose is requested.

A bounded diagnostic HTTP allowance observed the Worker return AI_PROVIDER_TIMEOUT at its unchanged 45,000ms AI limit: timeout layer WORKERS_AI; no usable result returned. Production HTTP read remains 45s, overall request 60s, visual stage 90s.

The trial 1024-token complex cap exhausted native reasoning with finish_reason=length and no answer. Original 2048-token ceiling was restored. Gemma native chat_template_kwargs.enable_thinking=false is used only for structural workloads; Qwen retains reasoning_effort=low. [Cloudflare native Gemma example](https://developers.cloudflare.com/workers-ai/get-started/workers-wrangler/). No timeout was increased.

Current verified Worker version: 1eea3c77-f1e9-462e-9fc9-785071370040. All seven original text tasks passed live after deployment. Production Moondream remains removed.

## Routing

Printed/simple diagram -> Gemma -> local operational fallback.
Handwriting/table/equation -> Qwen -> qualified Gemma -> local operational fallback.
Graph -> Qwen -> local operational fallback.
Flowchart -> Gemma -> qualified Qwen -> local operational fallback.
Explicit complex -> Qwen -> local operational fallback. Unqualified complex Gemma is excluded.

Policy benchmark-7a3c-v1; no LLM triage or arbitrary numeric complexity threshold. Unknown input stays general. Optional validated visual_workload upload metadata carries declared structure through the source job and image dispatcher. It selects a workload, never arbitrary model IDs or authorization; JWT ownership remains authoritative. Metadata is not an automatic classifier, and unknown images are not guaranteed complex detection.

Only timeout/rate-limit/network/unavailable/5xx errors permit operational fallback. Invalid educational evidence fails closed and never triggers quality provider hopping. Qualification remains fixture-specific, not a claim of broad visual grounding.

## Three normal-auth canonical live cases

Existing dedicated identities authenticated normally using local ignored configuration. No credential/token was emitted or stored in receipts.

| Case | Result | Time until failure | Vision evidence |
| --- | --- | --- | --- |
| SIMPLE | STRUCTURING / UNSUPPORTED_EVIDENCE | 50.257s | Gemma cloud, exact fixture PASS, no local vision call |
| STANDARD | STRUCTURING / INVALID_HIERARCHY | 30.159s | Gemma flowchart cloud, exact fixture PASS, no local vision call |
| COMPLEX | EXTRACTION / VISION_EXTRACTION_FAILED | 93.523s | No evidence accepted; deadline failure |

SIMPLE and STANDARD canonical source records are FAILED, knowledge remains LEGACY_UNMAPPED; persisted visual-v2 content passes fixture review. Identity B sees no content and receives the safe 404 boundary. COMPLEX created no canonical source record. No retry was made to obtain favorable quality output. No new READY knowledge/session/QA was produced. Embedding/Qdrant publication and full upload-to-READY timing cannot be established from these failed runs. Local baseline remains 78.354s; speedup and all QA timings are NOT_MEASURED. Existing accepted sources were not modified.

SIMPLE visual metrics: preprocessing 31.292ms, routing 3.741ms, provider request 24400.933ms, validation 0.396ms.
STANDARD visual metrics: preprocessing 5.332ms, routing 2.023ms, provider request 3416.244ms, validation 0.152ms.
Remaining failed-stage metrics are unavailable, not inferred from total elapsed time. Complex fallback call counts cannot be proven from absent accepted provenance; no zero-call success is claimed.

## Validation

Full Python: 1035 passed, 1 skipped, 4 existing warnings (287.97s).
Targeted source/router/structure/reasoning/multimodal/Phase6 security: 254 passed, 1 skipped.
Worker: 70 passed; strict JS type check PASS. Frontend: 21 passed. git diff --check PASS.
Regression tests show no Phase6, Phase7A, or central RAG regressions. Live knowledge preparation and complex extraction remain blockers.

No migrations, Auth/RLS changes, embedding changes, Qdrant architecture changes, quality repair agent, commit, or push.

## Phase-specific files

- app/api/pipeline.py
- app/api/source_jobs.py
- app/services/dispatcher.py
- app/services/ingestion/source_ingestion.py
- app/services/visual_router.py
- cloudflare/visualai-inference-worker/src/visual.js
- cloudflare/visualai-inference-worker/tests/visual.test.js
- scripts/benchmark_visual_models.py
- scripts/benchmark_visual_structure.py
- scripts/visual_structure_ground_truth.py
- tests/test_source_supabase.py
- tests/test_visual_model_router.py
- tests/test_visual_structure_ground_truth.py
- docs/phase7a3c_*.json and this report (raw attempts, immutable failed trials, separate deterministic reviews, request diagnosis, routing, canonical acceptance, validation).

Pre-existing uncommitted work from earlier phases remains in the worktree. Failed trial records are preserved; only separate review artifacts contain updated checker scores. Runtime diagnostic launchers/logs live outside the repository.
