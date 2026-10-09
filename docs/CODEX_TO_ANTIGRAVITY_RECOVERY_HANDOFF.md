# Codex → Antigravity: hierarchy-independent educational content

2026-10-09. Branch `phase10-mastery-remediation`; HEAD `d7bf07a67c39d030ae6bcfecce2b434790d84735`. Existing working tree preserved. No commit/push/merge/reset/checkout, remote migration, deployment, secret mutation or live inference.

## Classification and scope

**IMPLEMENTED / VERIFIED OFFLINE:** authenticated educational-content generation from a typed topic or existing owned exact-version extracted observations; default upload no longer invokes hierarchy construction or Qdrant; explicit downstream status; shared teaching input adapter; known daily-quota errors terminate without retry/fallback. No fake source records for typed topics.

**NOT IMPLEMENTED:** complete new-mode Notes/ASK/assessment/video routes, frontend wiring, persisted educational lessons/sessions/assessments, generated-content mastery and goal-aware roadmap adaptation. Existing canonical features retain their current APIs and requirements. This is the core and adapter handoff, not a completed learner UI or universal feature migration.

**UNVERIFIED:** live model quality, generated mathematical correctness, real PDF/image acceptance after these changes, current remote rows/RLS/deployed Worker parity, restart persistence of generated lessons (response-only by design). Existing deterministic math tests check notation preservation, not theorem correctness.

Historical image source supplied for continuation: `SRC_29b77cf15da6521f87525447e1f69813`. Its current remote state was NOT inspected or changed. Do not conflate it with the earlier ledger source `SRC_ad3e1c3e2ba85259ac5346396fc80abe` / job `JOB_16cff9ede6d2`; that ledger recorded successful visual evidence plus failed hierarchy publication, followed by an offline-only vocabulary fix. Neither is a fresh live failure/PASS claim.

## Preservation and exact files changed by this task

The Phase 0 restricted recovery baseline remains outside the repository. Current pre-fix source/configuration was additionally preserved under:

`C:\Users\ANVESH\Documents\Codex\2026-10-06\you-are-working-on-the-visualai\phase0-baseline-20261009-043746\pre-core-fixes`

It contains a hash manifest and pre-fix Git status, including the additional uncommitted work present when this task began. The parent ACL restricts access to the current Windows account and SYSTEM. Private configuration is not reproduced here. Existing Phase 0 snapshot contains generated storage artifacts; pre-core-fixes excludes storage/dependencies/caches. No active repository restore performed. Final hash verification detected a concurrent/local `.env` change since the pre-fix snapshot; this task did not write that file, restore it or inspect differences in secret values. The latest configuration was also preserved privately as configuration-at-core-close.private under the same restricted directory. Its origin is unverified; all other preexisting files outside the eight intended edits remained unchanged.

New:

- `app/services/educational_content.py`
- `app/api/educational_content.py`
- `tests/test_educational_content.py`
- `docs/CODEX_TO_ANTIGRAVITY_RECOVERY_HANDOFF.md`

Incremental edits to existing files, preserving their prior changes:

- `app/main.py` — register additive router.
- `app/services/ingestion/source_ingestion.py` — extraction-only default, explicit `enrich=True`, content availability DTO, optional-failure isolation.
- `app/services/ingestion/knowledge_publication.py` — allow explicit downstream publication for optional-mode versions without rewriting original evidence.
- `app/api/source_jobs.py` — content-ready terminal message/stage and explicit enrichment option for compatibility.
- `app/services/pipeline_tracker.py` — distinguish `CONTENT_READY` lifecycle from indexed `READY`.
- `app/core/reasoning.py` — recognize visible numeric quota codes safely and stop that request.
- `tests/test_source_supabase.py` — explicitly opt legacy enrichment tests into enrichment; assert the new default content-ready result; update compatible test-double signatures. Existing ownership/token/failure/answer checks retained.
- `tests/test_reasoning_provider.py` — quota regressions.

No changes to Worker, Supabase schema/Auth/RLS, Qdrant implementation/configuration, frontend assets or existing mastery/assessment engines. Existing unrelated uncommitted changes are not attributed to this task.

## Root causes addressed and execution flow

Old critical path made a usable upload depend on a complete canonical hierarchy, publication, embeddings and vector indexing. Label/hierarchy errors or vector outages therefore prevented learning. Generated teaching also inherited rules intended for literal source observations.

New default upload:

```text
Authenticated upload
 → file truth / extraction / existing visual correctness boundary
 → normalization and sanitization
 → atomic owned source/version/ContentUnit commit (unchanged RPC)
 → content_ready=true; no hierarchy or Qdrant call
```

New learning entry:

```text
POST /educational-content
 → verified Supabase identity
 → topic only, OR owned exact-version durable observations
 → deduplicated bounded context
 → one teaching proposal + strict response parsing
 → EducationalContent(status=READY, provenance_kind=AI_ENRICHED)
 → teaching_request(...) adapter for independent downstream generation
```

The new path never calls KnowledgeService, hierarchy validators, verified name vocabulary, evidence-anchor builders, RetrievalService or Qdrant. It can read safe durable observations even when an earlier source is FAILED or its knowledge remains unmapped. It does not rewrite that source to pretend publication/indexing succeeded.

`ingest_source(..., enrich=True)` retains the previous explicit upload-plus-enrichment operation. `/sources/{source_id}/retry-index` remains the explicit downstream knowledge/index operation. New default-upload versions carry `provenance.downstream_optional=true`; downstream structure/vector failures do not mark these source records FAILED. The explicit operation still returns a safe error. Historical versions retain their existing retry/failure semantics. Accepted existing READY canonical sources and IDs are not deleted, regenerated or backfilled.

### Status compatibility

The deployed source RPC requires source status INDEXING at commit. No migration or enum change was made. Consequently a content-only source can remain INDEXING in the legacy source row while its upload job has succeeded with `content_ready=true`, `readiness_basis=EXTRACTED_CONTENT`, `downstream.knowledge/indexing=NOT_REQUESTED`, `chunks_synced=0`. Job lifecycle reports CONTENT_READY. This does NOT assert indexed READY or knowledge READY.

Antigravity must use content readiness for the new learning path and legacy READY for canonical indexed behavior. The existing learner explorer is not adapted; it still expects a READY hierarchy. Do not call the backend core change a fixed browser experience. Optional index retries can repeat stable-ID upserts; a distinct persisted index-job state is future work.

## Shared contract and API

`app/services/educational_content.py`:

- `ContentRequest`: `topic`, or exact `source_id`/`source_version`, optionally both. No caller-supplied owner accepted.
- `Teaching`: topic, explanation, key concepts (name/explanation), examples, equations and optional conceptual relationships. No evidence-anchor/name-vocabulary restrictions or lexical match to uploaded words.
- `EducationalContent`: Teaching plus generation UUID (`content_id`), verified `user_id`, READY status, AI_ENRICHED label, optional source scope, server-loaded source observations and provider provenance.
- `SourceObservation`: canonical content/source/version/text/extraction method and actual page/time locations. Generated material cannot populate this structure through model output.
- `teaching_request(content, verified_user_id, purpose, question=..., response_schema=...)`: supports notes, ask, flowchart, assessment, video_plan and explanation. Produces a ReasoningRequest with generated teaching distinguished from uploaded observations. Rejects mismatched owner. This is an internal trusted-input adapter, not authorization to accept forged client content/provenance.

Authenticated additive endpoint:

```text
POST /educational-content
{"topic":"Newton's second law"}

POST /educational-content
{"source_id":"<owned existing source>","source_version":1}
```

Normal Supabase bearer authentication is required. Topic-only requests create no source or canonical LearningSession. Generation ID is correlation identity, not a persisted session. Source missing/foreign scopes deny before generation; invalid response fails with a safe error, never placeholder success or raw provider text. Provider failures produce 503 with safe category. No new public endpoint accepts arbitrary caller-supplied observations/citations.

## Gates decoupled, protections retained

**DECOUPLED from upload and new teaching:** closed canonical name vocabulary, literal-source wording for explanations, mandatory teaching anchors, hierarchy counts/organization, canonical publication, Qdrant/embedding availability, initial-plus-repair structure calls and model approval chain. The new teaching service makes one proposal, with no teaching repair/reviewer call.

**RETAINED on legacy canonical publication:** exact source support, hierarchy/reference/DAG checks and existing DTO contracts. These still protect claims published as source-backed canonical knowledge. They do not apply to the new AI_ENRICHED lesson path. Existing visual extraction/verification still protects uploaded observations; it was not removed wholesale.

**RETAINED everywhere applicable:** verified identity, owner/exact-version lookup, file safety, sanitized/quarantined observation filtering, model-output size/schema validation, real-source provenance, existing assessment answer-key/scoring and SafeQuestion boundaries, rendering/path/media safety and database transaction/idempotency contracts.

Generated explanations may paraphrase and add examples. They are not represented as extracted claims or source-supported citations. Mathematical notation is kept intact through context compaction; model-generated mathematical truth remains unverified.

## Prompt and model/quota behavior

`compact_context` includes each exact paragraph once within 16,000 characters. It omits whole over-budget paragraphs, reports omission count, and never slices an equation to fit. Generated response capped at128KiB. If no source context fits, fail explicitly rather than inventing content. There is no source text + raw visual extraction + anchor text duplication in the new generation prompt. The old optional canonical structurer prompt remains unchanged and can still be larger; it is no longer the default upload/teaching path. No live latency/21KiB reproduction is claimed.

Router/model ordering unchanged: new teaching uses existing reasoning task/router; input adapter maps Notes→notes, ASK→qa, assessments→assessment_structured, diagrams/video planning→reasoning. Existing Cloudflare/Ollama operational fallback remains bounded; one proposal is not necessarily one transport request.

When HTTP400/429 includes visible numeric code4006 or3036 (top-level, error or errors entries), transport emits nonretryable QUOTA_EXHAUSTED. Router does not retry or invoke local fallback for that terminal failure; API does not report READY. Unknown429 remains the existing bounded retry/fallback policy. A sanitized Worker502 without the upstream code cannot be identified as quota from Python; do not assume exhaustion. No Worker request, deployment, secret change, paid service or quota/billing change occurred. Comprehensive fallback/Worker contract work is deferred.

## Exact downstream adaptations for Antigravity

| Feature | IMPLEMENTED usable input | NOT IMPLEMENTED / exact next adaptation |
|---|---|---|
| Explanation | New authenticated endpoint produces usable Teaching from topic or durable extraction. | Wire learner UI to it; persist lesson/material identity if restart recovery is needed. |
| Notes | `teaching_request(..., purpose="notes", response_schema=...)` consumes shared teaching/observations. | `app/services/grounded_notes.py:GroundedNotesService.generate` still resolves canonical session/retrieval and validates literal claims. Add a separate educational-content overload and Notes DTO with honest AI_ENRICHED sections; do not fabricate EvidenceBundle/citations to satisfy validate_notes. Existing source-backed route unchanged. |
| Diagrams/flowcharts | Shared relationships + `teaching_request(...,"flowchart")`. | Add bounded nodes/edges diagram output schema and validate IDs/references; adapt `app/static/notes.js` renderer later. Generated relationships must be labeled conceptual enrichment, not extracted source arrows. |
| ASK | `teaching_request(...,"ask",question=...)` supports generated lesson and optional observations. | `app/services/qa/canonical_answer.py:generate_canonical_answer` remains source-bound. Add educational-content answer branch with no fabricated citations, explicit enriched/source-supported distinction and safe response DTO. Never pass synthetic evidence to validate_proposal. |
| Assessment | `teaching_request(...,"assessment",response_schema=...)` supplies concepts/explanation/equations independently of a hierarchy. | `app/services/assessment/session_assessment.py:SessionAssessmentService.start` and generator still require canonical selected concepts/EvidenceBundle. Add generated-lesson assessment DTO/storage keyed to real authenticated lesson identity; validate four distinct options/correct index/answer hiding; reuse scoring. Topic-only assessments cannot fake source IDs to use existing schema. No lesson MCQ route or key persistence implemented. |
| Video | `teaching_request(...,"video_plan",response_schema=...)` supplies educational planning input. | `app/services/video/session_video.py:SessionVideo.prepare` is tied to canonical remediation jobs. Add an educational-lesson plan adapter to existing VideoPlan, validate render inputs, use legitimate lesson/job identity, retain path/media/answer safety. Do not fake VideoTarget source_id or write topic-only artifacts via canonical remediation RPC. Existing canonical renderer unchanged. |
| LearningSession | EducationalContent UUID + verified user identity available; source scope optional. | `app/services/learning_session.py` current sessions require owned READY topic/subtopic selections. Add distinct generated-lesson/session contract and persistence only under separately approved database work, or explicitly keep temporary response-only mode. Never treat response UUID as authorized existing session. |
| Mastery / remediation / roadmap | Existing canonical services preserved; lesson key concepts available as adapter input. | `app/services/mastery/session_learning.py` still needs persisted canonical assessment/concept lineage. Add validated generated-lesson assessment linkage and stable concept identity before feeding attempts; reuse state machine, caps and reassessment engine. No fake mastery events or generated-session roadmap acceptance claimed. |

**Remaining dependency:** complete feature execution and durable storage need these adapters. Internal input adapters are ready and tested; existing feature routes have NOT all switched to them. UI and persisted-domain design are Antigravity work, not silently claimed complete here.

## Tests and limitations

VERIFIED OFFLINE affected gate: **220 passed in4.80s**, covering educational content, sources, reasoning transport, existing canonical assessment/retrieval/Notes/session ASK and pipeline observability. A final added failed-source recovery regression was then checked with the core file: **16 passed in1.67s** (overlaps earlier gate; one additional distinct test). After the optional-job reconciliation fix, the final affected source/provider/job/core gate passed **92 tests in3.32s**; unchanged Notes/ASK/retrieval/assessment compatibility was covered by the earlier gate. These counts overlap and must not be added. No full-suite or fast-verifier run; only affected tests as requested.

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_educational_content.py tests/test_source_supabase.py tests/test_reasoning_provider.py tests/test_canonical_assessment.py tests/test_canonical_retrieval.py tests/test_grounded_notes.py tests/test_session_grounded_qa.py tests/test_pipeline_observability.py -q -p no:cacheprovider --disable-warnings
.\.venv\Scripts\python.exe -m pytest tests/test_educational_content.py -q -p no:cacheprovider --disable-warnings
```

Initial unprivileged execution failed test collection because sandbox temporary storage was inaccessible; rerun with normal isolated test storage succeeded. Initial behavior assertions found legacy tests implicitly requesting enrichment; changed them to explicit enrich=True and preserved their original substantive assertions. No tests weakened to accept fabricated evidence or false READY.

Coverage: topic-only/no-source/no-storage; default extraction without optional calls; explicit hierarchy/vector failure preserves observation use; math/provenance; all shared downstream input purposes; anonymous/forged-owner rejection; actual owned fixture hidden from second mocked repository; exact missing-version denial; malformed/forged model provenance rejection; existing source-backed compatibility; known quota terminal/no-retry/no-fallback; previously FAILED source teaching without record rewrites. Mock transports are not live RLS proof. Existing PDF/image extraction paths are reused, not newly live-accepted. No raw private provider response or secret values included.

Stop here. Antigravity should implement the documented adapters incrementally, preserve current work, run affected tests and report limitations. Do not automatically deploy, migrate, commit, push or merge.
