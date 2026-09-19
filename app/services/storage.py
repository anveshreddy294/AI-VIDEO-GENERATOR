"""Atomic JSON persistence and cross-process serialization for local stores."""
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from ..core.config import settings

_mutex = threading.RLock()
_local = threading.local()


def validate_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("Identifiers must contain 1–128 letters, digits, underscores or hyphens")
    if value.upper().split('.')[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
        raise ValueError("Reserved identifier")
    return value


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def store_lock():
    """Serialize read/modify/write operations, including nested store calls."""
    with _mutex:
        if getattr(_local, "locked", False):
            yield
            return
        path = settings.runtime_dir / ".store.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as stream:
            if path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            _local.locked = True
            try:
                yield
            finally:
                _local.locked = False
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def serialized(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with store_lock():
            return fn(*args, **kwargs)
    return wrapped


def commit_assessment(session, profile, matrix) -> None:
    """Write-ahead record permits safe replay after a partial multi-file commit."""
    with store_lock():
        pending = settings.runtime_dir / "pending_assessment_commits"
        path = pending / f"{validate_id(session.session_id)}.json"
        atomic_json(path, {"session": session.model_dump(), "profile": profile.model_dump(), "matrix": matrix.model_dump()})
        recover_assessment_commits()


def recover_assessment_commits() -> None:
    from .assessment.schemas import AssessmentSession, StudentLearningProfile, VideoTargetMatrix
    from .assessment.session_store import save_session
    from .assessment.profile import save_profile
    from .assessment.video_target import save_video_matrix
    with store_lock():
        for path in sorted((settings.runtime_dir / "pending_assessment_commits").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            session = AssessmentSession.model_validate(data["session"])
            profile = StudentLearningProfile.model_validate(data["profile"])
            matrix = VideoTargetMatrix.model_validate(data["matrix"])
            if (session.student_id, session.source_id) != (profile.student_id, profile.source_id) or (profile.student_id, profile.source_id) != (matrix.student_id, matrix.source_id):
                raise ValueError("Assessment commit identity mismatch")
            save_profile(profile)
            save_video_matrix(matrix)
            save_session(session)
            path.unlink()
