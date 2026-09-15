#!/usr/bin/env python3
"""Smoke-test tree build from cached extracted_pages.json (no PDF/Ollama required)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pageindex.hierarchy_repair import inject_subsections_into_tree, repair_hierarchy
from pageindex.page_index import (
    _min_chapter_content_page,
    _validation_kwargs,
    check_toc,
    check_title_appearance_in_start_concurrent,
    meta_processor,
    post_processing,
    semantic_dedupe,
)
from pageindex.utils import (
    ConfigLoader,
    add_preface_if_needed,
    assign_parent_ids,
    write_node_id,
)
from pageindex.validators import validate_semantic_tree


async def main(doc: str = "Chemistry_9.pdf") -> int:
    results_dir = _ROOT / "results" / doc
    pages_path = results_dir / "extracted_pages.json"
    if not pages_path.is_file():
        print(f"MISSING {pages_path}", file=sys.stderr)
        return 1

    with open(pages_path, encoding="utf-8") as f:
        raw_pages = json.load(f)
    page_list = [(p.get("text") or "", p.get("token_count", 0)) for p in raw_pages]

    opt = ConfigLoader().load({"resume": True, "no_summaries": True})
    check = check_toc(page_list, opt)
    toc_items = await meta_processor(
        page_list,
        mode=check["mode"],
        toc_content=check.get("toc_content"),
        toc_page_list=check.get("toc_page_list", []),
        detection=check.get("detection"),
        opt=opt,
    )
    toc_items = add_preface_if_needed(toc_items)
    toc_items = await check_title_appearance_in_start_concurrent(toc_items, page_list)
    valid = [i for i in toc_items if i.get("physical_index") is not None]
    valid = repair_hierarchy(valid)
    tree = post_processing(valid, len(page_list), page_list=page_list, opt=opt)
    tree = semantic_dedupe(tree)

    min_content = _min_chapter_content_page(tree)
    added = inject_subsections_into_tree(tree, page_list, min_content_page=min_content)
    write_node_id(tree)
    assign_parent_ids(tree)

    result = {"doc_name": doc, "structure": tree}
    val = validate_semantic_tree(result, **_validation_kwargs(opt))

    def count_nodes(nodes):
        n = 0
        for node in nodes:
            n += 1
            n += count_nodes(node.get("nodes") or node.get("children") or [])
        return n

    node_count = count_nodes(tree)
    chapters = [n for n in tree if n.get("content_type") == "chapter"]
    ch_with_children = sum(1 for c in chapters if c.get("nodes"))

    print(f"children_added={added} node_count={node_count}")
    print(f"chapters={len(chapters)} chapters_with_children={ch_with_children}")
    print(f"validation passed={val['passed']} failures={val.get('failures')}")

    out = results_dir / "structure.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(results_dir / "semantic_validation.json", "w", encoding="utf-8") as f:
        json.dump(val, f, indent=2)
    print(f"Wrote {out}")

    ok = (
        val["checks"].get("has_hierarchy_depth")
        and val["checks"].get("chapters_have_children")
        and node_count >= 25
    )
    return 0 if ok else 1


if __name__ == "__main__":
    doc = sys.argv[1] if len(sys.argv) > 1 else "Chemistry_9.pdf"
    raise SystemExit(asyncio.run(main(doc)))
