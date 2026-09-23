# Walkthrough: Async Vision Extraction Concurrency & True Cancellation Repair

## Overview
We have resolved the fake thread cancellation, Pydantic `ValidationError` literal defect on job cancellation, and duplicate upload race conditions by replacing synchronous blocking thread execution with native asynchronous HTTP and job tracking.

---

## Key Changes Made

### 1. Native Async Multimodal Vision (`app/services/vision.py`)
- Replaced blocking `ThreadPoolExecutor` and `urllib.request.urlopen` with `httpx.AsyncClient` in `extract_vision_openrouter_async`.
- Enforced true cancellation: when an async task is cancelled, `httpx` immediately closes the TCP socket and connection pool, eliminating orphan background threads.
- Added native async wrappers `describe_image_async` and `describe_image_file_async`.
- Maintained a bounded 2-attempt budget for the default configuration (`openrouter/free` with strict JSON schema attempt 1, followed by JSON object attempt 2).

### 2. Async Modality Dispatcher (`app/services/dispatcher.py`)
- Added `dispatch_async`: directly awaits `describe_image_file_async` on the event loop for image modalities without thread pool overhead.
- Defers CPU-bound extractors (PDF, TXT, Video) to `asyncio.to_thread` while keeping image processing natively async.

### 3. Concurrency, Cancellation & Status Safety (`app/api/pipeline.py`)
- Attached running tasks to `job_manager.attach_task(job_id, task)` and detached on job termination.
- Replaced `asyncio.to_thread(dispatch, ...)` with `await asyncio.wait_for(dispatch_async(...), timeout=extraction_deadline)`.
- Replaced invalid status assignment `update_source_status(source_id, "CANCELLED")` with defensive mapping to `"FAILED"`, eliminating Pydantic `ValidationError` on `SourceRecord`.
- Protected concurrency semaphore acquisition inside `try:` blocks to guarantee zero permit leaks or double releases on cancellation.
- Implemented atomic deduplication using `await job_manager.get_or_create_active_job(dedup_key, ...)` under `_lock` to prevent duplicate concurrent upload jobs.
- Added explicit cancellation route `POST /pipeline/jobs/{job_id}/cancel`.

### 4. Graceful Server Shutdown (`app/main.py` & `app/services/pipeline_tracker.py`)
- Implemented FastAPI `lifespan` context manager calling `await job_manager.shutdown_active_jobs(timeout=5.0)`.
- Added `shutdown_active_jobs` in `JobManager` to cancel and await all active tasks during server shutdown.

---

## Verification Results

### Automated Test Suites
Executed 17 comprehensive unit and integration tests across:
- `tests/test_async_vision_cancellation.py` (11 scenarios A–K)
- `tests/test_vision_structured_output.py` (6 tests)

```
tests/test_async_vision_cancellation.py::test_scenario_a_async_vision_attempt1_success PASSED
tests/test_async_vision_cancellation.py::test_scenario_b_schema_fallback_to_json_object PASSED
tests/test_async_vision_cancellation.py::test_scenario_c_read_timeout_fails_cleanly PASSED
tests/test_async_vision_cancellation.py::test_scenario_d_stage_timeout_marks_job_failed PASSED
tests/test_async_vision_cancellation.py::test_scenario_e_true_async_cancellation PASSED
tests/test_async_vision_cancellation.py::test_scenario_f_graceful_shutdown PASSED
tests/test_async_vision_cancellation.py::test_scenario_g_source_status_on_cancelled_no_validation_error PASSED
tests/test_async_vision_cancellation.py::test_scenario_h_semaphore_cancellation_safety PASSED
tests/test_async_vision_cancellation.py::test_scenario_i_atomic_duplicate_upload_dedup PASSED
tests/test_async_vision_cancellation.py::test_scenario_j_dispatch_async_image PASSED
tests/test_async_vision_cancellation.py::test_scenario_k_bounded_attempt_budget_default_two_attempts PASSED
tests/test_vision_structured_output.py::test_schema_normalization PASSED
tests/test_vision_structured_output.py::test_clean_json_response_fences PASSED
tests/test_vision_structured_output.py::test_extract_vision_openrouter_schema_fallback_to_json_object PASSED
tests/test_vision_structured_output.py::test_extract_vision_openrouter_bounded_at_most_two_requests PASSED
tests/test_vision_structured_output.py::test_extract_vision_fallback_unavailable_code PASSED
tests/test_vision_structured_output.py::test_retry_failed_job_endpoint PASSED

======================== 17 passed, 1 warning in 3.50s ========================
```

### End-to-End Pipeline Progression Verification
Verified live execution with test image `original.jpeg` reaching:
- `extracting_content` (18% -> 25%)
- `normalizing_units` (30%)
- `analyzing_structure` (40%)
with zero orphan threads, zero hung processes, and zero Pydantic validation errors.
