# VisualAI

> **Personalized Educational Video & Knowledge Profiling Platform**  
> *Transform raw study materials into structured knowledge graphs, diagnose individual student learning gaps with adaptive assessments, and generate targeted remedial video blueprints.*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-DC2626?style=flat-square&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%20API-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black?style=flat-square&logo=ollama&logoColor=white)](https://ollama.ai/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

---

## Table of Contents

- [Platform Overview](#platform-overview)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
  - [Step 1: Multimodal Ingestion & Knowledge Extraction](#step-1-multimodal-ingestion--knowledge-extraction)
  - [Step 2: Diagnostic Assessment & Knowledge Profiling](#step-2-diagnostic-assessment--knowledge-profiling)
  - [Instructor Analytics & Governance](#instructor-analytics--governance)
  - [Video Target Matrix (Step 3 Blueprint)](#video-target-matrix-step-3-blueprint)
- [Interactive Web Dashboard](#interactive-web-dashboard)
- [Repository Structure](#repository-structure)
- [Canonical Data Schemas](#canonical-data-schemas)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Configuration](#environment-configuration)
  - [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Roadmap](#roadmap)

---

## Platform Overview

Students learn at different paces and struggle with different conceptual prerequisites. Traditional education delivers one-size-fits-all lectures and static textbooks, leaving foundational gaps unresolved.

**VisualAI** bridges this gap through an end-to-end automated pipeline:
1. **Understands what is taught**: Ingests multimodal textbooks, notes, slides, diagrams, and recorded lecture videos into authoritative facts, concepts, and dependency graphs (**Step 1**).
2. **Diagnoses what each student knows**: Dynamically generates grounded, provenance-anchored diagnostic quizzes, tracks mastery, detects root prerequisite failures, and stops infinite failure loops with an anti-loop kill switch (**Step 2**).
3. **Generates targeted instructional videos**: Synthesizes bite-sized, scene-by-scene remedial video lessons scaled by difficulty (30s foundational, 45s intermediate, 60s advanced) addressing only the concepts the student failed (**Step 3 — Blueprint Generated**).
4. **Interactive In-Video Chat**: Answers student questions in real-time during video playback grounded in the source video and document text (**Step 4 — In Design**).

---

## System Architecture

```
STUDY MATERIALS (PDF, Images, TXT, Lecture Videos)
   │
   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STEP 1: MULTIMODAL INGESTION & KNOWLEDGE ENGINE                        │
├────────────────────────────────────────────────────────────────────────┤
│ • Modality Dispatcher (PyMuPDF blocks, OCR / Vision, FFmpeg + Whisper) │
│ • Speech-Visual Timeline Fusion & ContentUnit Normalization            │
│ • Hierarchical Structure Detection (Chapters / Sections)               │
│ • Conceptual Knowledge Graph & Prerequisite DAG Construction           │
│ • Concept-Aware Semantic Chunking (RichChunks)                         │
│ • 5-Layer Quality Validation Gateway                                   │
│ • Qdrant Vector Storage (Layer A: Authoritative Ground Truth)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                         source_id  │  KnowledgeGraph
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STEP 2: DIAGNOSTIC ASSESSMENT & KNOWLEDGE PROFILING                    │
├────────────────────────────────────────────────────────────────────────┤
│ • Adaptive Assessment Planner (30% Foundational, 40% Mid, 30% Adv)     │
│ • Prerequisite Pairing DAG Traversal                                   │
│ • Grounded Question Generation (Gemini API / Local Ollama / Mock)      │
│ • Validation Gateway: Grounding overlap & Duplicate suppression        │
│ • Hidden Answer Key Isolation (SafeQuestion contract)                  │
│ • Submission Grading & False-Mastery Defense (consecutive passes)      │
│ • Anti-Loop Kill Switch (>3 failures -> REQUIRES_HUMAN_FALLBACK)       │
│ • StudentLearningProfile Persistence                                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STEP 3 HANDOFF: VIDEO TARGET MATRIX (storage/video_targets/)           │
├────────────────────────────────────────────────────────────────────────┤
│ • Targets only UNMASTERED concepts (filters out MASTERED & Kill Switch)│
│ • Duration Scaling: Foundational (30s) | Mid (45s) | Advanced (60s)    │
│ • Exact source provenance (ContentUnits, keyframes, audio timestamps)  │
│ • Feed-forward contract into Automated Video Synthesis Engine          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Step 1: Multimodal Ingestion & Knowledge Extraction

- **Universal Modality Dispatcher**:
  - **Documents (PDF, TXT)**: PyMuPDF block extraction preserving bounding boxes (`bbox`), page numbers, and embedded diagram extraction.
  - **Images (PNG, JPG, JPEG)**: Gemini Vision multimodal prompt analysis extracting formulas, structural hierarchy, and diagram semantics.
  - **Recorded Lectures (MP4, MOV, MKV)**:
    - FFmpeg audio ripping to 16kHz mono 16-bit PCM WAV.
    - Faster-Whisper ASR with word- and segment-level timestamps.
    - OpenCV keyframe extraction with 32×32 grayscale perceptual duplicate suppression (<4% visual variance skipped).
    - Speech-visual timeline fusion into canonical `ContentUnit` records.
- **Canonical `ContentUnit` Abstraction**: Single unified schema representing any visual, textual, or auditory element with precise page/timestamp provenance.
- **Knowledge Graph & Prerequisite DAG**: Automatically builds conceptual dependency trees (`ConceptNode`) identifying parent-child relationships and prerequisite chains.
- **Layer A Vector Storage**: Concept-aware semantic chunks (`RichChunk`) embedded via `gemini-embedding-2` (or local fallback) and isolated in Qdrant under `layer: "A"`.

### Step 2: Diagnostic Assessment & Knowledge Profiling

- **Intelligent Assessment Planner**:
  - Balanced cold-start distribution (30% foundational, 40% intermediate, 30% advanced).
  - Prerequisite pairing: when testing complex concepts, ensures prerequisite dependencies are evaluated simultaneously.
- **Strict Grounding & Hallucination Defense**:
  - Every question is generated from source-isolated Qdrant chunks (`source_id`).
  - Validation Gateway verifies 4 distinct choices, valid single correct answer, and token overlap with the authoritative source text.
  - Reserve candidate pool automatically backfills any failed questions to guarantee requested test length.
- **Hidden Answer Key Security**:
  - Question bank is partitioned into internal `DiagnosticQuestion` (with reasoning and answer keys) and student-facing `SafeQuestion` (options only, zero leakage).
- **Anti-Loop Kill Switch**:
  - Consecutive failures (>3 attempts on the same concept) automatically trigger `REQUIRES_HUMAN_FALLBACK`.
  - Halts automated re-quizzing and video generation for that concept, routing it directly to the **Instructor Portal**.
- **Student Learning Profile**: Tracks per-concept mastery state (`UNTESTED`, `IN_PROGRESS`, `MASTERED`, `REQUIRES_HUMAN_FALLBACK`), streak counts, and diagnostic history.

### Instructor Analytics & Governance

- **Cohort Mastery Analytics**: View aggregate mastery distribution across all students for any course or textbook.
- **Concept Gap Heatmaps**: Identify cohort-wide stumbling blocks and prerequisite bottlenecks.
- **Kill-Switch Alert Management**: Real-time alerts when a student hits the kill switch, complete with source context, failure history, and resolution actions.
- **Curriculum Alignment**: Inspect source documents, extracted concepts, and question banks.

### Video Target Matrix (Step 3 Blueprint)

Step 2 directly produces the production-ready contract for downstream video generation:
- Filters out mastered concepts and kill-switch exceptions.
- Computes target video durations scaled by conceptual difficulty:
  - **Foundational Concepts**: `30 seconds`
  - **Intermediate Concepts**: `45 seconds`
  - **Advanced Concepts**: `60 seconds`
- Provides exact source references (`content_ids`, `keyframes`, `timestamps`, `text_snippets`) for automated scriptwriters and animation renderers.

---

## Interactive Web Dashboard

VisualAI includes a modern, responsive web dashboard served directly at the root URL (`http://127.0.0.1:8000/`):

- **Live Document & Lecture Ingestion**: Drag-and-drop upload for PDFs, images, and videos with real-time processing status.
- **Knowledge Graph Explorer**: Interactive visualization of extracted concepts, difficulty tiers, and prerequisite dependencies.
- **Interactive Quiz Interface**: Clean student test-taking view with real-time submission, instant grading, and diagnostic explanations.
- **Learning Profile Inspector**: Real-time visualization of student mastery progress and concept streaks.
- **Video Target Matrix Viewer**: Inspect the generated blueprints ready for video rendering.

---

## Repository Structure

```
AI-VIDEO-GENERATOR/
├── app/
│   ├── api/
│   │   ├── upload.py              # POST /upload (Step 1 pipeline + auto-handoff)
│   │   ├── assessment.py          # Step 2 Assessment & Profiling endpoints
│   │   ├── dashboard.py           # Embedded Single-Page Web Dashboard (/)
│   │   ├── instructor.py          # Instructor analytics & kill-switch governance
│   │   └── pipeline.py            # Pipeline observability & execution stats
│   ├── core/
│   │   └── config.py              # Central Settings & environment configuration
│   ├── db/
│   │   └── vector_store.py        # Qdrant client, Layer A upsert & embedding
│   ├── services/
│   │   ├── schemas.py             # Step 1 schemas (ContentUnit, RichChunk, KG)
│   │   ├── registry.py            # File hashing, versioning & artifact store
│   │   ├── dispatcher.py          # Modality router (PDF, image, text, video)
│   │   ├── extractor.py           # PyMuPDF block extractor + vision hook
│   │   ├── vision.py              # Gemini Vision API wrapper
│   │   ├── structurer.py          # Structure detection & KnowledgeGraph builder
│   │   ├── chunker.py             # Concept-aware semantic chunking
│   │   ├── validator.py           # Step 1 5-layer Quality Gateway
│   │   ├── pipeline_tracker.py    # Pipeline progress tracking & observability
│   │   ├── storage.py             # Central storage & path manager
│   │   ├── assessment/            # Step 2 Assessment Subsystem
│   │   │   ├── schemas.py         # Session, Question, Profile, VideoTarget schemas
│   │   │   ├── planner.py         # Cold-start & prerequisite DAG planner
│   │   │   ├── generator.py       # Source-isolated grounded question generator
│   │   │   ├── providers.py       # LLM provider protocol (Gemini, Ollama, Mock)
│   │   │   ├── validator.py       # Grounding overlap & option validator
│   │   │   ├── engine.py          # Grading engine, anti-loop kill switch
│   │   │   ├── profile.py         # Student learning profile manager
│   │   │   ├── session_store.py   # Assessment session state store
│   │   │   └── video_target.py    # VideoTargetMatrix generator & handoff
│   │   └── video/                 # Video Ingestion Subsystem
│   │       ├── av_splitter.py     # FFmpeg audio track separator
│   │       ├── transcriber.py     # Faster-Whisper ASR engine
│   │       ├── frame_extractor.py # OpenCV keyframe sampling & deduplication
│   │       ├── fusion.py          # Speech-visual timeline alignment
│   │       └── pipeline.py        # Video ingestion pipeline orchestrator
│   └── main.py                    # FastAPI app entrypoint & middleware
├── storage/                       # Local persistent data directory
│   ├── uploads/                   # Original source files
│   ├── registry/                  # Source records, ContentUnits & KnowledgeGraphs
│   ├── processed/                 # Extracted audio & cached frames
│   ├── assessment_sessions/       # Step 2 active session snapshots
│   ├── learning_profiles/         # Student mastery profiles
│   ├── video_targets/             # Step 3 VideoTargetMatrix JSON contracts
│   └── qdrant/                    # In-process embedded Qdrant database
├── docs/                          # Architecture & technical documentation
├── tests/                         # Automated test suite (Steps 1 & 2)
├── run.py                         # Cross-platform runner with safe directory watch
├── run_step1_step2_ollama.py      # Standalone runner using local Ollama models
├── start.bat                      # Windows one-click starter
├── start.sh                       # Linux / macOS starter
├── Makefile                       # Cross-platform development tasks
├── Dockerfile                     # Container deployment image
├── docker-compose.yml             # API + Qdrant service configuration
├── requirements.txt               # Pinned Python dependencies
└── .env.example                   # Environment configuration template
```

---

## Canonical Data Schemas

### 1. `ContentUnit` (Canonical Source of Truth)
Unified atomic representation across all input modalities:
```json
{
  "content_id": "CU_8f72a910bc42",
  "source_id": "SRC_1138d072e1a6",
  "asset_id": "AST_b39cdc457a4f",
  "modality": "pdf",
  "text": "Newton's Second Law states that force equals mass times acceleration (F=ma)...",
  "visual_description": "Free-body diagram of a 5kg block accelerating on a frictionless plane",
  "page_number": 15,
  "sequence_index": 42,
  "chapter": "Mechanics",
  "section": "Newton's Laws",
  "bbox": [54.0, 120.0, 400.0, 250.0],
  "confidence_score": 0.95
}
```

### 2. `RichChunk` (Qdrant Vector Payload)
RAG-ready chunk with concept mapping and authoritative Layer A tag:
```json
{
  "chunk_id": "CHUNK_a2b2ff0e938f",
  "source_id": "SRC_1138d072e1a6",
  "layer": "A",
  "type": "rich_chunk",
  "text": "When a net external force acts on an object, it accelerates in the direction of the force...",
  "modality": "pdf",
  "concept_ids": ["CONCEPT_NEWTON_2", "CONCEPT_INERTIA"],
  "content_ids": ["CU_8f72a910bc42"],
  "page_start": 15,
  "page_end": 15
}
```

### 3. `VideoTargetMatrix` (Step 3 Video Generation Blueprint)
Direct input contract for automated video generation:
```json
{
  "student_id": "student_101",
  "source_id": "SRC_1138d072e1a6",
  "total_target_seconds": 75,
  "targets": [
    {
      "concept_id": "CONCEPT_NEWTON_2",
      "concept_name": "Newton's Second Law",
      "difficulty": "foundational",
      "target_duration_seconds": 30,
      "failed_question_ids": ["Q_01"],
      "prerequisite_gaps": ["CONCEPT_VECTORS"],
      "provenance_chunk_ids": ["CHUNK_a2b2ff0e938f"]
    },
    {
      "concept_id": "CONCEPT_MOMENTUM",
      "concept_name": "Conservation of Linear Momentum",
      "difficulty": "intermediate",
      "target_duration_seconds": 45,
      "failed_question_ids": ["Q_04"],
      "prerequisite_gaps": [],
      "provenance_chunk_ids": ["CHUNK_c91d8e02fa11"]
    }
  ]
}
```

---

## Getting Started

### Prerequisites

1. **Python 3.10+** (64-bit recommended)
2. **FFmpeg**: Required on your system `PATH` for processing lecture videos (audio track separation).
3. **LLM Access** (choose one):
   - **Google Gemini API Key** (default cloud provider)
   - **Ollama** running locally with `llama3.2` or `mistral` (zero cloud cost)
   - **Mock Provider** (for offline testing without external dependencies)
4. **Qdrant** (Optional):
   - VisualAI automatically falls back to an **embedded in-process Qdrant** database (`storage/qdrant/`) if Docker is not running.

---

### Environment Configuration

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Key configuration options in `.env`:

```ini
# --- LLM Provider Selection ---
LLM_PROVIDER=gemini                  # Options: gemini | ollama | mock
GEMINI_API_KEY=your_gemini_key_here  # Required if LLM_PROVIDER=gemini
GENERATION_MODEL=gemini-3.5-flash
EMBEDDING_MODEL=models/gemini-embedding-2

# --- Local Ollama Configuration (if LLM_PROVIDER=ollama) ---
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# --- Vector Database ---
QDRANT_URL=http://localhost:6333     # Falls back to embedded if unreachable
COLLECTION_NAME=visualai_layer_a

# --- Step 2 Assessment & Pedagogical Rules ---
MAX_QUESTIONS=10
MASTERY_THRESHOLD=2                  # Consecutive passes required for MASTERED
KILL_SWITCH_LIMIT=3                  # Failures before triggering REQUIRES_HUMAN_FALLBACK
ASSESSMENT_TTL_HOURS=24
```

---

### Running the Application

#### Option A: Quickstart Scripts

- **Windows**:
  ```powershell
  .\start.bat
  ```
- **Linux / macOS**:
  ```bash
  chmod +x start.sh
  ./start.sh
  ```

#### Option B: Using Python Runner (Cross-Platform)

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch server with safe auto-reload
python run.py
```

#### Option C: Docker Compose

```bash
docker compose up -d --build
```

#### Option D: Standalone Local Ollama Pipeline

To run an end-to-end extraction and assessment flow entirely offline using local Ollama models:
```bash
python run_step1_step2_ollama.py
```

---

## API Reference

### Upload & Ingestion (Step 1)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/upload` | Ingest PDF, Image, TXT, or Video. Builds Knowledge Graph and indexes to Qdrant Layer A. Supports optional `auto_start_assessment=true`. |
| `GET` | `/sources` | List all registered sources, status (`READY`, `PROCESSING`), and concept counts. |

### Assessment & Profiling (Step 2)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/assessment/start` | Initialize an adaptive diagnostic assessment session for a student. Returns `SafeQuestion` objects. |
| `POST` | `/assessment/submit` | Submit answers for grading. Updates `StudentLearningProfile`, checks kill switch, and evaluates prerequisite gaps. |
| `GET` | `/assessment/profile/{student_id}/{source_id}` | Retrieve real-time concept mastery status, streak counts, and learning history. |
| `GET` | `/assessment/video-target/{student_id}/{source_id}` | Retrieve or generate the `VideoTargetMatrix` blueprint for downstream video rendering. |
| `GET` | `/assessment/status/{session_id}` | Check active assessment session state and expiration TTL. |

### Instructor Portal & Governance

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/instructor/cohort/summary` | Cohort-wide mastery metrics, total assessments, and active alerts. |
| `GET` | `/instructor/alerts` | List all active kill-switch human intervention alerts (`REQUIRES_HUMAN_FALLBACK`). |
| `POST` | `/instructor/alerts/{alert_id}/resolve` | Mark an alert as resolved after instructor intervention. |
| `GET` | `/instructor/cohort/heatmap` | Per-concept breakdown of mastered, in-progress, and failed students. |

### Observability & System Diagnostics

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Single-Page Web Dashboard interface. |
| `GET` | `/health` | System health check reporting active service capabilities. |
| `GET` | `/pipeline/status/{task_id}` | Real-time stage tracker for long-running document/video processing tasks. |
| `GET` | `/pipeline/stats` | Pipeline execution throughput and stage latency statistics. |
| `GET` | `/docs` | Interactive Swagger UI API documentation. |
| `GET` | `/debug/qdrant` | Vector collection point counts and payload diagnostics (`VISUALAI_DEBUG=true`). |

---

## Testing & Quality Assurance

VisualAI includes comprehensive test suites covering all phases:

```bash
# Run the entire test suite
pytest tests/ -v

# Run Step 1 ingestion tests
pytest tests/test_step1.py -v

# Run Step 2 assessment contracts & grading tests
pytest tests/test_step2.py tests/test_step2_scoring_contract.py -v

# Run phase-specific validation suites
pytest tests/test_step2_fulfillment.py tests/test_step2_phase2b.py tests/test_step2_phase4.py -v

# Run instructor portal and pipeline observability tests
pytest tests/test_instructor_portal.py tests/test_pipeline_observability.py -v

# Run End-to-End ingestion test using a real PDF document
python tests/test_e2e_real_pdf_run.py
```

Using the `Makefile`:
```bash
make test         # Run complete test suite
make test-core    # Fast run of core integration tests
make audit        # Dependency security audit
```

---

## Roadmap

- [x] **Step 1: Multimodal Ingestion & Knowledge Graph**
  - PyMuPDF text & bounding box extraction
  - Multimodal Gemini Vision for complex diagrams
  - Video pipeline: FFmpeg audio rip + faster-whisper ASR + OpenCV keyframes + timeline fusion
  - Knowledge graph prerequisite mapping
  - Qdrant Layer A authoritative vector storage
- [x] **Step 2: Diagnostic Assessment & Knowledge Profiling**
  - Adaptive cold-start planning (30/40/30 distribution)
  - Grounded question generation with grounding validation
  - Anti-loop kill switch (>3 failures flags `REQUIRES_HUMAN_FALLBACK`)
  - Pluggable LLM providers (Gemini, local Ollama, Mock)
  - Student learning profile tracking & hidden answer key safety
  - `VideoTargetMatrix` handoff contract generation
- [x] **Web Dashboard & Instructor Portal**
  - Embedded interactive web console at `/`
  - Cohort analytics, mastery heatmaps, and kill-switch resolution workflows
- [ ] **Step 3: Automated Remedial Video Generation**
  - Scene-by-scene instructional scriptwriter consuming `VideoTargetMatrix`
  - Neural text-to-speech (TTS) voiceover synthesizer
  - Programmatic visual scene rendering (diagram animations, dynamic motion graphics)
  - Audio/video multiplexing and final video rendering pipeline
- [ ] **Step 4: Interactive Video RAG Agent**
  - Real-time in-video conversational assistant
  - Timestamp-accurate video seeking and question answering
- [ ] **Enterprise Features**
  - Multi-tenant student/organization isolation
  - LMS integration (LTI 1.3, Canvas, Moodle)