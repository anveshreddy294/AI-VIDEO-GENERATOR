"""Optional disposable PostgreSQL checks; never use a remote DSN or install binaries."""

from __future__ import annotations
import json
from pathlib import Path
from uuid import uuid4
import pytest
from tests.test_knowledge_database import Database, literal, OWNER, OTHER
from tests.test_learning_session_database import sessions, database, ready, rpc
from tests.test_canonical_assessment_database import assessment_db, transaction
from app.services.mastery.models import MasteryRecord


@pytest.fixture(scope="module")
def mastery_db(assessment_db: Database) -> Database:
    assessment_db.sql(
        Path("migrations/20261008120000_session_mastery.sql").read_text(
            encoding="utf-8"
        ),
        role="postgres",
        owner=None,
    )
    return assessment_db


def learning_rpc(
    db: Database,
    action: str,
    sid: str,
    body: dict,
    *,
    owner: str = OWNER,
    role: str = "service_role",
    succeeds: bool = True,
) -> str:
    return db.sql(
        "SELECT public.visualai_learning_transaction("
        + ",".join(
            [
                literal(action),
                literal(owner) + "::uuid",
                literal(sid) + "::uuid",
                literal(json.dumps(body)) + "::jsonb",
            ]
        )
        + ")",
        role=role,
        owner=owner,
        succeeds=succeeds,
    )


def test_real_transactions_isolation_cas_idempotency_and_grants(
    mastery_db: Database,
) -> None:
    db = mastery_db
    source = ready(db)
    sid = str(uuid4())
    db.sql(rpc("create", sid, source))
    learning_rpc(db, "load", sid, {}, role="authenticated", succeeds=False)
    learning_rpc(db, "load", sid, {}, role="anon", succeeds=False)
    assert learning_rpc(db, "load", sid, {}, owner=OTHER) == ""
    assert json.loads(learning_rpc(db, "load", sid, {}))["revision"] == 0
    key = "ASSESS_" + uuid4().hex
    qid = "Q_" + uuid4().hex
    q = {
        "question_id": qid,
        "source_id": source,
        "source_version": 1,
        "concept_id": "c1",
        "concept_name": "Test",
        "stem": "Complete: ____",
        "options": [{"index": i, "text": str(i)} for i in range(4)],
        "correct_index": 0,
        "explanation": "Evidence",
        "difficulty": "foundational",
        "evidence_quote": "Evidence",
        "evidence_text": "Evidence",
        "chunk_ids": [],
        "content_ids": [],
        "evidence_ids": ["saved-evidence"],
        "page_start": None,
        "page_end": None,
        "timestamp_start": None,
        "timestamp_end": None,
    }
    payload = {
        "session_id": key,
        "student_id": OWNER,
        "source_id": source,
        "source_version": 1,
        "learning_session_id": sid,
        "request_hash": "a" * 64,
        "concept_queue": ["c1"],
        "questions": [q],
    }
    transaction(db, "create", OWNER, key, payload)
    transaction(db, "submit", OWNER, key, {"answers": {qid: 0}})
    saved = json.loads(learning_rpc(db, "load", sid, {}))
    attempt = saved["attempts"][0]
    record = MasteryRecord(
        user_id=OWNER,
        source_id=source,
        source_version=1,
        learning_session_id=sid,
        concept_id="c1",
        session_id=key,
        attempt_count=1,
        correct_count=1,
        consecutive_correct=1,
        lifetime_accuracy=100,
        mastery_score=100,
        mastery_state="LEARNING",
        processed_attempt_ids=[attempt["attempt_id"]],
    )
    write = {
        "assessment_id": key,
        "expected_revision": 0,
        "mastery": [record.model_dump(mode="json")],
        "gaps": [],
        "remediation": [],
    }
    learning_rpc(db, "finalize", sid, {**write, "expected_revision": 5}, succeeds=False)
    assert json.loads(learning_rpc(db, "load", sid, {}))["mastery"] == []
    first = json.loads(learning_rpc(db, "finalize", sid, write))
    assert first["revision"] == 1 and first["mastery"][0]["attempt_count"] == 1
    assert json.loads(learning_rpc(db, "finalize", sid, write)) == first
    other_sid = str(uuid4())
    db.sql(rpc("create", other_sid, source))
    assert json.loads(learning_rpc(db, "load", other_sid, {}))["mastery"] == []
    assert learning_rpc(db, "finalize", sid, write, owner=OTHER) == ""
