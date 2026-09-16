# VisualAI

**Step 1: Multimodal Input, Ingestion, Normalization & Knowledge Preparation**

VisualAI ingests student study materials — **documents** (PDF, PNG, JPG, TXT) and **recorded lectures** (MP4, MOV, MKV) — normalizes all modalities into canonical `ContentUnit` abstractions, extracts structured concepts and prerequisite relationships into a persistent **Knowledge Graph**, and locks provenanced chunks into Qdrant vector storage tagged as **Layer A** (authoritative ground truth).

---

## Step 1 Complete Architecture

```
STUDENT
  │
  ▼
┌─────────────────────────────┐
│ 1. Upload / Input Interface │
│ PDF / Image / TXT / Video   │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 2. File Validation          │
│ Extension / MIME / Hash     │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 3. File Registration        │
│ source_id / asset_id        │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 4. Modality Dispatcher      │
│ PDF / Image / TXT / Video   │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 5. Modality Extraction      │
│ text / OCR / vision / audio │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 6. ContentUnit Normalization│
│ Canonical ContentUnit model │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 7. Structure Detection      │
│ chapter/section hierarchy   │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 8. Concept Extraction       │
│ concepts / prerequisites    │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 9. Semantic Chunking        │
│ concept-aware RichChunks    │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 10. Provenance Mapping      │
│ source → CU → chunk → concept│
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 11. Quality Validation      │
│ 5-layer Quality Gateway     │
└──────────────┬──────────────┘
               ▼
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌────────────────┐
│ Qdrant      │  │ Knowledge Graph│
│ RichChunks  │  │ concept nodes  │
└─────────────┘  └────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 12. Persistent Registry     │
│ status = READY              │
└─────────────────────────────┘
```

---

## Project Structure

```
AI-VIDEO-GENERATOR/
├── app/
│   ├── api/
│   │   └── upload.py          # POST /upload Step 1 pipeline endpoint
│   ├── core/
│   │   └── config.py          # Environment settings & thresholds
│   ├── db/
│   │   └── vector_store.py    # Qdrant vector store & payload upsert
│   ├── services/
│   │   ├── registry.py        # Source registration, hashing, versioning, storage
│   │   ├── schemas.py         # ContentUnit, SourceRecord, ConceptNode, RichChunk
│   │   ├── dispatcher.py      # Modality router logic
│   │   ├── extractor.py       # PDF block + image vision extractor
│   │   ├── vision.py          # Gemini Vision API wrappers
│   │   ├── structurer.py      # Structure detection & KnowledgeGraph generator
│   │   ├── chunker.py         # Concept-aware semantic chunking
│   │   ├── validator.py       # Quality Validation Gateway
│   │   └── video/             # Video Matrix pipeline
│   │       ├── av_splitter.py     # FFmpeg audio track rip
│   │       ├── transcriber.py     # faster-whisper ASR with timestamps
│   │       ├── frame_extractor.py # OpenCV keyframe sampling & deduplication
│   │       ├── fusion.py          # Speech × visual fusion into ContentUnits
│   │       └── pipeline.py        # Video pipeline orchestrator
│   └── main.py                # FastAPI application entry
├── storage/
│   ├── uploads/               # Persistent source files ({source_id}/original.<ext>)
│   ├── registry/              # Source records, ContentUnits & KnowledgeGraphs
│   ├── processed/             # Audio tracks & extraction output cache
│   └── qdrant/                # Embedded local vector DB (zero-Docker fallback)
├── start.bat                  # One-click Windows starter script
├── test_step1.py              # Step 1 verification test suite
├── .env.example
└── requirements.txt
```

---

## Canonical Data Models

### 1. `ContentUnit` (Canonical Source of Truth)
Unified output schema across all input modalities:
```json
{
  "content_id": "CU_8f72a910bc42",
  "source_id": "SRC_1138d072e1a6",
  "asset_id": "AST_b39cdc457a4f",
  "modality": "pdf",
  "text": "Force is defined as an interaction...",
  "visual_description": "Diagram of block on incline with force vectors",
  "page_number": 15,
  "sequence_index": 42,
  "chapter": "Mechanics",
  "section": "Force and Acceleration",
  "bbox": [54.0, 120.0, 400.0, 250.0],
  "region_id": "REG_15_1",
  "image_id": "IMG_15_201",
  "extraction_method": "pymupdf_block",
  "confidence_score": 0.95
}
```

### 2. `RichChunk` (Qdrant Vector Payload)
Provenanced RAG chunk stored with `layer: "A"` security tag:
```json
{
  "chunk_id": "CHUNK_a2b2ff0e938f",
  "source_id": "SRC_1138d072e1a6",
  "asset_id": "AST_b39cdc457a4f",
  "layer": "A",
  "type": "rich_chunk",
  "text": "[chunk text]",
  "modality": "pdf",
  "chapter": "Mechanics",
  "section": "Newton's Laws",
  "concept_ids": ["CONCEPT_FORCE", "CONCEPT_NEWTON_2"],
  "content_ids": ["CU_0d7444c2d8cf", "CU_cc4d6bfc1f2d"],
  "page_start": 15,
  "page_end": 16,
  "extraction_method": "pymupdf_block"
}
```

---

## Quickstart

### Method 1: Using `start.bat` (Windows)
```powershell
cd "d:\ai video generation\AI-VIDEO-GENERATOR"
.\start.bat
```

### Method 2: Manual Python Execution
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Add your GEMINI_API_KEY
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **FastAPI API Server**: `http://127.0.0.1:8000`
- **Swagger Interactive Docs**: `http://127.0.0.1:8000/docs`

---

## Running Verification Tests

To verify the complete Step 1 ingestion pipeline:
```bash
python test_step1.py
```