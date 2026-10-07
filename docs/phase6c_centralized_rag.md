# Phase 6C: canonical retrieval and grounded QA

Workspace: `C:\Users\ANVESH\Desktop\AI-VIDEO-GENERATOR`; branch `stabilization-python312`.
The initial working tree was clean. No commit, push, schema migration, Auth change,
source publication, embedding migration or Qdrant write occurred in this phase.

## Architecture and authority

`RetrievalService.retrieve(KnowledgeRepository, RetrievalRequest)` is the primary
canonical retrieval boundary. The repository is request-scoped and independently
verifies the supplied JWT through the existing Supabase runtime. Its verified UUID
creates the exact `SourceScope`; a request cannot supply an owner UUID. Normal
user Data API calls retain RLS throughout. Foreign or absent versions are rejected
before embeddings or reasoning.

KnowledgeService validates the READY map and hierarchy before selector resolution.
The service reads canonical ContentUnits and the exact source version's sanitization
records, verifies their scope/text/eligibility, and regenerates educational chunks
from the immutable READY snapshot, pinned chunk policy and canonical file hash.
This regeneration is in memory; it never invokes understanding, publishes a snapshot
or changes the index. The regenerated manifest is the authority for chunk identity,
content IDs, canonical spans, hierarchy, associations and policy metadata.

Qdrant supplies candidates only. Search requires the verified owner, source,
display and integer versions, Layer A, sanitized/retrieval-allowed status,
educational-chunks-v1 policy and exact embedding space. There are no optional
owner/version filters or `student_default` alternatives. Existing accepted storage
uses the existing Qdrant client configuration; no collection is created here.

Every candidate is compared with its regenerated point/chunk identity and manifest
metadata. Stale pointers, association changes, provenance mismatches and invalid
spans are rejected. Payload text is never used as evidence; even tampered payload
text cannot replace canonical excerpts. Sanitization eligibility is independently
checked against canonical source-version records.

## Contracts and selectors

RetrievalRequest is strict, frozen and forbids unknown fields. It requires source_id,
integer source_version and bounded query. Optional fields are topic_id, subtopic_id,
concept_ids, content_ids, bounded purpose, max_items, include_prerequisites and
semantic/exact retrieval_mode. Purposes are qa, notes, assessment, video, roadmap,
remediation and agent; this does not enable those feature APIs.

Topic, subtopic and concept selectors are intersections. A mismatched parent,
foreign selector or unknown content reference receives the same safe not-found
boundary. Empty selector sets produce insufficient evidence without broadening.
Prerequisites expand through validated canonical relationships, remain inside
explicit hierarchy selectors and the exact source version, and have a named
32-concept expansion ceiling.

Exact mode requires a selector or content reference and uses canonical associations
directly. It does not embed or search, and scores/provenance are null. Semantic
outages never switch to exact mode.

## Evidence, budgets and citations

EvidenceItems contain deterministic scope/span-bound evidence IDs, canonical
content/chunk identities, source/version, hierarchy, excerpt and character bounds,
location metadata, role, semantic ranking score and validated embedding provenance.
They contain no arbitrary provenance, vectors, credentials or prompts.

EvidenceBundles contain a unique request/bundle ID, verified scope, purpose/query,
resolved selectors, ordered items, manifest digest, outcome, bounded rejection
categories, token accounting and stage timings. Semantic bundles also expose the
owned exact-version compatible index count, useful for restart/duplicate checks.

Ranking combines semantic score with deterministic concept coverage, followed by
duplicate/overlap collapse and budgets. A score is never a factual confidence.
The existing cl100k tokenizer measures excerpts. Named EvidenceBudget defaults are
3000 total and 800 per item, with caps 8000 and 2000. Request max_items defaults to
5 and caps at 20. Candidate search caps at 80. These are safety/recall choices,
not calibrated educational-quality thresholds. Semantic minimum score is 0.35.
Budget truncation preserves contiguous canonical character ranges, though it can
end mid-sentence; future evaluation may justify sentence-aware clipping.

Citations use canonical page/slide/time/section/heading metadata, with a stable
content sequence fallback where no richer location exists. QA citations carry
the real chunk ID plus evidence ID, content ID, exact version and human location.
Models cannot specify page numbers or location strings.

## QA integration and validation

The existing `/qa/answer` and grounded-answer entry point dispatch to the canonical
branch in Supabase mode; explicit file/local mode retains legacy QA compatibility.
Supabase requests use `question` as the query field and require integer version.
`POST /qa/evidence` exposes the same authenticated RetrievalService for bounded
selector/exact-evidence acceptance. Trace-history endpoints remain guarded.

Only bounded verified evidence IDs/text enter the backend reasoning router with
task `qa`. Cloudflare remains primary. Existing infrastructure-only retry/fallback
policy, hard Auth/configuration rejection, circuit and Worker-secret handling are
unchanged. There is no browser Worker call or extra reranker.

The answer DTO contains refusal and supported claims with evidence IDs. This
phase deliberately uses **extractive claims**: each accepted claim must be an
exact contiguous quote in every cited EvidenceItem. This gives a deterministic
support gate instead of pretending lexical overlap proves arbitrary paraphrase
entailment. Unknown IDs, unsupported claims, invented fields/citations and existing
injection-reflection patterns are rejected. The existing answer validator remains
an additional barrier; its legacy permissive citation fallback cannot authorize a
canonical claim. One semantic repair is permitted; then a safe refusal follows.
The generation output limit is a named 512 tokens.

Evidence/question text is explicitly untrusted data. The model has no database
tools, ownership authority, scope expansion, readiness or mastery controls.
QAResponse's legacy confidence is left at zero; vector score is not substituted
for factual confidence. Clients should use verified citations/diagnostics.

## Failure and trace behavior

- Missing/foreign scope or selector: safe 404 before inference.
- Anonymous or invalid authentication: 401.
- Invalid request contract: 422; unready canonical knowledge: 409.
- No valid candidate/exact association: INSUFFICIENT_EVIDENCE.
- Index or semantic provider unavailable: explicit retryable 503, never empty success.
- Insufficient evidence: the uploaded material does not provide enough evidence
  to answer reliably; no reasoning call is made.
- Failed answer validation after one repair: grounded refusal, no fabricated answer.

Safe structured logs and a request-local ContextVar record bundle/manifest IDs,
counts, rejection categories, timings, provider usage and validation outcome.
No canonical-mode local answer trace persistence is enabled. Prompts, evidence
text, JWTs, Worker secrets, raw vectors and model reasoning are excluded. There is
no cross-user or evidence cache. Canonical map reads are currently repeated during
resolution/manifest construction; reducing redundant request-local network reads
is a future performance improvement, not a reason to relax verification.

## Live acceptance and measurements

Only existing `SRC_bdfe5e0faf7851159e3c83dbf22b69e2`, version 1, was used.
Normal dedicated test identities authenticated through Supabase Auth. The source
and knowledge remained READY with 2 topics, 2 subtopics, 4 concepts, 5 associations
and 4 indexed educational points. The pre-restart Qdrant ID/payload digest matched
the Phase 6B.1 receipt exactly. No point was inserted, deleted or re-embedded.

Real Ollama embeddinggemma supplied semantic version-1 768-dimensional query
vectors. Real Qdrant, normal-user canonical Data API hydration and Cloudflare
generation produced a verified osmosis answer/citation. Actual Worker model was
`@cf/qwen/qwen3-30b-a3b-fp8`. The unsupported capital-of-France question yielded
INSUFFICIENT_EVIDENCE with zero reasoning events. Algebra/Biology topic filters,
an answerable subtopic query and the Osmosis concept filter passed. The initial
generic subtopic query returned no qualifying semantic evidence; its empty result
was not accepted as a positive filter test. Foreign/anonymous QA returned 404/401.

| Measurement | Warm successful QA |
|---|---:|
| Canonical hydration/manifest preparation | 3.696 s |
| Semantic search including embedding | 2.059 s |
| Query embedding | 2.054 s |
| Retrieval total | 5.755 s |
| Cloudflare Worker latency | 2.535 s |
| Cloudflare transport | 3.281 s |
| QA total | 9.052 s |
| Prompt / completion tokens | 353 / 263 |
| Reported neurons | 9.647343 |

Cold standalone retrieval took 11.601 s initially and 10.464 s on the repeated
acceptance run; the latter included 4.105 s hydration and 6.359 s search, of which
2.095 s was embedding. Existing client startup/local endpoint probing contributes
to cold latency. The 1-second retrieval target was not met. Warm QA met the
12-second target; **post-restart cold QA took 14.505 s**, so latency is not uniformly
within target. Neurons are successful-envelope reported usage, not billed dollars
or total account usage. There were three real QA reasoning calls across the two
pre-restart acceptance runs and one post-restart run; no live fallback was forced.

VisualAI was restarted exactly once. Real HTTP owner QA/citations, foreign denial,
Biology-filtered evidence and owned index count 4 passed afterwards. Canonical
snapshot hash and operation receipt remained unchanged, with no duplicate points.
Migration history still contains canonical_knowledge_snapshot exactly once, and
the local migration SHA remains
`15f6871070288d1d0fc180cd7aa433a58985f88d60a4f2330810ed125f6b2e21`.

## Verification and remaining work

New retrieval tests use explicit repository/Qdrant/provider doubles for stale
pointers, provenance, spans, synthetic embedding rejection, ownership filters,
empty selectors, exact mode, budgets, overlap collapse, deterministic citations,
restart equivalence, prerequisites, outage-without-generation and one bounded
repair. Existing suites exercise actual isolated PostgreSQL migrations/RPC/RLS;
these are distinguished from live remote Data API evidence. Frontend Auth has
14 passing Node tests. The final full suite passed **915 tests**, with one optional
real-model E2E skip and four existing warnings (dashboard operation IDs, the
unregistered e2e marker and audioop deprecation). The first full run exposed one
obsolete direct endpoint invocation; it now exercises the HTTP request boundary.
New retrieval tests passed 29/29, targeted canonical/QA/provider/PostgreSQL suites
passed 371 tests before the final five test additions, and git diff --check passed.
Actual local secret values were absent from every changed file; .env remains ignored.

Notes, assessment, video, roadmap, remediation and agent domains retain their
Phase 6A.1 guards. Future migration must explicitly supply verified context and
exact scope, consume EvidenceBundles and enforce purpose-specific validation;
it must not call raw Qdrant or use legacy file graphs for canonical authority.
Remaining limitations are network/cold embedding latency, extractive rather than
free-form teaching answers, a fixed initial semantic threshold, per-request
manifest regeneration, conservative selector clipping and no canonical trace
storage. Larger-source quality/coverage and latency require later evaluation.
