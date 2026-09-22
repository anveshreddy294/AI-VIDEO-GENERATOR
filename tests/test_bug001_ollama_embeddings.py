"""Tests for BUG-001: Ollama Embedding Accumulator, Validation, and Diagnostics."""

import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock
import pytest

from app.db.vector_store import (
    _embed,
    _embed_ollama,
    get_last_embed_diagnostics,
)
from app.core.config import settings


def _mock_response(body_dict_or_bytes, status=200):
    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.__exit__.return_value = False
    if isinstance(body_dict_or_bytes, (dict, list)):
        content = json.dumps(body_dict_or_bytes).encode("utf-8")
    elif isinstance(body_dict_or_bytes, str):
        content = body_dict_or_bytes.encode("utf-8")
    else:
        content = body_dict_or_bytes
    mock.read.return_value = content
    mock.status = status
    return mock


def test_embed_ollama_success_single(monkeypatch):
    expected_vec = [0.1, 0.2, 0.3]
    mock_resp = _mock_response({"embedding": expected_vec})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["hello world"])
    assert res == [expected_vec]


def test_embed_ollama_success_multiple(monkeypatch):
    vec1 = [0.1, 0.2, 0.3]
    vec2 = [0.4, 0.5, 0.6]
    responses = [_mock_response({"embedding": vec1}), _mock_response({"embedding": vec2})]

    def mock_urlopen(req, timeout=30.0):
        return responses.pop(0)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    res = _embed_ollama(["first text", "second text"])
    assert res == [vec1, vec2]


def test_embed_ollama_invalid_json(monkeypatch):
    mock_resp = _mock_response(b"not json at all <xml>")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_missing_embedding_key(monkeypatch):
    mock_resp = _mock_response({"wrong_key": [0.1, 0.2, 0.3]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_empty_embedding_list(monkeypatch):
    mock_resp = _mock_response({"embedding": []})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_wrong_type_embedding(monkeypatch):
    mock_resp = _mock_response({"embedding": "0.1, 0.2, 0.3"})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_non_numeric_elements(monkeypatch):
    mock_resp = _mock_response({"embedding": [0.1, "not-a-number", 0.3]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_boolean_elements_rejected(monkeypatch):
    mock_resp = _mock_response({"embedding": [0.1, True, 0.3]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_non_finite_elements(monkeypatch):
    # NaN and Inf should be rejected
    mock_resp = _mock_response(b'{"embedding": [0.1, NaN, 0.3]}')
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_dimension_mismatch_in_batch(monkeypatch):
    vec_dim3 = [0.1, 0.2, 0.3]
    vec_dim4 = [0.1, 0.2, 0.3, 0.4]
    responses = [_mock_response({"embedding": vec_dim3}), _mock_response({"embedding": vec_dim4})]

    def mock_urlopen(req, timeout=30.0):
        return responses.pop(0)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    res = _embed_ollama(["text 1", "text 2"])
    assert res is None


def test_embed_ollama_connection_failure(monkeypatch):
    def mock_urlopen_fail(req, timeout=30.0):
        raise urllib.error.URLError("Connection refused [Errno 61]")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_fail)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_timeout(monkeypatch):
    def mock_urlopen_timeout(req, timeout=30.0):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_timeout)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_pipeline_success_vs_fallback(monkeypatch):
    # 1. Success case uses Ollama provider
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    real_vec = [0.5, 0.6, 0.7]
    mock_resp = _mock_response({"embedding": real_vec})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    vectors = _embed(["sample text"])
    assert vectors == [real_vec]
    diag = get_last_embed_diagnostics()
    assert diag is not None
    assert diag.provider_used == "ollama"
    assert diag.fallback_used is False
    assert diag.grounding_verified is True

    # 2. Failure case activates deterministic fallback
    def mock_fail(req, timeout=30.0):
        raise urllib.error.URLError("Ollama service down")

    monkeypatch.setattr(urllib.request, "urlopen", mock_fail)

    vectors_fallback = _embed(["sample text"])
    assert len(vectors_fallback) == 1
    assert len(vectors_fallback[0]) == len(real_vec)
    diag_fb = get_last_embed_diagnostics()
    assert diag_fb is not None
    assert diag_fb.provider_used == "deterministic_hash_fallback"
    assert diag_fb.fallback_used is True
