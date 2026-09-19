"""End-to-End Real PDF Integration Test: Ingestion → Assessment.

Executes a complete lifecycle run using a real PDF from storage:
1. Upload & Ingestion (Step 1): ContentUnits, KnowledgeGraph, Blueprint, Vector DB Upsert.
2. Diagnostic Assessment (Step 2): Grounded questions, safe dispatch, submission scoring.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

def run_real_e2e():
    print("==========================================================================")
    print("      VISUALAI FULL END-TO-END VERIFICATION: REAL PDF → ASSESSMENT")
    print("==========================================================================")

    client = TestClient(app)

    # Pick a real PDF
    pdf_path = Path("storage/uploads/SRC_1535f6ad1029/original.pdf")
    if not pdf_path.exists():
        pdf_path = Path("storage/runtime/uploads/SRC_2560b9141137/original.pdf")
    assert pdf_path.exists(), f"Sample PDF not found at {pdf_path}"

    student_id = "student_real_e2e"
    print(f"\n[1/3] Ingesting Real PDF: {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)...")

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/upload",
            files={"file": ("classical_mechanics_sample.pdf", f, "application/pdf")},
            params={"auto_start_assessment": "true", "student_id": student_id, "max_questions": 3},
        )

    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    up_data = resp.json()
    source_id = up_data["source_id"]
    print(f"   ✓ Status:               {up_data['status']}")
    print(f"   ✓ Source ID:            {source_id}")
    print(f"   ✓ Content Units:        {up_data['content_units']}")
    print(f"   ✓ Chunks Synced:        {up_data['chunks_synced']}")
    print(f"   ✓ Concepts Extracted:   {up_data['concepts_extracted']}")
    assert up_data["status"] == "READY"
    assert up_data["chunks_synced"] > 0
    assert "assessment" in up_data, "Assessment session should be auto-started"

    # Step 2: Diagnostic Assessment
    print("\n[2/3] Verifying Diagnostic Assessment Session...")
    assessment = up_data["assessment"]
    session_id = assessment["session_id"]
    questions = assessment["questions"]
    print(f"   ✓ Session ID:           {session_id}")
    print(f"   ✓ Questions Generated:  {len(questions)}")
    for i, q in enumerate(questions, 1):
        print(f"      Q{i} [{q['concept_name']}]: {q['stem'][:60]}... ({len(q['options'])} options)")
        assert "correct_index" not in q, "Safe dispatch must hide correct answers"
        assert len(q["options"]) == 4

    # Submit answers
    print(f"\n[3/3] Submitting Diagnostic Answers...")
    answers = [
        {"question_id": questions[0]["question_id"], "selected_index": 1, "response_time_seconds": 12.5},
        {"question_id": questions[1]["question_id"], "selected_index": 0, "response_time_seconds": 9.0},
        {"question_id": questions[2]["question_id"], "selected_index": 0, "response_time_seconds": 11.0},
    ]

    sub_resp = client.post(
        "/assessment/submit",
        json={
            "student_id": student_id,
            "session_id": session_id,
            "source_id": source_id,
            "answers": answers,
        },
    )
    assert sub_resp.status_code == 200, f"Submit failed: {sub_resp.text}"
    sub_data = sub_resp.json()
    print(f"   ✓ Score:                {sub_data['score']}/{sub_data['total']} ({sub_data['percentage']}%)")

    print("\n==========================================================================")
    print("      🎉 100% E2E CONTRACT VERIFICATION SUCCEEDED WITH REAL PDF ARTIFACTS!")
    print("==========================================================================")

if __name__ == "__main__":
    run_real_e2e()
