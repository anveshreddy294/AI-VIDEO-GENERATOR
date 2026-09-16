# VisualAI

**Step 1: Multimodal Ingestion & Verification — Layer A Population**

VisualAI ingests student study materials — **documents** (PDF, PNG, JPG, TXT) **and recorded lectures** (MP4, MOV, MKV) — extracts text and diagram descriptions via vision AI, structures the knowledge into a topic blueprint, and locks everything into a RAG vector store tagged as **Layer A** (authoritative ground truth). Lecture chunks carry clock timestamps so retrieval can point students at the exact 30-second window of the source recording.

## Architecture (Layer A)

```
Student File
    │  (multipart/form-data POST /upload)
    ▼
API Gateway (FastAPI)
    │  validate extension → save temp
    ▼
Extraction Engine (Dispatcher)
    ├─ PDF     → PyMuPDF (raw text + embedded image cropping)
    ├─ Image   → direct bytes → Gemini Vision API
    ├─ TXT     → raw text passthrough
    └─ Video   → VIDEO MATRIX (below)
    ▼
Knowledge Structuring (LLM)
    └─ Topic JSON blueprint
       { topic_name, key_concepts[], prerequisites[], difficulty_level }
    ▼
Layer A RAG Sync
    ├─ Recursive splitter → 1000-token overlapping chunks
    ├─ Tag: layer=A, type=authoritative_source | authoritative_video
    └─ Embed + upsert → Qdrant collection

═══════════ VIDEO MATRIX (mp4 / mov / mkv) ═══════════
Phase 1  FFmpeg ────────────── audio track (16kHz mono WAV) ──┐
         (original video kept for visuals)                   │
Phase 2  faster-whisper ────── timestamped transcript  ──────┤
Phase 3  OpenCV (frame/12s) ── Gemini Vision descriptions ───┤
Phase 4  Fusion engine ─────── chronological merge ──────────┘
         [01:15 - 01:30] Spoken: "..." | Visible on screen: "..."
Phase 5  chunker → layer=A, type=authoritative_video,
         start_timestamp, end_timestamp → Qdrant
```

## Project Structure

```
VisualAI/
├── app/
│   ├── api/
│   │   └── upload.py          # POST /upload entry point
│   ├── core/
│   │   └── config.py          # Env config, allowed extensions
│   ├── db/
│   │   └── vector_store.py    # Qdrant upsert logic
│   ├── services/
│   │   ├── dispatcher.py      # File-type router logic
│   │   ├── extractor.py       # PyMuPDF text + image cropping
│   │   ├── vision.py          # Gemini Vision API calls (diagrams + frames)
│   │   ├── structurer.py      # Topic JSON blueprint w/ Pydantic
│   │   ├── chunker.py         # Recursive splitting (page + clock tags)
│   │   └── video/             # The Video Matrix
│   │       ├── av_splitter.py     # Phase 1: FFmpeg audio rip
│   │       ├── transcriber.py     # Phase 2: faster-whisper timestamps
│   │       ├── frame_extractor.py # Phase 3: OpenCV keyframes + dedupe
│   │       ├── fusion.py          # Phase 4: speech × visuals merge
│   │       └── pipeline.py        # Orchestrator entry point
│   └── main.py                # FastAPI app entry
├── storage/
│   ├── uploads/               # Temp validated uploads
│   └── processed/             # Authoritative source strings + JSON
├── .env.example
└── requirements.txt
```

## Core Libraries

- **FastAPI** — upload endpoint / lifecycle
- **PyMuPDF (fitz)** — text + image extraction from PDFs
- **google-generativeai** — Gemini Vision + LLM structuring
- **langchain-text-splitters** — recursive character splitting
- **qdrant-client** — vector storage & retrieval (Layer A)
- **FFmpeg** (system) — audio-track rip for the Video Matrix (`brew install ffmpeg`)
- **faster-whisper** — offline, CPU-friendly timestamped transcription
- **opencv-python** — keyframe sampling from lecture videos

## Quickstart

```bash
cd VisualAI
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
uvicorn app.main:app --reload
```

Then upload a file:

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@physics_chapter_4.pdf"
```

## The Locked Ground-Truth Payload

Every chunk upserted to the vector DB is tagged so downstream agents can never confuse Layer A truth with generated content:

**Document chunk** — located by *page*:

```json
{
  "layer": "A",
  "type": "authoritative_source",
  "document_name": "physics_chapter_4.pdf",
  "text": "[chunked text...]",
  "page": 4
}
```

**Video chunk** — located by *clock window*, so a student question can point to the exact moment in the recording:

```json
{
  "layer": "A",
  "type": "authoritative_video",
  "video_name": "lecture_4.mp4",
  "start_timestamp": "01:15",
  "end_timestamp": "01:45",
  "text": "[01:15 - 01:45] Spoken: \"...\" | Visible on screen: \"...\""
}
```

The two shapes are enforced by a Pydantic discriminated union — a document chunk literally cannot carry video metadata and vice versa.

## Video Tuning (env)

| Variable | Default | Meaning |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `base` | faster-whisper model (`tiny`…`large-v3`); bigger = slower but more accurate |
| `FRAME_INTERVAL_SECONDS` | `12` | Keyframe sampling rate for the vision pipeline |
| `VIDEO_FRAME_SIMILARITY_THRESHOLD` | `0.04` | Below this mean pixel diff, a frame is treated as a duplicate and skipped (saves Gemini calls on static slides) |