from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

import ollama
from ollama import Client, ResponseError

logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "gemini/gemini-2.0-flash")
TOKEN_COUNT_MODEL: Optional[str] = None
MAX_PROMPT_TOKENS = int(os.environ.get("MAX_PROMPT_TOKENS", "3500"))
MAX_CONTEXT_TOKENS = int(os.environ.get("MAX_CONTEXT_TOKENS", "2048"))
INFERENCE_TIMEOUT_SECONDS = int(os.environ.get("INFERENCE_TIMEOUT_SECONDS", "180"))
MAX_RETRIES_DEFAULT = 2
MAX_RETRIES = MAX_RETRIES_DEFAULT
RESPONSE_TOKEN_RESERVE = 512
PRE_TRUNCATE_AGGRESSIVE = False
ENABLE_GEMINI_FALLBACK = os.environ.get("PAGEINDEX_ENABLE_GEMINI_FALLBACK", "1") != "0"

# Default per-stage Ollama generation options.
# Callers can override by passing inference_options={} to generate_structured.
_DEFAULT_STAGE_OPTIONS: Dict[str, Any] = {
    "temperature": 0.1,
    "top_p": 0.9,
    "keep_alive": "10m",
}
# TOC detection is small JSON → very short generation, low temp
TOC_GENERATION_OPTIONS: Dict[str, Any] = {
    "num_predict": 256,
    "temperature": 0,
    "top_p": 0.1,
    "keep_alive": "10m",
}

_CURRENT_STAGE: Optional[str] = None

_client: Optional[Client] = None
_model_ready: bool = False
_resolved_models: Dict[str, str] = {}

T = TypeVar("T", bound=BaseModel)


class TokenBudgetExceeded(Exception):
    def __init__(self, estimated_tokens: int, limit: int, reason: str = "prompt_too_large"):
        self.estimated_tokens = estimated_tokens
        self.limit = limit
        self.reason = reason
        super().__init__(f"Estimated {estimated_tokens} tokens exceeds limit {limit} ({reason})")


class PipelineStageFailure(Exception):
    def __init__(self, message: str, last_error: Optional[BaseException] = None):
        super().__init__(message)
        self.last_error = last_error


@dataclass
class RuntimeSummary:
    total_inference_calls: int = 0
    local_calls: int = 0
    fallback_calls: int = 0
    total_tokens_processed: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    pipeline_started_at: float = field(default_factory=time.time)

    def record_call(self, *, local: bool, tokens: int, latency_ms: float) -> None:
        self.total_inference_calls += 1
        if local:
            self.local_calls += 1
        else:
            self.fallback_calls += 1
        self.total_tokens_processed += tokens
        self.latencies_ms.append(latency_ms)

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    @property
    def total_runtime_seconds(self) -> float:
        return time.time() - self.pipeline_started_at


_runtime_summary = RuntimeSummary()


def get_runtime_summary() -> RuntimeSummary:
    return _runtime_summary


def reset_runtime_summary() -> None:
    global _runtime_summary
    _runtime_summary = RuntimeSummary()


def _list_installed_ollama_models() -> List[str]:
    try:
        resp = _get_client().list()
        if hasattr(resp, "models"):
            return [m.model for m in resp.models if getattr(m, "model", None)]
        if isinstance(resp, dict):
            models = resp.get("models") or []
            names = []
            for m in models:
                if isinstance(m, dict):
                    names.append(m.get("name") or m.get("model") or "")
                else:
                    names.append(getattr(m, "model", None) or getattr(m, "name", "") or "")
            return [n for n in names if n]
        return []
    except Exception as exc:
        logger.warning("Could not list Ollama models: %s", exc)
        return []


def _model_is_available(name: str) -> bool:
    try:
        _get_client().show(name)
        return True
    except ResponseError:
        return False
    except Exception:
        return False


def _resolve_available_model(preferred: str, fail_fast: bool = False) -> str:
    """Pick preferred model if pulled; else best available fallback (or raise if fail_fast)."""
    preferred = _normalize_ollama_model(preferred)
    if _model_is_available(preferred):
        return preferred

    installed = _list_installed_ollama_models()
    if fail_fast:
        installed_list = ", ".join(installed) if installed else "(none)"
        raise RuntimeError(
            f"\n\nModel not found: {preferred!r}\n"
            f"Installed models: {installed_list}\n"
            f"Fix: ollama pull {preferred}\n"
        )

    if not installed:
        logger.warning(
            "Ollama model %r not found and no models installed.\n"
            "  ➜  ollama pull %s\n"
            "Continuing without a resolved model (will likely fail at inference).",
            preferred,
            preferred,
        )
        return preferred

    def _rank(name: str) -> tuple:
        n = name.lower()
        # Prefer qwen2.5:3b as local fallback — avoid heavy 7b/coder models.
        family = 9
        if "qwen2.5:3b" in n or "qwen2.5:3" in n:
            family = 0
        elif "qwen2.5" in n and "coder" not in n:
            family = 1
        elif "qwen2.5-coder" in n or "qwen2.5-coder" in n:
            family = 8
        elif "qwen" in n:
            family = 2
        elif "gemma3" in n:
            family = 3
        elif "gemma" in n:
            family = 4
        size_score = 2
        if ":1b" in n or ":2b" in n:
            size_score = 0
        elif ":3b" in n or ":4b" in n:
            size_score = 1
        elif ":8b" in n or ":9b" in n or ":e4b" in n:
            size_score = 3
        return (family, size_score, len(n))

    candidates = sorted(installed, key=_rank)
    chosen = candidates[0]
    logger.warning(
        "Ollama model %r not available; using installed fallback %r.\n"
        "  ➜  ollama pull %s   (to use the configured model)\n"
        "  ➜  Add --fail-on-missing-model to abort instead of falling back.",
        preferred,
        chosen,
        preferred,
    )
    return chosen


_stage_timeout_counts: Dict[str, int] = {}


def configure_from_opt(opt: Any) -> None:
    """Apply generation_model and limits from ConfigLoader opt namespace."""
    global OLLAMA_MODEL, FALLBACK_MODEL, TOKEN_COUNT_MODEL, MAX_PROMPT_TOKENS
    global MAX_CONTEXT_TOKENS, INFERENCE_TIMEOUT_SECONDS, MAX_RETRIES, ENABLE_GEMINI_FALLBACK
    global PRE_TRUNCATE_AGGRESSIVE, _model_ready, TOC_GENERATION_OPTIONS

    fail_fast = str(getattr(opt, "model_not_found_behavior", "warn")).lower() == "fail"
    gen = getattr(opt, "generation_model", None) or os.environ.get("OLLAMA_MODEL")
    ql = getattr(opt, "quality_level", "fast")
    max_quality = bool(getattr(opt, "max_quality", False))
    local_fb = getattr(opt, "local_fallback_model", None)
    if (max_quality or ql == "high") and local_fb:
        gen = local_fb
    elif (max_quality or ql == "high"):
        from .model_router import LOCAL_FALLBACK_MODEL
        gen = LOCAL_FALLBACK_MODEL
    if gen:
        preferred = _normalize_ollama_model(gen)
        OLLAMA_MODEL = _resolve_available_model(preferred, fail_fast=fail_fast)

    fb = getattr(opt, "fallback_model", None)
    if fb:
        FALLBACK_MODEL = fb

    TOKEN_COUNT_MODEL = getattr(opt, "token_count_model", None) or getattr(opt, "model", None)

    if getattr(opt, "max_prompt_tokens", None):
        MAX_PROMPT_TOKENS = int(opt.max_prompt_tokens)
    if getattr(opt, "max_context_tokens", None):
        MAX_CONTEXT_TOKENS = int(opt.max_context_tokens)
    if getattr(opt, "inference_timeout_seconds", None):
        INFERENCE_TIMEOUT_SECONDS = int(opt.inference_timeout_seconds)
    elif any(tag in OLLAMA_MODEL.lower() for tag in ("gemma4", "e4b", ":8b", ":9b")):
        INFERENCE_TIMEOUT_SECONDS = max(INFERENCE_TIMEOUT_SECONDS, 600)
    if getattr(opt, "max_retries", None) is not None:
        MAX_RETRIES = int(opt.max_retries)
    else:
        MAX_RETRIES = MAX_RETRIES_DEFAULT

    pre_agg = getattr(opt, "pre_truncate_aggressive", None)
    if pre_agg is not None:
        PRE_TRUNCATE_AGGRESSIVE = str(pre_agg).lower() in ("yes", "true", "1")

    toc_np = getattr(opt, "toc_num_predict", None)
    if toc_np is not None:
        TOC_GENERATION_OPTIONS["num_predict"] = int(toc_np)

    fb_flag = getattr(opt, "enable_gemini_fallback", None)
    if fb_flag is not None:
        ENABLE_GEMINI_FALLBACK = str(fb_flag).lower() in ("yes", "true", "1")

    from .model_router import (
        configure_stage_models,
        set_max_quality_mode,
        set_quality_mode,
        set_high_quality_mode,
    )
    from .quality_policy import configure_quality_level, reset_path_stats

    configure_quality_level(getattr(opt, "quality_level", "fast"))
    reset_path_stats()

    configure_stage_models(getattr(opt, "stage_models", None))

    ql = getattr(opt, "quality_level", "fast")
    max_quality = bool(getattr(opt, "max_quality", False))
    if ql == "high":
        set_high_quality_mode(enabled=True)
        set_quality_mode(enabled=True)
        set_max_quality_mode(
            enabled=True,
            nvidia_stages=list(getattr(opt, "nvidia_stages", None) or []),
            route_after_timeouts=int(getattr(opt, "nvidia_route_after_timeouts", 0) or 0),
            nvidia_first=bool(getattr(opt, "nvidia_first", True)),
        )
    elif max_quality:
        nvidia_stages = getattr(opt, "nvidia_stages", None)
        route_after = getattr(opt, "nvidia_route_after_timeouts", 0)
        set_max_quality_mode(
            enabled=True,
            nvidia_stages=list(nvidia_stages) if nvidia_stages else None,
            route_after_timeouts=int(route_after or 0),
            nvidia_first=bool(getattr(opt, "nvidia_first", True)),
        )
        quality_cfg = getattr(opt, "quality_mode", None)
        if isinstance(quality_cfg, dict):
            stage_overrides = {
                k: v for k, v in quality_cfg.items()
                if not k.startswith("inference_") and not k.startswith("max_")
            }
            set_quality_mode(enabled=True, quality_overrides=stage_overrides or None)
        else:
            set_quality_mode(enabled=True)
    else:
        set_max_quality_mode(enabled=False)
        set_high_quality_mode(enabled=False)

    from .nvidia_hybrid import configure_nvidia

    configure_nvidia(opt)

    global _stage_timeout_counts, _resolved_models
    _stage_timeout_counts = {}
    _resolved_models = {}
    _model_ready = False
    logger.info(
        "local_llm configured: model=%r max_prompt_tokens=%s max_context=%s timeout=%ss max_retries=%s",
        OLLAMA_MODEL,
        MAX_PROMPT_TOKENS,
        MAX_CONTEXT_TOKENS,
        INFERENCE_TIMEOUT_SECONDS,
        MAX_RETRIES,
    )


def _normalize_ollama_model(model_id: str) -> str:
    m = model_id.strip()
    if m.startswith("ollama/"):
        m = m[len("ollama/") :]
    return m


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = ollama.Client()
        logger.debug("Ollama Client created (singleton)")
    return _client


def _ensure_model_for(model_name: str) -> str:
    """Resolve and cache a single Ollama model id."""
    global _resolved_models
    preferred = _normalize_ollama_model(model_name)
    if preferred in _resolved_models:
        return _resolved_models[preferred]
    fail_fast = os.environ.get("PAGEINDEX_FAIL_ON_MISSING_MODEL", "0") == "1"
    resolved = _resolve_available_model(preferred, fail_fast=fail_fast)
    _resolved_models[preferred] = resolved
    if _model_is_available(resolved):
        logger.info("Ollama model %r ready", resolved)
    else:
        logger.warning(
            "Ollama model %r not ready — run: ollama pull %s", resolved, resolved
        )
    return resolved


def _ensure_model_once() -> None:
    global _model_ready, OLLAMA_MODEL
    if _model_ready:
        return
    OLLAMA_MODEL = _ensure_model_for(OLLAMA_MODEL)
    _model_ready = True


def _is_connection_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        k in msg
        for k in ("connection refused", "connect call failed", "failed to connect", "socket", "timeout", "timed out")
    )


def _default_system_tail(schema: Type[BaseModel]) -> str:
    schema_block = json.dumps(schema.model_json_schema(), indent=2)
    return (
        "You must respond with ONLY valid JSON conforming exactly to this schema. "
        "No explanation. No markdown. No preamble.\n\n"
        f"JSON Schema:\n{schema_block}"
    )


def estimate_prompt_tokens(
    prompt: str,
    system_prompt: Optional[str],
    schema: Type[BaseModel],
    *,
    token_count_model: Optional[str] = None,
) -> int:
    from .utils import count_tokens

    model = token_count_model or TOKEN_COUNT_MODEL
    sys_parts = []
    if system_prompt:
        sys_parts.append(system_prompt.strip())
    sys_parts.append(_default_system_tail(schema))
    full_system = "\n\n".join(sys_parts)
    return count_tokens(full_system, model) + count_tokens(prompt, model)


def assert_prompt_within_budget(
    prompt: str,
    system_prompt: Optional[str],
    schema: Type[BaseModel],
    *,
    limit: Optional[int] = None,
    token_count_model: Optional[str] = None,
    stage: Optional[str] = None,
) -> int:
    cap = limit if limit is not None else MAX_PROMPT_TOKENS
    estimated = estimate_prompt_tokens(prompt, system_prompt, schema, token_count_model=token_count_model)
    if estimated > cap:
        logger.warning(
            "truncation_prevented stage=%s estimated_tokens=%s limit=%s",
            stage or "unknown",
            estimated,
            cap,
        )
        raise TokenBudgetExceeded(estimated, cap, f"stage={stage or 'inference'}")
    logger.info(
        "estimated_tokens_per_batch=%s stage=%s truncation_prevented=false",
        estimated,
        stage or "inference",
    )
    return estimated


def _pre_tokenize_truncate(messages: List[dict], schema: Type[BaseModel]) -> tuple:
    from .utils import count_tokens

    full = "\n".join(m["content"] for m in messages)
    original_tokens = count_tokens(full, TOKEN_COUNT_MODEL)
    cap = MAX_CONTEXT_TOKENS - RESPONSE_TOKEN_RESERVE
    if PRE_TRUNCATE_AGGRESSIVE:
        cap = int(cap * 0.70)
    if original_tokens <= cap:
        logger.info(
            "pre_tokenize stage=%s original=%s cap=%s truncated=0",
            _CURRENT_STAGE or "inference",
            original_tokens,
            cap,
        )
        return messages, original_tokens, 0

    user_msg = messages[-1]["content"]
    ratio = cap / max(original_tokens, 1)
    keep_chars = int(len(user_msg) * ratio * 0.95)
    user_msg = user_msg[:keep_chars] + "\n...(truncated by pre-tokenizer)"
    messages[-1]["content"] = user_msg
    truncated_tokens = count_tokens("\n".join(m["content"] for m in messages), TOKEN_COUNT_MODEL)
    removed = original_tokens - truncated_tokens
    stage = _CURRENT_STAGE or "inference"
    logger.warning(
        "pre_tokenize stage=%s original=%s truncated_to=%s removed=%s",
        stage,
        original_tokens,
        truncated_tokens,
        removed,
    )
    try:
        from .telemetry import PipelineMetrics
        PipelineMetrics.record_truncation(stage, original_tokens, truncated_tokens)
    except Exception:
        pass
    return messages, original_tokens, removed


def _call_slm(
    prompt: str,
    system_prompt: Optional[str],
    schema: Type[BaseModel],
    *,
    timeout_seconds: Optional[int] = None,
    inference_options: Optional[Dict[str, Any]] = None,
) -> str:
    from .model_router import model_for_stage

    _ensure_model_once()
    stage = _CURRENT_STAGE or "inference"
    routed = model_for_stage(stage, OLLAMA_MODEL)
    active_model = _ensure_model_for(routed)
    client = _get_client()
    sys_parts = []
    if system_prompt:
        sys_parts.append(system_prompt.strip())
    sys_parts.append(_default_system_tail(schema))
    full_system = "\n\n".join(sys_parts)
    messages = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": prompt},
    ]
    messages, orig_tokens, removed_tokens = _pre_tokenize_truncate(messages, schema)
    timeout = timeout_seconds if timeout_seconds is not None else INFERENCE_TIMEOUT_SECONDS

    # Build Ollama options: start from defaults, merge stage options
    opts = {**_DEFAULT_STAGE_OPTIONS, "num_ctx": MAX_CONTEXT_TOKENS}
    if inference_options:
        opts.update(inference_options)

    user_chars = len(messages[-1]["content"])
    print(
        f"[PageIndex] inference_start: stage={stage} schema={schema.__name__} "
        f"prompt_chars={user_chars} orig_tokens={orig_tokens} removed={removed_tokens} "
        f"timeout={timeout}s num_predict={opts.get('num_predict', 'unlimited')}",
        flush=True,
    )
    logger.info(
        "inference_start stage=%s schema=%s prompt_chars=%s orig_tokens=%s timeout=%s",
        stage, schema.__name__, user_chars, orig_tokens, timeout,
    )

    def _do_chat() -> str:
        response = client.chat(
            model=active_model,
            messages=messages,
            format="json",
            stream=False,
            options=opts,
        )
        return response.message.content or ""

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_do_chat)
        try:
            content = future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            try:
                from .telemetry import PipelineMetrics
                PipelineMetrics.record_timeout(stage)
            except Exception:
                pass
            elapsed = time.perf_counter() - t0
            print(
                f"[PageIndex] inference_timeout: stage={stage} after={elapsed:.1f}s",
                flush=True,
            )
            raise TimeoutError(f"Ollama inference timed out after {timeout}s") from exc

    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(
        f"[PageIndex] inference_end: stage={stage} response_chars={len(content)} "
        f"elapsed_ms={elapsed_ms:.0f}",
        flush=True,
    )
    logger.info("inference_end stage=%s response_chars=%s elapsed_ms=%.0f",
                stage, len(content), elapsed_ms)
    return content


def _build_retry_prompt(
    original_prompt: str,
    raw_output: str,
    error_message: str,
    schema_json: Dict[str, Any],
) -> str:
    truncated = raw_output if len(raw_output) <= 2000 else raw_output[:2000] + "\n...(truncated)"
    schema_block = json.dumps(schema_json, indent=2)
    retry = (
        f"RETRY: your previous response failed validation.\n"
        f"Error: {error_message}\n"
        f"Bad output:\n{truncated}\n"
        f"Required schema:\n{schema_block}\n"
        "Return ONLY valid JSON. No explanation.\n\n"
    )
    return retry + original_prompt


def _call_gemini_fallback(
    prompt: str,
    system_prompt: Optional[str],
    schema: Type[BaseModel],
    fallback_model: str = "gemini/gemini-2.0-flash",
) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    schema_json = schema.model_json_schema()
    schema_text = json.dumps(schema_json, indent=2)
    user_blob = prompt
    if system_prompt:
        user_blob = f"System instructions:\n{system_prompt}\n\nTask:\n{prompt}"

    logger.info("fallback_activation: Gemini schema=%s model=%s", schema.__name__, fallback_model)

    try:
        import litellm

        messages = [
            {
                "role": "system",
                "content": (
                    "Respond with ONLY valid JSON. No markdown. No preamble. "
                    f"Conform to this JSON Schema:\n{schema_text}"
                ),
            },
            {"role": "user", "content": user_blob},
        ]
        out = litellm.completion(model=fallback_model, messages=messages, api_key=api_key)
        text = out.choices[0].message.content
        if not text:
            raise RuntimeError("Empty Gemini response (litellm)")
        logger.info("Gemini fallback succeeded via litellm response_len=%s", len(text))
        return text
    except ImportError:
        logger.info("litellm not available, trying google.genai")
    except Exception as exc:
        logger.warning("Gemini fallback via litellm failed: %s", exc)

    from google import genai
    from google.genai import types
    model_name = fallback_model.split("/")[-1]
    full = f"Respond with ONLY valid JSON. No markdown.\nJSON Schema:\n{schema_text}\n\n{user_blob}"
    with genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000)) as client:
        response = client.models.generate_content(model=model_name, contents=full,
            config=types.GenerateContentConfig(response_mime_type="application/json"))
    if not response.text:
        raise RuntimeError("Empty Gemini response")
    return response.text


def generate_structured(
    prompt: str,
    schema: Type[T],
    system_prompt: Optional[str] = None,
    max_retries: Optional[int] = None,
    fallback_enabled: bool = True,
    fallback_model: Optional[str] = None,
    *,
    stage: Optional[str] = None,
    batch_index: Optional[int] = None,
    node_id: Optional[str] = None,
    skip_budget_check: bool = False,
    allow_fallback_on_timeout: bool = True,
    inference_options: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[int] = None,
    fail_fast_json: bool = False,
) -> T:
    global _CURRENT_STAGE, _stage_timeout_counts
    if max_retries is None:
        max_retries = MAX_RETRIES
    fb_model = fallback_model or FALLBACK_MODEL
    original_prompt = prompt
    schema_json: Dict[str, Any] = schema.model_json_schema()
    current_prompt = prompt
    last_error: Optional[Exception] = None
    last_raw: Optional[str] = None

    ctx = []
    if stage:
        ctx.append(f"stage={stage}")
    if batch_index is not None:
        ctx.append(f"batch={batch_index}")
    if node_id:
        ctx.append(f"node={node_id}")
    ctx_str = " ".join(ctx)
    _CURRENT_STAGE = stage or "inference"
    from .model_router import (
        model_for_stage,
        is_max_quality,
        nvidia_stage_eligible,
        route_after_timeouts,
        nvidia_first_enabled,
        local_fallback_model,
    )
    from .nvidia_hybrid import (
        nvidia_available,
        nvidia_generate_raw,
        nvidia_auth_failed_recently,
        reset_nvidia_escalation_flag,
        NvidiaAuthError,
        NvidiaUnavailableError,
    )

    reset_nvidia_escalation_flag()

    _ensure_model_once()
    routed = model_for_stage(_CURRENT_STAGE, OLLAMA_MODEL)
    active_model = _ensure_model_for(routed)
    if is_max_quality():
        active_model = _ensure_model_for(
            _normalize_ollama_model(local_fallback_model())
        )

    def _complete_from_raw(raw: str, tok_est: int, t0: float, *, local: bool) -> T:
        from .json_repair import repair_and_parse
        print(f"[PageIndex] parse_start: stage={stage} batch={batch_index} raw_chars={len(raw)}", flush=True)
        validated, _ = repair_and_parse(raw, schema)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _runtime_summary.record_call(local=local, tokens=tok_est, latency_ms=elapsed_ms)
        try:
            from .telemetry import PipelineMetrics
            PipelineMetrics.record_inference(_CURRENT_STAGE, tok_est, elapsed_ms, True)
            PipelineMetrics.stage_end(_CURRENT_STAGE)
        except Exception:
            pass
        print(
            f"[PageIndex] parse_success: stage={stage} batch={batch_index} "
            f"inference_ms={elapsed_ms:.0f}",
            flush=True,
        )
        return validated

    # Quality modes: NVIDIA NIM first, then local qwen2.5:3b (never 7b).
    if (
        nvidia_first_enabled()
        and nvidia_stage_eligible(stage)
        and nvidia_available()
        and not nvidia_auth_failed_recently()
    ):
        try:
            tok_est = estimate_prompt_tokens(
                original_prompt, system_prompt, schema, token_count_model=TOKEN_COUNT_MODEL
            )
            print(
                f"[PageIndex] stage={stage} batch={batch_index} action=nvidia_first "
                f"est_tokens={tok_est}",
                flush=True,
            )
            t0 = time.perf_counter()
            raw = nvidia_generate_raw(
                original_prompt, system_prompt, schema, stage=stage
            )
            return _complete_from_raw(raw, tok_est, t0, local=False)
        except (NvidiaAuthError, NvidiaUnavailableError, RuntimeError) as nvidia_exc:
            print(
                f"[PageIndex] nvidia_fallback_to_local: stage={stage} "
                f"local_model={active_model!r} reason={nvidia_exc}",
                flush=True,
            )
            logger.warning(
                "NVIDIA unavailable for %s — falling back to local %r: %s",
                ctx_str,
                active_model,
                nvidia_exc,
            )
        except Exception as nvidia_exc:
            print(
                f"[PageIndex] nvidia_fallback_to_local: stage={stage} "
                f"local_model={active_model!r} reason={type(nvidia_exc).__name__}",
                flush=True,
            )
            logger.warning("NVIDIA failed for %s: %s", ctx_str, nvidia_exc)

    try:
        from .telemetry import PipelineMetrics
        PipelineMetrics.stage_begin(_CURRENT_STAGE)
    except Exception:
        pass

    if not skip_budget_check:
        try:
            tok_est = assert_prompt_within_budget(
                prompt, system_prompt, schema, token_count_model=TOKEN_COUNT_MODEL, stage=stage
            )
        except TokenBudgetExceeded:
            raise

    for attempt in range(max_retries):
        t0 = time.perf_counter()
        try:
            if not skip_budget_check:
                tok_est = assert_prompt_within_budget(
                    current_prompt, system_prompt, schema, token_count_model=TOKEN_COUNT_MODEL, stage=stage
                )
            else:
                tok_est = estimate_prompt_tokens(
                    current_prompt, system_prompt, schema, token_count_model=TOKEN_COUNT_MODEL
                )

            if stage:
                print(
                    f"[PageIndex] stage={stage} batch={batch_index} attempt={attempt + 1}/{max_retries} "
                    f"action=run est_tokens={tok_est} model={active_model!r}",
                    flush=True,
                )
            raw = _call_slm(
                current_prompt, system_prompt, schema,
                timeout_seconds=timeout_seconds,
                inference_options=inference_options,
            )
            last_raw = raw
            print(f"[PageIndex] parse_start: stage={stage} batch={batch_index} raw_chars={len(raw)}", flush=True)
            from .json_repair import repair_and_parse, minify_for_retry
            try:
                validated, repaired_json = repair_and_parse(raw, schema)
            except ValueError as parse_err:
                print(
                    f"[PageIndex] parse_failure: stage={stage} batch={batch_index} "
                    f"error={parse_err} raw_chars={len(raw)}",
                    flush=True,
                )
                raise
            elapsed_ms = (time.perf_counter() - t0) * 1000
            _runtime_summary.record_call(local=True, tokens=tok_est, latency_ms=elapsed_ms)
            try:
                from .telemetry import PipelineMetrics
                PipelineMetrics.record_inference(_CURRENT_STAGE, tok_est, elapsed_ms, True)
                PipelineMetrics.stage_end(_CURRENT_STAGE)
            except Exception:
                pass
            print(
                f"[PageIndex] parse_success: stage={stage} batch={batch_index} "
                f"inference_ms={elapsed_ms:.0f}",
                flush=True,
            )
            logger.info(
                "generate_structured: OK %s schema=%s attempt=%s/%s inference_ms=%.0f",
                ctx_str,
                schema.__name__,
                attempt + 1,
                max_retries,
                elapsed_ms,
            )
            return validated
        except TokenBudgetExceeded:
            raise
        except TimeoutError as e:
            last_error = e
            try:
                from .telemetry import PipelineMetrics
                PipelineMetrics.record_timeout(_CURRENT_STAGE)
            except Exception:
                pass

            # Legacy path: escalate to NVIDIA after local timeout when nvidia_first is off.
            if (
                not nvidia_first_enabled()
                and is_max_quality()
                and nvidia_stage_eligible(stage)
                and nvidia_available()
                and not nvidia_auth_failed_recently()
            ):
                stage_key = stage or "inference"
                _stage_timeout_counts[stage_key] = _stage_timeout_counts.get(stage_key, 0) + 1
                if _stage_timeout_counts[stage_key] >= max(1, route_after_timeouts()):
                    print(
                        f"[PageIndex] nvidia_escalation_trigger: stage={stage} "
                        f"local_timeouts={_stage_timeout_counts[stage_key]}",
                        flush=True,
                    )
                    try:
                        t0 = time.perf_counter()
                        tok_est = estimate_prompt_tokens(
                            original_prompt,
                            system_prompt,
                            schema,
                            token_count_model=TOKEN_COUNT_MODEL,
                        )
                        raw = nvidia_generate_raw(
                            original_prompt,
                            system_prompt,
                            schema,
                            stage=stage,
                        )
                        return _complete_from_raw(raw, tok_est, t0, local=False)
                    except Exception as nvidia_exc:
                        logger.warning(
                            "nvidia_escalation failed %s: %s — falling back to caller shrink",
                            ctx_str,
                            nvidia_exc,
                        )

            logger.warning(
                "retry_reason: timeout %s — propagating to caller for batch shrink",
                ctx_str,
            )
            raise
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_error = e
            logger.warning(
                "retry_reason: parse/validate %s attempt=%s/%s: %s",
                ctx_str,
                attempt + 1,
                max_retries,
                e,
            )
            if stage == "toc_detection" and last_raw:
                try:
                    from .json_repair import regex_salvage_toc
                    from .schemas import TOCEntry, TOCDetectionResult

                    salvaged = regex_salvage_toc(last_raw)
                    if len(salvaged) >= 3:
                        entries = [
                            TOCEntry(
                                structure=e.get("structure") or "",
                                title=e["title"],
                                page_number=e.get("page_number") or 0,
                            )
                            for e in salvaged
                        ]
                        print(
                            f"[PageIndex] regex_salvage_toc: stage={stage} entries={len(entries)}",
                            flush=True,
                        )
                        return TOCDetectionResult(toc_found=True, toc_entries=entries)
                except Exception:
                    pass

            if fail_fast_json:
                print(
                    f"[PageIndex] fail_fast_json: stage={stage} batch={batch_index} "
                    f"skipping batch after parse error",
                    flush=True,
                )
                break
        except ResponseError as e:
            last_error = e
            err_s = str(e).lower()
            if "not found" in err_s or "404" in err_s:
                logger.error(
                    "Ollama model %r not available. Run: ollama pull %s (%s)",
                    OLLAMA_MODEL,
                    OLLAMA_MODEL,
                    ctx_str,
                )
                break
            logger.warning("retry_reason: Ollama ResponseError %s: %s", ctx_str, e)
        except Exception as e:
            last_error = e
            if _is_connection_error(e):
                logger.error("generate_structured: Ollama unreachable (%s): %s", ctx_str, e)
                break
            logger.exception("generate_structured: unexpected error %s attempt=%s/%s", ctx_str, attempt + 1, max_retries)
            break

        if attempt + 1 < max_retries and last_raw and not fail_fast_json:
            err_msg = str(last_error) if last_error else "unknown error"
            print(
                f"[PageIndex] repair_start: stage={stage} batch={batch_index} "
                f"attempt={attempt + 1}/{max_retries}",
                flush=True,
            )
            try:
                from .json_repair import repair_and_parse, minify_for_retry
                partial, repaired = repair_and_parse(last_raw, schema)
                minified = minify_for_retry(partial.model_dump())
                current_prompt = (
                    f"RETRY: return ONLY this JSON shape (minified example):\n{minified}\n\n"
                    f"Error was: {err_msg}\n\nTask:\n{original_prompt}"
                )
                print(
                    f"[PageIndex] repair_success: stage={stage} batch={batch_index} "
                    f"retry_prompt_chars={len(current_prompt)}",
                    flush=True,
                )
            except Exception as repair_err:
                print(
                    f"[PageIndex] repair_failure: stage={stage} batch={batch_index} "
                    f"err={repair_err}",
                    flush=True,
                )
                current_prompt = _build_retry_prompt(
                    original_prompt, last_raw, err_msg, schema_json
                )

    try:
        from .telemetry import PipelineMetrics
        PipelineMetrics.record_inference(_CURRENT_STAGE, 0, 0, False)
        PipelineMetrics.stage_end(_CURRENT_STAGE)
    except Exception:
        pass

    if (
        allow_fallback_on_timeout
        and fallback_enabled
        and ENABLE_GEMINI_FALLBACK
        and os.environ.get("GEMINI_API_KEY")
    ):
        logger.info("generate_structured: local retries exhausted; fallback_activation %s", ctx_str)
        try:
            t0 = time.perf_counter()
            tok_est = estimate_prompt_tokens(
                original_prompt, system_prompt, schema, token_count_model=TOKEN_COUNT_MODEL
            )
            raw = _call_gemini_fallback(original_prompt, system_prompt, schema, fb_model)
            last_raw = raw
            from .json_repair import repair_and_parse
            validated, _ = repair_and_parse(raw, schema)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            _runtime_summary.record_call(local=False, tokens=tok_est, latency_ms=elapsed_ms)
            logger.info(
                "generate_structured: Gemini fallback succeeded %s schema=%s inference_ms=%.0f",
                ctx_str,
                schema.__name__,
                elapsed_ms,
            )
            return validated
        except Exception as e:
            last_error = e
            logger.error("generate_structured: Gemini fallback failed %s: %s", ctx_str, e)
            raise PipelineStageFailure(
                f"All local retries and Gemini fallback failed for {schema.__name__}",
                last_error=e,
            ) from e

    hint = ""
    if isinstance(last_error, TimeoutError):
        hint = f" (Ollama timed out after {INFERENCE_TIMEOUT_SECONDS}s — use --test-mode or `ollama pull gemma3:4b`)"
    raise PipelineStageFailure(
        f"Structured generation failed for {schema.__name__} after {max_retries} attempt(s){hint}",
        last_error=last_error,
    )


def print_runtime_summary(*, tree_node_count: int = 0, summary_count: int = 0) -> None:
    s = _runtime_summary
    print("\n" + "=" * 72)
    print("PAGEINDEX RUNTIME SUMMARY")
    print("=" * 72)
    print(f"  total inference calls:     {s.total_inference_calls}")
    print(f"  local calls:               {s.local_calls}")
    print(f"  fallback (Gemini) calls:   {s.fallback_calls}")
    print(f"  avg inference latency:     {s.avg_latency_ms:.0f} ms")
    print(f"  total tokens processed:    {s.total_tokens_processed}")
    print(f"  total runtime:             {s.total_runtime_seconds:.1f} s")
    print(f"  tree node count:           {tree_node_count}")
    print(f"  summary count:             {summary_count}")
    print("=" * 72 + "\n")
