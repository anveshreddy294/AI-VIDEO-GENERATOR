# Analysis results and resource downloads

Implemented on `fixextra`.

## Behavior

- `Your analyzed materials` follows the upload analysis panel and precedes My sources and saved lessons. Recent materials appear there once; older materials remain in My sources.
- Each card uses owned API responses for source/version, filename, type, upload date and processing state. Learn is available only with confirmed content readiness. Topic counts/previews are displayed only when supplied by the API.
- Processing begins immediately; repeated polls merge into a single source/version card. Network uncertainty stays processing, rather than falsely claiming failure or completion. Supported failed jobs offer retry, respecting the existing retry limit.
- Owner-scoped durable job summaries preserve completed-with-warning and failed status on refresh. Only a small allowlisted status/result/failure projection is returned. No raw prompts, diagnostic messages or unrelated job payloads are added to the source list.
- Notes download as UTF-8 Markdown or text; the structured explanation downloads as Markdown. Export uses currently loaded content and makes no generation request.
- Flowcharts render from the existing structured nodes and directed connections into a safe SVG. The same SVG is downloaded directly or converted to PNG using the browser canvas. Invalid or empty diagrams cannot create placeholder downloads; oversized PNG exports advise downloading SVG.
- SVG labels are escaped and no provider markup is imported. Resource scope is cleared on navigation; asynchronous PNG conversion cannot download the previous lesson after a switch. Blob URLs are revoked after use.
- Controls sit beside each resource with status feedback. Diagram images have a keyboard-focusable horizontal scroll region and an accompanying text representation. Long filenames and the topic input fit narrow screens.

## Files

- `app/static/analysis-results.js`: result-card state, identity reconciliation and safe rendering.
- `app/static/resource-exports.js`: text serialization, filenames, safe SVG generation, PNG conversion and browser downloads.
- `app/static/learning.js`: existing upload/job/source integration, download handlers, navigation guards and saved note detail restoration.
- `app/static/learning.html` and `learning.css`: result placement, controls and responsive presentation.
- `app/api/learner.py`: two fixed JavaScript asset routes; no arbitrary filesystem/download endpoint.
- `app/services/pipeline_tracker.py` and `app/main.py`: read-only owner/version-scoped status summaries on existing source responses.
- `tests/test_resource_exports.js`, `tests/test_analysis_summaries.py`, and updated learning/topic frontend tests: export content, safety, ownership, statuses, duplicate reconciliation and regressions.

## Verification

- JavaScript/Worker/frontend suite: **192 passed, 0 failed**.
- Full Python suite: **1,500 passed, 137 skipped, 5 warnings** in 185.52 seconds. Skipped tests were not verified by this run.
- `git diff --check` passes.
- Signed-in browser verification: a repeated synthetic physics PDF showed processing immediately, merged to one completed card and remained a single card after refresh. Existing PNG warning completion and a failed material remained visible after refresh.
- Saved Newton's Second Law lesson restored notes and flowchart. Actual browser downloads were inspected on disk: notes Markdown (375 bytes), notes text (359 bytes), flowchart SVG (1,712 bytes), PNG (24,776 bytes), lesson Markdown (1,439 bytes). The PNG was visually inspected and contains the actual nodes, arrows and full connection labels.
- A browser automation download-event waiter timed out once even though the file downloaded successfully. Subsequent verification used the downloaded artifacts and visible download status.
- Screenshots are local, ignored artifacts under `storage/runtime/ux-analysis-browser.jpg` and `ux-flowchart-browser.jpg`.
- Final narrow-screen check: document width and viewport were both 375 pixels; the dashboard had no page-level horizontal overflow.

## Manual checks

1. Sign in and analyze a PDF or image. Confirm the card appears immediately below the upload panel, advances truthfully and exposes Learn only when ready. Refresh and repeat the same upload; check there is one card per source/version.
2. Use a failed retryable job and a non-retryable failure. Confirm only the supported job exposes Retry; pending or uncertain requests never display Completed.
3. Open a lesson, generate or restore notes, and download Markdown/TXT. Compare every displayed section, equation and Unicode character with the files. Try downloading before generation; expect a helpful error and no file.
4. Open the flowchart and download SVG/PNG. Inspect the whole image and connections. Switch lessons during PNG conversion; the previous lesson must not download. At mobile width, use the image's own horizontal scroll region.
5. Download the explanation as Markdown. Confirm no generation call occurs. Sign out and use another account; the first account's sources/jobs/resources must remain inaccessible. Ownership denial and late-navigation behavior are covered by automated tests; a second live account was not used in this browser session.

No dependencies were installed. No model routing, timeout budgets, authentication policy, learning loop or reassessment workflow was changed. PDF export was optional and is not added. Live provider generation quality is outside this focused export/placement change; downloads preserve the content already available in the lesson.
