#!/usr/bin/env python3
"""Thin CLI wrapper around pageindex.concept_graph — regenerate graphs for one or all docs."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pageindex.concept_graph import _cli_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_cli_main())
