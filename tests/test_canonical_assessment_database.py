"""Optional real PostgreSQL transaction/grant tests. Never install or use a remote DSN."""

from __future__ import annotations
import json
from pathlib import Path
from uuid import uuid4
import pytest
from tests.test_knowledge_database import Database, literal, OWNER, OTHER
from tests.test_learning_session_database import sessions, database, ready, rpc


@pytest.fixture(scope="module")
def assessment_db(sessions: Database) -> Database:
    sessions.sql(
        Path("migrations/20261008090000_session_assessments.sql").read_text(
            encoding="utf-8"
        ),
        role="postgres",
        owner=None,
    )
    return sessions


def transaction(
    db: Database,
    action: str,
    owner: str,
    key: str,
    body: dict,
    *,
    role: str = "service_role",
    succeeds: bool = True,
) -> str:
    return db.sql(
        "SELECT public.visualai_assessment_transaction("
        + ",".join(
            [
                literal(action),
                literal(owner) + "::uuid",
                literal(key),
                literal(json.dumps(body)) + "::jsonb",
            ]
        )
        + ")",
        role=role,
        owner=owner,
        succeeds=succeeds,
    )


def test_transaction_rollback_grants_idempotency_and_grading(
    assessment_db: Database,
) -> None:
    db = assessment_db
    source = ready(db)
    sid = str(uuid4())
    key = "ASSESS_" + uuid4().hex
    db.sql(rpc("create", sid, source))
    question = {
        "question_id": "Q_" + uuid4().hex,
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
        "questions": [question],
    }
    transaction(db, "load", OWNER, key, {}, role="authenticated", succeeds=False)
    broken = {
        **payload,
        "questions": [
            question,
            {**question, "question_id": "foreign", "concept_id": "foreign"},
        ],
        "concept_queue": ["c1", "c1"],
    }
    transaction(db, "create", OWNER, key, broken, succeeds=False)
    assert transaction(db, "load", OWNER, key, {}) == ""
    created = json.loads(transaction(db, "create", OWNER, key, payload))
    assert created["learning_session_id"] == sid and len(created["questions"]) == 1
    assert json.loads(transaction(db, "create", OWNER, key, payload)) == created
    transaction(
        db, "create", OWNER, key, {**payload, "request_hash": "b" * 64}, succeeds=False
    )
    assert transaction(db, "load", OTHER, key, {}) == ""
    submission = {"answers": {question["question_id"]: 0}}
    saved = json.loads(transaction(db, "submit", OWNER, key, submission))
    assert saved["submission_response"]["overall_score"] == 100
    assert json.loads(transaction(db, "submit", OWNER, key, submission)) == saved
    assert (
        db.sql(
            "SELECT count(*) FROM public.assessment_attempts WHERE session_id="
            + literal(key),
            role="postgres",
            owner=None,
        )
        == "1"
    )
    transaction(
        db,
        "submit",
        OWNER,
        key,
        {"answers": {question["question_id"]: 1}},
        succeeds=False,
    )
    assert "correct_index" not in json.dumps(saved["submission_response"])
