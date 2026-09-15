# PageIndex Improvement Plan (Local Ollama on Apple Silicon)

> Scope: Make the local PageIndex pipeline produce a *usable, hierarchical* tree on educational textbooks (e.g. SCERT Physics 10), and feed that tree cleanly into the `topic2manim` video pipeline. Target hardware: MacBook Air M2/M4, 16 GB unified RAM, models served by Ollama.
>
> Honesty note: Local 3B–7B models will not match GPT-4o/Gemini on messy textbook PDFs. The goal here is **reliable, hierarchical, non-empty** output that downstream tools can use — not perfection on the first run.

---

## 1. Executive Summary

The recent SCERT Physics run failed in three reinforcing ways. First, the pipeline is **mis-configured for the hardware**: `config.yaml` declares `generation_model: ollama/qwen2.5:3b` but every heavy stage is force-routed to `ollama/gemma4:e4b` via `stage_models` and `model_router.py`. On a MacBook Air that model is slow, frequently not pulled, and pushes prompts past the context window — which is why `pipeline_metrics.json` shows `no_toc_outline` failing 9/9 and `chapter_summary` failing 3/3, all with `0 ms` latency (i.e. they died *before* inference, at the token-budget gate or a model-not-found error). Second, the **token budget is too tight for whole-segment/whole-chapter prompts** (`max_prompt_tokens: 3500`, `max_context_tokens: 4096`), so summaries and the no-TOC outline are skipped instead of shrunk. Third, **tree quality is weak at the source**: the deterministic TOC parser strips the chapter number but leaves a stray `". "` (producing titles like `". Effects of Electric Current"`), captures only 3 of the chapters, and never recurses into chapter bodies to find sub-sections — so the tree is flat and `semantic_validation.json` correctly reports `passed: false`.

Recommended direction: **(a)** switch the default workhorse to `qwen2.5:3b` for structure/JSON and reserve `qwen2.5-coder:7b` for a quality pass; stop force-routing to `gemma4:e4b`. **(b)** Never send a whole chapter/segment — batch by *bounded* token windows and degrade gracefully (extractive summary) instead of skipping. **(c)** Fix titles and add one level of sub-section detection so the tree is genuinely hierarchical. **(d)** Move validation *earlier* with a cheap retry/repair gate. **(e)** Make the retriever return a small, structured, multi-section context object instead of one raw page blob. Roll this out in three phases so each change is independently testable.

---

## 2. Current State Analysis (from the SCERT run artifacts)

Observed in `results/SCERT .../`:

- **Flat tree, bad titles** — `structure.json` has 4 top-level nodes (`Preface` + 3 chapters), zero children, and titles such as `". Effects of Electric Current"` / `". Reflection of Light"`. `structure` codes jump `1 → 3 → 4` (chapter 2 is missing). Source of the junk: `deterministic_toc.py` `_make_entry`/regex keeps a leading `". "` and `parse_toc` stops at the first parser that yields `>= 3` entries.
- **Validation fails (correctly)** — `semantic_validation.json`: `passed: false`, failing `has_hierarchy_depth`, `chapters_have_children`, `summaries_non_empty`, `min_node_count` (node_count 4 < required 6). The checks in `validators.py` are reasonable; the problem is they run only *after* the full build, with no early gate or retry.
- **Empty summaries** — `summaries.json` shows `summary == title` and `keywords: []` for every node. Chapters have no children, so `_summarize_chapter_node` in `utils.py` has no child summaries to synthesize from and the SLM call fails.
- **Stages dying before inference** — `pipeline_metrics.json`: `no_toc_outline` = 9 calls / 9 failures / `avg_latency_ms: 0`; `chapter_summary` = 3 calls / 3 failures / `0 ms`. Zero latency = failure at the `assert_prompt_within_budget` gate (`TokenBudgetExceeded`) or a model-not-found `ResponseError` `break` — not a real model timeout. `summary_generation` recorded 1 `title_only_call` (the title-only fallback).
- **Model/config contradiction** — `config.yaml` and `model_router.py` route `toc_detection`, `no_toc_outline`, `tree_construction`, `summary_generation`, `chapter_summary` to `ollama/gemma4:e4b`, while the documented/onboarding default is `qwen2.5:3b`. If `gemma4:e4b` isn't pulled, `_resolve_available_model` silently falls back, adding inconsistency.
- **Tight budgets** — `cpu_mode`: `max_prompt_tokens: 3500`, `max_context_tokens: 4096`, `toc_pages_per_batch: 1`, `summary_nodes_per_batch: 1`. Whole-chapter text easily exceeds 3500 tokens, so the budget gate raises before any generation.
- **Retriever fragility** — `backend/modules/retrieval/pageindex_retriever.py` walks `node.get("nodes", [])`, but `structure.json` is a *flat* list with no `nodes` key; it returns only `matches[0]`, keys off `start_index`/`end_index`, and emits raw page text with no title/summary/breadcrumb. With junk titles, keyword matches are unreliable.

---

## 3. Recommended Model Strategy

Principle: use the **smallest model that reliably emits valid JSON** for structure work, and only escalate for a one-shot quality pass. Stop sending heavy models the giant prompts.

- **`qwen2.5:3b` — default workhorse (structure + JSON).** Fast on M2/M4, good instruction-following with `format="json"`. Use for: `toc_detection`, `toc_index_extractor`, `no_toc_outline`, `tree_construction`, `title_cleanup`, `ocr_cleanup`, `doc_description`. This is already the declared `generation_model`; make the `stage_models` actually honor it.
- **`qwen2.5-coder:7b` — quality/repair pass (optional, opt-in).** Better at strict schemas and hierarchy inference. Use for: a *single* TOC-structuring pass and (optionally) `chapter_summary` when the user can wait. Gate behind a `--quality` flag so the default stays fast.
- **`gemma4:e4b` — do not use as a default on the Air.** Too heavy; root cause of the `0 ms` failures when not pulled and of context overflow when it is. Keep it only as an explicit power-user override.
- **Gemini fallback — keep disabled by default** (`enable_gemini_fallback: "no"`). It's a correct last resort but should never be on the hot path for indexing.

Suggested `stage_models` (replace `gemma4:e4b` everywhere except an explicit override):

```yaml
stage_models:
  toc_detection:      "ollama/qwen2.5:3b"
  toc_index_extractor:"ollama/qwen2.5:3b"
  no_toc_outline:     "ollama/qwen2.5:3b"
  tree_construction:  "ollama/qwen2.5:3b"
  summary_generation: "ollama/qwen2.5:3b"
  chapter_summary:    "ollama/qwen2.5:3b"     # -> qwen2.5-coder:7b under --quality
  title_cleanup:      "ollama/qwen2.5:3b"
  ocr_cleanup:        "ollama/qwen2.5:3b"
  extractive_polish:  "ollama/qwen2.5:3b"
  doc_description:    "ollama/qwen2.5:3b"
```

Apple Silicon reality check (with summaries on): `qwen2.5:3b` ≈ a few minutes for `--demo`/30 pages; `qwen2.5-coder:7b` is roughly 2–4× slower. Full 100–200 page textbooks remain a "go get coffee" operation.

---

## 4. Key Technical Improvements Needed (prioritized)

### 4.1 Prompt engineering & schema design
1. **Fix titles at the source.** In `deterministic_toc.py`, strip leading separators after the number capture (e.g. `title = re.sub(r"^[\.\)\-:\s]+", "", title)`) and collapse internal double spaces. Add a tiny `title_cleanup` SLM pass (already a configured stage) only for titles that still look malformed.
2. **Don't bail at first parser.** `parse_toc` currently returns the first layout with `>= 3` entries. Run all layouts, keep the highest-confidence result, and merge gaps (chapter 2 was dropped).
3. **Add one level of sub-section detection.** For each chapter span, run a *bounded* `no_toc_outline`-style pass over that chapter's pages only, asking for `1.1 / 1.2`-style headings → real children. This is the single biggest lever for `has_hierarchy_depth` and `chapters_have_children`.
4. **Tighten schemas / keep `format="json"`.** `local_llm._call_slm` already uses Ollama `format="json"` (good). Keep schemas small and flat; large `model_json_schema()` blocks inflate the system prompt and the budget estimate.

### 4.2 Batching strategy (TOC + summarization) — *highest reliability ROI*
1. **TOC detection: send only TOC-candidate pages, char-capped.** Use `find_toc_page_index` to locate the "TABLE OF CONTENTS" page and send a small window around it (with `toc_page_chars_limit`) rather than scanning page-by-page.
2. **No-TOC outline: bounded sliding windows, never skip.** In `process_no_toc`, size each window to `max_prompt_tokens - reserve`, and on `TokenBudgetExceeded` **split the window in half and retry** instead of `continue` (the current code drops the whole segment — that's the 9 failures).
3. **Summaries: summarize bounded windows, not whole chapters.** In `utils._summarize_chapter_node`, never feed full 40-page body text. Prefer child summaries; if absent, take the chapter's first ~1500 chars + section-heading lines. Already partly capped — make the cap respect the *token* budget, not just char count.
4. **Make budget-skips visible and rare.** Today `TokenBudgetExceeded` is caught and silently skipped. Replace "skip" with "shrink-and-retry, then extractive fallback".

### 4.3 Validation & retry logic
1. **Validate the TOC/outline *before* building the full tree.** Add an early gate: if `< N` entries or `< 2` distinct levels, trigger the sub-section pass / a re-prompt *before* committing to a flat tree.
2. **Promote `validation_warnings` to a hard signal.** When `validate_semantic_tree` fails `min_node_count`/`chapters_have_children`, attempt one structured repair pass (use `hierarchy_repair.py`) before writing `structure.json`.
3. **Guarantee non-empty summaries deterministically.** If the SLM summary fails, fall back to an **extractive** summary (first 1–3 salient sentences via `extractive.py`) so `summaries_non_empty` can pass without a model call. `summary == title` should never be the final state.

### 4.4 Error handling for token limits & timeouts
1. **Recursive batch-shrink** on `TokenBudgetExceeded` and `TimeoutError` (halve the batch / window, retry; the tree-build path at `page_index.py:544` already does this for one path — apply the same pattern to `process_no_toc` and summaries).
2. **Per-stage timeouts** sized to the model: keep `gemma4:e4b`'s 600 s only if someone opts into it; `qwen2.5:3b` can use a much shorter `inference_timeout_seconds` so failures surface fast.
3. **Fail loud on model-not-found.** If the routed model isn't pulled, log a single clear "run `ollama pull qwen2.5:3b`" and stop — don't silently fall back to an arbitrary installed model.

---

## 5. Proposed Changes to `pageindex_retriever.py`

Current issues: walks a non-existent `nodes` key (the artifact is a flat `structure` list), returns only the first match, and emits raw page text with no context. Proposed shape:

- **Return a structured object, not a bare string.** Downstream `storyboard.py` only interpolates `curriculum_context` as text, so keep a `text` field but add structure:

```python
{
  "topic": "reflection of light",
  "matched": True,
  "sections": [
    {
      "title": "Reflection of Light",          # cleaned title
      "breadcrumb": "Physics 10 > Reflection of Light",
      "node_id": "0003",
      "start_page": 79, "end_page": 96,
      "summary": "…",                            # from structure.json
      "keywords": ["reflection", "mirror", …],
      "content": "… (page text, length-capped) …"
    }
  ],
  "context_text": "…concatenated, capped, ready to drop into the storyboard prompt…"
}
```

- **Walk the real schema.** Support both flat (`structure`) and nested (`nodes`/`children`) forms; key off `start_page`/`end_page` with `start_index`/`end_index` as fallback.
- **Rank, don't take `matches[0]`.** Score nodes by title + summary + keyword overlap with the topic; return top-k (e.g. 2–3) sections.
- **Cap content length.** Trim each section's page text to a token/char budget so the storyboard prompt never blows up.
- **Graceful empty path.** If nothing matches, return `matched: False` with `context_text: ""` (current behavior returns `""`, which `api.py` already tolerates — keep that contract).

This is only useful once §4 produces clean titles and non-empty summaries; otherwise keyword matching keeps hitting junk like `". Reflection of Light"`.

---

## 6. Integration Impact on the Video Pipeline

- **`api.py`** (`retrieve_curriculum_context(topic)` at stage 1): if the retriever returns a dict, read `context_text` for the prompt and optionally log `sections` for traceability. Minimal change; keep accepting an empty string.
- **`storyboard.py`** (`build_storyboard(..., curriculum_context=...)`): the `STORYBOARD_PROMPT` interpolates `{curriculum_context}` directly. Feed it `context_text`. Consider passing section titles/keywords so scenes can be anchored to real curriculum sections.
- **Contract stability.** Because `structure.json`'s on-disk format is unchanged (we only *clean* titles and *add* children/summaries), no migration is needed; the retriever change is the only consumer-side edit.
- **Caching.** Indexing is slow; ensure `structure.json` is reused (the CLI already supports `--resume`/cache). The retriever should index once per process (it already memoizes `DOC_ID`).

---

## 7. Practical Run Recommendations (try these next)

Prereqs:

```bash
ollama pull qwen2.5:3b
ollama pull qwen2.5-coder:7b   # only if you'll use --quality
curl http://127.0.0.1:11434/api/tags   # confirm Ollama is up
```

Fast smoke test (verifies hierarchy + non-empty summaries on a slice):

```bash
cd topic2manim/PageIndex
PYTHONPATH=. python run_pageindex.py \
  --pdf_path "examples/documents/SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf" \
  --demo \
  --max-pages 30 \
  --model qwen2.5:3b \
  --force-reindex
```

Tree-only (skip the slowest stage while iterating on structure):

```bash
PYTHONPATH=. python run_pageindex.py \
  --pdf_path "examples/documents/SCERT ... Part 1.pdf" \
  --max-pages 50 --model qwen2.5:3b --no-summaries --force-reindex
```

Full quality pass (when you can wait):

```bash
PYTHONPATH=. python run_pageindex.py \
  --pdf_path "examples/documents/SCERT ... Part 1.pdf" \
  --model qwen2.5-coder:7b
```

Always quote paths with spaces. Inspect `results/<pdf>.pdf/semantic_validation.json` and `pipeline_metrics.json` after each run — success looks like `passed: true` (or far fewer failures), `node_count >= 6`, and `0` budget-skips.

Config edits to make first (before any code): set the `stage_models` block from §3, and relax `cpu_mode` to `max_prompt_tokens: 3000` with **windowed** prompts (smaller prompts + shrink-on-overflow beats a single big budget).

---

## 8. Phased Implementation Roadmap

### Phase 1 — Quick wins (config + titles + no silent skips)
- Repoint all `stage_models` and `model_router.py` defaults from `gemma4:e4b` to `qwen2.5:3b`.
- Fix the leading-`". "` title bug in `deterministic_toc.py`; collapse double spaces; recover skipped chapters (don't stop at first parser).
- In `process_no_toc` and the summary path, replace `except (...): continue/skip` with **shrink-and-retry → extractive fallback** so summaries are never just the title.
- Verify on `--demo --max-pages 30`: expect `summaries_non_empty` to pass and `0` budget-skips in `pipeline_metrics.json`.

### Phase 2 — Structural quality (real hierarchy + early validation)
- Add a bounded per-chapter sub-section pass to populate children (fixes `has_hierarchy_depth`, `chapters_have_children`, `min_node_count`).
- Move validation earlier: gate on the TOC/outline before full build; run one `hierarchy_repair.py` pass when `validate_semantic_tree` fails.
- Add the extractive summary fallback via `extractive.py`.
- Verify: `semantic_validation.json` `passed: true` (or only minor failures) on the full SCERT PDF.

### Phase 3 — Integration & polish
- Rewrite `pageindex_retriever.py` to return the structured object in §5 (top-k, cleaned titles, summaries, capped content, breadcrumb).
- Wire `context_text` into `storyboard.py`; log matched sections in `api.py`.
- Optional `--quality` flag that routes `chapter_summary`/TOC-structuring to `qwen2.5-coder:7b`.
- Optional later: vision/OCR path for scanned TOC pages; parallelized summary batches.

---

## Limitations & honest expectations
- Local 3B–7B models will still occasionally mis-nest sections or write generic summaries on noisy OCR text. The plan optimizes for **usable and hierarchical**, with deterministic fallbacks so a run never ends with an empty/flat tree again.
- Indexing stays slow on a MacBook Air — design around "index once, reuse `structure.json`", not real-time indexing.
- `gemma4:e4b` and Gemini remain available as explicit, opt-in escalations; they are not part of the default local path.
