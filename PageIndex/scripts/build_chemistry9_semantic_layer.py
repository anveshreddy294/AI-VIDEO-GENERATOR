#!/usr/bin/env python3
"""Build concept_graph.json and pedagogical_metadata.json from structure.json.

Delegates to pageindex.concept_graph (single source of truth).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PAGEINDEX_ROOT = Path(__file__).resolve().parent.parent
if str(_PAGEINDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(_PAGEINDEX_ROOT))

from pageindex.concept_graph import write_concept_graph  # noqa: E402
from pageindex.results_loader import DocumentArtifacts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build semantic layer artifacts from structure.json"
    )
    parser.add_argument("--doc", default="Chemistry.pdf", help="Document results folder name")
    parser.add_argument(
        "--results-root",
        type=Path,
        default=_PAGEINDEX_ROOT / "results",
        help="PageIndex results root directory",
    )
    parser.add_argument(
        "--quality",
        action="store_true",
        help="Reserved for optional SLM polish (currently deterministic only)",
    )
    args = parser.parse_args()

    results_dir = args.results_root / args.doc
    arts = DocumentArtifacts(results_dir)
    if not arts.exists():
        print(f"ERROR: structure.json not found at {results_dir}", file=sys.stderr)
        return 1

    if args.quality:
        print(
            "[semantic_layer] --quality requested; SLM polish not implemented — "
            "deterministic output written.",
            file=sys.stderr,
        )

    graph = write_concept_graph(results_dir)
    print(
        f"Wrote {results_dir / 'concept_graph.json'} "
        f"(edges={graph['stats']['edge_count']})"
    )
    print(f"Wrote {results_dir / 'pedagogical_metadata.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
