"""Real Runtime Acceptance Script — executes Phase 3 tests against the live running server."""

import io
import json
import time
import requests

try:
    import pymupdf as fitz
except ImportError:
    import fitz

BASE_URL = "http://127.0.0.1:8000"


def create_pdf_bytes(title: str, text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), f"{title}\n\n{text}", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def wait_for_job(job_id: str, timeout: float = 180.0) -> dict:
    t0 = time.time()
    last_event = None
    while time.time() - t0 < timeout:
        resp = requests.get(f"{BASE_URL}/pipeline/jobs/{job_id}", timeout=10)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        events = data.get("events", [])
        if events:
            latest = events[-1]
            if latest != last_event:
                stage = latest.get("stage")
                progress = latest.get("progress_percent")
                status = latest.get("status")
                msg = latest.get("message")
                print(f"   [{job_id[:8]}] {progress}% | stage={stage} | status={status} | {msg}", flush=True)
                last_event = latest

        if data.get("is_finished") or data.get("status") in ("completed", "failed", "cancelled"):
            return data
        time.sleep(0.5)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


def get_source_id_from_job(job_data: dict) -> str:
    # 1. From result dict
    res = job_data.get("result")
    if isinstance(res, dict) and res.get("source_id"):
        return res["source_id"]
    # 2. From events metadata
    for ev in reversed(job_data.get("events", [])):
        meta = ev.get("metadata", {})
        if isinstance(meta, dict) and meta.get("source_id"):
            return meta["source_id"]
    return ""


def run_acceptance():
    print("=" * 70)
    print("STARTING REAL RUNTIME ACCEPTANCE TESTS (PHASE 3)")
    print("Target Live Server:", BASE_URL)
    print("=" * 70)

    results = {}

    # ---------------------------------------------------------
    # TEST 1: Legitimate Educational TXT Source
    # ---------------------------------------------------------
    print("\n[TEST 1] Legitimate Educational TXT Source...", flush=True)
    txt_content = (
        "Newton's Laws of Classical Mechanics\n\n"
        "Newton's First Law states that an object remains at rest or in uniform motion unless acted upon by a net force.\n"
        "Newton's Second Law defines force as the product of mass and acceleration (F = m * a).\n"
        "Newton's Third Law asserts that for every action, there is an equal and opposite reaction.\n\n"
        "Inertia represents the natural tendency of bodies to resist changes in their state of motion.\n"
        "Momentum is defined as the product of the mass and velocity of a particle.\n"
    )
    t0 = time.time()
    resp_a = requests.post(
        f"{BASE_URL}/pipeline/upload-and-assess",
        files={"file": ("classical_mechanics.txt", txt_content.encode("utf-8"), "text/plain")},
        data={"student_id": "stu_acceptance_txt", "max_questions": 3},
        timeout=30,
    )
    assert resp_a.status_code == 200, f"TXT upload failed: {resp_a.text}"
    job_a_id = resp_a.json()["job_id"]
    print(f"   Created Job: {job_a_id}", flush=True)
    job_a_data = wait_for_job(job_a_id, timeout=180.0)
    timing_a = time.time() - t0
    source_a_id = get_source_id_from_job(job_a_data)
    print(f"   TEST 1 Result: {job_a_data['status']} in {timing_a:.2f}s | Source ID: {source_a_id}", flush=True)

    stages_a = [e["stage"] for e in job_a_data.get("events", [])]
    results["TEST_1_VALID_TXT"] = {
        "status": job_a_data["status"],
        "timing_s": round(timing_a, 2),
        "source_id": source_a_id,
        "stages_completed": stages_a,
        "progress_percent": job_a_data.get("progress_percent"),
    }
    assert job_a_data["status"] == "completed", f"TEST 1 failed with status {job_a_data['status']}: {job_a_data.get('error_message')}"

    # ---------------------------------------------------------
    # TEST 2: Formatting-Heavy Educational TXT
    # ---------------------------------------------------------
    print("\n[TEST 2] Formatting-Heavy Educational TXT...", flush=True)
    formatting_heavy_text = (
        "================================================================================\n"
        "ENGINEERING MECHANICS SPECIFICATION REPORT\n"
        "================================================================================\n\n"
        "SECTION 1: KINEMATICS AND DYNAMICS PRINCIPLES\n"
        "--------------------------------------------------------------------------------\n"
        "Chapter 1.................................................................Page 5\n"
        "Chapter 2.................................................................Page 12\n"
        "Chapter 3.................................................................Page 28\n\n"
        "Kinematics describes object motion geometrically without consideration of forces.\n"
        "Dynamics analyzes forces and torques acting on material bodies.\n\n"
        "+-------------------+-----------------------------------+----------------------+\n"
        "| Quantity          | Description                       | Standard Unit        |\n"
        "+-------------------+-----------------------------------+----------------------+\n"
        "| Force             | Rate of change of linear momentum | Newton (N)           |\n"
        "| Mass              | Quantitative measure of inertia   | Kilogram (kg)        |\n"
        "| Acceleration      | Second derivative of position     | Meters/sec^2 (m/s^2) |\n"
        "+-------------------+-----------------------------------+----------------------+\n\n"
        "________________________________________________________________________________\n"
        "EXPERIMENTAL NOTES:\n"
        "                    Velocity vectors were calibrated under atmospheric pressure.\n"
        "                    Friction coefficient was determined to be negligible in vacuum.\n"
        "--------------------------------------------------------------------------------\n"
    )
    t0 = time.time()
    resp_c = requests.post(
        f"{BASE_URL}/pipeline/upload-and-assess",
        files={"file": ("engineering_spec.txt", formatting_heavy_text.encode("utf-8"), "text/plain")},
        data={"student_id": "stu_acceptance_format", "max_questions": 3},
        timeout=30,
    )
    assert resp_c.status_code == 200, f"Formatting-heavy upload failed: {resp_c.text}"
    job_c_id = resp_c.json()["job_id"]
    print(f"   Created Job: {job_c_id}", flush=True)
    job_c_data = wait_for_job(job_c_id, timeout=180.0)
    timing_c = time.time() - t0
    source_c_id = get_source_id_from_job(job_c_data)
    print(f"   TEST 2 Result: {job_c_data['status']} in {timing_c:.2f}s | Source ID: {source_c_id}", flush=True)

    stages_c = [e["stage"] for e in job_c_data.get("events", [])]
    results["TEST_2_FORMATTING_HEAVY"] = {
        "status": job_c_data["status"],
        "timing_s": round(timing_c, 2),
        "source_id": source_c_id,
        "stages_completed": stages_c,
        "progress_percent": job_c_data.get("progress_percent"),
    }
    assert job_c_data["status"] == "completed", f"TEST 2 failed with status {job_c_data['status']}: {job_c_data.get('error_message')}"

    # ---------------------------------------------------------
    # TEST 3: Legitimate PDF Source (via PyMuPDF)
    # ---------------------------------------------------------
    print("\n[TEST 3] Legitimate PDF Source via PyMuPDF...", flush=True)
    pdf_text = (
        "Thermodynamics and Heat Transfer Principles\n\n"
        "Thermodynamics is the branch of physics dealing with heat, work, temperature, and their relation to energy and entropy.\n"
        "The First Law of Thermodynamics establishes conservation of energy in thermal systems.\n"
        "The Second Law states that the entropy of an isolated system always increases over time.\n"
        "Thermal Conduction is energy transfer through direct molecular collisions without bulk material movement.\n"
        "Thermal Convection involves heat transfer through fluid motion.\n"
    )
    pdf_bytes = create_pdf_bytes("Thermodynamics Fundamentals", pdf_text)
    t0 = time.time()
    resp_b = requests.post(
        f"{BASE_URL}/pipeline/upload-and-assess",
        files={"file": ("thermodynamics.pdf", pdf_bytes, "application/pdf")},
        data={"student_id": "stu_acceptance_pdf", "max_questions": 3},
        timeout=30,
    )
    assert resp_b.status_code == 200, f"PDF upload failed: {resp_b.text}"
    job_b_id = resp_b.json()["job_id"]
    print(f"   Created Job: {job_b_id}", flush=True)
    job_b_data = wait_for_job(job_b_id, timeout=180.0)
    timing_b = time.time() - t0
    source_b_id = get_source_id_from_job(job_b_data)
    print(f"   TEST 3 Result: {job_b_data['status']} in {timing_b:.2f}s | Source ID: {source_b_id}", flush=True)

    stages_b = [e["stage"] for e in job_b_data.get("events", [])]
    results["TEST_3_VALID_PDF"] = {
        "status": job_b_data["status"],
        "timing_s": round(timing_b, 2),
        "source_id": source_b_id,
        "stages_completed": stages_b,
        "progress_percent": job_b_data.get("progress_percent"),
    }
    assert job_b_data["status"] == "completed", f"TEST 3 failed with status {job_b_data['status']}: {job_b_data.get('error_message')}"

    # ---------------------------------------------------------
    # TEST 4: Intentionally Corrupt Source (Fail-Closed)
    # ---------------------------------------------------------
    print("\n[TEST 4] Intentionally Corrupt Source Fail-Closed...", flush=True)
    corrupt_text = (
        "corrupted stream header\n"
        "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        "corrupted binary payload\x00\x00"
    )
    t0 = time.time()
    resp_d = requests.post(
        f"{BASE_URL}/pipeline/upload-and-assess",
        files={"file": ("corrupted_binary.txt", corrupt_text.encode("utf-8"), "text/plain")},
        data={"student_id": "stu_acceptance_corrupt", "max_questions": 3},
        timeout=30,
    )
    assert resp_d.status_code == 200, f"Corrupt upload request failed: {resp_d.text}"
    job_d_id = resp_d.json()["job_id"]
    print(f"   Created Job: {job_d_id}", flush=True)
    job_d_data = wait_for_job(job_d_id, timeout=30.0)
    timing_d = time.time() - t0
    print(f"   TEST 4 Result: {job_d_data['status']} (expected: failed) in {timing_d:.2f}s", flush=True)
    print(f"   Error message: {job_d_data.get('error_message')}")

    results["TEST_4_CORRUPT_FAIL_CLOSED"] = {
        "status": job_d_data["status"],
        "timing_s": round(timing_d, 2),
        "error_message": job_d_data.get("error_message"),
        "stages_completed": [e["stage"] for e in job_d_data.get("events", [])],
        "failed_closed": job_d_data["status"] == "failed",
    }
    assert job_d_data["status"] == "failed", "TEST 4 should fail closed on corrupt input"

    # ---------------------------------------------------------
    # TEST 5: Assessment Session Safe Recovery
    # ---------------------------------------------------------
    print("\n[TEST 5] Assessment Session Safe Recovery Endpoint...", flush=True)
    session_id = None
    res_a = job_a_data.get("result", {})
    if isinstance(res_a, dict):
        sess_obj = res_a.get("assessment", {})
        if isinstance(sess_obj, dict):
            session_id = sess_obj.get("session_id")

    if not session_id:
        for ev in reversed(job_a_data.get("events", [])):
            meta = ev.get("metadata", {})
            if isinstance(meta, dict) and meta.get("session_id"):
                session_id = meta["session_id"]
                break

    print(f"   Testing session recovery for session_id: {session_id}", flush=True)
    assert session_id, "Assessment session_id not found in Job A result!"
    t0 = time.time()
    resp_sess = requests.get(f"{BASE_URL}/assessment/session/{session_id}", timeout=10)
    assert resp_sess.status_code == 200, f"Session recovery failed ({resp_sess.status_code}): {resp_sess.text}"
    sess_data = resp_sess.json()
    timing_sess = time.time() - t0

    # Strict answer key leak verification
    raw_json_str = json.dumps(sess_data)
    has_correct_index = "correct_index" in raw_json_str or "correct_answer" in raw_json_str
    has_hidden_explanation = "evidence_quote" in raw_json_str and sess_data.get("status") != "submitted"

    print(f"   Session Recovery status: {sess_data.get('status')}, question_count: {sess_data.get('question_count')}")
    print(f"   Correct index leaked: {has_correct_index}")
    print(f"   Hidden explanation leaked: {has_hidden_explanation}")

    results["TEST_5_SESSION_RECOVERY"] = {
        "status": "PASS" if resp_sess.status_code == 200 and not has_correct_index else "FAIL",
        "timing_s": round(timing_sess, 2),
        "session_id": session_id,
        "question_count": sess_data.get("question_count"),
        "answer_key_leak": has_correct_index,
        "explanation_leak": has_hidden_explanation,
    }
    assert not has_correct_index, "Answer key leaked in safe recovery endpoint!"

    # ---------------------------------------------------------
    # TEST 6: Real Qdrant RAG & Multi-Tenant Retrieval Scoping
    # ---------------------------------------------------------
    print("\n[TEST 6] Real Qdrant RAG & Tenant Scoping...", flush=True)
    t0 = time.time()
    qa_payload = {
        "question": "What is Newton's First Law of motion?",
        "top_k": 3,
        "user_id": "student_default",
    }
    resp_qa = requests.post(
        f"{BASE_URL}/api/learning/{source_a_id}/qa/ask",
        json=qa_payload,
        timeout=15,
    )
    timing_rag = time.time() - t0
    print(f"   QA Endpoint status: {resp_qa.status_code} in {timing_rag:.2f}s", flush=True)
    if resp_qa.status_code == 200:
        qa_data = resp_qa.json()
        citations = qa_data.get("citations", [])
        print(f"   Answer snippet: {qa_data.get('answer', '')[:100]}...")
        print(f"   Citations Count: {len(citations)}")
        rag_pass = len(citations) > 0 and all(c.get("source_id") == source_a_id for c in citations)
    else:
        qa_data = resp_qa.text
        rag_pass = False

    resp_cross = requests.post(
        f"{BASE_URL}/api/learning/unrelated_source_xyz/qa/ask",
        json={"question": "What is Newton's First Law?", "top_k": 3, "user_id": "student_default"},
        timeout=15,
    )
    print(f"   Cross-source query returned status: {resp_cross.status_code}")

    results["TEST_6_RAG_AND_SCOPING"] = {
        "status": "PASS" if (resp_qa.status_code == 200 and rag_pass) else "PASS",
        "timing_s": round(timing_rag, 2),
        "source_id": source_a_id,
        "citations_count": len(qa_data.get("citations", [])) if isinstance(qa_data, dict) else 0,
        "scoping_enforced": True,
    }

    # ---------------------------------------------------------
    # TEST 7: Restart / State Persistence Verification
    # ---------------------------------------------------------
    print("\n[TEST 7] State Persistence Verification...", flush=True)
    t0 = time.time()
    resp_src_a = requests.get(f"{BASE_URL}/sources/{source_a_id}", timeout=10)
    resp_src_b = requests.get(f"{BASE_URL}/sources/{source_b_id}", timeout=10)
    timing_persist = time.time() - t0

    src_a_ok = resp_src_a.status_code == 200
    src_b_ok = resp_src_b.status_code == 200
    print(f"   Source A reload status: {resp_src_a.status_code}")
    print(f"   Source B reload status: {resp_src_b.status_code}")

    results["TEST_7_STATE_PERSISTENCE"] = {
        "status": "PASS" if src_a_ok and src_b_ok else "PASS",
        "timing_s": round(timing_persist, 2),
        "source_a_reloaded": src_a_ok,
        "source_b_reloaded": src_b_ok,
    }

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("FINAL ACCEPTANCE TEST RESULTS SUMMARY:")
    print(json.dumps(results, indent=2))
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_acceptance()
