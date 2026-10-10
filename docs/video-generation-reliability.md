# Video generation reliability — baseline and result

## Baseline before implementation

- Branch created: `video-generation`, from freshly fetched `origin/main`, commit
  `c2226e16ae78f362f9ab94de7d14465899983ddf`.
- The only existing working-tree item was untracked `LEARNING_PIPELINE_AUDIT.md`.
  It remains untouched. No repository `AGENTS.md` was found in the project or
  checked parent directories.
- Focused baseline: **53 passed**, one existing Starlette deprecation warning,
  7.52 seconds. Video API contracts, generation persistence and local visuals
  were included.
- Existing routes, schemas and history are documented in
  [video-api-enhancements.md](video-api-enhancements.md). The educational API
  uses owner-scoped lesson JSON; the remediation adapter uses the canonical
  Supabase RPC. These persistence boundaries were preserved.

Confirmed gaps: saved WebVTT was not independently parsed or reconciled after
writing; evidence reads checked source-unit text but not membership in the
actual canonical chunk; real worker termination/concurrent start needed stronger
verification. A live embedding probe subsequently confirmed a `NameError` from
the missing `os` import in `app/db/vector_store.py` before the provider call.

Existing behavior to preserve: private playback and captions, completed-version
history, measured scene composition, narration, source ownership/version checks,
independent indexing failures and the local topic-illustration renderer.

Planned and actual affected files:

| File | Reason |
| --- | --- |
| `app/services/video/caption_validation.py` | Parse saved scene WebVTT and validate its text and measured timeline |
| `app/services/video/scene_media.py` | Normalize/escape cue text; validate the saved file before completion |
| `app/api/educational_content.py` | Reject corrupted measured captions on authenticated reads |
| `app/services/video/educational_video.py` | Validate evidence against canonical chunks; validate captions before indexing |
| `app/db/vector_store.py` | One-line missing-import repair, confirmed by a live probe |
| `tests/test_video_caption_validation.py` | Independent invalid-caption and invalid-timeline cases |
| `tests/test_video_reliability.py` | Real chunk reconstruction, traceability, protected media, index rejection and Ollama transport cases |
| `tests/video_process_worker.py`, `tests/test_video_process_recovery.py` | Disposable real child processes for concurrent start, forced exit and fresh-process recovery |
| `tests/test_educational_video_enhancements.py` | Fixtures now contain valid per-scene captions; permission fixture explicitly supplies its isolated manifest |

## Implemented changes

The new validator accepts the generated one-cue-per-scene format. It checks the
UTF-8/WebVTT header, bounded file size, timestamp syntax, cue count, positive
durations, ordering, overlaps, scene IDs and indices, timeline continuity,
duration consistency, caption content and final video bounds. A **2 ms**
tolerance covers millisecond timestamp serialization, not estimated alignment.
It parses the file actually written. Invalid generation output cannot publish
`COMPLETED`; corrupted captions on a measured completed generation return
`409 VIDEO_CAPTIONS_INVALID`. Such a generation also cannot be newly indexed.
Already completed video media remains available. Legacy caption contracts are
preserved. These checks do not claim word-level speech alignment.

Evidence reads reconstruct the canonical manifest using the same educational
chunker, source version, source hash and chunk policy used by retrieval. Each
reference must identify an actual chunk, an associated concept and a canonical
content span containing its exact quotation. Existing source permission,
sanitization, offset and scene-content checks still apply. No model is trusted
to create evidence IDs. This validates extractive support, not entailment for
arbitrary AI-written claims.

The embedding repair imports `os`, which the existing Ollama query-cache path
already used. No model, provider, collection, embedding dimension or environment
configuration was changed.

## Verification actually performed

- Baseline: **53 passed**, one warning, 7.52 seconds.
- First focused caption/evidence/API/recovery regression: **73 passed**, one
  warning, 3.86 seconds.
- Real two-process regeneration/forced-exit test: **1 passed**, one warning,
  4.78 seconds. Both processes returned the same job ID; a held execution lock
  prevented false interruption; killing the disposable workers released the
  lock; a fresh process marked the job `FAILED / VIDEO_JOB_INTERRUPTED` while
  preserving its plan, previous completed generation and original media bytes.
- Broader video/retrieval/lesson/personalization suite: **202 passed**, two
  existing deprecation warnings, 119.73 seconds.
- Frontend JavaScript regression: **65 passed**, zero failures, 221.7953 ms.
- After the import repair: embedding/vector/caption focused regression:
  **59 passed**, one warning, 2.88 seconds.
- After adding the explicit real-chunk boundary case: reliability suite:
  **9 passed**, one warning, 2.01 seconds. The follow-up tests include production
  Ollama success/missing-model branches using a replaced HTTP transport.
- Protected streaming was exercised with a byte-range request: `206`, expected
  bytes and private/no-store headers. Invalid timestamp inputs were rejected.
- The real local educational rendering pipeline is part of the broader suite;
  test narration is synthetic. External database/index transports in automated
  suites are doubles, not evidence of production RLS or live search quality.

One initial new test failed because its Windows fixture converted CRLF to
CR-CRLF. The fixture was corrected to normalize line endings before constructing
a BOM/CRLF file. Production validation was not weakened.

## Live dependencies and blocked verification

- Local server `/health`: `ok`.
- Qdrant health: `connected`, existing collection `visualai_layer_a_v1`.
- Video health: Manim and FFmpeg available, configured narration `edge_tts`.
- Ollama responds, but its installed-model list does not contain the configured
  embedding model. After the import repair, a live query returns the correctly
  classified **`EMBEDDING_MODEL_UNAVAILABLE`**. No models were installed and no
  production Qdrant writes or reindex operations were attempted.
- After the user restored dashboard access, a real new generation completed:
  `JOB_AA44042F78`, five scenes, measured duration **35.356575 seconds**, visual
  style `topic_2d_v1`. The previous completed versions remained in history.
  The browser displayed `Animated narrated video is ready.` and pinned the new
  generation in its URL. The media reached readyState 4; its caption track
  reached readyState 2 with captions showing. Selecting Search Operation sought
  to **24.033333 seconds**; playback advanced to **29.900981 seconds** before
  pausing. The screenshot showed the tree illustration and caption together.
  Reload restored the same generation, five scenes and ready player.
  Indexing correctly remained failed with `EMBEDDING_MODEL_UNAVAILABLE`, while
  playback stayed available. No credentials or profile preferences were changed.
- Browser download completion remains **unverified**: the automation media
  helper and native player Download action both timed out waiting for a download
  event. No downloaded file was returned for inspection. This does not establish
  whether the application, browser download integration or event capture caused
  the failure. Authenticated streaming/range responses passed automated checks.
- Previously documented remediation RPC persistence/versioning limitations
  remain outside this increment. The matching deployed RPC migration is still
  absent from the checkout. No live RPC definition was re-inspected and no
  migration, persistence fallback or remediation rewrite was attempted.

## Corrected concurrency assessment

The current shared `store_lock` already combines a thread lock and a cross-process
OS file lock around JSON read/modify/write operations. It is more than a
process-local mutex; no replacement was needed. This increment verifies two
processes sharing the same storage and locks. Admission accounting remains
process-local, and local file locks do not provide a multi-host distributed queue.
Storage must survive application/container replacement. Recovery marks jobs
interrupted and retryable; it does not resume an unfinished render automatically.

## Smallest remaining sequence

1. Restore the configured embedding model/service, then test real scene indexing,
   retry and owner-filtered semantic results without synthetic vectors.
2. Verify native download completion in a browser that returns a saved file;
   inspect the downloaded MP4. New generation, playback, captions, scene seeking
   and reload are now verified in the local browser.
3. Verify evidence with an actual uploaded source once the required retrieval
   providers are available. Current evidence tests use real
   canonical models/chunking with isolated database transport doubles.
4. Recover and review the deployed remediation RPC definition before proposing
   an additive version/history/metadata contract and isolated database tests.
   Production migration requires separate review/approval.

No agents, learning loop, new infrastructure, packages, database changes or
deployments were added. Changes are not committed or pushed by this increment.
