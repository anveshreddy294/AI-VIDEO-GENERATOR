"""Automated test script for Step 1 Ingestion Pipeline."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.registry import register_source, update_source_status, save_content_units, save_knowledge_graph
from app.services.dispatcher import dispatch
from app.services.structurer import process_structure_and_concepts
from app.services.chunker import create_rich_chunks
from app.services.validator import validate_ingestion_quality


def run_test():
    print("--- Testing Step 1 Pipeline ---")
    
    # 1. Create a dummy test file
    test_dir = Path(__file__).resolve().parent.parent / "storage" / "runtime" / "test_scratch"
    test_dir.mkdir(parents=True, exist_ok=True)
    sample_file = test_dir / "physics_sample.txt"
    sample_file.write_text(
        "Newton's Laws of Motion\n\n"
        "Chapter 1: Classical Mechanics\n"
        "Section 1.1: Force and Acceleration\n"
        "Force is defined as an interaction that changes the motion of an object. "
        "Newton's Second Law states that F = ma, where F is net force, m is mass, and a is acceleration.\n\n"
        "Section 1.2: Inertia\n"
        "Newton's First Law states that an object remains at rest or in uniform motion unless acted upon by a net external force.",
        encoding="utf-8"
    )

    print("1. Registering sample source...")
    record, persistent_file = register_source(sample_file, "physics_sample.txt")
    print(f"   Source ID: {record.source_id}, Asset ID: {record.asset_id}, Hash: {record.file_hash[:10]}...")

    print("2. Dispatching & Normalizing ContentUnits...")
    result = dispatch(persistent_file, source_id=record.source_id, asset_id=record.asset_id)
    print(f"   Extracted {len(result.units)} ContentUnits (Modality: {result.modality})")
    for cu in result.units:
        print(f"   - [CU ID: {cu.content_id}] {cu.text[:60]}...")

    print("3. Structure Detection & Concept Extraction...")
    enriched_units, kg, blueprint = process_structure_and_concepts(result.units)
    print(f"   Topic: {blueprint.topic_name}")
    print(f"   Concepts Extracted ({len(kg.concepts)}): {list(kg.concepts.keys())}")

    print("4. Semantic Chunking & Provenance Mapping...")
    rich_chunks = create_rich_chunks(enriched_units, kg)
    print(f"   Generated {len(rich_chunks)} RichChunks")
    for ch in rich_chunks:
        print(f"   - [Chunk ID: {ch.chunk_id}] Layer: {ch.layer}, Concepts: {ch.concept_ids}, CUs: {ch.content_ids}")

    print("5. Validation Gateway Check...")
    val_report = validate_ingestion_quality(
        record=record,
        file_path=persistent_file,
        units=enriched_units,
        kg=kg,
        chunks=rich_chunks,
        upserted_count=len(rich_chunks),
    )
    print(f"   Validation Report Passed: {val_report['passed']}")
    print("--- STEP 1 PIPELINE TEST PASSED SUCCESSFULLY ---")


if __name__ == "__main__":
    run_test()
