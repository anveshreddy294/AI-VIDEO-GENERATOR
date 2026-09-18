# STEP3_SPECIFICATION.md — Targeted AI Video Generation Engine

## 1. Executive Summary & Objective

The **Targeted AI Video Generation Engine (Step 3)** transforms diagnostic remediation targets from Step 2 into personalized, pedagogically structured, bite-sized instructional videos.

When a student fails diagnostic questions during an assessment, Step 2 produces a [`VideoTargetMatrix`](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/assessment/schemas.py) containing specific concepts that require video intervention. Step 3 consumes this matrix, retrieves authoritative source text and diagram assets from Step 1, generates a timed multi-scene script, synthesizes voiceover audio, renders animated visual cards, and compiles a final broadcast-quality MP4 video.

---

## 2. Core Architectural Principles & Guardrails

1. **Strict Duration Compliance**:
   - **Foundational Concepts**: **30 seconds** (±2s tolerance).
   - **Intermediate Concepts**: **45 seconds** (±3s tolerance).
   - **Advanced Concepts**: **60 seconds** (±3s tolerance).
2. **Pedagogical Structure (The 3-Act Micro-Lesson)**:
   - **Act 1: Hook & Core Intuition** (15–20% of duration): Clear statement of the concept and why it matters.
   - **Act 2: Mechanical Breakdown & Evidence** (60–70% of duration): Step-by-step explanation using authoritative textbook diagrams, definitions, or equations from Step 1.
   - **Act 3: Takeaway & Mental Anchor** (15–20% of duration): Summary rule or heuristic to prevent future quiz mistakes.
3. **Zero Hallucination & Strict Provenance**:
   - All visual assets, formulas, and assertions must directly originate from the source [`ContentUnit`](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/schemas.py) records and [`RichChunk`](file:///d:/ai%20video%20generator/AI-VIDEO-GENERATOR/app/services/schemas.py) models mapped in the `VideoTarget`.
4. **Human Intervention Exclusion**:
   - Concepts marked in `human_intervention_concepts` (from the Step 2 anti-loop kill switch) are **never** processed by the automated video generator.
5. **Deterministic Offline Fallback**:
   - If Cloud TTS or LLM APIs are unavailable or rate-limited, the engine must support deterministic script templating and offline audio/visual synthesis to guarantee zero system crashes during tests.

---

## 3. Step 3 Data Contracts (`app/services/video_gen/schemas.py`)

### 3.1 Scene Schema (`VideoScene`)
```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class VideoScene(BaseModel):
    scene_number: int = Field(ge=1, description="Sequential scene index (1-based)")
    scene_type: Literal[
        "title_hook",           # Intro card with concept name & core question
        "concept_breakdown",    # Key definition and bullet points
        "diagram_focus",        # Cropped textbook figure with visual callout
        "formula_derivation",   # Mathematical equation or law breakdown
        "summary_takeaway"      # Final mental anchor / review
    ]
    title: str = Field(..., max_length=60, description="On-screen scene title")
    narration: str = Field(..., description="Voiceover spoken narration text")
    onscreen_bullets: List[str] = Field(default_factory=list, max_items=4, description="On-screen bullet points")
    highlight_text: Optional[str] = Field(None, description="Key formula or term to emphasize")
    diagram_cu_id: Optional[str] = Field(None, description="ContentUnit ID of source diagram/image if applicable")
    duration_seconds: float = Field(gt=0.0, description="Target duration for this scene in seconds")
```

### 3.2 Video Script Schema (`VideoScript`)
```python
class VideoScript(BaseModel):
    video_id: str
    student_id: str
    source_id: str
    concept_id: str
    concept_name: str
    difficulty: Literal["foundational", "intermediate", "advanced"]
    target_total_seconds: int = Field(..., description="Exact duration constraint (30, 45, or 60)")
    scenes: List[VideoScene]
    estimated_word_count: int
    source_chunk_ids: List[str] = Field(default_factory=list)
```

### 3.3 Video Render Status (`VideoRenderJob`)
```python
class VideoRenderJob(BaseModel):
    job_id: str
    video_id: str
    student_id: str
    concept_id: str
    status: Literal[
        "pending",
        "generating_script",
        "synthesizing_voiceover",
        "rendering_visuals",
        "muxing_media",
        "completed",
        "failed"
    ]
    progress_percent: int = Field(ge=0, le=100, default=0)
    video_file_path: Optional[str] = None
    subtitles_file_path: Optional[str] = None
    error_message: Optional[str] = None
```

---

## 4. Subsystem Components & Processing Pipeline

The Step 3 engine is composed of five distinct modules under `app/services/video_gen/`:

```
              ┌────────────────────────────────────────────────────────┐
              │           Step 2: VideoTargetMatrix JSON               │
              │ (Target duration: 30s/45s/60s, concept_id, chunk_ids)  │
              └───────────────────────────┬────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. SCRIPT GENERATION SERVICE (app/services/video_gen/script.py)                       │
│ - Fetches source ContentUnits and diagrams from storage/registry/{source_id}/          │
│ - Prompts Gemini / Ollama / Mock with word-budget constraints (approx 2.5 words/sec)  │
│ - Generates validated VideoScript schema with 3-5 distinct scenes                      │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. VOICEOVER SYNTHESIZER (app/services/video_gen/tts.py)                               │
│ - Uses Microsoft Edge Neural TTS (edge-tts) for high-fidelity spoken audio             │
│ - Outputs per-scene WAV files: scene_1.wav, scene_2.wav, etc.                          │
│ - Measures exact audio durations to dynamically calibrate scene visual timings        │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. VISUAL COMPOSITION ENGINE (app/services/video_gen/visuals.py)                       │
│ - Renders 1080p (1920x1080) high-contrast, modern dark-mode frames (Pillow + OpenCV) │
│ - Displays: animated header gradient, bullet points, callout badges, source diagrams  │
│ - Generates image sequence or lossless video stream for each scene                     │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. AUDIO-VISUAL MUXER & SUBTITLER (app/services/video_gen/muxer.py)                   │
│ - Combines scene video frames with synchronized voiceover audio                        │
│ - Generates burned-in or WebVTT subtitles synchronized with narration                  │
│ - Exports final web-optimized MP4 (H.264 / AAC) to storage/videos/                     │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. API & DASHBOARD INTEGRATION (app/api/video.py + app/api/dashboard.py)               │
│ - POST /video/generate (triggers generation in background)                             │
│ - GET /video/{video_id}/status (polls render status)                                   │
│ - GET /video/{video_id}/stream (streams MP4 video for HTML5 playback)                  │
│ - Interactive video player modal embedded in Web Dashboard                             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technology Choices & Rationale

| Layer | Selected Tool | Rationale | Fallback Strategy |
| :--- | :--- | :--- | :--- |
| **Script Generation** | Gemini 3.5 Flash / Ollama | Highly accurate structured JSON output adhering to word counts | Deterministic template-based script generator from `ContentUnit` |
| **Voiceover TTS** | `edge-tts` | Free, zero API key required, neural quality voices (`en-US-GuyNeural`, `en-US-JennyNeural`) | Offline PCM WAV tone / silent timing generator for testing |
| **Visual Rendering** | Pillow (`PIL`) + OpenCV (`cv2`) | Native Python, already installed in workspace, zero external binary headache | Direct frame rendering to AVI/MP4 container |
| **Video Assembly** | `imageio-ffmpeg` / FFmpeg | Bundles standalone self-contained FFmpeg executable on Windows without system install | OpenCV `VideoWriter` + FFmpeg subprocess |

---

## 6. Target Directory & Artifact Structure

Generated videos and intermediate staging assets are persisted under `storage/runtime/videos/`:

```
storage/
└── runtime/
    ├── video_targets/
    │   └── {student_id}_{source_id}.json
    └── videos/
        ├── {video_id}/
        │   ├── script.json               # Generated VideoScript
        │   ├── audio/
        │   │   ├── scene_1.wav
        │   │   ├── scene_2.wav
        │   │   └── master_voiceover.wav
        │   ├── frames/                   # Rendered scene keyframes / visual assets
        │   │   └── scene_1_visual.png
        │   ├── subtitles.vtt             # WebVTT subtitle track
        │   └── final_video.mp4           # 1080p rendered remediation video
        └── videos_index.json             # Master index of all rendered student videos
```

---

## 7. Next Implementation Steps

1. **Step 3.1**: Create `app/services/video_gen/schemas.py` with Pydantic models for scripts, scenes, and render jobs.
2. **Step 3.2**: Implement `app/services/video_gen/script.py` (Script Generator with LLM prompt + deterministic fallback).
3. **Step 3.3**: Implement `app/services/video_gen/tts.py` (Voiceover Synthesizer with `edge-tts` and duration measurement).
4. **Step 3.4**: Implement `app/services/video_gen/visuals.py` (Pillow/OpenCV 1080p frame composition with dark mode styling).
5. **Step 3.5**: Implement `app/services/video_gen/muxer.py` and `pipeline.py` (Full rendering orchestrator).
6. **Step 3.6**: Create unit and integration test suite `test_step3_video_generation.py`.
7. **Step 3.7**: Expose REST API in `app/api/video.py` and embed HTML5 player in `app/api/dashboard.py`.
