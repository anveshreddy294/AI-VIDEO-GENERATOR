# PROJECT_CONTEXT.md — VisualAI (AI-VIDEO-GENERATOR)

## 1. Project Overview
**VisualAI** is an AI-powered personalized educational video and knowledge profiling platform. It ingests multimodal study materials provided by or for students—including textbooks/notes (PDF, TXT), diagrammatic images (PNG, JPG, JPEG), and recorded lecture videos (MP4, MOV, MKV)—normalizes them into a canonical representation, constructs a structured conceptual Knowledge Graph with prerequisite links, indexes authoritative source chunks in a vector database, runs diagnostic student assessments, models concept mastery with anti-loop guardrails, and outputs a target blueprint (the **Video Target Matrix**) to guide downstream automated AI video generation.

---

## 2. Main Objective
The ultimate vision of the platform is to transform raw, dense study material into automated, highly targeted, bite-sized remedial video lessons tailored to an individual student's exact conceptual weaknesses and prerequisite gaps:
1. **Understand what is taught**: Parse any document, image, or video into authoritative facts, concepts, and dependency graphs without hallucination (**Step 1**).
2. **Diagnose what the student knows**: Generate grounded diagnostic quizzes directly from authoritative material, evaluate submissions, detect root prerequisite gaps, and avoid repetitive failure loops (**Step 2**).
3. **Generate targeted instructional videos**: Produce focused, multi-scene animated video explanations (30s foundational, 45s intermediate, 60s advanced) addressing only the unmastered concepts (**Step 3 — Upcoming**).

---

## 3. Current Project Status
- **Step 1 (Ingestion & Knowledge Graph)**: **100% Complete & Production-Hardened**. Supports PDF (PyMuPDF block extraction + diagram OCR), Images (Gemini Vision), TXT (semantic paragraphs), and Video (FFmpeg 16kHz audio separation + faster-whisper ASR + OpenCV keyframe extraction with perceptual deduplication + Gemini Vision + speech/visual fusion). Builds `ContentUnit` abstractions, `KnowledgeGraph`, `TopicBlueprint`, `RichChunk` objects, and syncs to Qdrant Layer A (`visualai_layer_a`).
- **Step 2 (Diagnostic Assessment & Knowledge Profiling)**: **100% Complete & Production-Hardened**. Implements session initialization, knowledge graph snapshotting (self-contained offline sessions), cold-start dynamic planning (30% foundational, 40% intermediate, 30% advanced), prerequisite pairing, grounded question generation (with Gemini, Ollama, and Mock providers), structural and grounding validation gateways, non-duplication filters, reserve candidate backfilling, hidden answer key evaluation, anti-loop kill switch (>3 failures flags `REQUIRES_HUMAN_FALLBACK`), prerequisite gap detection, `StudentLearningProfile` persistence, and the `VideoTargetMatrix` handoff generator.
- **Interactive Web Dashboard**: **Complete**. An HTML5/CSS3/Vanilla JS single-page dashboard is embedded and served directly by FastAPI at `/`, featuring interactive quiz generation, direct file uploads, profile inspection, and video target matrix exploration.
- **Step 3 (Targeted AI Video Generation Engine)**: **Pending / Next Major Phase**. The data contract (`VideoTargetMatrix` at `storage/video_targets/<student_id>_<source_id>.json` or `GET /assessment/video-target/{student_id}/{source_id}`) is established and actively produced by Step 2. Video generation scripts, scene synthesizers, voiceover TTS, and visual composition rendering have not yet been implemented.

---

## 4. Complete Technology Stack
- **Programming Language**: Python 3.10+ (Current runtime tested on Python 3.12).
- **Web Framework**: FastAPI 0.141.1, Starlette, Uvicorn 0.30.6.
- **Data Validation & Schemas**: Pydantic v2 (2.13.5) with BaseModel, Field, model_validator, BeforeValidator.
- **LLM & Vision Services**:
  - Google Gemini API (`google-generativeai` 0.8.3): `gemini-3.5-flash` for generation/structuring, `gemini-embedding-2` for embeddings.
  - Ollama HTTP adapter (`OllamaProvider` via native `urllib`) for local open-source models (e.g. `llama3.2`).
  - Offline Mock Provider (`MockProvider`) for zero-API test environments.
- **Vector Database**:
  - Qdrant (`qdrant-client` 1.12.1).
  - Production mode: Docker container running Qdrant at `http://localhost:6333`.
  - Embedded local fallback: In-process embedded disk database at `storage/qdrant/` or `storage/qdrant_local/`.
- **Text & Document Processing**:
  - PyMuPDF (`pymupdf` 1.28.2 / fitz) for PDF text blocks, bounding boxes, and pixmap image extraction.
  - LangChain Text Splitters (`langchain-text-splitters` 1.1.2) for `RecursiveCharacterTextSplitter`.
  - Tiktoken (`tiktoken` 0.14.0) with `cl100k_base` encoding for token-accurate splitting.
- **Audio & Video Processing**:
  - FFmpeg (external system CLI) for audio ripping to 16kHz mono 16-bit PCM WAV.
  - Faster-Whisper (`faster-whisper` 1.1.0, CTranslate2) for offline ASR with word/segment timestamps.
  - OpenCV (`opencv-python` 5.0.0.93) for video capture, frame extraction, and grayscale perceptual deduplication.
  - NumPy (`numpy` 2.5.3) for frame array operations.
- **Networking & HTTP**: HTTPX 0.28.1, Requests 2.34.2, Python-Multipart 0.0.32.
- **Environment Configuration**: Python-dotenv 1.2.3 (`.env` loader).

---

## 5. Major Modules & File Map

### Root Configuration & Entry Points
- [app/main.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/main.py): FastAPI application entrypoint. Mounts dashboard, upload, and assessment routers; exposes `/health`, `/sources`, `/debug/qdrant`.
- [app/core/config.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/core/config.py): Central `Settings` class loading environment variables from `.env`, directory auto-creation, extension checking.
- [requirements.txt](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/requirements.txt): Pinned Python package dependencies.
- [Dockerfile](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/Dockerfile): Container configuration with FFmpeg and Python dependencies.
- [docker-compose.yml](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/docker-compose.yml): Multi-container configuration for VisualAI API and Qdrant container.
- [start.bat](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/start.bat) / [start.sh](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/start.sh): One-click launch scripts for Windows and Linux/macOS.

### API Layer (`app/api/`)
- [app/api/dashboard.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/api/dashboard.py): Embedded single-page Web console (HTML/CSS/JS) for testing uploads, quiz generation, grading, and profile inspection.
- [app/api/upload.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/api/upload.py): `POST /upload` endpoint for the complete Step 1 ingestion pipeline with optional automatic handoff to Step 2.
- [app/api/assessment.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/api/assessment.py): Step 2 endpoints: `POST /assessment/start`, `POST /assessment/handoff`, `POST /assessment/submit`, `GET /assessment/profile/{student_id}/{source_id}`, `GET /assessment/status/{session_id}`, `GET /assessment/video-target/{student_id}/{source_id}`.

### Database Layer (`app/db/`)
- [app/db/vector_store.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/db/vector_store.py): Manages Qdrant client connection (Docker or embedded fallback), collection creation (`visualai_layer_a`), embedding generation via Gemini, payload creation, and idempotent upserting using deterministic UUIDv5 IDs.

### Ingestion & Knowledge Services (`app/services/`)
- [app/services/schemas.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/schemas.py): Core data models: `SourceRecord`, `ContentUnit`, `ConceptNode`, `KnowledgeGraph`, `RichChunk`, `TopicBlueprint`.
- [app/services/registry.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/registry.py): Manages `sources_index.json`, computes SHA-256 hashes, handles file versioning, magic byte validation, and persists original files and extracted artifacts.
- [app/services/dispatcher.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/dispatcher.py): Routes files by extension (PDF, TXT, Image, Video) to corresponding extraction handlers.
- [app/services/extractor.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/extractor.py): PyMuPDF text block extraction with bounding boxes; extracts embedded images and sends them to Gemini Vision.
- [app/services/vision.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/vision.py): Gemini Vision API wrapper for textbook diagrams and lecture video frames.
- [app/services/structurer.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/structurer.py): Extracts hierarchical chapters/sections, concepts, and prerequisites; generates `KnowledgeGraph` and `TopicBlueprint`; includes heuristic fallback for quota limits.
- [app/services/chunker.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/chunker.py): Groups `ContentUnits` by section/concept boundaries into `RichChunk` instances with Layer A provenance.
- [app/services/validator.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/validator.py): 5-layer ingestion quality gateway (file, content, chunk, concept, storage).

### Video Matrix Ingestion Subsystem (`app/services/video/`)
- [app/services/video/pipeline.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/video/pipeline.py): High-level video pipeline orchestrator.
- [app/services/video/av_splitter.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/video/av_splitter.py): Uses FFmpeg to extract 16kHz mono WAV audio tracks.
- [app/services/video/transcriber.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/video/transcriber.py): Faster-whisper ASR with word-level and segment-level timestamps.
- [app/services/video/frame_extractor.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/video/frame_extractor.py): OpenCV keyframe sampling with 32x32 grayscale perceptual duplicate suppression (<4% change skipped).
- [app/services/video/fusion.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/video/fusion.py): Chronologically aligns spoken speech segments with visible frame descriptions into unified `ContentUnit` records.

### Assessment & Profiling Subsystem (`app/services/assessment/`)
- [app/services/assessment/schemas.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/schemas.py): Pydantic contracts for assessment requests, questions, sanitized questions, sessions, submissions, grading results, concept mastery, learning profiles, and video target matrices.
- [app/services/assessment/session_store.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/session_store.py): JSON persistence for active assessment sessions under `storage/assessment_sessions/`.
- [app/services/assessment/planner.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/planner.py): Concept selector implementing cold-start balance (30/40/30), prerequisite pairing DAG traversal, and profile-based adaptive targeting.
- [app/services/assessment/generator.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/generator.py): Source-isolated Qdrant chunk retrieval, strict negative prompting for MCQ generation, provenance attachment, and deterministic grounded fallback generation.
- [app/services/assessment/providers.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/providers.py): LLM provider abstraction protocol supporting `GeminiProvider`, `OllamaProvider`, and `MockProvider`.
- [app/services/assessment/validator.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/validator.py): Question quality gateway verifying 4 distinct options, valid correct index, non-empty text, grounding token overlap with source chunks, and Jaccard duplicate detection.
- [app/services/assessment/engine.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/engine.py): Submission grading against hidden answer key, false-mastery prevention (2+ consecutive successes needed for `MASTERED`), anti-loop kill switch (>3 failures sets `REQUIRES_HUMAN_FALLBACK`), and prerequisite gap detection.
- [app/services/assessment/profile.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/profile.py): Persistence for `StudentLearningProfile` under `storage/learning_profiles/`.
- [app/services/assessment/video_target.py](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/video_target.py): Builds `VideoTargetMatrix` scaling target seconds by difficulty (30s/45s/60s), filtering passed concepts and kill-switch concepts, and saving to `storage/video_targets/`.

---

## 6. Environment & Setup Information

### Prerequisites
1. **Python 3.10+** (64-bit).
2. **FFmpeg**: Required on host for video processing (audio track separation).
3. **Docker Desktop** (Optional): If running Qdrant in a container on port 6333. Embedded Qdrant operates locally without Docker.
4. **Google Gemini API Key**: Set in `.env`.

### Environment Variables (`.env`)
```bash
GEMINI_API_KEY=your_gemini_api_key_here
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
COLLECTION_NAME=visualai_layer_a
UPLOAD_DIR=storage/uploads
PROCESSED_DIR=storage/processed
ALLOWED_EXTENSIONS=pdf,png,jpg,jpeg,txt,mp4,mov,mkv
EMBEDDING_MODEL=models/gemini-embedding-2
GENERATION_MODEL=gemini-3.5-flash
WHISPER_MODEL_SIZE=large-v3
FRAME_INTERVAL_SECONDS=12
VIDEO_FRAME_SIMILARITY_THRESHOLD=0.04

# Step 2: Assessment Settings
MAX_QUESTIONS=10
ASSESSMENT_TTL_HOURS=24
MAX_QUESTION_RETRIES=2
MASTERY_THRESHOLD=2
KILL_SWITCH_LIMIT=3
LLM_PROVIDER=gemini       # Options: gemini, ollama, mock
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

---

## 7. How to Run the Project

### On Windows
```powershell
# Quickstart using batch script:
.\start.bat

# Or manual execution:
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### On Linux / macOS
```bash
# Using start script:
chmod +x start.sh
./start.sh

# Or manual execution:
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Access URLs
- **Web Console**: `http://127.0.0.1:8000`
- **Swagger Interactive API Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc API Reference**: `http://127.0.0.1:8000/redoc`
- **System Health Check**: `http://127.0.0.1:8000/health`
- **Qdrant Web UI (if Docker active)**: `http://127.0.0.1:6333/dashboard`

---

## 8. How Major Components Interact

```
[Student Upload] ──► POST /upload ──► Dispatcher ──► Extraction ──► Structurer (KG)
                                                                       │
                                              ┌────────────────────────┘
                                              ▼
                                       Semantic Chunker ──► Qdrant Vector Store (Layer A)
                                              │
                                              ▼
                                       Registry (Status: READY)
                                              │
                                              ▼
[Quiz Request] ──► POST /assessment/start ──► Planner (Cold Start / Prereq Pairing)
                                                    │
                                                    ▼
                                            Chunk Retriever (Layer A)
                                                    │
                                                    ▼
                                            Question Generator (Gemini/Mock)
                                                    │
                                                    ▼
                                            Quality Gateways (Grounding/Dedupe)
                                                    │
                                                    ▼
[Student Quiz UI] ◄── Sanitized Quiz (SafeQuestion, Hidden Answers)
        │
        ▼ (Selected Options)
POST /assessment/submit ──► Engine (Grading & Anti-Loop Kill Switch)
                                   │
                                   ├──► Updates StudentLearningProfile
                                   └──► Derives VideoTargetMatrix (30s/45s/60s)
                                               │
                                               ▼
                                  Step 3: AI Video Generation Engine
```

---

## 9. Current Development Phase
- **Phase 1 (Multimodal Ingestion)**: Complete.
- **Phase 2 (Diagnostic Assessment & Profiling)**: Complete, including:
  - Phase 2A: Robust question backfilling and reserve pools.
  - Phase 2B: Self-contained assessment sessions (`ConceptSnapshot`).
  - Phase 2C: Centralized configuration and stable concept IDs.
  - Phase 3: Pluggable LLM provider abstraction (`GeminiProvider`, `OllamaProvider`, `MockProvider`).
  - Phase 4: Final production hardening and contract verification.
- **Phase 3 (Video Generation Engine)**: **CURRENT MILESTONE TO BE BUILT**.

---

## 10. Completed Work
1. Multimodal parsing pipeline for PDF, PNG, JPG, TXT, and MP4/MOV/MKV.
2. Canonical `ContentUnit` schema preserving line, bbox, page, and timestamp provenance.
3. Automated conceptual knowledge graph generation with prerequisite mapping and rule-based fallback.
4. Concept-aware semantic chunking with Qdrant Layer A embedding synchronization.
5. Persistent registry tracking file checksums, versioning, and processing statuses.
6. Diagnostic assessment planning, question generation, and validation gateways.
7. Anti-loop kill switch (>3 failures flags `REQUIRES_HUMAN_FALLBACK` and removes concept from automated video queues).
8. `VideoTargetMatrix` generation specifying target durations (30s/45s/60s) based on concept difficulty tiers.
9. Single-page web dashboard for interactive exploration and pipeline testing.
10. Comprehensive automated test suites across Step 1 and Step 2 phases (`test_step1.py` through `test_step2_phase4.py`).

---

## 11. Pending Work
1. **Step 3 Implementation (AI Video Generation)**:
   - Script generation engine transforming `VideoTarget` definitions into scene-by-scene instructional scripts.
   - Text-to-Speech (TTS) voiceover synthesizer (e.g. Edge-TTS, ElevenLabs, or Bark).
   - Visual scene generation (diagram animation, code highlighting, motion graphics via Manim, MoviePy, or Remotion).
   - Audio/video stitching and final MP4 rendering pipeline.
   - Video output storage and API endpoints to stream or download generated video lessons.
2. **Dynamic RAG Engine (Step 4)**:
   - Contextual real-time query engine for student chat during video playback.
3. **Production Authentication & Multi-Tenancy**:
   - Authentication (JWT / OAuth2), user roles, and database isolation across students.

---

## 12. Important Rules & Constraints for Future AI Agents
1. **Never mutate application code without verifying against existing contracts**:
   - The canonical schemas in `app/services/schemas.py` and `app/services/assessment/schemas.py` are strictly adhered to by tests and endpoints. Do not alter existing field names or types without backwards-compatible validators.
2. **Never break Layer A isolation**:
   - Chunks stored in Qdrant carry `"layer": "A"`. Assessment retrieval must strictly filter by `source_id` to prevent cross-document data leakage.
3. **Maintain Self-Contained Sessions**:
   - `AssessmentSession` includes `concept_snapshot` so that grading and prerequisite analysis can occur offline even if registry artifacts are unavailable.
4. **Enforce the Anti-Loop Kill Switch**:
   - Never generate automated quizzes or automated videos for concepts tagged `REQUIRES_HUMAN_FALLBACK`.
5. **Adhere to Target Duration Scaling in Step 3**:
   - Foundational concepts = 30 seconds.
   - Intermediate concepts = 45 seconds.
   - Advanced concepts = 60 seconds.
6. **Grounding Integrity**:
   - Generated questions must strictly derive from source text chunks. Hallucination checks in `validate_grounding` must pass.
7. **Cross-Platform & Windows Compatibility**:
   - Use `Path` objects from `pathlib` for all file paths.
   - Avoid non-ASCII console print statements that crash Windows CP1252 shells.
   - Maintain mock fallbacks so test suites can run without external network access or paid API keys.
