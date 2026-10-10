# Video API enhancement implementation — 2026-10-11

Follow-up reliability work and current dependency blockers are recorded in
[video-generation-reliability.md](video-generation-reliability.md).

## Continuous topic visuals update

Baseline: branch `new-implementations`, commit `8a97eda`; only the existing
untracked `LEARNING_PIPELINE_AUDIT.md` was present. It was left untouched.
The educational Video API baseline passed 31 tests. Inspection of the user
recording showed extended empty navy frames. Existing Manim scenes can fade out
before their requested duration; scene composition pads short visuals with their
final frame, which can therefore be empty. Other scenes displayed long text.

New educational plans use `visual_style=topic_2d_v1` in the existing renderer.
`app/services/video/topic_visuals.py` draws continuous local 2D illustrations,
short idea cards and changing visual focus throughout each scene. Presets cover
BSTs, ordered arrays, photosynthesis, water cycles and illustrative orbits.
Other topics use content-derived concept, sequence, comparison or cycle layouts.
The model planner requests six to eight concise scenes; the lesson fallback can
add up to two existing key-concept explanations. Scene count remains bounded by
available content, speech budget and the existing plan validator.

Grounded excerpts use source-derived cards, without adding domain-preset facts.
Schematics are labeled as illustrations, not source evidence or photographs.
No image API, external downloads, packages or agents were added. Narration,
measured composition, captions, authentication, download routes and generation
history retain their contracts. Old plans retain their rendering behavior;
completed videos are unchanged. Select **Generate a new version** for new visuals.

Verification includes decoded MP4 frames near the end of each test scene,
nonempty illustration regions and temporal visual changes, plus existing
educational video, audio, timeline, indexing and persistence regressions.
Preview frames were rendered locally and visually inspected. Two initial index
test failures were fixture assumptions about a four-scene duration; the fake
probe now uses the fixture artifact's duration while retaining duration-mismatch
validation. Production spoken-provider generation and browser playback of a new
generation have not been rerun for this visual update.

Regression result: **125 passed**, with two existing deprecation warnings, in
114.73 seconds. This includes the real local educational rendering pipeline;
synthetic test audio is not evidence of a new live spoken-provider run.

## Baseline and scope

Branch: `new-implementations`, starting commit `a3c38c9`.
The only pre-existing working-tree item was untracked `LEARNING_PIPELINE_AUDIT.md`; it was preserved.
The pre-edit focused baseline was **35 passed, 1 deselected** (3.14 seconds).
See `video-generation-baseline.md` for the original foundation increment and contracts.

This increment implements the educational lesson workspace through its existing owner-scoped JSON persistence boundary. Rendering now uses the existing shared video engine. It does not add agents, a learning loop, another engine, database, collection, object store, or a production migration.

## What changed

| Capability | Educational workspace | Verification / limit |
| --- | --- | --- |
| Topic-specific planning | Structured model scene sequence, difficulty, duration and preferences; explicit lesson fallback if the model fails | Model response schema and fallback contracts tested; topic must match the owned lesson |
| Visual changes | Animated BST search example; concept-map templates for diagram scenes; readable wrapped text and fonts | Local renderer and FFmpeg exercised; arbitrary topic-specific simulations are not generated |
| Grounded planning | Existing canonical retrieval, selected content/chunk IDs, exact source/version scope | Extractive quoted scenes labeled `EXTRACTIVE`; no claim of validated model paraphrasing or contradiction resolution |
| Scene narration | Separate speech synthesis per scene; extend visuals to preserve longer narration | Synthetic audio tested; production still requires a spoken provider |
| Timeline | Probe each composited segment, reconcile final MP4 duration, store actual scene boundaries | Final duration mismatches fail; no invented timing for old artifacts |
| Captions | Private authenticated WebVTT, measured scene boundaries | `SCENE_TIMED`, not word-level forced alignment; legacy Whisper path preserved |
| Metadata | Stable generation IDs, plans, actual timeline, media properties, status, caption quality and prior generation | Owned lesson JSON remains authoritative; public schemas exclude paths |
| Bidirectional evidence | Scene/video/time → exact evidence; source/content/chunk → matching scenes | Revalidates ownership, source version, sanitization, retrieval permission and literal offsets |
| Qdrant indexing | Existing collection and embedding helpers, deterministic point IDs, completion validation, read-back verification | Controlled retry after partial/index failures; separate status from video completion |
| Scene search | Owner and embedding-space filters; rehydrate owned metadata and reject stale digests/missing media | At most 200 candidates; honest pagination within that bounded candidate set |
| Regeneration | Explicit new version; completed generations and pinned playback remain available | Running regeneration conflicts; previous artifact is retained if a replacement fails |
| Frontend | Duration/level/grounding/preferences, regeneration, scene navigation, evidence, captions and search links | Exact generation/scene deep links; safe text rendering and authenticated media fetch |

## APIs

All routes use the existing authenticated source-repository dependency. Metadata/list endpoints have public Pydantic response contracts and private/no-store caching. Media paths are never accepted from callers.

| Method | Route | Operation |
| --- | --- | --- |
| POST | `/educational-content/{lesson_id}/video` | Existing route extended with optional generation options |
| GET | `/educational-content/{lesson_id}/video/status` | Existing job status contract preserved |
| GET | `/educational-content/{lesson_id}/video/stream` | Existing private playback; optional `generation_id` pins history |
| GET | `/educational-content/{lesson_id}/video/metadata` | Public metadata, complete scene timeline and independent index status |
| GET | `/educational-content/{lesson_id}/video/scenes` | Paginated scene records |
| GET | `/educational-content/{lesson_id}/video/scenes/{scene_id}` | One scene and its evidence |
| GET | `/educational-content/{lesson_id}/video/at` | Resolve finite nonnegative `seconds` using half-open scene boundaries |
| GET | `/educational-content/{lesson_id}/video/evidence` | Evidence for all scenes, or optional `scene_id` |
| GET | `/educational-content/{lesson_id}/video/captions` | Private WebVTT for the selected generation |
| POST | `/educational-content/{lesson_id}/video/reindex` | Reconcile a completed measured generation; required `generation_id` |
| GET | `/educational-content/video-scenes/search` | Bounded semantic search using `query`, `offset`, `limit` |
| GET | `/educational-content/video-sources/{source_id}/scenes` | Source lookup with required `source_version`, optional `content_id` / `chunk_id`, pagination |

Generation-specific metadata, scene, timestamp, evidence and caption reads accept optional `generation_id`. Omitting it selects the current generation. Default streaming can retain the previous completed video while regeneration is running; explicit history playback is always pinned.

Example generation options:

```json
{
  "regenerate": true,
  "grounded": false,
  "topic": "Binary Search Trees",
  "difficulty": "intermediate",
  "target_seconds": 45,
  "instructions": "Focus on a worked search example",
  "source_content_ids": [],
  "chunk_ids": []
}
```

Unknown options and invalid types are rejected. Duration is bounded to 20–180 requested seconds; individual actual scenes are bounded to 120 seconds, the complete artifact to 600 seconds. Actual duration may exceed the requested duration to preserve speech. A plan that exceeds the existing speech-rate/scene budget is rejected rather than silently truncating it.

## Persistence and dependencies

```text
Authenticated owned lesson
  → model plan OR existing canonical retrieval → exact extractive plan
  → saved generation record + execution lock
  → existing engine / TTS / deterministic renderer
  → FFmpeg per-scene composition + media probes
  → final MP4 + measured scene timeline + WebVTT
  → owned lesson JSON (authoritative artifact + mappings)
  → existing embeddings / Qdrant (derived scene pointers + metadata digest)
  → authenticated metadata, search, navigation and playback
```

Files remain in the configured lesson runtime, renders, audio and captions directories. Intermediate scene audio and visual/composited segments are retained; this increment adds no cleanup policy. Local persistent volumes/backups remain an operational requirement. The unchanged Docker command starts one Uvicorn process. The shared JSON store already serializes read/modify/write merging with a thread lock and a cross-process OS file lock; admission accounting remains process-local. OS execution/index locks protect individual jobs. These local locks are not a distributed queue or a guarantee of multi-host transactional writes.

Failed indexing does not turn a valid rendered video into a failed render. Reindex uses the same deterministic IDs and refuses incomplete/unmeasured media. Historical scene points can remain searchable only while their owned generation is valid and indexed; invalid metadata digests, foreign owners, removed evidence and missing media are rejected when results are rehydrated.

## Blocker: canonical remediation persistence

The live `visualai_internal.remediation_video` function was inspected read-only during baseline establishment:

- `claim` accepts and stores the initial plan.
- `save` persists basic job/media fields, but does **not** update the plan or output metadata.
- Completed/failed terminal records cannot be retried through that contract.
- The matching deployed function migration is not available in this checkout.

Affected components: `app/services/video/session_video.py`, the existing remediation Video API and Supabase `generated_videos` records. This increment preserves that path and does not bypass its database authority. The educational additions above do not imply that remediation now persists measured timelines, implements scene search or supports completed-video regeneration.

Minimum next action: recover the deployed RPC migration and review an additive contract for generation/version identity, measured timeline and evidence/index metadata persistence, and authorized regeneration history. Exercise it on an isolated database with tenant and terminal-transition tests before approving any production migration. Only then connect the existing canonical adapter to these capabilities.

## Actual automated verification

- Focused new video enhancement and canonical retrieval tests: **52 passed**, 1 warning, 2.43 seconds.
- Final broader video/retrieval/lesson/personalization regression: **163 passed**, 2 deprecation warnings, 112.43 seconds.
- Final browser JavaScript regression: **65 passed**, 0 failed, 169.11 milliseconds.
- After the final visual edge adjustment: the real local BST rendering regression passed again (**1 passed**, 12.56 seconds).
- A live 30-second request initially exposed an overly tight narration budget. The plan allocator now preserves narration with an explicit effective planned duration; metadata distinguishes requested `target_seconds`, `planned_seconds`, and measured `actual_seconds`. Invalid model scene plans use a labeled lesson fallback. Follow-up focused tests: **51 passed, 1 deselected**, 3.86 seconds.
- The real local rendering test exercises BST visuals, FFmpeg audio/video streams, timeline continuity, final duration and captions. Narration is synthetic test audio, not proof of live spoken narration or speech-recognition quality.
- External Qdrant, model and Supabase behavior is tested with doubles in these suites. These results do not certify live provider availability or production RLS.

Broader Python command:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_educational_video_enhancements.py tests/test_canonical_retrieval.py tests/test_video_generation_foundation.py tests/test_canonical_video_engine.py tests/test_phase5_video_animation.py tests/test_step3_manim_video.py tests/test_educational_lesson_features.py tests/test_educational_content.py tests/test_interest_personalization.py -q -p no:cacheprovider
```

Frontend command:

```powershell
& 'C:\Program Files\nodejs\node.exe' --test tests/test_topic_workspace_frontend.js tests/test_learning_frontend.js tests/test_learning_profile_frontend.js
```

## Live verification

The running local server responded `ok` and exposed the new routes in its OpenAPI schema. A signed-in browser created a Binary Search Trees lesson and generated job `JOB_3C4AB597D2` through the real configured providers:

- Model-generated plan, 30 seconds requested, 32 seconds effective plan, **44.756575 seconds actual**; four scenes.
- Edge-TTS configured; final validated H.264/AAC MP4, 907,910 bytes.
- Measured timeline and `SCENE_TIMED` captions persisted. The browser restored playback after reload, the pinned generation/scene URL remained intact, and the BST scene sought to 21.266667 seconds. Playback advanced normally; the private WebVTT track reported ready state 2 (loaded). At the narrow viewport, the document width remained within the viewport after the scoped wrapping fix.
- A frame from the live MP4 confirmed the worked tree diagram. Visual review identified edges crossing node labels; the renderer now stops edges at circle boundaries. Mobile review also identified scene-navigation overflow, fixed with wrapping scoped to the video panel.
- Qdrant health returned `connected`. Reindexing returned **`EMBEDDING_MODEL_UNAVAILABLE`**. The completed video remained playable, and the UI displayed the provider failure and a separate retry-index action. Live semantic scene search and source-grounded retrieval remain unverified until the configured embedding model is restored; no synthetic production embeddings were substituted.
- Live regeneration created `JOB_8CBCDF01D1` (**35.656575 seconds**) with prior generation `JOB_3C4AB597D2` still `COMPLETED`. A frame from this final version verified the corrected node/edge rendering. Both generations retained separate plans, timelines and artifacts.

Docker CLI was absent from PATH and the standard Docker Desktop executable location, so container status was not verified. No installation, environment change, migration, deployment, commit or push was performed. Browser testing created one ordinary lesson and two local rendered generations in the signed-in account; it did not change profile preferences or unrelated existing videos.
