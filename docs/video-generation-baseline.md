# Video generation foundation: baseline and acceptance criteria

The sections below preserve the first increment's historical baseline and results.
See [video-api-enhancements.md](video-api-enhancements.md) for the second-round implementation, API inventory, actual tests, and the canonical remediation persistence blocker.

## Second-round continuation baseline (2026-10-11)

- Branch `new-implementations`, commit `a3c38c9`; only pre-existing untracked `LEARNING_PIPELINE_AUDIT.md`, preserved.
- Before editing: foundation/canonical/lesson suite excluding the slow render case: **35 passed, 1 deselected**, 1 warning, 3.14 seconds.
- Actual educational pipeline still renders fixed slides and cannot regenerate completed videos. Final timeline, traceability query APIs, canonical scene search and index reconciliation are absent.
- Live RPC inspected read-only: `visualai_internal.remediation_video` stores `plan` at claim, but `save` does not update plan/output metadata, and terminal rows cannot be retried. Canonical remediation metadata/retry changes therefore require a reviewed migration; production will not be modified or bypassed. Independently testable educational enhancements reuse its established owned lesson JSON boundary.
- Focused files: shared engine/compositor/renderer for scene media and synchronization; educational service/API for generation options, metadata, provenance, reconciliation and regeneration; existing Qdrant integration for scene pointers; frontend for controls/navigation/captions; regression tests and documentation. No new agents, learning loop, database, object store, or parallel rendering engine.

## Baseline (2026-10-11, before implementation)

- Branch: `new-implementations`; HEAD: `278fdcb4f434bb4d6bf4507725e4cb3c1e7430cf`.
- Working tree: only untracked `LEARNING_PIPELINE_AUDIT.md`; preserved without edits.
- No `AGENTS.md` files found in the repository or checked parent directories.
- Existing test command: `.venv/Scripts/python.exe -B -m pytest tests/test_canonical_video_engine.py tests/test_phase5_video_animation.py tests/test_educational_lesson_features.py -q -p no:cacheprovider`.
- Actual baseline result: **32 passed, 2 deprecation warnings, 79.76 seconds**. Tests use isolated storage and mocked providers/test narration, not production services.

## Existing contracts and persistence boundaries

- `POST /educational-content/{lesson_id}/video`, `GET .../video/status`, `GET .../video/stream`: owned lesson JSON and local media.
- `POST/GET /learning-sessions/{session_id}/remediation/{job_id}/video`, `GET .../video/stream`: existing Supabase RPC, `generated_videos.plan`, and local media.
- Legacy `/video/*`: remains behind the existing Supabase compatibility boundary.
- Preserve existing status strings, routes, spoken-audio checks, artifact validation, ownership checks, and deterministic renderer. Do not introduce another engine, database, or object store.

## Confirmed defects and missing functionality

- Educational generation does not persist its scene plan before scheduling work.
- Process-local educational tasks can leave durable queued/running state after abrupt process termination.
- Canonical quote scenes attach all retrieved chunks rather than only the evidence supporting that quote.
- Educational video responses can expose internal paths.
- Actual scene timestamps, canonical scene indexing, full bidirectional query APIs, and safe completed-video regeneration are not complete.

## Focused increment

- Shared scene schema/validator: typed exact evidence references and optional authoritative source version; reject contradictory mappings and duplicate scene IDs.
- Canonical video adapter: preserve exact quote-to-evidence relationships in the existing saved plan.
- Educational service: generation history in existing lesson JSON, plan persistence before execution, safe interrupted-state recovery and duplicate-start behavior.
- Small local file-lock helper: OS-held generation execution ownership, released automatically on process death; never infer death solely from a different process's memory.
- Educational API: retain existing public fields while excluding paths and private plan/history data.
- Tests: exact references, owner isolation, plan persistence, live-lock protection, orphan recovery, retries and failure/completion metadata.

## Acceptance criteria

1. Existing targeted baseline tests remain passing.
2. A generation's stable plan is saved before its task begins and retained after failure/retry.
3. Scene evidence contains only actual supporting quotes with original source/version/content/chunk identity and offsets.
4. Interrupted educational jobs become retryable failures; an active execution lock prevents false recovery.
5. Existing public video responses do not disclose filesystem paths or private plans/history.
6. No API family, production migration, vector collection, infrastructure, or learning loop is added.

## Limits

This increment does not claim complete second-round enhancements. Accurate rendered scene timelines, canonical Qdrant indexing/reconciliation, traceability query APIs and UI remain subsequent work. Supabase RPC persistence is verified through deterministic mocks, not a production write. OS locks require a filesystem supporting advisory locks; they are not a distributed queue. No live cloud-provider verification is implied.

## Implemented result compared with baseline

- Educational lesson JSON now retains a `video_generations` dictionary keyed by job ID. Each entry contains the stable plan, previous job ID, status, timestamps, actual completed duration and safe failure code. The previous entry survives a retry.
- Plans are persisted before scheduling. Duplicate requests return the existing live/completed job. An OS file lock is held before saving QUEUED and for the duration of execution. A lesson/status read recovers an unlocked nonterminal job as `FAILED` / `VIDEO_JOB_INTERRUPTED`, enabling the existing retry path. Recovery is lazy, not an automatic mass rewrite or automatic regeneration.
- File locks work across local processes and are released by the OS on process termination. Cancellation before task execution also releases ownership. A live lock prevents false interruption reporting.
- Delayed writes from an old generation cannot replace a newer video's status or completion progress.
- Canonical quote scenes retain only supporting chunk references. Exact evidence references include source version, source/content/chunk/concept IDs, quoted text and original content character offsets. Split excerpts and the same quotation from multiple supporting chunks preserve correct mappings.
- Existing canonical Supabase plan persistence is reused. No new RPC, SQL migration, vector collection or persistence fallback was added.
- Shared plan validation rejects duplicate scene IDs and evidence scope/quote inconsistencies. Existing plans without the new optional fields remain supported; their grounding is not retrospectively certified.
- Educational public status/start/detail responses exclude private filesystem paths and plans/history. Streaming requires a completed video and preserves the existing owner/path checks.
- Educational videos remain explicitly AI-enriched. Their generation records honestly mark traceability and final timing unavailable, and indexing not requested. These changes do not invent evidence or timestamps.

## Files changed

| File | Purpose |
| --- | --- |
| `app/services/video/scene_schema.py` | Exact evidence references and optional plan source version. |
| `app/services/video/scene_validator.py` | Scene identity and evidence consistency validation. |
| `app/services/video/session_video.py` | Precise quote-to-source mapping using the existing retrieval/RPC boundaries. |
| `app/services/video/generation_lock.py` | Local cross-process execution ownership without another job engine. |
| `app/services/educational_content.py` | Private generation history, stable plan persistence, lazy recovery, retry history and stale-write protection. |
| `app/api/educational_content.py` | Safe public video fields and completed-only streaming. |
| `tests/test_video_generation_foundation.py` | Deterministic persistence, recovery, cancellation, security and evidence-mapping cases. |
| `docs/video-generation-baseline.md` | Baseline, acceptance criteria, implementation comparison and actual verification. |

## Actual verification

1. Before implementation: three existing targeted files, **32 passed**, 2 deprecation warnings, 79.76 seconds.
2. After the first code increment: canonical video and lesson tests excluding the render pipeline case, **14 passed, 1 deselected**, 1 warning, 6.28 seconds.
3. New foundation cases plus those targeted regressions: **33 passed, 1 deselected**, 1 warning, 3.11 seconds.
4. Broader regression command:

   ```powershell
   .\.venv\Scripts\python.exe -B -m pytest tests/test_video_generation_foundation.py tests/test_canonical_video_engine.py tests/test_phase5_video_animation.py tests/test_step3_manim_video.py tests/test_educational_lesson_features.py tests/test_educational_content.py tests/test_interest_personalization.py -q -p no:cacheprovider
   ```

   **107 passed**, 2 deprecation warnings, 107.30 seconds. This run included the original 19 foundation cases and local render/composition tests. Two further foundation cases were added while that run was executing, then verified separately below; do not add overlapping test totals together.
5. Final foundation-only command: `.\.venv\Scripts\python.exe -B -m pytest tests/test_video_generation_foundation.py -q -p no:cacheprovider`: **21 passed**, 1 deprecation warning, 2.27 seconds. Includes cross-process lock exclusion/release, whitespace/split-quote offsets, generation metadata and safe unavailable statuses.
6. Frontend command: `node --test tests/test_learning_frontend.js tests/test_topic_workspace_frontend.js tests/test_learning_profile_frontend.js`: **61 passed**, no failures/skips, 218.19 ms.
7. `git diff --check`: no whitespace errors.

Python tests required execution outside the sandbox because the virtual environment's interpreter launcher could not start inside it. Tests use the repository's existing isolated temporary storage and mock-service fixtures; no production migrations or writes were performed. Warnings concern Starlette/AnyIO and Python's deprecated `audioop` module.

## Remaining work, in order

1. Bounded render admission/concurrency and truthful audio/caption quality across the existing pipelines.
2. Measured final scene timing and persisted timeline reconciliation.
3. Canonical Qdrant scene indexing, explicit indexing state and idempotent reconciliation.
4. Authorized forward/reverse traceability, scene/timestamp lookup and pagination APIs.
5. Explicit completed-video regeneration with artifact/timeline/index consistency.
6. Topic-specific grounded instructional planning and scene navigation/evidence UI.

The current canonical flow remains one owned source/version per video. Multi-source video generation requires a later explicit contract extension. Canonical remediation retry/recovery requiring changes to the absent applied RPC migration is not silently worked around in application code. No AI agents or subagents, new learning loop, new infrastructure or duplicate rendering engine were added. Existing untracked `LEARNING_PIPELINE_AUDIT.md` was preserved.
