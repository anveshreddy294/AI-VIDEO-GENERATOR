# VisualAI Canonical User Journey

## Information architecture

```text
Dashboard
  ├── Learn a Topic          → My Learning → Generate Lesson
  ├── Upload Study Material  → My Materials → process source → create lesson
  └── Continue Learning      → Learning Workspace for the saved lesson

Learning Workspace: one lesson identity
  ├── Learn       explanation, concepts, examples, equations
  ├── Notes       generate/view backend notes
  ├── Visualize   generate/view backend diagram
  ├── Practice    generate/submit backend assessment
  ├── Ask AI      ask within the lesson context
  └── Video       generate/poll/watch authenticated video
```

## Canonical routes

| Human purpose | Route | Existing route compatibility |
| --- | --- | --- |
| Dashboard | `/app/dashboard` | unchanged |
| My Learning | `/app/explore` | label and purpose simplified |
| My Materials | `/app/library` | label and purpose simplified |
| Learning Workspace | `/app/studio?lesson=<lesson_id>&tab=<tab>` | `/app/workspace` and `/app/learning-workspace` redirect here |
| Practice deep link | `/app/assessment` | redirects to `/app/studio?tab=practice` |
| Video deep link | `/app/video` | redirects to `/app/studio?tab=video` |
| Materials alias | `/app/materials` | redirects to `/app/library` |
| Learning alias | `/app/learning` | redirects to `/app/explore` |

## Topic learning flow

1. Student selects **Learn a Topic** on the dashboard.
2. My Learning accepts a topic such as `Binary Search Trees`.
3. Existing `POST /educational-content` is called with the topic-only contract.
4. Returned `content_id` becomes the active lesson ID.
5. Student enters `/app/studio?lesson=<content_id>&tab=learn`.
6. The real explanation, concepts, examples and equations are rendered.
7. The student chooses Notes, Visualize, Practice, Ask AI or Video in the same workspace.

## Document learning flow

1. Student selects **Upload Study Material**.
2. My Materials submits the real file to `POST /pipeline/upload-and-assess`.
3. The UI polls the existing job endpoint and translates backend states into plain language.
4. `CONTENT_READY` and `INDEXING` remain distinct: extracted material may be available while document search is still preparing.
5. Once supported source identity/version data is available, the student selects the material and chooses **Create Source Lesson**.
6. The resulting source-grounded lesson enters the same Learning Workspace.

## Continue learning flow

1. Dashboard lists only returned saved lessons.
2. Selecting a lesson retains its actual lesson ID in the URL and session storage.
3. Refreshing `/app/studio` reloads the same lesson through `GET /educational-content/{lesson_id}`.
4. Switching tabs changes only the `tab` query parameter; it does not create another lesson.

## Learning workspace rules

- Learn is the default tab.
- Notes, diagrams, assessments and videos are generated only by explicit buttons.
- Practice grades only through the backend.
- Video status is polled only for an active lesson and does not start from tab navigation.
- Every tab displays the same lesson title and lesson identity.
- Old bookmarks continue to resolve to the corresponding workspace tab.
