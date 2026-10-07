# Phase 6B: evidence-grounded content understanding

## Foundation and reuse

Workspace: `C:\\Users\\ANVESH\\Desktop\\AI-VIDEO-GENERATOR`; branch `stabilization-python312`. The workspace was initially clean. The deployed `20261007062312 canonical_knowledge_snapshot` migration was inspected through the Supabase MCP and remains deployed exactly once. No migration, schema, Auth configuration or RLS change is part of this phase.

The existing extraction dispatch, normalizer, sanitizer, deterministic concept-ID validation, reasoning-only Ollama model-manager path, token counter, recursive token splitter, strict KnowledgeSnapshot contracts, KnowledgeService and authenticated atomic RPC adapter are reused. Existing historical ingestion and file-mode structuring remain available in their original modes.

Concrete defects found: new Supabase ingestion previously structured before source publication, depended on a local diagnostic graph write, and indexed per-unit chunks before canonical knowledge existed. The legacy chunker docstring overstated section awareness; it now accurately describes per-unit splitting. Direct upload also lacked a handler for durable post-commit structuring failures.

## Input and proposal contracts

Only canonical ContentUnits read through a verified caller UUID, source ID and exact integer version are accepted. Stored sanitized-content records must match canonical text and exact source/version; quarantined or retrieval-ineligible input is rejected. The existing sanitizer is rechecked before prompting. No local graph, vector text, model memory or raw upload bytes serve as knowledge authority. Canonical ContentUnits retain extraction confidence, method, heading, page/slide, timestamps, chapter/section and original offsets.

A strict, extra-forbidden proposal contains topics, subtopics, concepts and optional directed prerequisites. Every item has referenced ContentUnit IDs and verbatim evidence quotes. The model chooses temporary keys only; it cannot choose owner/source/version, canonical IDs, operation IDs or readiness. Derived definitions do not replace original evidence. Canonical IDs use scoped UUID5 identities and validated concept-ID syntax; duplicate normalized labels are rejected rather than silently merged.

Deterministic gates validate scope, IDs, exact quotes and spans, role evidence, source-grounded labels, complete parent membership, nonempty hierarchy, duplicate identities and prerequisite direction/DAGs. Summary citations may support definitions in another unit, provided they name a descendant concept in an educational statement. Heading-only hierarchy citations are rejected. Prerequisites require explicit directional evidence naming both endpoints; document order alone is insufficient.

Supported internal roles: DEFINITION, EXPLANATION, EXAMPLE, WORKED_EXAMPLE, FORMULA, PROCEDURE, DIAGRAM_DESCRIPTION, TABLE, QUESTION, ANSWER, SUMMARY, PREREQUISITE_EVIDENCE and GENERAL_CONTENT. Uncertain roles remain GENERAL_CONTENT.

## Bounded generation and failures

One whole-source primary generation and at most one repair are permitted per invocation. Existing local reasoning-only Ollama is used; there is no paid provider requirement or text-to-vision routing. Named safety limits are 60,000 source characters, a 32,768-token context, 4,096 output tokens, a 120-second provider timeout, a 512-token context margin and a 100,000-character response ceiling. Oversized input is rejected rather than silently truncated.

The prompt JSON-delimits untrusted source data and forbids instructions/tools/identity overrides. A repair receives the rejected proposal as untrusted data and safe diagnostic categories; reference, quote, role and label errors are distinguishable internally. No source documents or raw proposals are logged. Malformed, ungrounded, unsupported, cyclic or exhausted proposals fail closed without synthetic topics. Chunk layout is validated before publication using an honest PENDING canonical DTO, never fabricated READY state.

The current knowledge RPC has no supported FAILED transition. Therefore an exhausted proposal marks the already durable source FAILED using the existing source-status RPC while knowledge remains LEGACY_UNMAPPED. Direct upload returns a safe 422, or 503 for unavailable/timed-out providers. This lifecycle limitation is explicit; no unsupported database write is invented.

## Structural chunking

Policy `educational-chunks-v1` is pinned in source-version metadata: maximum 384 tokens, target 256, explanatory overlap 40 and minimum context 24. The defaults are safety choices, not a universally optimal retrieval size. Invalid target/maximum and excessive overlap combinations are rejected.

The chunker resolves canonical concept evidence spans to topic/subtopic membership, respects paragraphs, roles, headings, sections and modality, and groups coherent adjacent units. Conflicting overlapping hierarchy assignments are rejected before commit. Small heading context can attach to its following block. Oversized blocks use the existing token-aware recursive splitter; overlap is restricted to explanatory/general content and bounded to at most one quarter of the maximum. Definitions/examples are not duplicated by overlap. Oversized structural blocks and small fragments are reported. Equations and diagram interpretation within a coherent paragraph retain their context; exceptionally large blocks require bounded splitting.

Every new chunk has verified owner/source/version, deterministic scoped chunk ID, supporting content IDs, canonical character spans, topic/subtopic IDs where evidenced, concept IDs, role, sequence, heading/page/section/slide/timestamp references, extraction method, retrieval/sanitization flags and policy version/hash. Unassigned educational/administrative text can be preserved with null hierarchy metadata and is reported, not assigned invented concepts. Typed metadata excludes arbitrary prompts and unbounded provenance. Existing indexed embedding provenance is retained.

## Publication and recovery

Order: Auth -> extract -> sanitize -> canonical source/content commit -> propose -> validate -> one atomic knowledge RPC -> read canonical READY map -> structural chunks -> genuine embeddings -> Qdrant -> source READY. The operation UUID is stable per owner/source/version/understanding policy. The existing RPC provides server-side hashing, immutable READY publication and idempotency. No per-topic writes occur.

The immutable Phase 5B source RPC requires nonempty rich_chunks at source commit. New ingestion supplies safe per-unit bootstrap chunks using an empty graph solely to satisfy this existing contract. They are never indexed for the new pipeline. Structural chunks are regenerated from immutable canonical ContentUnits, READY knowledge and the persisted policy; source-version JSON is not rewritten. This deliberate structural constraint avoids editing/replaying deployed migrations.

If indexing fails after publication, knowledge remains READY and source becomes FAILED. Retry reads the durable snapshot and regenerates identical chunk IDs without re-extraction or another model/RPC publication. Qdrant upsert is the derived index operation. Production educational chunks reject synthetic/mock embeddings before Qdrant access. Historical unmarked sources retain their legacy indexing path and are not automatically backfilled. A deliberate one-version service path exists for controlled mapping.

No assessment, notes, video or learning-session operation is started. Existing Supabase legacy-learning guards and local-graph restrictions remain active.

## Quality and observability

Typed reports include evidence coverage, hierarchy/concept counts, prerequisite counts, unassigned content, chunk coverage, fragmentation and oversized blocks. Invalid/orphan/duplicate/cyclic proposals are rejected; successful reports cannot imply accepted invalid rows. Named events cover understanding start/validation/repair/rejection, commit, chunking and index start/completion/failure. Safe source/version identifiers, counts, durations and reason codes are logged, never credentials or full documents.

## Acceptance results

Targeted verification: 330 passed (two existing OpenAPI warnings); the two subsequently added diagnostic/policy regression tests also passed in the final full run. Final full suite: **843 passed, 1 optional real-model E2E test skipped, 4 existing warnings**, with the isolated PostgreSQL binary explicitly enabled. Warnings concern duplicate dashboard OpenAPI operation IDs, the pre-existing unregistered e2e marker and Python audioop deprecation. `git diff --check` passed. No commit or push was performed.

The actual-PostgreSQL/model-double integration verifies two-topic atomic publication, a supported prerequisite, canonical readback, failed vector indexing after READY, retry with generation/extraction forbidden, identical chunk IDs, unchanged source-version receipt and cross-user denial. Model-double and simulated index success are not live-provider evidence.

Live normal Supabase Auth/Data API acceptance created exactly one controlled source, `SRC_bdfe5e0faf7851159e3c83dbf22b69e2`, version 1, containing 6 canonical sanitized ContentUnits. Initial strict proposal failures exposed an over-restrictive same-unit hierarchy rule, corrected with a grounded descendant reference check and a regression test. Subsequent real proposals still failed evidence validation. The latest bounded run made 1 primary call and 1 repair call and took **209.062 seconds**; repair timed out and HTTP returned **503** with `CONTENT_UNDERSTANDING_FAILED:MODEL_TIMEOUT`. Source remains FAILED, knowledge remains LEGACY_UNMAPPED, and 0 topics/subtopics/concepts/educational chunks were published. Knowledge RPC writes and Qdrant writes for this source are zero. Embedding/index latency is unavailable because indexing was never reached.

No successful real-model, READY knowledge, semantic-index, or live post-READY index-retry acceptance is claimed. These remain blockers for Phase 6C. Further uncontrolled model retries were stopped rather than weakening grounding or fabricating a successful snapshot.

The VisualAI process was restarted exactly once and OpenAPI returned 200. The owner read the durable source/version and its unchanged LEGACY_UNMAPPED state. The second normally authenticated identity received 404 for source/knowledge/index retry, and anonymous index retry returned 401. Foreign understanding was rejected before provider/index access. The normal Data API returned no foreign knowledge rows. No duplicate controlled source exists; the previous accepted Phase 6A source remains READY. READY-map/vector restart persistence cannot be accepted for the new source because it never reached publication.

MCP migration history was rechecked unchanged: canonical_knowledge_snapshot appears exactly once. Local migration SHA256 remains `15f6871070288d1d0fc180cd7aa433a58985f88d60a4f2330810ed125f6b2e21`. Deterministic model doubles prove proposal handling, not live model quality. PostgreSQL tests execute the real migrations/RPC/RLS under authenticated roles. Live acceptance uses existing dedicated normal Auth identities and one controlled new source; no service-role identity is used as proof.

## Remaining constraints

Lexical role and name grounding checks are intentionally conservative and can reject legitimate paraphrased labels. A small local model may fail exact quote/hierarchy contracts; no unsafe fallback is permitted. Very large documents require a separately designed bounded multi-pass strategy. Structural ambiguity is rejected, and live semantic quality requires successful provider acceptance. Bootstrap chunks in immutable source-version JSON are compatibility artifacts; the canonical READY snapshot plus pinned policy defines the educational index.
