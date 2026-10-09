"""Offline append-only rebuild, identity deduplication and preserved historical evidence."""
import pytest
from app.services.ingestion.knowledge_rebuild import extend_snapshot
from app.services.knowledge_models import KnowledgeSnapshot
from app.services.repositories.knowledge_repository import KnowledgeError
from tests.test_canonical_retrieval import fixture


def proposal():
    return KnowledgeSnapshot.model_validate({"schema_version":1,
        "topics":[{"topic_id":"newtopic","title":"BIOLOGY","sequence":0,"provenance":{}}],
        "subtopics":[{"subtopic_id":"newsub","topic_id":"newtopic","title":"Cells","sequence":0,"provenance":{}}],
        "concepts":[{"concept_id":"newconcept","subtopic_id":"newsub","name":"Osmosis","sequence":0,"definition":None,"provenance":{}}],
        "content_concepts":[{"content_id":"content","concept_id":"newconcept","support_kind":"definition","char_start":0,"char_end":6,"provenance":{}}],
        "relationships":[]})


def test_rebuild_deduplicates_names_and_never_changes_historical_evidence(fixture):
    repo,_=fixture
    existing=repo.data
    old=existing.model_dump()
    result=extend_snapshot(existing,proposal())
    assert len(result.topics)==len(result.subtopics)==len(result.concepts)==1
    assert result.concepts[0].concept_id=="osmosis"
    assert result.concepts[0].definition==existing.concepts[0].definition
    assert result.content_concepts[0].char_end==existing.evidence[0].char_end
    assert existing.model_dump()==old
    assert extend_snapshot(existing,proposal())==result


def test_rebuild_adds_distinct_concept_with_noncolliding_sequence(fixture):
    repo,_=fixture
    value=proposal()
    new=value.concepts[0].model_copy(update={"name":"Membrane"})
    result=extend_snapshot(repo.data,value.model_copy(update={"concepts":[new]}))
    assert [c.name for c in result.concepts]==["Osmosis","Membrane"]
    assert [c.sequence for c in result.concepts]==[0,1]
    assert result.concepts[1].subtopic_id=="sub"
    assert {e.concept_id for e in result.content_concepts}=={"osmosis","newconcept"}


def test_rebuild_rejects_id_collision_with_different_label(fixture):
    repo,_=fixture
    value=proposal()
    new=value.concepts[0].model_copy(update={"concept_id":"osmosis","name":"Invented"})
    with pytest.raises(KnowledgeError,match="CONFLICT"):
        extend_snapshot(repo.data,value.model_copy(update={"concepts":[new]}))
