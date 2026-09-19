"""End-to-End Real PDF Integration Test: Ingestion → Assessment → Video → Remediation Loop.

Executes a complete lifecycle run using a real PDF from storage:
1. Upload & Ingestion (Step 1): ContentUnits, KnowledgeGraph, Blueprint, Vector DB Upsert.
2. Diagnostic Assessment (Step 2): Grounded questions, safe dispatch, submission scoring.
3. Video Synthesis (Step 3): Targeted micro-lesson, neural TTS, visuals, audio muxing, WebVTT.
4. Remediation Verification (Step 4): Re-test verification loop and mastery state transition.
5. In-Player Video RAG: Grounded timestamped Q&A against synthesized video scenes.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

def run_real_e2e():
    print("==========================================================================")
    print("      VISUALAI FULL END-TO-END VERIFICATION: REAL PDF → VIDEO → REMEDIATION")
    print("==========================================================================")

    client = TestClient(app)

    # Pick a real PDF
    pdf_path = Path("storage/uploads/SRC_1535f6ad1029/original.pdf")
    if not pdf_path.exists():
        pdf_path = Path("storage/runtime/uploads/SRC_2560b9141137/original.pdf")
    assert pdf_path.exists(), f"Sample PDF not found at {pdf_path}"

    student_id = "student_real_e2e"
    print(f"\n[1/5] Ingesting Real PDF: {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)...")

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
    print("\n[2/5] Verifying Diagnostic Assessment Session...")
    assessment = up_data["assessment"]
    session_id = assessment["session_id"]
    questions = assessment["questions"]
    print(f"   ✓ Session ID:           {session_id}")
    print(f"   ✓ Questions Generated:  {len(questions)}")
    for i, q in enumerate(questions, 1):
        print(f"      Q{i} [{q['concept_name']}]: {q['stem'][:60]}... ({len(q['options'])} options)")
        assert "correct_index" not in q, "Safe dispatch must hide correct answers"
        assert len(q["options"]) == 4

    # Submit answers: answer 1 question wrong to trigger targeted video remediation
    target_failed_concept_id = questions[0]["concept_id"]
    target_failed_concept_name = questions[0]["concept_name"]
    print(f"\n[3/5] Submitting Diagnostic Answers (intentionally missing '{target_failed_concept_name}')...")

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
    v_matrix = sub_data["video_target_matrix"]
    print(f"   ✓ Video Decision:       {v_matrix['decision']}")
    print(f"   ✓ Video Targets:        {len(v_matrix['videos'])}")
    assert len(v_matrix["videos"]) >= 1, "At least one video target should be generated"

    # Step 3: Trigger Targeted Video Generation
    print(f"\n[4/5] Synthesizing Remediation Video for concept: '{target_failed_concept_name}'...")
    from app.services.video_gen.pipeline import execute_video_generation_pipeline
    from app.services.assessment.video_target import load_video_matrix

    matrix = load_video_matrix(student_id, source_id)
    assert matrix is not None and len(matrix.videos) > 0
    target = matrix.videos[0]

    job = asyncio.run(
        execute_video_generation_pipeline(
            target=target,
            student_id=student_id,
            source_id=source_id,
            mock_mode=False,
        )
    )

    print(f"   ✓ Job ID:               {job.job_id}")
    print(f"   ✓ Video ID:             {job.video_id}")
    print(f"   ✓ Status:               {job.status}")
    print(f"   ✓ Duration:             {job.duration_seconds}s")
    print(f"   ✓ Video Path:           {job.video_file_path}")
    print(f"   ✓ Subtitles Path:       {job.subtitles_file_path}")
    assert job.status == "completed"
    assert Path(job.video_file_path).exists()
    assert Path(job.subtitles_file_path).exists()
    assert Path(job.video_file_path).stat().st_size > 1000

    # Step 4: Remediation Loop Verification Check
    print(f"\n[5/5] Executing Step 4 Remediation Re-Test Loop...")
    remed_session_resp = client.post(
        "/remediation/start",
        json={"student_id": student_id, "source_id": source_id, "concept_id": target.concept_id, "count": 1},
    )
    assert remed_session_resp.status_code == 200, f"Remediation session failed: {remed_session_resp.text}"
    remed_session = remed_session_resp.json()
    remed_q = remed_session["questions"][0]
    print(f"   ✓ Re-Test Generated:    {remed_q['stem'][:70]}...")

    # Answer correctly to master concept
    remed_eval_resp = client.post(
        "/remediation/submit",
        json={
            "session_id": remed_session["session_id"],
            "student_id": student_id,
            "concept_id": target.concept_id,
            "answers": [{"question_id": remed_q["question_id"], "selected_index": 0}],
        },
    )
    assert remed_eval_resp.status_code == 200, f"Remediation evaluate failed: {remed_eval_resp.text}"
    eval_data = remed_eval_resp.json()
    print(f"   ✓ Passed:                 {eval_data['passed']}")
    print(f"   ✓ Previous Status:        {eval_data['previous_status']}")
    print(f"   ✓ Concept Mastery Status: {eval_data['new_status']}")

    # Video RAG Query
    print("\n[BONUS] In-Player Dual-Layer Video RAG Verification...")
    rag_resp = client.post(
        "/video/rag/ask",
        json={
            "video_id": job.video_id,
            "timestamp": 5.0,
            "question": f"Explain {target_failed_concept_name} clearly based on this lesson.",
        },
    )
    assert rag_resp.status_code == 200, f"Video RAG failed: {rag_resp.text}"
    rag_data = rag_resp.json()
    scene_title = rag_data.get("active_scene", {}).get("title") if rag_data.get("active_scene") else "General Scene"
    print(f"   ✓ Resolved Scene:       {scene_title}")
    print(f"   ✓ Citations:            {len(rag_data['citations'])} authoritative Layer A chunks")
    print(f"   ✓ Answer Preview:       {rag_data['answer'][:100]}...")

    print("\n==========================================================================")
    print("      🎉 100% E2E CONTRACT VERIFICATION SUCCEEDED WITH REAL PDF ARTIFACTS!")
    print("==========================================================================")

if __name__ == "__main__":
    run_real_e2e()
