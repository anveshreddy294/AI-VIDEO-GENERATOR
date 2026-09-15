# PageIndex ↔ Video Pipeline Integration Guide

This document explains the architecture of `topic2manim` after copying `PageIndex/` from the curriculum repository, why the two pipelines are still disconnected, and exactly what must be built to connect them.

**Audience:** You (the developer) integrating curriculum intelligence into the working Manim video engine.

**Canonical roots:**
- Monorepo root: `topic2manim/`
- Video engine: `topic2manim/backend/`
- Curriculum indexer: `topic2manim/PageIndex/`

---

## 1. Current State After PageIndex Copy

### What exists now regarding PageIndex

| Component | Location | Status |
|-----------|----------|--------|
| Vendored PageIndex source | `PageIndex/` | **Present** — full Python package (`pageindex/`), CLI, demos |
| Indexing CLI | `PageIndex/run_pageindex.py` | **Present** — accepts `--pdf_path`, writes artifacts under `PageIndex/results/<pdf_name>/` when run from `PageIndex/` cwd |
| Core indexing logic | `PageIndex/pageindex/page_index.py` | **Present** — TOC detection, tree construction, summary generation |
| Retrieval utilities | `PageIndex/pageindex/retrieve.py` | **Present** — `_retrieve_nodes()`, `get_page_content()`, `get_document_structure()` |
| PageIndex client | `PageIndex/pageindex/client.py` | **Present** — `PageIndexClient` for programmatic indexing + QA |
| LangChain deps | `PageIndex/requirements.txt` | **Present** — separate from video backend deps |
| Demos | `PageIndex/demo_with_logging.py`, `PageIndex/examples/agentic_vectorless_rag_demo.py` | **Present** |

PageIndex is a **complete, self-contained indexing subsystem**. It can turn a PDF into a hierarchical tree with summaries. It lives in the same repo as the video engine but shares **no import path or runtime call** with `backend/main.py` or `backend/api.py`.

### Where PageIndex writes its output

PageIndex uses **two different output conventions** depending on which tool you run:

| Tool | Working directory | Output path |
|------|-------------------|-------------|
| `PageIndex/run_pageindex.py` | `PageIndex/` | `PageIndex/results/<pdf_basename>/` |
| Semantic layer builder (documented, **missing**) | `topic2manim/` root | `topic2manim/results/<pdf_name>/` |

**PageIndex CLI behavior** (from `run_pageindex.py`):

```154:155:topic2manim/PageIndex/run_pageindex.py
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = os.path.join('./results', pdf_name)
```

When indexing completes, `_write_output_artifacts()` in `page_index.py` writes at minimum:

```859:879:topic2manim/PageIndex/pageindex/page_index.py
    artifacts = {
        "structure.json": export_result,
        "tree_structure.json": export_structure,
    }
    ...
    if not skip_summaries or summaries:
        artifacts["summaries.json"] = summaries
```

**What actually exists on disk today:**

| Path | Contents |
|------|----------|
| `topic2manim/results/tree.json` | Partial semantic tree (NCERT Physics IX, 187 nodes) |
| `topic2manim/results/dependency.json` | Prerequisite graph (42 nodes, 67 edges) |
| `topic2manim/backend/results/` | **Empty** — FastAPI mounts this for `/results` |
| `PageIndex/results/` | **Does not exist yet** — created only after you run indexing |
| `topic2manim/scripts/` | **Does not exist** — README references `build_chemistry9_semantic_layer.py` here |

There is also a **path split**: curriculum JSON sits at `topic2manim/results/`, but the API serves static files from `backend/results/`:

```107:108:topic2manim/backend/api.py
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
```

```661:662:topic2manim/backend/api.py
app.mount("/generated", StaticFiles(directory=str(ROOT / "data" / "renders")), name="generated")
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")
```

The frontend proxy forwards `/results` to the backend (`frontend/vite.config.js`), but the mounted directory is empty. The real artifacts are one level up at the monorepo root and are never served or read.

### What is still missing from a full curriculum intelligence layer

1. **`scripts/build_chemistry9_semantic_layer.py`** — produces the extended artifact set (`concept_graph.json`, `pedagogical_metadata.json`, `retrieval_metadata.json`, `extracted_pages.json`, `validated_toc.json`).
2. **`dependency_graph_builder.py`** — referenced in `results/dependency.json` metadata; not in repo.
3. **Sample PDFs** — no `Chemistry_9.pdf` under `PageIndex/examples/documents/` (or anywhere in repo).
4. **Integration glue** — no `curriculum_loader.py`, no `retrieval_chain.py`.
5. **API endpoint for PDF upload + indexing** — frontend has no upload flow; backend has no subprocess wrapper for PageIndex.
6. **Unified results directory** — three locations (`PageIndex/results/`, `topic2manim/results/`, `backend/results/`) with no canonical merge.
7. **Frontend curriculum consumption** — `KnowledgeGraph.jsx` uses hardcoded `MOCK_SYLLABUS`, not real JSON.

---

## 2. The Critical Disconnection (Why It Doesn't Work End-to-End)

Uploading a PDF today **cannot** produce a curriculum-grounded Manim video because **the video pipeline never reads curriculum data**, and **nothing in the frontend or backend triggers PageIndex when a PDF is uploaded**.

### Disconnection 1: No PDF → PageIndex path

There is no backend route like `/api/curriculum/index` and no frontend file upload component wired to PageIndex. Grep across `frontend/src/` finds no PDF upload or PageIndex trigger — only marketing copy in `Workspace.jsx` ("pipeline will index the syllabus") that is not implemented.

PageIndex is only runnable manually:

```bash
cd PageIndex
PYTHONPATH=. python run_pageindex.py --pdf_path path/to/file.pdf
```

### Disconnection 2: Video pipeline input is a raw topic string

The CLI entry point passes only the topic to planning:

```54:56:topic2manim/backend/main.py
    # ── Step 1: Storyboard ────────────────────────────────────────────
    logger.info("[1/8] Building storyboard (5-scene concept arc)")
    storyboard = build_storyboard(topic)
```

`build_storyboard()` constructs an LLM prompt from `topic`, optional `learner_profile`, and `subject` — **not** from any JSON file:

```121:149:topic2manim/backend/modules/planning/storyboard.py
def build_storyboard(
    topic: str,
    learner_profile: dict[str, Any] | None = None,
    subject: str = "Physics",
) -> list[dict[str, Any]]:
    ...
    learner_context = format_learner_context(learner_profile, topic, subject)
    prompt = STORYBOARD_PROMPT.format(
        topic=topic,
        learner_context=learner_context,
        ...
    )
    raw = client.chat_json(NVIDIA_PLANNER_MODEL, messages, ...)
```

The LLM invents the lesson arc from general knowledge. It does not know what page 142 of `Chemistry_9.pdf` says.

### Disconnection 3: Fake "retrieving" stage in the API

The API **labels** the first stage as retrieval but performs none:

```366:368:topic2manim/backend/api.py
        await queue.put({"stage": "retrieving", "progress": 5, "message": "Contacting classroom agent pipeline..."})
        await asyncio.sleep(1.0)
```

After a 1-second sleep, it calls the LLM with the topic string and learner profile — same as if retrieval never existed. No call to `PageIndex/pageindex/retrieve.py`, no file read from `results/`.

### Disconnection 4: PageIndex retrieval code is isolated

`PageIndex/pageindex/retrieve.py` implements hierarchical node search:

```186:198:topic2manim/PageIndex/pageindex/retrieve.py
def _retrieve_nodes(structure, query: str, top_k: int = 5) -> list:
    nodes = structure_to_list(structure)
    ...
        score = len(q_tokens & text_tokens) / max(len(q_tokens), 1)
```

This module is used by PageIndex demos and benchmarks. **Nothing in `backend/modules/` imports it.**

### Disconnection 5: Manim compiler is deterministic, not LLM-driven — but its *inputs* are LLM-hallucinated

`semantic_compiler.py` correctly compiles template slots + timelines into Manim code without an LLM:

```32:47:topic2manim/backend/modules/manim/semantic_compiler.py
def semantic_compile(
    plan: dict[str, Any],
    sync_result: dict[str, Any],
) -> tuple[Path, str]:
    ...
    template_cls = TEMPLATES.get(template_id)
    ...
    timeline = sync_result.get("timeline", ...)
```

The compiler is only as accurate as the **semantic plan** and **narration** upstream — both generated by LLMs that never saw the textbook.

### Summary

```
PDF upload ──✗──► PageIndex ──✗──► results/*.json ──✗──► build_storyboard()
                                                              │
User topic string ───────────────────────────────────────────►│
                                                              ▼
                                                         LLM (general knowledge)
                                                              ▼
                                                         Manim video (may be wrong vs textbook)
```

---

## 3. Ideal Integrated Flow (How It Should Work)

### End-to-end numbered flow

1. **User uploads PDF** from the frontend (e.g. `Chemistry_9.pdf`).
2. **Backend receives file**, stores it under a known path (e.g. `backend/data/textbooks/Chemistry_9.pdf`), returns a `document_id`.
3. **Backend invokes PageIndex** as a subprocess (or imports `page_index_main`) with that PDF path.
4. **PageIndex produces base artifacts** in a canonical directory: `backend/results/Chemistry_9.pdf/` (or `topic2manim/results/Chemistry_9.pdf/` — pick one and stick to it).
5. **Semantic layer builder runs** (once per document) to enrich artifacts: `concept_graph.json`, `pedagogical_metadata.json`, `retrieval_metadata.json`, `extracted_pages.json`, `validated_toc.json`, and optionally `tree.json` / `dependency.json`.
6. **Artifacts become source of truth** for that document. The frontend Knowledge Graph reads `structure.json` or `tree.json` from `/results/<document_id>/`.
7. **User asks a question or selects a topic** (e.g. "Rutherford atomic model") from the graph or search box.
8. **`retrieval_chain.py` resolves the query** against the curriculum tree:
   - Match node(s) in `structure.json` / `summaries.json`
   - Pull prerequisites from `concept_graph.json` or `dependency.json`
   - Pull difficulty, misconceptions, worked examples from `pedagogical_metadata.json`
   - Pull page evidence from `extracted_pages.json` via `retrieval_metadata.json` node→page mapping
9. **`curriculum_loader.py` assembles a `CurriculumContext` object** — a structured prompt block (not raw JSON dump) containing: matched node, parent breadcrumb, child topics, prerequisite summaries, evidence excerpts, difficulty level.
10. **Context injected into every LLM planning stage:**
    - `build_storyboard()` — scene arc aligned to textbook section order and prerequisites
    - `build_semantic_plan()` — template slots filled with textbook-accurate labels, equations, diagrams
    - `write_all_narrations()` — narration grounded in evidence excerpts; anchor phrases traceable to source
    - Explanation package in `api.py` — objectives and prerequisites from `pedagogical_metadata.json`, not LLM invention
11. **Deterministic stages unchanged:** Piper TTS → sync → `semantic_compiler.py` → Manim render → FFmpeg merge.
12. **Final video** is pedagogically aligned with the uploaded textbook, verifiable against page spans in `extracted_pages.json`.

### Data flow diagram

```
                    ┌─────────────────────────────────────┐
                    │         results/<doc_id>/           │
                    │  structure.json, summaries.json,    │
                    │  concept_graph, pedagogical_meta,   │
                    │  retrieval_meta, extracted_pages    │
                    └──────────────┬──────────────────────┘
                                   │
         User query: "Rutherford model" │
                                   ▼
                    ┌──────────────────────────┐
                    │   retrieval_chain.py     │
                    │   (hierarchical RAG)     │
                    └──────────────┬───────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │   curriculum_loader.py   │
                    │   → CurriculumContext    │
                    └──────────────┬───────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
   build_storyboard()    build_semantic_plan()    write_all_narrations()
           │                       │                       │
           └───────────────────────┴───────────────────────┘
                                   ▼
                         semantic_compiler → Manim → MP4
```

---

## 4. Understanding PageIndex Output Artifacts

### PageIndex direct output vs semantic layer builder

| Aspect | PageIndex (`run_pageindex.py`) | Semantic layer builder (`scripts/build_chemistry9_semantic_layer.py`) |
|--------|--------------------------------|----------------------------------------------------------------------|
| **Purpose** | Index PDF → hierarchical tree + node summaries | Enrich tree with pedagogy, graphs, evidence, retrieval indexes |
| **Run from** | `PageIndex/` directory | `topic2manim/` root |
| **Output dir** | `PageIndex/results/<pdf_name>/` | `topic2manim/results/<pdf_name>/` |
| **Produces** | `structure.json`, `tree_structure.json`, `summaries.json` | Full 9-file set including graphs and metadata |
| **Status in repo** | **Runnable** (if you have a PDF) | **Script missing** |

Run PageIndex first to get the tree. Run the semantic builder second to add pedagogical and retrieval layers. **Both outputs should land in the same canonical `results/<doc_id>/` folder after integration work.**

---

### `structure.json`

**What it contains:** PageIndex's canonical document tree. Top-level keys include `doc_name` and `structure` — a nested list of nodes with `node_id`, `title`, `start_index`/`end_index` (PDF page spans), `summary`, `keywords`, and child nodes.

**Why it matters:** This is the **navigation skeleton** of the textbook. It preserves chapter → section → subsection hierarchy that vector RAG destroys.

**How LLM / planning should use it:**
- Resolve user query → best-matching node(s)
- Build breadcrumb ("Chemistry → Chapter 4 → Atomic Structure → Rutherford Model")
- Scope the 5-scene storyboard to the matched subtree, not the whole book
- Pass sibling/child node titles so the LLM knows what to defer vs cover now

---

### `summaries.json`

**What it contains:** Flat list of nodes that have summaries: `{node_id, title, structure, level, summary, keywords, semantic_tags, content_type}`.

**Why it matters:** Token-efficient retrieval index. Faster to search than traversing the full tree.

**How LLM / planning should use it:**
- First-pass retrieval: keyword overlap or embedding search over summaries
- Inject matched `summary` text into storyboard and narration prompts as **ground truth**
- Use `keywords` to constrain anchor phrases in semantic plans

---

### `concept_graph.json`

**What it contains:** (Produced by semantic builder — **not in repo today**.) Directed edges between concepts: `{source, target, relation}` e.g. "Dalton's model → prerequisite → Thomson model → Rutherford experiment".

**Why it matters:** Enables **prerequisite-aware** lesson planning. The video should not explain Rutherford's model without acknowledging Thomson's plum pudding model if the textbook assumes it.

**How LLM / planning should use it:**
- Before storyboard: fetch prerequisite chain for matched node
- Scene 1 (intro): recap prerequisites briefly
- Scene 2–4: core concept progression following graph order
- Scene 5 (summary): link forward to child concepts (e.g. Bohr model)

---

### `pedagogical_metadata.json`

**What it contains:** (Semantic builder — **missing today**.) Per-node pedagogy: `difficulty_estimate`, `misconceptions[]`, `worked_examples[]`, `exam_relevance`, `analogy_suggestions`, `notation_conventions`.

**Why it matters:** Separates **what the book teaches** from **how to teach it**. Prevents the LLM from inventing wrong exam framing or skipping common misconceptions.

**How LLM / planning should use it:**
- `build_storyboard()`: set scene difficulty and pacing from `difficulty_estimate`
- `write_all_narrations()`: explicitly address `misconceptions[]` in scene 3 or 4
- `build_semantic_plan()`: populate equation/diagram slots from `worked_examples[]`
- Explanation package in `api.py`: use real `learning_objectives` if stored here instead of LLM-generated ones

---

### `retrieval_metadata.json`

**What it contains:** (Semantic builder — **missing today**.) Index mapping `node_id` → evidence pointers: page ranges, chunk IDs, token counts, optional embedding IDs.

**Why it matters:** Connects abstract tree nodes to **verifiable source text** in `extracted_pages.json`.

**How LLM / planning should use it:**
- Given matched node, look up page span
- Fetch exact paragraphs from `extracted_pages.json`
- Include excerpts in prompt as `"TEXTBOOK EVIDENCE (do not contradict):"` blocks
- Enables post-hoc audit: "this narration sentence maps to page 47"

---

### `extracted_pages.json`

**What it contains:** (Semantic builder — **missing today**.) Raw or cleaned page-level text from the PDF, keyed by page number.

**Why it matters:** **Ground truth evidence layer.** Summaries can drift; extracted text cannot (modulo OCR errors).

**How LLM / planning should use it:**
- Retrieve 1–3 pages around matched node span
- Pass as context for narration (quote-friendly phrases become anchor phrases)
- Manim templates: equation slots should copy notation exactly from extracted text

---

### `validated_toc.json`

**What it contains:** (Semantic builder — **missing today**.) Table of contents extracted and validated against PDF structure — chapter titles, page numbers, validation pass/fail flags.

**Why it matters:** Quality gate. If TOC validation fails, indexing should not proceed to video generation.

**How LLM / planning should use it:**
- Frontend breadcrumb display
- Sanity check that `structure.json` aligns with physical book chapters
- Reject or warn on user topic selection if node is in an unvalidated section

---

### `tree.json` (current partial artifact)

**What it contains:** Present at `topic2manim/results/tree.json`. Rich semantic tree for NCERT Physics Class IX: `document` metadata + nested `tree[]` with `node_id`, `type` (chapter/section/concept), `page_range`, `summary`, `keywords`, `content_type`, `difficulty_estimate`.

**Why it matters:** Shows what the semantic builder *can* produce — more pedagogical fields than raw PageIndex `structure.json`.

**How LLM / planning should use it:** Same as `structure.json` + partial `pedagogical_metadata` (difficulty, content_type). **Should be the merged canonical tree** after integration, not a separate orphan file.

**Current problem:** Exists at monorepo `results/` but is **never loaded** by backend or frontend.

---

### `dependency.json` (current partial artifact)

**What it contains:** Present at `topic2manim/results/dependency.json`. Graph of prerequisite edges per node: `{node_id: {prerequisites: [{node_id, title, confidence, relation}], dependency_depth}}`.

**Why it matters:** Same role as `concept_graph.json` but focused on **learning order** with confidence scores and natural-language `relation` explanations.

**How LLM / planning should use it:**
- When user selects "Equations of motion", retrieve prerequisites ("distance vs displacement", "uniform motion") and inject into storyboard scene 1 recap
- Adjust depth based on `dependency_depth` and learner profile

**Current problem:** Metadata says `created_by: dependency_graph_builder.py` which is **not in the repo**. File is not consumed by video pipeline.

---

## 5. Current Video Generation Pipeline (How It Works Today)

### Entry points

| Entry | File | Input |
|-------|------|-------|
| CLI | `backend/main.py` | `topic: str` only |
| API | `backend/api.py` → `run_pipeline_task()` | `topic`, `subject`, API keys, optional `learnerProfile` |

### The 8 steps (CLI and API share the same core)

| Step | Action | Module(s) | Output path |
|------|--------|-----------|-------------|
| 1 | Storyboard (5-scene arc) | `modules/planning/storyboard.py` → `build_storyboard()` | `backend/data/json/storyboard.json` |
| 2 | Semantic plans (template slots + events) | `modules/planning/semantic_plan.py` → `build_all_semantic_plans()` | `backend/data/json/semantic_plan_{N}.json` |
| 3 | Narration scripts | `modules/planning/narration_writer.py` → `write_all_narrations()` | embedded in plans |
| 4 | TTS | `modules/tts/piper_tts.py` → `synthesize()` | `backend/data/audio/scene_{N}.wav` |
| 5 | Sync / timelines | `modules/sync/sync_engine.py` → `synchronize_all()` | `backend/data/timelines/scene_{N}.json`, `master_timeline.json` |
| 6 | Manim compile | `modules/manim/semantic_compiler.py` → `semantic_compile_all()` | `backend/data/manim/scene_{N}.py` |
| 7 | Render | `modules/manim/renderer.py` → `render()` | `backend/data/manim/media/videos/...`, copy to `backend/data/renders/scene_{N}.mp4` |
| 8 | Merge | `modules/video/ffmpeg_merge.py` → `merge()` | `backend/data/renders/final_video.mp4` |

CLI orchestration:

```54:93:topic2manim/backend/main.py
    storyboard = build_storyboard(topic)
    plans = build_all_semantic_plans(storyboard)
    plans = write_all_narrations(plans)
    ...
    timelines = synchronize_all(plans, audio_paths)
    manim_files = semantic_compile_all(plans, timelines)
    ...
    final = merge(scene_mp4s, scene_wavs)
```

### What the LLM currently receives

At each LLM call, inputs are roughly:

| Stage | LLM input today | Curriculum data |
|-------|-----------------|-----------------|
| Explanation package (API only) | `format_learner_context()` + `Topic: {topic}` | **None** |
| Storyboard | `topic`, learner context block, template lists | **None** |
| Semantic plan | Storyboard entry JSON, learner context, template schema | **None** |
| Narration | Plan JSON, learner context, word budget from pace | **None** |
| Manim repair (on render fail) | Broken code + error text | **None** |

The LLM relies on **parametric knowledge** (NVIDIA NIM / Gemini). It does not receive textbook excerpts.

### Where context injection should happen but doesn't

| Function | Should receive | Currently receives |
|----------|----------------|-------------------|
| `build_storyboard()` | `CurriculumContext` with matched node + prerequisites | `topic` string |
| `build_semantic_plan()` | Evidence excerpts + exact terminology | storyboard entry only |
| `write_all_narrations()` | Page-grounded facts, misconceptions to address | plan + learner profile |
| `api.py` explanation stage | `pedagogical_metadata` objectives | LLM-generated JSON |

**Injection point (recommended):** Immediately after query resolution, before step 1:

```python
# Pseudocode — does not exist yet
ctx = retrieval_chain.resolve(document_id, topic)
curriculum_block = curriculum_loader.format_context(ctx)
storyboard = build_storyboard(topic, curriculum_context=curriculum_block, ...)
```

### Role of `semantic_compiler.py` and templates

The compiler is **not an LLM**. It is a deterministic dispatcher:

1. Looks up `TEMPLATES[concept_template]` in `modules/templates/__init__.py` (25+ templates: mechanics simulations + explain layouts).
2. Calls `template_cls.compile(plan, timeline)` to generate Python with `run_time` injected from sync.
3. Validates output and writes `scene_N.py`.

Templates constrain Manim geometry — this is **working and production-ready**. The weakness is upstream: LLM fills template **content slots** (`content.title`, `content.equation`, `events[].anchor_phrase`) without textbook grounding.

---

## 6. Exact Points of Disconnection (Code-Level)

| # | Location | What happens | What's missing |
|---|----------|--------------|----------------|
| 1 | `backend/main.py:56` | `build_storyboard(topic)` | No `document_id`, no `curriculum_context` parameter |
| 2 | `backend/main.py:60` | `build_all_semantic_plans(storyboard)` | No retrieved node metadata passed through |
| 3 | `backend/api.py:367-368` | SSE stage `"retrieving"` + `sleep(1)` | No call to retrieval; cosmetic only |
| 4 | `backend/api.py:420` | `build_storyboard(topic, learner_profile, subject)` | Learner profile yes; curriculum no |
| 5 | `backend/api.py:432-434` | `build_all_semantic_plans(storyboard, learner_profile, topic, subject)` | Same gap |
| 6 | `backend/api.py:107-108, 661-662` | `RESULTS_DIR = backend/results/` mounted at `/results` | Empty dir; real JSON at `topic2manim/results/` |
| 7 | `backend/modules/config.py:14-23` | `PATHS` dict | No `PATHS["curriculum"]` or `PATHS["results"]` pointing to artifact root |
| 8 | **Absent** | `backend/modules/curriculum/curriculum_loader.py` | Should load + format JSON artifacts |
| 9 | **Absent** | `backend/modules/curriculum/retrieval_chain.py` | Should resolve query → nodes + evidence |
| 10 | `PageIndex/pageindex/retrieve.py` | `_retrieve_nodes()`, `get_page_content()` | Never imported by backend |
| 11 | `frontend/src/context/SessionContext.jsx:191-200` | POST `/api/pipeline/run` with `{topic, subject, learnerProfile}` | No `documentId`; no PDF upload step |
| 12 | `frontend/src/screens/KnowledgeGraph.jsx:5-28` | `MOCK_SYLLABUS` constant | Should fetch `/results/<doc>/structure.json` or `tree.json` |
| 13 | **Absent** | `/api/curriculum/upload`, `/api/curriculum/index` | No frontend trigger for PageIndex |
| 14 | **Absent** | `scripts/build_chemistry9_semantic_layer.py` | Cannot produce full artifact set |
| 15 | `backend/api.py:642-658` | `/api/health` checks ffmpeg, manim, piper | Does not verify `structure.json` exists |

### Legacy modules not in the active path (do not confuse with integration)

These exist but are **not called** by `main.py` / `api.py`:

- `modules/planning/scene_json.py` — older scene JSON generator
- `modules/planning/visual_skeleton.py` — stub
- `modules/planning/narration.py` — superseded by `narration_writer.py`
- `modules/llm/gemini_client.py` — unused; routing goes through `nvidia_client.py`

---

## 7. Concrete Example Walkthrough

**Scenario:** User uploads `Chemistry_9.pdf` and requests a video on **"Rutherford Atomic Model"**.

### What should happen (integrated system)

1. **Upload:** Frontend POSTs PDF to `/api/curriculum/upload` → saved as `backend/data/textbooks/Chemistry_9.pdf`.
2. **Index:** Backend runs PageIndex → `backend/results/Chemistry_9.pdf/structure.json` + `summaries.json`.
3. **Enrich:** Semantic builder runs → adds `concept_graph.json`, `pedagogical_metadata.json`, `retrieval_metadata.json`, `extracted_pages.json`, `validated_toc.json`, `dependency.json`.
4. **Graph UI:** Knowledge Graph renders nodes from `structure.json`. User clicks "Rutherford's Model" (`node_id: CHEM9_CH4_S03_C02` hypothetical).
5. **Retrieve:** `retrieval_chain.resolve("Chemistry_9.pdf", "Rutherford atomic model")` returns:
   - **Matched node:** Rutherford's alpha scattering experiment
   - **Prerequisites (from `concept_graph.json`):** Thomson plum pudding model, basic atomic structure
   - **Pedagogy (from `pedagogical_metadata.json`):** difficulty 0.55, misconception "electrons embedded in positive sphere like plum pudding"
   - **Evidence (from `extracted_pages.json` via `retrieval_metadata.json`):** pages 52–54 text about gold foil experiment
6. **Load context:** `curriculum_loader.format_context()` produces prompt block:

   ```
   == CURRICULUM CONTEXT ==
   Document: NCERT Chemistry Class IX
   Breadcrumb: Chapter 4 Structure of the Atom → 4.2 Rutherford's Model
   Prerequisites: Thomson model (summary: ...), Alpha particle properties (...)
   Evidence excerpt: "Rutherford directed a beam of alpha particles at a thin gold foil..."
   Misconceptions to address: ...
   Difficulty: 0.55 (standard)
   ```

7. **Storyboard:** LLM receives context + learner profile. Output:
   - Scene 1 (intro): Thomson recap + experiment setup
   - Scene 2 (diagram): Gold foil scattering diagram — labels from evidence text
   - Scene 3 (comparison): Plum pudding vs nuclear model
   - Scene 4 (equation/concept_card): Rutherford model conclusions (mostly empty nucleus)
   - Scene 5 (summary): Forward link to Bohr model (child node in graph)
8. **Semantic plans:** Template slots use **exact terms** from evidence ("nucleus", "mostly empty space", "alpha particles"). Anchor phrases are substrings planned for narration.
9. **Narration:** Script quotes and paraphrases page 52–54; addresses plum pudding misconception explicitly.
10. **TTS → sync → compile → render → merge:** Unchanged deterministic pipeline.
11. **Result:** Video traceable to textbook pages 52–54; chat panel shows breadcrumb and prerequisites from real JSON.

### What happens today

1. **Upload:** No upload endpoint. PDF is never accepted.
2. **Index:** PageIndex not invoked. No `structure.json` for Chemistry.
3. **User types** "Rutherford atomic model" in Workspace search box.
4. **`SessionContext.startPipeline()`** POSTs `{topic: "Rutherford atomic model", subject: "Chemistry", learnerProfile: {...}}` to `/api/pipeline/run`.
5. **API** sleeps 1s, labels stage `"retrieving"`, then asks NVIDIA LLM to invent an explanation package from general knowledge.
6. **`build_storyboard("Rutherford atomic model", ...)`** — LLM picks templates (maybe `concept_card`, `comparison`, `diagram`) based on topic name alone. May confuse Rutherford scattering with Bohr orbits.
7. **Semantic plans / narration** — content invented. Anchor phrases not tied to any PDF page.
8. **Manim video renders successfully** — pipeline engineering works — but content may:
   - Use wrong historical ordering (skip Thomson)
   - Use incorrect exam framing
   - Miss NCERT-specific notation or examples
9. **`concept_graph.json` and `pedagogical_metadata.json`** — do not exist for Chemistry; even if they did, nothing reads them.
10. **Knowledge Graph** still shows hardcoded Chemistry/Physics mock nodes unrelated to any upload.

---

## 8. What Needs to Be Built Next (Integration Glue)

Build these **minimal components** in order. Each is small in scope but unblocks the next.

### 8.1 Canonical paths (configuration)

**File:** extend `backend/modules/config.py`

```python
CURRICULUM_RESULTS = ROOT.parent / "results"   # or ROOT / "results" — pick one
PATHS["curriculum_results"] = CURRICULUM_RESULTS
PATHS["textbooks"] = ROOT / "data" / "textbooks"
```

Update FastAPI mount to serve the same directory:

```python
app.mount("/results", StaticFiles(directory=str(CURRICULUM_RESULTS)), ...)
```

Copy or symlink existing `topic2manim/results/tree.json` into the canonical location.

### 8.2 `curriculum_loader.py`

**Path:** `backend/modules/curriculum/curriculum_loader.py`

**Responsibilities:**
- `load_document(document_id: str) -> CurriculumDocument` — reads all JSON files from `results/<document_id>/`
- `get_node(document, node_id) -> Node`
- `format_context(ctx: CurriculumContext) -> str` — produces the markdown block injected into LLM prompts
- Handle missing files gracefully (warn if `pedagogical_metadata.json` absent, fall back to `summaries.json` only)

**Does not call LLMs.** Pure file I/O + string formatting.

### 8.3 `retrieval_chain.py`

**Path:** `backend/modules/curriculum/retrieval_chain.py`

**Responsibilities:**
- `resolve(document_id, query: str) -> CurriculumContext`
- Step 1: Search `summaries.json` / tree nodes (reuse logic from `PageIndex/pageindex/retrieve.py:_retrieve_nodes` or port it)
- Step 2: Expand prerequisites via `dependency.json` or `concept_graph.json`
- Step 3: Attach pedagogy from `pedagogical_metadata.json`
- Step 4: Fetch evidence pages via `retrieval_metadata.json` → `extracted_pages.json`
- Return structured object consumed by `curriculum_loader.format_context()`

**Optional:** Wrap PageIndex's `PageIndexClient` for agentic multi-hop retrieval later; start with heuristic search already in `retrieve.py`.

### 8.4 Pipeline wiring

**Files to modify:**

| File | Change |
|------|--------|
| `backend/main.py` | Add `--document-id` arg; call `retrieval_chain.resolve()` before storyboard |
| `backend/api.py` | Accept `documentId` in `PipelineRunRequest`; replace fake retrieve stage with real call |
| `backend/modules/planning/storyboard.py` | Add `curriculum_context: str \| None` parameter; append to prompt |
| `backend/modules/planning/semantic_plan.py` | Same |
| `backend/modules/planning/narration_writer.py` | Same; pass evidence excerpts for fact grounding |

### 8.5 PDF upload + indexing API

**New routes in `backend/api.py`:**

| Route | Action |
|-------|--------|
| `POST /api/curriculum/upload` | Save PDF to `data/textbooks/` |
| `POST /api/curriculum/index/{document_id}` | Subprocess: `PageIndex/run_pageindex.py --pdf_path ...` then semantic builder |
| `GET /api/curriculum/status/{document_id}` | SSE or polling for indexing progress |
| `GET /api/curriculum/documents` | List indexed documents |

### 8.6 Frontend wiring

| File | Change |
|------|--------|
| New upload component or `Library.jsx` | PDF file input → `/api/curriculum/upload` + index trigger |
| `KnowledgeGraph.jsx` | Replace `MOCK_SYLLABUS` with fetch from `/results/<docId>/tree.json` |
| `SessionContext.jsx` | Include `documentId` in pipeline POST body |
| `Workspace.jsx` | Show real breadcrumb from resolved node |

### 8.7 Restore semantic builder scripts

Copy from archived curriculum repo (or rebuild):

- `scripts/build_chemistry9_semantic_layer.py`
- `dependency_graph_builder.py`

Without these, you only get PageIndex's 3-file output, not the full pedagogical layer.

### 8.8 Minimum viable integration (MVP) scope

If you need the **smallest working slice** first:

1. `curriculum_loader.py` reads existing `topic2manim/results/tree.json` + `dependency.json`
2. `retrieval_chain.py` does keyword match on node titles/summaries
3. Inject formatted context into `build_storyboard()` only
4. Wire `documentId="NCERT_PHYSICS_9"` hardcoded in API until upload exists

This proves end-to-end context injection before building PDF upload.

---

## Quick Reference: Key File Locations

| Purpose | Path |
|---------|------|
| Video CLI entry | `backend/main.py` |
| Video API + pipeline task | `backend/api.py` |
| Path configuration | `backend/modules/config.py` |
| Storyboard LLM planner | `backend/modules/planning/storyboard.py` |
| Semantic plan LLM planner | `backend/modules/planning/semantic_plan.py` |
| Narration LLM writer | `backend/modules/planning/narration_writer.py` |
| Learner profile → prompt | `backend/modules/planning/profile_context.py` |
| Manim template compiler | `backend/modules/manim/semantic_compiler.py` |
| Template registry (25+ templates) | `backend/modules/templates/__init__.py` |
| Sync / timelines | `backend/modules/sync/sync_engine.py` |
| Final video output | `backend/data/renders/final_video.mp4` |
| PageIndex CLI | `PageIndex/run_pageindex.py` |
| PageIndex artifact writer | `PageIndex/pageindex/page_index.py` (`_write_output_artifacts`) |
| PageIndex retrieval (port this) | `PageIndex/pageindex/retrieve.py` |
| Partial curriculum artifacts | `results/tree.json`, `results/dependency.json` |
| API results mount (currently empty) | `backend/results/` |
| Frontend pipeline trigger | `frontend/src/context/SessionContext.jsx` |
| Frontend mock knowledge graph | `frontend/src/screens/KnowledgeGraph.jsx` |
| **To create:** curriculum loader | `backend/modules/curriculum/curriculum_loader.py` |
| **To create:** retrieval chain | `backend/modules/curriculum/retrieval_chain.py` |
| **To restore:** semantic builder | `scripts/build_chemistry9_semantic_layer.py` |
| Integration design doc (profile) | `docs/PROFILE_CONTEXT_IMPLEMENTATION.md` |
| Product spec (intended UX) | `../specui.html` (workspace root) |
