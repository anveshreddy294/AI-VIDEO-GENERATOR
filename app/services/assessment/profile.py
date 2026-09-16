"""Step 7 — Student Learning Profile persistence.

File-based storage of StudentLearningProfile artifacts.
These profiles are the handoff artifact to Step 3 (video generation).
"""

import json
from pathlib import Path

from ...core.config import BASE_DIR
from .schemas import ConceptMastery, StudentLearningProfile

PROFILES_DIR = BASE_DIR / "storage" / "learning_profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _profile_path(student_id: str, source_id: str) -> Path:
    """Get the file path for a student's profile on a specific source."""
    safe_student = student_id.replace("/", "_").replace("\\", "_")
    safe_source = source_id.replace("/", "_").replace("\\", "_")
    return PROFILES_DIR / f"{safe_student}_{safe_source}.json"


def save_profile(profile: StudentLearningProfile) -> None:
    """Persist a StudentLearningProfile to disk."""
    path = _profile_path(profile.student_id, profile.source_id)
    path.write_text(
        json.dumps(profile.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )


def load_profile(student_id: str, source_id: str) -> StudentLearningProfile | None:
    """Load a StudentLearningProfile from disk. Returns None if not found."""
    path = _profile_path(student_id, source_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return StudentLearningProfile.model_validate(data)
    except Exception as exc:
        print(f"[profile] Failed to load profile for {student_id}/{source_id}: {exc}")
        return None


def get_or_create_profile(student_id: str, source_id: str) -> StudentLearningProfile:
    """Load existing profile or create a new one."""
    profile = load_profile(student_id, source_id)
    if profile is not None:
        return profile
    return StudentLearningProfile(student_id=student_id, source_id=source_id)
