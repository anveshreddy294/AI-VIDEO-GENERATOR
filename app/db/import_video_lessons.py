"""Explicit, non-destructive import of owner-scoped lesson JSON into PostgreSQL."""
import argparse
from pathlib import Path
from uuid import UUID

from ..core import postgres
from ..services.educational_content import EducationalLesson
from ..services.repositories.lesson_store import read_lesson, write_lesson


def import_lessons(directory: Path, *, apply=False):
    if not postgres.enabled():
        raise postgres.VideoDatabaseError("POSTGRES_LESSON_PROVIDER_REQUIRED")
    postgres.readiness()
    imported = unchanged = 0
    # One transaction: conflicts/missing artifacts roll back the entire batch.
    with postgres.transaction():
        for path in sorted(directory.glob("*/*.json")):
            lesson = EducationalLesson.model_validate_json(path.read_text(encoding="utf-8"))
            if UUID(path.parent.name) != lesson.user_id or path.stem != lesson.lesson_id or lesson.content.user_id != lesson.user_id:
                raise ValueError("IMPORT_OWNER_MISMATCH")
            document = lesson.model_dump(mode="json")
            existing = read_lesson(directory, lesson.user_id, lesson.lesson_id)
            if existing is not None:
                if existing != document:
                    raise ValueError("IMPORT_CONFLICT")
                unchanged += 1
                continue
            from ..services.repositories.lesson_store import validate_artifact_references
            validate_artifact_references(document)
            if apply:
                write_lesson(directory, lesson.user_id, lesson.lesson_id, document)
            imported += 1
    return {"mode": "apply" if apply else "dry_run", "imported" if apply else "eligible": imported, "unchanged": unchanged}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Default is validation only; never overwrite existing records")
    args = parser.parse_args()
    try:
        print(import_lessons(args.directory.resolve(), apply=args.apply))
    except postgres.VideoDatabaseError as error:
        raise SystemExit(error.code) from None
    except (ValueError, OSError):
        raise SystemExit("IMPORT_VALIDATION_FAILED: check ownership, conflicts, JSON and media references") from None
    finally:
        postgres.close_pool()
