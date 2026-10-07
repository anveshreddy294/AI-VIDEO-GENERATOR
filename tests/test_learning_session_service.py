"""Normal HTTP/auth transport doubles backed by actual PostgreSQL session RPC/RLS."""

from __future__ import annotations
import json
from collections.abc import Iterator
from uuid import UUID, uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue, TypeAdapter
from app.core.supabase import SupabaseRuntime, SupabaseConfig
from app.main import app
from app.services.learning_session import (
    LearningSessionService,
    CreateLearningSession,
    SessionSelection,
    SessionQARequest,
)
from app.services.repositories.knowledge_repository import (
    KnowledgeRepository,
    KnowledgeError,
)
from app.services.qa.canonical_answer import CanonicalQARequest
from app.services.schemas import QAResponse
from tests.test_content_understanding import PipelineBridge
from tests.test_knowledge_repository import URL, token
from tests.test_knowledge_database import Database, OWNER, OTHER, literal
from tests.test_learning_session_database import sessions, database, ready, rpc

OBJECT = TypeAdapter(dict[str, JsonValue])
pytestmark = pytest.mark.usefixtures("supabase_storage_mode")


class SessionBridge(PipelineBridge):
    def __call__(self, request: httpx.Request) -> httpx.Response:
        owner = next(
            (
                o
                for o in (OWNER, OTHER)
                if request.headers.get("authorization") == "Bearer " + token(o)
            ),
            None,
        )
        if owner is None:
            return httpx.Response(401, json={})
        if request.url.path.endswith("/learning_sessions"):
            self.calls += 1
            conditions = []
            for key in ("user_id", "session_id"):
                value = request.url.params.get(key)
                if value:
                    assert value.startswith("eq.")
                    conditions.append("t." + key + "=" + literal(value[3:]))
            query = (
                "SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public.learning_sessions t WHERE "
                + " AND ".join(conditions)
            )
            return httpx.Response(200, json=json.loads(self.db.sql(query, owner=owner)))
        if request.url.path.endswith("/visualai_mutate_learning_session"):
            self.calls += 1
            body = OBJECT.validate_json(request.content)
            action = body["p_action"]
            sid = body["p_session_id"]
            assert isinstance(action, str) and isinstance(sid, str)
            source = body.get("p_source_id")
            if source is None:
                query = rpc(action, sid)
            else:
                assert (
                    isinstance(source, str)
                    and isinstance(body["p_source_version"], int)
                    and isinstance(body["p_topic_id"], str)
                )
                concepts = body["p_concept_ids"]
                assert isinstance(concepts, list) and all(
                    isinstance(c, str) for c in concepts
                )
                sub = body.get("p_subtopic_id")
                assert sub is None or isinstance(sub, str)
                query = rpc(
                    action,
                    sid,
                    source,
                    version=body["p_source_version"],
                    topic=body["p_topic_id"],
                    sub=sub,
                    concepts=tuple(c for c in concepts if isinstance(c, str)),
                )
            return httpx.Response(200, json=json.loads(self.db.sql(query, owner=owner)))
        return super().__call__(request)


@pytest.fixture
def runtime(
    sessions: Database, monkeypatch: pytest.MonkeyPatch
) -> Iterator[SupabaseRuntime]:
    bridge = SessionBridge(sessions)
    result = SupabaseRuntime(
        SupabaseConfig(URL, "public-test-key"), transport=httpx.MockTransport(bridge)
    )
    from app.services.security import auth

    monkeypatch.setattr(auth, "get_supabase_runtime", lambda: result)
    yield result
    result.close()


def test_create_resume_transition_and_reload(
    sessions: Database, runtime: SupabaseRuntime
) -> None:
    source = ready(sessions)
    context = KnowledgeRepository(None, token(OWNER), runtime)
    service = LearningSessionService(context)
    created = service.create(
        CreateLearningSession(
            source_id=source, source_version=1, topic_id="t1", subtopic_id="s1"
        )
    )
    assert created.user_id == UUID(OWNER) and created.selected_concept_ids == ["c1"]
    resumed = LearningSessionService(
        KnowledgeRepository(None, token(OWNER), runtime)
    ).transition(created.session_id, "resume")
    assert resumed.source_version == 1 and resumed.topic_id == created.topic_id
    view = service.get(created.session_id)
    assert len(view.concepts) == 1
    assert service.change_selection(
        created.session_id, SessionSelection(topic_id="t1", subtopic_id="s2")
    ).selected_concept_ids == ["c2"]
    assert service.transition(created.session_id, "complete").state == "COMPLETED"
    with pytest.raises(KnowledgeError, match="CONFLICT"):
        service.transition(created.session_id, "resume")


def test_http_owned_session_qa_and_contradictions(
    sessions: Database, runtime: SupabaseRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = ready(sessions)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + token(OWNER)}
    created = client.post(
        "/learning-sessions",
        headers=headers,
        json={
            "source_id": source,
            "source_version": 1,
            "topic_id": "t1",
            "subtopic_id": "s1",
        },
    )
    assert created.status_code == 200
    sid = created.json()["session_id"]
    captured: list[CanonicalQARequest] = []

    async def answer(
        request: CanonicalQARequest, *, context: KnowledgeRepository
    ) -> QAResponse:
        captured.append(request)
        assert context.user.user_id == UUID(OWNER)
        return QAResponse(answer="Scoped test double", refusal=True)

    from app.api import qa

    monkeypatch.setattr(qa, "generate_grounded_answer", answer)
    result = client.post(
        "/qa/answer", headers=headers, json={"session_id": sid, "question": "Question"}
    )
    assert result.status_code == 200
    assert captured[0].source_id == source and captured[0].source_version == 1
    assert (
        captured[0].topic_id == "t1"
        and captured[0].subtopic_id == "s1"
        and captured[0].concept_ids == ["c1"]
    )
    for extra in (
        {"source_id": "foreign"},
        {"source_version": 2},
        {"topic_id": "t2"},
        {"subtopic_id": None},
        {"concept_ids": ["c2"]},
        {"user_id": OTHER},
    ):
        assert (
            client.post(
                "/qa/answer",
                headers=headers,
                json={"session_id": sid, "question": "Question", **extra},
            ).status_code
            == 422
        )
    assert len(captured) == 1
    assert (
        client.post("/learning-sessions/" + sid + "/abandon", headers=headers).json()[
            "state"
        ]
        == "ABANDONED"
    )
    assert (
        client.post(
            "/qa/answer",
            headers=headers,
            json={"session_id": sid, "question": "Question"},
        ).status_code
        == 409
    )


def test_foreign_and_anonymous_sessions_uniform_denial(
    sessions: Database, runtime: SupabaseRuntime
) -> None:
    source = ready(sessions)
    owner = LearningSessionService(KnowledgeRepository(None, token(OWNER), runtime))
    created = owner.create(
        CreateLearningSession(
            source_id=source, source_version=1, topic_id="t1", subtopic_id="s1"
        )
    )
    client = TestClient(app)
    foreign = {"Authorization": "Bearer " + token(OTHER)}
    for sid in (str(created.session_id), str(uuid4())):
        get = client.get("/learning-sessions/" + sid, headers=foreign)
        assert get.status_code == 404
        for action in ("resume", "complete", "abandon"):
            assert (
                client.post(
                    "/learning-sessions/" + sid + "/" + action, headers=foreign
                ).json()
                == get.json()
            )
        assert (
            client.post(
                "/learning-sessions/" + sid + "/selection",
                headers=foreign,
                json={"topic_id": "t1"},
            ).json()
            == get.json()
        )
        assert (
            client.post(
                "/qa/answer",
                headers=foreign,
                json={"session_id": sid, "question": "Question"},
            ).json()
            == get.json()
        )
    assert (
        client.get("/learning-sessions/" + str(created.session_id)).status_code == 401
    )
    assert client.post("/learning-sessions", json={}).status_code == 401
    assert (
        client.post(
            "/learning-sessions",
            headers=foreign,
            json={"source_id": source, "source_version": 1, "topic_id": "t1"},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "selection",
    [
        {"topic_id": "foreign"},
        {"topic_id": "t2", "subtopic_id": "s1"},
        {"topic_id": "t1", "subtopic_id": "foreign"},
    ],
)
def test_invalid_selection_before_rpc(
    sessions: Database, runtime: SupabaseRuntime, selection: dict[str, str]
) -> None:
    source = ready(sessions)
    context = KnowledgeRepository(None, token(OWNER), runtime)
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        LearningSessionService(context).create(
            CreateLearningSession(source_id=source, source_version=1, **selection)
        )
