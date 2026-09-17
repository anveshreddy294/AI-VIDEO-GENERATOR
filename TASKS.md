# TASKS.md — VisualAI Development Tracking

## 1. Completed Tasks

### Step 1: Multimodal Ingestion & Knowledge Graph Preparation
- [x] **File Validation & Persistent Registration**: Implemented `register_source` with SHA-256 duplicate detection, file versioning, magic byte signature checks, and master index cataloging in `storage/registry/sources_index.json`.
- [x] **Universal Modality Dispatcher**: Created `dispatcher.py` to route PDF, Image, TXT, and Video files.
- [x] **PDF Extraction Engine**: Implemented `extractor.py` using PyMuPDF (fitz) to extract text blocks, bounding box coordinates, and embedded images.
- [x] **Vision Analysis Engine**: Implemented `vision.py` using Gemini Vision for diagram transcription and video keyframe analysis.
- [x] **Video Matrix Ingestion Subsystem**:
  - [x] Phase 1: FFmpeg audio extraction to 16kHz mono WAV (`av_splitter.py`).
  - [x] Phase 2: Offline speech transcription with timestamps via faster-whisper (`transcriber.py`).
  - [x] Phase 3: OpenCV keyframe extraction with 32x32 grayscale perceptual deduplication (`frame_extractor.py`).
  - [x] Phase 4: Multimodal fusion merging speech and visual descriptions into `ContentUnit` records (`fusion.py`).
- [x] **Canonical Data Normalization**: Created `ContentUnit` model capturing modality, text, bounding boxes, sequence indices, and visual descriptions.
- [x] **Structure Detection & Concept Extraction**: Implemented `structurer.py` extracting chapters, sections, concepts, and prerequisite links into a persistent `KnowledgeGraph`.
- [x] **Semantic Chunking & Layer A Provenance**: Created `chunker.py` to produce `RichChunk` objects carrying `layer: "A"`, concept IDs, content IDs, page ranges, and timestamps.
- [x] **Vector Database Synchronization**: Implemented `vector_store.py` for Qdrant client connection (Docker or embedded fallback), cosine distance collection management (`visualai_layer_a`), Gemini vector embeddings, and deterministic UUIDv5 upserting.
- [x] **Quality Validation Gateway**: Implemented 5-tier gateway (`validator.py`) verifying file, content, chunk, concept, and storage layers before marking source as `READY`.
- [x] **Verification Testing**: Step 1 end-to-end test suite passing (`test_step1.py`).

### Step 2: Diagnostic Assessment & Knowledge Profiling
- [x] **Step 1 -> Step 2 Handoff Interface**:
  - [x] Automatic handoff via `POST /upload?auto_start_assessment=true`.
  - [x] Explicit handoff via `POST /assessment/start` and `POST /assessment/handoff`.
- [x] **Dynamic Assessment Planning**: Implemented `planner.py` with Cold Start distribution (30% foundational, 40% intermediate, 30% advanced) and Prerequisite Pairing DAG traversal.
- [x] **Source-Isolated Grounded Generation**: Implemented `generator.py` querying Qdrant strictly filtering by `source_id` to prevent cross-document leakage.
- [x] **Pluggable LLM Provider Abstraction**: Created `providers.py` protocol supporting `GeminiProvider`, `OllamaProvider`, and deterministic `MockProvider`.
- [x] **Multi-Gateway Question Validation**: Implemented `validator.py` checking 4 distinct options, valid correct indices, keyword grounding overlap with source chunks, and Jaccard duplicate detection.
- [x] **Candidate Reserve Pool Backfilling**: Implemented automatic reserve pool backfilling to satisfy target question counts if primary candidates fail validation.
- [x] **Self-Contained Session Snapshots**: Embedded `ConceptSnapshot` into `AssessmentSession` for offline prerequisite evaluation and difficulty classification.
- [x] **Sanitized Quiz Delivery**: Created `SafeQuestion` model stripping hidden answer keys and explanations while preserving source page and chunk provenance.
- [x] **Grading & Scoring Engine**: Implemented `engine.py` evaluating answers, calculating concept-level scores, and updating student profiles.
- [x] **False-Mastery Protection**: Required consecutive successful attempts (`mastery_threshold=2`) before transitioning concepts to `MASTERED`.
- [x] **Anti-Loop Kill Switch**: Tracked consecutive failures (`iteration_count > 3`) to flag persistent struggles as `REQUIRES_HUMAN_FALLBACK` and exclude them from automated video loops.
- [x] **Prerequisite Gap Detection**: Flagged instances where a student failed a child concept and simultaneously failed its parent prerequisite.
- [x] **Student Learning Profile Persistence**: Persisted profiles to `storage/learning_profiles/<student_id>_<source_id>.json`.
- [x] **Video Target Matrix Generator**: Implemented `video_target.py` scaling video duration by difficulty (30s foundational, 45s intermediate, 60s advanced) and saving to `storage/video_targets/<student_id>_<source_id>.json`.
- [x] **Production Hardening Test Suites**: All test suites passing (`test_step2.py`, `test_step2_backfill.py`, `test_step2_phase2b.py`, `test_step2_phase2c.py`, `test_step2_phase3.py`, `test_step2_phase4.py`).

### User Interface & Tooling
- [x] Embedded interactive Web dashboard console served at `GET /` in `dashboard.py`.
- [x] Cross-platform execution scripts: `start.bat`, `start.sh`, `Makefile`, and `docker-compose.yml`.

---

## 2. Current Tasks
- [x] Comprehensive architectural exploration and documentation of the existing repository.
- [x] Creation of `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, and `TASKS.md`.
- [ ] Alignment on Step 3 (Targeted AI Video Generation Engine) technical specifications and library choices.

---

## 3. Pending Tasks

### Step 3: Targeted AI Video Generation Engine (Upcoming Phase)
- [ ] **Video Script Generation Service**:
  - Ingest `VideoTarget` items from the `VideoTargetMatrix`.
  - Retrieve original text and diagram descriptions from grounded `chunk_ids` and `source_content_ids`.
  - Prompt LLM to produce structured scene-by-scene script JSON (scene number, visual action, voiceover narration, on-screen text, duration in seconds).
- [ ] **Voiceover Audio Synthesizer**:
  - Integrate Text-to-Speech (TTS) engine (e.g. Edge-TTS, ElevenLabs, or Coqui/Bark).
  - Generate timed audio tracks matching the target durations (30s / 45s / 60s).
- [ ] **Visual Animation & Scene Composition**:
  - Evaluate and integrate video rendering framework (e.g. MoviePy, Manim for mathematical/technical concepts, or Remotion/Canvas).
  - Animate diagrams and display callout bullet points corresponding to source material.
- [ ] **Audio/Video Stitching & Export Pipeline**:
  - Render final MP4 files to `storage/videos/<student_id>_<concept_id>.mp4`.
  - Expose API endpoints to stream or download generated video lessons: `GET /videos/{video_id}`.
- [ ] **Dashboard Video Player**:
  - Add video playback modal directly into the Web dashboard so students can watch remediation lessons immediately after quiz completion.

### Step 4: Dynamic RAG & Interactive Learning Agent
- [ ] Implement interactive conversational RAG allowing students to ask clarifying questions about specific video timestamps.
- [ ] Cross-reference Qdrant Layer A chunks during student chat interactions.

### Enterprise & Platform Hardening
- [ ] Implement user authentication (JWT / OAuth2).
- [ ] Multi-tenant isolation for educational institutions and classroom cohorts.
- [ ] Asynchronous task queue (e.g. Celery / Redis or ARQ) for long-running video rendering jobs.

---

## 4. TODOs Discovered in Code

1. **`app/services/extractor.py`**:
   - Line 77: Vision failure on individual page images prints a warning but continues; consider adding fallback OCR using Tesseract if Gemini Vision is unavailable.
2. **`app/services/structurer.py`**:
   - Line 264: Fallback concept extractor uses hardcoded slice `units[:4]` when no regex patterns match; improve semantic paragraph heuristics for unstructured narrative texts.
3. **`app/services/video/pipeline.py`**:
   - Line 29: Video processing gracefully falls back to `_visuals_only_units` if FFmpeg fails; consider logging a prominent user-facing notification in the API response.
4. **`app/services/assessment/generator.py`**:
   - Line 153: When no chunks are matched, synthetic chunks are created with `page_start=None`; ensure downstream consumers format `None` gracefully in UI tooltips.
5. **`app/db/vector_store.py`**:
   - Collection vector size probe currently embeds a dummy string (`"dimension probe"`) on first collection initialization; could be statically declared if embedding model dimensions are fixed.

---

## 5. Known Bugs & Quirks
1. **Gemini Free-Tier Rate Limits (HTTP 429)**:
   - *Behavior*: In `storage/registry/sources_index.json`, sources `SRC_4ed5e4a243ba`, `SRC_3b78a96e1730`, `SRC_626c52ed6226`, and `SRC_7180765e66bf` failed during rapid sequential testing due to the Gemini free-tier quota (`limit: 20 requests per day per project per model`).
   - *Mitigation*: The codebase contains resilient fallback mechanisms in both Step 1 and Step 2, but initial file upload requires an active key or sufficient quota, or configuration of local Ollama / Mock providers.
2. **Windows Shell Non-ASCII Output**:
   - *Behavior*: Some terminal encodings (CP1252) throw `UnicodeEncodeError` when printing unicode arrows or emojis.
   - *Mitigation*: Hardened in Phase 4 (`test_windows_output_compatibility`), but future scripts should avoid raw emoji printing in console logs.
3. **FFmpeg Dependency on Host**:
   - *Behavior*: If FFmpeg is not installed on the host machine, video uploads will fall back to visuals-only or fail.
   - *Mitigation*: Documented in `start.bat`, `start.sh`, and `COMMANDS.md`.

---

## 6. Technical Debt
1. **File-Based JSON Storage**:
   - Registry records, assessment sessions, profiles, and video targets are stored in JSON files under `storage/`. While ideal for transparency and lightweight deployment, high-concurrency environments will eventually require a relational database (PostgreSQL + SQLAlchemy/SQLModel).
2. **Synchronous Video Processing in Request Loop**:
   - Large video ingestion (`POST /upload` with an MP4) blocks the HTTP connection while faster-whisper and OpenCV execute. This should eventually be moved to a background worker (Celery/RQ) with WebSocket or polling status updates.
3. **Redundant Legacy Schemas**:
   - `AuthoritativeSourceChunk` and `AuthoritativeVideoChunk` in `app/services/schemas.py` are maintained for backwards compatibility alongside `RichChunk`. They can be consolidated once all legacy fixtures are deprecated.

---

## 7. Integration Requirements for Step 3

When developing the Step 3 Video Generation Engine, adhere strictly to the following integration contracts:
1. **Handoff Artifact Location**:
   - Read from `storage/video_targets/{student_id}_{source_id}.json` or call `GET /assessment/video-target/{student_id}/{source_id}`.
2. **Handoff Data Contract (`VideoTargetMatrix`)**:
   - `decision`: Must be `"GENERATE_VIDEOS"` to proceed. If `"ALL_MASTERED"` or `"HUMAN_INTERVENTION"`, abort video generation.
   - `videos`: Array of `VideoTarget` objects.
   - `target_seconds`: Must strictly obey duration constraints:
     - Foundational = 30 seconds.
     - Intermediate = 45 seconds.
     - Advanced = 60 seconds.
   - `human_intervention_concepts`: Must NEVER generate automated videos for concepts listed here.
   - `chunk_ids` & `source_content_ids`: Use these IDs to fetch exact source text and diagrams from `storage/registry/{source_id}/content_units.json` or Qdrant for illustration.

---

## 8. Recommended Next Implementation Steps
1. **Define Step 3 Video Generation Architecture Specification**:
   - Create `STEP3_SPECIFICATION.md` detailing script generation schemas, TTS engine selection, visual rendering library, and video stitching workflows.
2. **Implement Voiceover Audio Synthesizer**:
   - Integrate an offline or API-based TTS library (e.g., `edge-tts` or `gTTS` for free high-quality synthesis, or ElevenLabs API).
3. **Implement Scene Composition & Rendering Prototype**:
   - Build a lightweight video renderer (e.g. using `moviepy` or `manim`) that renders an introductory title card, animated bullet points, original diagrams cropped from the source document, and synchronized voiceover audio.
4. **Implement Step 3 REST API Endpoint**:
   - Add `POST /video/generate` accepting `student_id` and `source_id`, returning progress status and generated video paths.
5. **Add Dashboard Video Player UI**:
   - Integrate HTML5 `<video>` player in `app/api/dashboard.py` to allow immediate preview of generated lessons.
