"""VisualAI Dashboard — Interactive Assessment Console & Pipeline Documentation."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Student Knowledge & Assessment Platform</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #0f1117;
            color: #e1e4e8;
            min-height: 100vh;
        }

        .header {
            background: #161b22;
            border-bottom: 1px solid #21262d;
            padding: 16px 36px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header h1 {
            font-size: 20px;
            font-weight: 700;
            color: #f0f6fc;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 10px;
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
            margin-left: 20px;
            font-size: 14px;
            font-weight: 500;
        }

        .nav-links a:hover { color: #79c0ff; }

        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 36px 24px;
        }

        /* Interactive Console */
        .console-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 48px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }

        .console-title {
            font-size: 20px;
            font-weight: 700;
            color: #f0f6fc;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .console-desc {
            font-size: 14px;
            color: #8b949e;
            margin-bottom: 20px;
        }

        .tabs {
            display: flex;
            gap: 8px;
            border-bottom: 1px solid #30363d;
            margin-bottom: 20px;
        }

        .tab-btn {
            background: none;
            border: none;
            color: #8b949e;
            font-size: 14px;
            font-weight: 600;
            padding: 8px 16px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab-btn.active {
            color: #58a6ff;
            border-bottom-color: #58a6ff;
        }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 16px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .form-group.full {
            grid-column: 1 / -1;
        }

        .form-label {
            font-size: 12px;
            font-weight: 600;
            color: #c9d1d9;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-input, .form-select {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 14px;
            color: #f0f6fc;
            outline: none;
            transition: border-color 0.2s;
        }

        .form-input:focus, .form-select:focus {
            border-color: #58a6ff;
        }

        .action-btn {
            background: #238636;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 12px 24px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: background 0.2s, transform 0.1s;
        }

        .action-btn:hover {
            background: #2ea043;
        }

        .action-btn:active {
            transform: scale(0.99);
        }

        .action-btn:disabled {
            background: #23863688;
            cursor: not-allowed;
        }

        /* Status & Alert Banner */
        .status-box {
            display: none;
            padding: 14px 18px;
            border-radius: 8px;
            margin-top: 18px;
            font-size: 14px;
            line-height: 1.5;
        }

        .status-loading {
            background: #1f6feb22;
            border: 1px solid #1f6feb66;
            color: #79c0ff;
            display: block;
        }

        .status-error {
            background: #da363322;
            border: 1px solid #da363366;
            color: #f85149;
            display: block;
        }

        .status-success {
            background: #23863622;
            border: 1px solid #23863666;
            color: #56d364;
            display: block;
        }

        .status-warning {
            background: #d2992222;
            border: 1px solid #d2992266;
            color: #e3b341;
            display: block;
        }

        /* Quiz Area */
        .quiz-area {
            display: none;
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid #30363d;
        }

        .quiz-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 18px;
        }

        .badge {
            font-size: 11px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 12px;
            background: #21262d;
            color: #8b949e;
        }

        .badge-blue { background: #1f6feb33; color: #58a6ff; }
        .badge-green { background: #23863633; color: #3fb950; }
        .badge-amber { background: #d2992233; color: #d29922; }

        .question-card {
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 18px;
            margin-bottom: 16px;
        }

        .question-meta {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }

        .question-stem {
            font-size: 15px;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 14px;
            line-height: 1.5;
        }

        .options-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .option-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 14px;
            border-radius: 6px;
            border: 1px solid #30363d;
            cursor: pointer;
            transition: all 0.15s;
        }

        .option-item:hover {
            border-color: #58a6ff;
            background: #161b22;
        }

        .option-item input[type="radio"] {
            accent-color: #1f6feb;
            width: 16px;
            height: 16px;
        }

        .option-text {
            font-size: 14px;
            color: #c9d1d9;
        }

        /* Results Display */
        .results-box {
            display: none;
            margin-top: 24px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }

        .score-banner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid #21262d;
        }

        .score-number {
            font-size: 32px;
            font-weight: 800;
            color: #3fb950;
        }

        /* Workflow Documentation Section */
        .flow-title {
            font-size: 24px;
            font-weight: 700;
            color: #f0f6fc;
            margin-bottom: 6px;
        }

        .flow-subtitle {
            font-size: 14px;
            color: #8b949e;
            margin-bottom: 36px;
        }

        .step {
            display: flex;
            gap: 20px;
            padding-bottom: 28px;
            position: relative;
        }

        .step-indicator {
            flex-shrink: 0;
            width: 42px;
            height: 42px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            font-weight: 700;
        }

        .step-1 .step-indicator { background: #1f6feb; color: #fff; }
        .step-2 .step-indicator { background: #238636; color: #fff; }
        .step-3 .step-indicator { background: #9e6a03; color: #fff; }

        .step-content { flex: 1; }
        .step-label { font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 2px; }
        .step-1 .step-label { color: #58a6ff; }
        .step-2 .step-label { color: #3fb950; }
        .step-3 .step-label { color: #d29922; }

        .step-name { font-size: 17px; font-weight: 600; color: #f0f6fc; margin-bottom: 6px; }
        .step-desc { font-size: 13px; color: #8b949e; line-height: 1.6; margin-bottom: 10px; }

        .step-endpoint {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 6px;
            padding: 6px 12px;
            font-family: monospace;
            font-size: 12px;
        }

        .method { font-weight: 700; font-size: 10px; padding: 2px 5px; border-radius: 3px; }
        .method-post { background: #238636; color: #fff; }
        .method-get { background: #1f6feb; color: #fff; }

        .links-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-top: 24px;
        }

        .link-card {
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 14px;
            text-decoration: none;
            transition: border-color 0.2s;
        }

        .link-card:hover { border-color: #388bfd; }
        .link-title { font-size: 14px; font-weight: 600; color: #f0f6fc; }
        .link-desc { font-size: 12px; color: #8b949e; margin-top: 4px; }

        /* Observable Pipeline Timeline */
        .timeline-card {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
            margin-top: 20px;
            margin-bottom: 20px;
        }

        .timeline-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .timeline-pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #58a6ff;
            display: inline-block;
            box-shadow: 0 0 8px #58a6ff;
            animation: pulse-ring 1.5s infinite;
        }

        @keyframes pulse-ring {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.3); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        .progress-bar-bg {
            background: #21262d;
            height: 6px;
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 16px;
        }

        .progress-bar-fill {
            background: linear-gradient(90deg, #1f6feb, #238636);
            height: 100%;
            transition: width 0.3s ease;
        }

        .timeline-stages-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .stage-item {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            font-size: 13px;
            color: #8b949e;
            transition: all 0.2s ease;
        }

        .stage-item.status-running {
            color: #f0f6fc;
            font-weight: 600;
        }

        .stage-item.status-completed {
            color: #c9d1d9;
        }

        .stage-item.status-warning {
            color: #d29922;
        }

        .stage-item.status-failed {
            color: #f85149;
            font-weight: 600;
        }

        .stage-icon {
            flex-shrink: 0;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            margin-top: 1px;
        }

        .status-pending .stage-icon { background: #21262d; color: #484f58; }
        .status-running .stage-icon { background: #1f6feb; color: #fff; animation: spin 1s linear infinite; }
        .status-completed .stage-icon { background: #238636; color: #fff; }
        .status-warning .stage-icon { background: #9e6a03; color: #fff; }
        .status-failed .stage-icon { background: #da3633; color: #fff; }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .stage-details { flex: 1; }
        .stage-title { font-weight: 600; margin-bottom: 2px; }
        .stage-message { font-size: 12px; color: #8b949e; }
        .stage-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 4px;
        }
        .meta-chip {
            background: #21262d;
            color: #8b949e;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            <span>🎓 VisualAI</span>
            <span class="version">v0.2.0</span>
        </h1>
        <nav class="nav-links">
            <a href="/docs" target="_blank">Swagger API</a>
            <a href="/redoc" target="_blank">ReDoc</a>
            <a href="/health" target="_blank">Health Check</a>
        </nav>
    </div>

    <div class="container">
        <!-- ⚡ INTERACTIVE AUTOMATED CONSOLE -->
        <div class="console-card">
            <div class="console-title">🚀 Automated Learning & Assessment Console</div>
            <div class="console-desc">
                Upload your lecture PDF, notes, or select an existing document. Step 1 will extract the Knowledge Graph and immediately hand off to Step 2 to generate your personalized quiz questions!
            </div>

            <div class="tabs">
                <button class="tab-btn active" id="tabUpload" onclick="switchTab('upload')">📤 Upload & Auto-Assess</button>
                <button class="tab-btn" id="tabExisting" onclick="switchTab('existing')">📚 Assess Existing Material</button>
            </div>

            <!-- Tab 1: Upload & Auto-Assess -->
            <div id="paneUpload">
                <div class="form-grid">
                    <div class="form-group full">
                        <label class="form-label">Study Material File (PDF, TXT, Image, Video)</label>
                        <input type="file" id="fileInput" class="form-input" accept=".pdf,.txt,.jpeg,.jpg,.png,.mp4,.mov,.mkv" />
                    </div>
                    <div class="form-group">
                        <label class="form-label">Student ID</label>
                        <input type="text" id="studentIdUpload" class="form-input" value="student_1" placeholder="e.g. student_1" />
                    </div>
                    <div class="form-group">
                        <label class="form-label">Max Questions</label>
                        <input type="number" id="maxQuestionsUpload" class="form-input" value="5" min="1" max="15" />
                    </div>
                </div>
                <button class="action-btn" id="btnUpload" onclick="runUploadAndAssess()">
                    <span>⚡ Upload & Generate Quiz</span>
                </button>
            </div>

            <!-- Tab 2: Assess Existing Material -->
            <div id="paneExisting" style="display:none;">
                <div class="form-grid">
                    <div class="form-group full">
                        <label class="form-label">Select Ingested Material</label>
                        <select id="sourceSelect" class="form-select">
                            <option value="">Loading sources...</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Student ID</label>
                        <input type="text" id="studentIdExisting" class="form-input" value="student_1" placeholder="e.g. student_1" />
                    </div>
                    <div class="form-group">
                        <label class="form-label">Max Questions</label>
                        <input type="number" id="maxQuestionsExisting" class="form-input" value="5" min="1" max="15" />
                    </div>
                </div>
                <button class="action-btn" id="btnAssessExisting" onclick="runExistingAssess()">
                    <span>⚡ Generate Quiz Questions</span>
                </button>
            </div>

            <!-- Observable Activity Telemetry Timeline Card -->
            <div id="timelineCard" class="timeline-card" style="display:none;">
                <div class="timeline-header">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span class="timeline-pulse-dot" id="timelinePulse"></span>
                        <span style="font-weight:700;font-size:14px;color:#f0f6fc;">Pipeline Execution Telemetry</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;">
                        <span id="timelineTimer" style="font-size:12px;color:#8b949e;font-variant-numeric:tabular-nums;">0.0s</span>
                        <span id="timelinePercent" style="font-size:12px;font-weight:600;color:#58a6ff;">0%</span>
                    </div>
                </div>
                <div class="progress-bar-bg">
                    <div id="timelineProgressBar" class="progress-bar-fill" style="width: 0%;"></div>
                </div>
                <div id="timelineStagesList" class="timeline-stages-list"></div>
            </div>

            <!-- Status Banner -->
            <div id="statusBox" class="status-box"></div>

            <!-- Quiz Runner Card -->
            <div id="quizArea" class="quiz-area">
                <div class="quiz-header">
                    <div>
                        <span class="badge badge-blue" id="lblSession">Session</span>
                        <span class="badge badge-green" id="lblSource">Source</span>
                        <span class="badge badge-amber" id="lblStudent">Student</span>
                    </div>
                    <span style="font-size:13px;color:#8b949e;" id="lblCount">0 Questions</span>
                </div>

                <div id="questionsContainer"></div>

                <button class="action-btn" style="background:#1f6feb;margin-top:12px;" id="btnSubmitQuiz" onclick="submitQuiz()">
                    <span>📝 Submit Answers & Grade Quiz</span>
                </button>
            </div>

            <!-- Results & Step 3 Directive Card -->
            <div id="resultsBox" class="results-box">
                <div class="score-banner">
                    <div>
                        <div style="font-size:13px;color:#8b949e;text-transform:uppercase;font-weight:600;">Assessment Score</div>
                        <div class="score-number" id="lblScore">0.0%</div>
                        <div id="lblFraction" style="font-size:13px;color:#8b949e;margin-top:4px;">0 / 0 correct</div>
                    </div>
                    <div style="display:flex;align-items:center;gap:20px;">
                        <div style="text-align:right;">
                            <div style="font-size:12px;color:#8b949e;text-transform:uppercase;font-weight:600;">Overall Profile Score</div>
                            <div id="lblProfileScore" style="font-size:24px;font-weight:700;color:#58a6ff;">0.0%</div>
                        </div>
                        <div id="lblGradeStatus"></div>
                    </div>
                </div>

                <div style="margin-bottom:14px;">
                    <div style="font-size:12px;font-weight:600;color:#8b949e;text-transform:uppercase;margin-bottom:6px;">Mastery Breakdown</div>
                    <div id="lblMasteries" style="display:flex;flex-wrap:wrap;gap:6px;"></div>
                </div>

                <div id="boxPrereqs" style="margin-bottom:14px;display:none;">
                    <div style="font-size:12px;font-weight:600;color:#f85149;text-transform:uppercase;margin-bottom:6px;">Prerequisite Gaps Detected</div>
                    <div id="lblPrereqs" style="font-size:13px;color:#f85149;"></div>
                </div>

                <div style="background:#161b22;border:1px solid #21262d;border-radius:6px;padding:14px;margin-top:12px;">
                    <div style="font-size:12px;font-weight:600;color:#58a6ff;text-transform:uppercase;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
                        <span>Step 3 Handoff — Video Target Matrix</span>
                        <span id="lblVideoCountBadge" class="badge badge-blue"></span>
                    </div>
                    <div id="lblVideoDirective" style="font-size:13px;color:#c9d1d9;line-height:1.5;"></div>
                    <div id="lblVideoQueue" style="margin-top:10px;display:flex;flex-direction:column;gap:8px;"></div>
                </div>

                <!-- Video Player Modal -->
                <div id="videoModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:9999;backdrop-filter:blur(4px);justify-content:center;align-items:center;">
                    <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;width:90%;max-width:860px;padding:24px;box-shadow:0 16px 40px rgba(0,0,0,0.6);position:relative;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                            <div>
                                <h3 id="modalVideoTitle" style="color:#f0f6fc;font-size:18px;font-weight:700;">Remediation Video</h3>
                                <p id="modalVideoSub" style="color:#8b949e;font-size:13px;">Targeted Micro-Lesson</p>
                            </div>
                            <button onclick="closeVideoModal()" style="background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;padding:6px 12px;cursor:pointer;font-weight:600;">✕ Close</button>
                        </div>
                        <div id="modalVideoLoader" style="display:none;padding:40px;text-align:center;">
                            <div style="display:inline-block;width:36px;height:36px;border:3px solid #30363d;border-top-color:#58a6ff;border-radius:50%;animation:spin 1s linear infinite;margin-bottom:14px;"></div>
                            <div id="modalProgressText" style="color:#f0f6fc;font-weight:600;font-size:15px;">Synthesizing Lesson Video...</div>
                            <div id="modalProgressSub" style="color:#8b949e;font-size:12px;margin-top:6px;">Generating timed script, voiceover, and visual cards</div>
                        </div>
                        <div id="modalVideoWrapper" style="display:none;text-align:center;">
                            <video id="html5VideoPlayer" controls style="width:100%;max-height:480px;border-radius:8px;background:#000;outline:none;" preload="auto">
                                <source id="videoSource" src="" type="video/mp4">
                                <track id="videoTrack" label="English" kind="subtitles" srclang="en" src="" default>
                                Your browser does not support the video tag.
                            </video>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- PIPELINE FLOW DOCUMENTATION -->
        <h2 class="flow-title">Pipeline Architecture</h2>
        <p class="flow-subtitle">Deterministic knowledge extraction, adaptive quiz evaluation, and AI video target handoff</p>

        <div class="step step-1">
            <div class="step-indicator">1</div>
            <div class="step-content">
                <div class="step-label">Step 1 — Ingestion</div>
                <div class="step-name">Multimodal Knowledge Extraction</div>
                <div class="step-desc">Upload study material. System extracts content, constructs a Knowledge Graph, and syncs chunks to Qdrant.</div>
                <div class="step-endpoint">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/upload?auto_start_assessment=true</span>
                </div>
            </div>
        </div>

        <div class="step step-2">
            <div class="step-indicator">2</div>
            <div class="step-content">
                <div class="step-label">Step 2 — Assessment</div>
                <div class="step-name">Adaptive Testing & Mastery Profiling</div>
                <div class="step-desc">Generates grounded questions from source chunks. Grades submissions, detects prerequisite gaps, and builds the Video Target Matrix.</div>
                <div class="step-endpoint">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/assessment/start &amp; /assessment/submit</span>
                </div>
            </div>
        </div>

        <div class="step step-3">
            <div class="step-indicator">3</div>
            <div class="step-content">
                <div class="step-label">Step 3 — Video Generation</div>
                <div class="step-name">Targeted Visual Remediation</div>
                <div class="step-desc">Consumes VideoTargetMatrix to produce 30s/45s/60s remedial video lessons for concepts needing reinforcement.</div>
                <div class="step-endpoint">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/assessment/video-target/{student_id}/{source_id}</span>
                </div>
            </div>
        </div>

        <div class="links-grid">
            <a href="/docs" class="link-card">
                <div class="link-title">Swagger UI</div>
                <div class="link-desc">Interactive endpoint testing</div>
            </a>
            <a href="/sources" class="link-card" target="_blank">
                <div class="link-title">Available Sources</div>
                <div class="link-desc">Inspect all registered materials</div>
            </a>
            <a href="/health" class="link-card">
                <div class="link-title">System Health</div>
                <div class="link-desc">Operational status check</div>
            </a>
        </div>
    </div>

    <script>
        let currentSession = null;
        let activeQuestions = [];

        function switchTab(tab) {
            document.getElementById('tabUpload').classList.toggle('active', tab === 'upload');
            document.getElementById('tabExisting').classList.toggle('active', tab === 'existing');
            document.getElementById('paneUpload').style.display = tab === 'upload' ? 'block' : 'none';
            document.getElementById('paneExisting').style.display = tab === 'existing' ? 'block' : 'none';
        }

        async function loadSources() {
            try {
                const res = await fetch('/sources');
                const data = await res.json();
                const sel = document.getElementById('sourceSelect');
                sel.innerHTML = '';
                const readySources = (data.sources || []).filter(s => s.status === 'READY');
                if (readySources.length === 0) {
                    sel.innerHTML = '<option value="">No ready sources found. Upload a file above!</option>';
                    return;
                }
                readySources.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.source_id;
                    opt.textContent = `${s.filename} (${s.source_id}) — ${s.concepts_count} concepts`;
                    sel.appendChild(opt);
                });
            } catch (err) {
                console.error('Failed to load sources:', err);
            }
        }

        let activeEventSource = null;
        let timelineTimerInterval = null;
        let timelineStartTime = 0;

        const STAGE_LABELS = {
            'validating_source': 'Validating Source & Hash',
            'extracting_content': 'Extracting Multimodal Content',
            'normalizing_units': 'Building ContentUnits',
            'analyzing_structure': 'Analyzing Document Structure',
            'extracting_concepts': 'Extracting Key Concepts',
            'building_knowledge_graph': 'Building Knowledge Graph',
            'creating_chunks': 'Creating Semantic Chunks',
            'syncing_qdrant': 'Syncing Vector Database',
            'quality_validation': 'Quality Validation Gateway',
            'planning_assessment': 'Planning Adaptive Assessment',
            'generating_questions': 'Generating Grounded Questions',
            'validating_questions': 'Validating Questions & Answer Key',
            'assessment_ready': 'Assessment Ready'
        };

        function resetTimeline() {
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            if (timelineTimerInterval) {
                clearInterval(timelineTimerInterval);
                timelineTimerInterval = null;
            }
            const card = document.getElementById('timelineCard');
            card.style.display = 'block';
            document.getElementById('timelineProgressBar').style.width = '0%';
            document.getElementById('timelinePercent').textContent = '0%';
            document.getElementById('timelineTimer').textContent = '0.0s';
            document.getElementById('timelineStagesList').innerHTML = '';
            document.getElementById('timelinePulse').className = 'timeline-pulse-dot';
            document.getElementById('timelinePulse').style.background = '#58a6ff';

            timelineStartTime = Date.now();
            timelineTimerInterval = setInterval(() => {
                const elapsed = ((Date.now() - timelineStartTime) / 1000).toFixed(1);
                document.getElementById('timelineTimer').textContent = `${elapsed}s`;
            }, 100);
        }

        function updateTimelineEvent(ev) {
            document.getElementById('timelineProgressBar').style.width = `${ev.progress_percent}%`;
            document.getElementById('timelinePercent').textContent = `${ev.progress_percent}%`;

            const list = document.getElementById('timelineStagesList');
            let stageElem = document.getElementById(`stage-${ev.stage}`);

            if (!stageElem) {
                stageElem = document.createElement('div');
                stageElem.id = `stage-${ev.stage}`;
                list.appendChild(stageElem);
            }

            stageElem.className = `stage-item status-${ev.status}`;

            let iconHtml = '○';
            if (ev.status === 'running') iconHtml = '⏳';
            else if (ev.status === 'completed') iconHtml = '✓';
            else if (ev.status === 'warning') iconHtml = '⚠️';
            else if (ev.status === 'failed') iconHtml = '✕';

            let metaChips = '';
            if (ev.metadata) {
                for (const [k, v] of Object.entries(ev.metadata)) {
                    metaChips += `<span class="meta-chip">${k}: ${v}</span>`;
                }
            }

            const label = STAGE_LABELS[ev.stage] || ev.stage;
            stageElem.innerHTML = `
                <div class="stage-icon">${iconHtml}</div>
                <div class="stage-details">
                    <div class="stage-title">${label}</div>
                    <div class="stage-message">${ev.message}</div>
                    ${metaChips ? `<div class="stage-meta">${metaChips}</div>` : ''}
                </div>
            `;

            if (ev.status === 'failed') {
                document.getElementById('timelinePulse').style.background = '#da3633';
            } else if (ev.status === 'completed' && ev.stage === 'assessment_ready') {
                document.getElementById('timelinePulse').style.background = '#238636';
            } else if (ev.status === 'warning') {
                document.getElementById('timelinePulse').style.background = '#d29922';
            }
        }

        function trackJobSSE(jobId, onComplete, onError) {
            const url = `/pipeline/jobs/${jobId}/events`;
            activeEventSource = new EventSource(url);

            activeEventSource.onmessage = (event) => {
                if (!event.data || event.data.trim() === '' || event.data.startsWith(':')) return;
                try {
                    const ev = JSON.parse(event.data);
                    updateTimelineEvent(ev);

                    if (ev.status === 'completed' && ev.stage === 'assessment_ready') {
                        if (activeEventSource) activeEventSource.close();
                        if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                        onComplete(jobId);
                    } else if (ev.status === 'failed') {
                        if (activeEventSource) activeEventSource.close();
                        if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                        onError(ev.message);
                    }
                } catch (err) {
                    console.error('Error parsing SSE event:', err);
                }
            };

            activeEventSource.onerror = async () => {
                // Fallback polling if SSE drops
                if (activeEventSource) activeEventSource.close();
                try {
                    const res = await fetch(`/pipeline/jobs/${jobId}`);
                    const job = await res.json();
                    if (job.events) {
                        job.events.forEach(updateTimelineEvent);
                    }
                    if (job.status === 'completed') {
                        if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                        onComplete(jobId);
                    } else if (job.status === 'failed') {
                        if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                        onError(job.error || 'Pipeline execution failed.');
                    }
                } catch (e) {
                    console.error('Polling fallback failed:', e);
                }
            };
        }

        function setStatus(msg, type) {
            const box = document.getElementById('statusBox');
            if (!msg) {
                box.style.display = 'none';
                return;
            }
            box.className = `status-box status-${type}`;
            box.innerHTML = msg;
            box.style.display = 'block';
        }

        async function runUploadAndAssess() {
            const fileInput = document.getElementById('fileInput');
            if (!fileInput.files || fileInput.files.length === 0) {
                setStatus('Please choose a file to upload.', 'error');
                return;
            }
            const file = fileInput.files[0];
            const studentId = document.getElementById('studentIdUpload').value.trim() || 'student_1';
            const maxQ = document.getElementById('maxQuestionsUpload').value || '5';

            const btn = document.getElementById('btnUpload');
            btn.disabled = true;
            resetTimeline();
            setStatus('', 'loading');

            const formData = new FormData();
            formData.append('file', file);

            try {
                const url = `/pipeline/upload-and-assess?student_id=${encodeURIComponent(studentId)}&max_questions=${maxQ}`;
                const res = await fetch(url, { method: 'POST', body: formData });
                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.detail || JSON.stringify(data));
                }

                trackJobSSE(data.job_id, async (jid) => {
                    btn.disabled = false;
                    const jobRes = await fetch(`/pipeline/jobs/${jid}`);
                    const jobData = await jobRes.json();
                    if (jobData.result && jobData.result.assessment) {
                        loadSources();
                        renderQuiz(jobData.result.assessment);
                    }
                }, (errMsg) => {
                    btn.disabled = false;
                    setStatus(`❌ Pipeline error: ${errMsg}`, 'error');
                });
            } catch (err) {
                btn.disabled = false;
                setStatus(`❌ Upload error: ${err.message}`, 'error');
            }
        }

        async function runExistingAssess() {
            const sourceId = document.getElementById('sourceSelect').value;
            if (!sourceId) {
                setStatus('Please select a valid study material source.', 'error');
                return;
            }
            const studentId = document.getElementById('studentIdExisting').value.trim() || 'student_1';
            const maxQ = parseInt(document.getElementById('maxQuestionsExisting').value || '5', 10);

            const btn = document.getElementById('btnAssessExisting');
            btn.disabled = true;
            resetTimeline();
            setStatus('', 'loading');

            try {
                const res = await fetch('/pipeline/assess-existing', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: studentId,
                        source_id: sourceId,
                        max_questions: maxQ
                    })
                });
                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.detail || JSON.stringify(data));
                }

                trackJobSSE(data.job_id, async (jid) => {
                    btn.disabled = false;
                    const jobRes = await fetch(`/pipeline/jobs/${jid}`);
                    const jobData = await jobRes.json();
                    if (jobData.result && jobData.result.assessment) {
                        renderQuiz(jobData.result.assessment);
                    }
                }, (errMsg) => {
                    btn.disabled = false;
                    setStatus(`❌ Assessment error: ${errMsg}`, 'error');
                });
            } catch (err) {
                btn.disabled = false;
                setStatus(`❌ Assessment error: ${err.message}`, 'error');
            }
        }

        function renderQuiz(session) {
            currentSession = session;
            activeQuestions = session.questions || [];

            const requested = session.requested_questions || activeQuestions.length;
            const generated = session.generated_questions !== undefined ? session.generated_questions : activeQuestions.length;
            const shortfall = session.shortfall || 0;

            document.getElementById('lblSession').textContent = `Session: ${session.session_id}`;
            document.getElementById('lblSource').textContent = `Source: ${session.source_id}`;
            document.getElementById('lblStudent').textContent = `Student: ${session.student_id}`;

            if (shortfall > 0) {
                document.getElementById('lblCount').textContent = `${generated} of ${requested} grounded questions generated`;
            } else {
                document.getElementById('lblCount').textContent = `${activeQuestions.length} Questions`;
            }

            const container = document.getElementById('questionsContainer');
            container.innerHTML = '';

            if (shortfall > 0) {
                const noticeCard = document.createElement('div');
                noticeCard.style.cssText = 'background: rgba(210, 153, 34, 0.15); border: 1px solid #d29922; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 13px; color: #f0f6fc;';
                noticeCard.innerHTML = `
                    <div style="font-weight:600; color:#e3b341; margin-bottom:4px;">⚠️ ${generated} of ${requested} grounded questions generated</div>
                    <div style="color:#c9d1d9; font-size:12px;">The authoritative study source contained insufficient distinct grounded evidence to generate all ${requested} requested questions without duplicating concepts or compromising strict evidentiary grounding.</div>
                `;
                container.appendChild(noticeCard);
            }

            activeQuestions.forEach((q, qIdx) => {
                const qCard = document.createElement('div');
                qCard.className = 'question-card';

                const meta = document.createElement('div');
                meta.className = 'question-meta';
                meta.innerHTML = `
                    <span class="badge badge-blue">Concept: ${q.concept_name}</span>
                    <span class="badge badge-amber">${q.difficulty}</span>
                    ${q.page_start ? `<span class="badge">Page ${q.page_start}${q.page_end && q.page_end !== q.page_start ? `-${q.page_end}` : ''}</span>` : ''}
                `;
                qCard.appendChild(meta);

                const stem = document.createElement('div');
                stem.className = 'question-stem';
                stem.textContent = `${qIdx + 1}. ${q.stem}`;
                qCard.appendChild(stem);

                const optList = document.createElement('div');
                optList.className = 'options-list';

                q.options.forEach(opt => {
                    const label = document.createElement('label');
                    label.className = 'option-item';
                    label.innerHTML = `
                        <input type="radio" name="q_${q.question_id}" value="${opt.index}" />
                        <span class="option-text">${opt.text}</span>
                    `;
                    optList.appendChild(label);
                });

                qCard.appendChild(optList);
                container.appendChild(qCard);
            });

            document.getElementById('quizArea').style.display = 'block';
            document.getElementById('resultsBox').style.display = 'none';
        }

        async function submitQuiz() {
            if (!currentSession) return;

            const answers = [];
            let unassigned = 0;

            activeQuestions.forEach(q => {
                const selected = document.querySelector(`input[name="q_${q.question_id}"]:checked`);
                if (selected) {
                    answers.push({
                        question_id: q.question_id,
                        selected_index: parseInt(selected.value, 10)
                    });
                } else {
                    unassigned++;
                }
            });

            if (unassigned > 0) {
                if (!confirm(`You have ${unassigned} unanswered question(s). Submit anyway?`)) {
                    return;
                }
            }

            const btn = document.getElementById('btnSubmitQuiz');
            btn.disabled = true;
            setStatus('⏳ Grading assessment & calculating mastery profile...', 'loading');

            try {
                const res = await fetch('/assessment/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: currentSession.session_id,
                        answers: answers
                    })
                });
                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.detail || JSON.stringify(data));
                }

                setStatus('✅ Assessment graded! See your profile and Step 3 targets below.', 'success');
                displayResults(data);
            } catch (err) {
                setStatus(`❌ Grading error: ${err.message}`, 'error');
            } finally {
                btn.disabled = false;
            }
        }

        function displayResults(data) {
            const resultsBox = document.getElementById('resultsBox');
            resultsBox.style.display = 'block';

            // Contract Validation: Ensure required backend fields exist
            if (typeof data.percentage !== 'number' || typeof data.score !== 'number' || typeof data.total !== 'number') {
                setStatus('❌ Contract Error: Missing authoritative assessment score fields (percentage, score, total) in backend response.', 'error');
                console.error('Invalid submit response schema:', data);
                return;
            }

            const profileSummary = data.profile_summary;
            if (!profileSummary || typeof profileSummary.overall_score !== 'number') {
                setStatus('❌ Contract Error: Missing profile_summary.overall_score in backend response.', 'error');
                console.error('Invalid profile_summary schema:', data);
                return;
            }

            // 1. Assessment Score (THIS submission) - Authoritative backend percentage
            const assessmentPercentage = data.percentage;
            const scoreEl = document.getElementById('lblScore');
            scoreEl.textContent = `${assessmentPercentage.toFixed(1)}%`;
            scoreEl.style.color = assessmentPercentage >= 70 ? '#3fb950' : (assessmentPercentage >= 50 ? '#d29922' : '#f85149');

            const fractionEl = document.getElementById('lblFraction');
            if (fractionEl) {
                fractionEl.textContent = `${data.score} / ${data.total} correct`;
            }

            // 2. Overall Profile Score (Historical aggregate)
            const profileScoreEl = document.getElementById('lblProfileScore');
            if (profileScoreEl) {
                profileScoreEl.textContent = `${profileSummary.overall_score.toFixed(1)}%`;
            }

            // 3. Status Badge
            const statusEl = document.getElementById('lblGradeStatus');
            statusEl.innerHTML = assessmentPercentage >= 70
                ? '<span class="badge badge-green" style="font-size:14px;padding:6px 12px;">PASSED</span>'
                : '<span class="badge badge-amber" style="font-size:14px;padding:6px 12px;">REVISION RECOMMENDED</span>';

            // 4. Mastery Breakdown from profile_summary
            const masteriesEl = document.getElementById('lblMasteries');
            masteriesEl.innerHTML = '';
            const strong = profileSummary.strong_concepts || [];
            const weak = profileSummary.weak_concepts || [];

            if (strong.length === 0 && weak.length === 0) {
                masteriesEl.innerHTML = '<span style="font-size:13px;color:#8b949e;">No concept mastery data recorded.</span>';
            } else {
                strong.forEach(c => {
                    masteriesEl.innerHTML += `<span class="badge badge-green">✔ ${c} (Strong)</span>`;
                });
                weak.forEach(c => {
                    masteriesEl.innerHTML += `<span class="badge badge-amber">⚠ ${c} (Needs Review)</span>`;
                });
            }

            // 5. Prerequisite Gaps
            const prereqsBox = document.getElementById('boxPrereqs');
            const prereqsEl = document.getElementById('lblPrereqs');
            if (data.prerequisite_gaps && data.prerequisite_gaps.length > 0) {
                prereqsBox.style.display = 'block';
                prereqsEl.innerHTML = data.prerequisite_gaps.map(g => `• ${g}`).join('<br>');
            } else {
                prereqsBox.style.display = 'none';
            }

            // 6. Step 3 Video Target Matrix
            const matrix = data.video_target_matrix || {};
            document.getElementById('lblVideoDirective').textContent = matrix.summary || 'All tested concepts mastered! No video generation needed.';

            const queueEl = document.getElementById('lblVideoQueue');
            queueEl.innerHTML = '';
            const videos = matrix.videos || [];
            const badgeEl = document.getElementById('lblVideoCountBadge');
            if (badgeEl) {
                badgeEl.textContent = `${videos.length} Targets`;
            }

            videos.forEach(v => {
                const btnId = `btnGenVid_${v.concept_id.replace(/[^a-zA-Z0-9_]/g, '_')}`;
                queueEl.innerHTML += `
                    <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:12px;">
                        <div>
                            <div style="color:#f0f6fc;font-weight:600;font-size:14px;">${v.concept_name}</div>
                            <div style="font-size:12px;color:#8b949e;margin-top:2px;">${v.directive} • <span style="color:#58a6ff;">${v.difficulty}</span></div>
                        </div>
                        <button id="${btnId}" onclick="generateAndPlayVideo('${v.concept_id}', '${v.concept_name}', '${v.difficulty}', ${v.target_seconds})" class="action-btn" style="width:auto;padding:6px 14px;font-size:13px;display:flex;align-items:center;gap:6px;">
                            <span>🎬 Generate & Watch (${v.target_seconds}s)</span>
                        </button>
                    </div>
                `;
            });

            resultsBox.scrollIntoView({ behavior: 'smooth' });
        }

        async function generateAndPlayVideo(conceptId, conceptName, difficulty, targetSeconds) {
            if (!currentSession) {
                alert('No active session.');
                return;
            }

            const modal = document.getElementById('videoModal');
            const modalTitle = document.getElementById('modalVideoTitle');
            const modalSub = document.getElementById('modalVideoSub');
            const loader = document.getElementById('modalVideoLoader');
            const wrapper = document.getElementById('modalVideoWrapper');
            const progressText = document.getElementById('modalProgressText');
            const player = document.getElementById('html5VideoPlayer');

            modalTitle.textContent = `Remediation: ${conceptName}`;
            modalSub.textContent = `${difficulty.toUpperCase()} • ${targetSeconds}s Targeted Lesson`;

            modal.style.display = 'flex';
            loader.style.display = 'block';
            wrapper.style.display = 'none';
            progressText.textContent = 'Initializing Step 3 Video Engine...';

            try {
                // Trigger POST /video/generate
                const res = await fetch('/video/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: currentSession.student_id,
                        source_id: currentSession.source_id,
                        concept_id: conceptId
                    })
                });

                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.detail || JSON.stringify(data));
                }

                const jobId = data.job_id;
                progressText.textContent = `Generating timed script & synthesizing voiceover...`;

                // Poll status until completed
                let attempts = 0;
                const pollInterval = setInterval(async () => {
                    attempts++;
                    try {
                        const sRes = await fetch(`/video/status/${jobId}`);
                        const sData = await sRes.json();

                        if (sData.current_stage) {
                            progressText.textContent = `[${sData.progress_percent}%] ${sData.current_stage}`;
                        }

                        if (sData.status === 'completed') {
                            clearInterval(pollInterval);
                            loader.style.display = 'none';
                            wrapper.style.display = 'block';

                            const videoSrc = document.getElementById('videoSource');
                            const videoTrack = document.getElementById('videoTrack');

                            videoSrc.src = `/video/${sData.video_id}/stream`;
                            videoTrack.src = `/video/${sData.video_id}/subtitles`;

                            player.load();
                            player.play().catch(() => {});
                        } else if (sData.status === 'failed') {
                            clearInterval(pollInterval);
                            progressText.textContent = `❌ Rendering Failed: ${sData.error_message || 'Unknown error'}`;
                        }
                    } catch (e) {
                        console.error('Polling error:', e);
                    }

                    if (attempts > 120) {
                        clearInterval(pollInterval);
                        progressText.textContent = '⏱ Generation timed out. Please try again.';
                    }
                }, 1500);

            } catch (err) {
                progressText.textContent = `❌ Error: ${err.message}`;
            }
        }

        function closeVideoModal() {
            const modal = document.getElementById('videoModal');
            const player = document.getElementById('html5VideoPlayer');
            if (player) {
                player.pause();
            }
            modal.style.display = 'none';
        }

        // Initialize sources on page load
        window.addEventListener('DOMContentLoaded', loadSources);
    </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def dashboard():
    """VisualAI dashboard — Interactive test runner and complete pipeline documentation."""
    return HTMLResponse(content=DASHBOARD_HTML)
