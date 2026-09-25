# VisualAI System Background Process & Error Audit Report

**Audit Timestamp:** September 25, 2026  
**Target Environment:** Local macOS (`AI-VIDEO-GENERATOR` Production Runtime)  
**Execution Context:** End-to-End Pipeline, Registry Diagnostics, Background Daemon Inspection

---

## 1. Executive Summary

A comprehensive forensic inspection of background daemons, listening ports, process tables, and source registries identified **four distinct categories of active or historical failures** affecting ingestion and the background pipeline execution:

1. **Vision Ingestion Authentication Blocker (`VISION_AUTH_FAILED`)**: Image ingestion halted because `.env` was missing `OPENROUTER_API_KEY` following Git branch operations.
2. **Multi-Image PDF Extraction Timeout Blocker (`VISION_TIMEOUT`)**: PDF documents containing numerous embedded diagrams (e.g., `python1.pdf` with 14 images) trigger serial vision requests that exceed the 100.0s pipeline stage deadline.
3. **Repetitive Text Guardrail False Positive (`CONTENT_SANITIZATION_FAILED`)**: PDF parsing encountered repeating sequences in academic formatting, triggering a fail-closed rejection.
4. **External Provider Quota Throttling (`VISION_RATE_LIMIT` / HTTP 429)**: Free-tier OpenRouter endpoints intermittently reject image analysis during high traffic.

---

## 2. Background Process & Port Audit

| Port / Process | Status | Process / Daemon | Observation & Health Check |
|---|---|---|---|
| **Port 11434** | **ONLINE** | `ollama` (PID 6454) | Healthy. Hosting `llama3.2:3b` and `nomic-embed-text:latest` (768-dim). |
| **Port 8000** | **OFFLINE** | Uvicorn / FastAPI | Server process is currently stopped. Launch with `./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`. |
| **Port 6333** | **FALLBACK** | Qdrant Vector DB | Remote Qdrant server offline; system cleanly uses embedded disk store (`storage/runtime/qdrant`). |
| **OCR Subsystem** | **AVAILABLE** | `/opt/homebrew/bin/tesseract` | Version 5.5.3 installed and operational for fallback text extraction. |
| **FFmpeg Engine** | **AVAILABLE** | `/opt/homebrew/bin/ffmpeg` | Operational for Manim rendering and video compilation. |

---

## 3. Forensic Registry Error Audit (`sources_index.json`)

Analysis of all 162 recorded ingestion attempts in `storage/runtime/registry/sources_index.json` reveals the following failed jobs:

### Failure 1: Missing API Key Configuration (`SRC_839149f27803`)
* **File:** `minato-namikaze-3840x2160-24353.png` (835 KB, 3840x2160 4K PNG)
* **Status:** `FAILED`
* **Error Code:** `VISION_AUTH_FAILED`
* **Error Message:** `VISION_AUTH_FAILED: OPENROUTER_API_KEY is not configured. Vision extraction cannot proceed.`
* **Root Cause:** Git fast-forward merge wiped `.env`. With no API key in memory or on disk, `extract_vision_openrouter_async` correctly failed closed.
* **Resolution:** Re-created `.env` and added dynamic file-reading getter in `app/core/config.py` so changes to `.env` apply without server restarts.

---

### Failure 2: PDF Serial Vision Cumulative Timeout (`SRC_4ad9b3a918b1`)
* **File:** `python1.pdf` (329 KB, 7 pages)
* **Status:** `FAILED`
* **Error Code:** `VISION_TIMEOUT`
* **Error Message:** `VISION_TIMEOUT: Image understanding exceeded the configured time limit. Please retry.`
* **Root Cause:**
  - `python1.pdf` extracted **14 embedded diagram images** across 7 pages into `storage/runtime/uploads/SRC_4ad9b3a918b1/images/`.
  - In `app/services/extractor.py`, each image is sent sequentially to `describe_image(...)`.
  - At ~10–25s network latency per OpenRouter request, 14 images take 140–350 seconds.
  - In `app/api/pipeline.py`, the entire stage is wrapped in `asyncio.wait_for(..., timeout=100.0s)`.
  - At $t=100.0s$, `asyncio.TimeoutError` killed the entire ingestion, discarding the already-extracted text units.
* **Remediation Needed:**
  1. Cap PDF embedded diagram vision analysis to a max budget of **2–3 critical images** per PDF document.
  2. Implement an elapsed-time guard: if stage budget has less than 20s remaining, skip remaining image descriptions and preserve extracted text.
  3. Never fail the entire PDF if secondary embedded diagram descriptions time out.

---

### Failure 3: Content Sanitization Repetition Guard (`SRC_2efd1e93aba5`)
* **File:** `python1.pdf` (First upload attempt)
* **Status:** `FAILED`
* **Error Code:** `SANITIZATION_REJECTED`
* **Error Message:** `Extracted content contains repeated garbage character sequences.`
* **Root Cause:**
  - `app/services/security/content_sanitizer.py` rejected text containing repetitive sequences (e.g. repeated table divider lines or code comment banners like `#############`).
* **Remediation Needed:**
  - Adjust repetitive character regex to allow normal programming comment bars and ASCII divider syntax.

---

### Failure 4: Provider HTTP 429 Rate Limits (`SRC_45b5802ec047`, `SRC_48847fd699f8`, etc.)
* **Files:** Synthetic benchmark & test images
* **Status:** `FAILED`
* **Error Code:** `VISION_RATE_LIMIT`
* **Error Message:** `VISION_RATE_LIMIT: OpenRouter rate limit reached (HTTP 429). All OpenRouter vision models rate-limited (HTTP 429)`
* **Root Cause:** Free-tier rate limits on `openrouter/free` upstream models.
* **Remediation:** Circuit breaker with exponential backoff (30s–120s cooldown) is now active to prevent thrashing.

---

## 4. Prioritized Action Plan

| Priority | Component | Action Item | Impact |
|---|---|---|---|
| **P0** | **Environment** | Populate `OPENROUTER_API_KEY` in `.env` | Restores cloud vision extraction immediately |
| **P1** | **`extractor.py`** | Budget PDF image vision to top 2 images max and check remaining deadline | Eliminates `VISION_TIMEOUT` on multi-page PDFs |
| **P1** | **`pipeline.py`** | Allow PDF text units to succeed even if embedded image descriptions time out | Prevents complete ingestion drop |
| **P2** | **`sanitizer.py`** | Permit code comment bars (`###`, `---`, `===`) in text validation | Prevents false-positive rejection on code PDFs |

---
*Audit completed by Antigravity Senior Reliability Engineering Suite.*
