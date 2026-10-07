# Phase 7A canonical multimodal ingestion

## Workspace and pre-change audit

Verified repository `AI-VIDEO-GENERATOR`, branch `stabilization-python312`, clean initial working tree, Phase 6D commit `d5139f9` present.

| Audit | Existing implementation and finding |
|---|---|
| A: formats | TXT, PDF, PNG/JPG/JPEG and existing video route. Phase 7A changes images/PDF visuals only. |
| B: image route | Authenticated upload -> dispatcher -> vision -> existing ContentUnit; old filename-derived text and fixed confidence were unsafe. |
| C: PDF text | PyMuPDF native blocks retain ordering, page and parser bounding boxes. |
| D: PDF visuals | Embedded raster images; scanned or drawing-only pages rendered only when no native text. |
| E: provider | Production Ollama; historical OpenRouter-named functions are compatibility aliases. Existing mock/file compatibility retained. |
| F: schema | Previously permissive lists/default confidence; now strict bounded typed visual-v2 schema and native Ollama structured output. |
| G: validation | Previously repaired plain prose into invented headings/diagram components; canonical path now rejects unsupported output. |
| H: injection | Reuses source sanitizer/quarantine and evidence-backed educational validation; image instructions remain untrusted source data. |
| I: fallback | Existing bounded model retry remains; canonical adapter bypasses legacy OCR/generic-caption fallback. |
| J: ContentUnits | Uses existing model; provenance added to Python model to represent already deployed JSONB column. |
| K: persistence | Existing authenticated source RPC; previously discarded unit provenance, now retains it. |
| L: structuring | Same anchored Phase 6 normalizer/structurer/validator/snapshot RPC. |
| M: indexing | Existing canonical commit precedes Qdrant; visual payload retains exact owner/source/version/evidence identity. |
| N: retrieval | Existing RetrievalService hydrates authoritative units and creates visual citations; no parallel index or retrieval path. |

## Implemented contract and bounds

Typed content kinds cover text, handwriting, diagrams, flowcharts, graphs, tables, equations, figures and mixed evidence. Table dimensions, axes, units, labels, directional relationships and visible formulas are validated. No invented headings, filename lessons, page numbers, coordinates, symbol meanings or confidence defaults are accepted as canonical evidence. Provider/model routing provenance comes from transport, not model-supplied JSON.

Limits: 8 MiB image bytes, 16 million pixels, one frame, two concurrent calls, existing configurable request/stage timeouts, two bounded attempts, 256 KiB streamed provider response, 2048 output tokens, 128 cache entries, at most 25 PDF vision regions. Text fields and collection dimensions are bounded by the typed schema. Embedded images with either dimension below 50 pixels are explicitly considered decorative and skipped. Rendering uses the existing 2x scale with a pre-render pixel check.

Mixed PDF policy is all-or-nothing for selected visual evidence: required decode/provider/validation failure aborts canonical acceptance. Native text is preserved, but a failed required visual cannot silently become READY. Optional missing image position is retained as unknown. Actual parser bounding boxes are normalized when available.

Unit provenance retains visual index, semantic kind, provider, actual model, validation state, image hash and bounded extraction. Canonical IDs/owner/version come from authenticated repositories. Qdrant carries only selected citation provenance, not the full extraction blob. Existing nonvisual chunk identity serialization excludes new defaults, preserving TXT identity. Sanitized visual text is not reconstructed from the original unsanitized description.

Supabase remote inspection confirmed existing provenance/bbox/image fields. No new migration, remote schema change, Auth setting change, RLS change or object store is needed.

## Validation

Deterministic fixtures cover printed educational diagram, handwritten-style note, flowchart, table, graph, injection, blank and corrupt images. Provider doubles exercise educational extraction types; these do not establish independent model accuracy for all handwriting/chart styles. Real disposable PostgreSQL applies existing migrations and exercises authenticated source RPC, exact version, retained provenance, idempotency, owner-only reads and anonymous denial.

Tests cover schema/malformed/refusal/garbage/low-information/equation validation, system/data boundary, actual resolved model, streaming budget, sanitization/quarantine, canonical commit before indexing, database failure without vectors, vector failure preserving canonical units, retry without extraction, central retrieval/grounded citations, and prior Auth/source/knowledge/session regressions.

Live acceptance used existing verified Auth identities and one small printed osmosis image with a labeled diagram. Ollama `gemma3:4b` returned validated evidence; one canonical visual ContentUnit persisted; the source and mapped knowledge reached READY. Authenticated focused session QA retrieved image evidence and returned a verified citation. Upload-to-READY: 78.354 seconds; QA: 14.863 seconds. After one restart, knowledge hash/session remained unchanged and grounded QA passed in 13.965 seconds. Anonymous API access was 401; foreign API access was 404 and foreign normal-JWT Data API returned no units. Read-only remote audit found no duplicate unit groups and unchanged five-entry migration history. The prior TXT source remains READY.

Initial provider output was empty JSON and correctly failed extraction without canonical evidence; supplying the complete prompt and native schema corrected the provider request. No fabricated acceptance was used. Failure-path tests explicitly mock failure instead of assuming absent OpenRouter credentials disable Ollama.

Frontend: 21 Node tests passed; strict TypeScript check of checked JS passed. Final Python suite: 968 passed, 1 optional live E2E skipped, 4 pre-existing warnings, 217.76 seconds. Targeted vision/canonical/database/runtime suite: 83 passed. `git diff --check` and changed-file credential-pattern check passed. Read-only local Qdrant persistence inspection found two distinct image points with canonical scope and visual provenance; it did not open a second writable Qdrant client or deserialize point blobs.

## Phase 7B limits and structural debt

No independent multi-model verification or calibrated confidence is claimed. Equation consistency checks compare visible transcription with extracted expression; they cannot prove image truth. Complex chart digitization, multi-panel figures, sophisticated layout/graph reconstruction and contradiction detection remain Phase 7B.

Vector drawings on pages that also have native text are not yet selected as separate visual regions. Repeated embedded image xrefs use the first parser position, and decorative filtering is size-based rather than educational relevance. Required failure aborts the whole mixed source; no partial canonical readiness is claimed.

Historical provider aliases and production test-aware urllib compatibility remain structural debt. Legacy OCR/video helpers retain their existing behavior; the canonical Phase 7A image/PDF adapter bypasses these fallback paths. No unrelated video redesign was made. Local job durability and model throughput remain existing limitations.

No commit or push performed.

## Files changed

- `app/services/dispatcher.py`
- `app/services/educational_chunker.py`
- `app/services/extractor.py`
- `app/services/ingestion/failures.py`
- `app/services/ingestion/normalizer.py`
- `app/services/repositories/knowledge_repository.py`
- `app/services/repositories/source_repository.py`
- `app/services/retrieval.py`
- `app/services/schemas.py`
- `app/services/snapshot_validation.py`
- `app/services/vision.py`
- `app/services/visual_contracts.py`
- `app/services/visual_evidence.py`
- `app/static/learning.js`
- `docs/phase7a_multimodal_understanding.md`
- `tests/fixtures/multimodal/blank.png`
- `tests/fixtures/multimodal/corrupted.png`
- `tests/fixtures/multimodal/flowchart.png`
- `tests/fixtures/multimodal/graph.png`
- `tests/fixtures/multimodal/handwriting.png`
- `tests/fixtures/multimodal/injection.png`
- `tests/fixtures/multimodal/printed.png`
- `tests/fixtures/multimodal/table.png`
- `tests/test_async_vision_cancellation.py`
- `tests/test_ingestion_runtime_repair.py`
- `tests/test_learning_frontend.js`
- `tests/test_multimodal_canonical.py`
- `tests/test_multimodal_database.py`
- `tests/test_vision_openrouter.py`
- `tests/test_vision_structured_output.py`
