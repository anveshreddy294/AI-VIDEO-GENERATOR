"""Assessment Session persistence.

File-based storage for active and completed assessment sessions.
"""

import json
from pathlib import Path

from ...core.config import BASE_DIR
from .schemas import AssessmentSession

SESSIONS_DIR = BASE_DIR / "storage" / "assessment_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def save_session(session: AssessmentSession) -> None:
    """Persist an AssessmentSession to disk."""
    path = SESSIONS_DIR / f"{session.session_id}.json"
    path.write_text(
        json.dumps(session.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )


def load_session(session_id: str) -> AssessmentSession | None:
    """Load an AssessmentSession from disk. Returns None if not found."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AssessmentSession.model_validate(data)
    except Exception as exc:
        print(f"[session_store] Failed to load session {session_id}: {exc}")
        return None
