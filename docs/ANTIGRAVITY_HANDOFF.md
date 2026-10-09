# VisualAI — Antigravity development handoff

Prepared 2026-10-09. Use the SAME repository: `C:\Users\ANVESH\Desktop\AI-VIDEO-GENERATOR`, branch `phase10-mastery-remediation`. Preserve all existing uncommitted work. This is documentation only; no Phase 1 implementation, live inference, remote mutation or deployment occurred.

Evidence labels: **VERIFIED CURRENT IMPLEMENTATION** = inspected repository code and explicitly identified Phase 0 tests; **HISTORICAL FAILURE EVIDENCE** = prior reports/artifacts, not fresh acceptance; **APPROVED FUTURE IMPLEMENTATION** = Phase 1–7 work below, not completed. Tables retain INSPECTED, HISTORICAL and TARGET shorthand for these distinctions.

## A. Project purpose — authoritative PS wording

Source: the full PS text supplied directly by the user in this conversation. Its wording is reproduced below; only list layout was normalized. The original uploaded PS file could not be located/read in the available text attachments; no unseen original-document text or formatting is reconstructed. No content is missing from the supplied Problem Description, five objectives or seven requirements.

### Problem Description

Students often struggle to understand complex concepts using traditional textbooks, static videos, and generic learning materials. Existing e-learning platforms primarily provide content delivery but lack intelligent content understanding, personalized learning guidance, interactive visual explanations, and adaptive assessments. As a result, students spend significant time searching for reliable resources while receiving the same learning experience regardless of their individual strengths and weaknesses. Develop an AI-Powered Intelligent Visual Learning Platform that utilizes Generative AI, Retrieval-Augmented Generation (RAG), Computer Vision, and Agentic AI to automatically understand educational content, generate animated visual lessons, provide trustworthy AI-based learning assistance, create personalized learning roadmaps, and deliver adaptive assessments. The platform should improve conceptual understanding through interactive visual learning while providing an intelligent, personalized, and engaging educational experience.

### Key Objectives & Scope

1. Develop an AI-powered platform capable of understanding and explaining educational content.
2. Generate personalized visual learning resources using Generative AI.
3. Provide reliable, source-backed learning assistance through RAG.
4. Create adaptive learning roadmaps and AI-generated assessments.
5. Enable students to learn from multiple content formats including text, PDFs, images, and handwritten notes.

### Online Round Requirements — seven requirements supplied by the user

1. AI Content Understanding Automatically analyze textbooks, PDFs, notes, and educational content to identify key concepts, summarize topics, and generate simplified explanations.
2. AI Animated Video Generator Generate short educational animated videos from textual content using AI-generated visuals, diagrams, scene transitions, and concept-based animations.
3. AI Narration & Synchronization Generate natural voice narration synchronized with AI-created animations and visual elements to produce engaging educational videos.
4. AI-Based Assessment Generation & Verification Automatically generate quizzes, MCQs, descriptive questions, and evaluate student responses with AI-powered feedback and scoring.
5. RAG-Based Learning Assistant Retrieve information from trusted educational resources to provide accurate, context-aware answers with source citations and minimal hallucination.
6. Personalized Roadmap Generator Generate adaptive study plans and learning paths based on student goals, completed topics, assessment performance, and identified knowledge gaps.
7. Computer Vision Module Process textbook pages, handwritten notes, diagrams, graphs, and images to extract educational content, explain concepts, and generate interactive study material.

README is historical background; its references to Qdrant as authoritative ground truth and video as only a blueprint do not accurately describe all current canonical paths.

## B. VERIFIED CURRENT IMPLEMENTATION — inspected

Paths below are relative to the repository root above. Entry wiring: `app/main.py`. Canonical mode is distinct from the still-present legacy local pipeline.

| Subsystem | Production entry and dependency flow | Durable authority / limiting boundary |
|---|---|---|
| Upload/jobs | `api/pipeline.py:create_upload_job` → MIME/size + `file_truth.inspect_upload` → authenticated `api/source_jobs.py:queue_source_job` → `ingestion/source_ingestion.ingest_source` | Supabase source dependency selects source-only canonical branch; legacy upload-and-assess body is not this branch. FastAPI BackgroundTasks, in-memory JobManager; status polling and SSE are process-local. |
| TXT | `dispatcher.dispatch` → UTF-8 paragraph ContentUnits → normalizer → content sanitizer | Original upload/hash retained; canonical sanitized evidence and exact owner/version committed before knowledge. Native marked outlines recognized by `outline_evidence`. |
| PDF | `extractor.extract_from_pdf` → PyMuPDF text blocks; actual embedded images/scanned pages → `visual_content_unit` | Native text can anchor literal claims in the exact page/region. Blank pages skipped. Up to 25 visual inputs; one failed visual input can abort the whole PDF, even with valid native text. |
| Images/vision | `visual_evidence.visual_content_units` → conservative stacked-panel splitter → `visual_content_unit` → `visual_router.VisualModelRouter.extract` → cloud response envelope/visual-v2 validation | Decode, byte/pixel/animation bounds; scoped cache/provider provenance; shared deadline. Panel pool up to 3; extraction semaphore 2. |
| Visual correctness | `visual_content_unit` → remove known chrome → `configured_visual_verifier` → `VisualEvidenceVerifier.verify` → native anchors or independent visual review → optional `verified_subset` → formatted ContentUnit | No schema-only acceptance. Mismatched pixel/page anchors and model self-anchors reject. Unresolved claims require independent review. Only retained VERIFIED claims publish; tables/graphs atomic. |
| Structuring | `prepare_knowledge_index` → persisted envelopes + sanitization equality → `content_understanding.understand_content` → verified inventory/outline/anchors → `structurer.generate_educational_proposal` → bind/retain/validate → snapshot chunk validation | At most 2 proposals (initial + repair), finite visual title/name vocabulary plus server membership check. Requires publishable hierarchy, literal supported labels/definitions, explicit containment/prerequisites, unique IDs and DAG. |
| Canonical persistence | source repository immutable source/version RPC → `KnowledgeService.commit_snapshot` → knowledge repository → `visualai_commit_knowledge_snapshot` under normal owner JWT | Supabase canonical application/domain authority. Transactional operation/hash and exact version checks; READY retries reuse knowledge. No file fallback. |
| Index/retrieval | accepted knowledge → `create_educational_chunks` → source indexing/Qdrant count check → source READY. `RetrievalService.retrieve` → canonical scope/map/chunk manifest → semantic candidates or exact canonical selection → evidence bundle | Qdrant remains semantic candidate index. Payloads never authorize evidence; hashes, embedding provenance, scope, canonical offsets and citations rechecked. Exact retrieval bypasses vector search, not canonical authorization. |
| Session/explorer | source/version knowledge route → `LearningSessionService` + `LearningSessionRepository` → selection/mutation RPC | Stored owner/version/topic/subtopic/concept selection authoritative; current map must be READY. Exact selected IDs rechecked; no automatic broadening. |
| Notes | `POST /learning-sessions/{id}/notes` → `GroundedNotesService.generate` → session resolution → RetrievalService → reasoning router → `validate_notes` | One proposal; literal claims/citations and explicit diagram edges checked. Invalid proposal fails entire notes response; no repair. Deterministic frontend diagram rendering. |
| ASK | `POST /qa/answer` → session-grounded request → `generate_canonical_answer` → RetrievalService → reasoning router → `validate_proposal` / answer injection validator | Up to 2 proposals; exact quote claims; safe insufficient/partial/refusal DTO. History is bounded context, not evidence authority. |
| Assessment | session assessment route → `SessionAssessmentService.start` → exact RetrievalService → planner → deterministic verified-visual cloze where applicable, otherwise `generate_canonical_questions` → `validate_canonical_question` → Supabase repository | Deterministic cloze requires label/cue and suitable distractors; otherwise one structured proposal. Canonical validator requires exact completion stem/quote, four unique choices, no answer leak, one supported correct choice and no duplicate. SafeQuestion strips answers. |
| Evaluation | session submit → owned assessment + stored selection → `grade_canonical_submission` → atomic repository submit/result | Deterministic grading; idempotency/conflicting resubmissions enforced; no LLM judging or approval agent. |
| Mastery/remediation | mastery finalize → `SessionLearningService` → state machine + grounded gap/remediation plan + exact RetrievalService → `visualai_learning_transaction` | Backend-only privileged RPC receives verified user UUID, rechecks saved scope and revisions. Threshold/streak and kill-switch rules; NEEDS_SUPPORT exposed in mastery response. Reassessment reuses SessionAssessmentService. |
| Video | session remediation video route → `SessionVideo.prepare` → grounded quote-only plan + scene validator → durable claim RPC → background `render_session_video` → existing engine → TTS → audio probe → Whisper alignment → Manim → FFmpeg → final media validation | Normal verified user boundary, privileged scoped video RPC, restricted local media path. Canonical branch explicitly excludes legacy fixed-v1 Layer B vector/artifact writes. Render deadline 300s; media remains filesystem-dependent. |
| Roadmap | canonical mastery response projects eligible remediation/reassessment/support states; legacy `/learning` roadmap → application/personalization service | Legacy `/learning`, assessment, video and instructor routers are authenticated then rejected with 409 in Supabase mode. Worker task `roadmap` alone does not imply a canonical roadmap API/generation caller. |
| Frontend | `/learn` → auth.js/notes.js/practice.js/learning.js + CSS → protected fetch → `/pipeline/jobs/{id}` polling every 2s; API also offers `/events` SSE | Learner upload currently uses polling, not SSE. Notes/ASK clear when scope changes; practice polls video status. Restart loses job registry despite durable source/video state. |

Entry functions additionally verified: `app/api/landing.py:get_landing_page`, `get_signup_page`, `get_login_page`, `browser_auth_script`; `app/api/dashboard.py:dashboard`; `app/api/learner.py:learning_page`, `learning_script`, `learning_style`, `notes_script`, `practice_script`. Canonical learner shell is `/learn`; landing/login/signup and `/dashboard` coexist. Do not assume legacy dashboard buttons imply canonical backend availability.

Authentication: `app/services/security/auth.py:get_current_user` calls `app/core/supabase.py:SupabaseRuntime.verify_user` and `ensure_profile`. Supabase Auth verifies the bearer through its user endpoint, then local issuer/audience/expiry/UUID checks bind the identity. Profile creation is caller-scoped; backend keys stay private. Database factories in `app/services/repositories/factory.py` reject missing canonical context and do not switch to files on Supabase failure.

## C. Real execution call graphs

1. `app/api/pipeline.py:create_upload_job` → `app/services/file_truth.py:inspect_upload` → `app/api/source_jobs.py:queue_source_job` / `execute_source_job` → `app/services/ingestion/source_ingestion.py:ingest_source` → `app/services/dispatcher.py:dispatch` → TXT paragraph extraction / `app/services/extractor.py:extract_from_pdf` / `app/services/visual_evidence.py:visual_content_units` → visual-v2 validation + verification where visual → `app/services/ingestion/normalizer.py:normalize_content_units` → `app/services/security/content_sanitizer.py:sanitize_content_records` → source/version persistence → `index_committed_source` → `app/services/ingestion/knowledge_publication.py:prepare_knowledge_index` → `app/services/content_understanding.py:understand_content` → `app/services/knowledge_service.py:KnowledgeService.commit_snapshot` → canonical chunks → Qdrant index/count → source READY.
2. Source/version + stored LearningSession → `app/services/learning_session.py:LearningSessionService.qa_request` (ASK) or Notes session resolution → `app/services/retrieval.py:RetrievalService.retrieve` → canonical manifest and exact selection or vector candidates rehydrated from Supabase → `app/services/qa/canonical_answer.py:generate_canonical_answer` / `app/services/grounded_notes.py:GroundedNotesService.generate` → literal claim/citation validation → learner response.
3. `app/services/assessment/session_assessment.py:SessionAssessmentService.start` → exact retrieval/planner → `app/services/assessment/generator.py:verified_visual_cloze_questions` or `generate_canonical_questions` → validator → persisted assessment → SafeQuestion → `SessionAssessmentService.submit` → `app/services/assessment/engine.py:grade_canonical_submission` → atomic result → `app/services/mastery/session_learning.py:SessionLearningService.finalize`.
4. `SessionLearningService.finalize` → `app/services/mastery/state_machine.py:MasteryStateMachine` → evidence-grounded remediation job → `app/services/video/session_video.py:SessionVideo.prepare` → `render_session_video` → `app/services/video/engine.py:execute_video_generation_job` → TTS/audio probe/Whisper/Manim/FFmpeg/media validation → durable status → `SessionLearningService.complete` → `SessionLearningService.reassess` → SAME `SessionAssessmentService.start` → scoring/finalize. Video is conditional; when started, completion checks require it to complete. Kill switch exposes NEEDS_SUPPORT.
5. `app/static/auth.js` protected fetch → `app/static/learning.js` upload → job ID → poll `/pipeline/jobs/{job_id}` every 2s → safe stage/failure DTO → load owned source/version knowledge → select/create session → `app/static/notes.js` / `app/static/practice.js`. `app/services/pipeline_tracker.py:JobManager` also provides API SSE events; learner upload uses polling. Background status is in-memory, source/video records durable.

## D. Implementation status and acceptance evidence

| Capability | Evidence and limit |
|---|---|
| Auth, owner/version source access, RLS, accepted-source retrieval | INSPECTED + historical live API/isolation acceptance. No fresh remote acceptance in this addendum. |
| TXT/PDF/image/native outline and visual inventory | INSPECTED; Phase 0 deterministic anchor/inventory tests 52 passed. Not universal image accuracy. |
| Existing dense verified image learner loop | HISTORICAL: accepted 2 topics/2 subtopics/45 concepts; ASK citations, Notes, three MCQs, scoring/mastery/remediation/video/reassessment API accepted. |
| Browser/UI | HISTORICAL API/DOM and asset-resolution checks; earlier user-approved helper layout. No current pixel-render or Antigravity browser acceptance claimed. |
| Last closed-vocabulary structuring fix | Offline tested only; the failing source was not retried after that final fix. Live knowledge-structuring release gate remains FAIL. |
| Animated video | Existing quote-based scene rendering + spoken audio pipeline; historical H264/AAC 4-second artifact. Arbitrary generated concept animation quality/synchronization is not fully accepted. |
| Adaptive assessment | Canonical grounded MCQs + deterministic scoring exist. Descriptive-question scoring and broader AI feedback required by challenge are unconfirmed/missing on canonical paths. |
| Roadmap | Canonical mastery/remediation state projection exists. Goal-aware adaptive roadmap generation/API is not established; legacy roadmap endpoint is blocked in Supabase mode. |
| AI_ENRICHED/progressive generation | TARGET distinction below; no implemented mode contract or progressive learner-content generation claimed. Current streaming is job progress. |
| Human fallback | NEEDS_SUPPORT surfaced; canonical instructor intervention route is not established. |
| Existing-source RAG | Implemented for owned canonical sources. No public internet/trusted-resource crawler or new search integration. |

Historical accepted Phase5–10 release: Python 1159 passed/137 skipped; Worker80 passed. Later learner-loop ledger: full Python1279 passed/137 skipped/1 failed (obsolete single-concept expectation), then targeted fix; no subsequent full rerun claimed. Latest structuring closure: targeted285 passed/43 skipped, new matrix44 passed, fast verifierPASS; live release gateFAIL, final closed-vocabulary fix offline only. These are reports, not executions in Phase 0.

Executed Phase 0: `.venv\Scripts\python.exe -m pytest tests/test_verified_inventory.py tests/test_evidence_anchors.py -q -p no:cacheprovider --disable-warnings`, with PYTHONDONTWRITEBYTECODE=1. **52 passed in3.14s**. Inspected conftest: dotenv disabled, private credentials stripped, isolated temporary storage, mock model/embedding defaults. No full suite, benchmarks, live inference, Worker tests/deployment or network acceptance rerun. No need to run broad verify_changed selection merely to baseline a read-only report.

## E. HISTORICAL FAILURE EVIDENCE and inspected critical-path risks

Read ledgers: `docs/AUTONOMOUS_LEARNER_LOOP_PROGRESS.md` and `docs/KNOWLEDGE_STRUCTURING_CLOSURE.md`.

Known source `SRC_ad3e1c3e2ba85259ac5346396fc80abe` v1 / job `JOB_16cff9ede6d2`: ledger records verified visual extraction, successful initial and repair cloud calls, rejected label and no knowledge publication. One later retry also failed before the final vocabulary fix. Current inspected code now includes whole-claim anchors, verified inventory, request-local schema override and server closed-vocabulary validation. Thus the old failure is not asserted as a fresh test of current code. Historical post-restart state: source FAILED; knowledge LEGACY_UNMAPPED; zero published knowledge and vectors. No live read/retry/inference performed in Phase 0; current remote row state unverified.

- Extraction VERIFIED and knowledge READY are different contracts. Mandatory structuring currently prevents verified evidence being usable in sessions until a complete acceptable map exists.
- Knowledge commit precedes indexing; knowledge READY with source FAILED can mean index failure, not failed evidence. Conversely failed structuring can leave durable source units with LEGACY_UNMAPPED knowledge. Learner retry UI keyed only to knowledge FAILED can miss this case; inspect both source and knowledge state in Phase 1.
- Immutable source RPC requires nonempty bootstrap chunks; source ingestion creates those before hierarchy. Derived accepted chunks replace their retrieval role. Preserve original evidence and version hashes when simplifying.
- Rebuild is explicit append/preserve + CAS, not normal retry. Staged vectors before CAS can leave unreferenced orphans. Do not auto-rebuild or replace accepted READY snapshots.
- Canonical video uses backend secret RPC; public generated-video reads are revoked by latest migration. Preserve backend user revalidation and response/path sanitization. Canonical engine correctly skips legacy fixed-v1 Layer B indexing; do not accidentally reconnect it.
- Learning-session selection/revision and selected concept IDs are revalidated. Changing a map under an existing session can invalidate the session; preserving historical IDs matters.
- Canonical roadmap/human instructor action is not equivalent to legacy route availability: legacy APIs return 409 in Supabase mode. NEEDS_SUPPORT is visible, but legacy instructor override is not a usable canonical endpoint.
- No Phase 0 database schema/API response changes. Remote actual schema, RLS and deployment are historical evidence, not re-audited guarantees.

Local migration inventory (9 SQL files, all privately hash-recorded): original `001_supabase_initial_schema.sql` draft; corrected foundation; source current-version index; source ingestion transaction; canonical knowledge snapshot; focused sessions; session assessments; session mastery; untracked learner-loop rebuild/video. Two migration directories coexist.

Historical remote order from ledger: corrected foundation `20261005190025`; current-version index `20261006142045`; ingestion `20261006142056`; knowledge `20261007062312`; focused sessions `20261007113613`; Phase9 assessments `20261008152124`; Phase10 mastery `20261008152710`; learner-loop rebuild/video `20261009014311`. Local timestamps differ, especially untracked `20261008200654_learner_loop_rebuild_and_video.sql`; bulk push risks duplicate application. Original draft is not proof of deployment. Canonical snapshot local SHA256 remains `15f6871070288d1d0fc180cd7aa433a58985f88d60a4f2330810ed125f6b2e21`. No remote migration operation performed.

- Code defaults: vision Cloudflare; independent verifier defaults none but private configuration selects Cloudflare. `get_visual_router()` uses local fallback disabled by default; a local model setting does not enable production cloud→local vision fallback. Explicit Ollama vision mode is separate. Text reasoning uses Cloudflare primary with retryable-failure fallback to Ollama; auth/config/invalid-response rejection does not silently fallback.
- Worker local text map: Llama 3.3 70B for understanding/repair/assessment_structured; Qwen3 30B for reasoning/qa/notes/roadmap. Vision chains: Gemma printed/diagram; Gemma→Qwen flowchart; Qwen→Gemma handwriting/table/equation; Qwen graph/complex. No deployment parity recheck in Phase 0. Last ledger records speedrun2 authenticated success, not an unresolved current auth failure.
- Structuring up to 2 proposals, ASK up to 2; each text proposal can entail up to 2 cloud transports +1 local fallback under router policy. Notes/canonical generated assessment one proposal each. Visual router bounded up to 2 cloud candidates and optional explicit local fallback; independent review adds batches per panel. PDF up to 25 visual inputs; image splitter up to 8 panels. Do not advertise a single global LLM-call cap by multiplying only one layer.
- Defaults: image 8MiB/16M pixels; visual transport 2MiB/2048px; visual response 256KiB; extraction semaphore2; vision stage90s, extraction stage100s; cloud text read45s/overall60s; Ollama timeout120s; video deadline300s. Constants and thresholds are scattered across config, routers, subset, region, assessment and video modules: structural configuration smell, not changed here.
- Blocking dependencies: Supabase Auth/profile/Data API, local original-file storage, cloud credentials/model availability, local Ollama embeddinggemma (768D), Qdrant for semantic indexing/search; video additionally spoken TTS network/provider, Whisper weights/runtime, Manim, FFmpeg/ffprobe and local artifacts. Exact retrieval avoids embedding/vector search after canonical readiness but source READY still depends on initial indexing.
- Job admission/semaphores/dedup/cache/circuit state are in process. `to_thread` cancellation does not kill underlying synchronous work. API source worker reconciles durable source state after errors; process restart loses job/SSE registry. Video claims are durable but current implementation has no fenced crash recovery or automatic FAILED rerender path.

Excessive repair is a measured architectural risk from nested proposal retries and provider transports, not an assertion of an unbounded loop. Structure/ASK repair caps are two proposals; independent image review can add many bounded calls. Do not fix one source by broadening accepted vocabulary to unsupported claims. Optional explanation/diagram/subtitle quality should not invalidate otherwise valid evidence without an explicit product contract.

## F. Validator decisions — recommendations for future work, not changes already applied

Classification: **S** essential security/integrity; **C** source-claim correctness; **T** optional teaching quality; **B** potentially redundant/improperly blocking policy. B is a Phase 1 review candidate, not permission to remove S/C checks.

| Gate and actual caller | Class | Can block valid extracted material / assessment |
|---|---|---|
| Supabase `/auth/v1/user` verifies bearer token; local issuer/audience/expiry/UUID consistency; profile provisioning; API dependencies | S | Auth/profile outage blocks access. Local claim parsing is paired with authoritative Auth verification, not standalone unsigned trust. Never authorize by student_id. |
| SourceScope, repository owner/version predicates, RLS, RPC references/CAS/idempotency; canonical source/chunk rehydration | S | Required denials and integrity checks; preserve. Backend service-role operations must keep verified identity plus DB guards. |
| Upload truth/decode/budgets, sanitizer quarantine, no-safe-content, unchanged sanitized text, ContentUnit confidence >0 | S/C/B | Correct text can be quarantined or rejected by text transformations, confidence metadata or budgets. Keep injection isolation; separate heuristic rejection from unsupported facts. |
| `vision._validate_vision_extraction`, called by router/local adapter | C/B | Refusal/provider-error regex, repeated words, filename/generic phrase heuristics, minimum four transcript words absent structural content, positive self-reported confidence, equation/transcript consistency. Literal teaching material containing “API key”, very short labels or repeated text can false-positive. Some empty/generic checks overlap. |
| VisualEvidenceVerifier, invoked once at ContentUnit boundary | C/S | Native literal anchors verify only supported claim types; structural claims still need independent review. Source scope/self-verification rejection essential. Raw arbitrary images generally need second model. Reviewer failures remain uncertainty. |
| Independent Cloudflare verifier, invoked only for unresolved claims | C/B | Different qualified model from extractor, correlated claim IDs, bounded batches. 16 claims/batch ×24 batches, 3 review slots; timeouts/capacity and excess claims become UNCERTAIN. No automatic verifier fallback. This is a source-correctness reviewer, not a teaching-quality agent. |
| `visual_publication.verified_subset`, called after non-VERIFIED result | C/B | Only independently VERIFIED claims salvageable. Minimum 2 distinct literal lines and 80 alphanumeric characters can reject a correct small equation/diagram. Tables/graphs all-or-nothing. Keep uncertainty out of publication; review minimum-size policy independently. |
| Verified inventory + anchors, called by understand_content and proposal binding | C/S/B | Canonical literal correspondence, evidence quote/role/offset checks essential. Whole-claim + sentence anchor duplication and normalization layers can disagree; missing renderer correspondence blocks even verified content. 4096-anchor bound fails whole source. |
| Hierarchy validator and retention, called by understand_content | C/B | Foreign reference/unsupported fact/DAG checks essential. Mandatory topic→subtopic→concept organization, all required visual label retention, label-role restrictions, closed vocabulary and full-proposal failure can turn valid extraction into no usable knowledge. A single bad name can fail whole publication after successful cloud inference. Closed vocabulary protects correctness but does not prove the hierarchy can be generated. |
| Snapshot preflight + KnowledgeService/RPC + chunking/retrieval revalidation | S/C/B | Several layers intentionally overlap across trust/transaction boundaries. Repeated chunk construction can be costly; do not conflate redundant computation with redundant security. Missing/oversized chunks fail. Chunk quality metrics include fragment/unassigned counts; not all reported metrics are hard gates. |
| Notes and ASK literal claim/citation validators | C/S/B | Correct paraphrases rejected by exact-quote policy; notes atomic failure vs ASK safe refusal after one repair. Diagram arrows require explicit source support. Optional diagrams can invalidate otherwise valid notes. |
| Canonical question validator/planner | S/C/T/B | Safe answer hiding and ownership essential. Exactly four options, literal cloze grammar and duplicate heuristics are teaching/presentation policies that can block valid small content. Canonical evaluator is deterministic. Legacy retry/overlap validators are not the canonical generator path. |
| Mastery thresholds/attempt limit/completion prerequisites | S/T | Keep attempt/idempotency guards. Two-success threshold and three-remediation cap are configurable teaching policy; correct one-question reassessment need not immediately master. Started video must complete before remediation completion. |
| Video scene/media validators + Whisper alignment | S/C/T/B | Media/path safety required. Alignment/subtitles, render tools and TTS availability can block a valid learning plan; review whether teaching enhancement should block a non-video remediation path. No LLM video-plan review in canonical quote-only branch. |
| Legacy extraction/ingestion `services/validator.py` quality gateway | S/C/T | Called in local upload-and-assess branch, not canonical queue_source_job path. Don’t simplify based only on this filename. `approval_status="approved"` in legacy Layer B is metadata, not an executed approval agent. |

No separate production LLM approval-agent chain was found on the canonical paths above. Actual repeated model work is extraction plus independent review, bounded structuring repair, ASK repair and provider transport retry/fallback. There is no general reviewer to delete without examining its caller and trust boundary.

Operational decision register supplements that inventory. Test files listed are existing regression protection; proposed future behavior requires additional tests before implementation.

| File/function | Caller | Decision / protection / blocking cost | Existing tests |
|---|---|---|---|
| `app/core/supabase.py:SupabaseRuntime.verify_user`, `ensure_profile`; `app/services/security/auth.py:get_current_user` | Authenticated API dependencies | KEEP verified identity/profile/RLS boundary; Auth/Data API I/O, no inference. | `tests/test_supabase_runtime.py`, `tests/test_signup_registration.py`, `tests/test_phase6a1_security.py` |
| `app/services/file_truth.py:inspect_upload`; `app/services/security/content_sanitizer.py:sanitize_content_records` | Upload/source ingestion | KEEP file truth and injection quarantine; SIMPLIFY only duplicate transformations after equality tests. Zero model calls. | `tests/test_multimodal_canonical.py`, `tests/test_source_supabase.py` |
| `app/services/vision.py:_validate_vision_extraction` | VisualModelRouter/local extractor | SIMPLIFY overlapping heuristics/minimum/self-confidence gates; KEEP bounded schema, provenance and actual evidence. Zero additional inference. | `tests/test_vision_structured_output.py`, `tests/test_extraction_quality_regression.py` |
| `app/services/visual_verifier.py:VisualEvidenceVerifier.verify` | visual_content_unit | KEEP scoped independent support; cannot promote UNCERTAIN. Deterministic portion zero calls; independent review may call provider. | `tests/test_visual_verifier.py` |
| `app/services/independent_visual_verifier.py:CloudflareIndependentVisualVerifier.verify`, `_review_batch` | VisualEvidenceVerifier | KEEP correctness and model independence; SIMPLIFY duplicate claim work only with same coverage. Up to24 batches per invocation, shared deadlines. | `tests/test_independent_visual_verifier.py` |
| `app/services/visual_publication.py:verified_subset` | visual_content_unit | SIMPLIFY arbitrary minimum-size rejection, KEEP verified-only subset/atomic structural integrity. Zero model calls. | `tests/test_tall_visual_publication.py` |
| `app/services/verified_inventory.py:verified_inventory`; `app/services/evidence_anchors.py:build_anchors`, `bind_verified_visual_labels` | understand_content | KEEP literal authority/foreign-ref rejection; SIMPLIFY repeated representation/normalization. Zero model calls. | `tests/test_verified_inventory.py`, `tests/test_evidence_anchors.py` |
| `app/services/content_understanding.py:validate_proposal`, `understand_content`; `app/services/structurer.py:generate_educational_proposal` | prepare_knowledge_index | KEEP facts/citations/DAG; SIMPLIFY whole-hierarchy bottleneck and repair dependency. Optional teaching organization should become NONBLOCKING only after a compatible readiness design. Up to2 proposals plus transport fallback. | `tests/test_content_understanding.py`, `tests/test_visual_knowledge_preparation.py`, `tests/test_outline_evidence.py` |
| `app/services/snapshot_validation.py:validate_snapshot_chunks`; `app/services/knowledge_service.py:KnowledgeService._validate`, `commit_snapshot`; `app/services/educational_chunker.py:create_educational_chunks` | understanding/publication/retrieval | KEEP trust-boundary validation; SIMPLIFY duplicated preflight computation only. No inference; DB/chunk CPU cost. | `tests/test_knowledge_repository.py`, `tests/test_canonical_retrieval.py` |
| `app/services/retrieval.py:RetrievalService.retrieve` | ASK/Notes/assessment/remediation/video | KEEP canonical evidence hydration and exact owner/version. Embedding/vector work only semantic mode. | `tests/test_canonical_retrieval.py`, `tests/test_session_grounded_qa.py` |
| `app/services/grounded_notes.py:validate_notes`; `app/services/qa/canonical_answer.py:validate_proposal`; `app/services/qa/answer_validator.py:validate_grounded_answer` | Notes/ASK generation | KEEP source claims/citations/injection protection; NONBLOCKING optional diagram/enrichment failures after explicit contract. Notes1/ASK up to2 proposals. | `tests/test_grounded_notes.py`, `tests/test_session_grounded_qa.py` |
| `app/services/assessment/validator.py:validate_canonical_question`; `app/services/assessment/session_assessment.py:SessionAssessmentService.safe`; `app/services/assessment/engine.py:grade_canonical_submission` | canonical start/submit/get | KEEP answer hiding/grading/evidence; SIMPLIFY teaching-format restrictions only with valid alternative types. Validator/grading zero inference. | `tests/test_canonical_assessment.py` |
| `app/services/mastery/state_machine.py:MasteryStateMachine`; `app/services/mastery/session_learning.py:SessionLearningService.complete`, `reassess` | mastery/remediation routes | KEEP idempotency, caps, completion/scope authority; thresholds configurable. Zero inference in state transitions; reassessment delegates generation. | `tests/test_session_mastery.py` |
| `app/services/video/scene_validator.py:validate_video_plan`; `app/services/video/video_compositor.py:validate_video_artifact` | SessionVideo/engine | KEEP path/media and source-plan integrity; NONBLOCKING optional subtitle/enrichment dependencies requires explicit separate completion semantics. No LLM in canonical quote-plan; TTS/Whisper/render cost. | `tests/test_canonical_video_engine.py` |
| `app/services/validator.py:validate_ingestion_quality` | legacy local pipeline only | KEEP while legacy path supported; REMOVE from proposed canonical simplification scope (not currently called there). No canonical benefit from deleting it. | `tests/test_multimodal_canonical.py` |
| `app/services/pipeline_tracker.py:JobManager`; source job ownership/idempotency guards | pipeline/source_jobs | KEEP ownership/dedup/cancel semantics; SIMPLIFY transient vs durable status reconciliation. Zero model calls in job manager. | `tests/test_source_supabase.py`, `tests/test_pipeline_observability.py` |

No named autonomous approval agent is executed in these canonical paths; do not invent one from approval metadata. No essential security gate is designated REMOVE. Recommendations are not authorization to bypass current acceptance gates.

## G. APPROVED FUTURE IMPLEMENTATION — architecture, not completion claims

- **SOURCE_GROUNDED**: source-backed claims with owned exact-version evidence and citations; current canonical paths approximate this behavior. No assertion that this mode enum currently exists.
- **AI_ENRICHED**: optional clearly labeled teaching examples/explanations beyond quoted source. Must not be labeled source-verified or enter canonical source evidence without support. Mode/schema/UX contract is approved future Phase 2 work; it is not implemented yet.
- **Fast progressive generation**: publish useful grounded learning outputs in bounded stages; enrichment/hierarchy quality should not hold all material hostage. Existing progress events are not progressive content publication. Keep truthful readiness states and atomic compatibility.
- **Existing-source RAG**: reuse Supabase canonical sources and RetrievalService; retain Qdrant semantic index; no internet search.
- **Short animated video**: reuse SessionVideo/engine, deterministic diagrams/scenes and spoken narration; improve concept animations within evidence scope and zero-spend constraints.
- **Agentic mastery/remediation**: reuse state machine and assessment engine, explicit eligible next action, bounded attempts and human fallback; no unnecessary agent framework.
- **Adaptive roadmap**: derive from goals, completed topics, assessment gaps and prerequisites; canonical route/goal model is a gap, not assumed complete.
- **Strict zero-spend policy**: no new paid service, upgrade or paid API call; free limits are operational blockers, not authorization to incur cost. No live inference authorized by this handoff. Local inference permitted only in a separately authorized implementation/test scope.

## H. Excluded work

No live internet search, Tavily/Brave, new paid services, replacement vector database, wholesale backend rewrite, unnecessary autonomous validator framework, automatic deployment or remote migration. No Git commit/push/stash/checkout/reset/clean/merge. No credentials, private student text or raw provider responses in documentation.

## I. APPROVED FUTURE IMPLEMENTATION — Phase 1–7

The following plan is explicitly approved by the user and replaces the earlier provisional sequence. Phase 1 is the immediate implementation task in Antigravity. None of these phases is completed by this documentation task. Execute one phase at a time and stop/report at its gate.

### Phase 1 — Project-Wide Validator Removal and Core Unblocking

- Audit actual production validation and reviewer paths.
- Remove redundant validator agents, unnecessary blocking quality checks, and repeated AI approval loops.
- Fix cascading failures that make otherwise usable educational sources unavailable.
- Preserve authentication, RLS, source-specific citation integrity, assessment correctness, and database safety.
- This is the HIGHEST implementation priority.

Dependency: secured Phase 0 baseline. Scope is PROJECT-WIDE, including visual verification/publication, hierarchy, retrieval consumers, Notes/ASK, assessments, video and job failure propagation—not only knowledge structuring. Use section F caller/decision inventory; distinguish review duplication from independently required source correctness. No current gate may be silently bypassed in Phase 0.

Likely affected modules: `app/services/vision.py`, `app/services/visual_verifier.py`, `app/services/independent_visual_verifier.py`, `app/services/visual_publication.py`, `app/services/content_understanding.py`, `app/services/verified_inventory.py`, `app/services/evidence_anchors.py`, `app/services/outline_evidence.py`, `app/services/structurer.py`, `app/services/snapshot_validation.py`, `app/services/ingestion/knowledge_publication.py`, `app/services/ingestion/source_ingestion.py`, `app/services/ingestion/failures.py`, `app/services/grounded_notes.py`, `app/services/qa/canonical_answer.py`, `app/services/assessment/validator.py`, `app/services/video/scene_validator.py`, `app/services/video/engine.py`, `app/api/source_jobs.py`, `app/services/pipeline_tracker.py`. These are inspection/change candidates, not a mandate to edit every file. API/readiness compatibility must be checked before changing publication semantics.

Tests: existing visual/inventory/anchor/structuring, grounded Notes/QA, canonical retrieval/assessment/video and pipeline suites listed in section F; add regressions for each removed blocking behavior and unchanged essential protections. Stop/go: affected deterministic tests + fast verifier, usable evidence no longer unnecessarily cascades to source failure, truthful readiness, preserved owner/version/citation/assessment/idempotency boundaries. Report exact removed/simplified gates and remaining live acceptance gaps; STOP after Phase 1. No blanket removal of correctness verification or inference/deploy/migration authorization.

### Phase 2 — AI-First Content Understanding

- Separate SOURCE_GROUNDED and AI_ENRICHED educational content.
- Allow models to generate useful explanations beyond the exact uploaded text.
- Support arbitrary topics without requiring a preloaded syllabus.
- Preserve honest source attribution and essential correctness checks.

Dependency: Phase 1 stable. Modules: `app/services/content_understanding.py`, `app/services/grounded_notes.py`, `app/services/qa/canonical_answer.py`, `app/services/learning_session.py`, `app/api/learning_sessions.py`. Tests: content understanding, grounded notes, session QA and API contracts. Gate: explicit output-mode attribution, no invented source citations, arbitrary-topic fixtures, compatible persisted evidence. Stop after Phase 2 results.

### Phase 3 — RAG, ASK, Notes and Visual Study Materials

- Maintain existing Supabase, Qdrant and RetrievalService.
- Produce source-backed answers with real citations.
- Support AI supplemental explanations without fabricated references.
- Generate usable notes, flowcharts and concept maps.

Dependency: Phase 2 attribution contracts. Modules: `app/services/retrieval.py`, `app/services/qa/canonical_answer.py`, `app/services/grounded_notes.py`, `app/services/learning_session.py`, `app/static/notes.js`, `app/static/learning.js`. Tests: canonical retrieval, session-grounded QA, grounded Notes and existing frontend tests. Gate: real owned/version-bound citations, untrusted vector data rejected, supplemental content visibly distinct, diagrams usable; no web search. Stop after Phase 3 results.

### Phase 4 — Performance and Progressive Learning

- Reduce unnecessary sequential execution and repeated model calls.
- Display the first useful explanation as quickly as practical.
- Make optional operations nonblocking.
- Preserve durable background jobs, correct statuses and restart recovery.

Dependency: stable learning output contracts from Phases 1–3. Modules: `app/api/source_jobs.py`, `app/services/pipeline_tracker.py`, `app/services/ingestion/source_ingestion.py`, `app/services/ingestion/knowledge_publication.py`, `app/services/visual_evidence.py`, `app/services/independent_visual_verifier.py`, `app/static/learning.js`. Tests: pipeline observability, ingestion/retry contracts, frontend and restart/failure tests. Gate: measured first-useful-output latency/call counts, optional failure containment, idempotency and restart recovery. Current job registry is in-memory: durable job recovery is FUTURE work, not an existing guarantee. Stop after Phase 4 results.

### Phase 5 — Animated Educational Videos and Narration

- Reuse the existing video engine.
- Develop reliable educational scene templates.
- Generate approximately 20–30-second explanatory animations.
- Synchronize narration and visuals.
- Remove redundant video-quality reviewer loops while keeping playable-media and safety checks.

Dependency: grounded/enriched content contracts and bounded job lifecycle. Modules: `app/services/video/session_video.py`, `app/services/video/engine.py`, `app/services/video/scene_validator.py`, `app/services/video/tts.py`, `app/services/video/whisper_alignment.py`, `app/services/video/manim_renderer.py`, `app/services/video/video_compositor.py`. Tests: canonical video engine and scene/media regressions. Gate: actual playable 20–30s explanatory artifact, verified duration/audio/visual sync, safety/path/source integrity; no paid APIs or automatic deployment. Stop after Phase 5 results.

### Phase 6 — Adaptive Assessments, Agentic AI and Personalized Roadmaps

- Preserve existing Phase 9/10 implementation.
- Complete assessment generation, scoring and feedback.
- Implement meaningful learning orchestration and remediation.
- Complete mastery, reassessment and visible personalized roadmaps.

Dependency: learning content, stable jobs and video interfaces. Modules: `app/services/assessment/session_assessment.py`, `app/services/assessment/generator.py`, `app/services/assessment/validator.py`, `app/services/assessment/engine.py`, `app/services/assessment/planner.py`, `app/services/mastery/session_learning.py`, `app/services/mastery/state_machine.py`, `app/services/mastery/roadmap_models.py`, `app/api/learning_sessions.py`, `app/static/practice.js`. Tests: canonical assessment/mastery/practice and route/isolation contracts. Gate: safe questions, correct scoring/feedback, bounded orchestration, useful canonical roadmap, remediation/reassessment and human fallback visible; reuse existing engines, not a rewrite. Stop after Phase 6 results.

### Phase 7 — Final Hackathon Acceptance and Main-Merge Preparation

- Verify all seven PS requirements.
- Run real learner end-to-end acceptance.
- Run targeted tests, fast verifier and full regression.
- Check performance, data integrity, security and branch differences.
- Assess readiness to merge into `main`, but do not merge automatically.

Dependency: all preceding phases accepted. Modules: existing application/API/frontend, tests, `scripts/verify_changed.py`, Worker tests and release documentation. Gate: requirement-by-requirement real evidence, one controlled final full regression, actual browser/learner-loop acceptance, explicit branch/migration/security risks; deterministic results never substitute for live acceptance. Live calls/deployments/migrations require their own authorization. Stop with merge-readiness report; no automatic merge/commit/push.

### Cross-phase architectural decisions — approved constraints

1. Remove unnecessary validators throughout the project, not only the knowledge-structuring module.
2. Preserve essential security, data-integrity, source-attribution and assessment-verification checks.
3. No live web research implementation for this MVP.
4. No new paid services.
5. Keep existing Cloudflare Workers AI, Supabase, Qdrant and video infrastructure.
6. All development remains on `phase10-mastery-remediation`.
7. Preserve every existing uncommitted modification.
8. No commits, pushes, resets, branch changes or deployments without authorization.
9. Execute one implementation phase at a time in Antigravity.
10. Never claim successful live acceptance based only on deterministic tests.

## J. Developer runtime — commands confirmed from repository, not all executed now

Use PowerShell in the exact project directory. Do not start a second backend over an existing listener; do not run `start.bat` as a read-only check (it installs dependencies, can start Docker and creates configuration).

```powershell
Set-Location -LiteralPath 'C:\Users\ANVESH\Desktop\AI-VIDEO-GENERATOR'
. .\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe run.py
# Targeted offline regression, actually executed in Phase0:
.\.venv\Scripts\python.exe -m pytest tests/test_verified_inventory.py tests/test_evidence_anchors.py -q -p no:cacheprovider --disable-warnings
# Inspect fast selection before execution:
.\.venv\Scripts\python.exe scripts/verify_changed.py --plan
.\.venv\Scripts\python.exe scripts/verify_changed.py
# Full suite is a separate phase-close gate, NOT a handoff action:
.\.venv\Scripts\python.exe -m pytest -q
```

`run.py` explicitly starts `app.main:app` at127.0.0.1:8000 and watches app/ only. Its auto-venv selection checks Unix .venv/bin/python, so use the explicit Windows interpreter above. Activate.ps1 file presence checked; invocation need not change execution policy. Worker tests are `npm test` from `cloudflare/visualai-inference-worker` (package script node --test tests/*.test.js); do not run deploy scripts.

Read-only integration health commands when server already running:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:8000/health/supabase'
Invoke-RestMethod 'http://127.0.0.1:8000/health/qdrant'
Invoke-RestMethod 'http://127.0.0.1:8000/health/inference'
Invoke-RestMethod 'http://127.0.0.1:8000/health/video'
```

These endpoints are verified in app/main.py, but not called in this handoff. Qdrant collections/health do not prove correct indexing or RLS. Supabase health does not prove cross-user isolation. No inference request is required by these checks. Avoid `/debug/qdrant`, a legacy guarded debug path.

Logs: foreground `run.py` uses terminal output. Historical launcher logs are `C:\Users\ANVESH\Documents\Codex\2026-10-06\you-are-working-on-the-visualai\learner_loop_server.out.log` and `learner_loop_server.err.log`; verify existence before `Get-Content -LiteralPath ... -Tail 100`. They may contain private diagnostics: inspect locally, do not paste unredacted logs. No canonical persistent application log path is configured by run.py; do not invent one.

## K. Git state and recovery

- Branch: `phase10-mastery-remediation`; HEAD: `d7bf07a67c39d030ae6bcfecce2b434790d84735`.
- Origin fetch/push: `https://github.com/anveshreddy294/AI-VIDEO-GENERATOR`.
- 33 tracked modified files; 14 individual untracked files; no staged changes. Tracked diff: 756 insertions, 210 deletions. Exact paths and status: `git-status.txt` alongside this document. No branch switch or Git mutation performed.
- Recovery directory: `C:\Users\ANVESH\Documents\Codex\2026-10-06\you-are-working-on-the-visualai\phase0-baseline-20261009-043746`.
- `history.bundle`: all local Git refs/history; successfully verified with `git bundle verify`. SHA256: `70EE350F06EEDD597325999DFBDBC3D235246B0A2794C5027F8B4A9CD823A256`.
- `working-files/`: 1,945 byte-preserving, individually SHA256-verified files, 330,434,509 bytes. Includes tracked/untracked work, ignored local configuration, earlier patches, uploads, processed data and generated media. `manifest.csv` records relative paths, classification, sizes and hashes, never file contents. `git-index.backup` preserves staging metadata.
- ACL inheritance disabled at snapshot root: only current Windows account and SYSTEM have full control; descendants inherit this restriction. No secrets included in this document. Private configuration remains in the restricted recovery copy.
- Excluded reproducible dependencies/caches: `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`; `.git` represented by bundle plus index, rather than copied lock/runtime files. Empty directories are not represented. No external database, remote storage or live Qdrant point-in-time backup is claimed. Running services were not paused: copied files are individually verified, not a transactional snapshot of actively changing services.
- Recovery procedure, if later needed: verify bundle and manifest; clone bundle into a NEW separate directory at the recorded HEAD; overlay `working-files` there. Review original status before reconstructing staging; index backup is recovery evidence, not an instruction to overwrite the active index. Restore private configuration only into an appropriately restricted directory. Do not publish the snapshot. No restoration performed in Phase 0.

The exact per-file inventory is in `manifest.csv` and `git-status.txt`. Tracked changes span canonical structuring/anchors, ingestion errors, session revision, notes, assessment, mastery, canonical video/TTS, learner assets, Worker normalization/diagnostics, fast-verifier selection and corresponding tests. They are broader than infrastructure-only fixes and must be preserved as a unit.

Untracked production source: `app/services/verified_inventory.py`, `app/services/ingestion/knowledge_rebuild.py`, `app/services/video/session_video.py`, `app/static/practice.js`. Untracked tooling: `scripts/rebuild_verified_knowledge.py`. Untracked tests: `test_verified_inventory.py`, `test_knowledge_rebuild.py`, `test_canonical_video_engine.py`, `test_practice_frontend.js`. Untracked ledgers: `docs/AUTONOMOUS_LEARNER_LOOP_PROGRESS.md`, `docs/KNOWLEDGE_STRUCTURING_CLOSURE.md`. Untracked migration: `supabase/migrations/20261008200654_learner_loop_rebuild_and_video.sql`. Local tooling artifacts: `.wrangler/cache/wrangler-account.json`, `supabase/.temp/cli-latest`.

No tracked configuration file changes in current status. `.env` is ignored and privately preserved; configuration values are not inferred from `.env.example`. The private file explicitly sets `DATABASE_PROVIDER=supabase`, `VISUAL_INDEPENDENT_VERIFIER=cloudflare`, `MASTERY_THRESHOLD=2`, `KILL_SWITCH_LIMIT=3`. Other inspected settings below are code defaults unless separately overridden by the running process; no claim of exact process-environment parity.

Generated/local storage inventory: 1,563 files, approximately 310.39 MiB; includes runtime registry, uploads, processed source evidence, JSON stores and rendered media. These coexist with canonical Supabase mode; their existence does not prove canonical domain reads fall back to files. Prior backup patches are preserved. Global OAuth/token stores and external private acceptance telemetry are outside this repository snapshot.

Cached remote refs only (no fetch/network): local branch is ahead1 of origin/phase10-mastery-remediation. HEAD has18 commits not in cached origin/main; cached origin/main has0 commits not in HEAD. origin/main at9cb44d0. Remote current truth is unconfirmed. Merge concerns: broad existing uncommitted learner-loop/Worker/frontend work, untracked production imports and migration, differing local/remote migration timestamps, legacy vs canonical API differences, stale README and pending live structuring acceptance. No merge attempted.

### Exact pre-handoff working-tree status

```text
 M app/api/learner.py
 M app/api/learning_sessions.py
 M app/core/model_manager.py
 M app/core/reasoning.py
 M app/services/assessment/generator.py
 M app/services/assessment/session_assessment.py
 M app/services/assessment/validator.py
 M app/services/content_understanding.py
 M app/services/evidence_anchors.py
 M app/services/grounded_notes.py
 M app/services/ingestion/failures.py
 M app/services/ingestion/source_ingestion.py
 M app/services/learning_session.py
 M app/services/mastery/session_learning.py
 M app/services/outline_evidence.py
 M app/services/repositories/source_repository.py
 M app/services/snapshot_validation.py
 M app/services/structurer.py
 M app/services/video/engine.py
 M app/services/video/tts.py
 M app/static/learning.css
 M app/static/learning.html
 M app/static/learning.js
 M cloudflare/visualai-inference-worker/src/index.js
 M cloudflare/visualai-inference-worker/src/visual.js
 M cloudflare/visualai-inference-worker/tests/diagnostics.test.js
 M scripts/verify_changed.py
 M tests/test_canonical_assessment.py
 M tests/test_grounded_notes.py
 M tests/test_learning_frontend.js
 M tests/test_multimodal_canonical.py
 M tests/test_reasoning_provider.py
 M tests/test_visual_knowledge_preparation.py
?? .wrangler/cache/wrangler-account.json
?? app/services/ingestion/knowledge_rebuild.py
?? app/services/verified_inventory.py
?? app/services/video/session_video.py
?? app/static/practice.js
?? docs/AUTONOMOUS_LEARNER_LOOP_PROGRESS.md
?? docs/KNOWLEDGE_STRUCTURING_CLOSURE.md
?? scripts/rebuild_verified_knowledge.py
?? supabase/.temp/cli-latest
?? supabase/migrations/20261008200654_learner_loop_rebuild_and_video.sql
?? tests/test_canonical_video_engine.py
?? tests/test_knowledge_rebuild.py
?? tests/test_practice_frontend.js
?? tests/test_verified_inventory.py

```

The two handoff documents are the only intended additions of this task. Final preservation/path/secret checks are recorded privately beside the recovery snapshot. No source changes, staging, commit or push.
