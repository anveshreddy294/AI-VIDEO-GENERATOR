"""Explicit model fallback, no synthetic production vectors, and pre-write dimension checks."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.processing_errors import ProcessingError
from app.db import vector_store as vectors
from app.services.schemas import RichChunk


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'embedding_provider', 'ollama')
    monkeypatch.setattr(settings, 'embedding_model', 'missing-model')
    monkeypatch.setattr(settings, 'embedding_fallback_model', 'embeddinggemma')
    monkeypatch.setattr(vectors, '_embedding_fallback_warnings', set())


def response(model: str = 'embeddinggemma', dimension: int = 768) -> MagicMock:
    result = MagicMock()
    result.__enter__.return_value = result
    result.read.return_value = json.dumps({'model': model, 'embeddings': [[0.1] * dimension]}).encode()
    return result


def test_missing_model_uses_only_explicit_supported_fallback(production: None, monkeypatch: pytest.MonkeyPatch,
                                                           caplog: pytest.LogCaptureFixture) -> None:
    models: list[str] = []

    def request(req: urllib.request.Request, timeout: float) -> MagicMock:
        model = json.loads(req.data)['model']
        models.append(model)
        if model == 'missing-model':
            raise urllib.error.HTTPError(req.full_url, 404, 'secret body', {}, None)
        return response()

    monkeypatch.setattr(urllib.request, 'urlopen', request)
    assert len(vectors._embed(['source evidence'])[0]) == 768
    assert len(vectors._embed(['source evidence'])[0]) == 768
    assert models == ['missing-model', 'embeddinggemma'] * 2
    assert caplog.text.count('using configured fallback') == 1
    assert 'secret body' not in caplog.text
    diagnostics = vectors.get_last_embed_diagnostics()
    assert diagnostics.model_used == 'embeddinggemma' and diagnostics.fallback_used


def test_configured_model_preferred_over_cached_fallback(production: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'embedding_model', 'embeddinggemma')
    monkeypatch.setattr(vectors, '_resolved_ollama_model', 'nomic-embed-text')
    request = MagicMock(return_value=response())
    monkeypatch.setattr(urllib.request, 'urlopen', request)
    vectors._embed(['source evidence'])
    assert json.loads(request.call_args.args[0].data)['model'] == 'embeddinggemma'
    assert not vectors.get_last_embed_diagnostics().fallback_used


def test_missing_primary_and_fallback_fails_deterministically(production: None, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(req: urllib.request.Request, timeout: float) -> MagicMock:
        raise urllib.error.HTTPError(req.full_url, 404, 'secret body', {}, None)
    monkeypatch.setattr(urllib.request, 'urlopen', missing)
    with pytest.raises(ProcessingError) as failure:
        vectors._embed(['source evidence'])
    assert failure.value.code == 'EMBEDDING_MODEL_UNAVAILABLE'


def test_unsupported_fallback_is_never_called(production: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'embedding_fallback_model', 'unapproved-model')
    request = MagicMock(side_effect=urllib.error.HTTPError('http://localhost/api/embed', 404, 'missing', {}, None))
    monkeypatch.setattr(urllib.request, 'urlopen', request)
    with pytest.raises(ProcessingError):
        vectors._embed(['source evidence'])
    request.assert_called_once()
    assert json.loads(request.call_args.args[0].data)['model'] == 'missing-model'


@pytest.mark.parametrize('dimension', [0, 384])
def test_invalid_vector_dimension_fails_before_indexing(production: None, monkeypatch: pytest.MonkeyPatch,
                                                       dimension: int) -> None:
    monkeypatch.setattr(settings, 'embedding_model', 'embeddinggemma')
    monkeypatch.setattr(urllib.request, 'urlopen', MagicMock(return_value=response(dimension=dimension)))
    with pytest.raises(ProcessingError) as failure:
        vectors._embed(['source evidence'])
    assert failure.value.code == 'EMBEDDING_FAILED'


def test_zero_vectors_are_rejected(production: None, monkeypatch: pytest.MonkeyPatch) -> None:
    result = response()
    result.read.return_value = json.dumps({'embeddings': [[0] * 768]}).encode()
    monkeypatch.setattr(urllib.request, 'urlopen', MagicMock(return_value=result))
    with pytest.raises(ProcessingError):
        vectors._embed(['source evidence'])


def test_production_cannot_use_synthetic_vectors_even_with_mock_reasoning(production: None,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'llm_provider', 'mock')
    monkeypatch.setattr(urllib.request, 'urlopen', MagicMock(side_effect=TimeoutError()))
    with pytest.raises(ProcessingError):
        vectors._embed(['source evidence'])
    with pytest.raises(ProcessingError):
        vectors._deterministic_embedding('source evidence')


def test_collection_dimension_mismatch_never_upserts_or_deletes(production: None,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'embedding_model', 'embeddinggemma')
    monkeypatch.setattr(urllib.request, 'urlopen', MagicMock(return_value=response()))
    client = MagicMock()
    collection = MagicMock()
    collection.name = settings.collection_name
    client.get_collections.return_value.collections = [collection]
    client.get_collection.return_value.config.params.vectors.size = 384
    monkeypatch.setattr(vectors, 'get_client', lambda: client)
    chunk = RichChunk(source_id='SRC_test', asset_id='AST_test', user_id='owner',
                      text='Photosynthesis converts light energy.', content_ids=['CU_test'], modality='txt')
    with pytest.raises(RuntimeError, match='dimension'):
        vectors.upsert_chunks([chunk])
    client.upsert.assert_not_called()
    client.delete_collection.assert_not_called()
    client.create_collection.assert_not_called()
