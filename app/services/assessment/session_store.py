"""Assessment Session persistence.

File-based storage for active and completed assessment sessions.
"""

import json
from pathlib import Path

from ...core.config import BASE_DIR, settings
from .schemas import AssessmentSession

SESSIONS_DIR = getattr(settings, "assessment_dir", BASE_DIR / "storage" / "runtime" / "assessment_sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_SESSIONS_DIR = BASE_DIR / "storage" / "assessment_sessions"


def save_session(session: AssessmentSession) -> None:
    """Persist an AssessmentSession to runtime disk."""
    path = SESSIONS_DIR / f"{session.session_id}.json"
    path.write_text(
        json.dumps(session.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )


def load_session(session_id: str) -> AssessmentSession | None:
    """Load an AssessmentSession from runtime disk with legacy fallback. Returns None if not found."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists() and LEGACY_SESSIONS_DIR.exists():
        path = LEGACY_SESSIONS_DIR / f"{session_id}.json"

    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AssessmentSession.model_validate(data)
    except Exception as exc:
        print(f"[session_store] Failed to load session {session_id}: {exc}")
        return None
