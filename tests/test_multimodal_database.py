"""Actual migrated PostgreSQL visual provenance and owner policy acceptance."""

from uuid import uuid4
from tests.test_knowledge_database import (
    Database,
    Json,
    OWNER,
    OTHER,
    database,
    json_literal,
    literal,
)


def test_visual_rpc_provenance_exact_version_and_rls(database: Database) -> None:
    source = "visual_" + uuid4().hex
    provenance: dict[str, Json] = {
        "visual_schema_version": "visual-v2",
        "provider": "ollama",
        "model": "actual-model",
        "visual_index": 0,
        "semantic_kind": "DIAGRAM",
        "validation_state": "VALIDATED",
    }
    unit: dict[str, Json] = dict(
        content_id="visual1",
        source_id=source,
        source_version=1,
        user_id=OWNER,
        asset_id=source,
        layer="A",
        modality="image",
        text="Water moves through a cell membrane by osmosis.",
        sequence_index=0,
        heading_path=[],
        extraction_method="vision_ollama",
        confidence_score=0.9,
        provenance=provenance,
    )
    source_row: dict[str, Json] = dict(
        source_id=source,
        user_id=OWNER,
        asset_id=source,
        upload_id=source,
        filename="diagram.png",
        source_type="image",
        mime_type="image/png",
        file_hash=source,
        file_size=50,
        version=1,
        source_version="v1",
        parser_version="v1",
        sanitization_version="v1",
        status="INDEXING",
    )
    version: dict[str, Json] = dict(
        user_id=OWNER,
        source_id=source,
        version=1,
        source_version="v1",
        file_hash=source,
        filename="diagram.png",
        file_location="test-only/diagram.png",
        provenance={},
        normalized_content=[unit],
        sanitized_content=[unit],
        quarantined_content=[],
        rich_chunks=[
            dict(
                user_id=OWNER,
                source_id=source,
                asset_id=source,
                source_version="v1",
                source_type="image",
                content_id="visual1",
                content_ids=["visual1"],
                text=unit["text"],
            )
        ],
    )
    sql = f"SELECT public.visualai_commit_source_ingestion({json_literal(source_row)}, {json_literal(version)}, {json_literal([unit])})"
    database.sql(sql)
    database.sql(sql)
    scope = f"source_id={literal(source)} AND source_version=1"
    assert (
        database.sql(f"SELECT count(*) FROM public.content_units WHERE {scope}") == "1"
    )
    assert (
        database.sql(
            f"SELECT provenance->>'model' FROM public.content_units WHERE {scope}"
        )
        == "actual-model"
    )
    assert (
        database.sql(
            f"SELECT count(*) FROM public.content_units WHERE {scope}", owner=OTHER
        )
        == "0"
    )
    assert (
        database.sql(
            f"SELECT count(*) FROM public.content_units WHERE source_id={literal(source)} AND source_version=2"
        )
        == "0"
    )
    assert "permission denied" in database.sql(
        f"SELECT * FROM public.content_units WHERE {scope}",
        role="anon",
        owner=None,
        succeeds=False,
    )
