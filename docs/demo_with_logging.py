#!/usr/bin/env python3
"""
Section 7.3 — Demo: PageIndex with Gemini (LiteLLM) and verbose logging

This script demonstrates the full pipeline with:
  - Loading secrets from a `.env` file via `python-dotenv` (GEMINI_API_KEY)
  - Default model `gemini/gemini-2.5-flash-lite` routed through LiteLLM
  - Tree structure printed after indexing (see `PageIndexClient` / `page_index_main` / `md_to_tree`)
  - Retrieval-path visibility when calling `get_document_structure` / `get_page_content`
    (see `[retrieve]` lines in `pageindex/retrieve.py`)

Prerequisites:
  - `pip install -r requirements.txt`
  - A `.env` file in this directory (or parents, depending on cwd) containing:
        GEMINI_API_KEY=your_key_here

Usage:
  python demo_with_logging.py path/to/document.pdf
  python demo_with_logging.py path/to/document.md
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load `.env` early so LiteLLM and PageIndex see GEMINI_API_KEY
load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pageindex import PageIndexClient  # noqa: E402
import pageindex.utils as utils  # noqa: E402


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY in your environment or in a `.env` file next to this script.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    file_path = Path(sys.argv[1]).expanduser().resolve()
    if not file_path.is_file():
        print(f"File not found: {file_path}")
        sys.exit(1)

    workspace = _REPO_ROOT / "examples" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    # PageIndexClient: Gemini key + default model (LiteLLM)
    client = PageIndexClient(
        api_key=api_key,
        model="gemini/gemini-2.5-flash-lite",
        workspace=str(workspace),
    )

    print("=" * 72)
    print("Indexing (tree + summaries are logged by the library)")
    print("=" * 72)
    doc_id = client.index(str(file_path))

    print("\n" + "=" * 72)
    print("Document metadata (get_document)")
    print("=" * 72)
    print(client.get_document(doc_id))

    print("\n" + "=" * 72)
    print("Retrieval: structure (triggers [retrieve] logging)")
    print("=" * 72)
    struct_json = client.get_document_structure(doc_id)
    print(struct_json[:1200] + ("..." if len(struct_json) > 1200 else ""))

    print("\n" + "=" * 72)
    print("Retrieval: first pages/lines (triggers [retrieve] logging)")
    print("=" * 72)
    print(client.get_page_content(doc_id, "1-2"))

    print("\n" + "=" * 72)
    print("Pretty tree (utils.print_tree on parsed structure)")
    print("=" * 72)
    tree = json.loads(client.get_document_structure(doc_id))
    utils.print_tree(tree)


if __name__ == "__main__":
    main()
