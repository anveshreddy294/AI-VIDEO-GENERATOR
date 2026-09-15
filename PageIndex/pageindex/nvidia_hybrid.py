"""Standalone NVIDIA NIM client for PageIndex hybrid local → cloud fallback."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Type

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Non-retryable HTTP statuses — bad API key, forbidden, etc.
_AUTH_ERROR_STATUSES = frozenset({401, 403})

_primary_model: str = "meta/llama-3.3-70b-instruct"
_fallback_model: str = "nvidia/nemotron-3-nano-30b-a3b"
_temperature: float = 0.1
_max_tokens: int = 4096
_timeout_seconds: int = 300
_use_guided_json: bool = True
_hybrid_enabled: bool = False
_max_retries: int = 3

_last_escalation_attempted: bool = False
_last_auth_failure: bool = False


class NvidiaAuthError(RuntimeError):
    """Raised when NVIDIA API key is invalid or unauthorized."""


class NvidiaUnavailableError(RuntimeError):
    """Raised when NVIDIA NIM cannot serve the request after retries."""


def configure_nvidia(opt: Any) -> None:
    """Cache NVIDIA settings from ConfigLoader opt namespace."""
    global _primary_model, _fallback_model, _temperature, _max_tokens
    global _timeout_seconds, _use_guided_json, _hybrid_enabled

    nvidia_cfg = getattr(opt, "nvidia", None) or {}
    if isinstance(nvidia_cfg, dict):
        _primary_model = str(nvidia_cfg.get("primary_model") or _primary_model)
        _fallback_model = str(nvidia_cfg.get("fallback_model") or _fallback_model)
        _temperature = float(nvidia_cfg.get("temperature", _temperature))
        _max_tokens = int(nvidia_cfg.get("max_tokens", _max_tokens))
        _timeout_seconds = int(nvidia_cfg.get("timeout_seconds", _timeout_seconds))
        _use_guided_json = bool(nvidia_cfg.get("use_guided_json", _use_guided_json))

    hybrid_flag = getattr(opt, "hybrid_nvidia_enabled", None)
    if hybrid_flag is not None:
        _hybrid_enabled = str(hybrid_flag).lower() in ("yes", "true", "1")
    else:
        _hybrid_enabled = bool(getattr(opt, "max_quality", False))

    if nvidia_available():
        logger.info(
            "nvidia_hybrid configured: primary=%r fallback=%r guided_json=%s",
            _primary_model,
            _fallback_model,
            _use_guided_json,
        )
    elif _hybrid_enabled:
        logger.warning(
            "nvidia_hybrid enabled but NVIDIA_API_KEY not set — will fallback to local qwen2.5:3b"
        )


def nvidia_enabled() -> bool:
    return _hybrid_enabled


def nvidia_available() -> bool:
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key or key.lower() in ("your-key", "your_key", "changeme", "placeholder"):
        return False
    return True


def nvidia_auth_failed_recently() -> bool:
    return _last_auth_failure


def nvidia_escalation_was_attempted() -> bool:
    """Return whether the last generate_structured call attempted NVIDIA escalation."""
    return _last_escalation_attempted


def reset_nvidia_escalation_flag() -> None:
    global _last_escalation_attempted, _last_auth_failure
    _last_escalation_attempted = False
    _last_auth_failure = False


def _build_messages(
    prompt: str,
    system_prompt: Optional[str],
    schema: Type[BaseModel],
) -> List[Dict[str, str]]:
    schema_block = json.dumps(schema.model_json_schema(), indent=2)
    sys_parts = [
        "You must respond with ONLY valid JSON conforming exactly to this schema. "
        "No explanation. No markdown. No preamble.",
        f"JSON Schema:\n{schema_block}",
    ]
    if system_prompt:
        sys_parts.insert(0, system_prompt.strip())
    return [
        {"role": "system", "content": "\n\n".join(sys_parts)},
        {"role": "user", "content": prompt},
    ]


def _post_chat(
    model: str,
    messages: List[Dict[str, str]],
    schema: Type[BaseModel],
) -> str:
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": _temperature,
        "max_tokens": _max_tokens,
        "stream": False,
    }
    if _use_guided_json:
        payload["guided_json"] = schema.model_json_schema()

    response = requests.post(
        NIM_BASE_URL,
        headers=headers,
        json=payload,
        timeout=_timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return (content or "").strip()


def nvidia_generate_raw(
    prompt: str,
    system_prompt: Optional[str],
    schema: Type[BaseModel],
    stage: Optional[str] = None,
) -> str:
    """Call NVIDIA NIM with guided_json; retry on transient errors, fail fast on 401/403."""
    global _last_escalation_attempted, _last_auth_failure
    _last_escalation_attempted = True

    if not nvidia_available():
        raise RuntimeError(
            "NVIDIA_API_KEY is not set or is a placeholder — skipping NVIDIA, use local Ollama"
        )

    messages = _build_messages(prompt, system_prompt, schema)
    models = [_primary_model, _fallback_model]
    last_exc: Optional[Exception] = None

    for model in models:
        for attempt in range(_max_retries):
            try:
                print(
                    f"[PageIndex] nvidia_escalation: stage={stage} model={model!r} "
                    f"attempt={attempt + 1}/{_max_retries}",
                    flush=True,
                )
                logger.info(
                    "nvidia_escalation stage=%s model=%r attempt=%s",
                    stage,
                    model,
                    attempt + 1,
                )
                t0 = time.perf_counter()
                content = _post_chat(model, messages, schema)
                elapsed = time.perf_counter() - t0
                print(
                    f"[PageIndex] nvidia_escalation_success: stage={stage} "
                    f"model={model!r} response_chars={len(content)} elapsed_s={elapsed:.1f}",
                    flush=True,
                )
                return content
            except requests.HTTPError as exc:
                last_exc = exc
                status = exc.response.status_code if exc.response is not None else 0
                if status in _AUTH_ERROR_STATUSES:
                    _last_auth_failure = True
                    msg = (
                        f"NVIDIA NIM auth failed ({status}) for stage={stage}. "
                        "Check NVIDIA_API_KEY — falling back to local qwen2.5:3b."
                    )
                    logger.error(msg)
                    print(f"[PageIndex] nvidia_auth_failed: {msg}", flush=True)
                    raise NvidiaAuthError(msg) from exc
                logger.warning(
                    "NVIDIA NIM attempt %d failed (%s) model=%r: %s",
                    attempt + 1,
                    status,
                    model,
                    exc,
                )
                if attempt < _max_retries - 1:
                    backoff = 15 if status in (429, 502, 503) else 2**attempt
                    time.sleep(backoff)
            except requests.Timeout as exc:
                last_exc = exc
                logger.warning(
                    "NVIDIA NIM timeout attempt %d model=%r stage=%s",
                    attempt + 1,
                    model,
                    stage,
                )
                if attempt < _max_retries - 1:
                    time.sleep(2**attempt)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "NVIDIA NIM attempt %d failed model=%r: %s",
                    attempt + 1,
                    model,
                    exc,
                )
                if attempt < _max_retries - 1:
                    time.sleep(2**attempt)

    msg = f"NVIDIA NIM escalation failed for stage={stage}: {last_exc}"
    logger.warning("%s — falling back to local qwen2.5:3b", msg)
    print(f"[PageIndex] nvidia_unavailable: {msg}", flush=True)
    raise NvidiaUnavailableError(msg) from last_exc
