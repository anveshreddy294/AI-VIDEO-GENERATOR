"""Credential-safe, bounded Worker reachability; health never invokes inference."""
from __future__ import annotations
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
import httpx
import json
from pydantic import BaseModel
from .config import settings

HEALTH_TIMEOUT_SECONDS = 5.0
MAX_HEALTH_BYTES = 4096

class InferenceHealth(BaseModel):
    configured: bool
    worker_reachable: bool
    primary_provider: Literal["cloudflare"] = "cloudflare"
    fallback_provider: Literal["ollama"] = "ollama"


def inference_health() -> InferenceHealth:
    configured = bool(settings.cloudflare_worker_url and settings.cloudflare_worker_secret.get_secret_value())
    result = InferenceHealth(configured=configured,worker_reachable=False)
    if not configured:
        return result
    url = urlsplit(settings.cloudflare_worker_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        return result
    health_url = urlunsplit((url.scheme,url.netloc,"/health","",""))
    try:
        with httpx.Client(timeout=httpx.Timeout(HEALTH_TIMEOUT_SECONDS),follow_redirects=False) as client:
            with client.stream("GET",health_url) as response:
                if response.status_code != 200:
                    return result
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_HEALTH_BYTES:
                        return result
        data = json.loads(body)
        result.worker_reachable = isinstance(data,dict) and data.get("status") == "ok" and data.get("service") == "visualai-cloudflare-inference"
    except (httpx.HTTPError,ValueError):
        result.worker_reachable = False
    return result
