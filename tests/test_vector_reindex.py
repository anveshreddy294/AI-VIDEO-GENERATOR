"""Offline repair, semantic-space isolation and narrow short-evidence regressions."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import Mock

import pytest
from qdrant_client import QdrantClient, models

from app.core.config import settings
from app.core.processing_errors import ProcessingError
from app.db import reindex as repair, vector_store
from app.services.schemas import ContentUnit, RichChunk, StageDiagnostics
from app.services import structurer

RepairFixture = tuple[QdrantClient, repair.CanonicalChunk, models.Record]

TEXT = 'Photosynthesis is the conversion of light energy into chemical energy.'


@pytest.fixture
def fixture(monkeypatch: pytest.MonkeyPatch) -> Generator[RepairFixture, None, None]:
    client = QdrantClient(':memory:')
    client.create_collection('repair', vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE))
    chunk = RichChunk(source_id='SRC_test', asset_id='asset', chunk_id='chunk', user_id='owner',
                      text=TEXT, modality='txt', content_ids=['CU_test'], source_version='1', retrieval_allowed=True,
                      injection_status='clean')
    vector = vector_store._deterministic_embedding(TEXT, 768)
    point = models.PointStruct(id=vector_store._point_id(chunk), vector=vector,
                              payload={**chunk.model_dump(), 'custom_timestamp': 'preserved'})
    client.upsert('repair', points=[point], wait=True)
    record = client.retrieve('repair', ids=[point.id], with_vectors=True, with_payload=True)[0]
    canonical = repair.CanonicalChunk('owner', 'SRC_test', chunk, frozenset(['CU_test']))
    monkeypatch.setattr(vector_store, 'get_last_embed_diagnostics', lambda: StageDiagnostics(
        provider_used='ollama', model_used='embeddinggemma', vector_dimension=768, dimension_validated=True))
    yield client, canonical, record
    client.close()


def real_embed(texts: list[str]) -> list[list[float]]:
    return [[1 / (i + 1) for i in range(768)] for _ in texts]


def run(fixture: RepairFixture, apply: bool = False,
        canonical: bool = True, embed: repair.EmbeddingFunction = real_embed) -> repair.ReindexReport:
    client, entry, point = fixture
    return repair.reindex(client, 'repair', {str(point.id): entry} if canonical else {},
                          {('owner', 'SRC_test')}, apply=apply, embed=embed)


def test_exact_historical_signature(fixture: RepairFixture) -> None:
    assert repair.is_historical(fixture[2])


def test_real_vector_not_historical(fixture: RepairFixture) -> None:
    point = fixture[2].model_copy(update={'vector': real_embed([TEXT])[0]})
    assert not repair.is_historical(point)


def test_dry_run_zero_mutations(fixture: RepairFixture) -> None:
    client, _, original = fixture
    report = run(fixture)
    assert report.replacements_validated == 1 and report.applied == 0
    assert client.retrieve('repair', ids=[original.id], with_vectors=True, with_payload=True)[0] == original


def test_apply_replaces_same_id(fixture: RepairFixture) -> None:
    assert run(fixture, apply=True).applied == 1
    client, _, original = fixture
    saved = client.retrieve('repair', ids=[original.id], with_vectors=True)[0]
    assert not repair.is_historical(saved) and client.count('repair').count == 1


def test_apply_idempotent(fixture: RepairFixture) -> None:
    run(fixture, apply=True)
    embed = Mock(side_effect=AssertionError('No repeated embedding work'))
    assert run(fixture, apply=True, embed=embed).applied == 0
    embed.assert_not_called()


def test_missing_canonical_retains_point(fixture: RepairFixture) -> None:
    assert run(fixture, apply=True, canonical=False).unreindexable == 1
    assert repair.is_historical(fixture[0].retrieve('repair', ids=[fixture[2].id], with_vectors=True)[0])


def test_embedding_failure_retains_point(fixture: RepairFixture) -> None:
    with pytest.raises(ProcessingError):
        run(fixture, apply=True, embed=Mock(side_effect=ProcessingError('EMBEDDING_FAILED', 'Unavailable')))
    assert repair.is_historical(fixture[0].retrieve('repair', ids=[fixture[2].id], with_vectors=True)[0])


def test_preserves_canonical_provenance(fixture: RepairFixture) -> None:
    run(fixture, apply=True)
    saved = fixture[0].retrieve('repair', ids=[fixture[2].id], with_payload=True)[0]
    assert all(saved.payload[key] == value for key, value in fixture[2].payload.items())


def test_repaired_dimension(fixture: RepairFixture) -> None:
    run(fixture, apply=True)
    assert len(fixture[0].retrieve('repair', ids=[fixture[2].id], with_vectors=True)[0].vector) == 768


def test_repaired_model_metadata(fixture: RepairFixture) -> None:
    run(fixture, apply=True)
    assert repair.semantic_metadata(fixture[0].retrieve('repair', ids=[fixture[2].id], with_payload=True)[0].payload)


def test_retrieval_excludes_incompatible(fixture: RepairFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    client, entry, original = fixture
    run(fixture, apply=True)
    wrong = entry.chunk.model_copy(update={'chunk_id': 'incompatible'})
    client.upsert('repair', points=[models.PointStruct(id=vector_store._point_id(wrong),
        vector=real_embed([TEXT])[0], payload={**wrong.model_dump(), **repair.provenance(),
                                            'embedding_model': 'nomic-embed-text'})])
    monkeypatch.setattr(settings, 'embedding_provider', 'ollama')
    monkeypatch.setattr(settings, 'collection_name', 'repair')
    monkeypatch.setattr(vector_store, 'get_client', lambda: client)
    monkeypatch.setattr(vector_store, '_embed', lambda *args, **kwargs: real_embed([TEXT]))
    hits = vector_store.search_source_chunks('owner', 'SRC_test', TEXT, score_threshold=0)
    assert len(hits) == 1 and hits[0]['chunk_id'] == original.payload['chunk_id']


def test_zero_compatible_vectors_explicitly_unavailable(fixture: RepairFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'embedding_provider', 'ollama')
    monkeypatch.setattr(settings, 'collection_name', 'repair')
    monkeypatch.setattr(vector_store, 'get_client', lambda: fixture[0])
    monkeypatch.setattr(vector_store, '_embed', lambda *args, **kwargs: real_embed([TEXT]))
    with pytest.raises(vector_store.RetrievalUnavailable):
        vector_store.search_source_chunks('owner', 'SRC_test', TEXT)


def test_invalid_replacement_zero_mutations(fixture: RepairFixture) -> None:
    with pytest.raises(RuntimeError, match='Invalid replacement'):
        run(fixture, apply=True, embed=lambda texts: [[0.0] * 768])
    assert repair.is_historical(fixture[0].retrieve('repair', ids=[fixture[2].id], with_vectors=True)[0])


def test_forged_semantic_hash_still_historical(fixture: RepairFixture) -> None:
    point = fixture[2].model_copy(update={'payload': {**fixture[2].payload, **repair.provenance()}})
    assert repair.is_historical(point)


def test_real_existing_vector_attestation_only(fixture: RepairFixture) -> None:
    client, _, point = fixture
    client.upsert('repair', points=[models.PointStruct(id=point.id, vector=real_embed([TEXT])[0], payload=point.payload)])
    before = client.retrieve('repair', ids=[point.id], with_vectors=True)[0].vector
    report = run(fixture, apply=True)
    assert report.applied == 0 and report.attested == 1
    assert client.retrieve('repair', ids=[point.id], with_vectors=True)[0].vector == before


def units(text: str) -> list[ContentUnit]:
    return [ContentUnit(content_id='CU_short', source_id='SRC_short', asset_id='asset',
                        modality='txt', text=text, sequence_index=0)]


def test_short_definition_extractive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(structurer, '_generate_with_llm', Mock(side_effect=AssertionError('No inference needed')))
    _, graph, _ = structurer.process_structure_and_concepts(units(TEXT))
    assert len(graph.concepts) == 1
    node = next(iter(graph.concepts.values()))
    assert node.name == 'Photosynthesis' and node.definition == TEXT and node.source_content_ids == ['CU_short']


def test_short_weak_still_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(structurer, '_generate_with_llm', lambda text: '{"topic_name":"Weak","concepts":[]}')
    with pytest.raises(ProcessingError) as error:
        structurer.process_structure_and_concepts(units('Hi. This is interesting.'))
    assert error.value.code == 'NO_GROUNDED_CONCEPTS'


def test_short_no_edges() -> None:
    _, graph, blueprint = structurer.process_structure_and_concepts(units(TEXT+' Chlorophyll absorbs light.'))
    assert not blueprint.prerequisites
    assert all(not node.prerequisite_concept_ids and not node.related_concept_ids for node in graph.concepts.values())


def test_large_evidence_bypasses_short_strategy() -> None:
    evidence = units((TEXT+' ') * 490)
    assert len(evidence[0].text) > 33000
    assert structurer._extract_short_definition(evidence) is None
    batches = structurer._structure_batches(evidence)
    assert ''.join(unit.text for batch in batches for unit in batch) == evidence[0].text
    assert all(sum(len(unit.text) for unit in batch) <= structurer.STRUCTURE_BATCH_CHARS for batch in batches)



def test_new_semantic_points_have_actual_provenance(fixture: RepairFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    client, entry, _ = fixture
    monkeypatch.setattr(settings, 'embedding_provider', 'ollama')
    monkeypatch.setattr(settings, 'collection_name', 'repair')
    monkeypatch.setattr(vector_store, 'get_client', lambda: client)
    monkeypatch.setattr(vector_store, '_embed', lambda *args, **kwargs: real_embed([TEXT]))
    assert vector_store.upsert_chunks([entry.chunk]) == 1
    saved = client.retrieve('repair', ids=[vector_store._point_id(entry.chunk)], with_payload=True)[0]
    assert repair.semantic_metadata(saved.payload)


def test_wrong_canonical_owner_not_reindexed(fixture: RepairFixture) -> None:
    client, entry, point = fixture
    wrong = repair.CanonicalChunk('other-owner', entry.source_id, entry.chunk, entry.content_ids)
    report = repair.reindex(client, 'repair', {str(point.id): wrong}, {('owner', 'SRC_test')},
                            apply=True, embed=Mock(side_effect=AssertionError('No embedding without provenance')))
    assert report.unreindexable == 1 and report.applied == 0
    assert repair.is_historical(client.retrieve('repair', ids=[point.id], with_vectors=True)[0])


def test_qa_unavailable_has_safe_explicit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import qa
    from app.services.schemas import QARequest
    async def unavailable(request: QARequest) -> None:
        raise vector_store.RetrievalUnavailable('No compatible vectors')
    monkeypatch.setattr(qa, 'generate_grounded_answer', unavailable)
    response = TestClient(app).post('/qa/answer', json={'user_id': 'owner', 'source_id': 'SRC_test', 'question': 'What is it?'})
    assert response.status_code == 503 and response.json()['detail']['code'] == 'RETRIEVAL_UNAVAILABLE'
