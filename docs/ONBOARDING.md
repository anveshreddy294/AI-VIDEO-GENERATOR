> **Note:** This is a **locally modified version** of [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex). It runs entirely on your machine using **Ollama** instead of OpenAI. No cloud API key is required for basic indexing.

# PageIndex Local Onboarding Guide

Welcome. This guide helps you set up and run PageIndex inside the `topic2manim` project on your Mac — especially Apple Silicon (M2/M4). It assumes you are already inside the `PageIndex/` folder.

---

## 1. Overview

PageIndex turns a long PDF (textbook, manual, report) into a **hierarchical tree index** — like a smart table of contents with page ranges and optional summaries. Downstream tools in `topic2manim` use that tree to find the right sections when generating educational videos.

This copy of PageIndex was modified to call **local models through Ollama** (`pageindex/local_llm.py`) instead of the original OpenAI API. That keeps indexing offline and free, at the cost of slower runs and occasional quality gaps on smaller MacBooks.

---

## 2. Prerequisites

Install these before you start:

| Requirement | Notes |
|-------------|-------|
| **Ollama** | [https://ollama.com](https://ollama.com) — local LLM server |
| **A local model** | Recommended: `qwen2.5:3b` (fast, lighter) or `qwen2.5-coder:7b` (better JSON/structure, slower) |
| **Python 3.10+** | Check with `python3 --version` |
| **Git** | Only needed if cloning the repo |

Optional (not required for local-only runs):

- A `.env` file with `GEMINI_API_KEY` — only used if Gemini fallback is enabled in `pageindex/config.yaml` (disabled by default).

---

## 3. Step-by-Step Setup (Mac — Apple Silicon)

### 1. Install Ollama

Download and install from [https://ollama.com/download](https://ollama.com/download), or:

```bash
brew install ollama
```

### 2. Start the Ollama server

Ollama usually starts automatically after install. If not:

```bash
ollama serve
```

Leave this running in a separate terminal tab, or rely on the macOS app.

Verify it is up:

```bash
curl http://127.0.0.1:11434/api/tags
```

### 3. Pull a recommended model

For a first run on MacBook Air M2/M4, start with the smaller model:

```bash
ollama pull qwen2.5:3b
```

When you want better structure quality (and can wait longer):

```bash
ollama pull qwen2.5-coder:7b
```

> **Heads-up:** `pageindex/config.yaml` references stage-specific models like `ollama/gemma4:e4b`. If you have not pulled those, PageIndex will try to fall back to whatever you *have* installed. Pulling `qwen2.5:3b` alone is enough to get started.

### 4. (Optional but recommended) Create a virtual environment

From inside `PageIndex/`:

```bash
cd /path/to/topic2manim/PageIndex
python3 -m venv venv
source venv/bin/activate
```

### 5. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install ollama
```

The last line matters: `ollama` is used by the local inference layer but is not always listed in `requirements.txt`. If you see `ModuleNotFoundError: ollama`, run that install again inside your venv.

---

## 4. Where to Place Your PDF

**Recommended location:**

```
PageIndex/examples/documents/your_textbook.pdf
```

**Why this folder?**

- Paths stay short and predictable.
- Matches examples in the parent `topic2manim/README.md`.
- Works with relative paths when your shell is already in `PageIndex/`.

**Create the folder if it does not exist:**

```bash
mkdir -p examples/documents
cp ~/Downloads/your_textbook.pdf examples/documents/
```

**Alternative — any absolute path:**

```bash
--pdf_path "/Users/you/Documents/NCERT_Physics_9.pdf"
```

PageIndex resolves paths relative to your current directory, the `PageIndex/` script directory, or an absolute path.

> **Important — filenames with spaces:** Always wrap the path in **double quotes**. Without quotes, the shell splits the path and you get `error: unrecognized arguments: Kerala State Syllabus...`
>
> ```bash
> # Wrong — shell sees extra arguments after "SCERT"
> --pdf_path examples/documents/SCERT Kerala State Syllabus 10th.pdf
>
> # Correct
> --pdf_path "examples/documents/SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf"
> ```

> There are currently **no sample PDFs** checked into this repo (PDFs are large and gitignored). You must supply your own.

---

## 5. How to Run PageIndex

Always run from inside `PageIndex/` so output paths and imports resolve correctly.

**Recommended command:**

```bash
cd /path/to/topic2manim/PageIndex
source venv/bin/activate   # if using a venv
/Users/abhisheklgowda/Desktop/manim/topic2manim/PageIndex/examples/documents/SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf
PYTHONPATH=. python run_pageindex.py --pdf_path examples/documents/SCERT Kerala State Syllabus 10th.pdf --model qwen2.5:3b
```

**Useful flags:**

| Flag | Purpose |
|------|---------|
| `--pdf_path` | **Required.** Path to your PDF |
| `--model` | Override the model in `pageindex/config.yaml` (e.g. `qwen2.5:3b`, `qwen2.5-coder:7b`) |
| `--demo` | Quick proof-of-concept: limits pages, shallow tree, CPU-friendly settings |
| `--max-pages N` | Index only the first N pages (great for testing) |
| `--cpu` / `--gpu` | Execution profile (default: CPU on Mac) |
| `--no-summaries` | Skip summary generation — faster, tree only |
| `--resume` | Continue from checkpoints in `results/` if a prior run stopped |
| `--force-reindex` | Ignore cache and re-index from scratch |
| `--no-gemini-fallback` | Fail locally instead of calling Gemini API |

**Example — full textbook (slow on Air):**

```bash
PYTHONPATH=. python run_pageindex.py \
  --pdf_path "examples/documents/SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf" \
  --model qwen2.5:3b
```

Use the **exact filename** from `ls examples/documents/` — your PDF is not named `SCERT Kerala State Syllabus 10th.pdf`.

**Example — fast smoke test:**

```bash
PYTHONPATH=. python run_pageindex.py \
  --pdf_path examples/documents/your_textbook.pdf \
  --demo \
  --model qwen2.5:3b
```

### What happens after you run it

1. PageIndex extracts text from each PDF page (PyMuPDF).
2. A local Ollama model detects the table of contents and builds a section tree.
3. Summaries and keywords are generated per section (unless `--no-summaries`).
4. JSON artifacts are written under `PageIndex/results/`.
5. The terminal prints the document tree and a `PIPELINE COMPLETE` message when finished.

**Expect minutes, not seconds**, on a MacBook Air — especially for 100+ page textbooks with summaries enabled.

---

## 6. Understanding the Output

Output lives under:

```
PageIndex/results/
```

Because of how the CLI and pipeline name folders, you may see **two related directories** for the same PDF:

| Folder pattern | What it contains |
|----------------|------------------|
| `results/MyBook.pdf/` | **Full artifact set** from the indexing pipeline (checkpoints, metrics, summaries) |
| `results/MyBook/` | Final `structure.json` + cache hash written by `run_pageindex.py` |

For a PDF named `Chemistry_9.pdf`, look in:

```
PageIndex/results/Chemistry_9.pdf/
```

### Key files

| File | Description |
|------|-------------|
| `structure.json` | **Main deliverable** — document metadata + hierarchical tree with page ranges, summaries, keywords |
| `tree_structure.json` | Same tree in an export-friendly nested format |
| `summaries.json` | Flat list of per-node summaries (when summaries are enabled) |
| `extracted_pages.json` | Raw page text extracted from the PDF |
| `validated_toc.json` | Validated table-of-contents entries |
| `toc_candidates.json` | Raw TOC detection output |
| `semantic_validation.json` | Validation report for the final tree |
| `pipeline_metrics.json` | Timing, inference call counts, stage failures |
| `structure.json.hash` | Cache fingerprint (in the folder *without* `.pdf` suffix) |

Open `structure.json` first. A healthy tree has multiple chapter/section nodes with sensible `start_page` / `end_page` values — not just one giant node covering the whole book.

Logs from each run are saved separately under:

```
PageIndex/logs/<pdf_name>_<timestamp>.json
```

---

## 7. Common Issues & Troubleshooting (Mac M2/M4)

### Very slow or laggy performance

This is normal on MacBook Air with local models.

- Use `--demo` or `--max-pages 10` while learning the workflow.
- Prefer `qwen2.5:3b` over `qwen2.5-coder:7b` or larger Gemma variants.
- Run with `--no-summaries` to skip the slowest stage.
- Close other heavy apps; Ollama uses unified memory on Apple Silicon.
- Increase timeouts in `pageindex/config.yaml` under `cpu_mode.inference_timeout_seconds` if runs abort near the limit (default: 600s).

### Empty or incomplete tree / flat `structure.json`

Known limitation on local small models:

- The tree may collapse to a few top-level chapters with weak titles (e.g. leading dots, missing subsections).
- `pipeline_metrics.json` may show stage failures (e.g. `no_toc_outline` failures) even when a partial tree is saved.
- Textbook PDFs without a clear printed TOC are harder — the model must infer structure from body text.

**Things to try:**

```bash
# Retry with more pages context but still bounded
PYTHONPATH=. python run_pageindex.py \
  --pdf_path examples/documents/your_textbook.pdf \
  --max-pages 30 \
  --model qwen2.5-coder:7b \
  --force-reindex
```

Check `semantic_validation.json` and `pipeline_metrics.json` for what failed.

### `unrecognized arguments: Kerala State Syllabus...`

Your PDF path contains **spaces** and was not quoted. Wrap the full path in double quotes (see section 4).

Also confirm the filename matches exactly:

```bash
ls "examples/documents/"
```

### Ollama connection errors

```
Could not list Ollama models / Connection refused
```

- Ensure Ollama is running: `ollama serve` or open the Ollama app.
- Test: `curl http://127.0.0.1:11434/api/tags`
- Restart Ollama after pulling a new model.

### Model not found

```
Ollama model 'gemma4:e4b' not available
```

Pull the model you intend to use:

```bash
ollama pull qwen2.5:3b
```

Or override on the command line:

```bash
--model qwen2.5:3b
```

PageIndex will fall back to another installed model if the configured one is missing, but results may be inconsistent — best to pull the model you want explicitly.

### `ModuleNotFoundError: pageindex` or `ollama`

Run from `PageIndex/` with `PYTHONPATH=.` and use the venv Python:

```bash
PYTHONPATH=. ./venv/bin/python run_pageindex.py --pdf_path ...
./venv/bin/pip install ollama
```

### Long processing time

| PDF size | Model | Rough expectation on MacBook Air |
|----------|-------|----------------------------------|
| 10 pages, `--demo` | `qwen2.5:3b` | ~1–5 minutes |
| 50 pages + summaries | `qwen2.5:3b` | ~10–30+ minutes |
| Full 200-page textbook | `qwen2.5:3b` | Often 30–90+ minutes; machine may feel sluggish |

Use `--resume` if a run stops mid-way — checkpoints in `results/<pdf>.pdf/` avoid re-extracting pages.

### Lighter models vs. better quality

| Model | Speed | Quality | Best for |
|-------|-------|---------|----------|
| `qwen2.5:3b` | Fastest | Adequate for testing | First setup, `--demo`, iteration |
| `qwen2.5-coder:7b` | Slower | Better JSON / structure | Production indexing when you can wait |
| `gemma3:4b` / `gemma4:e4b` | Medium | Config defaults reference these | Pull only if you want to match `config.yaml` exactly |

---

## 8. Quick Test Command

After setup, run this to verify Ollama + PageIndex work end-to-end (uses demo limits — should finish in a few minutes):

```bash
cd /path/to/topic2manim/PageIndex
source venv/bin/activate

PYTHONPATH=. python run_pageindex.py \
  --pdf_path examples/documents/your_textbook.pdf \
  --demo \
  --model qwen2.5:3b
```

**Success looks like:**

- No Python import errors
- Terminal prints a document tree (even if small)
- `PageIndex/results/your_textbook.pdf/` contains `structure.json`
- `pipeline_metrics.json` shows mostly successful stages

If you do not have a PDF yet, place any short PDF (even 5–10 pages) in `examples/documents/` first.

---

## 9. Next Steps After Indexing

PageIndex is the **curriculum intelligence** layer inside the larger `topic2manim` project. Its output feeds the video-generation pipeline:

1. **`structure.json` / `summaries.json`** — section-level content map for retrieval (which pages cover which topic).
2. **Future semantic layer** — scripts at the `topic2manim/` root can enrich artifacts into `concept_graph.json`, `dependency.json`, and richer `tree.json` files under `topic2manim/results/`.
3. **Video engine** — `topic2manim/backend/` uses curriculum context (when wired) to plan Manim scenes, narration, and explanations for a given topic.

Today, indexing and video generation are **separate steps**: run PageIndex here first, then use or build integration scripts that read from `PageIndex/results/`. See `topic2manim/INTEGRATION_GUIDE.md` and `topic2manim/README.md` for how artifacts connect to the LearnOS frontend and Manim backend.

---

## Quick reference

```bash
# One-time setup
brew install ollama          # or download from ollama.com
ollama pull qwen2.5:3b
cd topic2manim/PageIndex
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && pip install ollama
mkdir -p examples/documents

# Index a PDF
PYTHONPATH=. python run_pageindex.py \
  --pdf_path examples/documents/your_textbook.pdf \
  --model qwen2.5:3b

# Output
ls PageIndex/results/your_textbook.pdf/
```

You do not need an OpenAI API key for this workflow. Take your time on the first full textbook run — local indexing is slow, but once `structure.json` exists, you can reuse it without re-running the model (`--force-reindex` only when the PDF changes).
