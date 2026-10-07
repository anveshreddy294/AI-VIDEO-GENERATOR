"""Real PostgreSQL RLS through a test HTTP bridge; no hosted writes or tenant mocks.

GoTrue and PostgREST transport are local doubles. SQL, grants, RLS, constraints,
snapshot hashing and idempotency execute against the actual disposable database.
"""

from __future__ import annotations

import base64
import copy
import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue, TypeAdapter, ValidationError

from app.core.supabase import AuthenticatedUser, SupabaseConfig, SupabaseRuntime
from app.main import app
from app.services.knowledge_models import KnowledgeSnapshot, ScopedContentUnit
from app.services.knowledge_service import KnowledgeService
from app.services.repositories.knowledge_repository import (
    KnowledgeError,
    KnowledgeRepository,
    METADATA_COLUMNS,
    SELECTS,
)
from app.services.security.auth import get_runtime
from app.services.security.source_scope import SourceScope
from tests.test_knowledge_database import (
    Database,
    OWNER,
    OTHER,
    database,
    literal,
    payload,
    seed,
)

OBJECT = TypeAdapter(dict[str, JsonValue])
NOW = 2_000_000_000
URL = "https://knowledge-test.supabase.co"
pytestmark = pytest.mark.usefixtures("supabase_storage_mode")


def token(owner: str) -> str:
    claims = dict(
        sub=owner,
        iss=URL + "/auth/v1",
        aud="authenticated",
        exp=NOW + 60,
        role="authenticated",
    )
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "header." + encoded + ".test-signature"


def projection(columns: str, alias: str) -> str:
    parts: list[str] = []
    for field in columns.split(","):
        key, column = field.split(":") if ":" in field else (field, field)
        assert column.replace("_", "").isalnum()
        parts.extend((literal(key), alias + "." + column))
    return "jsonb_build_object(" + ",".join(parts) + ")"


@dataclass
class Bridge:
    db: Database
    calls: int = 0
    failure: int | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        authorization = request.headers.get("authorization", "")
        owner = next(
            (
                identity
                for identity in (OWNER, OTHER)
                if authorization == "Bearer " + token(identity)
            ),
            None,
        )
        assert request.headers["apikey"] == "public-test-key"
        if owner is None:
            return httpx.Response(401)
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": owner})
        if self.failure:
            return httpx.Response(
                self.failure, json={"message": "DO_NOT_LEAK_PROVIDER_BODY"}
            )
        if request.method == "POST":
            assert request.url.path == "/rest/v1/rpc/visualai_commit_knowledge_snapshot"
            body = OBJECT.validate_json(request.content)
            assert isinstance(body["p_source_id"], str) and isinstance(
                body["p_operation_id"], str
            )
            assert isinstance(body["p_source_version"], int)
            statement = self.db.call_sql(
                body["p_source_id"],
                body["p_payload"],
                body["p_operation_id"],
                body["p_source_version"],
            )
            result = subprocess.run(
                self.db.args(),
                input="BEGIN; SET LOCAL ROLE authenticated;"
                + f'SET LOCAL "request.jwt.claim.sub"={literal(owner)};'
                + statement
                + ";COMMIT;",
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode:
                return httpx.Response(
                    409 if "23505" in result.stderr else 400,
                    json={"message": "DO_NOT_LEAK_PROVIDER_BODY"},
                )
            return httpx.Response(200, json=json.loads(result.stdout.strip()))
        table = request.url.path.rsplit("/", 1)[-1]
        assert table in SELECTS
        filters: list[str] = []
        for key, value in request.url.params.items():
            if key in ("select", "order", "limit", "offset"):
                continue
            assert key.replace("_", "").isalnum()
            if value.startswith("eq."):
                filters.append("t." + key + "=" + literal(value[3:]))
            else:
                assert value.startswith("in.(") and value.endswith(")")
                filters.append(
                    "t."
                    + key
                    + " IN ("
                    + ",".join(literal(v) for v in value[4:-1].split(","))
                    + ")"
                )
        columns = SELECTS[table]
        if table == "content_concepts":
            fields = columns.split(",content:")[0]
            unit = projection(METADATA_COLUMNS, "u")
            record = (
                projection(fields, "t")
                + " || jsonb_build_object('content', (SELECT "
                + unit
                + """
                FROM public.content_units u WHERE u.user_id=t.user_id AND u.source_id=t.source_id
                AND u.source_version=t.source_version AND u.content_id=t.content_id))"""
            )
        else:
            record = projection(columns, "t")
        limit = int(request.url.params.get("limit", "500"))
        offset = int(request.url.params.get("offset", "0"))
        sql = f"SELECT coalesce(jsonb_agg(value),'[]'::jsonb) FROM (SELECT {record} value FROM public.{table} t"
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += f" ORDER BY t.user_id LIMIT {limit} OFFSET {offset}) page"
        return httpx.Response(200, json=json.loads(self.db.sql(sql, owner=owner)))


@pytest.fixture
def live_db_runtime(database: Database) -> Iterator[tuple[SupabaseRuntime, Bridge]]:
    bridge = Bridge(database)
    runtime = SupabaseRuntime(
        SupabaseConfig(URL, "public-test-key", "unused-admin-key"),
        transport=httpx.MockTransport(bridge),
        clock=lambda: NOW,
    )
    yield runtime, bridge
    runtime.close()


@pytest.fixture
def ready(database: Database) -> str:
    source = seed(database)
    database.commit(source, payload())
    return source


def repository(runtime: SupabaseRuntime, owner: str = OWNER) -> KnowledgeRepository:
    return KnowledgeRepository(None, token(owner), runtime)


def test_owner_hierarchy_evidence_direction_and_bounded_calls(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, bridge = live_db_runtime
    repo = repository(runtime)
    result = KnowledgeService(repo).get_knowledge_map(repo.scope(ready, 1))
    assert result.knowledge_state == "READY"
    assert [t.topic_id for t in result.topics] == ["t1", "t2"]
    assert [s.subtopic_id for s in result.topics[0].subtopics] == ["s1", "s2"]
    dependent = result.topics[0].subtopics[0].concepts[0]
    prerequisite = result.topics[0].subtopics[1].concepts[0]
    assert dependent.prerequisite_concept_ids == ["c2"]
    assert prerequisite.prerequisite_concept_ids == []
    assert dependent.source_content_ids == ["u1", "u2"]
    assert dependent.evidence[0].content.heading_path == ["Chapter"]
    assert dependent.evidence[0].content.user_id == UUID(OWNER)
    assert dependent.evidence[0].content.source_version == 1
    assert repo.database_calls == 6 and bridge.calls == 7
    serialized = result.model_dump_json()
    assert "Canonical evidence for concepts." not in serialized
    assert "unused-admin-key" not in serialized and "test-signature" not in serialized
    assert '"provenance"' not in serialized and "image_path" not in serialized


@pytest.mark.parametrize(
    "method",
    [
        "get_complete_knowledge_map",
        "get_topic",
        "get_subtopic",
        "get_concept",
        "list_concept_evidence",
        "list_relationships",
        "get_scoped_content",
    ],
)
def test_foreign_and_missing_scope_same_boundary(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str, method: str
) -> None:
    runtime, _ = live_db_runtime
    repo = repository(runtime, OTHER)
    args = {
        "get_topic": ["t1"],
        "get_subtopic": ["s1"],
        "get_concept": ["c1"],
        "list_concept_evidence": ["c1"],
        "get_scoped_content": ["u1"],
    }.get(method, [])
    for source in (ready, "missing_source"):
        with pytest.raises(KnowledgeError, match="NOT_FOUND"):
            getattr(repo, method)(repo.scope(source, 1), *args)


def test_database_rls_without_owner_filter(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, _ = live_db_runtime
    for table in (
        "topics",
        "subtopics",
        "concepts",
        "content_concepts",
        "concept_relationships",
    ):
        assert (
            runtime.user_request(
                "GET",
                "/rest/v1/" + table,
                token=token(OTHER),
                params={"source_id": "eq." + ready},
            )
            == []
        )


def test_forged_scope_and_context_rejected_before_data_access(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, bridge = live_db_runtime
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        KnowledgeRepository(
            AuthenticatedUser(UUID(OWNER), None, {}), token(OTHER), runtime
        )
    repo = repository(runtime, OTHER)
    calls = bridge.calls
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        repo.list_topics(
            SourceScope(user_id=UUID(OWNER), source_id=ready, source_version=1)
        )
    assert bridge.calls == calls


@pytest.mark.parametrize("version", [True, 0, -1, "1", "v1", "latest", None])
def test_exact_integer_scope(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], version: object
) -> None:
    runtime, _ = live_db_runtime
    with pytest.raises(KnowledgeError, match="INVALID_SCOPE"):
        repository(runtime).scope("source", version)  # type: ignore[arg-type]


def test_no_latest_fallback(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, _ = live_db_runtime
    repo = repository(runtime)
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        repo.get_complete_knowledge_map(repo.scope(ready, 2))


@pytest.mark.parametrize("state", ["LEGACY_UNMAPPED", "PENDING", "FAILED"])
def test_unready_states_empty_not_invented(
    database: Database, live_db_runtime: tuple[SupabaseRuntime, Bridge], state: str
) -> None:
    source = seed(database)
    database.sql(
        f"UPDATE public.source_versions SET knowledge_state={literal(state)} WHERE source_id={literal(source)}",
        role="postgres",
    )
    runtime, bridge = live_db_runtime
    repo = repository(runtime)
    result = KnowledgeService(repo).get_knowledge_map(repo.scope(source, 1))
    assert result.knowledge_state == state and result.topics == []
    assert result.diagnostic_code == (
        "KNOWLEDGE_BUILD_FAILED" if state == "FAILED" else None
    )
    assert repo.database_calls == 1 and bridge.calls == 2
    with pytest.raises(KnowledgeError, match="NOT_READY"):
        KnowledgeService(repo).get_topic(repo.scope(source, 1), "t1")


def test_membership_and_selectors(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, _ = live_db_runtime
    repo = repository(runtime)
    scope = repo.scope(ready, 1)
    assert repo.get_topic(scope, "t1").topic_id == "t1"
    assert repo.get_subtopic(scope, "s1").topic_id == "t1"
    assert repo.get_concept(scope, "c1").subtopic_id == "s1"
    assert [c.concept_id for c in repo.list_concepts(scope, topic_id="t1")] == [
        "c1",
        "c2",
    ]
    assert repo.list_concepts(scope, topic_id="t2") == []
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        repo.list_concepts(scope, topic_id="t2", subtopic_id="s1")
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        KnowledgeService(repo).get_subtopic(scope, "s1", topic_id="t2")
    with pytest.raises(KnowledgeError, match="INVALID_SCOPE"):
        repo.get_topic(scope, "t1,or=(user_id.eq.other)")


def test_content_envelope_roundtrip(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, _ = live_db_runtime
    repo = repository(runtime)
    content = repo.get_scoped_content(repo.scope(ready, 1), "u1")
    roundtrip = ScopedContentUnit.model_validate_json(content.model_dump_json())
    assert roundtrip.user_id == UUID(OWNER) and roundtrip.source_version == 1
    assert (
        roundtrip.source_id == ready
        and roundtrip.content_id == roundtrip.content.content_id
    )
    assert roundtrip.provenance == {"parser": "original"}
    assert roundtrip.content.text == "Canonical evidence for concepts."


@pytest.mark.parametrize(
    "status,category",
    [
        (503, "PROVIDER_UNAVAILABLE"),
        (429, "PROVIDER_UNAVAILABLE"),
        (400, "INVALID_PROVIDER_RESPONSE"),
    ],
)
def test_provider_failure_not_empty(
    live_db_runtime: tuple[SupabaseRuntime, Bridge],
    ready: str,
    status: int,
    category: str,
) -> None:
    runtime, bridge = live_db_runtime
    repo = repository(runtime)
    bridge.failure = status
    with pytest.raises(KnowledgeError, match=category) as error:
        KnowledgeService(repo).get_knowledge_map(repo.scope(ready, 1))
    assert "DO_NOT_LEAK" not in str(error.value)


def test_internal_rpc_real_idempotency_and_conflict(
    database: Database, live_db_runtime: tuple[SupabaseRuntime, Bridge]
) -> None:
    source = seed(database)
    runtime, _ = live_db_runtime
    repo = repository(runtime)
    scope = repo.scope(source, 1)
    snapshot = KnowledgeSnapshot.model_validate_json(json.dumps(payload()))
    operation = uuid4()
    committed = repo.commit_snapshot(scope, operation, snapshot)
    assert committed == repo.commit_snapshot(scope, operation, snapshot)
    with pytest.raises(KnowledgeError, match="CONFLICT"):
        repo.commit_snapshot(scope, uuid4(), snapshot)
    assert repo.get_knowledge_state(scope).payload_hash == committed.payload_hash
    foreign = repository(runtime, OTHER)
    with pytest.raises(KnowledgeError, match="NOT_FOUND"):
        foreign.commit_snapshot(foreign.scope(source, 1), uuid4(), snapshot)


def test_strict_snapshot_rejects_identity_injection() -> None:
    invalid = copy.deepcopy(payload())
    invalid["user_id"] = OWNER
    with pytest.raises(ValidationError):
        KnowledgeSnapshot.model_validate_json(json.dumps(invalid))


@pytest.mark.parametrize("version", [True, "1", 1.0, 0, 2])
def test_strict_snapshot_schema_version(version: JsonValue) -> None:
    invalid = payload()
    invalid["schema_version"] = version
    with pytest.raises(ValidationError):
        KnowledgeSnapshot.model_validate_json(json.dumps(invalid))


@pytest.mark.parametrize(
    "module",
    [
        "app.services.knowledge_models",
        "app.services.repositories.knowledge_repository",
        "app.services.knowledge_service",
        "app.api.knowledge",
    ],
)
def test_standalone_imports_without_application_import_order(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import " + module],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stderr


def test_api_auth_scope_openapi_and_read_only(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, _ = live_db_runtime
    app.dependency_overrides[get_runtime] = lambda: runtime
    route = "/sources/" + ready + "/versions/1/knowledge"
    with TestClient(app) as client:
        assert client.get(route).status_code == 401
        headers = {"Authorization": "Bearer " + token(OWNER)}
        response = client.get(route, headers=headers)
        assert (
            response.status_code == 200
            and response.json()["knowledge_state"] == "READY"
        )
        assert response.headers["cache-control"] == "private, no-store"
        foreign = client.get(route, headers={"Authorization": "Bearer " + token(OTHER)})
        missing = client.get("/sources/missing/versions/1/knowledge", headers=headers)
        assert (
            foreign.status_code == missing.status_code == 404
            and foreign.json() == missing.json()
        )
        for field in ("user_id", "student_id", "topic_id", "source_version"):
            assert (
                client.get(
                    route + "?" + field + "=" + OTHER, headers=headers
                ).status_code
                == 422
            )
        for version in ("latest", "v1", "0", "-1"):
            assert (
                client.get(
                    route.replace("/versions/1/", "/versions/" + version + "/"),
                    headers=headers,
                ).status_code
                == 422
            )
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        path = schema.json()["paths"][
            "/sources/{source_id}/versions/{version}/knowledge"
        ]
        assert list(path) == ["get"]
        assert path["get"]["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("KnowledgeMap")
        assert client.post(route, headers=headers).status_code == 405


def test_fresh_repository_restart_projection(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    runtime, _ = live_db_runtime
    first = repository(runtime)
    before = KnowledgeService(first).get_knowledge_map(first.scope(ready, 1))
    second = repository(runtime)
    assert before == KnowledgeService(second).get_knowledge_map(second.scope(ready, 1))
    graph = KnowledgeService(second).project_graph(second.scope(ready, 1))
    assert graph.concepts["c1"].prerequisite_concept_ids == ["c2"]


def test_supabase_registry_guard_and_file_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.core.supabase import SupabaseConfigurationError
    from app.services import registry
    from app.services.schemas import KnowledgeGraph
    from app.services.registry import load_knowledge_graph

    with pytest.raises(SupabaseConfigurationError):
        load_knowledge_graph("source")
    monkeypatch.setattr(settings, "database_provider", "file")
    graph = KnowledgeGraph(concepts={})
    registry.save_knowledge_graph("source", graph)
    assert load_knowledge_graph("source") == graph


def test_shuffled_rows_and_multiple_concepts_order(
    database: Database, live_db_runtime: tuple[SupabaseRuntime, Bridge]
) -> None:
    source = seed(database)
    body = payload()
    concepts = body["concepts"]
    links = body["content_concepts"]
    assert isinstance(concepts, list) and isinstance(links, list)
    concepts.append(
        dict(concept_id="c3", subtopic_id="s1", name="Last", sequence=1, provenance={})
    )
    links.append(
        dict(content_id="u2", concept_id="c3", support_kind="example", provenance={})
    )
    for key in ("topics", "subtopics", "concepts", "content_concepts"):
        rows = body[key]
        assert isinstance(rows, list)
        rows.reverse()
    database.commit(source, body)
    runtime, _ = live_db_runtime
    repo = repository(runtime)
    result = KnowledgeService(repo).get_knowledge_map(repo.scope(source, 1))
    assert [t.topic_id for t in result.topics] == ["t1", "t2"]
    assert [s.subtopic_id for s in result.topics[0].subtopics] == ["s1", "s2"]
    assert [c.concept_id for c in result.topics[0].subtopics[0].concepts] == [
        "c1",
        "c3",
    ]


@pytest.mark.parametrize(
    "alteration",
    [
        "foreign_owner",
        "foreign_version",
        "extra_field",
        "missing_content",
        "unknown_parent",
    ],
)
def test_corrupt_provider_response_fails_closed(
    database: Database, ready: str, alteration: str
) -> None:
    bridge = Bridge(database)

    def handler(request: httpx.Request) -> httpx.Response:
        response = bridge(request)
        if request.url.path.endswith("/content_concepts"):
            records = response.json()
            if alteration == "foreign_owner":
                records[0]["content"]["user_id"] = OTHER
            if alteration == "foreign_version":
                records[0]["content"]["source_version"] = 2
            if alteration == "extra_field":
                records[0]["content"]["text"] = "DO_NOT_RETURN"
            if alteration == "missing_content":
                records[0]["content"] = None
            return httpx.Response(200, json=records)
        if request.url.path.endswith("/subtopics") and alteration == "unknown_parent":
            records = response.json()
            records[0]["topic_id"] = "absent"
            return httpx.Response(200, json=records)
        return response

    runtime = SupabaseRuntime(
        SupabaseConfig(URL, "public-test-key"),
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )
    try:
        repo = repository(runtime)
        with pytest.raises(KnowledgeError, match="INVALID_PROVIDER_RESPONSE"):
            KnowledgeService(repo).get_knowledge_map(repo.scope(ready, 1))
    finally:
        runtime.close()


def test_graph_projection_uses_canonical_source_adapter(
    live_db_runtime: tuple[SupabaseRuntime, Bridge], ready: str
) -> None:
    from app.core.supabase import SupabaseResponseError
    from app.services.repositories.source_repository import SupabaseSourceRepository
    from app.services.schemas import KnowledgeGraph

    runtime, _ = live_db_runtime
    source_repo = SupabaseSourceRepository(
        runtime.verify_user(token(OWNER)), token(OWNER), runtime
    )
    assert source_repo.get_knowledge_graph(ready, 1).concepts[
        "c1"
    ].prerequisite_concept_ids == ["c2"]
    with pytest.raises(KnowledgeError, match="INVALID_SCOPE"):
        source_repo.get_knowledge_graph(ready)
    with pytest.raises(SupabaseResponseError):
        source_repo.save_knowledge_graph(ready, KnowledgeGraph(concepts={}))
