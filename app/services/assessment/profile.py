from ..storage import atomic_json, validate_id, serialized
"""Step 7 — Student Learning Profile persistence.

File-based storage of StudentLearningProfile artifacts.
These profiles are the handoff artifact to Step 3 (video generation).
"""

import json
import logging
from pathlib import Path

from ...core.config import BASE_DIR, settings
from .schemas import ConceptMastery, StudentLearningProfile

logger = logging.getLogger(__name__)

PROFILES_DIR = getattr(settings, "learning_profiles_dir", BASE_DIR / "storage" / "runtime" / "learning_profiles")
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_PROFILES_DIR = BASE_DIR / "storage" / "learning_profiles"


def _profile_path(student_id: str, source_id: str) -> Path:
    """Get the file path for a student's profile on a specific source in runtime storage."""
    safe_student = validate_id(student_id)
    safe_source = validate_id(source_id)
    return PROFILES_DIR / f"{safe_student}_{safe_source}.json"


def save_profile(profile: StudentLearningProfile) -> None:
    """Persist a StudentLearningProfile to runtime disk."""
    path = _profile_path(profile.student_id, profile.source_id)
    atomic_json(path, profile.model_dump())


def load_profile(student_id: str, source_id: str) -> StudentLearningProfile | None:
    """Load a StudentLearningProfile from runtime disk with legacy fallback. Returns None if not found."""
    path = _profile_path(student_id, source_id)
    if not path.exists() and LEGACY_PROFILES_DIR.exists():
        safe_student = validate_id(student_id)
        safe_source = validate_id(source_id)
        path = LEGACY_PROFILES_DIR / f"{safe_student}_{safe_source}.json"

    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return StudentLearningProfile.model_validate(data)
    except Exception as exc:
        logger.warning("[profile] Failed to load profile for %s/%s: %s", student_id, source_id, exc)
        return None


def get_or_create_profile(student_id: str, source_id: str) -> StudentLearningProfile:
    """Load existing profile or create a new one."""
    profile = load_profile(student_id, source_id)
    if profile is not None:
        return profile
    return StudentLearningProfile(student_id=student_id, source_id=source_id)


def get_learning_profile(student_id: str, source_id: str) -> StudentLearningProfile | None:
    """Convenience alias for load_profile."""
    return load_profile(student_id, source_id)

