"""Real disposable PostgreSQL: session migration, RLS, RPC grants and invariants."""

from __future__ import annotations
import json
from pathlib import Path
from uuid import uuid4
import pytest
from tests.test_knowledge_database import (
    Database,
    database,
    seed,
    payload,
    literal,
    OWNER,
    OTHER,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations/20261007110254_focused_learning_sessions.sql"
)


@pytest.fixture(scope="module")
def sessions(database: Database) -> Database:
    database.sql(MIGRATION.read_text(), role="postgres", owner=None)
    return database


def rpc(
    action: str,
    sid: str,
    source: str | None = None,
    *,
    version: int = 1,
    topic: str = "t1",
    sub: str | None = "s1",
    concepts: tuple[str, ...] = ("c1",),
) -> str:
    args = [literal(action), literal(sid) + "::uuid"]
    if source is not None:
        args += [
            literal(source),
            str(version),
            literal(topic),
            literal(sub) if sub else "NULL",
            "ARRAY[" + ",".join(literal(c) for c in concepts) + "]::text[]",
        ]
    return "SELECT public.visualai_mutate_learning_session(" + ",".join(args) + ")"


def ready(db: Database, owner: str = OWNER) -> str:
    source = seed(db, owner=owner)
    db.commit(source, payload(), owner=owner)
    return source


def test_create_resume_idempotency_and_pinning(sessions: Database) -> None:
    db = sessions
    source = ready(db)
    sid = str(uuid4())
    first = json.loads(db.sql(rpc("create", sid, source)))
    second = json.loads(db.sql(rpc("create", sid, source)))
    assert (
        first == second
        and first["user_id"] == OWNER
        and first["selected_concept_ids"] == ["c1"]
    )
    resumed = json.loads(db.sql(rpc("resume", sid)))
    assert (
        resumed["source_version"] == 1
        and resumed["topic_id"] == "t1"
        and resumed["subtopic_id"] == "s1"
    )
    assert (
        db.sql(
            f"SELECT count(*) FROM public.learning_sessions WHERE session_id={literal(sid)}"
        )
        == "1"
    )
    # A later canonical version cannot retarget the persisted row.
    db.sql(
        f"INSERT INTO public.source_versions(user_id,source_id,version,source_version,filename,file_hash,file_location) SELECT user_id,source_id,2,'v2',filename,file_hash,file_location FROM public.source_versions WHERE source_id={literal(source)} AND version=1",
        role="postgres",
    )
    assert json.loads(db.sql(rpc("resume", sid)))["source_version"] == 1


@pytest.mark.parametrize(
    "action,state", [("complete", "COMPLETED"), ("abandon", "ABANDONED")]
)
def test_terminal_states_not_reactivated(
    sessions: Database, action: str, state: str
) -> None:
    source = ready(sessions)
    sid = str(uuid4())
    sessions.sql(rpc("create", sid, source))
    result = json.loads(sessions.sql(rpc(action, sid)))
    assert result["state"] == state
    assert json.loads(sessions.sql(rpc(action, sid))) == result
    assert "55000" in sessions.sql(rpc("resume", sid), succeeds=False)
    assert "55000" in sessions.sql(
        rpc("selection", sid, source, sub=None, concepts=("c1", "c2")), succeeds=False
    )


def test_explicit_selection_keeps_source(sessions: Database) -> None:
    source = ready(sessions)
    sid = str(uuid4())
    sessions.sql(rpc("create", sid, source))
    changed = json.loads(
        sessions.sql(rpc("selection", sid, source, sub="s2", concepts=("c2",)))
    )
    assert changed["selected_concept_ids"] == ["c2"] and changed["source_id"] == source
    assert "22023" in sessions.sql(
        rpc("selection", sid, source, version=2, sub="s2", concepts=("c2",)),
        succeeds=False,
    )


@pytest.mark.parametrize(
    "case",
    [
        "source",
        "version",
        "topic",
        "subtopic",
        "parent",
        "concept",
        "empty",
        "duplicate",
        "unready",
    ],
)
def test_invalid_selections_rejected(sessions: Database, case: str) -> None:
    source = seed(sessions) if case == "unready" else ready(sessions)
    sql = rpc(
        "create",
        str(uuid4()),
        "foreign" if case == "source" else source,
        version=2 if case == "version" else 1,
        topic="foreign" if case == "topic" else "t2" if case == "parent" else "t1",
        sub="foreign" if case == "subtopic" else "s1",
        concepts=(
            ()
            if case == "empty"
            else (
                ("c1", "c1")
                if case == "duplicate"
                else ("foreign",) if case == "concept" else ("c1",)
            )
        ),
    )
    assert "42501" in sessions.sql(sql, succeeds=False)


def test_owner_rls_and_foreign_safe_rpc_denial(sessions: Database) -> None:
    source = ready(sessions)
    sid = str(uuid4())
    sessions.sql(rpc("create", sid, source))
    assert (
        sessions.sql(
            f"SELECT count(*) FROM public.learning_sessions WHERE session_id={literal(sid)}",
            owner=OTHER,
        )
        == "0"
    )
    for action in ("resume", "complete", "abandon", "selection"):
        sql = rpc(action, sid, source if action == "selection" else None)
        error = sessions.sql(sql, owner=OTHER, succeeds=False)
        missing = sessions.sql(
            rpc(action, str(uuid4()), source if action == "selection" else None),
            owner=OTHER,
            succeeds=False,
        )
        assert (
            "42501" in error
            and "Session unavailable" in error
            and "Session unavailable" in missing
        )
    assert "42501" in sessions.sql(
        rpc("create", str(uuid4()), source), owner=OTHER, succeeds=False
    )
    assert "42501" in sessions.sql(rpc("resume", sid), owner=None, succeeds=False)
    assert "42501" in sessions.sql(
        rpc("resume", sid), owner=None, role="anon", succeeds=False
    )


def test_direct_mutation_and_anonymous_reads_denied(sessions: Database) -> None:
    assert "42501" in sessions.sql(
        "DELETE FROM public.learning_sessions", succeeds=False
    )
    assert "42501" in sessions.sql(
        "UPDATE public.learning_sessions SET state='ACTIVE'", succeeds=False
    )
    assert "42501" in sessions.sql(
        "SELECT * FROM public.learning_sessions",
        owner=None,
        role="anon",
        succeeds=False,
    )
    assert (
        sessions.sql(
            "SELECT relrowsecurity FROM pg_class WHERE oid='public.learning_sessions'::regclass",
            role="postgres",
        )
        == "t"
    )
    assert (
        sessions.sql(
            "SELECT has_function_privilege('anon','public.visualai_mutate_learning_session(text,uuid,text,integer,text,text,text[])','EXECUTE')",
            role="postgres",
        )
        == "f"
    )
    assert (
        sessions.sql(
            "SELECT has_table_privilege('authenticated','public.learning_sessions','INSERT')",
            role="postgres",
        )
        == "f"
    )
