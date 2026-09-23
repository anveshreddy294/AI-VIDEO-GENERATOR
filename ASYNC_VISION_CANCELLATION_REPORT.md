# Async Vision Extraction Concurrency & True Cancellation Repair Report

**Date:** 2026-09-23  
**Branch:** `openrouter`  
**Status:** Complete & Verified  

---

## 1. Executive Summary

This repair successfully addressed three confirmed production runtime defects:
1. **Fake Thread Cancellation:** Background threads previously continued executing in a `ThreadPoolExecutor` and processing OpenRouter responses after cancellation or server shutdown. Replaced by native `httpx.AsyncClient` coroutines that cancel immediately and close sockets cleanly.
2. **Invalid `CANCELLED` Literal in `SourceRecord`:** Fixed Pydantic `ValidationError` by implementing defensive status mapping in `app/services/registry.py` and ensuring pipeline cancellation updates source status to `"FAILED"`.
3. **Duplicate Active Jobs for Identical Files:** Eliminated race condition by introducing atomic check-and-create (`get_or_create_active_job`) under `JobManager._lock`.

---

## 2. Root Cause Analysis & Architecture Fixes

### A. True Cancellation vs Fake Thread Timeouts
- **Previous Failure:** `ThreadPoolExecutor.shutdown(wait=False, cancel_futures=True)` and future timeouts in Python do not abort blocking sockets in worker threads. When Uvicorn shut down, the worker thread remained active and emitted log lines after shutdown.
- **Solution:** Converted multimodal vision extraction in `app/services/vision.py` to `extract_vision_openrouter_async` using `httpx.AsyncClient`. When an `asyncio.Task` is cancelled, `httpx` closes the TCP socket and connection pool immediately. No background thread continues execution.

### B. Modality Dispatcher Native Async Integration
- **Previous Failure:** `app/api/pipeline.py` ran `await asyncio.to_thread(dispatch, ...)` which pushed image extraction into an un-cancellable thread pool.
- **Solution:** Added `dispatch_async` in `app/services/dispatcher.py` and `describe_image_file_async` in `app/services/vision.py`. Image files are directly awaited on the event loop.

### C. Semaphore Cancellation Safety
- **Previous Failure:** If an extraction job was cancelled while holding or waiting for an `asyncio.Semaphore` permit, permit leaks or double releases could occur.
- **Solution:** Wrapped `await sem.acquire()` with `acquired_sem = False` inside `try:` blocks and released permits in `finally:` only if `acquired_sem` was `True`.

### D. Source Status Literal Compliance
- **Previous Failure:** `SourceRecord.status` is defined with `Literal["UPLOADED", "PROCESSING", "EXTRACTING", "NORMALIZING", "INDEXING", "READY", "FAILED", "VISION_EXTRACTION_FAILED"]`. Setting status to `"CANCELLED"` caused Pydantic `ValidationError`.
- **Solution:** In `app/services/registry.py`, added a defensive mapping layer where non-standard statuses (e.g. `"CANCELLED"`, `"EXTRACTION_FAILED"`) are mapped cleanly to `"FAILED"`. Updated `app/api/pipeline.py` to set `"FAILED"` on cancellation.

### E. Atomic Deduplication
- **Previous Failure:** Concurrent upload requests of the same file caused two background tasks to spawn simultaneously.
- **Solution:** Implemented `get_or_create_active_job` under `_lock` in `JobManager`. Concurrent requests for the same SHA256 file safely receive the existing active job without starting a second pipeline run.

### F. Graceful Server Shutdown
- **Previous Failure:** Active jobs continued running or were abruptly severed without cleaning up resources.
- **Solution:** Added FastAPI `lifespan` in `app/main.py` calling `await job_manager.shutdown_active_jobs(timeout=5.0)`.

---

## 3. Test & Verification Results

### Automated Test Suite: 17 Passed, 0 Failed
Executed `tests/test_async_vision_cancellation.py` and `tests/test_vision_structured_output.py`:
- `test_scenario_a_async_vision_attempt1_success`: PASSED
- `test_scenario_b_schema_fallback_to_json_object`: PASSED
- `test_scenario_c_read_timeout_fails_cleanly`: PASSED
- `test_scenario_d_stage_timeout_marks_job_failed`: PASSED
- `test_scenario_e_true_async_cancellation`: PASSED
- `test_scenario_f_graceful_shutdown`: PASSED
- `test_scenario_g_source_status_on_cancelled_no_validation_error`: PASSED
- `test_scenario_h_semaphore_cancellation_safety`: PASSED
- `test_scenario_i_atomic_duplicate_upload_dedup`: PASSED
- `test_scenario_j_dispatch_async_image`: PASSED
- `test_scenario_k_bounded_attempt_budget_default_two_attempts`: PASSED
- `test_schema_normalization`: PASSED
- `test_clean_json_response_fences`: PASSED
- `test_extract_vision_openrouter_schema_fallback_to_json_object`: PASSED
- `test_extract_vision_openrouter_bounded_at_most_two_requests`: PASSED
- `test_extract_vision_fallback_unavailable_code`: PASSED
- `test_retry_failed_job_endpoint`: PASSED

### End-to-End Progression Verification
- Progressed from upload to `extracting_content` (18% -> 25%) and directly into `normalizing_units` (30%) and `analyzing_structure` (40%).
- Real OpenRouter HTTP 429 response handled cleanly in 906ms total with zero hung tasks, zero late responses, and zero Pydantic validation errors.
