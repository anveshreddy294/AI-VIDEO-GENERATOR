"""Explicit TXT organizational evidence; scope and dependencies stay authoritative."""
import copy
import json
from uuid import UUID
import pytest
from app.services.content_understanding import StructureProposal, UnderstandingError, validate_proposal, understand_content
from app.services.outline_evidence import detect_outline
from app.services.knowledge_models import ScopedContentUnit
from app.services.schemas import ContentUnit
from app.services.security.source_scope import SourceScope

SCOPE = SourceScope(user_id=UUID("00000000-0000-4000-8000-000000000001"),source_id="outline",source_version=1)

def fixture():
    texts = ["1. API LAYERS", "A. SOURCE API\nPurpose:\n- Upload source\n- Extract source", "B. RAG API\nPurpose:\n- Retrieve grounded evidence"]
    units = [ScopedContentUnit(**SCOPE.model_dump(),content_id=f"u{i}",provenance={},content=ContentUnit(content_id=f"u{i}",source_id="outline",asset_id="asset",modality="txt",text=text,sequence_index=i,extraction_method="txt_paragraph")) for i,text in enumerate(texts)]
    def evidence(i,quote=None):
        return [{"content_id":f"u{i}","quote":quote or texts[i],"role":"GENERAL_CONTENT"}]
    body = {"topics":[{"key":"t","title":"API LAYERS","evidence":evidence(0)}],"subtopics":[{"key":"s1","topic_key":"t","title":"SOURCE API","evidence":evidence(1)},{"key":"s2","topic_key":"t","title":"RAG API","evidence":evidence(2)}],"concepts":[{"key":"c1","subtopic_key":"s1","name":"Upload source","definition":None,"evidence":evidence(1,"Upload source")},{"key":"c2","subtopic_key":"s2","name":"Retrieve grounded evidence","definition":None,"evidence":evidence(2,"Retrieve grounded evidence")}],"prerequisites":[]}
    return units,body

def validate(units,body):
    return validate_proposal(SCOPE,units,StructureProposal.model_validate_json(json.dumps(body)))

def test_explicit_outline_grouping_without_semantic_sentence():
    units,body=fixture()
    nodes=detect_outline(SCOPE,units)
    assert len(nodes)==5 and nodes[1].parent_node==(nodes[0].content_id,nodes[0].char_start)
    snapshot,_=validate(units,body)
    assert len(snapshot.topics)==1 and len(snapshot.subtopics)==2 and len(snapshot.concepts)==2
    assert snapshot.relationships==[]

def test_cross_section_evidence_cannot_be_attached_to_sibling():
    units,body=fixture()
    body['concepts'][0]['subtopic_key']='s2'
    body['concepts'][1]['subtopic_key']='s1'
    with pytest.raises(UnderstandingError) as error: validate(units,body)
    assert error.value.code=='INVALID_HIERARCHY' and error.value.detail=='CHILD_SUPPORT'

@pytest.mark.parametrize('texts',[['RANDOM UPPERCASE TEXT','Ordinary prose with no explicit nesting.'],['1. An ordinary sentence.','A. Another ordinary sentence.','B. More ordinary prose.']])
def test_random_caps_or_ordinary_prose_is_not_outline(texts):
    units,_=fixture()
    changed=[units[0].model_copy(update={'content_id':f'x{i}','content':units[0].content.model_copy(update={'content_id':f'x{i}','sequence_index':i,'text':text})}) for i,text in enumerate(texts)]
    assert detect_outline(SCOPE,changed)==[]

def test_foreign_version_and_ambiguous_order_have_no_structural_authority():
    units,_=fixture()
    assert detect_outline(SCOPE.model_copy(update={'source_version':2}),units)==[]
    duplicate=units[1].model_copy(update={'content':units[1].content.model_copy(update={'sequence_index':0})})
    assert detect_outline(SCOPE,[units[0],duplicate,units[2]])==[]

def test_outline_order_cannot_establish_prerequisite():
    units,body=fixture()
    body['prerequisites']=[{'dependent_key':'c2','prerequisite_key':'c1','evidence':[{'content_id':'u2','quote':units[2].content.text,'role':'PREREQUISITE_EVIDENCE'}]}]
    with pytest.raises(UnderstandingError): validate(units,body)

@pytest.mark.parametrize('corrected',[True,False])
def test_outline_repair_is_bounded_and_preserves_final_safe_detail(corrected):
    units,good=fixture(); bad=copy.deepcopy(good)
    bad['concepts'][0]['subtopic_key']='s2';bad['concepts'][1]['subtopic_key']='s1'
    calls=[]
    def provider(prompt):
        calls.append(prompt)
        return json.dumps(good if corrected and len(calls)==2 else bad)
    if corrected:
        result=understand_content(SCOPE,units,provider);assert result.repair_model_calls==1
    else:
        with pytest.raises(UnderstandingError) as error: understand_content(SCOPE,units,provider)
        assert error.value.detail=='CHILD_SUPPORT'
    assert len(calls)==2 and 'STRUCTURAL_OUTLINE_DATA=' in calls[0]


def test_malformed_repair_does_not_report_stale_hierarchy_detail():
    units,body=fixture(); body['concepts'][0]['subtopic_key']='s2';body['concepts'][1]['subtopic_key']='s1'
    calls=[]
    def provider(prompt):
        calls.append(prompt)
        return json.dumps(body) if len(calls)==1 else 'invalid JSON'
    with pytest.raises(UnderstandingError) as error: understand_content(SCOPE,units,provider)
    assert error.value.code=='INVALID_MODEL_OUTPUT' and error.value.detail is None
    assert len(calls)==2


def test_failure_detail_serialization_is_allowlisted():
    from pydantic import ValidationError
    from app.services.ingestion.failures import SourceFailure
    failure=SourceFailure(stage='STRUCTURING',code='INVALID_HIERARCHY',validation_detail='CHILD_SUPPORT',retryable=True,message='Canonical source saved; knowledge preparation failed. Retry this source.')
    assert failure.model_dump()['validation_detail']=='CHILD_SUPPORT'
    with pytest.raises(ValidationError):
        SourceFailure(**{**failure.model_dump(),'validation_detail':'Bearer private-token'})
