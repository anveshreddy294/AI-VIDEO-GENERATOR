"""Instructor Analytics & Human Intervention Portal API.

Endpoints:
- GET  /instructor              → HTML Instructor Dashboard UI
- GET  /instructor/api/overview → Cohort overview, alerts, and concept analytics JSON
- POST /instructor/api/reset-mastery → Override student mastery or reset from kill switch
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from ..services.instructor.analytics import get_cohort_overview, reset_student_concept_status
from ..services.instructor.schemas import (
    CohortOverview,
    ResetMasteryRequest,
    ResetMasteryResponse,
)

router = APIRouter(prefix="/instructor", tags=["Instructor Analytics"])

INSTRUCTOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Instructor Analytics & Human Intervention Portal</title>
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
            display: flex;
            align-items: center;
            gap: 10px;
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
            max-width: 1200px;
            margin: 0 auto;
            padding: 30px 24px;
        }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }
        .kpi-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 20px;
        }
        .kpi-title { font-size: 13px; color: #8b949e; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; }
        .kpi-value { font-size: 28px; font-weight: 700; color: #f0f6fc; }
        .kpi-sub { font-size: 12px; color: #8b949e; margin-top: 4px; }
        .kpi-alert { border-color: #f8514966; background: #da363310; }
        .kpi-alert .kpi-value { color: #f85149; }
        .section-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 28px;
        }
        .section-title {
            font-size: 18px;
            font-weight: 700;
            color: #f0f6fc;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .section-desc { font-size: 13px; color: #8b949e; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { text-align: left; padding: 12px; border-bottom: 1px solid #30363d; color: #8b949e; font-weight: 600; }
        td { padding: 12px; border-bottom: 1px solid #21262d; color: #c9d1d9; }
        tr:hover { background: #21262d33; }
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-red { background: #da363326; color: #f85149; border: 1px solid #da363355; }
        .badge-green { background: #23863626; color: #3fb950; border: 1px solid #23863655; }
        .badge-blue { background: #1f6feb26; color: #58a6ff; border: 1px solid #1f6feb55; }
        .badge-amber { background: #d2992226; color: #d29922; border: 1px solid #d2992255; }
        .btn-action {
            background: #21262d;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-action:hover { background: #30363d; color: #fff; }
        .btn-success { background: #23863626; border-color: #238636; color: #3fb950; }
        .btn-success:hover { background: #238636; color: #fff; }
        .progress-bar-bg {
            background: #21262d;
            border-radius: 4px;
            height: 10px;
            width: 140px;
            display: inline-flex;
            overflow: hidden;
            vertical-align: middle;
            margin-right: 8px;
        }
        .progress-fill-green { background: #2ea043; height: 100%; }
        .progress-fill-amber { background: #d29922; height: 100%; }
        .progress-fill-red { background: #da3633; height: 100%; }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            <span>👩‍🏫 VisualAI Instructor Portal</span>
            <span class="badge badge-blue">Cohort Analytics</span>
        </h1>
        <nav class="nav-links">
            <a href="/">← Student Dashboard</a>
            <a href="/docs" target="_blank">Swagger API</a>
            <a href="/health" target="_blank">Health</a>
        </nav>
    </div>

    <div class="container">
        <!-- KPI METRICS -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Total Students Assessed</div>
                <div class="kpi-value" id="kpiStudents">0</div>
                <div class="kpi-sub">Tracked across active sessions</div>
            </div>
            <div class="kpi-card kpi-alert">
                <div class="kpi-title">Human Interventions Needed</div>
                <div class="kpi-value" id="kpiInterventions">0</div>
                <div class="kpi-sub">Triggered by Anti-Loop Kill Switch (>3 attempts)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Average Cohort Mastery</div>
                <div class="kpi-value" id="kpiMastery">0.0%</div>
                <div class="kpi-sub">Mean score across all curriculum concepts</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Prerequisite Bottlenecks</div>
                <div class="kpi-value" id="kpiBottlenecks">0</div>
                <div class="kpi-sub">Core concepts blocking downstream learning</div>
            </div>
        </div>

        <!-- ACTIVE HUMAN INTERVENTION ALERTS -->
        <div class="section-card">
            <div class="section-title">
                <span>🚨 Active Human Intervention Alerts</span>
                <button onclick="loadInstructorData()" class="btn-action">🔄 Refresh</button>
            </div>
            <div class="section-desc">
                Students below have failed targeted remediation checks more than 3 times. The anti-loop kill switch has locked their status to prevent infinite video looping. Review their gap analysis and take action below.
            </div>

            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Student</th>
                            <th>Material</th>
                            <th>Struggling Concept</th>
                            <th>Failed Attempts</th>
                            <th>Prerequisites</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="alertsTableBody">
                        <tr><td colspan="6" style="text-align:center;color:#8b949e;padding:24px;">Loading active alerts...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- COHORT CONCEPT HEALTH HEATMAP -->
        <div class="section-card">
            <div class="section-title">
                <span>📊 Concept Mastery & Bottleneck Heatmap</span>
            </div>
            <div class="section-desc">
                Cohort-wide distribution of student mastery across each curriculum topic. Concepts marked with <strong>⚠️ Bottleneck</strong> are prerequisites where failure cascades to dependent topics.
            </div>

            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Concept Name</th>
                            <th>Total Students</th>
                            <th>Mastery Distribution</th>
                            <th>Mastery Rate</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="conceptsTableBody">
                        <tr><td colspan="5" style="text-align:center;color:#8b949e;padding:24px;">Loading concept analytics...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        async function loadInstructorData() {
            try {
                const res = await fetch('/instructor/api/overview');
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Failed to load');

                // KPIs
                document.getElementById('kpiStudents').textContent = data.total_students;
                document.getElementById('kpiInterventions').textContent = data.total_interventions_needed;
                document.getElementById('kpiMastery').textContent = `${data.average_mastery_percent.toFixed(1)}%`;

                const bottlenecks = (data.concept_analytics || []).filter(c => c.is_prerequisite_bottleneck).length;
                document.getElementById('kpiBottlenecks').textContent = bottlenecks;

                // Alerts Table
                const aBody = document.getElementById('alertsTableBody');
                aBody.innerHTML = '';
                if (!data.alerts || data.alerts.length === 0) {
                    aBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#3fb950;padding:24px;">✔ No active human intervention alerts. All students are progressing smoothly!</td></tr>';
                } else {
                    data.alerts.forEach(a => {
                        const prereqs = (a.prerequisite_concept_ids && a.prerequisite_concept_ids.length > 0)
                            ? a.prerequisite_concept_ids.map(p => `<span class="badge badge-amber">${p}</span>`).join(' ')
                            : '<span style="color:#8b949e;">None</span>';

                        aBody.innerHTML += `
                            <tr>
                                <td><strong style="color:#f0f6fc;">${a.student_id}</strong></td>
                                <td><span style="font-size:12px;color:#8b949e;">${a.source_id}</span></td>
                                <td>
                                    <div style="font-weight:600;color:#f85149;">${a.concept_name}</div>
                                    <div style="font-size:11px;color:#8b949e;">ID: ${a.concept_id}</div>
                                </td>
                                <td>
                                    <span class="badge badge-red">${a.iteration_count} Fails</span>
                                    <div style="font-size:11px;color:#8b949e;margin-top:2px;">Last: ${a.last_score}%</div>
                                </td>
                                <td>${prereqs}</td>
                                <td>
                                    <div style="display:flex;gap:6px;">
                                        <button onclick="overrideMastery('${a.student_id}', '${a.source_id}', '${a.concept_id}', 'LEARNING')" class="btn-action" title="Reset iterations to 0 and allow student to retry remediation">🔄 Reset to Learning</button>
                                        <button onclick="overrideMastery('${a.student_id}', '${a.source_id}', '${a.concept_id}', 'MASTERED')" class="btn-action btn-success" title="Manually verify concept after 1-on-1 instructor session">✔ Verify Mastered</button>
                                    </div>
                                </td>
                            </tr>
                        `;
                    });
                }

                // Concepts Table
                const cBody = document.getElementById('conceptsTableBody');
                cBody.innerHTML = '';
                if (!data.concept_analytics || data.concept_analytics.length === 0) {
                    cBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#8b949e;padding:24px;">No concept assessment data available yet.</td></tr>';
                } else {
                    data.concept_analytics.forEach(c => {
                        const mPct = (c.mastered_count / c.total_students) * 100;
                        const lPct = (c.learning_count / c.total_students) * 100;
                        const fPct = (c.fallback_count / c.total_students) * 100;

                        const bottleneckBadge = c.is_prerequisite_bottleneck
                            ? '<span class="badge badge-red">⚠️ Bottleneck</span>'
                            : '';

                        cBody.innerHTML += `
                            <tr>
                                <td>
                                    <div style="font-weight:600;color:#f0f6fc;">${c.concept_name} ${bottleneckBadge}</div>
                                    <div style="font-size:11px;color:#8b949e;">${c.concept_id}</div>
                                </td>
                                <td>${c.total_students}</td>
                                <td>
                                    <div class="progress-bar-bg" title="Green: Mastered (${c.mastered_count}), Amber: Learning (${c.learning_count}), Red: Flagged (${c.fallback_count})">
                                        <div class="progress-fill-green" style="width: ${mPct}%;"></div>
                                        <div class="progress-fill-amber" style="width: ${lPct}%;"></div>
                                        <div class="progress-fill-red" style="width: ${fPct}%;"></div>
                                    </div>
                                    <span style="font-size:11px;color:#8b949e;">${c.mastered_count}M / ${c.learning_count}L / ${c.fallback_count}F</span>
                                </td>
                                <td><strong style="color:${c.mastery_rate_percent >= 70 ? '#3fb950' : '#d29922'};">${c.mastery_rate_percent.toFixed(1)}%</strong></td>
                                <td>
                                    ${c.fallback_count > 0 ? '<span class="badge badge-red">Requires Intervention</span>' : (c.mastery_rate_percent >= 70 ? '<span class="badge badge-green">Healthy</span>' : '<span class="badge badge-amber">Review Needed</span>')}
                                </td>
                            </tr>
                        `;
                    });
                }

            } catch (err) {
                console.error('Error loading instructor overview:', err);
                document.getElementById('alertsTableBody').innerHTML = `<tr><td colspan="6" style="color:#f85149;padding:20px;">Error: ${err.message}</td></tr>`;
            }
        }

        async function overrideMastery(studentId, sourceId, conceptId, newStatus) {
            const reason = prompt(`Confirm setting status of '${conceptId}' to ${newStatus} for ${studentId}. Optional notes:`, "Instructor 1-on-1 review");
            if (reason === null) return;

            try {
                const res = await fetch('/instructor/api/reset-mastery', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: studentId,
                        source_id: sourceId,
                        concept_id: conceptId,
                        new_status: newStatus,
                        instructor_notes: reason
                    })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Override failed');

                alert(data.message);
                loadInstructorData();
            } catch (err) {
                alert('Error: ' + err.message);
            }
        }

        window.addEventListener('DOMContentLoaded', loadInstructorData);
    </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def get_instructor_portal() -> HTMLResponse:
    """Render the Instructor Analytics & Human Intervention Web Portal."""
    return HTMLResponse(content=INSTRUCTOR_HTML)


@router.get("/api/overview", response_model=CohortOverview)
def get_overview_api(source_id: Optional[str] = Query(default=None)) -> CohortOverview:
    """Retrieve cohort overview metrics, active alerts, and concept analytics."""
    return get_cohort_overview(source_id)


@router.post("/api/reset-mastery", response_model=ResetMasteryResponse)
def reset_mastery_api(req: ResetMasteryRequest) -> ResetMasteryResponse:
    """Instructor override endpoint to reset or verify a student's concept mastery."""
    try:
        return reset_student_concept_status(
            student_id=req.student_id,
            source_id=req.source_id,
            concept_id=req.concept_id,
            new_status=req.new_status,
            instructor_notes=req.instructor_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset mastery: {str(e)}")
