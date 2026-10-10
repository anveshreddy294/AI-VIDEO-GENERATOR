"""Static learner shell; private data is fetched with the existing verified auth helper."""

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
from ..core.config import settings

router = APIRouter(tags=["Learning experience"])
STATIC = Path(__file__).resolve().parent.parent / "static"


@router.get('/profile', include_in_schema=False)
def profile_page() -> HTMLResponse:
    return HTMLResponse((STATIC / 'learning-profile.html').read_text(encoding='utf-8'), headers={'Cache-Control': 'no-store'})


@router.get('/assets/learning-profile.js', include_in_schema=False)
def profile_script() -> FileResponse:
    return FileResponse(STATIC / 'learning-profile.js', media_type='application/javascript', headers={'Cache-Control': 'no-cache'})


@router.get("/learn", include_in_schema=False)
def learning_page() -> HTMLResponse:
    return HTMLResponse(
        (STATIC / "learning.html").read_text(encoding="utf-8").replace("__JOB_POLL_TIMEOUT_SECONDS__", str(settings.frontend_job_poll_timeout_seconds)),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/assets/learning.js", include_in_schema=False)
def learning_script() -> FileResponse:
    return FileResponse(STATIC / "learning.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@router.get("/assets/learning.css", include_in_schema=False)
def learning_style() -> FileResponse:
    return FileResponse(STATIC / "learning.css", media_type="text/css", headers={"Cache-Control": "no-cache"})


@router.get("/assets/notes.js", include_in_schema=False)
def notes_script() -> FileResponse:
    return FileResponse(STATIC / "notes.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@router.get("/assets/practice.js", include_in_schema=False)
def practice_script() -> FileResponse:
    return FileResponse(STATIC / "practice.js", media_type="application/javascript", headers={"Cache-Control":"no-cache"})


@router.get("/assets/resource-exports.js", include_in_schema=False)
def resource_exports_script() -> FileResponse:
    return FileResponse(STATIC / "resource-exports.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@router.get("/assets/analysis-results.js", include_in_schema=False)
def analysis_results_script() -> FileResponse:
    return FileResponse(STATIC / "analysis-results.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})
