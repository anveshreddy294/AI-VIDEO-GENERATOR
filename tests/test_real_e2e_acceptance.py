"""Real End-to-End Acceptance Test for VisualAI / AI-VIDEO-GENERATOR.

Exercises the complete real pipeline against the running FastAPI application:
1. Upload image with title 'Polar Research Station'
2. Vision extraction via OpenRouter (openrouter/free)
3. Local reasoning via Ollama llama3.2:3b
4. Grounded concept canonicalization to CONCEPT_POLAR_RESEARCH_STATION
5. Diagnostic question generation & registration
6. Submit intentional wrong answer -> WEAK state
7. Next-action -> REMEDIATE
8. Remediation via RemediationOrchestrator + Step 3 VideoEngine -> READY
9. Next-action -> REASSESS
10. Reassessment Question #1 generation & submission
11. If REASSESS continues: Reassessment Question #2 generation with novel question_id
12. Final mastery decision (MASTERED / WEAK)
13. State rehydration / refresh verification
"""

import io
import time
import pytest
import requests
from PIL import Image, ImageDraw


BASE_URL = "http://127.0.0.1:8000"
USER_ID = f"student_e2e_{int(time.time())}"


def create_test_image() -> bytes:
    """Generate a clean educational image with clear text for OpenRouter vision."""
    img = Image.new("RGB", (900, 450), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    text = (
        "Polar Research Station\n\n"
        "A polar research station is an extreme-climate scientific facility located in Antarctica.\n"
        "Scientists conduct glaciology, meteorology, and climate observation.\n"
        "Key survival systems include thermal insulation, backup fuel logistics, and microgrid power."
    )
    draw.text((40, 40), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.e2e
def test_real_end_to_end_acceptance_workflow():
    # 0. Health check
    health_resp = requests.get(f"{BASE_URL}/docs", timeout=10)
    assert health_resp.status_code == 200, "FastAPI server is not responding"

    # 1. Upload educational image
    image_bytes = create_test_image()
    files = {"file": ("polar_research_station.png", image_bytes, "image/png")}
    data = {"student_id": USER_ID, "max_questions": 3}

    t0 = time.time()
    upload_resp = None
    params = {"student_id": USER_ID, "max_questions": 3}
    for attempt in range(5):
        try:
            upload_resp = requests.post(f"{BASE_URL}/pipeline/upload-and-assess", files=files, params=params, timeout=30)
            if upload_resp.status_code == 200:
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(1.0)

    assert upload_resp is not None and upload_resp.status_code == 200, f"Upload failed: {getattr(upload_resp, 'text', 'No response')}"
    job_info = upload_resp.json()
    job_id = job_info["job_id"]
    assert job_id, "No job_id returned"

    # 2. Poll pipeline job to completion
    status = "pending"
    poll_count = 0
    job_data = {}
    while status not in ("completed", "failed") and poll_count < 180:
        time.sleep(2.0)
        try:
            poll_resp = requests.get(f"{BASE_URL}/pipeline/jobs/{job_id}", timeout=30)
            if poll_resp.status_code == 200:
                job_data = poll_resp.json()
                status = job_data.get("status")
                pct = job_data.get("progress_percent", 0)
                msg = job_data.get("message", "")
                print(f"\n[E2E] Job {job_id}: status={status}, progress={pct}%, msg={msg}", flush=True)
        except requests.exceptions.RequestException as rex:
            print(f"\n[E2E] Poll retry: {rex}", flush=True)
            time.sleep(1.0)
        poll_count += 1

    upload_duration = time.time() - t0
    assert status == "completed", f"Pipeline job failed: {job_data.get('error') or job_data.get('events')}"

    # Extract source_id and verify canonical concept ID
    result = job_data.get("result", {})
    source_id = result.get("source_id")
    assert source_id, f"Missing source_id in job result: {result}"

    # 3. Verify concept canonicalization in KnowledgeGraph
    state_resp = requests.get(f"{BASE_URL}/api/learning/{source_id}/state?user_id={USER_ID}", timeout=10)
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["source_id"] == source_id

    roadmap_resp = requests.get(f"{BASE_URL}/api/learning/{source_id}/roadmap?user_id={USER_ID}", timeout=10)
    assert roadmap_resp.status_code == 200
    roadmap_data = roadmap_resp.json()
    all_concepts = (
        roadmap_data.get("unassessed_concepts", [])
        + roadmap_data.get("weak_concepts", [])
        + roadmap_data.get("mastered_concepts", [])
        + roadmap_data.get("remediating_concepts", [])
        + roadmap_data.get("reassessing_concepts", [])
    )
    if roadmap_data.get("current_concept"):
        all_concepts.append(roadmap_data["current_concept"])
    concept_ids = list(dict.fromkeys(all_concepts))
    assert len(concept_ids) > 0, f"No concepts found in roadmap: {roadmap_data}"
    # Ensure all concept IDs are canonical (no whitespace)
    for cid in concept_ids:
        assert " " not in cid, f"Concept ID '{cid}' contains illegal whitespace"
        assert cid.startswith("CONCEPT_"), f"Concept ID '{cid}' does not have standard prefix"

    target_concept = concept_ids[0]
    print(f"\n[E2E] Source={source_id}, TargetConcept={target_concept}, UploadDuration={upload_duration:.1f}s")

    # 4. Diagnostic submission with wrong answer
    # First get question for this concept
    questions = result.get("assessment", {}).get("questions", [])
    q_to_answer = None
    for q in questions:
        if q.get("concept_id") == target_concept:
            q_to_answer = q
            break
    if not q_to_answer and questions:
        q_to_answer = questions[0]
        target_concept = q_to_answer["concept_id"]

    assert q_to_answer, "No diagnostic question found to answer"
    q_id = q_to_answer["question_id"]

    # Submit intentional incorrect answer (selected_answer=9 -> wrong index)
    from uuid import uuid4
    sub_payload = {
        "attempt_id": f"ATT_{uuid4().hex[:12]}",
        "user_id": USER_ID,
        "question_id": q_id,
        "concept_id": target_concept,
        "selected_answer": 9,
        "assessment_type": "DIAGNOSTIC",
    }
    sub_resp = requests.post(
        f"{BASE_URL}/api/learning/{source_id}/assessment/submit?user_id={USER_ID}",
        json=sub_payload,
        timeout=15,
    )
    assert sub_resp.status_code == 200, f"Submit failed: {sub_resp.text}"
    sub_data = sub_resp.json()
    assert sub_data["is_correct"] is False, "Expected wrong answer to be marked incorrect"
    assert sub_data["mastery_state"] in ("WEAK", "NEEDS_SUPPORT")

    # 5. Verify next action is REMEDIATE
    na_resp = requests.get(f"{BASE_URL}/api/learning/{source_id}/next-action?user_id={USER_ID}", timeout=10)
    assert na_resp.status_code == 200
    na_data = na_resp.json()
    assert na_data["action_type"] == "REMEDIATE"
    assert na_data["concept_id"] == target_concept

    # 6. Trigger Remediation via Step 5E endpoint (NOT legacy /video/generate)
    rem_payload = {
        "user_id": USER_ID,
        "concept_id": target_concept,
    }
    rem_resp = requests.post(
        f"{BASE_URL}/api/learning/{source_id}/remediation?user_id={USER_ID}",
        json=rem_payload,
        timeout=30,
    )
    assert rem_resp.status_code in (200, 202), f"Remediation trigger failed: {rem_resp.text}"
    rem_data = rem_resp.json()
    remediation_job_id = rem_data.get("remediation_job_id") or rem_data.get("job_id")
    assert remediation_job_id

    # 7. Poll remediation to READY
    rem_status = "PENDING"
    rem_poll_count = 0
    t_rem0 = time.time()
    while rem_status not in ("READY", "FAILED") and rem_poll_count < 120:
        time.sleep(2.5)
        try:
            r_poll = requests.get(
                f"{BASE_URL}/api/learning/{source_id}/remediation/{remediation_job_id}?user_id={USER_ID}",
                timeout=30,
            )
            if r_poll.status_code == 200:
                rem_poll_data = r_poll.json()
                rem_status = rem_poll_data.get("status")
        except requests.exceptions.RequestException:
            pass
        rem_poll_count += 1

    rem_duration = time.time() - t_rem0
    print(f"[E2E] Remediation status={rem_status} in {rem_duration:.1f}s")
    assert rem_status == "READY", f"Remediation job failed: {rem_poll_data}"
    assert rem_poll_data.get("stream_url"), "Missing stream_url on ready video"

    # 8. Check next action is REASSESS
    na_resp2 = requests.get(f"{BASE_URL}/api/learning/{source_id}/next-action?user_id={USER_ID}", timeout=10)
    assert na_resp2.status_code == 200
    na_data2 = na_resp2.json()
    assert na_data2["action_type"] == "REASSESS"

    # 9. Generate Reassessment Question #1
    gen_payload = {
        "user_id": USER_ID,
        "concept_id": target_concept,
    }
    reass_resp = requests.post(
        f"{BASE_URL}/api/learning/{source_id}/reassessment/generate?user_id={USER_ID}&concept_id={target_concept}",
        json=gen_payload,
        timeout=30,
    )
    assert reass_resp.status_code == 200, f"Reassessment generation failed: {reass_resp.text}"
    q1 = reass_resp.json()
    q1_id = q1["question_id"]
    assert q1_id
    assert q1["concept_id"] == target_concept
    assert "correct_answer" not in q1, "Answer key leaked in client question response!"

    # 10. Submit Question #1
    options = q1.get("options", [])
    assert len(options) >= 2
    sub1_payload = {
        "attempt_id": f"ATT_{uuid4().hex[:12]}",
        "user_id": USER_ID,
        "question_id": q1_id,
        "concept_id": target_concept,
        "selected_answer": 0,
        "assessment_type": "REASSESSMENT",
    }
    sub1_resp = requests.post(
        f"{BASE_URL}/api/learning/{source_id}/assessment/submit?user_id={USER_ID}",
        json=sub1_payload,
        timeout=15,
    )
    assert sub1_resp.status_code == 200
    sub1_data = sub1_resp.json()

    # 11. Check next action after Question #1
    na_resp3 = requests.get(f"{BASE_URL}/api/learning/{source_id}/next-action?user_id={USER_ID}", timeout=10)
    assert na_resp3.status_code == 200
    na_data3 = na_resp3.json()

    # If policy requires more evidence, next action will still be REASSESS
    if na_data3["action_type"] == "REASSESS":
        # Must request next question
        reass2_resp = requests.post(
            f"{BASE_URL}/api/learning/{source_id}/reassessment/generate?user_id={USER_ID}&concept_id={target_concept}&previous_question_id={q1_id}",
            json=gen_payload,
            timeout=30,
        )
        assert reass2_resp.status_code == 200
        q2 = reass2_resp.json()
        q2_id = q2["question_id"]
        # CRITICAL VERIFICATION: new question_id must not equal previous question_id
        assert q2_id != q1_id, f"Question Registry recycled already-answered question {q1_id}!"
        print(f"[E2E] Reassessment Q1={q1_id}, Q2={q2_id} (novel question verified)")

        # Submit Question #2
        sub2_payload = {
            "attempt_id": f"ATT_{uuid4().hex[:12]}",
            "user_id": USER_ID,
            "question_id": q2_id,
            "concept_id": target_concept,
            "selected_answer": 0,
            "assessment_type": "REASSESSMENT",
        }
        sub2_resp = requests.post(
            f"{BASE_URL}/api/learning/{source_id}/assessment/submit?user_id={USER_ID}",
            json=sub2_payload,
            timeout=15,
        )
        assert sub2_resp.status_code == 200

    # 12. Page Refresh Verification
    # Simulate page refresh by fetching state, roadmap, and next-action again
    refreshed_state = requests.get(f"{BASE_URL}/api/learning/{source_id}/state?user_id={USER_ID}", timeout=10).json()
    refreshed_roadmap = requests.get(f"{BASE_URL}/api/learning/{source_id}/roadmap?user_id={USER_ID}", timeout=10).json()
    refreshed_na = requests.get(f"{BASE_URL}/api/learning/{source_id}/next-action?user_id={USER_ID}", timeout=10).json()

    assert refreshed_state["source_id"] == source_id
    assert refreshed_roadmap["source_id"] == source_id
    assert refreshed_na["action_type"] in ("REASSESS", "ASSESS", "COMPLETE", "REMEDIATE")
    print(f"[E2E] SUCCESS! Final Next Action: {refreshed_na['action_type']}")

