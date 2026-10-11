# Frontend API Contract Matrix

Contracts below were verified against the current FastAPI routers and schemas, not inferred from the React UI. Authenticated requests use `Authorization: Bearer <Supabase access token>`.

| Frontend action | Method/path | Request | Response used by React | Auth / errors | Loading, success, dependencies |
| --- | --- | --- | --- | --- | --- |
| Sign up | `POST /api/auth/signup` | `{email,password,full_name}`; no role | `AuthResult`; may be `confirmation_required` with no session | Public; 400/401/422/429/503/502 | Form busy → confirmation or authenticated workspace; Supabase signup/profile |
| Sign in | `POST /api/auth/login` | `{email,password}` | `AuthResult` with `session`, `profile` | Public; 401 invalid credentials, 422, 429, 503 | Form busy → `/app/dashboard` or backend-authorized `/educator`; Supabase auth |
| Restore identity | `GET /api/auth/me` | none | `{user_id,email,profile}` | Bearer; 401 clears session | App loading → protected shell; verified JWT/profile |
| Refresh | `POST /api/auth/refresh` | `{refresh_token}` | `AuthResult` | Public endpoint carrying refresh token; 401/503 | Deduplicated by client; invoked only on expiry/401 |
| Logout | `POST /api/auth/logout` | none | `204` | Bearer; client clears session even on failure | Sign-out then public state; Supabase logout |
| Owned source list | `GET /sources` | none | `{sources:[...]}` | Bearer in Supabase mode; 401/503 | Loading/empty/error; owner-scoped repository |
| Upload source/job | `POST /pipeline/upload-and-assess` | multipart `file`; no manual multipart header | `{job_id,status,message}` | Bearer in Supabase mode; 415/413/422/429/503 | Uploading → poll job; file truth + source ingestion/Qdrant as backend decides |
| Poll upload | `GET /pipeline/jobs/{job_id}` | path ID | `PipelineJob` with progress/events/result/failure | Bearer owner scope; 404 | Bounded 2-second polling; terminal success/failure; job manager/source repository |
| Read source | `GET /sources/{source_id}` | path ID | `SourceRecord` | Bearer owner scope; 404/409 | Source detail when required; Supabase source repository |
| Read source units | `GET /sources/{source_id}/content-units?version=N` | exact version optional | `{content_units:[...]}` | Bearer; 404 | Source evidence only when returned; owner/version scope |
| List lessons | `GET /educational-content` | none | `{lessons:[LessonSummary]}` | Bearer through `SourceDependency`; 401/409/503 | Dashboard/explorer loading; owner lesson store |
| Create topic lesson | `POST /educational-content` | `{topic}` for topic-only; or exact `{topic?,source_id,source_version}` | `EducationalContent`; durable ID is `content_id` | Bearer; 404 `CONTENT_UNAVAILABLE`, 422 `EDUCATIONAL_CONTENT_INVALID`, 503 provider categories | Generation busy → navigate with returned ID; reasoning provider + persistence |
| Reload lesson | `GET /educational-content/{lesson_id}` | path ID | `EducationalLesson` detail | Bearer; 404 `LESSON_NOT_FOUND` | Fetch on reload; owner lesson store; public assessment only |
| Notes | `POST /educational-content/{lesson_id}/notes` | `{detail_level,regenerate}` or empty | `EducationalNotes` | Bearer; 404/503 `NOTES_GENERATION_FAILED` | Explicit generate/regenerate; reasoning provider |
| Flowchart | `POST /educational-content/{lesson_id}/diagram` | `{regenerate}` or empty | `FlowchartDiagram` with valid node/edge IDs | Bearer; 404/503 `DIAGRAM_GENERATION_FAILED` | Explicit generate; validated backend diagram |
| Assessment generation | `POST /educational-content/{lesson_id}/assessment` | none | `PublicAssessment` without keys | Bearer; 404/503 `ASSESSMENT_GENERATION_FAILED` | Generate button; private persisted key stays backend-only |
| Assessment submit | `POST /educational-content/{lesson_id}/assessment/submit` | `{mcq_answers,descriptive_answer}` | `SubmissionResult` server score/feedback | Bearer; 404/422/503 | Submit busy → authoritative result; private assessment + grader |
| ASK | `POST /educational-content/{lesson_id}/ask` | `{question}` 1–4000 chars | `AskResponse` answer/evidence status/provenance/citations | Bearer; 404/422 `ASK_INVALID`/503 `ASK_FAILED` | Query busy → backend response; lesson context/reasoning provider |
| Start video | `POST /educational-content/{lesson_id}/video` | none | status dictionary (`job_id,status,stage,progress,...`) | Bearer; 404/422 `VIDEO_PLAN_INVALID`/503 `VIDEO_START_FAILED` | Duplicate clicks disabled; existing job returned; renderer pipeline |
| Video status | `GET /educational-content/{lesson_id}/video/status` | none | status dictionary, or `NOT_STARTED` | Bearer; 404 | Bounded poll every 2.5 seconds during supported active stages |
| Video playback | `GET /educational-content/{lesson_id}/video/stream` | none | private `video/mp4` | Bearer owner; 404 `VIDEO_NOT_READY`/`VIDEO_FILE_MISSING` | Authenticated fetch → size-checked Blob URL → HTML5 controls/download |

## Important verified deviations

- The candidate `/upload` route is synchronous and separate. The React workspace intentionally uses the canonical `/pipeline/upload-and-assess` job flow.
- `POST /pipeline/upload-and-assess` in Supabase mode queues source-only ingestion; it does not fabricate or assume an assessment handoff.
- `GET /sources` is declared on the main app, while source detail/version/content-unit routes are in `app/api/sources.py`.
- Topic lesson creation returns `EducationalContent`, not an `EducationalLesson` wrapper. React uses `content_id` as the durable lesson ID, then reloads the detail route.
- Educational lesson notes are `EducationalNotes` and AI-enriched; they are not canonical session-grounded notes.
- The lesson assessment public response omits answer keys. The post-submit result may reveal grading details to the authenticated owner after grading.
- A native `<video src>` cannot attach the bearer header. React fetches the protected stream and uses a temporary Blob URL; no public media URL is exposed.
- Legacy `/api/learning`, `/assessment`, and generic `/video` routes are not used for the Supabase educational-content workspace because their legacy boundary is unavailable in canonical Supabase mode.
