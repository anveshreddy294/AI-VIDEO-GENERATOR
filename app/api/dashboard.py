"""VisualAI Dashboard — Clean landing page showing the exact workflow."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Student Knowledge Platform</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1117;
            color: #e1e4e8;
            min-height: 100vh;
        }

        .header {
            background: #161b22;
            border-bottom: 1px solid #21262d;
            padding: 20px 40px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header h1 {
            font-size: 22px;
            font-weight: 600;
            color: #f0f6fc;
            letter-spacing: -0.5px;
        }

        .header .version {
            font-size: 12px;
            color: #8b949e;
            background: #21262d;
            padding: 4px 10px;
            border-radius: 12px;
        }

        .nav-links a {
            color: #58a6ff;
            text-decoration: none;
            margin-left: 24px;
            font-size: 14px;
            font-weight: 500;
        }

        .nav-links a:hover { color: #79c0ff; }

        .container {
            max-width: 960px;
            margin: 0 auto;
            padding: 48px 40px;
        }

        .flow-title {
            font-size: 28px;
            font-weight: 700;
            color: #f0f6fc;
            margin-bottom: 8px;
        }

        .flow-subtitle {
            font-size: 15px;
            color: #8b949e;
            margin-bottom: 48px;
            line-height: 1.6;
        }

        .step {
            display: flex;
            gap: 24px;
            margin-bottom: 0;
            position: relative;
        }

        .step:not(:last-child) {
            padding-bottom: 32px;
        }

        .step-indicator {
            flex-shrink: 0;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: 700;
            position: relative;
            z-index: 1;
        }

        .step:not(:last-child) .step-indicator::after {
            content: '';
            position: absolute;
            top: 52px;
            left: 50%;
            transform: translateX(-50%);
            width: 2px;
            height: calc(100% + 24px);
            background: #21262d;
        }

        .step-1 .step-indicator { background: #1f6feb; color: #fff; }
        .step-2 .step-indicator { background: #238636; color: #fff; }
        .step-3 .step-indicator { background: #9e6a03; color: #fff; }
        .step-4 .step-indicator { background: #8957e5; color: #fff; }
        .step-5 .step-indicator { background: #da3633; color: #fff; }

        .step-content {
            flex: 1;
            padding-top: 4px;
        }

        .step-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }

        .step-1 .step-label { color: #58a6ff; }
        .step-2 .step-label { color: #3fb950; }
        .step-3 .step-label { color: #d29922; }
        .step-4 .step-label { color: #a371f7; }
        .step-5 .step-label { color: #f85149; }

        .step-name {
            font-size: 18px;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 8px;
        }

        .step-desc {
            font-size: 14px;
            color: #8b949e;
            line-height: 1.6;
            margin-bottom: 12px;
        }

        .step-endpoint {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 6px;
            padding: 8px 14px;
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 13px;
        }

        .method {
            font-weight: 700;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 3px;
        }

        .method-post { background: #238636; color: #fff; }
        .method-get { background: #1f6feb; color: #fff; }

        .endpoint-path { color: #e1e4e8; }

        .io-box {
            margin-top: 12px;
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 16px;
        }

        .io-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #8b949e;
            margin-bottom: 8px;
        }

        .io-content {
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 12px;
            color: #c9d1d9;
            line-height: 1.8;
        }

        .io-content .key { color: #79c0ff; }
        .io-content .val { color: #a5d6ff; }
        .io-content .comment { color: #484f58; }

        .divider {
            height: 1px;
            background: #21262d;
            margin: 48px 0;
        }

        .links-section h2 {
            font-size: 20px;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 20px;
        }

        .links-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .link-card {
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 16px;
            text-decoration: none;
            transition: border-color 0.2s;
        }

        .link-card:hover { border-color: #388bfd; }

        .link-card .link-title {
            font-size: 14px;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 4px;
        }

        .link-card .link-desc {
            font-size: 12px;
            color: #8b949e;
        }

        .link-card .link-url {
            font-family: monospace;
            font-size: 12px;
            color: #58a6ff;
            margin-top: 8px;
            display: block;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            color: #3fb950;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background: #3fb950;
            border-radius: 50%;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>VisualAI</h1>
        <div style="display:flex;align-items:center;gap:16px;">
            <span class="status-badge"><span class="status-dot"></span> Server Online</span>
            <span class="version">v0.2.0</span>
            <nav class="nav-links">
                <a href="/docs">API Docs</a>
                <a href="/redoc">ReDoc</a>
                <a href="/health">Health</a>
            </nav>
        </div>
    </div>

    <div class="container">
        <h2 class="flow-title">How It Works</h2>
        <p class="flow-subtitle">
            Upload study material → System extracts knowledge → Generate quiz → Track mastery
        </p>

        <!-- Step 1 -->
        <div class="step step-1">
            <div class="step-indicator">1</div>
            <div class="step-content">
                <div class="step-label">Ingestion</div>
                <div class="step-name">Upload Study Material</div>
                <div class="step-desc">
                    Upload a PDF, image, text file, or lecture video.
                    The system extracts text, describes diagrams via AI vision,
                    transcribes speech, and builds a structured knowledge graph.
                </div>
                <div class="step-endpoint">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/upload</span>
                </div>
                <div class="io-box">
                    <div class="io-label">Input → Output</div>
                    <div class="io-content">
                        <span class="comment">// Upload any supported file</span><br>
                        file: physics_chapter.pdf<br><br>
                        <span class="comment">// Returns structured JSON blueprint</span><br>
                        {<br>
                        &nbsp;&nbsp;<span class="key">"source_id"</span>: <span class="val">"SRC_a1b2c3d4e5f6"</span>,<br>
                        &nbsp;&nbsp;<span class="key">"status"</span>: <span class="val">"READY"</span>,<br>
                        &nbsp;&nbsp;<span class="key">"topic_blueprint"</span>: {<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"topic_name"</span>: <span class="val">"Newton's Laws of Motion"</span>,<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"key_concepts"</span>: [<span class="val">"Force"</span>, <span class="val">"Inertia"</span>, <span class="val">"Acceleration"</span>],<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"difficulty_level"</span>: <span class="val">"beginner"</span><br>
                        &nbsp;&nbsp;},<br>
                        &nbsp;&nbsp;<span class="key">"concepts_extracted"</span>: <span class="val">8</span>,<br>
                        &nbsp;&nbsp;<span class="key">"chunks_synced"</span>: <span class="val">12</span><br>
                        }
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 2 -->
        <div class="step step-2">
            <div class="step-indicator">2</div>
            <div class="step-content">
                <div class="step-label">Assessment Planning</div>
                <div class="step-name">Generate Quiz from Knowledge</div>
                <div class="step-desc">
                    Based on the uploaded material and extracted concepts,
                    the system generates a quiz. Each question is grounded in
                    the source material — no hallucinated facts. Concepts are
                    paired with their prerequisites to detect learning gaps.
                </div>
                <div class="step-endpoint">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/assessment/start</span>
                </div>
                <div class="io-box">
                    <div class="io-label">Input → Output</div>
                    <div class="io-content">
                        <span class="comment">// Pass the source_id from Step 1</span><br>
                        {<br>
                        &nbsp;&nbsp;<span class="key">"student_id"</span>: <span class="val">"STU_001"</span>,<br>
                        &nbsp;&nbsp;<span class="key">"source_id"</span>: <span class="val">"SRC_a1b2c3d4e5f6"</span><br>
                        }<br><br>
                        <span class="comment">// Returns quiz questions (no answers exposed)</span><br>
                        {<br>
                        &nbsp;&nbsp;<span class="key">"session_id"</span>: <span class="val">"SESS_x9y8z7..."</span>,<br>
                        &nbsp;&nbsp;<span class="key">"question_count"</span>: <span class="val">10</span>,<br>
                        &nbsp;&nbsp;<span class="key">"questions"</span>: [{<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"question_id"</span>: <span class="val">"Q_abc123"</span>,<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"stem"</span>: <span class="val">"What does Newton's First Law state?"</span>,<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"options"</span>: [<span class="val">4 choices</span>]<br>
                        &nbsp;&nbsp;}]<br>
                        }
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 3 -->
        <div class="step step-3">
            <div class="step-indicator">3</div>
            <div class="step-content">
                <div class="step-label">Submission</div>
                <div class="step-name">Student Answers the Quiz</div>
                <div class="step-desc">
                    The student submits their answers. The system validates
                    the session hasn't expired, grades against the backend
                    answer key, and calculates the score.
                </div>
                <div class="step-endpoint">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/assessment/submit</span>
                </div>
                <div class="io-box">
                    <div class="io-label">Input → Output</div>
                    <div class="io-content">
                        {<br>
                        &nbsp;&nbsp;<span class="key">"session_id"</span>: <span class="val">"SESS_x9y8z7..."</span>,<br>
                        &nbsp;&nbsp;<span class="key">"answers"</span>: [{<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"question_id"</span>: <span class="val">"Q_abc123"</span>,<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"selected_index"</span>: <span class="val">0</span><br>
                        &nbsp;&nbsp;}]<br>
                        }<br><br>
                        <span class="comment">// Returns graded results</span><br>
                        {<br>
                        &nbsp;&nbsp;<span class="key">"score"</span>: <span class="val">7</span>,<br>
                        &nbsp;&nbsp;<span class="key">"total"</span>: <span class="val">10</span>,<br>
                        &nbsp;&nbsp;<span class="key">"percentage"</span>: <span class="val">70.0</span>,<br>
                        &nbsp;&nbsp;<span class="key">"prerequisite_gaps"</span>: [<span class="val">"Failed Force + Inertia"</span>]<br>
                        }
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 4 -->
        <div class="step step-4">
            <div class="step-indicator">4</div>
            <div class="step-content">
                <div class="step-label">Profiling</div>
                <div class="step-name">Track Mastery & Learning Profile</div>
                <div class="step-desc">
                    The system updates the student's learning profile.
                    Tracks which concepts are mastered, which need work,
                    and detects prerequisite gaps. Prevents "lucky guess"
                    mastery with multi-session verification.
                </div>
                <div class="step-endpoint">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/assessment/profile/{student_id}/{source_id}</span>
                </div>
                <div class="io-box">
                    <div class="io-label">Output</div>
                    <div class="io-content">
                        {<br>
                        &nbsp;&nbsp;<span class="key">"overall_score"</span>: <span class="val">72.5</span>,<br>
                        &nbsp;&nbsp;<span class="key">"total_sessions"</span>: <span class="val">3</span>,<br>
                        &nbsp;&nbsp;<span class="key">"strong_concepts"</span>: [<span class="val">"Force"</span>, <span class="val">"Inertia"</span>],<br>
                        &nbsp;&nbsp;<span class="key">"weak_concepts"</span>: [<span class="val">"Acceleration"</span>, <span class="val">"Momentum"</span>],<br>
                        &nbsp;&nbsp;<span class="key">"prerequisite_gaps"</span>: [<span class="val">"Friction requires Force"</span>],<br>
                        &nbsp;&nbsp;<span class="key">"concept_masteries"</span>: {<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"CONCEPT_FORCE"</span>: { <span class="key">"status"</span>: <span class="val">"MASTERED"</span> },<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<span class="key">"CONCEPT_ACCELERATION"</span>: { <span class="key">"status"</span>: <span class="val">"LEARNING"</span> }<br>
                        &nbsp;&nbsp;}<br>
                        }
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 5 -->
        <div class="step step-5">
            <div class="step-indicator">5</div>
            <div class="step-content">
                <div class="step-label">Handover</div>
                <div class="step-name">Pass to Video Generation (Step 3)</div>
                <div class="step-desc">
                    The learning profile is ready. Step 3 (not yet implemented)
                    uses this profile to generate targeted, adaptive video scenes
                    that address the student's specific weak concepts and gaps.
                </div>
            </div>
        </div>

        <div class="divider"></div>

        <div class="links-section">
            <h2>Quick Links</h2>
            <div class="links-grid">
                <a href="/docs" class="link-card">
                    <div class="link-title">Swagger UI</div>
                    <div class="link-desc">Interactive API explorer — test every endpoint</div>
                    <span class="link-url">/docs</span>
                </a>
                <a href="/redoc" class="link-card">
                    <div class="link-title">ReDoc</div>
                    <div class="link-desc">Clean API reference documentation</div>
                    <span class="link-url">/redoc</span>
                </a>
                <a href="/health" class="link-card">
                    <div class="link-title">Health Check</div>
                    <div class="link-desc">Verify server status</div>
                    <span class="link-url">/health</span>
                </a>
                <a href="https://github.com/anveshreddy294/AI-VIDEO-GENERATOR" class="link-card" target="_blank">
                    <div class="link-title">GitHub</div>
                    <div class="link-desc">Source code and documentation</div>
                    <span class="link-url">github.com/.../AI-VIDEO-GENERATOR</span>
                </a>
            </div>
        </div>
    </div>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def dashboard():
    """VisualAI dashboard — shows the complete workflow."""
    return HTMLResponse(content=DASHBOARD_HTML)
