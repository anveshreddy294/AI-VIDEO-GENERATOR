"""Presentation relevance must never become source or assessment authority."""
import json
from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.core.supabase import AuthenticatedUser, SupabaseConfig, SupabaseRuntime, SupabaseResponseError
from app.services.learning_profile import LearningPreferences, ProfileUpdate, read_profile, update_profile
from app.services.interest_personalization import build_context, personalize_request


def prefs(*interests, **kwargs):
    return LearningPreferences(education_level='Secondary', interested_domains=list(interests), **kwargs)


@pytest.mark.parametrize('interests,topic,expected',[
    (['Sports'],"Newton's Second Law",True), (['Dance'],'Symmetry and transformations',True),
    (['Dance'],'Binary search trees',False), (['Sports'],'Mitochondrial DNA',False),
    (['Gaming'],'Binary search trees',True), (['Music'],'Sound frequency',True),
])
def test_relevance(interests,topic,expected):
    context=build_context(prefs(*interests),'',topic,'Unchanged source facts','notes')
    assert context.appropriate is expected
    assert bool(context.connections) is expected
    assert context.reason


def test_source_mentions_do_not_force_analogy_and_custom_interest_not_instructions():
    assert not build_context(prefs('Sports'),'','Cell division','A source mentions sports','ask').appropriate
    assert not build_context(prefs('Other',custom_interest='Chess'),'','Newton force','', 'video').appropriate
    with pytest.raises(ValidationError): prefs('Other',custom_interest='<script>')


@pytest.mark.parametrize('body',[
    {'interested_domains':[]}, {'interested_domains':['unknown']}, {'interested_domains':['Sports','Sports']},
    {'interested_domains':['Other']}, {'interested_domains':['Sports'],'custom_interest':'Chess'},
    {'interested_domains':['Sports'],'preferred_language':'unsupported'},
    {'interested_domains':['Sports'],'user_id':str(uuid4())},
])
def test_profile_validation(body):
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({'education_level':'Secondary',**body})


def test_disable_and_no_profile_are_conventional():
    assert not build_context(None,'','Force','','explanation').appropriate
    context=build_context(prefs('Sports',personalization_enabled=False),'','Force','','explanation')
    assert not context.appropriate and not context.connections and not context.selected_interests


def test_context_does_not_change_evidence_or_request_schema():
    from app.core.reasoning import ReasoningRequest, Message
    repo=SimpleNamespace(_learning_preferences=prefs('Sports'))
    original=ReasoningRequest(task='notes',messages=[Message(role='user',content='F = ma; evidence=owned-1')],max_tokens=512)
    result=personalize_request(original,repo,'Force','notes','F = ma')
    assert result.messages[0]==original.messages[0]
    assert result.task==original.task and result.max_tokens==original.max_tokens
    assert 'never evidence' in result.messages[-2].content
    assert 'Sports' in result.messages[-1].content


def test_profile_transport_is_owned_persistent_and_never_writes_role():
    owner,other=uuid4(),uuid4();user=AuthenticatedUser(owner,None,{})
    stored={'id':str(owner),'full_name':'Existing name','learning_preferences':{}}
    calls=[]
    def handler(request):
        assert request.headers['apikey']=='public-test'
        assert request.headers['authorization']=='Bearer token'
        assert request.url.params['id']=='eq.'+str(owner)
        calls.append(request.method)
        if request.method=='PATCH':
            payload=json.loads(request.content);assert set(payload)<= {'full_name','learning_preferences'}
            stored.update(payload);return httpx.Response(204)
        return httpx.Response(200,json=[stored])
    runtime=SupabaseRuntime(SupabaseConfig('https://test.supabase.co','public-test'),transport=httpx.MockTransport(handler))
    assert not read_profile(user,'token',runtime).complete
    body=ProfileUpdate(education_level='Secondary',interested_domains=['Sports'])
    assert update_profile(user,'token',runtime,body).complete
    assert read_profile(user,'token',runtime).display_name=='Existing name'
    stored['id']=str(other)
    with pytest.raises(SupabaseResponseError):read_profile(user,'token',runtime)
    runtime.close()


def test_profile_api_rejects_anonymous_and_client_owner_fields():
    from app.api.learning_profile import router
    from app.services.security.auth import get_current_user, get_runtime, require_access_token
    application=FastAPI();application.include_router(router);client=TestClient(application)
    assert client.get('/api/learning-profile').status_code==401
    owner=uuid4();application.dependency_overrides[get_current_user]=lambda:AuthenticatedUser(owner,None,{})
    application.dependency_overrides[get_runtime]=lambda:object()
    application.dependency_overrides[require_access_token]=lambda:'token'
    result=client.put('/api/learning-profile',json={'education_level':'Secondary','interested_domains':[],'user_id':str(uuid4())})
    assert result.status_code==422
    assert all('input' not in issue for issue in result.json()['detail'])


def test_profile_reaches_lesson_resources_and_cached_content_stays_unchanged(context):
    from tests.test_educational_content import Provider
    from app.services.educational_content import ContentRequest, EducationalContentService
    _,repo,_=context
    repo._learning_preferences=prefs('Sports')
    provider=Provider();service=EducationalContentService(repo,provider)
    content=service.generate(ContentRequest(topic="Newton's Second Law"))
    lesson=service.get_lesson(str(content.content_id))
    notes=service.generate_notes(lesson)
    service.generate_diagram(lesson)
    service.generate_assessment(lesson)
    provider.raw=json.dumps({'answer':'Net force equals mass times acceleration; F = ma.'})
    service.ask(lesson,'Explain force')
    contexts=[json.loads(r.messages[-1].content.split('\n',1)[1]) for r in provider.requests]
    assert {c['resource_type'] for c in contexts}=={'explanation','notes','flowchart','assessment','ask'}
    assert all(c['appropriate'] and c['connections'][0]['interest']=='Sports' for c in contexts)
    assert content.equations==['F = ma'] and content.source_observations==[]
    plan=service.create_video_plan(content)
    assert any(s.title=='Illustrative example: Sports' for s in plan.scenes)
    repo._learning_preferences=prefs('Dance')
    count=len(provider.requests)
    assert service.generate_notes(lesson)==notes and len(provider.requests)==count
    service.generate_notes(lesson,regenerate=True)
    current=json.loads(provider.requests[-1].messages[-1].content.split('\n',1)[1])
    assert current['selected_interests']==['Dance'] and not current['appropriate']
    assert content.equations==['F = ma']


# Reuse only the existing isolated owned repository transport fixture.
from tests.test_source_supabase import context
