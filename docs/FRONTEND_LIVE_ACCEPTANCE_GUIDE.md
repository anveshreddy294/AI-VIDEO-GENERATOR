# React / FastAPI Live Acceptance Guide

Live acceptance is gated. Do not mark a row `LIVE_VERIFIED` until the action is executed against a real Supabase account, the running FastAPI service, configured AI provider, and required source/vector/video dependencies.

## Start two separate development servers

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run.py
```

FastAPI runs at `http://127.0.0.1:8000`.

In a second terminal:

```bash
cd newfront
npm run dev
```

React/Vite runs at `http://127.0.0.1:5175`.

The Vite proxy forwards `/api`, `/educational-content`, `/pipeline`, `/sources`, `/learning-sessions`, `/upload` and `/health` to port 8000. It does not proxy `/`.

## Gate 1 — real student journey

1. Open `http://127.0.0.1:5175/`.
2. Select Start Learning and enter `/signin`.
3. Sign in with a real confirmed Supabase student account. Do not use a preset or role selector.
4. Confirm the UI reaches `/app/dashboard` and identity matches `GET /api/auth/me`.
5. Open Topic Explorer and submit `Binary Search Trees` with **Topic-only lesson** selected.
6. In browser devtools, confirm an authenticated `POST /educational-content` with a topic-only JSON body and no fabricated source ID.
7. Confirm the response contains `content_id`, and the UI navigates to `/app/studio?lesson=<content_id>`.
8. Compare the displayed explanation, concepts and examples with the response body; they must be returned fields.
9. Refresh the page. Confirm `GET /educational-content/{content_id}` runs and the same lesson is rendered.
10. Record the request IDs, status codes and result in the acceptance table below.

Do not continue to provider-heavy flows until this gate passes.

## Gate 2 — source upload

1. Use a supported real PDF, TXT or image that is permitted for the environment.
2. Confirm the browser sends multipart field `file` to `POST /pipeline/upload-and-assess` and does not set its own multipart content type.
3. Confirm the returned `job_id` is polled through `GET /pipeline/jobs/{job_id}`.
4. Record actual states such as `EXTRACTING`, `CONTENT_READY`, `READY`, `FAILED`, `VISION_EXTRACTION_FAILED`, `EXTRACTION_INSUFFICIENT` or the backend’s current failure code.
5. Only treat a source as ready after the backend returns source metadata/readiness. Never infer page counts or vector indexing from the client.
6. If the job fails, verify the UI reports the failure and only offers retry where the backend supports it.

## Gate 3 — educational artifacts

For the real lesson ID, execute Notes, Flowchart, Assessment and ASK one at a time. Confirm each request is authenticated, the returned artifact is rendered, a 4xx/5xx response remains an error, and no local template is appended. For assessment, verify the initial response has no answer keys and only the server submission response supplies grading.

## Gate 4 — video

1. Start the job once and verify duplicate clicks do not create a second client request while an active status is shown.
2. Poll only actual statuses returned by FastAPI.
3. On `COMPLETED`, verify the client calls the authorized stream endpoint, creates a Blob URL, and an HTML5 `<video controls>` element plays the MP4.
4. Verify download is disabled until the Blob exists.
5. Verify an expired/foreign session cannot fetch the stream.
6. Verify failed rendering shows the backend error category and does not show a success notification.

## Browser coverage

Run the journey in Safari using `127.0.0.1` consistently for the backend and Vite origin. Repeat using the chosen development host only if both origin and proxy configuration are intentionally changed. Check reload during lesson generation and video polling, tab close/unmount, network offline, token expiry, and back/forward navigation.

## Acceptance status table

| FEATURE | FRONTEND COMPONENT | BACKEND ENDPOINT | IMPLEMENTATION STATUS | OFFLINE TEST RESULT | LIVE TEST RESULT |
| --- | --- | --- | --- | --- | --- |
| Signup/login/session | `SignInPage`, `WorkspaceContext` | `/api/auth/*` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| Topic-only lesson | `TopicExplorerPage` | `POST /educational-content` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| Lesson reload | `LearningStudioPage`, `WorkspaceContext` | `GET /educational-content/{id}` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| Source upload/job | `LibraryPage`, `DashboardPage` | `/pipeline/upload-and-assess`, `/pipeline/jobs/*` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| Notes/diagram | `LearningStudioPage` | `/{id}/notes`, `/{id}/diagram` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| Assessment | `AssessmentPage` | `/{id}/assessment*` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| ASK | `LearningStudioPage` | `POST /educational-content/{id}/ask` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| Video generation/playback | `VideoStudioPage` | `/{id}/video*` | IMPLEMENTED_UNTESTED | Build passed | NOT_STARTED |
| Progress/educator unsupported states | `ProgressPage`, `EducatorHubPage` | No safe connected aggregate contract | OFFLINE_VERIFIED | Build passed | NOT_APPLICABLE |

## Rollback

Stop the Vite server and switch back to branch `success` (or the pre-integration commit). FastAPI remains on its original code and port. No automatic push or production route change is part of this work.
