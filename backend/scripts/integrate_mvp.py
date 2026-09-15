"""One-time integration patch applied during development."""
from pathlib import Path
p = Path("backend/api.py")
s = p.read_text()
start = s.index("async def run_pipeline_task(")
end = s.index('@app.get("/api/curriculum/documents")', start)
s = s[:start] + '''
async def run_pipeline_task(session_id, gemini_key=None, nvidia_key=None, target_concept_id=None):
    from modules.learning.pipeline import run_lesson
    loop = asyncio.get_running_loop()
    job = ACTIVE_JOBS[session_id]
    def emit(event):
        def append():
            job["events"].append(event)
            job["status"] = event["stage"]
        loop.call_soon_threadsafe(append)
    result = await asyncio.to_thread(run_lesson, session_id, emit,
        target_concept_id=target_concept_id, gemini_key=gemini_key, nvidia_key=nvidia_key)
    if result:
        # Keep existing Library/session loading compatible with the new knowledge store.
        payload = {"session_id": session_id, "topic_query": job["topic"],
            "topic_resolved": job["topic"], "pipeline_stage": "complete", **result,
            "messages": [], "notes": result["explanation_package"]["core_explanation"]}
        _save_user_json("session.json", payload)
        history = _load_user_json("history.json", {"sessions": []})
        duration = result["provenance"]["duration_seconds"]
        history["sessions"].insert(0, {"session_id": session_id, "topic": job["topic"],
            "video_path": result["video_url"], "duration_seconds": duration,
            "duration": f"{int(duration)//60:02d}:{int(duration)%60:02d}",
            "date": datetime.now().date().isoformat(), "subject": job["subject"]})
        _save_user_json("history.json", history)
        _sync_analytics_from_history()


@app.post("/api/pipeline/run")
async def start_pipeline(req: PipelineRunRequest, background_tasks: BackgroundTasks):
    from modules.learning.knowledge import build_topic
    from modules.learning.routes import invoke
    from modules.rag.store import KnowledgeStore
    store = KnowledgeStore()
    if req.session_id:
        knowledge = invoke(store.load, req.session_id)
    else:
        knowledge, _ = await asyncio.to_thread(invoke, build_topic, req.topic, req.subject, req.documentId)
    session_id = knowledge.session_id
    if session_id in ACTIVE_JOBS and ACTIVE_JOBS[session_id]["status"] not in ("complete", "error"):
        raise HTTPException(409, "This learning session already has an active lesson")
    if req.learnerProfile:
        knowledge.learner_profile = req.learnerProfile.model_dump()
        store.save(knowledge)
    ACTIVE_JOBS[session_id] = {"topic": knowledge.topic, "subject": knowledge.subject,
        "events": [], "status": "queued"}
    background_tasks.add_task(run_pipeline_task, session_id,
        req.geminiApiKey or req.apiKey, req.nvidiaApiKey, req.target_concept_id)
    return {"sessionId": session_id, "resolvedTopic": knowledge.topic}


@app.get("/api/pipeline/status/{session_id}")
async def get_pipeline_status(session_id: str):
    job = ACTIVE_JOBS.get(session_id)
    if not job:
        raise HTTPException(404, "No active job; use the session provenance endpoint for persisted history")
    async def stream():
        cursor = 0
        while True:
            while cursor < len(job["events"]):
                event = job["events"][cursor]
                cursor += 1
                yield f"data: {json.dumps(event)}\\n\\n"
                if event["stage"] in ("complete", "error"):
                    return
            await asyncio.sleep(.2)
    return StreamingResponse(stream(), media_type="text/event-stream")

''' + s[end:]
s = s.replace('    subject: str\n    documentId:', '    subject: str = ""\n    session_id: Optional[str] = None\n    target_concept_id: Optional[str] = None\n    remediation_mode: bool = False\n    documentId:')
s = s.replace('class ChatRequest(BaseModel):', 'class ChatRequest(BaseModel):\n    session_id: Optional[str] = None')
s = s.replace('def chat(request: ChatRequest):', '''def chat(request: ChatRequest):
    if request.session_id:
        from modules.learning.tutor import answer_session
        from modules.learning.routes import invoke
        return invoke(answer_session, request.session_id, request.message,
                      [m.model_dump() for m in request.history])
''')
s = s.replace('    allow_origins=["*"],', '    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3002").split(","),')
anchor = '# Active jobs tracking for SSE status streaming'
s = s.replace(anchor, '''from modules.learning.routes import router as learning_router
app.include_router(learning_router)

# Basic local MVP throttling. A production multi-worker service needs a shared limiter.
from collections import defaultdict, deque
_request_times = defaultdict(deque)

@app.middleware("http")
async def throttle_expensive_requests(request, call_next):
    expensive = request.method == "POST" and any(x in request.url.path for x in
        ("pipeline/run", "materials/upload", "learning/sessions", "providers/health", "/relearn", "/api/chat"))
    if expensive:
        key = request.client.host if request.client else "local"
        timestamps = _request_times[key]
        current = time.monotonic()
        while timestamps and current - timestamps[0] > 60:
            timestamps.popleft()
        if len(timestamps) >= int(os.getenv("EXPENSIVE_REQUESTS_PER_MINUTE", "20")):
            return JSONResponse(status_code=429, content={"detail": "Please wait before another expensive request."})
        timestamps.append(current)
    return await call_next(request)

''' + anchor)
p.write_text(s)
