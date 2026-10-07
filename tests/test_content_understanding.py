"""Deterministic model-double extraction and actual PostgreSQL publication/RLS tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError

from app.core.supabase import SupabaseConfig, SupabaseRuntime, SupabaseError
from app.services.content_understanding import (
    StructureProposal,
    UnderstandingError,
    understand_content,
    validate_proposal,
)
from app.services.educational_chunker import (
    ChunkPolicy,
    create_educational_chunks,
    ChunkMetadata,
)
from app.services.knowledge_models import ScopedContentUnit
from app.services.repositories.knowledge_repository import (
    KnowledgeRepository,
    KnowledgeError,
)
from app.services.repositories.source_repository import SupabaseSourceRepository
from app.services.schemas import ContentUnit, RichChunk
from app.services.security.source_scope import SourceScope
from tests.test_knowledge_database import (
    Database,
    OWNER,
    OTHER,
    database,
    literal,
    json_literal,
)
from tests.test_knowledge_repository import Bridge, NOW, URL, token

CASES = TypeAdapter(dict[str, list[str]]).validate_json(
    (Path(__file__).parent / "fixtures/educational/cases.json").read_text()
)
SCOPE = SourceScope(user_id=UUID(OWNER), source_id="educational_test", source_version=1)
OBJECT = TypeAdapter(dict[str, JsonValue])
pytestmark = pytest.mark.usefixtures("supabase_storage_mode")


def envelopes(case: str) -> list[ScopedContentUnit]:
    return [
        ScopedContentUnit(
            **SCOPE.model_dump(),
            content_id="u" + str(i),
            provenance={},
            content=ContentUnit(
                content_id="u" + str(i),
                source_id=SCOPE.source_id,
                asset_id="asset",
                modality="txt",
                text=text,
                sequence_index=i,
                heading_path=["Educational material"],
                confidence_score=0.9,
            ),
        )
        for i, text in enumerate(CASES[case])
    ]


def proposed(material: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    """Fixture provider reads only the supplied material and quotes it verbatim."""
    topics: list[JsonValue] = []
    subs: list[JsonValue] = []
    concepts: list[JsonValue] = []
    edges: list[JsonValue] = []
    names: list[str] = []
    for unit in material:
        text = unit["text"]
        cid = unit["content_id"]
        assert isinstance(text, str) and isinstance(cid, str)
        for name in ("Variables", "Linear equations", "Osmosis", "Diffusion"):
            if (
                name.casefold() + " is " in text.casefold()
                or name.casefold() + " are " in text.casefold()
            ) and name not in names:
                names.append(name)
                key = "c" + str(len(names))
                title = name
                topic = (
                    "t_math"
                    if name in ("Variables", "Linear equations")
                    else "t_" + key
                )
                # A broad label is still an actual literal source term here.
                topic_title = "Variables" if topic == "t_math" else title
                evidence = {"content_id": cid, "quote": text, "role": "DEFINITION"}
                if not any(isinstance(t, dict) and t["key"] == topic for t in topics):
                    topics.append(
                        {"key": topic, "title": topic_title, "evidence": [evidence]}
                    )
                subs.append(
                    {
                        "key": "s" + key,
                        "topic_key": topic,
                        "title": name,
                        "evidence": [evidence],
                    }
                )
                concepts.append(
                    {
                        "key": key,
                        "subtopic_key": "s" + key,
                        "name": name,
                        "definition": text,
                        "evidence": [evidence],
                    }
                )
    for unit in material:
        text = unit["text"]
        cid = unit["content_id"]
        assert isinstance(text, str) and isinstance(cid, str)
        if (
            "requires" in text.casefold()
            and "linear equations" in text.casefold()
            and "variables" in text.casefold()
        ):
            assert "Linear equations" in names and "Variables" in names
            a, b = (
                ("Linear equations", "Variables")
                if text.casefold().find("linear equations")
                < text.casefold().find("variables")
                else ("Variables", "Linear equations")
            )
            edges.append(
                {
                    "dependent_key": "c" + str(names.index(a) + 1),
                    "prerequisite_key": "c" + str(names.index(b) + 1),
                    "evidence": [
                        {
                            "content_id": cid,
                            "quote": text,
                            "role": "PREREQUISITE_EVIDENCE",
                        }
                    ],
                }
            )
    return {
        "topics": topics,
        "subtopics": subs,
        "concepts": concepts,
        "prerequisites": edges,
    }


def fixture_provider(prompt: str) -> str:
    material = TypeAdapter(list[dict[str, JsonValue]]).validate_json(
        prompt.split("SOURCE_DATA=", 1)[1].split("\nREPAIR:", 1)[0]
    )
    return json.dumps(proposed(material))


@pytest.mark.parametrize(
    "case",
    [
        "textbook",
        "multi_topic",
        "definition_example",
        "question_answer",
        "summary",
        "repeated_heading",
        "sparse",
        "formula",
        "diagram_table",
    ],
)
def test_realistic_grounded_fixtures(case: str) -> None:
    units = envelopes(case)
    result = understand_content(SCOPE, units, fixture_provider)
    assert result.structuring_model_calls == 1 and result.repair_model_calls == 0
    assert result.quality.concept_evidence_coverage == 1.0
    assert (
        result.snapshot.topics
        and result.snapshot.subtopics
        and result.snapshot.concepts
    )
    assert (
        result.snapshot == understand_content(SCOPE, units, fixture_provider).snapshot
    )
    if case == "multi_topic":
        assert (
            len(result.snapshot.topics) == 2
            and len(result.snapshot.subtopics) == 3
            and len(result.snapshot.relationships) == 1
        )
    for evidence in result.snapshot.content_concepts:
        unit = next(u for u in units if u.content_id == evidence.content_id)
        assert evidence.char_start is not None and evidence.char_end is not None
        assert unit.content.text[evidence.char_start : evidence.char_end]


@pytest.mark.parametrize(
    "bad",
    [
        "malformed",
        "hallucinated_id",
        "cycle",
        "empty",
        "owner",
        "duplicate",
        "generic_title",
        "wrong_parent",
        "unquoted",
        "unsupported_role",
    ],
)
def test_reject_and_exhaust_bounded_repair(bad: str) -> None:
    units = envelopes("cyclic" if bad == "cycle" else "multi_topic")
    body = proposed(
        [{"content_id": u.content_id, "text": u.content.text} for u in units]
    )
    if bad == "hallucinated_id":
        body["concepts"][0]["evidence"][0]["content_id"] = "foreign_id"
    if bad == "owner":
        body["user_id"] = OTHER
    if bad == "duplicate":
        body["concepts"].append(copy.deepcopy(body["concepts"][0]))
    if bad == "generic_title":
        body["topics"][0]["title"] = "General Concepts"
    if bad == "wrong_parent":
        body["concepts"][0]["subtopic_key"] = "foreign"
    if bad == "unquoted":
        body["concepts"][0]["evidence"][0][
            "quote"
        ] = "Invented theory from model memory."
    if bad == "unsupported_role":
        body["concepts"][0]["evidence"][0]["role"] = "TABLE"
    calls: list[str] = []

    def generate(prompt: str) -> str:
        calls.append(prompt)
        return (
            "broken JSON"
            if bad == "malformed"
            else "{}" if bad == "empty" else json.dumps(body)
        )

    with pytest.raises(UnderstandingError):
        understand_content(SCOPE, units, generate)
    assert len(calls) == 2


def test_repair_success_and_no_fallback() -> None:
    calls: list[str] = []

    def generate(prompt: str) -> str:
        calls.append(prompt)
        return "invalid" if len(calls) == 1 else fixture_provider(prompt)

    result = understand_content(SCOPE, envelopes("multi_topic"), generate)
    assert result.repair_model_calls == 1 and len(calls) == 2


def test_prompt_injection_and_foreign_scope_stop_before_provider() -> None:
    def forbidden(prompt: str) -> str:
        pytest.fail("Unsafe evidence reached the provider")

    with pytest.raises(UnderstandingError, match="NO_SAFE_CONTENT"):
        understand_content(SCOPE, envelopes("injection"), forbidden)
    with pytest.raises(UnderstandingError, match="NO_SAFE_CONTENT"):
        understand_content(
            SourceScope(
                user_id=UUID(OTHER), source_id=SCOPE.source_id, source_version=1
            ),
            envelopes("sparse"),
            forbidden,
        )


class PipelineBridge(Bridge):
    def __call__(self, request: httpx.Request) -> httpx.Response:
        owner = next(
            (
                o
                for o in (OWNER, OTHER)
                if request.headers.get("authorization") == "Bearer " + token(o)
            ),
            None,
        )
        if request.url.path == "/auth/v1/user" or owner is None:
            return super().__call__(request)
        if request.method == "POST" and not request.url.path.endswith(
            "visualai_commit_knowledge_snapshot"
        ):
            self.calls += 1
            body = OBJECT.validate_json(request.content)
            if request.url.path.endswith("visualai_commit_source_ingestion"):
                sql = (
                    "SELECT public.visualai_commit_source_ingestion("
                    + ",".join(
                        json_literal(body[k])
                        for k in ("p_source", "p_version", "p_units")
                    )
                    + ")"
                )
            else:
                assert request.url.path.endswith("visualai_source_index_status")
                assert isinstance(body["p_source_id"], str) and isinstance(
                    body["p_status"], str
                )
                sql = (
                    "SELECT public.visualai_source_index_status("
                    + literal(body["p_source_id"])
                    + ","
                    + str(body["p_version"])
                    + ","
                    + literal(body["p_status"])
                    + ","
                    + (
                        literal(str(body["p_error"]))
                        if body["p_error"] is not None
                        else "NULL"
                    )
                    + ")"
                )
            return httpx.Response(200, json=json.loads(self.db.sql(sql, owner=owner)))
        if request.url.params.get("select") == "*":
            self.calls += 1
            table = request.url.path.rsplit("/", 1)[-1]
            assert table in ("sources", "source_versions", "content_units")
            filters = []
            for key, value in request.url.params.items():
                if value.startswith("eq."):
                    assert key.replace("_", "").isalnum()
                    filters.append("t." + key + "=" + literal(value[3:]))
            sql = (
                "SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) FROM public."
                + table
                + " t WHERE "
                + " AND ".join(filters)
            )
            return httpx.Response(200, json=json.loads(self.db.sql(sql, owner=owner)))
        return super().__call__(request)


def test_real_atomic_publication_index_failure_retry_and_isolation(
    database: Database, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import structurer
    from app.services.ingestion.source_ingestion import (
        ingest_source,
        index_committed_source,
    )
    from app.services.ingestion.knowledge_publication import prepare_knowledge_index
    from app.db import vector_store
    from app.core.config import settings
    from app.services.ingestion.failures import SourceIndexFailed

    monkeypatch.setattr(structurer, "generate_educational_proposal", fixture_provider)
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    runtime = SupabaseRuntime(
        SupabaseConfig(URL, "public-test-key"),
        transport=httpx.MockTransport(PipelineBridge(database)),
        clock=lambda: NOW,
    )
    try:
        repo = SupabaseSourceRepository(
            runtime.verify_user(token(OWNER)), token(OWNER), runtime
        )
        path = tmp_path / "educational.txt"
        path.write_text("\n\n".join(CASES["multi_topic"]))
        captured: list[list[str]] = []

        def fail(chunks: list[RichChunk]) -> int:
            captured.append([c.chunk_id for c in chunks])
            assert (
                database.sql(
                    "SELECT knowledge_state FROM public.source_versions WHERE source_id="
                    + literal(chunks[0].source_id)
                )
                == "READY"
            )
            assert all(
                c.metadata["chunking_policy_version"] == "educational-chunks-v1"
                for c in chunks
            )
            raise RuntimeError("private downstream error")

        monkeypatch.setattr(vector_store, "upsert_chunks", fail)
        with pytest.raises(SourceIndexFailed):
            ingest_source(repo, path, path.name)
        rows = repo.list_sources()
        assert len(rows) == 2  # Includes isolated migration's historical fixture.
        record = next(r for r in rows if r.filename == path.name)
        assert record.status == "FAILED"
        before = database.sql(
            "SELECT to_jsonb(v) FROM public.source_versions v WHERE source_id="
            + literal(record.source_id)
        )
        other = SupabaseSourceRepository(
            runtime.verify_user(token(OTHER)), token(OTHER), runtime
        )
        with pytest.raises(KnowledgeError, match="NOT_FOUND"):
            prepare_knowledge_index(other, record)
        with pytest.raises(SupabaseError):
            index_committed_source(other, record)
        monkeypatch.setattr(
            structurer,
            "generate_educational_proposal",
            lambda _: pytest.fail("READY retry regenerated knowledge"),
        )
        from app.services.ingestion import source_ingestion

        monkeypatch.setattr(
            source_ingestion,
            "dispatch",
            lambda *a, **k: pytest.fail("Retry re-extracted evidence"),
        )

        def success(chunks: list[RichChunk]) -> int:
            assert captured[0] == [c.chunk_id for c in chunks]
            return len(chunks)

        monkeypatch.setattr(vector_store, "upsert_chunks", success)
        result = index_committed_source(repo, record)
        assert result["status"] == result["knowledge_state"] == "READY"
        assert result["understanding_metrics"]["structuring_model_calls"] == 0
        assert before == database.sql(
            "SELECT to_jsonb(v) FROM public.source_versions v WHERE source_id="
            + literal(record.source_id)
        )
        fresh = KnowledgeRepository(None, token(OWNER), runtime)
        data = fresh.get_complete_knowledge_map(fresh.scope(record.source_id, 1))
        units = fresh.list_scoped_content(fresh.scope(record.source_id, 1))
        chunks, quality = create_educational_chunks(
            fresh.scope(record.source_id, 1), units, data
        )
        assert (
            quality.oversized_chunks == 0
            and len(data.topics) == 2
            and len(data.relationships) == 1
        )
        for chunk in chunks:
            meta = ChunkMetadata.model_validate(chunk.metadata)
            assert (
                "\n\n".join(
                    next(u.content.text for u in units if u.content_id == s.content_id)[
                        s.char_start : s.char_end
                    ]
                    for s in meta.canonical_spans
                )
                == chunk.text
            )
        assert (
            database.sql(
                "SELECT count(*) FROM public.topics WHERE source_id="
                + literal(record.source_id)
            )
            == "2"
        )
    finally:
        runtime.close()


def test_explicit_policy_validation() -> None:
    with pytest.raises(ValidationError):
        ChunkPolicy(max_tokens=True)


@pytest.mark.parametrize(
    "text,role",
    [
        ("Osmosis is water movement.", "DEFINITION"),
        ("Water moves because solute concentrations differ.", "EXPLANATION"),
        ("Example: osmosis fills a cell.", "EXAMPLE"),
        ("Worked example: Step 1 solves x.", "WORKED_EXAMPLE"),
        ("x + 2 = 5", "FORMULA"),
        ("Step 1: isolate x.", "PROCEDURE"),
        ("Diagram: an arrow shows water.", "DIAGRAM_DESCRIPTION"),
        ("Table: each row gives a value.", "TABLE"),
        ("What is osmosis?", "QUESTION"),
        ("Answer: water moves.", "ANSWER"),
        ("Summary: water moves.", "SUMMARY"),
        ("Solving equations requires variables.", "PREREQUISITE_EVIDENCE"),
        ("Copyright notice", "GENERAL_CONTENT"),
    ],
)
def test_supported_internal_roles(text: str, role: str) -> None:
    from app.services.educational_chunker import classify_content_role

    assert classify_content_role(text) == role


def test_ambiguous_concepts_are_not_silently_merged() -> None:
    units = envelopes("ambiguous")
    body = proposed(
        [{"content_id": u.content_id, "text": u.content.text} for u in units]
    )
    duplicate = copy.deepcopy(body["concepts"][0])
    duplicate["key"] = "different_variables"
    duplicate["definition"] = units[1].content.text
    duplicate["evidence"] = [
        {
            "content_id": units[1].content_id,
            "quote": units[1].content.text,
            "role": "DEFINITION",
        }
    ]
    body["concepts"].append(duplicate)
    with pytest.raises(UnderstandingError, match="DUPLICATE_IDENTITY"):
        validate_proposal(
            SCOPE, units, StructureProposal.model_validate_json(json.dumps(body))
        )


def test_summary_citation_can_support_separate_definition_unit() -> None:
    units = envelopes("summary")
    body = proposed(
        [{"content_id": u.content_id, "text": u.content.text} for u in units]
    )
    body["topics"][0]["evidence"] = [
        {"content_id": "u1", "quote": units[1].content.text, "role": "SUMMARY"}
    ]
    snapshot, quality = validate_proposal(
        SCOPE, units, StructureProposal.model_validate_json(json.dumps(body))
    )
    assert (
        quality.topic_evidence_coverage == 1.0
        and snapshot.topics[0].provenance["evidence"][0]["content_id"] == "u1"
    )


def test_educational_index_rejects_synthetic_embeddings_before_qdrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db import vector_store
    from app.core.config import settings
    from app.core.processing_errors import ProcessingError

    monkeypatch.setattr(settings, "embedding_provider", "mock")
    monkeypatch.setattr(
        vector_store,
        "get_client",
        lambda: pytest.fail("Synthetic index reached Qdrant"),
    )
    chunk = RichChunk(
        source_id=SCOPE.source_id,
        asset_id="asset",
        text="Genuine source text",
        modality="txt",
        metadata={"chunking_policy_version": "educational-chunks-v1"},
    )
    with pytest.raises(ProcessingError, match="semantic embeddings"):
        vector_store.upsert_chunks([chunk])


def test_policy_rejects_incoherent_overlap_and_target_bounds() -> None:
    with pytest.raises(ValidationError):
        ChunkPolicy(max_tokens=64, target_tokens=80, explanatory_overlap_tokens=8)
    with pytest.raises(ValidationError):
        ChunkPolicy(max_tokens=64, target_tokens=64, explanatory_overlap_tokens=40)


def test_repair_identifies_quote_failure_without_revealing_source() -> None:
    units = envelopes("textbook")
    body = proposed(
        [{"content_id": u.content_id, "text": u.content.text} for u in units]
    )
    body["concepts"][0]["evidence"][0]["quote"] = "Fabricated missing source evidence"
    with pytest.raises(UnderstandingError) as caught:
        validate_proposal(
            SCOPE, units, StructureProposal.model_validate_json(json.dumps(body))
        )
    assert caught.value.code == "UNSUPPORTED_EVIDENCE"
    assert caught.value.detail == "QUOTE"
    assert "Fabricated" not in str(caught.value)
