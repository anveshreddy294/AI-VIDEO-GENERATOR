"""Namespace isolation, cache provenance and non-destructive collection contracts."""
import contextvars
import json
from unittest.mock import MagicMock

import pytest
from qdrant_client import QdrantClient, models

from app.core.config import Settings, settings
from app.core.processing_errors import ProcessingError
from app.db import vector_store as vs


@pytest.mark.parametrize('legacy', ['visualai_layer_a', 'visualai_layer_a_v1'])
def test_intended_model_retires_only_legacy_namespaces(monkeypatch, legacy):
    monkeypatch.setenv('EMBEDDING_PROVIDER', 'ollama')
    monkeypatch.setenv('EMBEDDING_MODEL', 'embeddinggemma')
    monkeypatch.delenv('OLLAMA_EMBED_MODEL', raising=False)
    monkeypatch.delenv('SEMANTIC_COLLECTION_NAME', raising=False)
    monkeypatch.setenv('COLLECTION_NAME', legacy)
    config = Settings()
    assert config.requested_collection_name == legacy
    assert config.collection_name == config.qdrant_collection == 'visualai_embeddinggemma_v2'
    monkeypatch.setenv('COLLECTION_NAME', 'custom_existing')
    assert Settings().collection_name == 'custom_existing'
    monkeypatch.setenv('SEMANTIC_COLLECTION_NAME', 'explicit_new_v3')
    assert Settings().collection_name == 'explicit_new_v3'


def test_query_cache_restores_exact_provenance_in_new_request_context(monkeypatch):
    monkeypatch.setattr(settings, 'embedding_provider', 'ollama')
    monkeypatch.setattr(settings, 'embedding_model', 'embeddinggemma')
    monkeypatch.setattr(settings, 'embedding_fallback_model', '')
    monkeypatch.setattr(vs, '_QUERY_EMBED_CACHE', {})
    monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({'model':'embeddinggemma:latest', 'embeddings':[[.1]*768]}).encode()
    provider = MagicMock(return_value=response)
    monkeypatch.setattr('urllib.request.urlopen', provider)
    def query():
        vector = vs.embed_query('How does force depend on mass?')
        return vector, vs.embedding_provenance()
    first = contextvars.Context().run(query)
    second = contextvars.Context().run(query)
    assert first == second and provider.call_count == 1
    assert second[1]['embedding_preprocessing'] == 'ollama-raw-v1'
    # A different endpoint must not inherit a cached vector from another server.
    monkeypatch.setattr(settings, 'ollama_base_url', 'http://other-ollama:11434')
    contextvars.Context().run(query)
    assert provider.call_count == 2


@pytest.mark.parametrize('vectors', [
    models.VectorParams(size=768, distance=models.Distance.DOT),
    {'named': models.VectorParams(size=768, distance=models.Distance.COSINE)},
])
def test_incompatible_collection_contract_is_preserved(monkeypatch, vectors):
    monkeypatch.setattr(settings, 'collection_name', 'existing')
    client = QdrantClient(':memory:')
    try:
        client.create_collection('existing', vectors_config=vectors)
        before = client.get_collection('existing').config.params.vectors
        with pytest.raises(RuntimeError):
            vs.ensure_collection(client, 768)
        assert client.get_collection('existing').config.params.vectors == before
        assert client.count('existing').count == 0
    finally:
        client.close()


def test_different_model_tag_is_not_attested_as_configured_model(monkeypatch):
    monkeypatch.setattr(settings, 'embedding_provider', 'ollama')
    monkeypatch.setattr(settings, 'embedding_model', 'embeddinggemma:verified')
    monkeypatch.setattr(settings, 'embedding_fallback_model', '')
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({'model':'embeddinggemma:other', 'embeddings':[[.1]*768]}).encode()
    monkeypatch.setattr('urllib.request.urlopen', MagicMock(return_value=response))
    with pytest.raises(ProcessingError):
        vs.embed_documents(['source text'])
