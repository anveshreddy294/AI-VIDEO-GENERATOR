# AICARLS inspection and development report

Inspected the uploaded ZIP on 13–14 September 2026 (India time). The archive, rather than the historical handoff or the separate Downloads checkout, was used as the source of truth.

**Result:** deterministic curriculum retrieval, semantic compilation, Piper speech, Manim rendering, and FFmpeg assembly produced a real work-energy video. The final sample is approximately 11.1 seconds. The storyboard/plan/narration in this sample are a curated verification fixture, not live LLM output. The complete live generation goal is still blocked by provider authentication.

**Live blocker:** one grounded chat request reached the configured Gemini route and failed with HTTP 401, reason `ACCESS_TOKEN_TYPE_UNSUPPORTED`. The API returned 503. This run did not reproduce the historical 429 quota error. No full live video run was attempted after this failure.

1. **Actual repository structure**

   Root contains Dockerfile, docker-compose.yml, requirements.txt, frontend/, backend/, PageIndex/, docs/, legacy/, data/, and pageindex_workspace/. Backend contains api.py, main.py, modules/, tests/, scripts/, samples/, public/, legacy/, results/, and data/. Frontend src contains screens/, components/, context/, assets/, mock/, and utils/.

   The extracted working copy is:
   `C:\Users\ANVESH\Documents\Codex\2026-09-13\files-mentioned-by-the-user-aicarls\work\source\AICARLS-AI-Driven-Context-Aware-Retrieval-Augmented-Learning-System-main`.

   Downloads source files were not patched. Deliverable AICARLS-fixes.zip contains replacement/additional files relative to the repository root; AICARLS.patch provides a reviewable diff.

2. **Actual architecture**

   React/Vite calls FastAPI. The active Compose entry point is `python backend/api.py`. It resolves a textbook, retrieves context, generates an explanation package, builds a storyboard, validates lexical grounding, builds semantic plans, writes narration, synthesizes speech, builds timelines, compiles registered concept templates, renders Manim scenes, and merges audio/video with FFmpeg. Pipeline progress is streamed over SSE.

   The semantic compiler is primarily a deterministic template dispatcher, not a general LLM-to-Manim compiler. Registered concept templates are legitimate semantic scenes. A generic replacement after failure is a different outcome. The separation of planning, narration, timing, compilation, rendering, and assembly was retained.

3. **Actual providers and models**

   | Operation | Code route | Effective configuration in inspected container |
   |---|---|---|
   | Explanation and storyboard | NvidiaClient | NVIDIA planner model requested; Gemini used because no NVIDIA key is present |
   | Semantic planning | NvidiaClient | Same planner routing |
   | Narration | NvidiaClient | Same planner routing |
   | Render repair | NvidiaClient | NVIDIA repair model requested; Gemini fallback when needed |
   | Chat, added by this patch | NvidiaClient, one attempt | Same planner routing, with curriculum evidence |
   | Registered work-energy compilation | Local Python template | No LLM call |
   | PageIndex indexing | Local Ollama configuration and stage router | See below; live inference not verified |
   | Backend retrieval | Local artifact ranking/PDF lexical search | No model call |

   Central default remains `gemini-2.5-flash` in backend/modules/config.py. The uploaded environment overrides it to `gemini-3.5-flash`. NVIDIA planner and repair configuration resolve to `meta/llama-3.3-70b-instruct` and `deepseek-ai/deepseek-r1`. Credential checks printed presence only: Gemini present, NVIDIA absent.

   Before this patch, NvidiaClient ignored GEMINI_MODEL and hardcoded `gemini-2.5-flash` in its fallback. That active route now uses the shared GEMINI_MODEL. GeminiClient already honored configuration, but no active backend caller of that class was found.

   Remaining older Gemini strings in Python/YAML:

   - backend/modules/config.py: active default `gemini-2.5-flash`, overridden in this environment.
   - PageIndex/pageindex/config.yaml: `gemini/gemini-2.5-flash-lite` for token_count_model and retrieve_model. The former is tokenization configuration; the inspected backend retrieval does not call the latter.
   - PageIndex/pageindex/page_index_md.py: alternate Markdown indexing path default `gemini/gemini-2.5-flash-lite`; not the active PDF/video path.
   - PageIndex/pageindex/utils.py: compatibility mappings from Gemini 1.x names to `gemini/gemini-2.5-flash-lite`.
   - PageIndex/examples/agentic_vectorless_rag_demo.py: example-only `gemini/gemini-2.5-flash-lite`.
   - PageIndex config/local_llm defaults also retain `gemini/gemini-2.0-flash` as a fallback.

   PageIndex YAML selects `ollama/qwen2.5:3b` for generation and stage models, with Gemini fallback disabled in that YAML. local_llm.py has separate environment defaults (`gemma3:4b`, and a Gemini fallback toggle enabled until configuration is applied). Quality modes can route through NVIDIA and then local Ollama. Actual indexing model selection depends on options, environment, and installed models; live indexing was not verified.

4. **Actual API routes**

   | Method | Route | Archive status |
   |---|---|---|
   | POST | /api/persist | Present |
   | GET | /api/load/{filename} | Present |
   | POST | /api/pipeline/run | Present |
   | GET | /api/pipeline/status/{session_id} | Present, SSE |
   | GET | /api/curriculum/documents | Present |
   | GET | /api/curriculum/validate | Present |
   | POST | /api/curriculum/index | Present |
   | GET | /api/pageindex/health | Present |
   | GET | /api/health | Present |
   | POST | /api/chat | Absent; added |
   | GET | /api/curriculum/retrieve | Absent; added |

   FastAPI also provides its standard documentation/schema endpoints and the application mounts generated media.

5. **Actual retrieval**

   Original retrieval loads PageIndex structure.json/extracted_pages.json and scores node metadata with lexical terms, subject-specific boosts, and structural bonuses. This is not proof of semantic retrieval quality. Resolution supports normalized names, stale aliases, subject overrides, and a newest-document default. No populated PageIndex/results artifacts were bundled.

   The new PDF fallback uses PyMuPDF, bounded cached page extraction, lexical term scoring, a minimum term-overlap threshold, and at most three excerpts. Sources use real physical PDF page numbers. It does not invent a PageIndex structure. Indexed-document status remains distinct from PDF availability.

   Tests verify Physics work/energy and Chemistry atomic structure/benzene, and verify that each returned excerpt occurs on the reported physical page. The bundled Physics volume has 184 pages and did not contain the phrase “electromagnetic induction”; that query returns insufficient evidence. A requested subject/document should still be supplied to avoid the legacy newest-document default.

6. **PDF fallback**

   Absent in the ZIP; now implemented in backend/modules/retrieval/pdf_fallback.py and integrated into pageindex_retriever.py. It is labeled `pdf_lexical`. Indexed sections lacking readable content/pages also yield to fallback. This is resilience, not validated PageIndex indexing.

7. **Chat API**

   Added grounded retrieval, bounded recent history, server-side provider routing, server-generated source metadata, citation-ID validation, insufficient-evidence refusal, and provider-error responses. Unsupported citation IDs are rejected. Empty evidence does not invoke the model.

   Source-ID validation does not establish factual entailment of every sentence. This limitation is exposed in the response and remains an evaluation task.

8. **Frontend chat**

   The ZIP used a delayed canned response with an invented 0:15 video reference. It now calls /api/chat, sends subject/document and recent history, shows returned sources, and reports errors. Session identity is checked before applying a delayed answer. Existing mock dashboard, analytics, knowledge-graph, and video-canvas functionality was not redesigned.

   Browser interaction with a successful live model answer remains NOT VERIFIED because authentication failed.

9. **Tests and startup**

   - Original suite in isolated Docker runtime: **4 passed, 14 failed**.
   - With PDF fallback, before test-fixture correction: **16 passed, 2 failed**. The remaining assertions assumed real index artifacts and a PageIndex chapter title.
   - Indexed tests now create explicit synthetic PageIndex fixtures rather than depending on missing local results. These fixtures are confined to temporary test directories.
   - Final deterministic suite: **29 passed**, four dependency deprecation warnings.
   - New coverage includes real PDF excerpts/pages, insufficient evidence, semantic compilation without stubs, strict compile/render failure, configured model routing, grounded chat inputs, provider failure, and invalid citations.
   - Frontend production build: **PASS**.
   - Frontend lint: **FAIL, 52 errors**. The only changed frontend file has the same two lint rules failing before and after the patch (export-only-components and an unused variable); other frontend files were unchanged. The accompanying lint JSON files record this comparison.
   - npm install reported seven dependency vulnerabilities (one low, one moderate, five high); dependency remediation was not part of this core-path patch.
   - Docker Desktop was started. The existing Downloads-backed backend became healthy on localhost:5000.
   - The uploaded source was tested separately in a container named aicarls-audit-backend on localhost:5001 using the existing backend image.
   - A fresh Docker image build was NOT VERIFIED. Python 3.14 on the host lacked pytest; verification used the installed Python 3.11 Docker runtime.

10. **Semantic compiler bug and video evidence**

    The missing `strip_latex_in_text_literals` import was present in the ZIP and is fixed. A registered work_energy scene compiled into executable Python and rendered on the first attempt without fallback or LLM repair.

    The quota-free verification script exercises real textbook retrieval, the existing lexical grounding check, a curated semantic plan/narration, Piper TTS, uniform timing, semantic compilation, Manim, and FFmpeg. It explicitly disallows compiler and renderer fallbacks and asserts non-silent audio.

    Visual inspection revealed a misplaced kinetic-energy bar and unreadable theorem styling. The work-energy template now centers its foreground bar correctly, separates equation cards from the bar, and restores translucent card fills. The final inspected frame shows readable equations and the aligned energy bar.

    The delivered MP4 is approximately 11.1 seconds, H.264/AAC, 1920×1080 at 30 fps. Rendering used Manim low quality and FFmpeg upscaled it; this is a component verification sample, not a full-quality five-scene lesson or a live LLM end-to-end success.

11. **Fallbacks that remain**

    - New PDF lexical fallback: exercised.
    - Uniform/proportional timing: exercised; USE_WHISPERX=false.
    - Piper TTS: exercised successfully. gTTS, pyttsx3, and silent audio fallback remain in code but were not used in the final sample.
    - Compiler unknown-template/exception fallbacks: remain for normal operation; verification rejects them.
    - Renderer repair, template replacement, minimal/blank scenes, and ultimately an empty placeholder path: remain in normal operation. Strict rendering fails instead.
    - Structured explanation fallback, semantic-plan fallback, freeform internal fallback, and frontend prototype displays remain.
    - `STRICT_SEMANTIC=true` enables fail-fast compiler/renderer behavior in the API pipeline. It is not a complete provenance system for every planning/freeform/TTS fallback.
    - Grounded API video generation now stops when readable curriculum evidence is unavailable instead of silently continuing in LLM-only mode.

12. **Handoff discrepancies**

    The archive had none of the claimed later PDF/chat patches, retained the compiler NameError, and bypassed central Gemini configuration in the active NVIDIA fallback. PageIndex results were missing despite bundled PDFs. Grounding was a warning-only word-overlap heuristic, not a factual verifier. The current live failure was authentication, not quota. An old MP4 or a healthy server cannot establish semantic or grounding success.

13. **Current blockers and limits**

    Valid provider authentication is required to verify live storyboard, semantic planning, narration, and chat. No credentials were printed or included in the patch. Existing .env files were not replaced.

    Full live E2E, live PageIndex indexing, broader subject/template rendering, factual grounding evaluation, production hardening, and SDK migration remain NOT VERIFIED or incomplete. The SDK emits an end-of-support warning. Default fallback observability and frontend lint debt remain. This project is not production-ready.

14. **Exact next implementation sequence**

    1. Correct server-side Gemini authentication securely; retain the configured provider/model unless intentionally changed. Verify one minimal request.
    2. Verify one grounded chat response against its returned textbook excerpts and citations.
    3. Run one controlled work-energy lesson with STRICT_SEMANTIC=true. Save storyboard, plans, narration, source excerpts, timings, scene outcomes, and the final MP4.
    4. Inspect every generated scene for semantic correctness and layout; compare narration claims against textbook evidence. Treat any fallback as a separate outcome.
    5. Add persistent scene/TTS/planning provenance so normal UI results identify semantic/template/stub/silent paths.
    6. Validate PageIndex indexing with a bounded local job and compare retrieval against known source pages. Keep lexical PDF retrieval available.
    7. Modernize the Google SDK and add authentication/quota classification, request budgeting, and caching before broader live tests.
    8. Address frontend lint/dependencies, then authentication, storage, rate limiting, and deployment hardening.

To reproduce deterministic verification from the patched repository:

```powershell
docker compose up -d
docker compose exec backend pip install -r requirements-dev.txt
docker compose exec -e PYTHONPATH=/app/backend backend python -m pytest backend/tests -q
docker compose exec -e MANIM_QUALITY=-ql backend python backend/verify_semantic.py
```

The verification script creates a new uniquely named workspace beneath backend/data/renders and never requires an LLM request. Piper may download its voice model on first use.
