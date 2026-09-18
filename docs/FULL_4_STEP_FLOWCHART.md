# VisualAI Platform — Complete 4-Step Continuous System Flowchart

> **Authoritative Technical Flowchart & Line-by-Line Execution Architecture**  
> Covering **Step 1 (Ingestion)**, **Step 2 (Assessment)**, **Step 3 (Video Generation)**, **Step 4 (Remediation Loop)**, plus **Interactive Video RAG**, **Instructor Portal**, and **Pipeline Telemetry**.

---

## Table of Contents
1. [Master End-to-End Pipeline Flowchart (Mermaid)](#1-master-end-to-end-pipeline-flowchart-mermaid)
2. [Step 1: Multimodal Ingestion & Knowledge Graph (Line-by-Line Flowchart)](#2-step-1-multimodal-ingestion--knowledge-graph-line-by-line-flowchart)
3. [Step 1 ➔ Step 2 Handoff Interface](#3-step-1--step-2-handoff-interface)
4. [Step 2: Diagnostic Assessment & Knowledge Profiling (Line-by-Line Flowchart)](#4-step-2-diagnostic-assessment--knowledge-profiling-line-by-line-flowchart)
5. [Step 2 ➔ Step 3 Handoff Interface](#5-step-2--step-3-handoff-interface)
6. [Step 3: Targeted AI Video Generation Engine (Line-by-Line Flowchart)](#6-step-3-targeted-ai-video-generation-engine-line-by-line-flowchart)
7. [Step 3 ➔ Step 4 Handoff Interface](#7-step-3--step-4-handoff-interface)
8. [Step 4: Remediation Verification & Re-Testing Loop (Line-by-Line Flowchart)](#8-step-4-remediation-verification--re-testing-loop-line-by-line-flowchart)
9. [Auxiliary Subsystems (Video RAG, Instructor Portal, Telemetry)](#9-auxiliary-subsystems-video-rag-instructor-portal-telemetry)
10. [Continuous Line-by-Line Code Symbol & Storage Matrix](#10-continuous-line-by-line-code-symbol--storage-matrix)

---

## 1. Master End-to-End Pipeline Flowchart (Mermaid)

```mermaid
flowchart TD
    classDef step1 fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff
    classDef step2 fill:#065f46,stroke:#10b981,stroke-width:2px,color:#fff
    classDef step3 fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff
    classDef step4 fill:#4c1d95,stroke:#8b5cf6,stroke-width:2px,color:#fff
    classDef aux fill:#374151,stroke:#9ca3af,stroke-width:2px,color:#fff
    classDef store fill:#1f2937,stroke:#6b7280,stroke-dasharray: 5 5,color:#93c5fd

    User([User / Student / Teacher]):::aux -->|Upload PDF, TXT, Image, Video| S1_Entry[POST /upload]:::step1

    subgraph SUB_STEP1["STEP 1: MULTIMODAL INGESTION & KNOWLEDGE EXTRACTION"]
        S1_Entry --> S1_Reg[File Registration & SHA-256 Checksum]:::step1
        S1_Reg --> S1_Disp{Modality Dispatcher}:::step1
        S1_Disp -->|PDF| S1_PDF[PyMuPDF Text Blocks & Bounding Boxes]:::step1
        S1_Disp -->|TXT| S1_TXT[Semantic Paragraph Segmentation]:::step1
        S1_Disp -->|Image| S1_IMG[Gemini Vision Diagram Description]:::step1
        S1_Disp -->|Video| S1_VID[FFmpeg 16kHz WAV + faster-whisper + OpenCV Frames + Temporal Fusion]:::step1
        S1_PDF & S1_TXT & S1_IMG & S1_VID --> S1_CU[Canonical ContentUnits JSON]:::step1
        S1_CU --> S1_KG[Gemini Structurer & Prerequisite DAG Extraction]:::step1
        S1_KG --> S1_Chunk[Concept-Aware Chunker: RichChunks Layer A]:::step1
        S1_Chunk --> S1_Vec[Gemini Vector Embeddings -> Qdrant Layer A]:::step1
        S1_Vec --> S1_Val[5-Tier Quality Validation Gateway]:::step1
        S1_Val --> S1_Ready[Status: READY in sources_index.json]:::step1
    end

    S1_Ready -->|source_id + auto_start_assessment=true| S2_Entry[POST /assessment/start]:::step2

    subgraph SUB_STEP2["STEP 2: DIAGNOSTIC ASSESSMENT & PROFILING"]
        S2_Entry --> S2_Plan[Dynamic Planner: 30% Foundational / 40% Intermediate / 30% Advanced]:::step2
        S2_Plan --> S2_Gen[Source-Isolated Grounded Question Generator via Qdrant]:::step2
        S2_Gen --> S2_ValGate{3 Quality Gateways: Format, Grounding, Non-Dup}:::step2
        S2_ValGate -->|Fail| S2_Backfill[Reserve Pool Backfill Candidate]:::step2
        S2_Backfill --> S2_Gen
        S2_ValGate -->|Pass| S2_Session[Save AssessmentSession with Hidden Answer Key]:::step2
        S2_Session --> S2_SafeQ[Strip Answers -> SafeQuestions Dispatched to Student]:::step2
        S2_SafeQ --> S2_Student[Student Takes Quiz on Web Console]:::aux
        S2_Student --> S2_Submit[POST /assessment/submit]:::step2
        S2_Submit --> S2_Grade[Grading Engine: False-Mastery Safeguard & Prereq Gap Detection]:::step2
        S2_Grade --> S2_KillCheck{Failures > 3?}:::step2
        S2_KillCheck -->|Yes| S2_Kill[Status: REQUIRES_HUMAN_FALLBACK -> Flag Instructor]:::aux
        S2_KillCheck -->|No| S2_Prof[Update StudentLearningProfile]:::step2
        S2_Prof --> S2_VTM[Generate VideoTargetMatrix: 30s/45s/60s targets]:::step2
    end

    S2_VTM -->|VideoTarget: concept_id + target_seconds| S3_Entry[POST /video/generate]:::step3

    subgraph SUB_STEP3["STEP 3: TARGETED AI VIDEO GENERATION ENGINE"]
        S3_Entry --> S3_Check{In Human Intervention?}:::step3
        S3_Check -->|Yes| S3_Block[Reject: HTTP 400 Anti-Loop Guardrail]:::aux
        S3_Check -->|No| S3_Script[Grounded 3-Act Lesson Scriptwriter: 30s/45s/60s Word Budget]:::step3
        S3_Script --> S3_TTS[Neural Voiceover Audio Synthesizer: Edge-TTS / pyttsx3]:::step3
        S3_TTS --> S3_Vis[1080p Visual Scene Renderer: Pillow Cards + Diagrams + Progress Bar]:::step3
        S3_Vis --> S3_Mux[FFmpeg Audio-Video Muxer & WebVTT Caption Generator]:::step3
        S3_Mux --> S3_Register[Register Video in videos_index.json & Final MP4]:::step3
        S3_Register --> S3_Stream[GET /video/{video_id}/stream to In-Browser Player]:::step3
    end

    S3_Stream -->|Student Watches Video Lesson| S4_UserAction[Learner Clicks 'Verify Mastery' Button]:::aux

    subgraph SUB_STEP4["STEP 4: REMEDIATION VERIFICATION & RE-TESTING LOOP"]
        S4_UserAction --> S4_Start[POST /remediation/start]:::step4
        S4_Start --> S4_Gen[Generate 1-2 Focused Questions: Application & Misconception Variants]:::step4
        S4_Gen --> S4_Dispatch[SafeQuestions Dispatched to Re-Test Modal]:::step4
        S4_Dispatch --> S4_Submit[POST /remediation/submit Answers]:::step4
        S4_Submit --> S4_Eval[Evaluate Submission against Hidden Ground Truth]:::step4
        S4_Eval --> S4_ScoreCheck{Score >= 70%?}:::step4
        S4_ScoreCheck -->|Yes: Passed| S4_Pass[Transition Status: LEARNING -> MASTERED]:::step4
        S4_Pass --> S4_ResolveVTM[Dynamic Resolution: Remove Concept from VideoTargetMatrix]:::step4
        S4_ResolveVTM --> S4_SyncProf[Update StudentLearningProfile: weak -> strong]:::step4
        S4_SyncProf --> S4_Closed([Remediation Loop Complete & Closed!]):::step4

        S4_ScoreCheck -->|No: Failed| S4_FailAttempts{Attempts > 3?}:::step4
        S4_FailAttempts -->|Yes| S4_TriggerKill[Status: REQUIRES_HUMAN_FALLBACK -> Push Alert to Portal]:::aux
        S4_FailAttempts -->|No| S4_KeepLearning[Status Remains LEARNING -> Re-watch Video]:::step4
    end

    subgraph SUB_AUX["AUXILIARY SUBSYSTEMS"]
        S3_Stream -.->|While Watching| AUX_RAG[POST /video/rag/ask: Timestamp Playhead Sync + Layer A Citations]:::aux
        S2_Kill & S4_TriggerKill -.->|Kill-Switch Alerts| AUX_Inst[GET /instructor: Cohort KPIs, Bottlenecks & Mastery Overrides]:::aux
        SUB_STEP1 & SUB_STEP2 & SUB_STEP3 & SUB_STEP4 -.->|Real-Time Telemetry| AUX_SSE[GET /pipeline/events: Sanitized SSE Stream]:::aux
    end
```

---

## 2. Step 1: Multimodal Ingestion & Knowledge Graph (Line-by-Line Flowchart)

```
[UPLOAD REQUEST]
  │
  ├─► POST /upload (app/api/upload.py::upload_file)
  │     │
  │     ├─► [Line 55-60]: Buffer incoming stream to temporary disk storage:
  │     │     Path: storage/uploads/{uuid4}_{filename}
  │     │
  │     ├─► [Line 64]: Call app/services/registry.py::register_source(temp_path, filename)
  │     │     │
  │     │     ├─► validate_file(): Check size (<500MB), extension, and magic bytes
  │     │     ├─► calculate_sha256(): Compute SHA-256 hash
  │     │     ├─► Deduplication check against storage/registry/sources_index.json:
  │     │     │     If exists: increment version (e.g. v2) and link parent_source_id
  │     │     ├─► Generate unique deterministic identifiers:
  │     │     │     source_id (SRC_...), asset_id (AST_...), upload_id (UPL_...)
  │     │     ├─► Copy permanent file to: storage/uploads/{source_id}/original.{ext}
  │     │     └─► Write SourceRecord to sources_index.json (status="PROCESSING")
  │     │
  │     ├─► [Line 78]: Call app/services/dispatcher.py::dispatch(file_path, source_id, asset_id)
  │     │     │
  │     │     ├─► IF PDF: Call app/services/extractor.py::extract_from_pdf()
  │     │     │     ├─► PyMuPDF fitz.open(pdf_path)
  │     │     │     ├─► Extract text blocks, line coordinates, bounding boxes [x0, y0, x1, y1]
  │     │     │     └─► Extract embedded pixmap diagrams -> call vision.py::describe_image()
  │     │     │
  │     │     ├─► IF TXT: Split text by double newline (\n\n), compute char offsets & indices
  │     │     │
  │     │     ├─► IF IMAGE (PNG, JPG): Call app/services/vision.py::describe_image_file()
  │     │     │     └─► Prompt Gemini Vision API -> Return rich diagram transcription
  │     │     │
  │     │     └─► IF VIDEO (MP4, MOV, MKV): Call app/services/video/pipeline.py::process_video_units()
  │     │           ├─► Phase 1: FFmpeg rip audio -> 16kHz mono 16-bit PCM WAV (av_splitter.py)
  │     │           ├─► Phase 2: faster-whisper ASR with word/segment timestamps (transcriber.py)
  │     │           ├─► Phase 3: OpenCV keyframe extraction every 12s; 32x32 grayscale deduplication
  │     │           │            (<4% difference skipped) -> Gemini Vision frame description
  │     │           └─► Phase 4: Temporal multimodal fusion (2.0s jitter tolerance) into ContentUnits
  │     │
  │     ├─► [Line 85]: Persist normalized ContentUnits:
  │     │     Path: storage/registry/{source_id}/content_units.json
  │     │
  │     ├─► [Line 90]: Call app/services/structurer.py::process_structure_and_concepts(units)
  │     │     │
  │     │     ├─► Serialize ContentUnits with IDs into Gemini prompt (gemini-3.5-flash)
  │     │     ├─► Discover chapters, sections, discrete concepts, and prerequisite DAG
  │     │     ├─► RESILIENT FALLBACK: If Gemini 429 quota occurs, execute regex heuristic parser
  │     │     │   parsing headings, capitalized definitions & acronyms (zero empty concepts)
  │     │     ├─► Derive TopicBlueprint (topic_name, key_concepts, prerequisites, difficulty)
  │     │     └─► Persist KnowledgeGraph: storage/registry/{source_id}/knowledge_graph.json
  │     │
  │     ├─► [Line 98]: Call app/services/chunker.py::create_rich_chunks(units, kg)
  │     │     │
  │     │     ├─► Group ContentUnits by concept boundaries and token limits (~500 tokens)
  │     │     └─► Output List[RichChunk] with layer="A", page ranges, and content_ids
  │     │
  │     ├─► [Line 104]: Call app/db/vector_store.py::upsert_chunks(chunks)
  │     │     │
  │     │     ├─► Embed chunk text via models/gemini-embedding-2 (768 dimensions)
  │     │     ├─► Generate deterministic point IDs via UUIDv5(source_id + chunk_id + text)
  │     │     └─► Upsert points into Qdrant collection: visualai_layer_a (cosine distance)
  │     │
  │     ├─► [Line 112]: Call app/services/validator.py::validate_ingestion_quality()
  │     │     │
  │     │     ├─► Tier 1: File size > 0, disk path exists, SHA-256 match
  │     │     ├─► Tier 2: ContentUnits count >= 1, non-empty text, valid sequence order
  │     │     ├─► Tier 3: RichChunks count >= 1, token bounds within limits
  │     │     ├─► Tier 4: KnowledgeGraph concepts count >= 1, no cyclical self-dependencies
  │     │     └─► Tier 5: Qdrant points count verified > 0
  │     │
  │     └─► [Line 125]: Update status to "READY" in storage/registry/sources_index.json
  │           └─► Return HTTP 200 JSON with source_id, asset_id, concepts_count, topic_blueprint
```

---

## 3. Step 1 ➔ Step 2 Handoff Interface

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STEP 1 ➔ STEP 2 HANDOFF CONTRACT                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Mandatory Preconditions:                                                 │
│    - source_id must exist in storage/registry/sources_index.json            │
│    - Source status MUST be "READY" (fails with HTTP 423 Locked if INDEXING) │
│                                                                             │
│ 2. Available Handoff Trigger Modes:                                         │
│    - Mode A (Seamless Single-Shot):                                         │
│      POST /upload?auto_start_assessment=true&student_id=student_1           │
│      -> Directly chains into start_assessment() upon validation completion. │
│    - Mode B (Explicit REST API Call):                                       │
│      POST /assessment/start with { "source_id": "SRC_...", "student_id": "" }│
│    - Mode C (Interactive Dashboard):                                        │
│      Web Console GET /sources populates dropdown -> user clicks "Start Quiz"│
│                                                                             │
│ 3. Data Invariants Consumed by Step 2:                                      │
│    - KnowledgeGraph: Concepts, definitions, and prerequisite DAG links      │
│    - ContentUnits: Ground-truth text blocks, diagram references & bboxes    │
│    - Qdrant Collection: visualai_layer_a indexed with source_id payload tag │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Step 2: Diagnostic Assessment & Knowledge Profiling (Line-by-Line Flowchart)

```
[ASSESSMENT INITIALIZATION]
  │
  ├─► POST /assessment/start (app/api/assessment.py::start_assessment)
  │     │
  │     ├─► [Line 85]: Verify source_id exists and status == "READY"
  │     ├─► [Line 92]: Generate session_id: SESS_{uuid4_hex}
  │     │
  │     ├─► [Line 98]: Embed ConceptSnapshot directly into session:
  │     │     Extract concept_id, name, definition, prerequisites, difficulty.
  │     │     Guarantee: AssessmentSession is self-contained and immune to external edits.
  │     │
  │     ├─► [Line 110]: Call app/services/assessment/planner.py::plan_assessment()
  │     │     │
  │     │     ├─► Cold Start Planning (Balanced Distribution):
  │     │     │     * ~30% Foundational (Beginner)
  │     │     │     * ~40% Intermediate
  │     │     │     * ~30% Advanced
  │     │     ├─► Prerequisite Pairing:
  │     │     │     Automatically traverses DAG to pair parent prerequisites
  │     │     │     alongside advanced concepts for root-gap diagnostic detection.
  │     │     └─► Allocate candidate pools: Primary candidates + Reserve backup pool.
  │     │
  │     ├─► [Line 135]: Call app/services/assessment/generator.py::generate_question_for_concept()
  │     │     │
  │     │     ├─► Source-Isolated Retrieval:
  │     │     │     Query Qdrant Layer A with filter must=[source_id == req.source_id].
  │     │     │     Prevents cross-document data leakage between different courses.
  │     │     ├─► LLM Prompting via pluggable LLMProvider (Gemini, Ollama, or Mock):
  │     │     │     Provide retrieved source chunks as authoritative context.
  │     │     │     Generate 4-option MCQ: 1 unambiguously correct, 3 plausible distractors.
  │     │     └─► Grounded Deterministic Fallback:
  │     │           If LLM quota exhausted, synthesize grounded question from concept definition
  │     │           with varied correct answer index hashing (not always index 0).
  │     │
  │     ├─► [Line 160]: 3 Quality Validation Gateways (app/services/assessment/validator.py)
  │     │     │
  │     │     ├─► Gateway 1 (Structural): Exactly 4 options, valid correct_index (0-3), non-empty stem.
  │     │     ├─► Gateway 2 (Grounding): Stem & options must share >10% vocabulary with source chunks.
  │     │     ├─► Gateway 3 (Non-Duplication): Jaccard stem similarity with other questions < 0.6.
  │     │     │
  │     │     └─► RESERVE POOL BACKFILLING:
  │     │           If any question fails a gateway, engine pops candidate from reserve pool,
  │     │           generates replacement, and validates until target count is satisfied.
  │     │
  │     ├─► [Line 180]: Persist complete session to disk:
  │     │     Path: storage/assessment_sessions/{session_id}.json
  │     │     (Contains full Question models with hidden correct_index and explanation)
  │     │
  │     └─► [Line 195]: Sanitize questions into SafeQuestion objects (hidden answers stripped)
  │           └─► Return HTTP 200 with session_id, questions, question_count.
  │
[STUDENT QUIZ SUBMISSION]
  │
  ├─► POST /assessment/submit (app/api/assessment.py::submit_assessment)
  │     │
  │     ├─► [Line 210]: Verify session exists, status != "SUBMITTED", and TTL not expired (24h)
  │     ├─► [Line 225]: Call app/services/assessment/engine.py::grade_submission()
  │     │     │
  │     │     ├─► Compare submitted selected_index with hidden correct_index
  │     │     ├─► Calculate overall score and percentage (e.g. 75.0%)
  │     │     │
  │     │     ├─► Prerequisite Gap Detection:
  │     │     │     Identify cases where child concept failed AND parent prerequisite failed.
  │     │     │
  │     │     ├─► False-Mastery Safeguard:
  │     │     │     Requires consecutive correct attempts (mastery_threshold=2)
  │     │     │     before concept transitions to "MASTERED". Lucky guesses remain "LEARNING".
  │     │     │
  │     │     └─► Anti-Loop Kill Switch:
  │     │           Track consecutive failure iterations per concept.
  │     │           If iteration_count > kill_switch_limit (default: 3):
  │     │           Concept status is marked: "REQUIRES_HUMAN_FALLBACK".
  │     │           Permanently excluded from automated video loops; alerts teacher.
  │     │
  │     ├─► [Line 260]: Persist updated StudentLearningProfile:
  │     │     Path: storage/learning_profiles/{student_id}_{source_id}.json
  │     │
  │     ├─► [Line 275]: Call app/services/assessment/video_target.py::build_video_target_matrix()
  │     │     │
  │     │     ├─► Filter out mastered concepts (score >= 70%) -> no video needed
  │     │     ├─► Filter out kill-switch concepts -> push to human_intervention_concepts
  │     │     ├─► Scale target duration by concept difficulty:
  │     │     │     * Foundational: 30 seconds (±2s tolerance)
  │     │     │     * Intermediate: 45 seconds (±3s tolerance)
  │     │     │     * Advanced:     60 seconds (±3s tolerance)
  │     │     ├─► Attach provenance: chunk_ids and source page numbers
  │     │     └─► Set decision: "GENERATE_VIDEOS" | "ALL_MASTERED" | "HUMAN_INTERVENTION"
  │     │
  │     ├─► [Line 295]: Persist VideoTargetMatrix:
  │     │     Path: storage/video_targets/{student_id}_{source_id}.json
  │     │
  │     └─► Return HTTP 200 with score, results, prerequisite_gaps, and video_target_matrix.
```

---

## 5. Step 2 ➔ Step 3 Handoff Interface

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STEP 2 ➔ STEP 3 HANDOFF CONTRACT                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Handoff Artifact:                                                        │
│    - storage/video_targets/{student_id}_{source_id}.json                    │
│    - Accessible via: GET /assessment/video-target/{student_id}/{source_id}   │
│                                                                             │
│ 2. Contract Guarantees & Constraints:                                       │
│    - Separation of Concerns: Step 2 dictates WHAT to teach (unmastered);    │
│      Step 3 dictates HOW to teach it visually and auditorily.               │
│    - Anti-Loop Guardrail: Concepts listed in "human_intervention_concepts"  │
│      are STRICTLY PROHIBITED from automated video generation (HTTP 400).    │
│    - Strict Duration Compliance: Target duration is strictly enforced:       │
│      Foundational = 30s | Intermediate = 45s | Advanced = 60s               │
│    - Grounding Provenance: Scriptwriting must anchor to the chunk_ids and   │
│      page numbers recorded in each VideoTarget item.                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Step 3: Targeted AI Video Generation Engine (Line-by-Line Flowchart)

```
[VIDEO GENERATION TRIGGER]
  │
  ├─► POST /video/generate (app/api/video.py::generate_video_endpoint)
  │     │
  │     ├─► [Line 83]: Load VideoTargetMatrix from storage/video_targets/{student_id}_{source_id}.json
  │     ├─► [Line 91]: Verify decision == "GENERATE_VIDEOS" and targets exist
  │     │
  │     ├─► [Line 100]: ANTI-LOOP GUARD CHECK:
  │     │     If requested concept_id is in human_intervention_concepts:
  │     │     RAISE HTTP 400 Bad Request: Automated video generation strictly blocked.
  │     │
  │     ├─► [Line 121]: Generate unique identifiers:
  │     │     job_id = "JOB_VGEN_{concept_id[:8]}_{student_id[:6]}"
  │     │     video_id = "VID_{uuid4_hex[:12]}"
  │     │
  │     ├─► [Line 135]: Register in-memory VideoRenderJob (status="pending", progress=5%)
  │     ├─► [Line 138]: Spawn background task: execute_video_generation_pipeline()
  │     └─► Return HTTP 200 immediately with job_id, video_id, status="pending".
  │
[BACKGROUND ASYNCHRONOUS PIPELINE EXECUTION]
  │
  ├─► app/services/video_gen/pipeline.py::execute_video_generation_pipeline()
  │     │
  │     ├─► [Stage 1: Workspace Setup]
  │     │     Create directory: storage/runtime/videos/{video_id}/
  │     │
  │     ├─► [Stage 2: Script Generation (0% -> 25%)]
  │     │     Call app/services/video_gen/script_generator.py::generate_video_script()
  │     │     │
  │     │     ├─► Retrieve source text from RichChunks & ContentUnits
  │     │     ├─► Check for diagram assets (diagram_cu_id) in source units
  │     │     ├─► Enforce word budget (~130-150 words per minute):
  │     │     │     * 30s: ~65-75 words | 45s: ~100-115 words | 60s: ~130-150 words
  │     │     ├─► Prompt LLM to construct 3-Act Pedagogical Structure:
  │     │     │     * Act 1 (title_hook): 15-20% duration (hook & core question)
  │     │     │     * Act 2 (concept_breakdown / diagram_focus): 60-70% duration (mechanical explanation)
  │     │     │     * Act 3 (summary_takeaway): 15-20% duration (mental anchor heuristic)
  │     │     ├─► Deterministic Fallback: If LLM offline, format template script from definition
  │     │     └─► Persist script: storage/runtime/videos/{video_id}/script.json
  │     │
  │     ├─► [Stage 3: Neural Audio Synthesis (25% -> 50%)]
  │     │     Call app/services/video_gen/audio_synthesizer.py::synthesize_script_audio()
  │     │     │
  │     │     ├─► Synthesize per-scene audio tracks:
  │     │     │     Path: storage/runtime/videos/{video_id}/scene_{i}_audio.wav
  │     │     │     TTS Strategy: Edge-TTS (en-US-ChristopherNeural) -> pyttsx3 fallback -> mock
  │     │     ├─► Concatenate into master narration track:
  │     │     │     Path: storage/runtime/videos/{video_id}/master_audio.wav
  │     │     └─► Accurately measure exact audio duration per scene via wave/probe
  │     │
  │     ├─► [Stage 4: 1080p Visual Scene Rendering (50% -> 80%)]
  │     │     Call app/services/video_gen/visual_renderer.py::render_scene_to_video_clip()
  │     │     │
  │     │     ├─► Loop each VideoScene in script:
  │     │     │     * Resolution: 1920x1080 @ 24 FPS
  │     │     │     * Theme: Dark-mode slate backdrop (#0f172a) with cyan/emerald accents
  │     │     │     * Typography: Pillow anti-aliased text (title, badges, bullets)
  │     │     │     * Callout Box: Highlight text / core equation in emphasized border box
  │     │     │     * Diagram Integration: Embed source diagram image if diagram_cu_id present
  │     │     │     * Progress Bar: Dynamic bottom progress bar tracking overall elapsed time
  │     │     │     * OpenCV cv2.VideoWriter encodes scene frame sequence to MP4
  │     │     └─► Output per scene: storage/runtime/videos/{video_id}/scene_{idx}_clip.mp4
  │     │
  │     ├─► [Stage 5: Media Multiplexing & Subtitles (80% -> 95%)]
  │     │     Call app/services/video_gen/muxer.py
  │     │     │
  │     │     ├─► Concatenate visual scene clips via FFmpeg concat demuxer:
  │     │     │     Output: storage/runtime/videos/{video_id}/raw_video.mp4
  │     │     ├─► Multiplex visual track with master_audio.wav:
  │     │     │     ffmpeg -y -i raw_video.mp4 -i master_audio.wav -c:v libx264 -pix_fmt yuv420p
  │     │     │            -c:a aac -b:a 192k -shortest final_video.mp4
  │     │     │     Output: storage/runtime/videos/{video_id}/final_video.mp4
  │     │     └─► Generate WebVTT subtitle track (generate_webvtt_subtitles):
  │     │           Output: storage/runtime/videos/{video_id}/subtitles.vtt
  │     │
  │     └─► [Stage 6: Finalization & Indexing (100%)]
  │           ├─► Update job: status="completed", progress=100%, video_file_path, subtitles_file_path
  │           ├─► Persist job status: storage/runtime/videos/{video_id}/job.json
  │           ├─► Register in master catalog: storage/runtime/videos/videos_index.json
  │           └─► Streamable via GET /video/{video_id}/stream to HTML5 video modal
```

---

## 7. Step 3 ➔ Step 4 Handoff Interface

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STEP 3 ➔ STEP 4 HANDOFF CONTRACT                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Learner Interaction Trigger:                                             │
│    - Student finishes watching remedial video in embedded dashboard player. │
│    - Student clicks the "🎯 Verify Mastery" button below the player.        │
│                                                                             │
│ 2. Handoff Payload:                                                         │
│    - student_id: Identifier of student                                      │
│    - source_id: Source material ID                                          │
│    - concept_id: Specific concept taught in the video lesson                │
│                                                                             │
│ 3. Pedagogical Objective:                                                   │
│    - Administer an immediate, lightweight 1-2 question re-test.             │
│    - Focus exclusively on the single concept just taught.                   │
│    - Employ higher-order cognitive variants (application / misconception)   │
│      rather than repeating the identical diagnostic question.               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Step 4: Remediation Verification & Re-Testing Loop (Line-by-Line Flowchart)

```
[VERIFICATION SESSION INITIALIZATION]
  │
  ├─► POST /remediation/start (app/api/remediation.py::start_remediation)
  │     │
  │     ├─► [Line 71]: Call app/services/remediation/engine.py::create_remediation_session()
  │     │     │
  │     │     ├─► Load KnowledgeGraph for concept definitions & difficulty
  │     │     ├─► Pedagogical Variant Selection:
  │     │     │     * "application": Tests concrete scenario application of principle
  │     │     │     * "misconception": Tests resolution of the specific cognitive trap
  │     │     ├─► Generate fresh question via generate_question_for_concept()
  │     │     │     (Deterministic fallback if LLM quota exhausted)
  │     │     ├─► Embed ConceptSnapshot into session
  │     │     ├─► Generate session_id: SESS_REM_{uuid4_hex}
  │     │     ├─► Persist session: storage/assessment_sessions/{session_id}.json
  │     │     └─► Strip hidden answer keys to produce SafeQuestion objects
  │     │
  │     └─► Return HTTP 200 with session_id, concept_id, and safe questions.
  │
[STUDENT VERIFICATION SUBMISSION & MASTERY TRANSITION]
  │
  ├─► POST /remediation/submit (app/api/remediation.py::submit_remediation)
  │     │
  │     ├─► [Line 95]: Call app/services/remediation/engine.py::evaluate_remediation_submission()
  │     │     │
  │     │     ├─► Load session from storage/assessment_sessions/{session_id}.json
  │     │     ├─► Compare submitted answers against hidden ground truth
  │     │     ├─► Calculate score percentage (e.g. 100.0%)
  │     │     ├─► Load StudentLearningProfile from storage/learning_profiles/
  │     │     │
  │     │     ├─► [BRANCH A: PASSED (Score >= 70%)]
  │     │     │     │
  │     │     │     ├─► Mastery State Transition:
  │     │     │     │     status = "MASTERED"
  │     │     │     │     Increment correct_attempts & consecutive_correct
  │     │     │     │
  │     │     │     ├─► Update StudentLearningProfile:
  │     │     │     │     * Remove concept from weak_concepts & weak_concept_ids
  │     │     │     │     * Add concept to strong_concepts & strong_concept_ids
  │     │     │     │     * Recalculate average mastery score
  │     │     │     │     * Persist to storage/learning_profiles/{student_id}_{source_id}.json
  │     │     │     │
  │     │     │     ├─► Dynamic VideoTargetMatrix Resolution:
  │     │     │     │     * Load storage/video_targets/{student_id}_{source_id}.json
  │     │     │     │     * Remove cleared concept_id from matrix.videos
  │     │     │     │     * IF matrix.videos is now empty:
  │     │     │     │     │   - If human_intervention_concepts empty:
  │     │     │     │     │       decision = "ALL_MASTERED"
  │     │     │     │     │       summary = "All assessed concepts have been successfully mastered."
  │     │     │     │     │   - If human_intervention_concepts not empty:
  │     │     │     │     │       decision = "HUMAN_INTERVENTION"
  │     │     │     │     │       summary = "Remaining items require human instructor intervention."
  │     │     │     │     * Save updated VideoTargetMatrix to disk
  │     │     │     │
  │     │     │     └─► [CLOSED LOOP ACHIEVED]: Remediation verified; target resolved!
  │     │     │
  │     │     └─► [BRANCH B: FAILED (Score < 70%)]
  │     │           │
  │     │           ├─► Increment attempts; reset consecutive_correct = 0
  │     │           │
  │     │           ├─► Anti-Loop Kill Switch Evaluation:
  │     │           │     IF attempts > kill_switch_limit (default: 3):
  │     │           │       * Status transitions to: "REQUIRES_HUMAN_FALLBACK"
  │     │           │       * Concept permanently removed from automated video queues
  │     │           │       * Alert pushed to Instructor Portal for 1-on-1 human tutoring
  │     │           │     ELSE:
  │     │           │       * Status remains: "LEARNING" (student advised to re-watch lesson)
  │     │           │
  │     │           └─► Save updated StudentLearningProfile to disk
  │     │
  │     └─► Return HTTP 200 with passed (bool), new_status, explanations, and profile_summary.
```

---

## 9. Auxiliary Subsystems (Video RAG, Instructor Portal, Telemetry)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. INTERACTIVE VIDEO RAG & PLAYBACK Q&A AGENT (POST /video/rag/ask)         │
├─────────────────────────────────────────────────────────────────────────────┤
│ - Input: video_id, timestamp (e.g. 18.5s), question text                   │
│ - Processing:                                                               │
│   1. Load script: storage/runtime/videos/{video_id}/script.json             │
│   2. Pinpoint active VideoScene at timestamp interval [start_sec, end_sec] │
│   3. Query Qdrant Layer A for textbook citations matching concept & query   │
│   4. Prompt LLM with scene narration + retrieved chunk quotes               │
│   5. Deterministic fallback if LLM rate-limited                             │
│ - Output: explanation, citations (chunk_id, pages), jump_to_seconds seeking │
│   button, and suggested pedagogical follow-up questions                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. INSTRUCTOR ANALYTICS & HUMAN INTERVENTION PORTAL (/instructor)           │
├─────────────────────────────────────────────────────────────────────────────┤
│ - GET /instructor: Responsive dark-mode web console for educators          │
│ - GET /instructor/api/overview: Scans storage/learning_profiles/*.json      │
│   * Cohort KPIs: Total Students, Interventions Needed, Average Mastery %   │
│   * Kill-Switch Active Alerts: Table of students stuck in fallback status   │
│   * Prerequisite Bottleneck Heatmap: Identifies parent concepts causing     │
│     widespread downstream failures across multiple students                 │
│ - POST /instructor/api/reset-mastery: Teacher override controls             │
│   * "Reset to Learning": Resets iteration count to 0 for a fresh attempt   │
│   * "Verify Mastered": Forces status to MASTERED after manual 1-on-1 review │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. PIPELINE OBSERVABILITY & EVENT BROADCASTER (GET /pipeline/events)        │
├─────────────────────────────────────────────────────────────────────────────┤
│ - Real-time Server-Sent Events (SSE) streaming progress across all 4 steps │
│ - Security & Sanitization (SEC-010):                                        │
│   Strips API keys, bearer tokens, LLM prompts, file paths, and stack traces │
│ - Broadcasts safe operational metrics: stage, progress_percent, score, etc. │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Continuous Line-by-Line Code Symbol & Storage Matrix

| Pipeline Step | Source File & Function | Key Input Model | Key Output Model | Persistent Disk Storage Path |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1: Ingest** | `app/api/upload.py::upload_file` | `UploadFile` (multipart) | `IngestionResponse` | `storage/uploads/{source_id}/original.<ext>` |
| **Step 1: Register**| `app/services/registry.py::register_source` | Raw temporary file path | `SourceRecord` | `storage/registry/sources_index.json` |
| **Step 1: Extract** | `app/services/dispatcher.py::dispatch` | Raw file path | `List[ContentUnit]` | `storage/registry/{source_id}/content_units.json` |
| **Step 1: Structure**| `app/services/structurer.py::process_structure_and_concepts` | `List[ContentUnit]` | `KnowledgeGraph` | `storage/registry/{source_id}/knowledge_graph.json` |
| **Step 1: Chunk** | `app/services/chunker.py::create_rich_chunks` | `ContentUnits` + `KG` | `List[RichChunk]` | Memory / Qdrant payload |
| **Step 1: Embed** | `app/db/vector_store.py::upsert_chunks` | `List[RichChunk]` | Qdrant Points (UUIDv5) | `storage/qdrant_local/collections/visualai_layer_a` |
| **Step 2: Plan** | `app/services/assessment/planner.py::plan_assessment`| `KnowledgeGraph` + `Profile` | Candidate concepts pool | `AssessmentSession.concept_snapshot` |
| **Step 2: Generate**| `app/services/assessment/generator.py::generate_question_for_concept`| ConceptNode + Qdrant Chunks | `Question` | `storage/assessment_sessions/{session_id}.json` |
| **Step 2: Sanitize**| `app/api/assessment.py::start_assessment` | `List[Question]` | `List[SafeQuestion]` | Client HTTP Response |
| **Step 2: Grade** | `app/services/assessment/engine.py::grade_submission` | `StudentSubmission` | `GradingResult` | `storage/learning_profiles/{student_id}_{source_id}.json` |
| **Step 2: Target** | `app/services/assessment/video_target.py::build_video_target_matrix`| `StudentLearningProfile` | `VideoTargetMatrix` | `storage/video_targets/{student_id}_{source_id}.json` |
| **Step 3: Script** | `app/services/video_gen/script_generator.py::generate_video_script`| `VideoTarget` | `VideoScript` | `storage/runtime/videos/{video_id}/script.json` |
| **Step 3: Audio** | `app/services/video_gen/audio_synthesizer.py::synthesize_script_audio`| `VideoScript` | WAV audio tracks | `storage/runtime/videos/{video_id}/master_audio.wav` |
| **Step 3: Visual** | `app/services/video_gen/visual_renderer.py::render_scene_to_video_clip`| `VideoScene` (1080p) | MP4 scene clips | `storage/runtime/videos/{video_id}/scene_{i}_clip.mp4` |
| **Step 3: Mux** | `app/services/video_gen/muxer.py::mux_audio_and_video` | Raw video + Master audio | Final MP4 + WebVTT | `storage/runtime/videos/{video_id}/final_video.mp4` |
| **Step 3: Index** | `app/services/video_gen/pipeline.py::register_completed_video`| `VideoRenderJob` | Video metadata entry | `storage/runtime/videos/videos_index.json` |
| **Step 4: Re-Test** | `app/services/remediation/engine.py::create_remediation_session`| `concept_id` + `student_id` | `List[SafeQuestion]` | `storage/assessment_sessions/SESS_REM_{uuid}.json` |
| **Step 4: Verify** | `app/services/remediation/engine.py::evaluate_remediation_submission`| Re-test answers | `RemediationSubmitResponse`| Updates `learning_profiles` & `video_targets` |
| **Aux: Video RAG** | `app/services/video_rag/engine.py::answer_video_question` | Timestamp + Question | `VideoQAResponse` | Memory / Client HTTP Response |
| **Aux: Portal** | `app/services/instructor/analytics.py::get_cohort_overview`| Stored profiles & KGs | `CohortOverview` | `GET /instructor` & `GET /instructor/api/overview` |
| **Aux: Telemetry**| `app/services/pipeline_tracker.py::broadcast_event` | Progress event metadata | Sanitized SSE event | `GET /pipeline/events` |

---
*End of Authoritative 4-Step Continuous System Flowchart.*
