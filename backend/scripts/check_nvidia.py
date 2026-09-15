#!/usr/bin/env python3
"""Quick NVIDIA NIM auth + chat smoke test."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from modules.config import (
    NVIDIA_API_KEY,
    NVIDIA_CODE_MODEL,
    NVIDIA_PLANNER_MODEL,
    NVIDIA_VISUAL_MODEL,
)

CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def check(model: str) -> None:
    r = requests.post(
        CHAT_URL,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 8,
        },
        timeout=30,
    )
    print(f"{model:60s} -> {r.status_code}", r.text[:120].replace("\n", " "))


def main() -> None:
    if not NVIDIA_API_KEY:
        print("NVIDIA_API_KEY missing in .env")
        sys.exit(1)
    print(f"Using key: {NVIDIA_API_KEY[:12]}...{NVIDIA_API_KEY[-4:]}")
    for m in {NVIDIA_PLANNER_MODEL, NVIDIA_VISUAL_MODEL, NVIDIA_CODE_MODEL}:
        check(m)


if __name__ == "__main__":
    main()
