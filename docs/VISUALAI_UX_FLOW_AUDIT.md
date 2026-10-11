# VisualAI Current UX Flow Audit

## Scope and evidence

Audited the current React source in `newfront/`, including routes, `WorkspaceContext`, API services, dashboard, materials, My Learning, Learning Studio, assessment, video and profile pages. No screen recording was present in the repository, so this report does not claim a recording review. The running application was checked through Vite/FastAPI and the available Brave/Puppeteer browser acceptance suite.

Pre-existing uncommitted changes were found in backend files (`app/db/vector_store.py`, `app/services/content_understanding.py`) and `tests/test_content_understanding.py`. They were treated as user work and left untouched.

## Current navigation problems

| Problem | Evidence | User impact |
| --- | --- | --- |
| Too many unrelated destinations | Sidebar exposed Dashboard, Source Library, Topic Explorer, Learning Studio, Practice, Progress and Video Studio separately | A student had to infer which page owned the current lesson |
| Practice and video were separate contexts | `/app/assessment` and `/app/video` rendered separate pages even though both require the active lesson | The student could lose the feeling of learning one topic |
| Learning Studio opened on Notes | `LearningStudioPage` initialized `activeTab` to `notes` | The most important explanation was not the first experience |
| Dashboard offered technical framing | Hero and cards emphasized server context, status and implementation language | First-time students did not immediately see the three starting choices |
| Upload language was implementation-heavy | “Ingestion”, “pipeline”, raw job stages and source registry language were prominent | Students had to understand backend processing to know what to do |
| Statuses were not translated | Raw states such as `INDEXING`, `CONTENT_READY` and `PROCESSING` appeared in the student UI | A student could not tell whether material was readable, searchable or failed |
| Actions did not always reveal outcomes | “Explore”, “Open”, “Start Ingestion” and “Video Studio” did not consistently say whether they create, open or watch | Button intent was ambiguous |
| Missing next action | Lesson pages did not consistently guide the student from explanation to notes, visualization, practice or video | The experience felt like separate tools rather than one lesson |

## Duplicate or confusing actions

- Topic creation was available through Topic Explorer while saved lesson continuation was also represented as a separate Dashboard/Studio route.
- Assessment and video were both navigational destinations instead of views of the current lesson.
- The same lesson could be reached through dashboard, explorer, studio, assessment and video, but only studio made the active context clear.
- Upload used source/job concepts without a simple “read material → prepare search → create lesson” explanation.

## Missing user guidance

- No clear “What would you like to learn today?” starting point.
- No explicit distinction between topic learning and learning from material on the dashboard.
- No single workspace description explaining Learn, Notes, Visualize, Practice, Ask AI and Video.
- No clear explanation that opening Notes/Visualize/Video does not automatically trigger an expensive generation request.
- No contextual next-step suggestion after the lesson explanation.

## Backend/API preservation

The UX changes compose existing frontend API services only. No backend route, schema, storage behavior, authentication semantics, source identity, lesson identity, assessment identity or video pipeline was changed.
