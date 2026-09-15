#!/usr/bin/env python3
"""Apply extractive summaries + deterministic metadata to an existing structure.json."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pageindex.utils import (
    ConfigLoader,
    add_node_text,
    children_to_nodes,
    generate_summaries_for_structure,
    nodes_to_children_export,
    remove_structure_text,
    structure_to_list,
)
from pageindex.validators import validate_semantic_tree
from pageindex.page_index import _validation_kwargs


async def main(doc: str = "Chemistry_9.pdf") -> int:
    results_dir = _ROOT / "results" / doc
    structure_path = results_dir / "structure.json"
    pages_path = results_dir / "extracted_pages.json"
    if not structure_path.is_file() or not pages_path.is_file():
        print("Missing structure.json or extracted_pages.json", file=sys.stderr)
        return 1

    with open(structure_path, encoding="utf-8") as f:
        data = json.load(f)
    with open(pages_path, encoding="utf-8") as f:
        raw_pages = json.load(f)
    page_list = [(p.get("text") or "", p.get("token_count", 0)) for p in raw_pages]

    structure = data.get("structure") or []
    structure = children_to_nodes(structure)
    add_node_text(structure, page_list)
    opt = ConfigLoader().load({"no_summaries": False, "if_add_node_text": "yes"})
    await generate_summaries_for_structure(structure, opt=opt)
    remove_structure_text(structure)

    export = nodes_to_children_export(structure)
    data["structure"] = export
    result = {"doc_name": data.get("doc_name", doc), "structure": export}
    val = validate_semantic_tree(result, **_validation_kwargs(opt))

    with open(structure_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    summaries = [
        {
            "node_id": n.get("node_id"),
            "title": n.get("title"),
            "summary": n.get("summary"),
            "keywords": n.get("keywords"),
            "semantic_tags": n.get("semantic_tags"),
            "learning_objectives": n.get("learning_objectives"),
        }
        for n in structure_to_list(export)
        if n.get("summary")
    ]
    with open(results_dir / "summaries.json", "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)
    with open(results_dir / "semantic_validation.json", "w", encoding="utf-8") as f:
        json.dump(val, f, indent=2)

    print(f"summaries={len(summaries)} validation passed={val['passed']} failures={val.get('failures')}")
    return 0 if val["passed"] else 1


if __name__ == "__main__":
    doc = sys.argv[1] if len(sys.argv) > 1 else "Chemistry_9.pdf"
    raise SystemExit(asyncio.run(main(doc)))
