import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from modules.config import PATHS
from modules.learning.schemas import LearningSessionKnowledge, now


class KnowledgeStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("AICARLS_DB", str(PATHS["root"] / "data/learning.sqlite3")))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, session_id TEXT,
                    payload TEXT NOT NULL, PRIMARY KEY(kind,id),
                    FOREIGN KEY(session_id) REFERENCES sessions(id));
                CREATE INDEX IF NOT EXISTS records_session ON records(session_id,kind);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
                    session_id UNINDEXED, chunk_id UNINDEXED, source_id UNINDEXED,
                    text, payload UNINDEXED, tokenize='porter unicode61');
                CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, payload TEXT, created REAL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, knowledge):
        knowledge.updated_at = now()
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (knowledge.session_id, knowledge.model_dump_json()))
            db.execute("DELETE FROM chunks WHERE session_id=?", (knowledge.session_id,))
            db.executemany("INSERT INTO chunks VALUES(?,?,?,?,?)", [
                (knowledge.session_id, c.chunk_id, c.source_id, c.text, c.model_dump_json())
                for c in knowledge.source_chunks])
        return knowledge

    def load(self, session_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise KeyError("Learning session not found")
        return LearningSessionKnowledge.model_validate_json(row["payload"])

    def put(self, kind, identifier, session_id, payload):
        self.load(session_id)
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?)",
                       (kind, identifier, session_id, json.dumps(payload)))
        return payload

    def get(self, kind, identifier, session_id=None):
        with self.connect() as db:
            row = db.execute("SELECT session_id,payload FROM records WHERE kind=? AND id=?",
                             (kind, identifier)).fetchone()
        if not row or (session_id and row["session_id"] != session_id):
            raise KeyError("Record not found")
        return json.loads(row["payload"])

    def list(self, kind, session_id):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM records WHERE kind=? AND session_id=? ORDER BY rowid",
                              (kind, session_id)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def retrieve(self, session_id, query, top_k=5):
        self.load(session_id)
        words = re.findall(r"\w{3,}", query.lower(), flags=re.UNICODE)[:32]
        stop = set("the and what how does explain please this that with are for".split())
        words = [w for w in words if w not in stop]
        if not words:
            return []
        expression = " OR ".join('"' + w + '"' for w in words)
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload,bm25(chunks) AS rank FROM chunks WHERE chunks MATCH ? "
                "AND session_id=? ORDER BY rank LIMIT ?",
                (expression, session_id, min(max(top_k * 3, 1), 60))).fetchall()
        items = [dict(json.loads(row["payload"]), score=-row["rank"]) for row in rows]
        items.sort(key=lambda c: (c["source_type"] == "generated", -c["score"]))
        return items[:min(max(top_k, 1), 20)]


def index_session_knowledge(session_id, knowledge):
    if knowledge.session_id != session_id:
        raise ValueError("Session mismatch")
    return KnowledgeStore().save(knowledge)
