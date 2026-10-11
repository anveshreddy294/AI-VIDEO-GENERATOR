# Qdrant embedding compatibility repair

## Baseline (2026-10-11, before implementation)

Branch `postgre-implementation`; the only existing working-tree entry was the
untracked user file `LEARNING_PIPELINE_AUDIT.md`, which is preserved. No repository
AGENTS.md was found. The embedding/retrieval/security baseline passed 56 tests.
The preceding full verification reported 1,639 passed, 139 skipped and one
duration assertion failure; frontend 115 passed and PostgreSQL 32 passed.

The effective model is `embeddinggemma`, provider Ollama, dimension 768. The
configured collection is `visualai_layer_a` (missing). The only live collection,
`visualai_layer_a_v1`, has five points, unnamed 768-dimensional Cosine vectors,
four video scenes and one source chunk. None has verified embedding provenance.
Its initial sorted point/payload/vector SHA-256 is
`53cce31efb69d65c9688868281180a7dd856bffaa850d499678c623692d94d0f`.
Compatibility is unknown; no existing vector will be relabeled or rewritten.
The model is absent from Ollama. Docker's existing Qdrant container uses a missing
`wget`; the repository already contains a Bash TCP readiness probe.

All active source, scene-indexing, retry and retrieval callers use
`settings.collection_name`. Canonical retrieval rehydrates owned, versioned,
sanitized Supabase evidence and verifies chunk manifests. Preserve those checks,
grounded refusal, PostgreSQL persistence and completed media.

Confirmed repair defects: explicit source retry skips indexing for non-optional
READY sources; query-cache hits do not restore context-local validated model
diagnostics; collection validation checks dimension but not distance/named vectors.
The default duration is 45 seconds (VideoOptions and README intermediate contract),
while one acceptance test asserts at most 40 without requesting a duration.

## Controlled changes and rollback

1. Export the five original points including vectors/payloads to an ignored local
   backup, and create/download a Qdrant snapshot before container recreation.
2. Install the intended `embeddinggemma` model; verify real finite nonzero
   768-dimensional embeddings. Never substitute the installed nomic model.
3. Use `visualai_embeddinggemma_v2` for the intended model. Retire only the two
   generic legacy collection aliases for that model. Preserve explicit custom
   names; `SEMANTIC_COLLECTION_NAME` permits an explicit operator override.
   Keep `.env` byte-for-byte unchanged and expose requested/effective names.
4. Persist and filter preprocessing and collection identity with model provenance;
   fix context-safe query caching and validate unnamed Cosine collection contracts.
5. Make explicit source retry actually refresh its owned source in the active
   collection. Use existing authenticated APIs for a bounded source-backed test,
   not a bulk migration or administrative source impersonation.
6. Recreate only Qdrant with its same named storage volume and a working readiness
   probe. Preserve localhost API access through an explicit local Compose override.
7. Correct the acceptance test to explicitly request the documented 45-second
   budget and validate measured timing/captions, rather than changing production
   duration behavior or merely relaxing a magic upper bound.

Rollback requires no destructive database operation: stop new indexing, restore
the previous code/configuration selection and retain both collections. An operator
may explicitly select `visualai_layer_a_v1`, but its unknown-provenance records
must still fail closed. The original snapshot/point export permit independent
recovery; do not restore over a live collection without a separately approved
plan. Model installation is additive. Do not delete either collection, remove
volumes, change Supabase/PostgreSQL schemas, commit, or push.

Expected changes: configuration and environment example (safe namespace selection),
vector store/retrieval/reindex provenance (consistent embedding contracts), source
retry API/service (bounded repair), focused tests, duration acceptance test,
local Qdrant Compose override and this operational report. No renderer or
PostgreSQL changes are planned.

## Implemented changes

| File | Reason |
| --- | --- |
| `app/core/config.py` | Resolve the retired generic embeddinggemma namespaces to the isolated v2 collection; preserve custom names and expose requested/effective configuration. |
| `.env.example`, `README.md`, `docs/embedding_configuration.md` | Document the active namespace, optional explicit override, provenance and bounded source retry. |
| `app/db/vector_store.py` | Restore validated provenance on query-cache hits, isolate endpoint/model cache keys, reject mismatched model tags and non-Cosine/named collections, and share complete stored/query embedding contracts. |
| `app/db/reindex.py` | Keep the existing explicit repair tool's provenance consistent. This tool was not executed against historical data. |
| `app/services/retrieval.py` | Require collection version and preprocessing identity alongside existing canonical ownership, source-version and manifest validation. |
| `app/services/ingestion/source_ingestion.py` | Allow an explicit READY-source refresh without downgrading canonical readiness when indexing fails. |
| `app/api/sources.py` | Use forced refresh in the existing retry endpoint; optionally reject a stale source version before writes. |
| `app/static/analysis-results.js`, `app/static/learning.js` | Expose a version-bound Prepare source search action on owned READY source cards. |
| `app/main.py` | Report the active collection and its existence in existing Qdrant health diagnostics. |
| `docker-compose.local.yml` | Preserve local API access with a loopback-only port when merging with the base Compose configuration. The base file already had the supported readiness probe. |
| `tests/test_embedding_repair.py` | Cover namespace selection, cache provenance/endpoint isolation, incompatible collection preservation and exact model tags. |
| `tests/test_canonical_retrieval.py`, `tests/test_source_supabase.py` | Cover provenance tampering, forced retries, stale versions and preservation of READY content after retry failure. |
| `tests/test_vector_reindex.py` | Explicitly bind the isolated test collection for namespace provenance. |
| `tests/test_resource_exports.js` | Verify the owned READY source action passes its exact version. |
| `tests/test_acceptance_journeys.py` | Explicitly request the documented 45-second target and validate measured video/caption timing rather than an unsupported 40-second ceiling. |
| `docs/qdrant-embedding-repair.md` | Record baseline, operational actions, validation and limitations. |

No production renderer, caption generator, PostgreSQL/Supabase schema, authentication
boundary or regeneration implementation was changed. No agent infrastructure was
added. The existing user audit file is untouched; no commit or push was performed.

## Actual operational actions

- Installed the intended model using `ollama pull embeddinggemma`.
  Installed `embeddinggemma:latest` digest:
  `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`.
- Real document and query embeddings were finite, nonzero and 768-dimensional.
  A force/mass query had cosine similarity 0.72557 to related physics text versus
  0.25326 to unrelated photosynthesis text. No model substitution was used.
- Exported all five legacy points, including their vectors and payloads, to
  `storage/runtime/backups/qdrant-20261011-embedding-repair/visualai_layer_a_v1.points.json`.
  Downloaded the pre-change snapshot to that same ignored backup directory:
  `visualai_layer_a_v1-1154243538407718-2026-10-11-01-45-49.snapshot`;
  990,720 bytes, SHA-256
  `0e2d4fb2758de0ca858e4877f64df3a7300df27981328aa343c0a2d2487d54ce`.
- Recreated only Qdrant using the existing Compose project and the local override:

  ```powershell
  wsl.exe -d Ubuntu -- docker compose -p ai-video-generator --project-directory '/mnt/d/ai video generator/AI-VIDEO-GENERATOR' -f '/mnt/d/ai video generator/AI-VIDEO-GENERATOR/docker-compose.yml' -f '/mnt/d/ai video generator/AI-VIDEO-GENERATOR/docker-compose.local.yml' up -d --no-deps --force-recreate --pull never qdrant
  ```

  Qdrant kept image `qdrant/qdrant:v1.12.0`, the named volume
  `ai-video-generator_qdrant_data`, and a loopback-only port 6333. The running
  container `visualai-qdrant` is healthy; `/readyz` returns HTTP 200. PostgreSQL
  was not recreated. No orphan containers or volumes were removed.
- Final comparison of every legacy point ID, payload and vector with the exported
  backup was identical. The old collection still contains five points.
  `.env` remained byte-for-byte unchanged. Both prior completed MP4s retained
  their pre-change hashes.

## Live retrieval and grounded-generation evidence

Used the signed-in user's normal UI and authenticated endpoints to refresh one
existing canonical PDF: `visualai-integration-sample.pdf`, source
`SRC_65dcf2aa05eb5ef9b48a44a6a9c4a99c`, version 1. The retry returned HTTP 200 and
the UI showed Source search is ready. Two source chunks were indexed in v2 with
complete model/collection/preprocessing provenance. This was a bounded explicit
refresh, not a bulk reindex.

The real owner-filtered query "How are force, mass and acceleration related?"
returned physics chunks `CHUNK_8967b239c39b5e1d98366f5936d094fa` (0.54303) and
`CHUNK_21e695cfb96455c28470b5a28ce747a6` (0.53036), both canonical source version 1.
The heading-only chunk was not treated as evidence for unsupported concepts.

Through the normal UI, created lesson `66c65010-d34b-44b8-a511-bab3e8f970f1`, enabled
source-only retrieval, and generated `JOB_78FAE3985C`. No exact-chunk selection was
supplied; the request exercised semantic retrieval and canonical validation.
Result: COMPLETED, SOURCE_GROUNDED, two scenes, two scene-specific quotation
references with canonical content/chunk IDs, source version and character offsets.
Scene indexing reached INDEXED. Actual ffprobe duration: 45.056575 seconds;
timeline status MEASURED. Caption validation against the final MP4/timeline passed.

Authenticated browser playback advanced with no media error; selecting a scene
displayed its source quotation. The browser search "force and acceleration"
returned links to both generated scenes. Authenticated video, metadata, captions
and scene-search endpoints returned HTTP 200. The player initially displayed a
pending-index message before indexing finished; PostgreSQL subsequently recorded
INDEXED. After reloading the grounded lesson, the browser also displayed
"Scenes are indexed and searchable." This is not evidence of an indexing failure.

The new collection held 11 points at the final check, including other concurrent
local video activity. Only the bounded source refresh and grounded generation
above are claimed as this repair's live test evidence.

## Executed tests

```powershell
$env:VISUALAI_VIDEO_TEST_DOCKER_WSL='Ubuntu'
.\.venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider
$visualaiFrontendTests = @(Get-ChildItem tests -Filter 'test_*.js' | ForEach-Object {$_.FullName})
node --test $visualaiFrontendTests
```

- Full backend: **1,652 passed, 139 skipped, 5 warnings**, 264.38 seconds; no failures.
  Includes the Docker PostgreSQL regression tests and corrected duration journey.
- Full frontend: **116 passed, 0 failed, 0 skipped**.
- Focused repair/retrieval suite: **127 passed** before the last two source cases;
  subsequent source/embedding run: **40 passed**. Both extra cases also passed in
  the full backend suite.
- Skipped tests are not claimed as successful external verification. Warnings
  include existing Starlette/audioop deprecations, duplicate dashboard operation ID
  and an unregistered e2e marker. They remain outside this repair.

## Remaining limitations and manual steps

1. A separate extraction-only `original.pdf` source,
   `SRC_886d1918d74e5070bacc899c6d7129e9`, returned HTTP 422 from retry-index during
   knowledge preparation. Its older lesson
   `b378983d-2c42-4a59-87a3-d09c3f8aac20` returned HTTP 503 when reopened in this
   final browser check. The precise underlying knowledge failure is unverified;
   do not describe it as repaired by embedding installation. Investigate that
   source's safe structured failure diagnostics separately. Validation was not
   bypassed. The two previous completed MP4 files are unchanged, but this prevented
   a fresh browser retry-index/playback check for those older generations.
2. Prepare additional existing sources individually through the version-bound
   action. Unproven legacy vectors remain excluded. No automatic migration or
   full historical reindex was performed.
3. Browser download completion and native subtitle-menu interaction remain
   unverified. The authenticated captions endpoint and on-disk final caption
   timing were verified; these do not establish a browser download completion.
4. Ownership/version/refusal negative cases passed automated tests; a second-account
   live browser test was not performed in this repair.
5. A future model-weight update must use a separately validated namespace. The
   installed model digest is recorded here; tags alone do not prove immutable
   weights across future operator updates.

Rollback: preserve both collections and backups. Revert only this repair's code
with a separately reviewed patch, leaving user changes intact. If explicitly
selecting a previous namespace, use `SEMANTIC_COLLECTION_NAME` in the deployment
configuration; unknown-provenance vectors must continue to fail closed. Do not
restore a snapshot over the live volume or remove collections as a shortcut.

## Operational follow-up (2026-10-11)

Baseline for this follow-up: same branch and existing uncommitted repair changes
listed above, plus the untouched user audit file. The existing source/embedding
suite passed 40 tests before these changes. No pending changes were discarded.

The original PDF failure was reproduced through the owned source UI. Safe server
diagnostics identified `STRUCTURING / INVALID_HIERARCHY / PARENT_REFERENCE`, after
the existing model repair attempt. More precise counts showed zero missing topic
or subtopic references, one topic with no subtopics, and zero subtopics with no
concepts. This was an unused proposed heading, not an embedding error.

`app/services/content_understanding.py` now removes unused candidate topic/subtopic
headings before full proposal validation. It preserves every concept, evidence
span, definition and surviving parent relationship. Missing parent references,
duplicate identities and wholly empty hierarchies are left for rejection. All
existing canonical snapshot/evidence validation still runs before publication.
No previously stored knowledge is deleted. Repair markers are recorded in the
existing deterministic-repair metrics. Safe category/count logging was added to
the validator and the existing failure handler in `app/main.py`; no raw proposal,
source text, bearer token or provider exception is logged by these additions.

`app/static/learning.js` now renders allowlisted source-preparation failure
classifications through the existing safe formatter and replaces stale Preparing
status on failure. The source card continues to offer an explicit retry.

The older lesson reopened successfully without changing its persistence or
validation. Owner-scoped loading returned its completed generation, and its
authenticated browser lesson, stream, metadata and captions requests returned
HTTP 200. Its existing reindex endpoint successfully reconciled `JOB_D30BF95093`;
the UI now says Scenes are indexed and searchable. The prior HTTP 503 has not
recurred in this check; its precise transient cause is not established. Lesson
loading does not call knowledge preparation, so do not attribute that 503 to the
PDF hierarchy error without further evidence.

The native browser video Download menu was disabled. `app/static/learning.html`
and `app/static/learning.js` now expose an explicit **Download video MP4** link
using the current authenticated media blob. Filenames identify the lesson and
generation. Navigation hides the link and removes its revoked blob URL; no token
is placed in the URL and no new public endpoint was added. Behavioral frontend
tests verify the displayed generation, blob URL and cleanup after navigation.

Focused hierarchy/evidence/source tests: 93 passed, 1 skipped. Final full backend:
**1,656 passed, 139 skipped, 5 existing warnings**, 272.62 seconds. Final full
frontend: **118 passed, no failures**. `git diff --check` is included in final
verification. The additional tests cover unchanged canonical snapshots after
pruning, refusal of dangling references/empty knowledge, safe direct-retry error
messages, exact-generation download links and older-source version authority.

### Final live outcomes

- The PDF retry on the updated worker passed the former empty-parent condition,
  but the model then failed full evidence validation with
  `STRUCTURING / UNSUPPORTED_EVIDENCE / LABEL`, object `TOPIC`, repair attempted.
  The UI displayed that safe classification. **This source is not yet ready for
  grounded retrieval.** No fabricated label was accepted or canonical validation
  bypassed. Further repeated blind retries were stopped. The next required step
  is to constrain or improve the existing PDF topic-label proposal against its
  verified inventory/anchors, and demonstrate this exact source passing the
  existing validator before committing knowledge or indexing it. No model or
  provider was silently changed.
- The older lesson and `JOB_D30BF95093` load successfully; scene reconciliation
  reached INDEXED. Both original MP4 hashes remained unchanged. Its later
  generation `JOB_89DB2DDBB2` still has its historical failed-index status; that
  version was not retried in this follow-up. Neither was regenerated.
- **Browser MP4 download completed.** Clicking the new link saved
  `C:\Users\kudir\Downloads\visualai-b378983d-2c42-4a59-87a3-d09c3f8aac20-JOB_D30BF95093.mp4`,
  1,080,303 bytes. SHA-256
  `61c7f4b2f0317e0c847de27e99e5d2f512ffdd3f7a7a474a3590134a4ae4cc72`
  equals the original rendered video. The browser tool timed out waiting for a
  download event, so completion was verified from the actual saved file and its
  hash instead. The explicit link fixes reliance on the disabled native menu.
- Older canonical READY source cards now expose the same individual preparation
  action as recent materials. Extraction-only CONTENT_READY entries are not
  automatically promoted to grounded readiness. No bulk migration was performed.
- Final checks confirmed `.env` and every legacy vector/payload remained identical
  to the original baseline. No commit or push was performed.
