"""Static learner shell; private data is fetched with the existing verified auth helper."""

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["Learning experience"])
STATIC = Path(__file__).resolve().parent.parent / "static"


@router.get("/learn", include_in_schema=False)
def learning_page() -> FileResponse:
    return FileResponse(
        STATIC / "learning.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/assets/learning.js", include_in_schema=False)
def learning_script() -> FileResponse:
    return FileResponse(STATIC / "learning.js", media_type="application/javascript")


@router.get("/assets/learning.css", include_in_schema=False)
def learning_style() -> FileResponse:
    return FileResponse(STATIC / "learning.css", media_type="text/css")
