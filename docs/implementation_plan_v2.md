# Topic2Manim — Implementation Plan v2
**Date:** 2026-06-15  
**Author:** Senior Production Systems Engineer  
**Supersedes:** `production_implementation_plan.md` (Phase 1 items now implemented; this plan addresses the three remaining production blockers)

---

## 1. Executive Summary

The production implementation plan created on 2026-06-15 (`production_implementation_plan.md`) successfully resolved the original seven defects:

- D1 (wrong document routing) — **FIXED.** `_resolve_doc_folder` now accepts `subject`, blacklists `ilovepdf_merged.pdf`, and performs subject-keyword matching. `Workspace.jsx` and `Dashboard.jsx` both pass `documentId` to `startPipeline`.
- D2 (substring scoring) — **FIXED.** `_score_node` uses `\b`-bounded regex and a +2.0 tag boost for chemistry.
- D3 (no chemistry templates) — **FIXED.** 12 chemistry templates now exist under `backend/modules/templates/chemistry/`.
- D4–D7 — **FIXED.** Sync engine consumed, `visualizable_elements` propagated, grounding validator active.

Three new production blockers remain:

| # | Issue | User Impact | Severity |
|---|-------|-------------|----------|
| P1 | **Inconsistent audio** — some videos are silent | Silent lecture videos; broken product experience | BLOCKER |
| P2 | **No delete in Video Library** — bad videos accumulate | Demo pollution; users cannot clean up failed renders | HIGH |
| P3 | **Multi-textbook routing not fully robust** — subject/docId mismatch still possible at edge cases | Wrong content retrieved; poor answer quality | HIGH |

This plan addresses all three in three prioritized phases. Phases are ordered: P1 audio fix first (most user-visible), then P3 routing hardening (data quality), then P2 delete functionality (usability). The audio fix unlocks clean videos; those clean videos must then be deletable once the library has delete support.

**Estimated effort:** 2–3 focused engineering days.

---

## 2. Current State Analysis

### 2.1 What Works (as of v1 plan)

| Component | File | Status |
|-----------|------|--------|
| Subject-aware routing | `pageindex_retriever.py:_resolve_doc_folder` | Working — priority 1→2→3→4→5 chain |
| Document ID passed from frontend | `Workspace.jsx:68`, `Dashboard.jsx` | Working — `subjectDocMap[selectedSubject]` passed as arg 3 |
| `ilovepdf_merged.pdf` blacklisted | `_BLACKLISTED_AUTO_FOLDERS` frozenset | Working |
| Chemistry templates | `templates/chemistry/` (12 files) | Working — bohr_orbit, rutherford_gold_foil, redox_transfer, etc. |
| Retrieval audit log | `api.py:424–450` writes `retrieval_audit.json` | Working |
| Word-boundary scoring + tag boost | `_score_node` | Working |
| TTS fallback chain | `piper_tts.py` | Working — but **silent fallback is the last resort and not flagged** |
| FFmpeg merge | `ffmpeg_merge.py:merge` | Working — but **silent WAV produces technically valid but mute MP4** |
| History save | `api.py:661–688` | Working — but **saves regardless of audio quality** |

### 2.2 Root Causes of Remaining Issues

#### P1 — Inconsistent Audio (Silent Videos)

**Root cause chain:**

1. `synthesize()` in `piper_tts.py` falls through four backends: Piper CLI → Piper Python → gTTS → pyttsx3 → `_synthesize_silent()`.
2. `_synthesize_silent()` writes a valid WAV file containing only `\x00\x00` null bytes — technically a valid PCM stream. FFmpeg processes it without error.
3. `ffmpeg_merge.py:sync_scene_av` pads video to the silent WAV's duration and muxes audio. FFmpeg returns exit code `0` because the silent WAV is valid audio.
4. The final MP4 has an audio track — it just contains silence. There is no post-synthesis validation step anywhere.
5. The history entry is written as `"success"` regardless.

**Secondary cause:** On macOS, `pyttsx3` works but `gTTS` requires internet access. On the dev machine, `piper` CLI may not be in PATH (confirmed by `_piper_cli_available()` returning `False` if `shutil.which("piper") is None`). If internet is offline, gTTS also fails. The net result: `_synthesize_silent()` is reached silently (no SSE error, no history status flag).

**Evidence:**
- `piper_tts.py:119–133` — `_synthesize_silent` logs only a `WARNING` and returns normally
- `piper_tts.py:136–156` — `synthesize()` calls `_synthesize_silent()` with `if not success:` and **never raises**
- `api.py:584–586` — pipeline proceeds after `synthesize()` returns without checking if audio is real
- `ffmpeg_merge.py:75–92` — `sync_scene_av` cannot distinguish silent from voiced WAV
- `api.py:675–688` — history entry written with `"duration": "01:30"` hardcoded, no `audio_status` field

#### P2 — No Video Library Delete

**Root cause:** `Library.jsx` is entirely read-only. There is no `DELETE /api/videos/{sessionId}` backend route, no soft-delete status field in `history.json`, no UI affordance for deletion, and no filtering of `failed`/`silent` sessions from the library view.

**Evidence:**
- `Library.jsx:258–265` — only action button is `Replay Module`; no delete button
- `api.py` — no `DELETE` route for videos or sessions anywhere
- `api.py:675` — history sessions have no `status` field (only `session_id`, `topic`, `duration`, `date`, `video_path`, `subject`)
- `data/renders/` — old session folders accumulate forever with no cleanup

#### P3 — Routing Edge Cases

The v1 plan fixed the primary routing failure. Two edge cases remain:

1. **`/api/curriculum/documents` response shape mismatch:** The endpoint at `api.py:762` returns `{"documents": [...]}` (wrapped). `Workspace.jsx:43` iterates `for (const doc of docs)` where `docs` is the raw response object — not `docs.documents`. This means `doc.subject` and `doc.id` are always `undefined`, so `subjectDocMap` is never updated from the API and always stays as the static fallback.

2. **Mathematics has no indexed folder yet:** The `_STATIC_SUBJECT_DOC_MAP` in both `Workspace.jsx` and `Dashboard.jsx` does not include a Mathematics entry. When subject is "Mathematics", `docId = subjectDocMap["Mathematics"]` is `undefined`, and the retriever falls through to subject-keyword matching — but if no mathematics folder exists, it reaches "newest non-blacklisted" which may be Physics or Chemistry.

3. **Cross-subject topic graceful degradation:** If a user selects Physics but asks about Bohr's model (a Chemistry topic), the retriever correctly queries the Physics textbook but finds low-scoring or zero matches. There is no user-facing feedback about this; the pipeline proceeds with an empty curriculum context and produces a generic hallucinated video.

---

## 3. Detailed Implementation Plan

### Phase 1: Fix Inconsistent Audio (P1) — Priority: BLOCKER
**Target files:** `backend/modules/tts/piper_tts.py`, `backend/api.py`  
**Estimated time:** 3–4 hours

### Phase 2: Harden Multi-Textbook Routing (P3) — Priority: HIGH
**Target files:** `backend/api.py`, `frontend/src/screens/Workspace.jsx`, `frontend/src/screens/Dashboard.jsx`, `backend/modules/retrieval/pageindex_retriever.py`  
**Estimated time:** 2–3 hours

### Phase 3: Video Library Delete + Status Hygiene (P2) — Priority: HIGH
**Target files:** `backend/api.py`, `frontend/src/screens/Library.jsx`, `frontend/src/context/SessionContext.jsx`  
**Estimated time:** 3–4 hours

---

## 4. Specific File Changes & Code Suggestions

### 4.1 Phase 1 — Audio Consistency

#### Change 1a: `piper_tts.py` — Differentiate real from silent synthesis

The `synthesize()` function must return a flag indicating whether real audio was produced. Callers can then gate on this flag.

**File:** `backend/modules/tts/piper_tts.py`

Replace the return signature of `synthesize()`:

```python
# Current signature (line 136):
def synthesize(text: str, out_wav: Path) -> tuple[Path, float]:

# New signature:
def synthesize(text: str, out_wav: Path) -> tuple[Path, float, bool]:
    """Synthesize speech to WAV.
    
    Returns:
        (wav_path, duration_seconds, has_real_audio)
        has_real_audio is False only when _synthesize_silent fallback was used.
    """
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Synthesizing audio: %s", out_wav.name)

    success = False
    if _piper_cli_available():
        success = _synthesize_piper_cli(text, out_wav)
    if not success:
        success = _synthesize_piper_python(text, out_wav)
    if not success:
        success = _synthesize_gtts(text, out_wav)
    if not success:
        logger.warning("gTTS/Piper unavailable, trying pyttsx3 fallback")
        success = _synthesize_pyttsx3(text, out_wav)
    if not success:
        _synthesize_silent(text, out_wav)
        duration = get_audio_duration(out_wav)
        logger.error(
            "AUDIO_FALLBACK_SILENT: scene audio is SILENT for %s — "
            "all TTS backends failed. Piper CLI: %s, gTTS: requires internet, "
            "pyttsx3: requires system TTS. Duration: %.2fs",
            out_wav.name, _piper_cli_available(), duration,
        )
        return out_wav, duration, False  # <-- has_real_audio = False

    duration = get_audio_duration(out_wav)
    logger.info("Audio synthesized: %s (%.2fs) [real]", out_wav, duration)
    return out_wav, duration, True  # <-- has_real_audio = True
```

#### Change 1b: `api.py` — Detect and block silent videos

In `run_pipeline_task`, Stage 4 (TTS synthesis), collect audio quality status and abort the pipeline if all scenes produce silent audio:

```python
# --- Stage 4: Synthesize Audio --- (api.py ~line 580)
await queue.put({"stage": "tts", "progress": 75, "message": "[4/8] Running offline TTS audio synthesizer per scene..."})
audio_paths = {}
silent_scenes = []

for plan in plans:
    sid = plan["scene_id"]
    wav_path = ROOT / "data" / "audio" / f"scene_{sid}.wav"
    wav, _duration, has_real_audio = synthesize(plan["narration"], wav_path)
    audio_paths[sid] = wav
    if not has_real_audio:
        silent_scenes.append(sid)
        logger.error(
            "SILENT_AUDIO scene_id=%d topic=%r subject=%r — "
            "video will be muted unless TTS is fixed",
            sid, topic, subject
        )

# Abort if ALL scenes are silent (total failure), warn if SOME are silent
if len(silent_scenes) == len(plans):
    raise RuntimeError(
        f"TTS synthesis failed for all {len(plans)} scenes. "
        "No real audio produced. Check Piper installation, gTTS internet access, "
        "or pyttsx3 system TTS. Silent video not saved to library."
    )
elif silent_scenes:
    logger.warning(
        "PARTIAL_SILENT_AUDIO: scenes %s are silent (out of %d total). "
        "Video will have mixed audio quality.",
        silent_scenes, len(plans)
    )

await queue.put({"stage": "tts", "progress": 80, "message": "Narration voiceovers generated successfully!"})
```

Then in the history save section (~line 675), add `audio_status`:

```python
history_data["sessions"].insert(0, {
    "session_id": session_id,
    "topic": topic,
    "duration": "01:30",
    "duration_seconds": duration_seconds,
    "date": session_date,
    "completed_at": completed_at,
    "video_path": video_url,
    "subject": session_subject,
    "follow_up_count": 0,
    "audio_status": "silent" if len(silent_scenes) == len(plans) else (
        "partial" if silent_scenes else "ok"
    ),
    "status": "success",  # pipeline completed
})
```

#### Change 1c: `api.py` — Add `DELETE /api/videos/{session_id}` (needed for P2, but the status field above enables filtering)

This endpoint is detailed in Phase 3 (section 4.3). The `audio_status` field added above is what makes silent-video filtering possible in Phase 3.

#### Change 1d: `api.py` — Add a `/api/audio/test` diagnostic endpoint

This helps identify TTS configuration issues in production without running the full pipeline:

```python
@app.get("/api/audio/test")
async def audio_test():
    """Diagnose TTS availability without running the full pipeline."""
    from modules.tts.piper_tts import _piper_cli_available, _synthesize_piper_python
    import shutil
    return {
        "piper_cli": shutil.which("piper") is not None,
        "gtts_importable": _check_import("gtts"),
        "pyttsx3_importable": _check_import("pyttsx3"),
        "pydub_importable": _check_import("pydub"),
        "internet_likely": _check_internet(),
    }

def _check_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

def _check_internet() -> bool:
    import socket
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False
```

---

### 4.2 Phase 2 — Multi-Textbook Routing Hardening

#### Change 2a: `Workspace.jsx` and `Dashboard.jsx` — Fix the documents API response shape bug

**This is the single most impactful fix.** The endpoint returns `{"documents": [...]}` but the frontend iterates the wrapper object directly.

**File:** `frontend/src/screens/Workspace.jsx` (line 40–47) and same pattern in `Dashboard.jsx` (line 43–50)

```javascript
// Current (broken):
const docs = await res.json();
const map = { ..._STATIC_SUBJECT_DOC_MAP };
for (const doc of docs) {   // <-- iterates the wrapper object {documents:[...]}

// Fixed:
const json = await res.json();
const docs = json.documents || json;  // handle both wrapped and bare array
const map = { ..._STATIC_SUBJECT_DOC_MAP };
for (const doc of (Array.isArray(docs) ? docs : [])) {
    if (doc.subject && doc.id) {
        map[doc.subject] = doc.id;
    }
}
```

Apply this identical fix in both `Workspace.jsx` and `Dashboard.jsx`.

#### Change 2b: Add Mathematics to the static fallback map

Both `Workspace.jsx` and `Dashboard.jsx` have:

```javascript
const _STATIC_SUBJECT_DOC_MAP = {
  Chemistry: 'Chemistry.pdf',
  Physics: 'SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf',
};
```

Add Mathematics (update when a mathematics PDF is indexed):

```javascript
const _STATIC_SUBJECT_DOC_MAP = {
  Chemistry: 'Chemistry.pdf',
  Physics: 'SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf',
  Mathematics: null,  // null = no document indexed yet; retriever will use subject-keyword fallback
};
```

With `null`, the `docId` passed to `startPipeline` is `null`, and `_resolve_doc_folder(None, subject="Mathematics")` correctly falls to subject-keyword matching, then to "newest non-blacklisted", rather than an incorrect static string.

#### Change 2c: `pageindex_retriever.py` — Add cross-subject mismatch detection

In `retrieve_curriculum_sections`, after scoring, detect if the best match score is very low (suggesting the topic doesn't exist in the selected document):

```python
# Add after: top_matches = [(n, s) for n, s in scored[:_TOP_K] if s > 0]  (line 368)

_CROSS_SUBJECT_THRESHOLD = 1.0  # minimum acceptable score for "on-topic" retrieval

if top_matches:
    best_score = top_matches[0][1]
    if best_score < _CROSS_SUBJECT_THRESHOLD:
        logger.warning(
            "LOW_SCORE_MATCH topic=%r document=%r best_score=%.2f — "
            "topic may not exist in the selected subject's textbook. "
            "Consider checking if the correct subject was selected.",
            topic, folder, best_score,
        )
```

#### Change 2d: `api.py` — Surface cross-subject mismatch warnings in SSE events

In Stage 0 of `run_pipeline_task`, after `retrieve_curriculum_sections`, if no sections were found or the best score is very low, emit a warning SSE event (not an error — the pipeline continues with a warning):

```python
# After the curriculum section retrieval logging (~line 419)
if not curriculum_sections:
    await queue.put({
        "stage": "retrieving",
        "progress": 8,
        "message": (
            f"Warning: No matching sections found for '{topic}' in the selected "
            f"{subject} textbook. The video will be generated from general knowledge. "
            "Try switching subject or rephrasing your topic."
        ),
        "warning": "no_curriculum_match",
    })
elif curriculum_sections and curriculum_sections[0].get("score", 0) < 1.0:
    await queue.put({
        "stage": "retrieving",
        "progress": 8,
        "message": (
            f"Note: Weak curriculum match for '{topic}' in {subject}. "
            "Content may be from general knowledge."
        ),
        "warning": "low_curriculum_score",
    })
```

#### Change 2e: `pageindex_retriever.py` — Expose `resolution_source` in `list_documents()`

Currently `list_documents()` does not expose what subjects are actually available. Add a helper used by the health endpoint to make routing decisions transparent:

```python
# In list_documents(), enrich each entry:
docs.append({
    "id": folder.name,
    "doc_name": doc_name,
    "node_count": len(nodes),
    "subject": _guess_subject(doc_name),
    "subject_keywords_matched": [
        kw for subj, kws in _SUBJECT_KEYWORDS.items()
        for kw in kws if kw in folder.name.lower()
    ],
})
```

---

### 4.3 Phase 3 — Video Library Delete + Status Hygiene

#### Change 3a: `api.py` — Add `DELETE /api/videos/{session_id}` endpoint

```python
@app.delete("/api/videos/{session_id}")
async def delete_video(session_id: str):
    """Delete a video session: remove MP4 from disk and entry from history.json."""
    if not session_id or ".." in session_id or "/" in session_id:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    errors = []

    # 1. Remove render directory from disk
    render_dir = ROOT / "data" / "renders" / session_id
    if render_dir.is_dir():
        try:
            shutil.rmtree(render_dir)
            logger.info("Deleted render dir: %s", render_dir)
        except Exception as e:
            errors.append(f"disk_delete_failed: {e}")
            logger.error("Failed to delete render dir %s: %s", render_dir, e)
    else:
        logger.info("Render dir not found (already deleted?): %s", render_dir)

    # 2. Remove from history.json
    history_data = _load_user_json("history.json", {"sessions": []})
    original_count = len(history_data.get("sessions", []))
    history_data["sessions"] = [
        s for s in history_data.get("sessions", [])
        if s.get("session_id") != session_id
    ]
    removed_count = original_count - len(history_data["sessions"])

    if removed_count > 0:
        try:
            _save_user_json("history.json", history_data)
            _sync_analytics_from_history()
            logger.info("Removed %d session(s) from history: %s", removed_count, session_id)
        except Exception as e:
            errors.append(f"history_update_failed: {e}")

    if errors:
        return JSONResponse(
            status_code=207,
            content={"deleted": removed_count > 0, "errors": errors, "session_id": session_id}
        )

    return {"deleted": True, "session_id": session_id, "removed_from_history": removed_count}
```

#### Change 3b: `api.py` — Add `GET /api/videos` endpoint (Video Library API)

Currently `Library.jsx` loads `history.json` raw from `/api/load/history.json`. This mixes persistence with display. Add a dedicated endpoint that returns only clean, displayable sessions:

```python
@app.get("/api/videos")
async def list_videos(subject: Optional[str] = None, status: Optional[str] = None):
    """Return filtered, display-ready video sessions for the Library.
    
    Query params:
        subject: filter by subject (Physics, Chemistry, etc.)
        status:  filter by status (success, failed, silent, partial)
                 Defaults to showing only 'success' sessions.
    """
    history_data = _load_user_json("history.json", {"sessions": []})
    sessions = history_data.get("sessions", [])

    # Default: only show sessions with status='success' (or legacy sessions with no status field)
    allowed_statuses = {status} if status else {"success", None}  # None = legacy sessions

    results = []
    for s in sessions:
        s_status = s.get("status")  # None for legacy sessions
        s_audio = s.get("audio_status", "ok")  # "ok", "silent", "partial"

        # Filter by status
        if s_status not in allowed_statuses:
            continue

        # Filter by subject
        if subject and s.get("subject") != subject:
            continue

        # Build a clean display object
        results.append({
            "session_id": s.get("session_id"),
            "topic": s.get("topic"),
            "subject": s.get("subject"),
            "date": s.get("date"),
            "completed_at": s.get("completed_at"),
            "duration_seconds": s.get("duration_seconds", 90),
            "video_path": s.get("video_path") or s.get("video_url"),
            "follow_up_count": s.get("follow_up_count", 0),
            "audio_status": s_audio,
            "status": s_status or "success",
        })

    return {"videos": results, "total": len(results)}
```

#### Change 3c: `Library.jsx` — Migrate to `/api/videos`, add delete button

Replace the entire data-fetching approach and add delete functionality:

```jsx
// Replace fetchHistory useEffect (lines 15–29) with:
const [isDeleting, setIsDeleting] = useState(null); // session_id being deleted

useEffect(() => {
  async function fetchVideos() {
    try {
      const response = await fetch('/api/videos');
      if (response.ok) {
        const data = await response.json();
        setHistoryData({ sessions: data.videos || [] });
        setFilteredSessions(data.videos || []);
      }
    } catch (err) {
      console.warn('Failed to load video library:', err);
    }
  }
  fetchVideos();
}, []);

const handleDeleteVideo = async (sessionId, e) => {
  e.stopPropagation();  // prevent card click
  if (!window.confirm('Delete this video? This cannot be undone.')) return;
  
  setIsDeleting(sessionId);
  try {
    const res = await fetch(`/api/videos/${sessionId}`, { method: 'DELETE' });
    if (res.ok) {
      setHistoryData(prev => ({
        sessions: prev.sessions.filter(s => s.session_id !== sessionId)
      }));
    } else {
      console.error('Delete failed:', await res.text());
    }
  } catch (err) {
    console.error('Delete error:', err);
  } finally {
    setIsDeleting(null);
  }
};
```

Add delete button inside the session card (after the "Replay Module" button):

```jsx
// Replace the bottom button section (lines 248–265) with:
<div style={{ display: 'flex', gap: 'var(--space-2)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)', marginTop: 'auto' }}>
  <button
    onClick={() => handlePlayVideo(sessionItem.session_id)}
    className="btn btn-primary"
    style={{ padding: '6px 12px', fontSize: '12px', flex: 1 }}
  >
    Replay Module
  </button>
  <button
    onClick={(e) => handleDeleteVideo(sessionItem.session_id, e)}
    disabled={isDeleting === sessionItem.session_id}
    className="btn btn-ghost"
    style={{
      padding: '6px 10px',
      fontSize: '12px',
      color: 'var(--color-red, #ef4444)',
      borderColor: 'var(--color-red, #ef4444)',
      opacity: isDeleting === sessionItem.session_id ? 0.5 : 1,
    }}
    title="Delete this video"
  >
    {isDeleting === sessionItem.session_id ? '...' : '✕'}
  </button>
</div>
```

#### Change 3d: `Library.jsx` — Filter silent/failed videos from default view

Add a visual badge for `audio_status` and optionally hide silent sessions:

```jsx
// Add audio status badge in card Info Text section, after SubjectPill:
{sessionItem.audio_status === 'silent' && (
  <span style={{ fontSize: '10px', color: 'var(--color-red, #ef4444)', background: 'rgba(239,68,68,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
    No Audio
  </span>
)}
{sessionItem.audio_status === 'partial' && (
  <span style={{ fontSize: '10px', color: '#f59e0b', background: 'rgba(245,158,11,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
    Partial Audio
  </span>
)}
```

For production demo mode, add a toggle to hide problematic videos:

```jsx
const [hideProblematic, setHideProblematic] = useState(false);

// In filter useEffect, add:
if (hideProblematic) {
  result = result.filter(s => s.audio_status === 'ok' || !s.audio_status);
}
```

#### Change 3e: `api.py` — History save: never save pipeline errors to history

Currently `api.py:700–707` catches pipeline exceptions and only emits an SSE error event. History is NOT written on failure (the history write at line 661 is inside the try block before the error). However, the `session.json` file IS overwritten at line 646 with `pipeline_stage: "complete"`. This means loading from `session.json` after a failed pipeline shows a ghost session.

Fix: write `session.json` only on success, or mark it clearly on error:

```python
# In the except block (api.py ~line 700), add:
except Exception as e:
    logger.error(f"Error in pipeline generation: {e}", exc_info=True)
    # Mark session.json as failed so Library doesn't show ghost sessions
    try:
        session_file_path = USER_DATA_DIR / "session.json"
        if session_file_path.exists():
            existing = json.loads(session_file_path.read_text(encoding="utf-8"))
            existing["pipeline_stage"] = "error"
            existing["error_message"] = str(e)
            _save_user_json("session.json", existing)
    except Exception:
        pass
    await queue.put({
        "stage": "error",
        "progress": 100,
        "message": f"Pipeline generation failed: {str(e)}",
        "data": None
    })
```

---

## 5. Frontend Changes Required

### 5.1 `Workspace.jsx`
| Location | Change | Priority |
|----------|--------|----------|
| Line 40–47 (`fetchDocMap`) | Fix `docs` → `json.documents || json` to unpack the API response wrapper | **BLOCKER** |
| `_STATIC_SUBJECT_DOC_MAP` | Add `Mathematics: null` | HIGH |

### 5.2 `Dashboard.jsx`
| Location | Change | Priority |
|----------|--------|----------|
| Lines 43–50 (`fetchDocMap`) | Same fix as Workspace — unpack `json.documents` | **BLOCKER** |
| `_STATIC_SUBJECT_DOC_MAP` | Add `Mathematics: null` | HIGH |

### 5.3 `Library.jsx`
| Location | Change | Priority |
|----------|--------|----------|
| `fetchHistory` useEffect | Replace with `/api/videos` call (returns only clean sessions) | HIGH |
| Session card bottom buttons | Add delete button with `handleDeleteVideo` | HIGH |
| Info Text section | Add audio status badge (`silent` / `partial`) | MEDIUM |
| Filter state | Add `hideProblematic` toggle for demo mode | MEDIUM |

### 5.4 `SessionContext.jsx`
No changes required for the core fixes. However, `loadSessionById` at line 316 loads sessions from `session.json` and falls back to `history.json`. If `session.json` has `pipeline_stage: "error"` after the fix above, the Workspace will correctly show an error state. No code change needed.

---

## 6. Backend API & Pipeline Changes

### 6.1 New Endpoints

| Method | Route | File | Purpose |
|--------|-------|------|---------|
| `DELETE` | `/api/videos/{session_id}` | `api.py` | Delete video from disk + history |
| `GET` | `/api/videos` | `api.py` | Filtered video listing for Library |
| `GET` | `/api/audio/test` | `api.py` | TTS diagnostic endpoint |

### 6.2 Modified Endpoints / Functions

| Function | File | Change |
|----------|------|--------|
| `synthesize()` | `piper_tts.py` | Return `(path, duration, has_real_audio: bool)` |
| `run_pipeline_task()` | `api.py` | Use `has_real_audio` flag; abort on total silence; add `audio_status` to history |
| `list_documents()` | `pageindex_retriever.py` | Add `subject_keywords_matched` field |
| `retrieve_curriculum_sections()` | `pageindex_retriever.py` | Log `LOW_SCORE_MATCH` warning when best score < 1.0 |
| `run_pipeline_task()` | `api.py` | Emit warning SSE when no curriculum match or low score |

### 6.3 Data Model Changes

**`history.json` sessions** — add two new fields:
```json
{
  "session_id": "session_1234567890",
  "topic": "Bohr's Model",
  "status": "success",
  "audio_status": "ok",
  ...
}
```
`status`: `"success"` | `"failed"` (previously only success was written)  
`audio_status`: `"ok"` | `"partial"` | `"silent"`

**Backward compatibility:** Old sessions without these fields are treated as `status: "success"`, `audio_status: "ok"` by the `/api/videos` endpoint.

---

## 7. Testing & Validation Steps

### 7.1 Audio Fix Validation

**Test 1 — Happy path (real TTS available):**
```bash
# Start backend, ensure piper or gTTS is available
python api.py

# Run a pipeline request
curl -X POST http://localhost:5000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "Bohr Model", "subject": "Chemistry", "documentId": "Chemistry.pdf"}'

# Check the result MP4 has audio
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name \
  backend/data/renders/session_*/manim_*.mp4
# Expected: codec_name = aac (not empty)

# Check history entry
cat backend/data/user/history.json | python3 -c "import json,sys; s=json.load(sys.stdin)['sessions'][0]; print(s.get('audio_status'))"
# Expected: ok
```

**Test 2 — Forced silent fallback (simulate TTS failure):**
```bash
# Temporarily break TTS by setting PATH to exclude piper and blocking gTTS
# Then run a pipeline — the abort logic should trigger

# Check SSE output contains stage=error with message "TTS synthesis failed"
# Check history.json is NOT updated (no new session added for full-silent failure)
```

**Test 3 — Audio diagnostic endpoint:**
```bash
curl http://localhost:5000/api/audio/test
# Expected: shows which backends are available
```

### 7.2 Routing Fix Validation

**Test 4 — Document API shape fix:**
```bash
# Open browser console on Workspace, check:
# Before fix: subjectDocMap stays as static fallback (Chemistry: 'Chemistry.pdf')
# After fix: map is populated from /api/curriculum/documents response

# Backend check:
curl http://localhost:5000/api/curriculum/documents
# Response: {"documents": [...]} 
# Frontend must iterate data.documents, not data
```

**Test 5 — Chemistry routing:**
```bash
# Generate a session for "Bohr Model" with Chemistry subject
# Check retrieval_audit.json
cat backend/data/json/retrieval_audit.json | python3 -c \
  "import json,sys; a=json.load(sys.stdin); print(a['document_id'], [s['title'] for s in a['sections']])"
# Expected: document_id contains "Chemistry", sections contain atomic structure nodes
```

**Test 6 — Cross-subject mismatch warning:**
```bash
# Generate session: topic="Bohr Model", subject="Physics"
# Check backend logs for LOW_SCORE_MATCH warning
# Check SSE events stream for warning message to frontend
```

### 7.3 Delete Functionality Validation

**Test 7 — Delete via API:**
```bash
SESSION_ID="session_1234567890"  # use a real session_id from history

# Delete via API
curl -X DELETE http://localhost:5000/api/videos/$SESSION_ID
# Expected: {"deleted": true, "session_id": "...", "removed_from_history": 1}

# Verify disk cleanup
ls backend/data/renders/$SESSION_ID  # should fail (directory removed)

# Verify history cleanup
curl http://localhost:5000/api/load/history.json | python3 -c \
  "import json,sys; h=json.load(sys.stdin); print([s['session_id'] for s in h['sessions']])"
# Session ID should not appear
```

**Test 8 — Library delete button:**
- Open Library screen in browser
- Hover over a session card — delete button (✕) appears in bottom right
- Click ✕ → confirmation dialog appears
- Confirm → card disappears from grid, no page reload needed
- Reload Library → session still gone

**Test 9 — `/api/videos` filtering:**
```bash
# All successful videos
curl "http://localhost:5000/api/videos"

# Only Chemistry videos
curl "http://localhost:5000/api/videos?subject=Chemistry"

# Failed videos (for debugging)
curl "http://localhost:5000/api/videos?status=failed"
```

---

## 8. Risks & Rollback Considerations

### 8.1 Audio Fix Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Existing callers of `synthesize()` break (return tuple arity change) | MEDIUM | Search all call sites: only `api.py:585` calls it. Update that one caller. |
| Pipeline aborts on fully-silent batch, leaving mid-pipeline state | LOW | The abort raises `RuntimeError` inside the try block; SSE error is emitted; history is NOT written (correct). |
| `has_real_audio=False` for gTTS if network is offline during dev | LOW | The warning-only mode for partial silence still saves the video; only total silence aborts. |

**Rollback:** Revert `synthesize()` to return 2-tuple and remove the `silent_scenes` check in `api.py`. Audio inconsistency returns but nothing breaks.

### 8.2 Routing Fix Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `json.documents || json` shape check breaks future API changes | LOW | Backend `/api/curriculum/documents` consistently wraps in `{"documents": [...]}` |
| Setting `Mathematics: null` in static map triggers null-as-docId path unexpectedly | LOW | `_resolve_doc_folder(None, "Mathematics")` already handles this correctly via subject-keyword matching |
| Cross-subject warning SSE confuses users | LOW | Warning message is informational, not blocking |

**Rollback:** Revert `docs` line to `const docs = await res.json()` — dynamic map doesn't populate but static fallback still works for Chemistry and Physics.

### 8.3 Delete Functionality Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `shutil.rmtree` on wrong directory if `session_id` has path traversal | LOW | `".." in session_id or "/" in session_id` validation guard in endpoint |
| User accidentally deletes the only copy of a successful video | MEDIUM | Confirmation dialog in UI; no undo. Consider adding a 30-second grace period in UI before actual deletion (medium-term). |
| `/api/videos` endpoint excludes legacy sessions (no `status` field) | LOW | `None` is in `allowed_statuses` by default, so legacy sessions are shown |
| `_sync_analytics_from_history()` after delete may briefly show stale counts | LOW | Analytics are recomputed synchronously before returning from DELETE |

**Rollback:** Remove the DELETE route and the `/api/videos` route, revert `Library.jsx` to use `/api/load/history.json` directly.

---

## 9. Recommended Order of Implementation

### Immediate (Do Today — ≤4 hours total)

These are the two highest-impact, lowest-risk changes:

**Step 1 — Fix the `docs` response shape bug in Workspace.jsx and Dashboard.jsx** (30 min)  
This is a one-line fix that immediately makes dynamic subject→docId routing work correctly. Without this, the `_STATIC_SUBJECT_DOC_MAP` is always used and the dynamically indexed document IDs from the backend are never consumed.

- File: `frontend/src/screens/Workspace.jsx`, line 43
- File: `frontend/src/screens/Dashboard.jsx`, line 44
- Change: `for (const doc of docs)` → `for (const doc of (json.documents || []))`
- Test: Open browser console on Workspace, verify map is populated after API call

**Step 2 — Add `has_real_audio` return flag to `synthesize()`** (45 min)  
Update `piper_tts.py` to return a 3-tuple. Update the one call site in `api.py`. Add `audio_status` field to history saves. Add the total-silence abort guard.

- File: `backend/modules/tts/piper_tts.py`, function `synthesize()` 
- File: `backend/api.py`, Stage 4 and history write section
- Test: Run `/api/audio/test` to confirm backend TTS status; simulate silent fallback

### Short-term (Do This Week — 3–4 hours)

**Step 3 — Add `DELETE /api/videos/{session_id}` endpoint** (1.5 hours)  
Add the delete route to `api.py` with proper validation and disk + history cleanup.

**Step 4 — Update `Library.jsx` with delete button + migrate to `/api/videos`** (1.5 hours)  
Replace `fetchHistory` with `fetchVideos`, add delete button to cards, add `audio_status` badge.

**Step 5 — Add `/api/videos` GET endpoint** (45 min)  
Filtered listing for Library.jsx with `status` and `subject` params.

### Medium-term (Next Sprint — 1–2 hours)

**Step 6 — Cross-subject mismatch SSE warning** (1 hour)  
Surface the `LOW_SCORE_MATCH` warning from `pageindex_retriever.py` into the frontend SSE stream so users see a gentle "this topic may not be in your selected textbook" message before the video generates.

**Step 7 — Mathematics document indexing** (depends on PDF availability)  
Index a Mathematics textbook PDF via `/api/curriculum/index`. Update the static fallback map once the folder name is known.

**Step 8 — `/api/audio/test` diagnostic endpoint** (30 min)  
Useful for production debugging but not user-facing.

---

## 10. Mode Recommendation

| Phase | Work Type | Recommended Mode |
|-------|-----------|-----------------|
| Step 1 (frontend docs shape fix) | Small, surgical, one-line fix × 2 files | **Agent Mode** — straightforward implementation |
| Step 2 (audio flag + abort guard) | Backend logic change with clear spec | **Agent Mode** — implement now |
| Steps 3–5 (delete API + Library UI) | Backend route + frontend component changes | **Agent Mode** — well-defined changes |
| Step 6 (cross-subject warning SSE) | Requires discussion on UX messaging | **Plan Mode first**, then Agent |
| Step 7 (Math PDF indexing) | Operational task, not code | Shell / manual operation |

**Bottom line:** Steps 1–5 can all be executed directly in Agent Mode now. Step 6 warrants a brief Plan Mode discussion on what the user-facing warning message should say and where it appears in the UI. Steps 7–8 are operational/convenience tasks.

---

## Appendix A: File Change Matrix

| File | Phase | Type | Lines Changed (est.) |
|------|-------|------|---------------------|
| `backend/modules/tts/piper_tts.py` | P1 | Modify | ~20 |
| `backend/api.py` | P1, P2, P3 | Modify + Add | ~80 |
| `backend/modules/retrieval/pageindex_retriever.py` | P2 | Modify | ~20 |
| `frontend/src/screens/Workspace.jsx` | P2 | Modify | ~5 |
| `frontend/src/screens/Dashboard.jsx` | P2 | Modify | ~5 |
| `frontend/src/screens/Library.jsx` | P3 | Modify | ~60 |

Total estimated lines changed: ~190 across 6 files. No new files need to be created.

---

## Appendix B: Known Non-Issues (Do Not Rework)

The following work from `production_implementation_plan.md` is confirmed complete and should **not** be re-implemented:

- `_resolve_doc_folder` routing chain (5 priorities) — verified working in code
- `_score_node` word-boundary regex + tag boost — verified present at lines 265–303
- Chemistry templates (12 files in `templates/chemistry/`) — verified on disk
- `ilovepdf_merged.pdf` blacklist — verified in `_BLACKLISTED_AUTO_FOLDERS`
- Retrieval audit log — verified at `api.py:424–450`
- `documentId` passed from `Workspace.jsx` to `startPipeline` — verified at line 68–69
- `documentId` passed from `Dashboard.jsx` — verified in `handleSuggestionClick`
- Grounding validator — verified in `api.py:516–528`
