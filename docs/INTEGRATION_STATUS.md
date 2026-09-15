# PageIndex ↔ Video Pipeline — Integration Status Report

**Repository:** `topic2manim/` (RAG-MANIM monorepo)  
**Report date:** 2026-06-14  
**Audience:** Developers integrating curriculum intelligence into the Manim video engine  
**Companion doc:** [`INTEGRATION_GUIDE.md`](./INTEGRATION_GUIDE.md) (design spec — partially outdated)

---

## Executive Summary

PageIndex indexing is **working** for two textbooks. The **API video pipeline** has been wired to retrieve curriculum context from on-disk PageIndex artifacts and inject it into all LLM planning stages. However, integration is **backend-only, single-document, and invisible to the UI**.

| Layer | Status | Score |
|-------|--------|-------|
| PageIndex indexing | ✅ Both PDFs indexed with rich artifacts | 8/10 |
| Backend retrieval glue | ⚠️ Works; env-based doc selection; keyword matching | 6/10 |
| LLM pipeline injection (API) | ✅ Context flows to all 4 LLM stages | 7/10 |
| Prerequisite / pedagogy layer | ❌ `concept_graph.json` not built | 2/10 |
| CLI (`main.py`) | ❌ No retrieval | 1/10 |
| Frontend | ❌ Mock syllabus; no `documentId` | 1/10 |
| Dev ergonomics | ⚠️ Import path fixed; results mount still wrong | 4/10 |

### Integration Health Score: **5 / 10**

The system is **past proof-of-concept on the API path** but **not yet usable end-to-end** from the product UI without manual server configuration.

---

## 1. What Was Integrated (Since INTEGRATION_GUIDE.md)

The integration guide describes a fully disconnected system. The codebase has since gained meaningful backend wiring that the guide does not reflect.

### 1.1 New retrieval module (replaces planned `curriculum/` package)

The guide calls for:

- `backend/modules/curriculum/curriculum_loader.py`
- `backend/modules/curriculum/retrieval_chain.py`

**Actual implementation:** a single module at `backend/modules/retrieval/pageindex_retriever.py` that combines loader + retrieval responsibilities.

| Planned function | Actual equivalent | File |
|------------------|-------------------|------|
| `load_document(document_id)` | `DocumentArtifacts(results_dir)` / `DocumentArtifacts.from_pdf_path()` | `PageIndex/pageindex/results_loader.py:42–63` |
| `resolve(document_id, query)` | `retrieve_curriculum(topic)` → structured dict | `pageindex_retriever.py:195–231` |
| `format_context(ctx)` | `retrieve_curriculum_context(topic)` → prompt string | `pageindex_retriever.py:189–192` |
| Node search | `_score_node()` keyword overlap over `structure.json` tree | `pageindex_retriever.py:99–108, 134–141` |
| Page evidence | `artifacts.get_page_text(start, end)` | `results_loader.py:88–112` |

### 1.2 API pipeline wiring

`backend/api.py` → `run_pipeline_task()` now performs **real retrieval** at stage 0:

```python
# api.py:372–407
curriculum_sections = retrieve_curriculum_sections(topic)
curriculum_context = retrieve_curriculum_context(topic)
```

Context is passed downstream to:

| Stage | Function | Lines |
|-------|----------|-------|
| Explanation package | NVIDIA LLM prompt with `CURRICULUM CONTEXT:` block | `api.py:417–418` |
| Storyboard | `build_storyboard(..., curriculum_context=..., curriculum_sections=...)` | `api.py:464–469` |
| Semantic plans | `build_all_semantic_plans(..., curriculum_context=..., curriculum_sections=...)` | `api.py:482–488` |
| Narration | `write_all_narrations(..., curriculum_context=..., curriculum_sections=...)` | `api.py:493–499` |

The old cosmetic `asyncio.sleep(1.0)` on the `"retrieving"` stage has been **removed**.

### 1.3 Planning modules accept curriculum context

All three LLM planners inject `{curriculum_context}` into prompts and instruct the model to treat it as primary source of truth:

| Module | Parameter(s) | Prompt injection |
|--------|--------------|------------------|
| `storyboard.py` | `curriculum_context`, `curriculum_sections` | Lines 35–47, 134–155, 158–164 |
| `semantic_plan.py` | `curriculum_context`, `curriculum_sections` | Lines 37, 86, 137–177, 230–247 |
| `narration_writer.py` | `curriculum_context`, `curriculum_sections` | Lines 35–39, 62–63, 74–178 |

### 1.4 PageIndex health endpoint

New diagnostic route: `GET /api/pageindex/health` (`api.py:701–742`)

Returns artifact list, node/chapter counts, validation status, and active results directory.

### 1.5 Import path fix (2026-06-14)

**Problem:** `pageindex_retriever.py` imports `PageIndex.pageindex.results_loader`, but `api.py` only added `backend/` to `sys.path`. Running `cd backend && python api.py` crashed with `ModuleNotFoundError: No module named 'PageIndex'`.

**Fix:** `pageindex_retriever.py` now inserts the repo root (`topic2manim/`) onto `sys.path` before the PageIndex import (lines 9–11).

---

## 2. Indexed Documents (On Disk Today)

Both textbooks have been indexed under `PageIndex/results/<pdf_basename>/`:

| Document | Results path | Nodes (approx.) | Key artifacts present |
|----------|--------------|-----------------|-------------------------|
| SCERT Class 9 Chemistry | `PageIndex/results/Chemistry.pdf/` | 33 | `structure.json`, `tree.json`, `summaries.json`, `extracted_pages.json`, `validated_toc.json`, `semantic_validation.json` |
| SCERT Kerala Physics 10 Part 1 | `PageIndex/results/SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf/` | 20 | Same core set |

### Artifacts **missing** from both directories

| Artifact | Purpose | Status |
|----------|---------|--------|
| `concept_graph.json` | Prerequisite edges between concepts | ❌ Not generated |
| `pedagogical_metadata.json` | Difficulty, misconceptions, worked examples | ❌ Not generated |
| `retrieval_metadata.json` | Node → page chunk index | ❌ Not generated |
| `dependency.json` | Learning-order prerequisite graph | ❌ Not present |

**Builder script exists** but has not been run on these indexes:

```bash
PageIndex/scripts/build_chemistry9_semantic_layer.py
```

---

## 3. Component-by-Component Status

### 3.1 Checklist vs INTEGRATION_GUIDE.md

| Item | Status | Evidence |
|------|--------|----------|
| `backend/modules/curriculum/curriculum_loader.py` | ❌ **Not Implemented** | No `curriculum/` directory; logic in `pageindex_retriever.py` |
| `backend/modules/curriculum/retrieval_chain.py` | ❌ **Not Implemented** | Same |
| `build_storyboard()` accepts `curriculum_context` | ✅ **Implemented** | `storyboard.py:158–164` |
| `build_all_semantic_plans()` accepts curriculum context | ✅ **Implemented** | `semantic_plan.py:230–247` |
| `write_all_narrations()` accepts curriculum context | ✅ **Implemented** | `narration_writer.py:161–178` |
| `api.py` accepts `documentId` | ⚠️ **Partially Implemented** | Retrieval is real; no `documentId` in `PipelineRunRequest` (`api.py:102–108`) |
| `PageIndex/pageindex/retrieve.py` used by backend | ❌ **Not Implemented** | Backend uses `results_loader.py` + custom scoring; `retrieve.py` unused |
| Unified results directory | ❌ **Not Implemented** | Real data at `PageIndex/results/`; API mounts empty `backend/results/` (`api.py:113–114, 766`) |
| Frontend reads real curriculum JSON | ❌ **Not Implemented** | `KnowledgeGraph.jsx:5–45` uses `MOCK_SYLLABUS` |
| PDF upload + index API | ❌ **Not Implemented** | No `/api/curriculum/*` routes |
| CLI retrieval | ❌ **Not Implemented** | `main.py:56–64` calls planners with topic only |

### 3.2 Document selection (critical limitation)

The retriever resolves which textbook to query via `_resolve_active_doc()` (`pageindex_retriever.py:31–44`):

1. **`PAGEINDEX_ACTIVE_DOC` environment variable** (if set)
2. **Most recently modified** `PageIndex/results/*/structure.json`
3. **Hardcoded fallback:** SCERT Physics 10 PDF filename

**Current default:** Physics 10 (newer mtime). Chemistry topics will match against the **wrong textbook** unless the server process has `PAGEINDEX_ACTIVE_DOC=Chemistry.pdf`.

There is **no per-request document routing** from the frontend or API body.

### 3.3 What the retriever returns

`retrieve_curriculum_sections(topic)` returns up to 3 matched sections, each containing:

```json
{
  "title": "Rutherford's Gold Foil Experiment",
  "breadcrumb": "Unit 1 : Structure of Atom > Rutherford's Gold Foil Experiment",
  "node_id": "...",
  "start_page": 11,
  "end_page": 12,
  "page_numbers": [11, 12],
  "summary": "...",
  "keywords": ["atom", "electron", "proton"],
  "semantic_tags": ["section", "atomic-structure"],
  "learning_objectives": ["..."],
  "prerequisites": [],
  "score": 2.3,
  "content": "[page 11]\n...(up to 3000 chars from extracted_pages.json)...",
  "artifacts_dir": ".../PageIndex/results/Chemistry.pdf"
}
```

`retrieve_curriculum_context(topic)` flattens this into a prompt-ready string with `---` separators between sections.

**Verified retrieval (Chemistry, `PAGEINDEX_ACTIVE_DOC=Chemistry.pdf`):**

- Topic: `"Rutherford atomic model"`
- Match: ✅ 3 sections
- Top node: `"Rutherford's Gold Foil Experiment"`, pages 11–12
- Source text includes plum pudding model content from the textbook
- Prerequisites: `[]` (empty — no `concept_graph.json`)

---

## 4. Data Flow (Actual vs Intended)

### 4.1 Intended flow (from INTEGRATION_GUIDE.md)

```
PDF upload → PageIndex index → results/<doc_id>/ → retrieval_chain.resolve(doc_id, topic)
  → curriculum_loader.format_context() → build_storyboard / semantic_plan / narration → Manim → MP4
```

### 4.2 Actual flow — API path (works with caveats)

```
User types topic in Workspace OR clicks mock KnowledgeGraph node
  → SessionContext.startPipeline(topic, subject)          # no documentId
  → POST /api/pipeline/run
  → pageindex_retriever (env/default doc, keyword match)
  → curriculum_context string + curriculum_sections list
  → LLM stages (explanation, storyboard, plans, narration)
  → deterministic pipeline (TTS → sync → compile → render → merge)
  → final_video.mp4
```

### 4.3 Actual flow — CLI path (disconnected)

```
python main.py "some topic"
  → build_storyboard(topic)                    # no curriculum_context
  → build_all_semantic_plans(storyboard)
  → write_all_narrations(plans)
  → ... render ...
```

### 4.4 Actual flow — Frontend (disconnected from PageIndex)

```
KnowledgeGraph.jsx
  → MOCK_SYLLABUS (10 hardcoded Chemistry/Physics nodes)
  → startPipeline(selectedNode.label, selectedNode.subject)
  → API may retrieve from a *different* real textbook (env/default)
```

The UI graph and the backend retrieval layer are **completely decoupled**.

---

## 5. What Gets Injected Into LLM Prompts

When retrieval matches (`matched: true`), each LLM call receives a block like:

```
== CURRICULUM CONTEXT (implicit via prompt template) ==

[Unit 1 : Structure of Atom > Rutherford's Gold Foil Experiment] (pages 11-12)
Summary: Rutherford's alpha-particle scattering showed that most of the atom is empty space...
Keywords: atom, electron, proton
Tags: section, atomic-structure
Objectives: Understand the key concepts of Rutherford's Gold Foil Experiment.; ...
Source text:
[page 11]
11
Unit 1 :  Structure of Atom
Fig. 1.5
Plum pudding model
...
```

Storyboard additionally receives a **keyword anchor block** built from matched sections (`storyboard.py:134–155`):

```
MATCHED CURRICULUM SECTIONS:
  • Unit 1 : Structure of Atom > Rutherford's Gold Foil Experiment [pp. 11-12] — key terms: atom, electron, proton
```

When retrieval fails (`matched: false`), prompts fall back to parametric LLM knowledge with an empty curriculum block.

---

## 6. Gaps and Risks

### P0 — Blocks reliable testing

| Gap | Impact | Fix |
|-----|--------|-----|
| No `documentId` in API / frontend | Chemistry requests may hit Physics artifacts | Add `documentId` to `PipelineRunRequest` + `SessionContext` |
| Default doc = newest index (Physics) | Silent wrong-textbook grounding | Set `PAGEINDEX_ACTIVE_DOC` in `.env` or pass doc per request |

### P1 — Reduces grounding quality

| Gap | Impact | Fix |
|-----|--------|-----|
| No `concept_graph.json` | Prerequisites always `[]` | Run `build_chemistry9_semantic_layer.py` on both PDF dirs |
| Keyword-only matching | Weak matches (e.g. "Newton laws" → "Laws of Reflection") | Improve scoring; consider porting `retrieve.py:_retrieve_nodes()` |
| Curriculum context not persisted in outputs | Cannot audit grounding post-hoc from JSON alone | Save `curriculum_sections` alongside `storyboard.json` |
| `backend/results/` mount is empty | Frontend cannot fetch real tree via `/results/` | Mount `PageIndex/results/` or symlink |

### P2 — Product completeness

| Gap | Impact | Fix |
|-----|--------|-----|
| `KnowledgeGraph.jsx` uses mock data | UI does not reflect indexed textbooks | Fetch `/results/<docId>/structure.json` or `tree.json` |
| No PDF upload / index API | Manual PageIndex CLI only | Implement `/api/curriculum/upload` + `/api/curriculum/index` |
| CLI disconnected | `main.py` ignores curriculum | Mirror API retrieval before storyboard |
| `INTEGRATION_GUIDE.md` outdated | Misleading for new developers | Update or link to this report |

---

## 7. How to Test Integration Today

### 7.1 Start the backend

```bash
cd /Users/abhisheklgowda/Desktop/manim/topic2manim

# Select textbook (add to backend/.env for persistence):
export PAGEINDEX_ACTIVE_DOC=Chemistry.pdf

cd backend && python api.py
# Listens on http://localhost:5000
```

### 7.2 Health check

```bash
curl -s http://localhost:5000/api/pageindex/health | python3 -m json.tool
```

Expect `"status": "ready"` and `"results_dir"` pointing to the chosen PDF's artifact folder.

### 7.3 Retrieval smoke test (no LLM)

```bash
cd /Users/abhisheklgowda/Desktop/manim/topic2manim
PAGEINDEX_ACTIVE_DOC=Chemistry.pdf python3 -c "
import sys; sys.path.insert(0, 'backend')
from modules.retrieval.pageindex_retriever import retrieve_curriculum
r = retrieve_curriculum('Rutherford atomic model')
print('matched:', r['matched'], '| sections:', len(r['sections']))
if r['sections']:
    s = r['sections'][0]
    print('top:', s['title'], '| pages:', s['start_page'], '-', s['end_page'])
print('context chars:', len(r['context_text']))
"
```

### 7.4 Full pipeline (requires NVIDIA API key)

```bash
curl -s -X POST http://localhost:5000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Rutherford atomic model",
    "subject": "Chemistry",
    "nvidiaApiKey": "'"$NVIDIA_API_KEY"'"
  }'
```

Watch server logs for:

```
Retrieved N curriculum sections          # N > 0 = integrated
curriculum_sections topic='Rutherford...' matched=3
Curriculum preview:
[Unit 1 : Structure of Atom > Rutherford's Gold Foil Experiment] (pages 11-12)
```

### 7.5 Inspect outputs

| File | What to look for (integrated) | Disconnected signal |
|------|-------------------------------|---------------------|
| Server logs | `matched > 0`, correct breadcrumb + page refs | `matched=0`, empty preview |
| `backend/data/json/storyboard.json` | Scene titles echo textbook section names | Generic titles unrelated to SCERT |
| `backend/data/json/semantic_plan_*.json` | Labels/phrases from textbook pages | Unrelated mechanics templates |
| SSE `data.script` | Narration mentions textbook-specific terms | Generic parametric explanation |
| `backend/data/renders/final_video.mp4` | Content traceable to pages 11–12 (Chemistry example) | Correct by LLM luck only |

### 7.6 Build semantic layer (prerequisites)

```bash
cd PageIndex
PYTHONPATH=. python scripts/build_chemistry9_semantic_layer.py \
  --results-dir results/Chemistry.pdf

# Repeat for Physics dir, then re-run retrieval smoke test and check prereqs non-empty
```

---

## 8. Recommended Next Steps (Priority Order)

1. **Add `documentId` to API + frontend** — unblocks multi-textbook use without env vars.
2. **Run semantic layer builder** on both indexed PDFs — enables prerequisite injection.
3. **Mount `PageIndex/results/` at `/results`** — enables frontend curriculum graph.
4. **Replace `MOCK_SYLLABUS`** in `KnowledgeGraph.jsx` with fetch from real JSON.
5. **Wire CLI (`main.py`)** to call the same retrieval path as the API.
6. **Persist `curriculum_sections` in pipeline outputs** for auditability.
7. **Update `INTEGRATION_GUIDE.md`** to reflect current API wiring and remaining gaps.

---

## 9. File Reference

| Purpose | Path | Integration status |
|---------|------|-------------------|
| API entry + pipeline | `backend/api.py` | ✅ Retrieval + injection wired |
| CLI entry | `backend/main.py` | ❌ No retrieval |
| Retriever (loader + chain) | `backend/modules/retrieval/pageindex_retriever.py` | ✅ Active |
| Artifact loader | `PageIndex/pageindex/results_loader.py` | ✅ Used by retriever |
| PageIndex retrieval (unused) | `PageIndex/pageindex/retrieve.py` | ❌ Not imported by backend |
| Storyboard planner | `backend/modules/planning/storyboard.py` | ✅ Accepts context |
| Semantic plan planner | `backend/modules/planning/semantic_plan.py` | ✅ Accepts context |
| Narration writer | `backend/modules/planning/narration_writer.py` | ✅ Accepts context |
| Semantic layer builder | `PageIndex/scripts/build_chemistry9_semantic_layer.py` | ⚠️ Exists, not run |
| Chemistry artifacts | `PageIndex/results/Chemistry.pdf/` | ✅ Indexed |
| Physics artifacts | `PageIndex/results/SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf/` | ✅ Indexed |
| API results mount (empty) | `backend/results/` | ❌ Wrong directory |
| Frontend mock graph | `frontend/src/screens/KnowledgeGraph.jsx` | ❌ MOCK_SYLLABUS |
| Frontend pipeline trigger | `frontend/src/context/SessionContext.jsx` | ❌ No documentId |
| Integration design spec | `INTEGRATION_GUIDE.md` | ⚠️ Partially outdated |
| **This report** | `INTEGRATION_STATUS.md` | ✅ Current |

---

## 10. Changelog

| Date | Change |
|------|--------|
| 2026-06-14 | Initial integration status report |
| 2026-06-14 | Fixed `pageindex_retriever.py` sys.path so `api.py` starts without manual `PYTHONPATH` |

---

*For the target architecture and artifact schema, see [`INTEGRATION_GUIDE.md`](./INTEGRATION_GUIDE.md). For PageIndex indexing details, see [`PageIndex/PAGEINDEX_DEEP_DIVE.md`](./PageIndex/PAGEINDEX_DEEP_DIVE.md).*
