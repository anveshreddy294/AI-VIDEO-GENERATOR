# Phase 6B.1: Cloudflare primary reasoning

## Pre-edit call graph

A. Canonical content understanding: source_ingestion.index_committed_source -> knowledge_publication.prepare_knowledge_index -> content_understanding.understand_content -> structurer.generate_educational_proposal -> ModelManager.generate_with_fallback(reasoning_only=True) -> local Ollama /api/generate. This is the only product inference path migrated in this phase.

B. General reasoning: qa.grounded_answer -> core.llm.get_llm_provider -> OllamaProvider.generate_content -> /api/generate. Assessment generator -> assessment.providers -> the same legacy provider. Roadmap/remediation consumers retain their current contracts. Not migrated.

C. Embeddings: vector_store._embed -> _embed_ollama -> local embedding endpoints; reindex uses the same genuine embedding provenance. Unchanged.

D. Vision: vision extraction -> extract_vision_ollama_async -> local /api/generate with image payloads. Existing vision-provider compatibility remains unchanged.

E. Video: video_planner -> core.llm.get_llm_provider -> generate_content; video engine supplies its existing configured model. Rendering, narration, Manim, FFmpeg, captions and QA remain unchanged.

F. Legacy/local compatibility: process_structure_and_concepts -> existing structurer helper -> ModelManager; models API -> ModelManager inspection/switching. Retained.

The Phase 6B working tree is preserved; no reset, migration replay, commit or push. Previous failed controlled-source attempt: one Ollama primary plus one repair, 209.062 seconds, final MODEL_TIMEOUT.

Cloudflare schema support was checked against https://developers.cloudflare.com/workers-ai/features/json-mode/; structured output remains untrusted and is validated locally.

## Provider contract and routing

A single synchronous typed ReasoningProviderRouter is used by canonical content understanding. CloudflareProvider calls only the configured backend Worker /v1/generate; no browser credentials or arbitrary model-selection input exists. Task names are an allowlist: content_understanding for the primary proposal and structure_repair for semantic repair. Future task types exist but no QA/notes/assessment/roadmap/video feature was migrated. Legacy ModelManager remains the dedicated one-call reasoning-only local fallback.

Worker response envelopes, task correlation, model/request-ID shape, finite numeric usage, token accounting and unknown fields are validated strictly. Response bytes are bounded to 1 MiB. Raw upstream bodies, headers, prompts and model proposals are never forwarded into errors or logs. Secrets use SecretStr, are excluded from configuration representations, and are not added to frontend/OpenAPI/health output. Redirects and credential-bearing/query/fragment/insecure endpoint URLs are rejected. Only backend HTTPS Worker requests carry the bearer secret.

## Failure matrix and budget

| Primary outcome | Policy |
|---|---|
| Successful typed Worker response | Return proposal; local validators still decide acceptance |
| Connect/network/read timeout, 429, 5xx | At most one transport retry within the same Cloudflare deadline, then one Ollama fallback |
| Typed Worker provider_unavailable | Same retryable infrastructure policy |
| 401, 403, invalid secret/configuration, unsupported task, malformed request/response | Hard rejection; no Ollama fallback |
| Semantic/evidence/hierarchy/DAG rejection | One semantic repair maximum, not infrastructure failover |
| Source authorization/RLS/foreign scope | Reject before inference/index access |
| Programming error | Propagate from router; never select fallback |

Named defaults: connect/write/pool timeout 5 seconds; read timeout 45 seconds; overall Cloudflare deadline 60 seconds. asyncio cancellation bounds the full HTTP exchange, including trickling bodies; read/connect budgets are reserved within the remaining overall deadline. Sync services call this adapter from their existing worker threads; future async consumers should use their thread-pool boundary. Ollama retains its separate configured local timeout (120 seconds here). Cloudflare transport retry cannot restart the 60-second budget. No recursive failover or local transport retry is added. One primary plus one semantic repair bounds the entire understanding invocation to at most four Cloudflare transports and two local calls; slow Cloudflare failures often leave no room for a second transport.

The process-local thread-safe circuit counts failed retryable operations. Three consecutive retryable failures open it for 60 seconds; permitted requests use local fallback during cooldown. A single half-open probe is allowed afterward. Success clears the circuit. Nonretryable/semantic failures cannot open it. Programming errors release an outstanding probe without invoking fallback. No prompts or credentials are stored in circuit state.

## Evidence anchors and grounded annotations

Scope-bound UUID5 sentence anchors include exact canonical ContentUnit identity, owner/source/version, character bounds, text and anchor-policy version in their identity. The model references anchor IDs only; it does not copy canonical quotes, compute offsets or select canonical IDs. The server regenerates and resolves anchors from scoped canonical ContentUnits, rejects unknown/foreign/duplicate refs, and preserves repeated-sentence offsets. The authoritative anchored proposal DTO supplies the Worker response schema. The strict internal Phase 6B quote contract remains available for internal compatibility/model doubles and still validates exact text and scope.

Adjacent selected sentences with the same ContentUnit and role merge only across whitespace into one exact canonical span, matching the deployed one-association-per-content/concept/support-kind key. Disjoint conflicting spans remain rejected. Explicit must/should-before prerequisite wording is recognized; role classification does not establish an edge by itself.

Titles need not be literal source quotes: inflections and a limited set of educational qualifiers are supported while substantive label words remain evidenced. Dependency mentions may resolve a qualified label to a uniquely evidenced definition subject from that concept's canonical anchors. Ambiguous aliases are unavailable. Endpoint scope, explicit dependency wording/direction, genuine source spans and DAG validation remain mandatory; no fuzzy name merging or model-memory evidence is accepted.

Initial 30-second read/45-second overall defaults were tested against the real structured workload. Healthy ~744-token responses took 23–27 seconds, but some exceeded the initial read deadline. Defaults were therefore raised to 45 seconds read/60 seconds overall, independently of the local 120-second timeout. No secret or ignored .env change was needed.

The compact primary prompt contains each evidence anchor once without database internals, authentication values, Qdrant metadata or a repeated JSON schema. Repair adds only the prior proposal as untrusted data and targeted safe diagnostics; it does not nest the full prior prompt.

## Publication/lifecycle

The exact existing source/version is retried via the authenticated source retry route. No new upload or re-extraction occurs. Snapshot generation stays after canonical source/content publication, and Qdrant stays after the existing atomic knowledge commit. Stable operation identity and immutable READY knowledge are unchanged. Existing source-status RPCs handle FAILED -> INDEXING -> READY recovery. No separate knowledge-state migration is necessary for this controlled retry, and no schema/Auth/RLS change was created or deployed.

Embedding and vision paths remain unchanged. Educational chunks use the existing genuine embedding space and educational-chunks-v1 metadata. READY retry regenerates chunks from canonical ContentUnits, READY map and pinned policy without any model/extractor call or new snapshot publication.

## Verification

Provider doubles test success, transport fallback, hard rejection, response validation, attempt limits, circuit cooldown and overall cancellation. Anchor/model doubles test exact scope/spans, supported derived labels, unique definition-subject resolution and ambiguity rejection. Real isolated PostgreSQL tests retain actual RPC/RLS/constraint enforcement; doubles are not live-provider proof.

Final targeted tests: **373 passed**, including provider/anchor/model doubles and real isolated PostgreSQL suites. Frontend Auth: **14 passed** under Node. Final full suite: **884 passed, 1 optional real-model E2E test skipped, 4 existing warnings** with the PostgreSQL binary explicitly enabled. `git diff --check` passed. The warnings are duplicate dashboard operation IDs, the existing unregistered e2e marker and audioop deprecation. No commit/push occurred.

Secret checks found the actual Worker secret absent from git diff, all changed files, live receipts, server logs, OpenAPI and health output; .env remains ignored. The working tree contains 24 changed/new files including the preserved Phase 6B changes. Phase 6B.1 touches 11 of these: .env.example, config.py, reasoning.py, structurer.py, content_understanding.py, evidence_anchors.py, educational_chunker.py, knowledge_publication.py, the two new provider/anchor test files and this document.

## Real live acceptance

Only source `SRC_bdfe5e0faf7851159e3c83dbf22b69e2`, version 1, was retried. Its six original canonical ContentUnits were reused. Real Cloudflare returned @cf/meta/llama-3.3-70b-instruct-fp8-fast proposals through the authenticated Worker. The primary proposal had an invalid prerequisite key and was rejected before publication. One structure_repair call produced the accepted proposal; no Ollama inference was used in the accepted invocation.

The resulting canonical snapshot has **2 topics, 2 subtopics, 4 concepts, 5 evidence associations and 1 prerequisite** (Linear Equations depends on Variables). One summary ContentUnit was deliberately not promoted to a concept; all six units remain represented in chunk evidence. No generic filler/synthetic topic or extra count-driven structure was created.

| Topic | Subtopic | Concept | Supporting canonical content IDs |
|---|---|---|---|
| Algebra | Algebra Basics | Variables | CU_072329bb9370559fb50ab448b2301077 |
| Algebra | Algebra Basics | Linear Equations | CU_96cccdcd7a7d5cabb0bf4cf9a3ac29ea; CU_aa124ffdd7db539baf4e85ab925e3ba4 |
| Biology | Cell Biology | Cell Membranes | CU_3ba098a12db6502baad5b5b576233ea8 |
| Biology | Cell Biology | Osmosis | CU_b249e4bc1cdb55db85abe2215f230b5e |

Supabase normal-user Data API/RPC publication completed and knowledge/source both reached READY. MCP metadata checks are supplemental; live authorization proof uses normal authenticated JWTs and public API credentials. The canonical migration remains deployed exactly once and its local SHA remains 15f6871070288d1d0fc180cd7aa433a58985f88d60a4f2330810ed125f6b2e21. No new migration was necessary or applied.

Four educational-chunks-v1 Qdrant points were read through the actual SDK. Their verified user/source/exact integer and display versions, point IDs, supporting content IDs, topic/subtopic/concept fields, canonical spans, roles, policy version, sanitization/retrieval eligibility and genuine embedding provenance were verified. Existing Ollama embeddinggemma produced semantic version-1 vectors of dimension 768. No vector-space/collection migration or synthetic embeddings occurred. Initial embedding/index duration was **8.375 seconds**.

## Successful-run benchmark


| Measurement | Accepted invocation |
|---|---:|
| Primary semantic calls | 1 |
| Semantic repair calls | 1 |
| Ollama fallback calls | 0 |
| Prompt tokens | 3033 |
| Completion tokens | 1293 |
| Total tokens | 4326 |
| Returned neurons | 345.696335 |
| Worker inference latency, primary | 24.409 s |
| Worker inference latency, repair | 15.298 s |
| Sum of raw Worker inference latency | 39.707 s |
| Sum of application transport latency | 41.048 s |
| End-to-end proposal/validation stage | 41.063 s |
| Reported validation timer | 0.0 s (below timer resolution, not zero computational work) |
| KnowledgeRepository Data API calls | 9 |
| Initial Qdrant batch writes | 1 |
| Initial embedding/index latency | 8.375 s |

The 41.063-second understanding-stage timer includes generation/repair and deterministic validation but excludes canonical read/commit network overhead and indexing. The earlier 209.062-second Ollama measurement was a failed generation/repair attempt. These are disclosed stage measurements; no whole-ingestion speedup factor is claimed. Neurons are usage reported for returned successful Worker envelopes in the accepted invocation, not a dollar charge or total account usage. Before acceptance, five diagnostic/recovery invocations failed closed on this same source; including acceptance, there were 11 controlled-source Cloudflare transports and two real local fallback calls, plus one small Worker contract probe. These diagnostics consumed additional inference and are not included in the accepted-run table. Timeout calls may consume unreturned usage.

## Restart and recovery

A controlled downstream indexing failure was injected only after the first genuine indexing success. Knowledge remained READY and the source became FAILED through the existing status RPC. A subsequent real retry re-embedded/upserted from canonical content/map with inference and extraction replaced by rejecting sentinels. It made zero model calls, preserved the operation UUID/hash/commit timestamp, recovered source READY and created no duplicate source/version/snapshot or point IDs. This failure injection tests recovery; the successful embeddings/Qdrant operations themselves were real.

VisualAI was restarted exactly once. Normal owner HTTP access returned the identical canonical map hash, second-user HTTP access remained 404, and actual Qdrant points retained an identical sorted ID/payload hash. Source and knowledge remained READY. Foreign index retry returned 404; anonymous retry returned 401. Foreign understanding was denied before any provider/index access. A valid reconstructed owner snapshot submitted through the real Data API using the second normal JWT was rejected with HTTP 403 / SQLSTATE 42501; the owner operation/hash/timestamp remained unchanged. Foreign reads across all five knowledge tables returned no rows. Legacy student_id override attempts were rejected (knowledge 422; index retry 404). Owner Data API counts confirmed one source, one version/snapshot and six original units, with zero duplicates.

## Remaining risks

Hosted latency can vary and quotas may trigger bounded fallback; the local model remains slower and may fail the same strict semantic contract. The production batch retains the existing 60,000-character/context caps; large-source batching is a later design task. Labels/definition-subject aliases are conservative, and ambiguous evidence remains a hard rejection. Structured-output guarantees do not replace evidence validation. Circuit state is process-local and resets on restart. Existing knowledge-state transitions do not independently record FAILED; source lifecycle carries that diagnostic until a separately approved design requires otherwise.

Phase 6C was not implemented. Video, vision, embeddings and existing legacy-learning guards were not migrated.
