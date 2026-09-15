"""JSON repair helpers for malformed SLM output."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError


def _strip_md_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _balance_braces(text: str) -> str:
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        return text
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    end = start
    for i, ch in enumerate(text[start:], start):
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return text[start:end]


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _extract_first_json_object(raw: str) -> str:
    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(raw[start:], start):
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return raw[start : i + 1]
    return raw


def _candidates(raw: str) -> Iterator[str]:
    yield raw
    s = _strip_md_fences(raw)
    yield s
    yield _balance_braces(s)
    yield _strip_trailing_commas(_balance_braces(s))
    yield _extract_first_json_object(s)


def repair_and_parse(raw: str, schema: Type[BaseModel]) -> Tuple[BaseModel, str]:
    """Try plain json.loads; then strip fences, balance braces, validate schema."""
    last_err: Optional[Exception] = None
    seen: set = set()
    for candidate in _candidates(raw):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
            validated = schema.model_validate(parsed)
            return validated, candidate
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            continue
    raise ValueError(f"json_repair: no candidate parsed: {last_err}")


def minify_for_retry(parsed: Dict[str, Any]) -> str:
    return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)


def regex_salvage_toc(raw: str) -> List[dict]:
    """Parse TOC-like text from malformed SLM output via deterministic parser."""
    from .deterministic_toc import parse_toc

    entries, confidence = parse_toc(raw)
    if confidence < 0.3 or len(entries) < 3:
        return []
    return entries
