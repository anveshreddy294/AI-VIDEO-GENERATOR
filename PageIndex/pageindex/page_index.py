"""
page_index.py — PDF → hierarchical tree index.

Architecture (stabilised):
  1. find_toc_pages()   → one SLM call → TOCDetectionResult with toc_entries
  2. _toc_entries_to_flat_list() → deterministic flat list, NO reparsing
  3. process_toc_from_entries() → offset calc + deterministic_repair_missing_pages
  4. deterministic_appear_start() → NO LLM
  5. post_processing / list_to_tree → deterministic
  6. process_large_node_recursively() → depth-1 only, hard cap MAX_LARGE_NODE_SPLITS=4
  7. generate_summaries_for_structure() → batched SLM

Legacy functions are preserved as importable symbols but NOT called by the active pipeline.
"""

import asyncio
import os
import json
import copy
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .utils import (
    ConfigLoader,
    PipelineCheckpoints,
    convert_page_to_int,
    convert_physical_index_to_int,
    count_tokens,
    structure_to_list,
    validate_and_truncate_physical_indices,
    add_preface_if_needed,
    post_processing,
    add_node_text,
    remove_structure_text,
    write_node_id,
    assign_parent_ids,
    nodes_to_children_export,
    strip_page_list_banners,
    generate_summaries_for_structure,
    generate_doc_description,
    create_clean_structure_for_description,
    format_structure,
    get_page_tokens,
    get_pdf_name,
    JsonLogger,
    print_tree,
    ollama_text_completion,
    page_list_to_group_text,
    deterministic_appear_start,
    deterministic_repair_missing_pages,
    verify_page_anchors,
    semantic_dedupe,
    MAX_PROMPT_TOKENS_DEFAULT,
    PROMPT_OVERHEAD_TOKENS,
)
from .deterministic_toc import parse_toc as deterministic_parse_toc, find_toc_page_index
from .heading_hints import detect_textbook_content_start
from .model_router import is_max_quality
from .hierarchy_repair import (
    repair_hierarchy,
    semantic_boundary_refiner,
    map_toc_pages_to_physical,
    inject_subsections_into_tree,
    filter_junk_toc_entries,
    reset_junk_filter_stats,
    log_junk_filter_stats,
    polish_titles_llm,
)
from .quality_policy import (
    skip_deterministic_toc,
    junk_filter_strict,
    force_title_polish,
    log_quality_path_summary,
    record_path,
)
from .validators import validate_semantic_tree
from .telemetry import PipelineMetrics
from .local_llm import (
    TokenBudgetExceeded,
    generate_structured,
    PipelineStageFailure,
    print_runtime_summary,
    reset_runtime_summary,
    TOC_GENERATION_OPTIONS,
)
from .schemas import (
    TOCDetectionResult,
    TOCEntry,
    HierarchicalTOC,
    TOCNode,
    ThinkingCompleted,
    TocDetectorAnswer,
    PageIndexInTocAnswer,
    TOCPhysicalIndexList,
    AddPageNumberResult,
    TitleAppearanceAnswer,
    TitleStartAnswer,
    SectionPhysicalIndexAnswer,
)

# Hard cap: at most this many nodes may be recursively subdivided per document run.
MAX_LARGE_NODE_SPLITS = 4
_split_counter: list = []  # mutable global counter reset per page_index_main call


# ── Core helpers ──────────────────────────────────────────────────────────────

def _hierarchical_toc_to_flat_list(hier: HierarchicalTOC) -> list:
    def walk(node: TOCNode, parts: list[str]) -> list:
        rows = []
        struct = ".".join(parts) if parts else None
        rows.append({"structure": struct, "title": node.title, "page": node.page_number})
        for i, ch in enumerate(node.children, start=1):
            rows.extend(walk(ch, parts + [str(i)]))
        return rows
    return walk(hier.root, [])


def _hierarchical_toc_to_flat_physical(hier: HierarchicalTOC) -> list:
    def walk(node: TOCNode, parts: list[str]) -> list:
        rows = []
        struct = ".".join(parts) if parts else None
        rows.append({"structure": struct, "title": node.title, "physical_index": node.page_number})
        for i, ch in enumerate(node.children, start=1):
            rows.extend(walk(ch, parts + [str(i)]))
        return rows
    return walk(hier.root, [])


def _toc_entries_to_flat_list(detection: TOCDetectionResult) -> list:
    """
    Convert TOCDetectionResult.toc_entries into a flat list of
    {structure, title, page} dicts — NO inference, purely deterministic.
    """
    rows = []
    for entry in detection.toc_entries:
        rows.append({
            "structure": entry.structure if entry.structure else None,
            "title": entry.title,
            "page": entry.page_number,
        })
    return rows


def _entries_have_page_numbers(detection: TOCDetectionResult, min_ratio: float = 0.6) -> bool:
    """Return True if at least `min_ratio` of toc_entries carry a non-zero page_number."""
    if not detection.toc_entries:
        return False
    with_page = sum(1 for e in detection.toc_entries if e.page_number and e.page_number > 0)
    return (with_page / len(detection.toc_entries)) >= min_ratio


# ── Deterministic TOC-with-page-numbers path ──────────────────────────────────

def process_toc_from_entries(detection: TOCDetectionResult, toc_page_list: list,
                              page_list: list, opt=None, logger=None) -> list:
    """
    Build a flat list with physical_index from toc_entries — no toc_transformer, no
    toc_index_extractor, no detect_page_index inference.

    Steps:
      1. Convert entries → flat list with 'page' (logical page number from TOC text).
      2. Anchor the offset by scanning the first pages after TOC to find where chapter 1 starts.
      3. Apply offset to all entries.
      4. deterministic_repair_missing_pages for any entry that has page=0 or None.
    """
    flat = _toc_entries_to_flat_list(detection)
    flat = convert_page_to_int(flat)

    if logger:
        logger.info(f"process_toc_from_entries: {len(flat)} entries from toc_entries")

    start_page_index = toc_page_list[-1] + 1 if toc_page_list else 0
    toc_check_page_num = getattr(opt, "toc_check_page_num", 20)

    with_page = sum(1 for e in flat if e.get("page"))
    use_direct_pages = with_page >= max(3, int(0.8 * len(flat)))

    if use_direct_pages:
        result = []
        for item in flat:
            r = dict(item)
            if r.get("page"):
                r["physical_index"] = r.pop("page")
            result.append(r)
        if logger:
            logger.info("process_toc_from_entries: direct TOC page numbers (skipped toc_index_extractor)")
    else:
        main_content = ""
        scan_end = min(start_page_index + toc_check_page_num, len(page_list))
        for page_index in range(start_page_index, scan_end):
            main_content += (
                f"<physical_index_{page_index + 1}>\n"
                f"{page_list[page_index][0]}\n"
                f"<physical_index_{page_index + 1}>\n\n"
            )

        toc_no_page = remove_page_number(copy.deepcopy(flat))
        try:
            toc_with_physical = toc_index_extractor(
                toc_no_page, main_content,
                model=getattr(opt, "token_count_model", getattr(opt, "model", None)), opt=opt
            )
            toc_with_physical = convert_physical_index_to_int(toc_with_physical)
        except Exception as exc:
            if logger:
                logger.info(f"process_toc_from_entries: toc_index_extractor failed ({exc}); flat fallback")
            toc_with_physical = []

        matching_pairs = extract_matching_page_pairs(flat, toc_with_physical, start_page_index)
        offset = calculate_page_offset(matching_pairs)

        if logger:
            logger.info(f"process_toc_from_entries: offset={offset}, pairs={len(matching_pairs)}")

        if offset is not None:
            result = add_page_offset_to_toc_json(flat, offset)
        else:
            result = []
            for item in flat:
                r = dict(item)
                if "page" in r and r["page"]:
                    r["physical_index"] = r.pop("page")
                result.append(r)

    result = map_toc_pages_to_physical(result, page_list, start_index=1, logger=logger)
    result = verify_page_anchors(result, page_list, logger=logger)
    result = deterministic_repair_missing_pages(result, page_list, start_index=1, logger=logger)
    result = convert_physical_index_to_int(result)

    if logger:
        logger.info(f"process_toc_from_entries: result={result}")

    return result


# ── No-TOC path (unchanged, single SLM call) ─────────────────────────────────

_GARBLED_RE = re.compile(r"/G\d{2,3}")


def _is_garbled_ocr(text: str) -> bool:
    """Return True if the text looks like PDF glyph-code garbage (/G65 sequences)."""
    if not text:
        return False
    hits = len(_GARBLED_RE.findall(text))
    return hits > 10 and (hits / max(len(text), 1)) > 0.02


def process_no_toc(page_list, start_index=1, model=None, logger=None, opt=None):
    page_contents = []
    token_lengths = []
    for page_index in range(start_index, start_index + len(page_list)):
        page_text = (
            f"<physical_index_{page_index}>\n"
            f"{page_list[page_index - start_index][0]}\n"
            f"<physical_index_{page_index}>\n\n"
        )
        page_contents.append(page_text)
        token_lengths.append(count_tokens(page_text, model))
    max_group = (
        getattr(opt, "max_prompt_tokens", MAX_PROMPT_TOKENS_DEFAULT) - PROMPT_OVERHEAD_TOKENS
        if opt
        else MAX_PROMPT_TOKENS_DEFAULT - PROMPT_OVERHEAD_TOKENS
    )
    group_texts = page_list_to_group_text(page_contents, token_lengths, max_tokens=max_group)
    if logger:
        logger.info(f"process_no_toc: len(group_texts)={len(group_texts)} max_group_tokens={max_group}")

    system_prompt = (
        "You extract a hierarchical outline from textbook body text. "
        "Each node's page_number is the 1-based document page index where that section begins "
        "(infer from <physical_index_N> tags). Respond with ONLY valid HierarchicalTOC JSON."
    )
    all_physical = []
    for seg_index, group_text in enumerate(group_texts):
        user_prompt = (
            f"Document text with page tags:\n\n{group_text}\n\nReturn the hierarchical JSON object."
        )
        if logger:
            logger.info(f"pipeline_stage=no_toc_outline segment={seg_index + 1}/{len(group_texts)}")

        # Skip segments that are clearly garbled OCR glyph codes — the model cannot help.
        if _is_garbled_ocr(group_text):
            print(
                f"[PageIndex] stage=no_toc_outline batch={seg_index + 1}/{len(group_texts)} "
                f"action=skip reason=garbled_ocr",
                flush=True,
            )
            if logger:
                logger.info(f"process_no_toc: segment {seg_index + 1} skipped — garbled OCR")
            continue

        # Try with full segment; on TokenBudgetExceeded shrink by half and retry once.
        result = None
        for attempt, prompt_to_use in enumerate([user_prompt, None]):
            if attempt == 1:
                # Shrink: keep first half of the group_text content
                half = len(group_text) // 2
                short_text = group_text[:half]
                prompt_to_use = (
                    f"Document text with page tags:\n\n{short_text}\n\nReturn the hierarchical JSON object."
                )
                print(
                    f"[PageIndex] stage=no_toc_outline batch={seg_index + 1}/{len(group_texts)} "
                    f"action=shrink_retry chars={len(short_text)}",
                    flush=True,
                )
            else:
                prompt_to_use = user_prompt

            try:
                result = generate_structured(
                    prompt_to_use,
                    HierarchicalTOC,
                    system_prompt=system_prompt,
                    stage="no_toc_outline",
                    batch_index=seg_index,
                )
                break
            except TokenBudgetExceeded as exc:
                if attempt == 0:
                    print(
                        f"[PageIndex] stage=no_toc_outline batch={seg_index + 1}/{len(group_texts)} "
                        f"action=budget_exceeded shrinking",
                        flush=True,
                    )
                    continue
                # Second attempt also exceeded — skip this segment
                if logger:
                    logger.info(
                        f"process_no_toc: segment {seg_index + 1}/{len(group_texts)} "
                        f"budget exceeded after shrink; skipping"
                    )
                print(
                    f"[PageIndex] stage=no_toc_outline batch={seg_index + 1}/{len(group_texts)} "
                    f"action=skip reason=TokenBudgetExceeded",
                    flush=True,
                )
                break
            except (TimeoutError, PipelineStageFailure) as exc:
                if logger:
                    logger.info(
                        f"process_no_toc: segment {seg_index + 1}/{len(group_texts)} "
                        f"failed ({type(exc).__name__}); skipping"
                    )
                print(
                    f"[PageIndex] stage=no_toc_outline batch={seg_index + 1}/{len(group_texts)} "
                    f"action=skip reason={type(exc).__name__}",
                    flush=True,
                )
                break

        if result is not None:
            all_physical.extend(_hierarchical_toc_to_flat_physical(result))

    if logger:
        logger.info(f"process_no_toc: {len(all_physical)} sections from {len(group_texts)} segment(s)")

    return convert_physical_index_to_int(all_physical)


# ── TOC without page numbers path (no-index fallback) ────────────────────────

def process_toc_no_page_numbers(toc_content, toc_page_list, page_list, start_index=1, model=None, logger=None):
    page_contents = []
    token_lengths = []
    toc_content = toc_transformer(toc_content, model)
    if logger:
        logger.info(f"process_toc_no_page_numbers: toc_transformer done")
    for page_index in range(start_index, start_index + len(page_list)):
        page_text = (
            f"<physical_index_{page_index}>\n"
            f"{page_list[page_index - start_index][0]}\n"
            f"<physical_index_{page_index}>\n\n"
        )
        page_contents.append(page_text)
        token_lengths.append(count_tokens(page_text, model))

    group_texts = page_list_to_group_text(page_contents, token_lengths)
    toc_with_page_number = copy.deepcopy(toc_content)
    for group_text in group_texts:
        toc_with_page_number = add_page_number_to_toc(group_text, toc_with_page_number, model)
    if logger:
        logger.info(f"process_toc_no_page_numbers: add_page_number_to_toc done")

    toc_with_page_number = convert_physical_index_to_int(toc_with_page_number)
    toc_with_page_number = deterministic_repair_missing_pages(
        toc_with_page_number, page_list, start_index=start_index, logger=logger
    )
    return toc_with_page_number


# ── Deterministic appear_start ────────────────────────────────────────────────

async def check_title_appearance_in_start_concurrent(structure, page_list, model=None, logger=None):
    """
    Deterministic replacement: uses rapidfuzz/substring matching only.
    Signature preserved for compatibility with tree_parser callers.
    """
    if logger:
        logger.info("check_title_appearance_in_start_concurrent: deterministic mode")

    for item in structure:
        idx = item.get("physical_index")
        if idx is None:
            item["appear_start"] = "no"
            continue
        list_idx = idx - 1  # page_list is 0-based
        if list_idx < 0 or list_idx >= len(page_list):
            item["appear_start"] = "no"
            continue
        page_text = page_list[list_idx][0]
        item["appear_start"] = deterministic_appear_start(item.get("title", ""), page_text)

    return structure


# ── TOC detection (budgeted multi-batch SLM calls, max 5 pages each) ───────────

def _dedupe_toc_entries(entries):
    seen = set()
    out = []
    for e in entries:
        key = (e.title.strip().lower(), e.page_number)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _min_chapter_content_page(nodes: list, page_list: list | None = None) -> int:
    """Earliest start page among chapter nodes — skips front-matter during subsection scan."""
    chapters = [n for n in nodes if n.get("content_type") == "chapter"]
    if chapters:
        return min(n.get("start_index") or n.get("start_page") or 1 for n in chapters)
    if page_list:
        return detect_textbook_content_start(page_list)
    return 1


_REPEATED_HEADER_RE = re.compile(r"(?:^|\n)([^\n]{0,120})\n(?:.*\n)*?\1\n", re.MULTILINE)


def _strip_headers_footers(text: str, max_header_len: int = 120) -> str:
    """Remove lines that look like repeated page headers / footers."""
    lines = text.splitlines()
    if len(lines) < 4:
        return text
    # Count occurrences of each short line; remove if it appears on >50% of pages
    from collections import Counter
    short = [l.strip() for l in lines if 0 < len(l.strip()) <= max_header_len]
    counts = Counter(short)
    total_pages_approx = max(text.count("--- PAGE"), 1)
    noise = {l for l, c in counts.items() if c >= max(2, total_pages_approx * 0.4)}
    cleaned = [l for l in lines if l.strip() not in noise]
    return "\n".join(cleaned)


def _detect_toc_batch(batch_start, batch_end, page_list, opt, logger, batch_index,
                      checkpoints=None, results_dir=None):
    chars_limit = getattr(opt, "toc_page_chars_limit", 1200)
    batch_timeout = getattr(opt, "toc_batch_timeout_seconds", 90)
    chunks = []
    for i in range(batch_start, batch_end):
        raw_text = page_list[i][0] or ""
        # Hard-truncate per page before assembling prompt
        truncated = raw_text[:chars_limit]
        chunks.append(f"--- PAGE {i + 1} ---\n{truncated}")

    batch_text = "\n\n".join(chunks)
    # Strip repeated headers/footers from assembled batch text
    batch_text = _strip_headers_footers(batch_text)

    system_prompt = (
        "You are a table-of-contents extractor. "
        "Given page text from a document, detect if a Table of Contents exists. "
        "If yes, return every entry with its title and page number. "
        "Be concise. Return ONLY the JSON object."
    )
    user_prompt = (
        f"Pages {batch_start + 1}-{batch_end} from document:\n\n{batch_text}\n\n"
        "Return JSON with toc_found and toc_entries list."
    )

    est_tokens = count_tokens(user_prompt + system_prompt, None)
    print(
        f"[PageIndex] stage=toc_detection batch={batch_index} "
        f"pages={batch_start + 1}-{batch_end} "
        f"prompt_chars={len(user_prompt)} est_tokens={est_tokens} "
        f"timeout={batch_timeout}s",
        flush=True,
    )
    if logger:
        logger.info(
            f"pipeline_stage=toc_detection batch_index={batch_index} "
            f"pages={batch_start + 1}-{batch_end} "
            f"prompt_chars={len(user_prompt)} est_tokens={est_tokens}"
        )

    # Save raw batch text for debugging
    if results_dir:
        try:
            raw_path = os.path.join(results_dir, f"raw_toc_batch_{batch_index}.txt")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(f"=== BATCH {batch_index} pages {batch_start + 1}-{batch_end} ===\n")
                f.write(f"est_tokens={est_tokens} prompt_chars={len(user_prompt)}\n\n")
                f.write(user_prompt)
        except OSError:
            pass

    toc_opts = dict(TOC_GENERATION_OPTIONS)
    np = getattr(opt, "toc_num_predict", None)
    if np is not None:
        toc_opts["num_predict"] = int(np)

    result = generate_structured(
        user_prompt,
        TOCDetectionResult,
        system_prompt=system_prompt,
        stage="toc_detection",
        batch_index=batch_index,
        inference_options=toc_opts,
        timeout_seconds=batch_timeout,
        fail_fast_json=False,
        max_retries=getattr(opt, "max_retries", 2),
    )

    # Save raw response alongside batch text
    if results_dir:
        try:
            raw_path = os.path.join(results_dir, f"raw_toc_batch_{batch_index}.txt")
            with open(raw_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n=== RESULT toc_found={result.toc_found} entries={len(result.toc_entries)} ===\n")
        except OSError:
            pass

    return result


def _pages_text(page_list, start: int, end: int, chars_limit: int = 0) -> str:
    chunks = []
    for i in range(start, end):
        text = page_list[i][0] or ""
        if chars_limit:
            text = text[:chars_limit]
        chunks.append(f"--- PAGE {i + 1} ---\n{text}")
    return "\n\n".join(chunks)


def _detection_from_deterministic(entries, toc_page_list):
    toc_entries = []
    for e in entries:
        toc_entries.append(
            TOCEntry(
                structure=e.get("structure") or "",
                title=e["title"],
                page_number=e.get("page_number") or 0,
            )
        )
    return TOCDetectionResult(toc_found=True, toc_entries=toc_entries), toc_page_list


def find_toc_pages(start_page_index, page_list, opt, logger=None, results_dir=None):
    """
    Scan `opt.toc_check_page_num` pages starting at `start_page_index`.
    Deterministic parser first on TOC anchor page; SLM batches only when confidence is low.
    Returns (TOCDetectionResult, toc_page_list) or (None, []) on failure.
    """
    n = opt.toc_check_page_num
    pages_per_batch = getattr(opt, "toc_pages_per_batch", 1)
    chars_limit = getattr(opt, "toc_page_chars_limit", 5000)
    end = min(start_page_index + n, len(page_list))
    if start_page_index >= len(page_list):
        if logger:
            logger.info("find_toc_pages: start_page_index beyond document")
        return None, []

    page_texts = [page_list[i][0] or "" for i in range(start_page_index, end)]
    toc_anchor = find_toc_page_index(page_texts, max_scan=len(page_texts))
    min_conf = getattr(opt, "toc_deterministic_min_confidence", 0.55)
    use_deterministic = not skip_deterministic_toc(opt)

    if use_deterministic and toc_anchor is not None:
        abs_idx = start_page_index + toc_anchor
        toc_page_list = [abs_idx]
        full_toc_text = page_list[abs_idx][0] or ""
        det_entries, det_conf = deterministic_parse_toc(full_toc_text, max_pages=len(page_list))
        if det_entries and det_conf >= min_conf:
            if logger:
                logger.info(
                    f"find_toc_pages: TOC page {abs_idx + 1} deterministic conf={det_conf:.2f} "
                    f"entries={len(det_entries)}"
                )
            print(
                f"[PageIndex] stage=toc_detection action=deterministic_toc_page "
                f"page={abs_idx + 1} entries={len(det_entries)} confidence={det_conf:.2f}",
                flush=True,
            )
            record_path("deterministic_toc")
            detection, _ = _detection_from_deterministic(det_entries, toc_page_list)
            detection.toc_entries = _dedupe_toc_entries(detection.toc_entries)
            return detection, toc_page_list

    toc_page_list = list(range(start_page_index, end))
    if use_deterministic:
        batch_text = _pages_text(page_list, start_page_index, end, chars_limit=chars_limit)
        det_entries, det_conf = deterministic_parse_toc(batch_text, max_pages=len(page_list))
        if det_entries and det_conf >= min_conf:
            if logger:
                logger.info(
                    f"find_toc_pages: deterministic parser confidence={det_conf:.2f} "
                    f"entries={len(det_entries)}"
                )
            print(
                f"[PageIndex] stage=toc_detection action=deterministic "
                f"entries={len(det_entries)} confidence={det_conf:.2f}",
                flush=True,
            )
            record_path("deterministic_toc")
            detection, _ = _detection_from_deterministic(det_entries, toc_page_list)
            detection.toc_entries = _dedupe_toc_entries(detection.toc_entries)
            return detection, toc_page_list
    elif logger:
        logger.info("find_toc_pages: skipping deterministic TOC (quality-level=high)")
        print("[PageIndex] stage=toc_detection mode=llm_only (deterministic skipped)", flush=True)

    merged_entries = []
    toc_found = False
    batch_index = 0
    total_batches = max(1, (end - start_page_index + pages_per_batch - 1) // pages_per_batch)

    for batch_start in range(start_page_index, end, pages_per_batch):
        batch_end = min(batch_start + pages_per_batch, end)
        try:
            detection = _detect_toc_batch(
                batch_start, batch_end, page_list, opt, logger, batch_index,
                checkpoints=None, results_dir=results_dir,
            )
            record_path("llm_toc")
        except (TokenBudgetExceeded, TimeoutError, PipelineStageFailure) as exc:
            from .model_router import is_max_quality
            from .nvidia_hybrid import nvidia_escalation_was_attempted, nvidia_available

            batch_size = batch_end - batch_start
            should_shrink = batch_size > 1
            if should_shrink and isinstance(exc, (TimeoutError, PipelineStageFailure)) and is_max_quality():
                should_shrink = nvidia_escalation_was_attempted() or not nvidia_available()

            if should_shrink:
                mid = batch_start + (batch_end - batch_start) // 2
                PipelineMetrics.record_shrink("toc_detection")
                if logger:
                    logger.info(
                        f"batch_shrink stage=toc_detection reason={type(exc).__name__} "
                        f"pages {batch_start + 1}-{batch_end}"
                    )
                print(
                    f"[PageIndex] stage=toc_detection batch={batch_index + 1}/{total_batches} "
                    f"action=shrink pages={batch_start + 1}-{batch_end}",
                    flush=True,
                )
                for sub_start, sub_end in ((batch_start, mid), (mid, batch_end)):
                    if sub_start >= sub_end:
                        continue
                    try:
                        sub = _detect_toc_batch(
                            sub_start, sub_end, page_list, opt, logger, batch_index,
                            checkpoints=None, results_dir=results_dir,
                        )
                        if sub.toc_found:
                            toc_found = True
                            merged_entries.extend(sub.toc_entries)
                    except Exception as sub_exc:
                        if logger:
                            logger.info(f"find_toc_pages: sub-batch failed: {sub_exc}")
                batch_index += 1
                continue
            if logger:
                logger.info(
                    f"toc_detection: single page {batch_start + 1} failed ({exc}); skipping"
                )
            batch_index += 1
            continue
        except Exception as exc:
            if logger:
                logger.info(f"find_toc_pages: detection failed batch {batch_index}: {exc}")
            batch_index += 1
            continue

        if detection.toc_found:
            toc_found = True
            merged_entries.extend(detection.toc_entries)
            if logger:
                logger.info(
                    f"toc_detection progress batch={batch_index + 1} "
                    f"entries_in_batch={len(detection.toc_entries)}"
                )
        batch_index += 1

    if not toc_found or len(merged_entries) < 3:
        if logger:
            logger.info("find_toc_pages: no TOC or fewer than 3 entries after all batches")
        return None, []

    merged_entries = _dedupe_toc_entries(merged_entries)
    detection = TOCDetectionResult(toc_found=True, toc_entries=merged_entries)
    if logger:
        logger.info(
            f"find_toc_pages: found {len(detection.toc_entries)} entries "
            f"in {batch_index} batch(es), pages {toc_page_list}"
        )
    return detection, toc_page_list


# ── check_toc: rewritten to use toc_entries directly ─────────────────────────

def check_toc(page_list, opt=None, logger=None, results_dir=None):
    """
    Returns a dict with:
      - mode: 'toc_from_entries' | 'toc_no_page_numbers' | 'no_toc'
      - detection: TOCDetectionResult | None
      - toc_page_list: list[int]
      - toc_content: str | None  (legacy; populated only for toc_no_page_numbers)
    """
    detection, toc_page_list = find_toc_pages(0, page_list, opt, logger=logger, results_dir=results_dir)

    if detection is None:
        if logger:
            logger.info("check_toc: no TOC found")
        return {"mode": "no_toc", "detection": None, "toc_page_list": [], "toc_content": None}

    if _entries_have_page_numbers(detection):
        if logger:
            logger.info("check_toc: TOC with page numbers — using toc_entries directly")
        return {
            "mode": "toc_from_entries",
            "detection": detection,
            "toc_page_list": toc_page_list,
            "toc_content": None,
        }

    # TOC found but no page numbers in entries — build raw content for toc_no_page_numbers path
    if logger:
        logger.info("check_toc: TOC without page numbers — using toc_no_page_numbers path")
    toc_content = ""
    for page_index in toc_page_list:
        toc_content += page_list[page_index][0]
    return {
        "mode": "toc_no_page_numbers",
        "detection": detection,
        "toc_page_list": toc_page_list,
        "toc_content": toc_content,
    }


# ── meta_processor: deterministic validation, no recursive repair ─────────────

async def meta_processor(page_list, mode=None, toc_content=None, toc_page_list=None,
                          detection=None, start_index=1, opt=None, logger=None):
    if logger:
        logger.info(f"meta_processor: mode={mode} start_index={start_index}")

    if mode == "toc_from_entries":
        toc_with_page_number = process_toc_from_entries(
            detection, toc_page_list, page_list, opt=opt, logger=logger
        )
    elif mode == "toc_no_page_numbers":
        toc_with_page_number = process_toc_no_page_numbers(
            toc_content, toc_page_list, page_list,
            start_index=start_index, model=getattr(opt, "model", None), logger=logger
        )
    else:  # no_toc
        toc_with_page_number = process_no_toc(
            page_list,
            start_index=start_index,
            model=getattr(opt, "model", None),
            logger=logger,
            opt=opt,
        )

    # Filter None physical_index
    toc_with_page_number = [item for item in toc_with_page_number if item.get("physical_index") is not None]

    # Deterministic range clamp (out-of-bounds → None → filter)
    toc_with_page_number = validate_and_truncate_physical_indices(
        toc_with_page_number, len(page_list), start_index=start_index, logger=logger
    )
    toc_with_page_number = [item for item in toc_with_page_number if item.get("physical_index") is not None]

    toc_with_page_number = filter_junk_toc_entries(
        toc_with_page_number,
        logger=logger,
        strict=junk_filter_strict(opt),
        min_content_page=detect_textbook_content_start(page_list),
    )

    if logger:
        logger.info(f"meta_processor: {len(toc_with_page_number)} entries after junk filter")

    return toc_with_page_number


# ── Bounded large-node recursion ─────────────────────────────────────────────

async def process_large_node_recursively(node, page_list, opt=None, logger=None, _depth: int = 0):
    """
    Subdivide `node` if it exceeds both page and token thresholds.
    Bounded to depth=1 (children are never recursed) and a global split cap.
    """
    if _depth > 0:
        # Never recurse beyond depth 1
        return node

    recursive_depth = getattr(opt, "recursive_depth", 0)
    if recursive_depth <= 0 or _depth >= recursive_depth:
        if logger:
            logger.info("process_large_node_recursively: skipped (recursive_depth=%s)", recursive_depth)
        return node

    if len(_split_counter) >= MAX_LARGE_NODE_SPLITS:
        if logger:
            logger.warning(
                f"process_large_node_recursively: MAX_LARGE_NODE_SPLITS={MAX_LARGE_NODE_SPLITS} "
                f"exceeded — skipping further splits for '{node.get('title', '')}'"
            )
        return node

    node_page_list = page_list[node["start_index"] - 1: node["end_index"]]
    token_num = sum(page[1] for page in node_page_list)

    page_threshold = getattr(opt, "max_page_num_each_node", 10)
    token_threshold = getattr(opt, "max_token_num_each_node", 20000)
    page_span = node["end_index"] - node["start_index"]

    if page_span <= page_threshold or token_num < token_threshold:
        return node

    if logger:
        logger.info(
            f"process_large_node_recursively: splitting '{node['title']}' "
            f"pages={page_span} tokens={token_num}"
        )
    _split_counter.append(1)

    node_toc_tree = await meta_processor(
        node_page_list, mode="no_toc", start_index=node["start_index"], opt=opt, logger=logger
    )
    node_toc_tree = await check_title_appearance_in_start_concurrent(
        node_toc_tree, page_list, model=getattr(opt, "model", None), logger=logger
    )

    valid_items = [item for item in node_toc_tree if item.get("physical_index") is not None]

    if valid_items and node["title"].strip() == valid_items[0]["title"].strip():
        node["nodes"] = post_processing(valid_items[1:], node["end_index"])
        node["end_index"] = valid_items[1]["start_index"] if len(valid_items) > 1 else node["end_index"]
    else:
        node["nodes"] = post_processing(valid_items, node["end_index"])
        if valid_items:
            node["end_index"] = valid_items[0]["start_index"]

    # depth-1: do NOT recurse into newly created children
    return node


# ── tree_parser: main pipeline orchestrator ───────────────────────────────────

def _validation_kwargs(opt=None) -> dict:
    ratio = getattr(opt, "fragment_summary_max_fragment_ratio", None) if opt else None
    if ratio is not None:
        return {"fragment_max_ratio": float(ratio)}
    return {}


async def tree_parser(page_list, opt, doc=None, logger=None, checkpoints=None, results_dir=None):
    resume = getattr(opt, "resume", False)

    if checkpoints and checkpoints.is_done("tree_structure.json", resume):
        if logger:
            logger.info("tree_parser: resume — loading tree_structure.json")
        return checkpoints.load("tree_structure.json")

    detection = None
    check_toc_result = None
    if checkpoints and checkpoints.is_done("toc_candidates.json", resume):
        raw = checkpoints.load("toc_candidates.json")
        if raw:
            entries = [TOCEntry(**e) if isinstance(e, dict) else e for e in raw]
            detection = TOCDetectionResult(toc_found=True, toc_entries=entries)
            check_toc_result = {
                "mode": "toc_from_entries" if _entries_have_page_numbers(detection) else "toc_no_page_numbers",
                "detection": detection,
                "toc_page_list": list(range(min(getattr(opt, "toc_check_page_num", 20), len(page_list)))),
                "toc_content": None,
            }
            if logger:
                logger.info("tree_parser: resume — loaded toc_candidates.json")
    else:
        if logger:
            logger.info("pipeline_stage=check_toc")
        print("[PageIndex] stage=toc_detection starting ...", flush=True)
        check_toc_result = check_toc(page_list, opt, logger=logger, results_dir=results_dir)
        print(
            f"[PageIndex] stage=toc_detection COMPLETE mode={check_toc_result['mode']}",
            flush=True,
        )
        if logger:
            logger.info(f"tree_parser: check_toc mode={check_toc_result['mode']}")
        detection = check_toc_result.get("detection")
        if checkpoints and detection:
            checkpoints.save(
                "toc_candidates.json",
                [e.model_dump() for e in detection.toc_entries],
            )

    if checkpoints and checkpoints.is_done("validated_toc.json", resume):
        toc_with_page_number = checkpoints.load("validated_toc.json")
        if logger:
            logger.info("tree_parser: resume — loaded validated_toc.json")
    else:
        if logger:
            logger.info("pipeline_stage=meta_processor")
        mode = check_toc_result["mode"]
        toc_with_page_number = await meta_processor(
            page_list,
            mode=mode,
            toc_content=check_toc_result.get("toc_content"),
            toc_page_list=check_toc_result.get("toc_page_list", []),
            detection=detection,
            start_index=1,
            opt=opt,
            logger=logger,
        )
        if checkpoints:
            checkpoints.save("validated_toc.json", toc_with_page_number)

    toc_with_page_number = add_preface_if_needed(toc_with_page_number)
    toc_with_page_number = await check_title_appearance_in_start_concurrent(
        toc_with_page_number, page_list, model=getattr(opt, "model", None), logger=logger
    )

    valid_toc_items = [item for item in toc_with_page_number if item.get("physical_index") is not None]
    valid_toc_items = repair_hierarchy(valid_toc_items, logger=logger)
    toc_tree = post_processing(
        valid_toc_items, len(page_list), page_list=page_list, opt=opt, logger=logger
    )
    toc_tree = semantic_dedupe(toc_tree, logger=logger)

    # ── Phase 2: early validation + deterministic sub-section injection ──────
    _early_val = validate_semantic_tree({"structure": toc_tree}, **_validation_kwargs(opt))
    if not _early_val["checks"].get("chapters_have_children"):
        print("[PageIndex] stage=subsection_injection action=run reason=no_children", flush=True)
        min_content = _min_chapter_content_page(toc_tree, page_list)
        min_heading_len = int(getattr(opt, "min_heading_len", 8) or 8)
        added = inject_subsections_into_tree(
            toc_tree, page_list, logger=logger,
            min_content_page=min_content,
            min_heading_len=min_heading_len,
            opt=opt,
        )
        log_junk_filter_stats(logger=logger, max_quality=is_max_quality())
        if added:
            print(f"[PageIndex] stage=subsection_injection action=complete children_added={added}", flush=True)
        else:
            print("[PageIndex] stage=subsection_injection action=no_headings_found", flush=True)
    # ─────────────────────────────────────────────────────────────────────────

    if checkpoints:
        checkpoints.save("tree_structure.json", toc_tree)

    recursive_depth = getattr(opt, "recursive_depth", 0)
    if recursive_depth > 0:
        if logger:
            logger.info("pipeline_stage=large_node_splitting")
        tasks = [
            process_large_node_recursively(node, page_list, opt, logger=logger, _depth=0)
            for node in toc_tree
        ]
        await asyncio.gather(*tasks)
        if checkpoints:
            checkpoints.save("tree_structure.json", toc_tree)
    elif logger:
        logger.info("pipeline_stage=large_node_splitting skipped (recursive_depth=0)")

    print(f"[PageIndex] stage=tree_construction COMPLETE nodes={len(toc_tree)}", flush=True)
    return toc_tree


# ── page_index_main ───────────────────────────────────────────────────────────

def _write_output_artifacts(result: dict, results_dir: str, pdf_name: str, skip_summaries: bool):
    """Write canonical output artifacts and print explicit completion messages."""
    import json as _json
    export_structure = nodes_to_children_export(result.get("structure", []))
    export_result = {**result, "structure": export_structure}
    artifacts = {
        "structure.json": export_result,
        "tree_structure.json": export_structure,
    }
    nodes = structure_to_list(result.get("structure", []))
    summaries = [
        {
            "node_id": n.get("node_id"),
            "title": n.get("title"),
            "structure": n.get("structure"),
            "level": n.get("level"),
            "summary": n.get("summary", ""),
            "keywords": n.get("keywords", []),
            "semantic_tags": n.get("semantic_tags", []),
            "content_type": n.get("content_type"),
        }
        for n in nodes
        if n.get("summary")
    ]
    if not skip_summaries or summaries:
        artifacts["summaries.json"] = summaries

    written = []
    for fname, data in artifacts.items():
        path = os.path.join(results_dir, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            written.append(fname)
        except OSError as e:
            print(f"[PageIndex] artifact_write_error: {fname}: {e}", flush=True)

    # tree.json is an alias used by the video pipeline / frontend
    tree_path = os.path.join(results_dir, "tree.json")
    try:
        with open(tree_path, "w", encoding="utf-8") as f:
            _json.dump(export_structure, f, ensure_ascii=False, indent=2)
        written.append("tree.json")
    except OSError as e:
        print(f"[PageIndex] artifact_write_error: tree.json: {e}", flush=True)

    print(
        f"[PageIndex] artifacts_written: {', '.join(written)} → {results_dir}",
        flush=True,
    )
    print(f"[PageIndex] PIPELINE COMPLETE — {pdf_name}", flush=True)


def _minimal_flat_structure(page_list, pdf_name: str) -> list:
    return [
        {
            "node_id": f"{i:04d}",
            "title": f"Page {i + 1}",
            "start_index": i + 1,
            "end_index": i + 1,
        }
        for i in range(len(page_list))
    ] or [{"node_id": "0000", "title": pdf_name or "Document", "start_index": 1, "end_index": 1}]


def _merge_summaries_into_structure(structure: list, cached_summaries: list) -> list:
    """Apply flat summary cache onto an in-memory tree without replacing page spans."""
    if not cached_summaries or not structure:
        return structure
    by_id = {s["node_id"]: s for s in cached_summaries if s.get("node_id")}

    def _apply(node: dict) -> None:
        nid = node.get("node_id")
        if nid and nid in by_id:
            src = by_id[nid]
            for key in (
                "summary", "keywords", "semantic_tags", "learning_objectives",
                "visualizable_elements", "content_type",
            ):
                if src.get(key):
                    node[key] = src[key]
        for ch in node.get("nodes") or node.get("children") or []:
            _apply(ch)

    for root in structure:
        _apply(root)
    return structure


def page_index_main(doc, opt=None):
    global _split_counter
    _split_counter = []
    reset_runtime_summary()
    reset_junk_filter_stats()

    if opt is None:
        opt = ConfigLoader().load()

    logger = JsonLogger(doc)

    from io import BytesIO
    is_valid_pdf = (
        (isinstance(doc, str) and os.path.isfile(doc) and doc.lower().endswith(".pdf"))
        or isinstance(doc, BytesIO)
    )
    if not is_valid_pdf:
        raise ValueError("Unsupported input type. Expected a PDF file path or BytesIO object.")

    pdf_name = get_pdf_name(doc)
    results_dir = os.path.join("results", pdf_name)
    os.makedirs(results_dir, exist_ok=True)
    checkpoints = PipelineCheckpoints(results_dir)

    mode = getattr(opt, "mode", "cpu")
    PipelineMetrics.reset(pdf_name=pdf_name, mode=mode)

    print("Parsing PDF (local token estimates)...")
    if checkpoints.is_done("extracted_pages.json", getattr(opt, "resume", False)):
        raw_pages = checkpoints.load("extracted_pages.json") or []
        page_list = [
            (p.get("text") or p.get("text_preview", ""), p.get("token_count", 0))
            for p in raw_pages
        ]
        print(f"  resume: loaded {len(page_list)} pages from extracted_pages.json")
    else:
        page_list = get_page_tokens(
            doc,
            model=None,
            use_api_tokenizer=False,
            pdf_parser=getattr(opt, "pdf_parser", None) or "PyPDF2",
        )
        print(f"  extracted {len(page_list)} pages")

    page_list = strip_page_list_banners(page_list, logger=logger)

    max_pages = getattr(opt, "max_pages", None)
    if max_pages:
        page_list = page_list[: int(max_pages)]
        logger.info({"max_pages_applied": max_pages, "pages_after_trim": len(page_list)})

    if not checkpoints.is_done("extracted_pages.json", getattr(opt, "resume", False)):
        checkpoints.save(
            "extracted_pages.json",
            [{"page": i + 1, "token_count": p[1], "text": p[0]} for i, p in enumerate(page_list)],
        )

    logger.info({"total_page_number": len(page_list)})
    logger.info({"total_token": sum(page[1] for page in page_list)})

    is_demo = getattr(opt, "demo", False)
    skip_summaries = (
        getattr(opt, "no_summaries", False)
        or str(getattr(opt, "if_add_node_summary", "yes")).lower() == "no"
    )
    if is_demo:
        print("[PageIndex] demo mode: using demo_overrides from config.yaml", flush=True)

    async def page_index_builder():
        try:
            structure = await tree_parser(
                page_list, opt, doc=doc, logger=logger,
                checkpoints=checkpoints, results_dir=results_dir,
            )
        except PipelineStageFailure as exc:
            logger.error({"pipeline_aborted_stage": str(exc), "fallback": "minimal_structure"})
            structure = _minimal_flat_structure(page_list, pdf_name)
            checkpoints.save("tree_structure.json", structure)

        if getattr(opt, "if_add_node_id", "yes") == "yes":
            write_node_id(structure)
            assign_parent_ids(structure)
        if getattr(opt, "if_add_node_text", "no") == "yes":
            add_node_text(structure, page_list)

        if not skip_summaries and getattr(opt, "if_add_node_summary", "yes") == "yes":
            if getattr(opt, "if_add_node_text", "no") == "no":
                add_node_text(structure, page_list)
            max_summaries = getattr(opt, "max_summary_pages", None)
            if checkpoints.is_done("summaries.json", getattr(opt, "resume", False)):
                cached = checkpoints.load("summaries.json")
                if cached:
                    structure = _merge_summaries_into_structure(structure, cached)
                    if logger:
                        logger.info("page_index_builder: resume — merged summaries.json into tree")
            else:
                logger.info("pipeline_stage=summary_generation")
                try:
                    await generate_summaries_for_structure(
                        structure,
                        model=getattr(opt, "token_count_model", getattr(opt, "model", None)),
                        max_nodes=max_summaries,
                        checkpoints=checkpoints,
                        opt=opt,
                    )
                except PipelineStageFailure as exc:
                    logger.error({"summary_stage_failed": str(exc), "fallback": "title_only"})
            if force_title_polish(opt):
                polished = polish_titles_llm(structure, opt=opt, logger=logger)
                print(
                    f"[PageIndex] stage=title_polish action=complete polished={polished}",
                    flush=True,
                )
            if getattr(opt, "if_add_node_text", "no") == "no":
                remove_structure_text(structure)

        if getattr(opt, "if_add_doc_description", "no") == "yes":
            try:
                clean_structure = create_clean_structure_for_description(structure)
                doc_description = generate_doc_description(
                    clean_structure, model=getattr(opt, "model", None)
                )
            except Exception as exc:
                logger.error({"doc_description_failed": str(exc)})
                doc_description = ""
            structure = format_structure(
                structure,
                order=["title", "node_id", "start_index", "end_index", "summary", "text", "nodes"],
            )
            print("\n" + "=" * 72)
            print("FULL DOCUMENT TREE (post-indexing)")
            print("=" * 72)
            print_tree(structure)
            result = {
                "doc_name": pdf_name,
                "doc_description": doc_description,
                "structure": structure,
            }
            checkpoints.save("structure.json", result)
            _write_output_artifacts(result, results_dir, pdf_name, skip_summaries)
            return result

        structure = format_structure(
            structure,
            order=[
                "title", "structure", "level", "parent_id", "node_id",
                "start_page", "end_page", "start_index", "end_index",
                "summary", "keywords", "semantic_tags", "learning_objectives",
                "visualizable_elements", "grade_appropriateness", "content_type", "text", "nodes",
            ],
        )
        print("\n" + "=" * 72)
        print("FULL DOCUMENT TREE (post-indexing)")
        print("=" * 72)
        print_tree(structure)
        result = {"doc_name": pdf_name, "structure": structure}
        validation = validate_semantic_tree(result, logger=logger, **_validation_kwargs(opt))

        # ── Phase 2: final repair pass if hierarchy is still flat ───────────
        needs_repair = (
            not validation["checks"].get("chapters_have_children")
            or not validation["checks"].get("has_hierarchy_depth")
        )
        if needs_repair:
            print(
                "[PageIndex] stage=final_repair action=inject_subsections "
                f"failures={validation['failures']}",
                flush=True,
            )
            min_content = _min_chapter_content_page(structure, page_list)
            min_heading_len = int(getattr(opt, "min_heading_len", 8) or 8)
            added = inject_subsections_into_tree(
                structure, page_list, logger=logger,
                min_content_page=min_content,
                min_heading_len=min_heading_len,
                opt=opt,
            )
            log_junk_filter_stats(logger=logger, max_quality=is_max_quality())
            if added:
                validation = validate_semantic_tree(result, logger=logger, **_validation_kwargs(opt))
                print(
                    f"[PageIndex] stage=final_repair action=complete "
                    f"children_added={added} passed={validation['passed']}",
                    flush=True,
                )
        # ────────────────────────────────────────────────────────────────────

        if not validation["passed"]:
            result["validation_warnings"] = validation["failures"]
            if validation.get("advisory"):
                result["validation_advisory"] = validation["advisory"]
        checkpoints.save("structure.json", result)
        checkpoints.save("semantic_validation.json", validation)
        _write_output_artifacts(result, results_dir, pdf_name, skip_summaries)
        return result

    try:
        result = asyncio.run(page_index_builder())
    except Exception as exc:
        logger.error({"pipeline_aborted": str(exc), "fallback": "minimal_success"})
        structure = _minimal_flat_structure(page_list, pdf_name)
        result = {"doc_name": pdf_name, "structure": structure, "fallback": "minimal_success"}
        checkpoints.save("structure.json", result)
        checkpoints.save("tree_structure.json", structure)
        _write_output_artifacts(result, results_dir, pdf_name, skip_summaries)

    if "validation_warnings" not in result and result.get("structure"):
        validation = validate_semantic_tree(result, logger=logger, **_validation_kwargs(opt))
        if not validation["passed"]:
            result["validation_warnings"] = validation["failures"]
        checkpoints.save("semantic_validation.json", validation)

    PipelineMetrics.dump(os.path.join(results_dir, "pipeline_metrics.json"))
    log_junk_filter_stats(logger=logger, max_quality=is_max_quality())
    log_quality_path_summary(quality_level=getattr(opt, "quality_level", "fast"))

    if getattr(opt, "build_concept_graph", True) and result.get("structure"):
        try:
            from .concept_graph import write_concept_graph
            export_for_graph = nodes_to_children_export(result.get("structure", []))
            write_concept_graph(
                results_dir,
                structure=export_for_graph,
                doc_name=pdf_name,
            )
            print(f"[PageIndex] concept_graph written → {results_dir}/concept_graph.json", flush=True)
        except Exception as cg_exc:
            logger.error({"concept_graph_failed": str(cg_exc)})

    if getattr(opt, "benchmark", False):
        try:
            from .retrieve import benchmark_retrieval
            queries = [n.get("title", "") for n in structure_to_list(result.get("structure", []))[:5] if n.get("title")]
            if queries:
                bench_doc = {
                    pdf_name: {
                        "structure": result.get("structure", []),
                        "pages": [{"page": i + 1, "content": p[0]} for i, p in enumerate(page_list)],
                        "type": "pdf",
                    }
                }
                bench = benchmark_retrieval(bench_doc, pdf_name, queries)
                checkpoints.save("retrieval_benchmark.json", bench)
        except Exception as bench_exc:
            logger.error({"benchmark_failed": str(bench_exc)})

    nodes = structure_to_list(result.get("structure", []))
    summary_count = sum(1 for n in nodes if n.get("summary"))
    print_runtime_summary(tree_node_count=len(nodes), summary_count=summary_count)
    return result


def page_index(doc, model=None, toc_check_page_num=None, max_page_num_each_node=None,
               max_token_num_each_node=None, if_add_node_id=None, if_add_node_summary=None,
               if_add_doc_description=None, if_add_node_text=None):
    user_opt = {
        arg: value for arg, value in locals().items()
        if arg != "doc" and value is not None
    }
    opt = ConfigLoader().load(user_opt)
    return page_index_main(doc, opt)


# ── Shared deterministic/utility helpers (still used) ────────────────────────

def remove_page_number(data):
    if isinstance(data, dict):
        data.pop("page_number", None)
        data.pop("page", None)
        for key in list(data.keys()):
            if "nodes" in key:
                remove_page_number(data[key])
    elif isinstance(data, list):
        for item in data:
            remove_page_number(item)
    return data


def extract_matching_page_pairs(toc_page, toc_physical_index, start_page_index):
    pairs = []
    for phy_item in toc_physical_index:
        for page_item in toc_page:
            if phy_item.get("title") == page_item.get("title"):
                physical_index = phy_item.get("physical_index")
                if physical_index is not None and int(physical_index) >= start_page_index:
                    pairs.append({
                        "title": phy_item.get("title"),
                        "page": page_item.get("page"),
                        "physical_index": physical_index,
                    })
    return pairs


def calculate_page_offset(pairs):
    if not pairs:
        return None
    differences = []
    for pair in pairs:
        try:
            differences.append(pair["physical_index"] - pair["page"])
        except (KeyError, TypeError):
            continue
    if not differences:
        return None
    counts: dict = {}
    for d in differences:
        counts[d] = counts.get(d, 0) + 1
    return max(counts.items(), key=lambda x: x[1])[0]


def add_page_offset_to_toc_json(data, offset):
    for item in data:
        if item.get("page") is not None and isinstance(item["page"], int):
            item["physical_index"] = item["page"] + offset
            del item["page"]
    return data


def add_page_number_to_toc(part, structure, model=None):
    fill_prompt = (
        "You are given a JSON structure of a document and a partial part of the document. "
        "Your task is to check if the title described in the structure starts in the partial document.\n\n"
        "The provided text contains tags like <physical_index_X> to indicate the physical location of page X.\n\n"
        "If the section starts, insert: \"start\": \"yes\", \"physical_index\": \"<physical_index_X>\".\n"
        "If not, insert: \"start\": \"no\", \"physical_index\": None.\n\n"
        "The response should be in the following format:\n"
        "[\n"
        "    {\"structure\": <str or None>, \"title\": <str>, \"start\": \"yes/no\","
        " \"physical_index\": \"<physical_index_X>\" or None},\n"
        "    ...\n"
        "]\n"
        "Do not change previously filled results.\n"
        "Return ONLY valid JSON."
    )
    prompt = fill_prompt + f"\n\nCurrent Document:\n{part}\n\nStructure:\n{json.dumps(structure, indent=2)}\n"
    system_prompt = (
        "Respond with ONLY valid JSON: an object with key \"items\" "
        "(array of rows with structure, title, start, physical_index)."
    )
    parsed = generate_structured(prompt, AddPageNumberResult, system_prompt=system_prompt)
    json_result = []
    for row in parsed.items:
        d = row.model_dump()
        d.pop("start", None)
        json_result.append(d)
    return json_result


def toc_index_extractor(toc, content, model=None, opt=None):
    max_content_tokens = (
        getattr(opt, "max_prompt_tokens", MAX_PROMPT_TOKENS_DEFAULT) - PROMPT_OVERHEAD_TOKENS - 500
        if opt
        else MAX_PROMPT_TOKENS_DEFAULT - PROMPT_OVERHEAD_TOKENS - 500
    )
    content_tokens = count_tokens(content, model)
    if content_tokens > max_content_tokens:
        ratio = max_content_tokens / max(content_tokens, 1)
        trim_len = int(len(content) * ratio * 0.95)
        content = content[:trim_len] + "\n...(truncated for token budget)"
        logging.info(
            "batch_split_reason=token_budget toc_index_extractor content_tokens=%s limit=%s",
            content_tokens,
            max_content_tokens,
        )

    prompt = (
        "You are given a table of contents in JSON format and several pages of a document. "
        "Add the physical_index to each TOC entry based on where it appears in the document.\n\n"
        "Pages contain tags like <physical_index_X> to indicate page X.\n\n"
        "Return JSON: {\"items\": [{\"structure\": ..., \"title\": ..., \"physical_index\": "
        "\"<physical_index_X>\" or null}, ...]}"
    )
    prompt = prompt + "\n\nTable of contents:\n" + str(toc) + "\nDocument pages:\n" + content
    system_prompt = (
        "Respond with ONLY valid JSON: an object with key \"items\" whose value is an array of "
        "{structure, title, physical_index} entries."
    )
    parsed = generate_structured(
        prompt,
        TOCPhysicalIndexList,
        system_prompt=system_prompt,
        stage="toc_index_extractor",
    )
    legacy = []
    for it in parsed.items:
        row = {"title": it.title}
        if it.structure is not None:
            row["structure"] = it.structure
        if it.physical_index is not None:
            row["physical_index"] = it.physical_index
        legacy.append(row)
    return legacy


def toc_transformer(toc_content, model=None):
    system_prompt = (
        "You are a document hierarchy builder. Convert the flat table of contents into a "
        "hierarchical tree, inferring parent-child relationships from section numbering "
        "(e.g. 1, 1.1, 1.1.2). Assign unique node_id strings (e.g. n0000) in depth-first order."
    )
    user_prompt = f"Given table of contents:\n{toc_content}\n\nReturn the hierarchical JSON object."
    hier = generate_structured(user_prompt, HierarchicalTOC, system_prompt=system_prompt)
    flat_list = _hierarchical_toc_to_flat_list(hier)
    return convert_page_to_int(flat_list)


# ── Legacy functions (importable but NOT called by active pipeline) ───────────
# These are preserved for backward compatibility with external callers/tests.

def _LEGACY_toc_detector_single_page(content, model=None):
    """LEGACY: per-page TOC detection. Not called by active pipeline."""
    prompt = (
        f"Your job is to detect if there is a table of content in the given text.\n\n"
        f"Given text: {content}\n\n"
        "return: {\"thinking\": ..., \"toc_detected\": \"yes or no\"}"
    )
    time.sleep(1.2)
    system_prompt = "Respond with ONLY valid JSON matching the schema."
    parsed = generate_structured(prompt, TocDetectorAnswer, system_prompt=system_prompt)
    return parsed.toc_detected or "no"


def _LEGACY_check_if_toc_extraction_is_complete(content, toc, model=None):
    """LEGACY: LLM check for TOC completeness. Not called by active pipeline."""
    prompt = (
        "You are given a partial document and a table of contents. "
        "Check if the table of contents is complete.\n\n"
        "Reply: {\"thinking\": ..., \"completed\": \"yes or no\"}\n\n"
        f"Document:\n{content}\nTable of contents:\n{toc}"
    )
    parsed = generate_structured(prompt, ThinkingCompleted)
    return parsed.completed or "no"


def _LEGACY_check_if_toc_transformation_is_complete(content, toc, model=None):
    """LEGACY: LLM check for TOC transformation completeness. Not called by active pipeline."""
    prompt = (
        "You are given a raw table of contents and a cleaned table of contents. "
        "Check if the cleaned version is complete.\n\n"
        "Reply: {\"thinking\": ..., \"completed\": \"yes or no\"}\n\n"
        f"Raw TOC:\n{content}\nCleaned TOC:\n{toc}"
    )
    for attempt in range(3):
        try:
            parsed = generate_structured(prompt, ThinkingCompleted)
            return parsed.completed or "no"
        except Exception as exc:
            if attempt == 2:
                return "no"
            time.sleep(1)
    return "no"


def _LEGACY_extract_toc_content(content, model=None):
    """LEGACY: raw TOC text extraction with continuation loop. Not called by active pipeline."""
    prompt = (
        f"Extract the full table of contents from the given text, replace ... with :\n\n"
        f"Given text: {content}\n\nReturn only the TOC content."
    )
    response, finish_reason = ollama_text_completion(model=model, prompt=prompt, return_finish_reason=True)
    if_complete = _LEGACY_check_if_toc_transformation_is_complete(content, response, model)
    if if_complete == "yes" and finish_reason == "finished":
        return response
    chat_history = [{"role": "user", "content": prompt}, {"role": "assistant", "content": response}]
    cont_prompt = "please continue the generation of table of contents, directly output the remaining part"
    new_response, finish_reason = ollama_text_completion(model=model, prompt=cont_prompt,
                                                          chat_history=chat_history, return_finish_reason=True)
    response = response + new_response
    for attempt in range(5):
        if_complete = _LEGACY_check_if_toc_transformation_is_complete(content, response, model)
        if if_complete == "yes" and finish_reason == "finished":
            return response
        chat_history = [{"role": "user", "content": cont_prompt}, {"role": "assistant", "content": response}]
        new_response, finish_reason = ollama_text_completion(model=model, prompt=cont_prompt,
                                                              chat_history=chat_history, return_finish_reason=True)
        response = response + new_response
    raise Exception("LEGACY: Failed to complete TOC extraction after maximum retries")


def _LEGACY_detect_page_index(toc_content, model=None):
    """LEGACY: LLM detection of page numbers in TOC. Not called by active pipeline."""
    prompt = (
        f"Detect if there are page numbers within the table of contents.\n\n"
        f"Given text: {toc_content}\n\n"
        "Reply: {\"thinking\": ..., \"page_index_given_in_toc\": \"yes or no\"}"
    )
    parsed = generate_structured(prompt, PageIndexInTocAnswer)
    return parsed.page_index_given_in_toc


def _LEGACY_toc_extractor(page_list, toc_page_list, model):
    """LEGACY: raw text TOC extractor. Not called by active pipeline."""
    def transform_dots_to_colon(text):
        text = re.sub(r"\.{5,}", ": ", text)
        text = re.sub(r"(?:\. ){5,}\.?", ": ", text)
        return text

    toc_content = ""
    for page_index in toc_page_list:
        toc_content += page_list[page_index][0]
    toc_content = transform_dots_to_colon(toc_content)
    has_page_index = _LEGACY_detect_page_index(toc_content, model=model)
    return {"toc_content": toc_content, "page_index_given_in_toc": has_page_index}


async def _LEGACY_check_title_appearance(item, page_list, start_index=1, model=None):
    """LEGACY: LLM title-in-page check. Not called by active pipeline."""
    title = item["title"]
    if "physical_index" not in item or item["physical_index"] is None:
        return {"list_index": item.get("list_index"), "answer": "no", "title": title, "page_number": None}
    page_number = item["physical_index"]
    page_text = page_list[page_number - start_index][0]
    prompt = (
        f"Check if the section '{title}' appears or starts in the following page text.\n\n"
        f"Page text:\n{page_text}\n\n"
        "Reply: {\"thinking\": ..., \"answer\": \"yes or no\"}"
    )
    parsed = await asyncio.to_thread(generate_structured, prompt, TitleAppearanceAnswer)
    return {"list_index": item["list_index"], "answer": parsed.answer or "no",
            "title": title, "page_number": page_number}


async def _LEGACY_check_title_appearance_in_start(title, page_text, model=None, logger=None):
    """LEGACY: LLM appear-at-start check. Not called by active pipeline."""
    prompt = (
        f"Check if section '{title}' starts at the very beginning of the page text.\n\n"
        f"Page text:\n{page_text}\n\n"
        "Reply: {\"thinking\": ..., \"start_begin\": \"yes or no\"}"
    )
    parsed = await asyncio.to_thread(generate_structured, prompt, TitleStartAnswer)
    return parsed.start_begin or "no"


async def _LEGACY_single_toc_item_index_fixer(section_title, content, model=None):
    """LEGACY: LLM physical index finder for a single section. Not called by active pipeline."""
    prompt = (
        f"Find the physical index of the start page of section '{section_title}'.\n\n"
        f"Document pages:\n{content}\n\n"
        "Reply: {\"thinking\": ..., \"physical_index\": \"<physical_index_X>\"}"
    )
    parsed = await asyncio.to_thread(generate_structured, prompt, SectionPhysicalIndexAnswer)
    return convert_physical_index_to_int(parsed.physical_index)


async def _LEGACY_verify_toc(page_list, list_result, start_index=1, N=None, model=None):
    """LEGACY: probabilistic TOC verification via LLM. Not called by active pipeline."""
    import random
    last_physical_index = None
    for item in reversed(list_result):
        if item.get("physical_index") is not None:
            last_physical_index = item["physical_index"]
            break
    if last_physical_index is None or last_physical_index < len(page_list) / 2:
        return 0, []
    if N is None:
        sample_indices = range(len(list_result))
    else:
        N = min(N, len(list_result))
        sample_indices = random.sample(range(len(list_result)), N)
    indexed_sample = []
    for idx in sample_indices:
        item = list_result[idx]
        if item.get("physical_index") is not None:
            it = item.copy()
            it["list_index"] = idx
            indexed_sample.append(it)
    tasks = [_LEGACY_check_title_appearance(it, page_list, start_index, model) for it in indexed_sample]
    results = await asyncio.gather(*tasks)
    correct = sum(1 for r in results if r["answer"] == "yes")
    incorrect = [r for r in results if r["answer"] != "yes"]
    accuracy = correct / len(results) if results else 0
    return accuracy, incorrect


async def _LEGACY_fix_incorrect_toc(toc_with_page_number, page_list, incorrect_results,
                                     start_index=1, model=None, logger=None):
    """LEGACY: LLM-based TOC repair. Not called by active pipeline."""
    incorrect_indices = {r["list_index"] for r in incorrect_results}
    end_index = len(page_list) + start_index - 1

    async def process_item(incorrect_item):
        list_index = incorrect_item["list_index"]
        prev_correct = start_index - 1
        for i in range(list_index - 1, -1, -1):
            if i not in incorrect_indices:
                idx = toc_with_page_number[i].get("physical_index")
                if idx is not None:
                    prev_correct = idx
                    break
        next_correct = end_index
        for i in range(list_index + 1, len(toc_with_page_number)):
            if i not in incorrect_indices:
                idx = toc_with_page_number[i].get("physical_index")
                if idx is not None:
                    next_correct = idx
                    break
        page_contents = []
        for page_index in range(prev_correct, next_correct + 1):
            li = page_index - start_index
            if 0 <= li < len(page_list):
                page_contents.append(
                    f"<physical_index_{page_index}>\n{page_list[li][0]}\n<physical_index_{page_index}>\n\n"
                )
        content_range = "".join(page_contents)
        physical_index_int = await _LEGACY_single_toc_item_index_fixer(incorrect_item["title"], content_range, model)
        check_item = incorrect_item.copy()
        check_item["physical_index"] = physical_index_int
        check_result = await _LEGACY_check_title_appearance(check_item, page_list, start_index, model)
        return {
            "list_index": list_index,
            "title": incorrect_item["title"],
            "physical_index": physical_index_int,
            "is_valid": check_result["answer"] == "yes",
        }

    tasks = [process_item(item) for item in incorrect_results]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    results = [r for r in results if not isinstance(r, Exception)]

    invalid = []
    for result in results:
        li = result["list_index"]
        if result["is_valid"] and 0 <= li < len(toc_with_page_number):
            toc_with_page_number[li]["physical_index"] = result["physical_index"]
        else:
            invalid.append({"list_index": li, "title": result["title"],
                             "physical_index": result["physical_index"]})
    return toc_with_page_number, invalid


async def _LEGACY_fix_incorrect_toc_with_retries(toc_with_page_number, page_list, incorrect_results,
                                                  start_index=1, max_attempts=3, model=None, logger=None):
    """LEGACY: retry loop for LLM TOC repair. Not called by active pipeline."""
    current_toc = toc_with_page_number
    current_incorrect = incorrect_results
    for attempt in range(max_attempts):
        if not current_incorrect:
            break
        current_toc, current_incorrect = await _LEGACY_fix_incorrect_toc(
            current_toc, page_list, current_incorrect, start_index, model, logger
        )
    return current_toc, current_incorrect


def _LEGACY_process_toc_with_page_numbers(toc_content, toc_page_list, page_list,
                                           toc_check_page_num=None, model=None, logger=None):
    """LEGACY: original process_toc_with_page_numbers path. Not called by active pipeline."""
    toc_with_page_number = toc_transformer(toc_content, model)
    toc_no_page_number = remove_page_number(copy.deepcopy(toc_with_page_number))
    start_page_index = toc_page_list[-1] + 1
    main_content = ""
    for page_index in range(start_page_index,
                             min(start_page_index + (toc_check_page_num or 20), len(page_list))):
        main_content += (f"<physical_index_{page_index + 1}>\n"
                         f"{page_list[page_index][0]}\n"
                         f"<physical_index_{page_index + 1}>\n\n")
    toc_with_physical_index = toc_index_extractor(toc_no_page_number, main_content, model)
    toc_with_physical_index = convert_physical_index_to_int(toc_with_physical_index)
    matching_pairs = extract_matching_page_pairs(toc_with_page_number, toc_with_physical_index, start_page_index)
    offset = calculate_page_offset(matching_pairs)
    toc_with_page_number = add_page_offset_to_toc_json(toc_with_page_number, offset)
    toc_with_page_number = deterministic_repair_missing_pages(
        toc_with_page_number, page_list, start_index=1, logger=logger
    )
    return toc_with_page_number
