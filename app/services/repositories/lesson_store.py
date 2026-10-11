"""One persistence seam for existing educational lesson/video contracts."""
from contextlib import contextmanager
from functools import wraps
import json
from pathlib import Path

from ...core import postgres
from ...core.config import settings
from ..storage import atomic_json, store_lock, validate_id


@contextmanager
def lesson_store_lock():
    # Keep existing OS/thread serialization and execution-lock ordering intact.
    with store_lock():
        if postgres.enabled():
            with postgres.transaction():
                yield
        else:
            yield


def lesson_serialized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with lesson_store_lock():
            return function(*args, **kwargs)
    return wrapped


def _owner(connection, owner):
    connection.execute("SELECT set_config('visualai.owner_id', %s, true)", (str(owner),))


def read_lesson(directory, owner, lesson_id):
    validate_id(lesson_id)
    if not postgres.enabled():
        path = directory / str(owner) / f"{lesson_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    with postgres.transaction() as connection:
        _owner(connection, owner)
        row = connection.execute("SELECT document FROM visualai_video.lessons WHERE owner_id=%s AND lesson_id=%s", (owner, lesson_id)).fetchone()
        if row is None:
            return None
        document = row[0]
        document["video_generations"] = {job: data for job, data in connection.execute(
            "SELECT job_id, document FROM visualai_video.generations WHERE owner_id=%s AND lesson_id=%s ORDER BY history_index, job_id",
            (owner, lesson_id)).fetchall()}
        return document


def write_lesson(directory, owner, lesson_id, document):
    validate_id(lesson_id)
    if document.get("user_id") != str(owner) or document.get("content", {}).get("user_id") != str(owner) or document.get("lesson_id") != lesson_id:
        raise ValueError("Lesson ownership mismatch")
    if not postgres.enabled():
        atomic_json(directory / str(owner) / f"{lesson_id}.json", document)
        return
    from psycopg.types.json import Jsonb
    with postgres.transaction() as connection:
        _owner(connection, owner)
        previous = read_lesson(directory, owner, lesson_id)
        validate_artifact_references(document, previous)
        base = {key: value for key, value in document.items() if key != "video_generations"}
        connection.execute("""INSERT INTO visualai_video.lessons
            (owner_id,lesson_id,source_id,source_version,created_at,updated_at,document)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (owner_id,lesson_id) DO UPDATE SET
            source_id=EXCLUDED.source_id, source_version=EXCLUDED.source_version,
            updated_at=EXCLUDED.updated_at, document=EXCLUDED.document""",
            (owner,lesson_id,document.get("source_id"),document.get("source_version"),
             document["created_at"],document["updated_at"],Jsonb(base)))
        for history_index, (job_id, generation) in enumerate(document.get("video_generations", {}).items()):
            validate_id(job_id)
            artifact = generation.get("artifact") or {}
            current = document.get("video") or {}
            details = current if current.get("job_id") == job_id else artifact
            connection.execute("""INSERT INTO visualai_video.generations
                (owner_id,lesson_id,job_id,prior_job_id,history_index,status,stage,progress,error_code,indexing_status,created_at,completed_at,document)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (owner_id,lesson_id,job_id) DO UPDATE SET
                status=EXCLUDED.status, stage=EXCLUDED.stage, progress=EXCLUDED.progress,
                error_code=EXCLUDED.error_code, indexing_status=EXCLUDED.indexing_status,
                completed_at=EXCLUDED.completed_at, document=EXCLUDED.document""",
                (owner,lesson_id,job_id,generation.get("prior_job_id"),history_index,generation["status"],
                 details.get("stage"),details.get("progress",0),generation.get("error_code"),
                 generation.get("indexing_status","NOT_REQUESTED"),generation["created_at"],
                 generation.get("completed_at"),Jsonb(generation)))


def lesson_ids(directory, owner, *, limit=None):
    if not postgres.enabled():
        return sorted(path.stem for path in (directory / str(owner)).glob("*.json"))
    with postgres.transaction() as connection:
        _owner(connection, owner)
        query = "SELECT lesson_id FROM visualai_video.lessons WHERE owner_id=%s ORDER BY lesson_id"
        params = (owner,)
        if limit is not None:
            query += " LIMIT %s"
            params += (limit,)
        return [row[0] for row in connection.execute(query, params).fetchall()]


def validate_artifact_references(document, previous=None):
    """Only newly completed artifacts must exist; historical loss is handled by playback."""
    for job_id, generation in document.get("video_generations", {}).items():
        artifact = generation.get("artifact") or {}
        if generation.get("status") != "COMPLETED" or not artifact:
            continue
        old = (previous or {}).get("video_generations", {}).get(job_id, {})
        if old.get("status") == "COMPLETED" and old.get("artifact") == artifact:
            continue
        for field, roots in (("video_path", (settings.renders_dir, settings.video_output_dir)),
                             ("subtitle_path", (settings.captions_dir,))):
            value = artifact.get(field)
            if not value and field == "subtitle_path":
                continue  # Legacy generations may legitimately have no captions.
            if not value:
                raise postgres.VideoDatabaseError("VIDEO_ARTIFACT_REFERENCE_INVALID")
            path = Path(value).resolve()
            if not any(path.is_relative_to(root.resolve()) for root in roots) or not path.is_file():
                raise postgres.VideoDatabaseError("VIDEO_ARTIFACT_REFERENCE_INVALID")
