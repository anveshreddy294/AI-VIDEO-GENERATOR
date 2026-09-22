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
    expected_vec = [0.1] * 768
    mock_resp = _mock_response({"embeddings": [expected_vec]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["hello world"])
    assert res == [expected_vec]


def test_embed_ollama_success_multiple(monkeypatch):
    vec1 = [0.1] * 768
    vec2 = [0.4] * 768
    mock_resp = _mock_response({"embeddings": [vec1, vec2]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["first text", "second text"])
    assert res == [vec1, vec2]


def test_embed_ollama_invalid_json(monkeypatch):
    mock_resp = _mock_response(b"not json at all <xml>")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_missing_embeddings_key(monkeypatch):
    mock_resp = _mock_response({"wrong_key": [[0.1] * 768]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_count_mismatch(monkeypatch):
    # Sent 2 texts, received 1 vector
    mock_resp = _mock_response({"embeddings": [[0.1] * 768]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["first text", "second text"])
    assert res is None


def test_embed_ollama_empty_embeddings_list(monkeypatch):
    mock_resp = _mock_response({"embeddings": []})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_empty_inner_vector(monkeypatch):
    mock_resp = _mock_response({"embeddings": [[]]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_wrong_type_embeddings(monkeypatch):
    mock_resp = _mock_response({"embeddings": "0.1, 0.2, 0.3"})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_non_numeric_elements(monkeypatch):
    bad_vec = [0.1, "not-a-number"] + [0.1] * 766
    mock_resp = _mock_response({"embeddings": [bad_vec]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_boolean_elements_rejected(monkeypatch):
    bad_vec = [0.1, True] + [0.1] * 766
    mock_resp = _mock_response({"embeddings": [bad_vec]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_non_finite_elements(monkeypatch):
    # NaN and Inf should be rejected
    mock_resp = _mock_response(b'{"embeddings": [[0.1, NaN, 0.3]]}')
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["test text"])
    assert res is None


def test_embed_ollama_dimension_mismatch(monkeypatch):
    vec_dim512 = [0.1] * 512
    mock_resp = _mock_response({"embeddings": [vec_dim512]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: mock_resp)

    res = _embed_ollama(["text 1"])
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
    real_vec = [0.5] * 768
    mock_resp = _mock_response({"embeddings": [real_vec]})
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
