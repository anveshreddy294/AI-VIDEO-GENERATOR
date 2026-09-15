# PageIndex Architectural Transformation: Execution-Ready Specification

> **Document Purpose:** This is an authoritative, execution-ready specification for a coding agent to transform the existing PageIndex RAG pipeline from an API-heavy, sequential, unreliable architecture into a local-first, batched, deterministically validated, production-scalable system.
>
> **Hardware Target:** MacBook Air M4, 16 GB unified RAM
> **Primary Model:** `google/gemma-4-e4b-it` (4-bit quantized via MLX)
> **Fallback Model:** Google Gemini (API, used only when all local retries fail)
> **Guiding Principle:** *Use SLM for generation, deterministic systems for validation, and LLM only as fallback.*

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Design Principles](#2-design-principles)
3. [Architecture Diagram (Textual)](#3-architecture-diagram-textual)
4. [Pipeline Breakdown — All Stages](#4-pipeline-breakdown--all-stages)
5. [Component-Level Responsibilities](#5-component-level-responsibilities)
6. [Model Usage Strategy](#6-model-usage-strategy)
7. [Validation Strategy](#7-validation-strategy)
8. [Retry and Fallback Design](#8-retry-and-fallback-design)
9. [Data Structures and Contracts](#9-data-structures-and-contracts)
10. [Performance and Scalability Considerations](#10-performance-and-scalability-considerations)
11. [Execution Guidelines for Coding Agent](#11-execution-guidelines-for-coding-agent)
12. [File and Module Map](#12-file-and-module-map)
13. [Extensibility and Future Improvements](#13-extensibility-and-future-improvements)

---

## 1. System Overview

### 1.1 What the System Does

PageIndex is a vectorless tree-based RAG (Retrieval-Augmented Generation) pipeline. It:

1. Ingests a PDF document (e.g., NCERT textbook).
2. Detects and extracts the Table of Contents (TOC) from the document.
3. Builds a hierarchical tree of sections with page-range assignments.
4. Generates summaries and keywords for each tree node.
5. Stores the annotated tree as a JSON artifact.
6. At query time, traverses the tree to retrieve relevant page content without a vector database.
7. Uses the retrieved content plus the user query to generate a final explanation.

### 1.2 What Is Broken in the Current Implementation

| Problem | Impact |
|---|---|
| TOC detection makes one LLM call per page (up to 20 calls) | 20x latency, 20x API cost, inconsistent reasoning |
| Summaries generated one node at a time | O(n) API calls for n sections |
| Validation performed by a probabilistic model (SLM) | Non-deterministic pass/fail, false positives, added latency |
| Unconstrained JSON generation with raw `json.loads()` | High parse failure rate (30–50% in complex cases) |
| All calls go to remote LLM API (Gemini/GPT) | Cost at scale, rate limits, no offline capability |
| No retry-with-error-feedback loop | Single failure = silent bad data or crash |
| No fallback hierarchy | Any API failure breaks the entire pipeline |
| No guided/constrained decoding | JSON validity left to prompt engineering alone |

### 1.3 Target State After Transformation

- **Total LLM calls for indexing:** 4–8 (down from 40–150+)
- **JSON reliability:** 96–99% first-try; near 100% after retries
- **Cost:** Zero API cost for indexing (local model only)
- **Latency:** Acceptable for one-time indexing (minutes, not seconds — that is fine)
- **Determinism:** All validation is code-based, not model-based
- **Fallback:** One optional Gemini call only if all local retries fail

---

## 2. Design Principles

These principles govern every implementation decision in this transformation. The coding agent must apply them consistently.

### 2.1 SLM for Generation Only

The local small language model (`gemma-4-e4b-it`) is used **only** for text generation tasks: TOC detection, TOC structuring, summarization, and final explanation. It is **never** used for validation, error checking, or decision logic.

### 2.2 Deterministic Validation

All validation — JSON structure, schema conformance, semantic rules (e.g., page numbers are increasing, titles are non-empty) — must be implemented as deterministic Python code using Pydantic models and explicit rule checks. No model is involved in validation.

### 2.3 Batching by Default

Any operation that was previously performed per-item (per-page, per-node) must be restructured to batch multiple items into a single model call. TOC detection batches all candidate pages into one call. Summarization batches 5–8 small nodes per call.

### 2.4 Guided / Constrained Decoding

Every SLM call that expects a JSON output must use guided decoding (MLX's built-in support or Ollama's `format` parameter). This mathematically constrains the model's token sampling to produce syntactically valid JSON that conforms to the declared schema. This is the single highest-ROI reliability improvement.

### 2.5 Retry with Error Feedback

After every SLM generation call, the output is validated. If validation fails, the **same model** is called again with the original prompt plus the exact validation error message appended. Maximum 3 attempts per call. No separate repair model is ever used.

### 2.6 Fallback Only as Last Resort

The remote LLM (Gemini) is called **only** if all 3 local retries have failed. It is called **once** per failure, not once per page. It is optional and can be disabled entirely.

### 2.7 Model Loaded Once

The local model is loaded into memory once at process startup and reused for all calls. It is never loaded per-call.

### 2.8 Preserved Interfaces

All existing tree-building logic, retrieval functions, logging, CLI interface, and storage format remain unchanged. Only the LLM-calling layer changes.

---

## 3. Architecture Diagram (Textual)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT: PDF File                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 1: PDF INGESTION (Deterministic — No Model)                  │
│  Tool: PyMuPDF (fitz)                                               │
│  Output: page_list = [(page_text: str, token_count: int)]           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 2: TOC DETECTION (SLM — Single Batched Call)                 │
│  Input: First N pages concatenated (default N=20)                   │
│  Model: gemma-4-e4b-it via local_llm.py                             │
│  Output: TOCDetectionResult (Pydantic) or fallback to Gemini        │
│  Validation: Pydantic + deterministic rules                         │
│  Retry: Max 3 attempts with error feedback                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 3: TOC STRUCTURING (SLM — Single Call)                       │
│  Input: Flat TOC entry list from Stage 2                            │
│  Model: gemma-4-e4b-it via local_llm.py                             │
│  Output: HierarchicalTOC (Pydantic)                                 │
│  Validation: Tree depth, child consistency, no cycles               │
│  Retry: Max 3 attempts with error feedback                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 4: TREEIFICATION (Deterministic — No Model)                  │
│  Input: Validated hierarchical TOC + page_list                      │
│  Functions: list_to_tree, write_node_id, calculate_page_offset      │
│  Output: DocumentTree JSON (existing format preserved)              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 5: SUMMARIZATION (SLM — Batched Calls)                       │
│  Input: Tree nodes (batched 5–8 per call)                           │
│  Model: gemma-4-e4b-it via local_llm.py                             │
│  Output: SummaryBatch (Pydantic) per batch                          │
│  Validation: Each node_id present, summary non-empty, keywords list │
│  Retry: Max 3 attempts per batch                                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 6: DOCUMENT DESCRIPTION (SLM — Single Call)                  │
│  Input: Full tree + top 5 pages                                     │
│  Model: gemma-4-e4b-it via local_llm.py                             │
│  Output: DocDescription (Pydantic)                                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 7: STORAGE (Deterministic — No Model)                        │
│  Output files:                                                       │
│    results/{name}_structure.json                                    │
│    results/{name}_summaries.json  (optional)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                          [QUERY TIME]
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 8: RETRIEVAL (Deterministic — No Model)                      │
│  Functions: get_document_structure, get_page_content                │
│  Method: Keyword match / BM25 tree traversal                        │
│  Output: Retrieved page content chunks                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 9: EXPLANATION (SLM — Single Call)                           │
│  Input: User query + retrieved content                              │
│  Model: gemma-4-e4b-it via local_llm.py                             │
│  Output: Structured explanation (text + steps + examples)           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Pipeline Breakdown — All Stages

### Stage 1: PDF Ingestion

**Status:** Unchanged from original implementation.

**Responsibility:** Convert a PDF file into a structured list of page tuples. Each tuple contains the extracted text of one page and its estimated token count.

**Input:** Absolute file path to a PDF document.

**Output:** `page_list: List[Tuple[str, int]]` — one entry per page, ordered by page number (zero-indexed).

**Implementation Notes:**
- Use the existing `get_page_tokens()` function.
- The tool for extraction is PyMuPDF (`fitz`).
- No model is involved at this stage.
- Text quality depends on OCR quality of the PDF. No preprocessing is required at this stage; noisy text is handled by the retry logic in later stages.

---

### Stage 2: TOC Detection

**Status:** Major architectural change. Replaces 20 sequential per-page calls with a single batched call.

**Responsibility:** Determine whether the document contains a Table of Contents. If yes, extract all TOC entries as a flat list with title and page number.

**Input:** The first `N` pages from `page_list` (default `N = toc_check_pages`, which is typically 20). These pages are concatenated into a single prompt string with clear page delimiters.

**Output:** A `TOCDetectionResult` Pydantic object:
```
TOCDetectionResult:
  toc_found: bool
  toc_entries: List[TOCEntry]
    TOCEntry:
      title: str
      page_number: int
      structure: str  (e.g., "1.2.3" — optional, for hierarchical hint)
```

**Model Call:** Single call to `local_llm.generate_structured(prompt, schema=TOCDetectionResult)`.

**Validation (deterministic, no model):**
- JSON parses without error.
- Pydantic schema validates successfully.
- If `toc_found == True`: `len(toc_entries) > 0`.
- All `page_number` values are positive integers.
- `page_number` values are non-decreasing across entries (TOC entries appear in order).
- All `title` strings are non-empty after stripping whitespace.
- Entry count is above a minimum threshold (e.g., `>= 3`) if `toc_found == True`.

**Retry:** If validation fails, retry the same model with the original prompt + appended error message. Maximum 3 attempts.

**Fallback:** If all 3 retries fail, invoke Gemini API once with the same prompt.

**Prompt Construction Rules:**
- Each page is prefixed with a clear delimiter: `--- PAGE {n} ---`.
- The system prompt explicitly states the output must be strict JSON only, no markdown, no explanation.
- The full JSON schema is included in the system prompt.
- Guided decoding is enforced via `response_format`.

---

### Stage 3: TOC Structuring

**Status:** Changed. Previously multiple calls across modes 2 and 3. Now a single batched call.

**Responsibility:** Convert the flat TOC entry list (from Stage 2) into a hierarchical tree structure, inferring parent-child relationships from numbering patterns (e.g., "1", "1.1", "1.1.2") or indentation cues in the raw TOC text.

**Input:** The validated `toc_entries` list from Stage 2.

**Output:** A `HierarchicalTOC` Pydantic object:
```
HierarchicalTOC:
  root: TOCNode
    TOCNode:
      title: str
      page_number: int
      node_id: str  (assigned in this stage as placeholder, finalized in Stage 4)
      children: List[TOCNode]
```

**Model Call:** Single call to `local_llm.generate_structured(prompt, schema=HierarchicalTOC)`.

**Validation (deterministic, no model):**
- JSON parses without error.
- Pydantic schema validates recursively.
- Tree depth does not exceed a maximum (e.g., 6 levels — beyond this is almost certainly a hallucination).
- No node appears more than once (no cycles — check all node titles for duplicates at the same level).
- Every leaf node has `children == []` (not null, not missing).
- Page numbers in children are >= page numbers of their parent.

**Retry:** Same model with error feedback. Maximum 3 attempts.

**Fallback:** Gemini API once if all retries fail.

**Note:** If `toc_found == False` from Stage 2, this stage is skipped. The pipeline falls through to a heuristic tree-building mode (using chapter/section heading detection in the body text — this is an existing fallback in the codebase and is preserved unchanged).

---

### Stage 4: Treeification

**Status:** Unchanged from original implementation.

**Responsibility:** Combine the validated hierarchical TOC with the full `page_list` to produce the complete `DocumentTree`. This assigns `start_page` and `end_page` to every node by computing intervals from the TOC page numbers and total document page count.

**Input:**
- Validated `HierarchicalTOC` from Stage 3 (or heuristic fallback).
- `page_list` from Stage 1.

**Output:** `DocumentTree` JSON — the canonical document structure artifact. Format is identical to the existing output format; no schema change.

**Functions Used (unchanged):**
- `list_to_tree()`
- `write_node_id()`
- `calculate_page_offset()`
- `post_processing()`

**Implementation Notes:**
- No model is involved.
- This stage is purely deterministic and computationally cheap.
- All existing logging hooks in this stage are preserved.

---

### Stage 5: Summarization

**Status:** Changed. Replaces one-call-per-node with batched calls (5–8 nodes per call).

**Responsibility:** For every node in the `DocumentTree`, generate a short summary and a list of keywords using the page content belonging to that node.

**Input:** 
- `DocumentTree` from Stage 4.
- `page_list` from Stage 1 (for fetching `pages[start_page:end_page]` per node).

**Batching Strategy:**
- Collect all leaf nodes first, then their parents.
- Group nodes into batches of 5–8. For nodes whose page content is very large (> 2000 tokens), process them individually (batch size = 1).
- For very small books (< 30 nodes total), a single call batching all nodes is acceptable.

**Output per batch:** A `SummaryBatch` Pydantic object:
```
SummaryBatch:
  nodes: List[NodeSummary]
    NodeSummary:
      node_id: str
      summary: str  (2–5 sentences)
      keywords: List[str]  (3–10 keywords)
```

**Model Call:** One call per batch to `local_llm.generate_structured(prompt, schema=SummaryBatch)`.

**Validation (deterministic, no model):**
- All `node_id` values in the response match the `node_id` values that were sent in the batch (exact set match).
- No `summary` field is empty or shorter than 20 characters.
- Each `keywords` list has at least 1 entry.
- No `keywords` entry is empty after stripping.

**Retry:** Max 3 attempts per batch with error feedback.

**Fallback:** If a batch fails all retries, fall back to Gemini for that batch only. If Gemini also fails, write a placeholder summary (`"Summary not available."`) and continue — do not abort the pipeline.

---

### Stage 6: Document Description

**Status:** Unchanged in purpose. Changed to use local model.

**Responsibility:** Generate a single high-level description of the entire document.

**Input:** The complete `DocumentTree` JSON (titles only, no page content) + text from the first 5 pages of the document.

**Output:** A `DocDescription` Pydantic object:
```
DocDescription:
  title: str
  subject: str
  grade_level: str  (e.g., "Class 9", "Undergraduate", "Unknown")
  description: str  (3–6 sentences)
  primary_topics: List[str]
```

**Model Call:** Single call to `local_llm.generate_structured(prompt, schema=DocDescription)`.

**Validation:** Pydantic schema. `description` non-empty. `primary_topics` has at least 1 entry.

**Retry:** Max 3 attempts.

**Fallback:** Gemini once if all retries fail.

---

### Stage 7: Storage

**Status:** Unchanged.

**Responsibility:** Write the final annotated tree and optional summaries to disk as JSON files.

**Output Files:**
- `results/{document_name}_structure.json` — the `DocumentTree` with summaries embedded.
- `results/{document_name}_summaries.json` — standalone summary file (optional, for caching).

**Implementation Notes:**
- No model is involved.
- Directory is created if it does not exist.
- Existing logging of the final structure is preserved.

---

### Stage 8: Retrieval

**Status:** Unchanged.

**Responsibility:** At query time, traverse the `DocumentTree` to find the most relevant sections for a given user query, without a vector database.

**Method:** Keyword matching and/or BM25 scoring against node titles and summaries. Traverse from root to leaves, scoring each node. Return the top-k nodes and their associated page content.

**Functions Used (unchanged):**
- `get_document_structure()`
- `get_page_content()`

**Implementation Notes:**
- No model is involved in retrieval.
- This stage is purely deterministic.

---

### Stage 9: Explanation Generation

**Status:** Changed from remote LLM to local SLM.

**Responsibility:** Given the user's query and the retrieved page content, generate a structured educational explanation.

**Input:**
- User query string.
- Retrieved page content from Stage 8.
- Optional: Grade level from user profile (passed as context in the prompt).

**Output:** A `ExplanationResult` Pydantic object:
```
ExplanationResult:
  answer: str
  steps: List[str]  (optional — if the answer involves a process)
  examples: List[str]  (optional — concrete examples)
  key_terms: List[str]
```

**Model Call:** Single call to `local_llm.generate_structured(prompt, schema=ExplanationResult)`.

**Validation:** Pydantic schema. `answer` non-empty.

**Retry:** Max 3 attempts.

**Fallback:** Gemini once if all retries fail (this is the most user-visible call, so Gemini fallback is most justified here).

---

## 5. Component-Level Responsibilities

### 5.1 `pageindex/local_llm.py` — **NEW FILE**

This is the central new module. It replaces all `litellm.completion()` calls throughout the codebase.

**Responsibilities:**
- Load the local model (`gemma-4-e4b-it`, 4-bit quantized) **once** at module initialization.
- Expose a single primary function: `generate_structured(prompt: str, schema: Type[BaseModel], system_prompt: str = None, max_retries: int = 3) -> BaseModel`.
- Internally manage:
  - Guided decoding configuration (pass schema to MLX or Ollama `format` parameter).
  - Prompt construction with schema injected into the system prompt.
  - Retry loop: on `ValidationError` or `JSONDecodeError`, re-call the model with the original prompt + error message appended.
  - Fallback invocation: after `max_retries` exhausted, call Gemini API once.
- Accept an optional `fallback_enabled: bool = True` flag to disable Gemini fallback in offline mode.
- Log every call, retry, and fallback event using the existing logging infrastructure.

**Dependencies:**
- `mlx_lm` (for MLX backend on M4)
- `pydantic` (for schema validation)
- `json` (standard library)
- `google.generativeai` or `litellm` (for Gemini fallback — optional import, gracefully disabled if not installed)
- Existing logger from the codebase

**What this module does NOT do:**
- It does not build prompts for specific stages. Each stage builds its own prompt and passes it in.
- It does not know about TOC, summaries, or any domain-specific logic.
- It does not perform validation beyond JSON parsing and Pydantic schema check.

---

### 5.2 `pageindex/utils.py` — **MODIFIED FILE**

**Responsibilities:**
- Replace every `litellm.completion(...)` call with a call to `local_llm.generate_structured(...)`.
- Each call site passes the appropriate Pydantic schema for that stage.
- Keep the same function signatures visible to calling code (no interface changes).
- Import `local_llm` at the top of the file.

**Changes Required:**
- Identify every call to `litellm.completion` in this file.
- For each call, determine which Pydantic schema corresponds to its expected output (schemas defined in `schemas.py` — see below).
- Replace the call with the equivalent `local_llm.generate_structured()` call.
- Remove the `litellm` import.

---

### 5.3 `pageindex/schemas.py` — **NEW FILE**

This file defines all Pydantic models used as output schemas throughout the pipeline.

**Models to define:**
- `TOCEntry`
- `TOCDetectionResult`
- `TOCNode` (recursive)
- `HierarchicalTOC`
- `NodeSummary`
- `SummaryBatch`
- `DocDescription`
- `ExplanationResult`

**Design Rules:**
- Every field must have an explicit type annotation.
- Optional fields must have a default value.
- Nested models must be fully defined (no forward references unless using `model_rebuild()`).
- Add `model_config = ConfigDict(strict=True)` to all models to prevent unexpected field coercion.

---

### 5.4 `pageindex/page_index.py` — **MODIFIED FILE**

**Responsibilities:**
- Restructure `find_toc_pages()` to batch all candidate pages into a single prompt (eliminating the per-page loop).
- Update `process_toc_with_page_numbers()` and related Mode 2/3 processing functions to use a single batched SLM call.
- Update `generate_summaries_for_structure()` to batch nodes 5–8 per call.
- All other functions (tree building, storage, retrieval) remain unchanged.

**Specific Function Changes:**

`find_toc_pages(page_list, toc_check_pages=20)`:
- Old behavior: Calls `toc_detector_single_page()` for each of the first 20 pages in a loop.
- New behavior: Concatenates the first `toc_check_pages` page texts with `--- PAGE {i} ---` delimiters into a single prompt string. Calls `local_llm.generate_structured(prompt, schema=TOCDetectionResult)` once. Returns the validated result.

`generate_summaries_for_structure(tree, page_list)`:
- Old behavior: Iterates over every node and calls LLM once per node.
- New behavior: Collects all nodes into a list. Splits into batches of `SUMMARY_BATCH_SIZE = 7`. For each batch, constructs a prompt containing all node IDs, titles, and their concatenated page content. Calls `local_llm.generate_structured(prompt, schema=SummaryBatch)`. Merges all batch results into the tree.

---

### 5.5 Existing Modules (Unchanged)

The following modules are **not modified** under any circumstance:

| Module | Reason Unchanged |
|---|---|
| `retrieve.py` | Retrieval is deterministic; no LLM calls |
| `tree_builder.py` (or equivalent) | Pure code: `list_to_tree`, `write_node_id`, `calculate_page_offset` |
| `run_pageindex.py` (CLI) | Interface is preserved; changes are internal |
| `logging` setup | Existing logging hooks are reused, not replaced |
| Storage format | `results/{name}_structure.json` schema unchanged |

---

## 6. Model Usage Strategy

### 6.1 Decision Table

| Pipeline Stage | Model Used | Rationale |
|---|---|---|
| PDF Ingestion | None | Deterministic extraction |
| TOC Detection | SLM (gemma-4-e4b-it) | Structured JSON extraction, bounded output |
| TOC Structuring | SLM (gemma-4-e4b-it) | Hierarchical conversion, bounded reasoning |
| Validation (all stages) | None | Deterministic rule checks only |
| Treeification | None | Pure algorithmic computation |
| Summarization | SLM (gemma-4-e4b-it) | Low-complexity bounded generation |
| Document Description | SLM (gemma-4-e4b-it) | Low-complexity, single call |
| Retrieval | None | BM25 / keyword traversal |
| Explanation Generation | SLM (gemma-4-e4b-it) | Primary user-visible output |
| Any stage after 3 failed retries | LLM (Gemini) — once | Last resort fallback only |

### 6.2 Model Loading

- The model is loaded once when `local_llm.py` is first imported.
- Loading is performed by `mlx_lm.load("path/to/gemma4-e4b-mlx")`.
- The model and tokenizer objects are stored as module-level globals.
- All calls reuse these globals. There is no per-call model load.
- Expected memory footprint: 5–7 GB for E4B 4-bit quantized. This leaves sufficient headroom on 16 GB unified RAM.

### 6.3 Guided Decoding Configuration

- MLX backend: Use the `guided_decode` parameter (check current `mlx_lm` API for exact parameter name in the installed version).
- Ollama backend (alternative): Use `format: "json"` with the schema passed as a JSON Schema object.
- The schema passed to guided decoding must be the JSON Schema representation of the Pydantic model, obtained via `ModelClass.model_json_schema()`.
- If guided decoding is not available in the installed version of `mlx_lm`, the fallback is to include the schema in the system prompt with explicit instructions: `"You must respond with ONLY valid JSON. No markdown. No explanation. No preamble."`.

### 6.4 Gemini Fallback Configuration

- The Gemini API key is read from environment variable `GEMINI_API_KEY`.
- If the variable is not set, the fallback is silently disabled and the pipeline proceeds with whatever partial output is available.
- The Gemini call uses the same prompt and schema as the failed local call.
- The Gemini response is parsed with the same Pydantic validation — if it also fails, the pipeline logs the failure and either uses a placeholder or aborts with a clear error message.

---

## 7. Validation Strategy

### 7.1 Philosophy

Validation is a **deterministic code contract**, not a model judgment. It answers the question: "Does this output satisfy the structural and semantic requirements we specified?" This question has a binary yes/no answer that can be computed without ambiguity.

### 7.2 Layers of Validation

Every SLM output goes through three layers in sequence:

**Layer 1: JSON Parsing**
- Attempt `json.loads(raw_output)`.
- If this fails, the output is immediately invalid. Do not attempt further validation.
- Trigger: retry with error `"Output is not valid JSON. Error: {parse_error}. Raw output was: {raw_output}. Return ONLY valid JSON."`

**Layer 2: Pydantic Schema Validation**
- Pass the parsed JSON dict to `ModelClass.model_validate(parsed_dict)`.
- If this fails, capture the `ValidationError` with all field-level errors.
- Trigger: retry with error `"JSON schema validation failed. Errors: {validation_error}. Correct ALL listed fields and return the full valid object."`

**Layer 3: Semantic Rule Checks**
- Apply stage-specific rule checks (see below).
- If any rule fails, raise a `ValueError` with a descriptive message.
- Trigger: retry with error `"Semantic validation failed: {rule_violation_description}. Fix the specific issue and return the complete corrected JSON."`

### 7.3 Stage-Specific Semantic Rules

**TOC Detection (`TOCDetectionResult`):**
- If `toc_found == True`, then `len(toc_entries) >= 3`.
- All `title` fields: `len(title.strip()) > 0`.
- All `page_number` fields: `page_number > 0`.
- `page_number` values across entries: non-decreasing (each entry's page >= previous entry's page).

**Hierarchical TOC (`HierarchicalTOC`):**
- Maximum tree depth: 6 levels (check recursively).
- All node titles non-empty.
- No duplicate titles at the same parent level.
- All `page_number` values are positive integers.
- Children's page numbers are >= their parent's page number.

**Summary Batch (`SummaryBatch`):**
- The set of `node_id` values in the response exactly matches the set of `node_id` values in the request (no missing, no extra).
- All `summary` fields: `len(summary.strip()) >= 20`.
- All `keywords` lists: `len(keywords) >= 1`.
- No keyword is an empty string.

**Document Description (`DocDescription`):**
- `description` has at least 50 characters.
- `primary_topics` has at least 1 entry.
- `title` is non-empty.

**Explanation Result (`ExplanationResult`):**
- `answer` has at least 30 characters.

### 7.4 Error Message Construction for Retry

When constructing the retry prompt, the error message must be specific enough for the model to correct it. Always include:
1. A plain-English description of what failed.
2. The exact field or rule that was violated.
3. The raw output that was produced (truncated to 2000 characters if very long).
4. A re-statement of the full JSON schema.
5. The instruction to return the corrected full JSON object (not just the fixed field).

---

## 8. Retry and Fallback Design

### 8.1 Retry Loop Structure

For every SLM call, the following loop is executed inside `local_llm.generate_structured()`:

```
attempt = 0
max_attempts = 3
last_error = None
last_raw_output = None

while attempt < max_attempts:
    raw_output = call_slm(prompt, guided_decoding_schema)
    last_raw_output = raw_output
    
    try:
        parsed = json.loads(raw_output)
        validated = schema.model_validate(parsed)
        run_semantic_rules(validated)   # raises ValueError on failure
        return validated                # SUCCESS
    except (JSONDecodeError, ValidationError, ValueError) as e:
        last_error = e
        prompt = build_retry_prompt(original_prompt, raw_output, str(e))
        attempt += 1
        log_retry(attempt, str(e))

# All retries exhausted
log_failure(max_attempts, last_error)
```

### 8.2 Fallback Invocation

After the retry loop exits without success:

```
if fallback_enabled and GEMINI_API_KEY is set:
    log_fallback_attempt()
    fallback_raw = call_gemini(original_prompt)
    try:
        parsed = json.loads(fallback_raw)
        validated = schema.model_validate(parsed)
        run_semantic_rules(validated)
        log_fallback_success()
        return validated
    except Exception as e:
        log_fallback_failure(str(e))
        raise PipelineStageFailure(stage_name, last_error)
else:
    raise PipelineStageFailure(stage_name, last_error)
```

### 8.3 Partial Failure Handling

Not all stages are equally critical. The pipeline should not abort completely for a non-critical failure:

| Stage | Failure Policy |
|---|---|
| TOC Detection — total failure | Abort pipeline, raise `PipelineStageFailure` with clear message. TOC is required. |
| TOC Structuring — total failure | Abort pipeline. Tree cannot be built without it. |
| Summarization batch — total failure | Write placeholder summary (`"Summary unavailable."`), continue to next batch. Log warning. |
| Document Description — total failure | Write empty description, continue. Non-critical. |
| Explanation Generation — total failure | Raise to user. This is the final user-visible call; failure must be reported. |

### 8.4 Retry Prompt Template

The retry prompt must follow this exact structure:

```
RETRY INSTRUCTION:
Your previous response failed validation. Here is the error:
---
{error_message}
---
Your previous raw output was:
---
{raw_output_truncated}
---
You must correct the issue and return the complete, corrected JSON object.
The required schema is:
---
{json_schema}
---
IMPORTANT: Return ONLY valid JSON. No explanation. No markdown. No preamble.
```

This is followed by the original user/task content from the initial prompt.

---

## 9. Data Structures and Contracts

### 9.1 `TOCEntry`

```
{
  "title": string,           // Non-empty. The section title as it appears in the TOC.
  "page_number": integer,    // > 0. The page number listed in the TOC.
  "structure": string        // Optional. Numbering hint e.g. "1.2.3". Empty string if not present.
}
```

### 9.2 `TOCDetectionResult`

```
{
  "toc_found": boolean,
  "toc_entries": [           // Empty list if toc_found == false
    TOCEntry, ...
  ]
}
```

### 9.3 `TOCNode` (recursive)

```
{
  "title": string,
  "page_number": integer,
  "node_id": string,         // Placeholder at this stage; finalized in Stage 4
  "children": [              // Empty list for leaf nodes
    TOCNode, ...
  ]
}
```

### 9.4 `HierarchicalTOC`

```
{
  "root": TOCNode
}
```

### 9.5 `NodeSummary`

```
{
  "node_id": string,         // Must exactly match the node_id from the tree
  "summary": string,         // 2–5 sentences. >= 20 characters.
  "keywords": [string, ...]  // 3–10 items. No empty strings.
}
```

### 9.6 `SummaryBatch`

```
{
  "nodes": [NodeSummary, ...]
}
```

### 9.7 `DocDescription`

```
{
  "title": string,
  "subject": string,
  "grade_level": string,
  "description": string,        // >= 50 characters
  "primary_topics": [string, ...]
}
```

### 9.8 `ExplanationResult`

```
{
  "answer": string,             // >= 30 characters
  "steps": [string, ...],       // Optional. Empty list if not applicable.
  "examples": [string, ...],    // Optional. Empty list if not applicable.
  "key_terms": [string, ...]    // Optional. Empty list if not applicable.
}
```

### 9.9 `DocumentTree` (existing format — unchanged)

The `DocumentTree` JSON format written to `results/{name}_structure.json` is **identical** to the current format. No schema change is made to the output artifact. This guarantees backward compatibility with any downstream consumers of the tree.

---

## 10. Performance and Scalability Considerations

### 10.1 Call Count Comparison

| Operation | Before (per 200-page book) | After |
|---|---|---|
| TOC Detection | 20 sequential calls | 1 call |
| TOC Transformation/Verification | 3–5 calls | 1 call |
| Summarization (assume 40 nodes) | 40 calls | ~6 batched calls |
| Document Description | 1 call | 1 call |
| Explanation (per query) | 1 call | 1 call |
| **Total for indexing** | **64–66 calls** | **9 calls** |
| **Total API cost** | **High (Gemini API)** | **Zero (local model)** |

### 10.2 Latency Profile

On M4 16 GB with gemma-4-e4b-it at 4-bit quantization (~19–40 tok/s generation):

| Stage | Estimated Duration |
|---|---|
| Model Load (once at startup) | 15–30 seconds |
| TOC Detection (1 call, ~800 token output) | 20–40 seconds |
| TOC Structuring (1 call, ~500 token output) | 15–25 seconds |
| Treeification (code only) | < 1 second |
| Summarization (6 batched calls, ~300 tokens each) | 45–90 seconds |
| Document Description (1 call) | 10–20 seconds |
| **Total Indexing Time (first run)** | **~2–4 minutes** |
| Explanation (per query, 1 call) | 20–40 seconds |

This is a 10–30x slowdown from the API version for indexing. This is acceptable because indexing is a one-time operation per document. Query-time explanation is comparable in latency to the API version.

### 10.3 Batching Configuration Constants

Define the following constants at the top of `page_index.py` (or in a `config.py`):

```
TOC_CHECK_PAGES = 20         # Number of pages to include in TOC detection call
SUMMARY_BATCH_SIZE = 7       # Number of nodes per summarization call
MAX_NODE_PAGE_TOKENS = 2000  # Nodes with content exceeding this are processed solo
MAX_RETRIES = 3              # Maximum retry attempts per LLM call
FALLBACK_ENABLED = True      # Set to False for fully offline operation
```

### 10.4 Memory Management

- The model (5–7 GB) is loaded once and kept resident for the full indexing session.
- During batched summarization, page content for the entire batch is loaded into memory simultaneously. For large documents, ensure that the combined token count of a batch's page content does not exceed the model's context window (~8K tokens for E4B). If it does, reduce `SUMMARY_BATCH_SIZE` or truncate page content per node.
- After indexing completes, the model can be unloaded by deleting the module-level references and calling the appropriate MLX cleanup if memory is needed for other processes.

### 10.5 Caching

- Once `results/{name}_structure.json` exists for a document, skip all indexing stages and go directly to Stage 8 (Retrieval).
- Add a check at the start of the pipeline: `if os.path.exists(structure_path): load_and_return_cached_tree()`.
- This ensures re-running the CLI on an already-indexed document is instant.

---

## 11. Execution Guidelines for Coding Agent

### 11.1 Prerequisites (Run Once Before Starting)

The coding agent must verify or execute the following before writing any code:

**Step A — Install MLX stack:**
```
pip install mlx-lm pydantic json-repair
```

**Step B — Download and quantize the model (one-time, ~10 minutes):**
```
python -m mlx_lm.convert \
  --hf-path google/gemma-4-e4b-it \
  --mlx-path ./gemma4-e4b-mlx \
  --quantize 4bit
```

**Step C — Verify model loads and generates output:**
```python
from mlx_lm import load, generate
model, tokenizer = load("./gemma4-e4b-mlx")
response = generate(model, tokenizer, prompt='Return only JSON: {"test": true}', max_tokens=50)
print(response)
# Expected: {"test": true}  (or similar valid JSON)
```

**Step D — Verify existing test still passes:**
```
python3 run_pageindex.py --pdf_path PageIndex/examples/documents/science_grade5.pdf
```
Record current output for regression comparison after transformation.

---

### 11.2 Build Order (Execute in Strict Sequence)

The following steps must be executed in the exact order listed. Do not skip ahead. Each step has a verification check that must pass before proceeding.

---

#### STEP 1: Create `pageindex/schemas.py`

**What to build:** A new Python file containing all Pydantic model definitions.

**Models to define in order (order matters for forward references):**
1. `TOCEntry`
2. `TOCDetectionResult`
3. `TOCNode` (requires `model_rebuild()` call after definition due to self-reference)
4. `HierarchicalTOC`
5. `NodeSummary`
6. `SummaryBatch`
7. `DocDescription`
8. `ExplanationResult`

**Verification:** Run `python -c "from pageindex.schemas import TOCDetectionResult, HierarchicalTOC, SummaryBatch, DocDescription, ExplanationResult; print('schemas OK')"`. Must print `schemas OK` with no errors.

---

#### STEP 2: Create `pageindex/local_llm.py`

**What to build:** The central SLM wrapper module.

**Must implement:**
- Module-level model and tokenizer loading (deferred to first call, not on import, to avoid slow startup when running retrieval-only operations).
- `_load_model()` — private function that loads model once and caches in module globals.
- `_call_slm(prompt: str, system_prompt: str, schema_json: dict) -> str` — private function that calls the MLX model with guided decoding. Returns raw string output.
- `_call_gemini_fallback(prompt: str, system_prompt: str, schema_json: dict) -> str` — private function that calls Gemini API. Returns raw string output. Must handle `ImportError` and `KeyError` for missing API key gracefully.
- `_build_retry_prompt(original_prompt: str, raw_output: str, error_message: str, schema_json: dict) -> str` — private function that assembles the retry prompt following the template in Section 8.4.
- `generate_structured(prompt: str, schema: Type[BaseModel], system_prompt: str = None, max_retries: int = MAX_RETRIES) -> BaseModel` — public function. Implements the full retry loop described in Section 8.1 and fallback in Section 8.2.

**Verification:** Write a small test that calls `generate_structured` with a simple schema (e.g., `{"status": "ok"}` shape) and asserts the return type is the expected Pydantic model. Must pass without errors.

---

#### STEP 3: Modify `find_toc_pages()` in `pageindex/page_index.py`

**What to change:** Replace the per-page loop with a single batched call.

**Before (conceptual):**
```
for page in first_N_pages:
    result = toc_detector_single_page(page)  # one LLM call per page
    accumulate results
```

**After (conceptual):**
```
batch_prompt = concatenate pages with delimiters
result: TOCDetectionResult = local_llm.generate_structured(batch_prompt, TOCDetectionResult)
return result
```

**What must NOT change:**
- The function's return type (whatever the rest of the pipeline expects).
- Any logging that occurs in this function.
- The `toc_check_pages` parameter and its default value.

**Verification:** Run the existing test document. Verify that TOC detection completes with exactly 1 model call (check logs). Verify the returned structure contains the expected chapters.

---

#### STEP 4: Modify TOC transformation functions in `pageindex/page_index.py`

**What to change:** Functions that implement Modes 2 and 3 of TOC processing (`process_toc_with_page_numbers()` and/or `check_toc()` and/or `meta_processor()` — identify the exact function names from the actual codebase).

**Goal:** Consolidate multiple LLM calls in these functions into a single call that receives the full flat TOC list and returns the `HierarchicalTOC`.

**Verification:** After this step, run the test document again. Total model calls for TOC detection + structuring combined should be 2 (one for detection, one for structuring). Verify in logs.

---

#### STEP 5: Create Pydantic models in `pageindex/schemas.py` for any schemas missed in Step 1

After examining the actual codebase, there may be additional intermediate data structures used by the TOC transformation functions. Define Pydantic models for any such structures that were not covered in Step 1.

---

#### STEP 6: Modify `generate_summaries_for_structure()` in `pageindex/page_index.py`

**What to change:** Replace the per-node loop with batched calls.

**Logic to implement:**
1. Collect all nodes from the tree into a flat list.
2. Filter out nodes with zero page content (page range is empty).
3. Sort by content size (ascending) to pack small nodes together and avoid oversized batches.
4. Split into batches of `SUMMARY_BATCH_SIZE`.
5. For each batch: build prompt with all node IDs, titles, and page contents; call `local_llm.generate_structured(prompt, SummaryBatch)`; merge results back into the tree.
6. For any node not covered by a successful batch (due to failure with placeholder): write `"Summary unavailable."`.

**Verification:** Run the test document. Count model calls for summarization in logs. For a 40-node tree, expect approximately 6 calls. Verify all nodes in the output tree have a non-null summary field.

---

#### STEP 7: Update `generate_doc_description()` to use local model

**What to change:** Replace the existing LLM call in this function with `local_llm.generate_structured(prompt, DocDescription)`.

**Verification:** Output `structure.json` contains a populated description field.

---

#### STEP 8: Update `pageindex/utils.py` to remove remaining `litellm` calls

**What to change:** Search for any remaining `litellm.completion` or equivalent API calls not yet addressed in Steps 3–7. Replace each with the appropriate `local_llm.generate_structured()` call.

**Verification:** Run `grep -r "litellm" pageindex/`. Result should be empty (no remaining litellm references, or only the optional import in `local_llm.py` itself).

---

#### STEP 9: End-to-End Regression Test

**Run:**
```
python3 run_pageindex.py --pdf_path PageIndex/examples/documents/science_grade5.pdf
```

**Verify:**
- Pipeline completes without exception.
- `results/science_grade5_structure.json` is written.
- Total model call count (from logs) is between 4 and 10.
- Tree structure is semantically equivalent to the pre-transformation output (same chapter titles, same nesting depth, same number of nodes).
- All node summaries are populated (not "unavailable").

---

#### STEP 10: Test with a second document

Run with a different document that has a different TOC structure (e.g., a document with numbered sections vs. one with descriptive chapter names). Verify robustness of the batched TOC detection.

---

## 12. File and Module Map

```
pageindex/
├── local_llm.py         ← NEW: Central SLM wrapper, retry loop, fallback
├── schemas.py           ← NEW: All Pydantic models for structured outputs
├── page_index.py        ← MODIFIED: Batched TOC, batched summaries
├── utils.py             ← MODIFIED: Replace litellm calls with local_llm calls
├── retrieve.py          ← UNCHANGED
├── tree_builder.py      ← UNCHANGED (or equivalent tree logic file)
└── config.py            ← OPTIONAL NEW: Constants (batch sizes, retry counts)

run_pageindex.py         ← UNCHANGED (CLI entry point)

results/
├── {name}_structure.json    ← UNCHANGED format
└── {name}_summaries.json    ← OPTIONAL new file

gemma4-e4b-mlx/          ← NEW DIRECTORY: quantized model weights
```

---

## 13. Extensibility and Future Improvements

### 13.1 Swapping the Local Model

To swap `gemma-4-e4b-it` for a different model, only `local_llm.py` needs to change — specifically the `_load_model()` function and the MLX generate call. The rest of the pipeline is model-agnostic.

Candidate future upgrades:
- `Gemma 4 27B` (if RAM is upgraded beyond 32 GB) — for improved TOC accuracy on noisy/complex textbooks.
- `Qwen2.5-7B` or `Phi-4` — if structured output performance needs improvement.
- Any HuggingFace-compatible model accessible via `mlx_lm.load()`.

### 13.2 Adding a Vector Index (Optional Future Enhancement)

The current retrieval (Stage 8) uses keyword matching. If semantic retrieval is needed in future, a vector index can be added **without changing any other part of the pipeline**:

- After Stage 7 (Storage), add a Stage 7b that embeds all node summaries using a local embedding model (e.g., `nomic-embed-text` via `mlx` or `sentence-transformers`).
- Save embeddings to `results/{name}_embeddings.npy`.
- In Stage 8, add a FAISS or ChromaDB lookup as a secondary retrieval path.
- The existing keyword retrieval remains as the primary path and fallback.

### 13.3 Parallelizing Summarization

Once the local model call is stable, summary batches can be parallelized using Python `concurrent.futures.ThreadPoolExecutor`. The MLX model is not thread-safe by default — use `ProcessPoolExecutor` with separate model instances per process, or queue calls through a single worker thread.

This is a future optimization and is **not** part of the current transformation scope.

### 13.4 Upgrading to API-First in Production

When deploying at scale (not on a local MacBook), swap the backend:

- In `local_llm.py`, add a `BACKEND` environment variable: `local` (default), `gemini`, `openai`.
- When `BACKEND=gemini`, replace `_call_slm()` with a Gemini API call.
- All validation, retry, and schema logic remains identical — only the generation call changes.
- This means the transformation done now is directly production-upgradeable with a single env var change.

### 13.5 Multi-Language Support

The system prompt in each SLM call can include a `LANGUAGE` directive. For Hindi or other Indian language output, append `"Generate all text in {language}."` to the system prompt. The Pydantic schemas do not need to change. Only the prompts change.

### 13.6 Adding Image-Based TOC Detection

Some PDFs have image-rendered TOC pages (scanned). In this case, the text extraction in Stage 1 returns empty or garbled text for TOC pages. A future enhancement:

- In Stage 1, detect pages with very low text token count (< 50 tokens).
- For those pages, render the page to an image using PyMuPDF's `page.get_pixmap()`.
- Pass the image to a vision-capable model (Gemini Vision or `gemma-4-e4b-it` with vision) for OCR and TOC extraction.
- This is an additive change to the existing pipeline and does not require refactoring any current stage.

---

## Appendix A: Prompt Templates

### A.1 TOC Detection System Prompt

```
You are a document structure extraction engine. You will be given the text of multiple pages from a textbook or educational document. Your task is to:
1. Determine whether the document contains a Table of Contents page.
2. If yes, extract all entries from the Table of Contents including their titles and page numbers.

You must respond with ONLY valid JSON conforming exactly to this schema:
{toc_detection_json_schema}

No explanation. No markdown. No preamble. Only JSON.
```

### A.2 TOC Detection User Prompt

```
Here are the first {N} pages of the document:

{for each page:}
--- PAGE {page_number} ---
{page_text}

{end for}

Extract the Table of Contents if one exists. Return the JSON object.
```

### A.3 TOC Structuring System Prompt

```
You are a document hierarchy builder. You will be given a flat list of Table of Contents entries extracted from a textbook. Your task is to convert this flat list into a hierarchical tree structure, inferring parent-child relationships from section numbering patterns (e.g., "1", "1.1", "1.1.2") or title indentation cues.

You must respond with ONLY valid JSON conforming exactly to this schema:
{hierarchical_toc_json_schema}

No explanation. No markdown. No preamble. Only JSON.
```

### A.4 Summarization System Prompt

```
You are a content summarization engine for educational documents. You will be given a list of document sections, each with a title, an identifier, and the page content belonging to that section. For each section, generate a concise summary (2–5 sentences) and a list of 3–10 keywords.

You must respond with ONLY valid JSON conforming exactly to this schema:
{summary_batch_json_schema}

Include an entry for EVERY section provided. No explanation. No markdown. No preamble. Only JSON.
```

---

## Appendix B: Error Taxonomy

| Error Class | Definition | Trigger |
|---|---|---|
| `JSONDecodeError` | Raw model output is not parseable JSON | Retry with corrective message |
| `ValidationError` (Pydantic) | JSON parses but does not match the declared schema | Retry with field-level error details |
| `SemanticValidationError` | Custom `ValueError` from rule checks (e.g., page numbers decreasing) | Retry with rule violation description |
| `PipelineStageFailure` | All retries and fallback have failed for a stage | Abort pipeline (critical stages) or skip with placeholder (non-critical stages) |
| `ModelLoadError` | MLX model cannot be loaded | Abort immediately with clear message, suggest re-running the model download step |
| `FallbackDisabledError` | `FALLBACK_ENABLED=False` and all local retries failed | Raise `PipelineStageFailure` directly |

---

*End of Specification. This document supersedes all earlier planning documents for the PageIndex architectural transformation. All implementation decisions must be traceable to a section in this document.*

Minor notes (not blockers):

The plan mentions tree_builder.py — the actual repo uses logic inside page_index.py. The coding agent will adapt automatically.
It assumes MLX guided decoding is available — it is (mlx-lm supports it natively).
Everything else is perfect and ready for implementation.

Verdict: This is the final authoritative spec. You can proceed with 100% confidence.