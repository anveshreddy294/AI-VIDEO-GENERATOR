"""Instructor Analytics & Human Intervention Portal API.

Endpoints:
- GET  /instructor              → HTML Instructor Dashboard UI
- GET  /instructor/api/overview → Cohort overview, alerts, and concept analytics JSON
- POST /instructor/api/reset-mastery → Override student mastery or reset from kill switch

SEC-003: All API endpoints are guarded by an INSTRUCTOR_API_KEY header check.
Set INSTRUCTOR_API_KEY in your .env file. If unset, access is blocked in all
environments to prevent accidental exposure of student data.
"""

import logging
import os
from typing import Any,Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Security
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader

from ..services.instructor.analytics import get_cohort_overview, reset_student_concept_status
from ..services.instructor.schemas import (
    CohortOverview,
    ResetMasteryRequest,
    ResetMasteryResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SEC-003: Instructor API Key Guard
# ---------------------------------------------------------------------------
_INSTRUCTOR_KEY_ENV = "INSTRUCTOR_API_KEY"
_api_key_header = APIKeyHeader(name="X-Instructor-Key", auto_error=False)


def _require_instructor_key(api_key: str = Security(_api_key_header)) -> str:
    """Dependency: validates the X-Instructor-Key header against INSTRUCTOR_API_KEY env var."""
    expected = os.getenv(_INSTRUCTOR_KEY_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="Instructor access is disabled. Set INSTRUCTOR_API_KEY in your .env to enable.",
        )
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Instructor-Key header.",
        )
    return api_key


router = APIRouter(prefix="/instructor", tags=["Instructor Analytics"])

INSTRUCTOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI - Instructor Analytics & Human Intervention Portal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: #0f1117;
            background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27160%27%20height%3D%27160%27%20viewBox%3D%270%200%20160%20160%27%3E%3Cg%20fill%3D%27none%27%20stroke%3D%27%234ecb94%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%20opacity%3D%270.10%27%3E%3Ccircle%20cx%3D%2780%27%20cy%3D%2780%27%20r%3D%275%27%20fill%3D%27%23f09a80%27%20fill-opacity%3D%270.25%27%20stroke%3D%27none%27/%3E%3Cpath%20d%3D%27M80%2C72%20C76%2C58%2084%2C48%2080%2C42%20C76%2C48%2084%2C58%2080%2C72%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M80%2C88%20C84%2C102%2076%2C112%2080%2C118%20C84%2C112%2076%2C102%2080%2C88%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M72%2C80%20C58%2C76%2048%2C84%2042%2C80%20C48%2C76%2058%2C84%2072%2C80%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M88%2C80%20C102%2C84%20112%2C76%20118%2C80%20C112%2C84%20102%2C76%2088%2C80%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M80%2C42%20Q80%2C20%2050%2C20%20Q20%2C20%2020%2C50%20Q20%2C80%2042%2C80%27/%3E%3Cpath%20d%3D%27M80%2C118%20Q80%2C140%20110%2C140%20Q140%2C140%20140%2C110%20Q140%2C80%20118%2C80%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3C/g%3E%3C/svg%3E");
            background-repeat: repeat;
            background-size: 160px 160px;
            background-attachment: fixed;
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
            border-radius: 4px;
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
            border-radius: 4px;
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
            border-radius: 3px;
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
            border-radius: 3px;
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
            <span> VisualAI Instructor Portal</span>
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
                <span> Active Human Intervention Alerts</span>
                <button onclick="loadInstructorData()" class="btn-action"> Refresh</button>
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
                <span> Concept Mastery & Bottleneck Heatmap</span>
            </div>
            <div class="section-desc">
                Cohort-wide distribution of student mastery across each curriculum topic. Concepts marked with <strong> Bottleneck</strong> are prerequisites where failure cascades to dependent topics.
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
                    aBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#3fb950;padding:24px;"> No active human intervention alerts. All students are progressing smoothly!</td></tr>';
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
                                        <button onclick="overrideMastery('${a.student_id}', '${a.source_id}', '${a.concept_id}', 'LEARNING')" class="btn-action" title="Reset iterations to 0 and allow student to retry remediation"> Reset to Learning</button>
                                        <button onclick="overrideMastery('${a.student_id}', '${a.source_id}', '${a.concept_id}', 'MASTERED')" class="btn-action btn-success" title="Manually verify concept after 1-on-1 instructor session"> Verify Mastered</button>
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
                            ? '<span class="badge badge-red"> Bottleneck</span>'
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
def get_overview_api(
    source_id: Optional[str] = Query(default=None),
    _key: str = Depends(_require_instructor_key),
) -> CohortOverview:
    """Retrieve cohort overview metrics, active alerts, and concept analytics.

    Requires: X-Instructor-Key header matching INSTRUCTOR_API_KEY env var.
    """
    return get_cohort_overview(source_id)


@router.post("/api/reset-mastery", response_model=ResetMasteryResponse)
def reset_mastery_api(
    req: ResetMasteryRequest,
    _key: str = Depends(_require_instructor_key),
) -> ResetMasteryResponse:
    """Instructor override endpoint to reset or verify a student's concept mastery.

    Requires: X-Instructor-Key header matching INSTRUCTOR_API_KEY env var.
    SEC-008: new_status is constrained to ['LEARNING', 'MASTERED'] via schema Literal.
    """
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
    except Exception:
        # SEC-010: Do not leak internal exception details to API responses
        logger.exception("Failed to reset mastery for %s / %s", req.student_id, req.concept_id)
        raise HTTPException(status_code=500, detail="Failed to reset mastery. Check server logs.")


@router.get("/alerts")
def get_alerts(
    source_id: Optional[str] = Query(default=None),
    _key: str = Depends(_require_instructor_key),
) -> dict[str, Any]:
    """Retrieve all active kill-switch human intervention alerts."""
    overview = get_cohort_overview(source_id)
    return {"alerts": overview.alerts, "total": len(overview.alerts)}


@router.get("/analytics", response_model=CohortOverview)
def get_analytics(
    source_id: Optional[str] = Query(default=None),
    _key: str = Depends(_require_instructor_key),
) -> CohortOverview:
    """Retrieve cohort-wide mastery analytics and concept bottleneck heatmaps."""
    return get_cohort_overview(source_id)


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    notes: Optional[str] = Body(default="Resolved by instructor"),
    _key: str = Depends(_require_instructor_key),
) -> ResetMasteryResponse:
    """Resolve an active human intervention alert by resetting the concept status."""
    overview = get_cohort_overview()
    target_alert = next((a for a in overview.alerts if a.alert_id == alert_id), None)
    if not target_alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    return reset_student_concept_status(
        student_id=target_alert.student_id,
        source_id=target_alert.source_id,
        concept_id=target_alert.concept_id,
        new_status="LEARNING",
        instructor_notes=notes,
    )


@router.post("/mastery/{student_id}/{source_id}/{concept_id}/reset", response_model=ResetMasteryResponse)
def reset_student_mastery_path(
    student_id: str,
    source_id: str,
    concept_id: str,
    new_status: str = Query(default="LEARNING"),
    notes: Optional[str] = Query(default=None),
    _key: str = Depends(_require_instructor_key),
) -> ResetMasteryResponse:
    """Direct path parameter endpoint to reset or override student concept mastery."""
    if new_status not in ("LEARNING", "MASTERED"):
        raise HTTPException(status_code=400, detail="new_status must be 'LEARNING' or 'MASTERED'")
    try:
        return reset_student_concept_status(
            student_id=student_id,
            source_id=source_id,
            concept_id=concept_id,
            new_status=new_status,  # type: ignore
            instructor_notes=notes or "Reset via instructor mastery endpoint",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

