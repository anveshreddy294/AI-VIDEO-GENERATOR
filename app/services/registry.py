"""Persistent Source Registry & File Validation Engine for Step 1.

Handles:
- Unique ID generation (source_id, asset_id, upload_id)
- SHA-256 hash calculation & duplicate detection
- File signature & MIME validation
- Source status lifecycle management
- Persistent storage of original files and derived JSON records (ContentUnits, KnowledgeGraph)
"""

import hashlib
import json
import logging
import mimetypes
import shutil
from .storage import atomic_json, serialized, validate_id
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..core.config import BASE_DIR, settings
from .schemas import ContentUnit, KnowledgeGraph, SourceRecord

logger = logging.getLogger(__name__)

# Known magic bytes / signatures for allowed file types
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "mp4": [b"ftyp"],  # matched anywhere in first 32 bytes
    "mov": [b"ftyp", b"moov", b"free", b"wide"],
    "mkv": [b"\x1a\x45\xdf\xa3"],
}

def get_registry_dir() -> Path:
    """Active runtime registry directory for mutable storage."""
    d = getattr(settings, "registry_dir", BASE_DIR / "storage" / "runtime" / "registry")
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_fixtures_registry_dir() -> Path:
    """Deterministic fixtures registry directory for reproducible seed data."""
    f_dir = getattr(settings, "fixtures_dir", BASE_DIR / "tests" / "fixtures") / "registry"
    if not settings.include_fixture_sources:
        return get_registry_dir()
    if f_dir.exists():
        return f_dir
    return BASE_DIR / "storage" / "registry"


# Backward-compatibility alias
REGISTRY_DIR = get_registry_dir()
SOURCES_INDEX_FILE = get_registry_dir() / "sources_index.json"


def _load_sources_index() -> dict[str, dict[str, Any]]:
    """Loads sources index by merging seed fixtures with runtime additions."""
    fixtures_index: dict[str, dict[str, Any]] = {}
    fixtures_file = get_fixtures_registry_dir() / "sources_index.json"
    if settings.include_fixture_sources and fixtures_file.exists():
        try:
            fixtures_index = json.loads(fixtures_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("[registry] Could not read fixtures sources_index: %s", exc)

    runtime_file = get_registry_dir() / "sources_index.json"
    if not runtime_file.exists():
        return fixtures_index

    try:
        runtime_index = json.loads(runtime_file.read_text(encoding="utf-8"))
        return {**fixtures_index, **runtime_index}
    except Exception as exc:
        raise RuntimeError("Cannot read runtime source index; refusing to overwrite it") from exc


def _save_sources_index(index: dict[str, dict[str, Any]]) -> None:
    """Save sources index exclusively to isolated runtime storage."""
    runtime_file = get_registry_dir() / "sources_index.json"
    atomic_json(runtime_file, index)


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_file(file_path: Path, filename: str) -> tuple[str, str]:
    """Validate extension, MIME type, file size, readability, corruption, and magic bytes.

    Returns: (source_type, mime_type)
    """
    if not file_path.exists() or file_path.stat().st_size == 0:
        raise ValueError(f"File '{filename}' is empty or does not exist.")

    ext = Path(filename).suffix.lstrip(".").lower()
    if not settings.is_allowed(filename):
        raise ValueError(f"Extension '.{ext}' is not allowed.")

    size = file_path.stat().st_size
    # 500 MB size limit
    if size > 500 * 1024 * 1024:
        raise ValueError(f"File '{filename}' exceeds maximum allowed size of 500MB.")

    # Determine source_type
    if ext == "pdf":
        source_type = "pdf"
    elif ext in settings.IMAGE_EXTENSIONS if hasattr(settings, "IMAGE_EXTENSIONS") else ext in {"png", "jpg", "jpeg"}:
        source_type = "image"
    elif ext == "txt":
        source_type = "txt"
    elif ext in settings.video_extensions:
        source_type = "video"
    else:
        source_type = "pdf"

    guessed_mime, _ = mimetypes.guess_type(filename)
    mime_type = guessed_mime or f"application/{ext}"

    # Check magic bytes for non-txt files
    if ext != "txt":
        with file_path.open("rb") as f:
            header = f.read(32)
        signatures = MAGIC_SIGNATURES.get(ext, [])
        valid = False
        for sig in signatures:
            if sig in header:
                valid = True
                break
        if not valid and signatures:
            raise ValueError(
                f"File signature check failed for '{filename}'. File may be corrupted or disguised."
            )

    return source_type, mime_type


def find_existing_by_hash(file_hash: str) -> SourceRecord | None:
    """Check if the exact file hash has already been registered."""
    index = _load_sources_index()
    matches = [SourceRecord.model_validate(r) for r in index.values() if r.get("file_hash") == file_hash]
    return max(matches, key=lambda r: r.version) if matches else None


def find_latest_by_filename(filename: str) -> SourceRecord | None:
    """Check the latest version registered under the same filename."""
    index = _load_sources_index()
    matches = [SourceRecord.model_validate(r) for r in index.values() if r.get("filename") == filename]
    return max(matches, key=lambda r: r.version) if matches else None



@serialized
def register_source(
    temp_path: Path,
    filename: str,
    uploaded_by: str = "student_default",
    user_id: str | None = None,
    title: str | None = None,
) -> tuple[SourceRecord, Path]:
    """Validate file, compute hash, create SourceRecord with versioning, and persist original file."""
    source_type, mime_type = validate_file(temp_path, filename)
    file_hash = calculate_sha256(temp_path)
    file_size = temp_path.stat().st_size

    # Check existing records by hash and filename for accurate versioning
    existing_by_hash = find_existing_by_hash(file_hash)
    existing_by_name = find_latest_by_filename(filename)

    # Version resolves from latest registered record of this content or filename
    latest_record = existing_by_name or existing_by_hash
    version = (latest_record.version + 1) if latest_record else 1
    parent_id = latest_record.source_id if latest_record else None
    effective_user = user_id or uploaded_by or "student_default"
    source_ver = f"v{version}"

    record = SourceRecord(
        filename=filename,
        title=title or Path(filename).stem.replace("_", " ").title(),
        source_type=source_type,  # type: ignore
        mime_type=mime_type,
        file_hash=file_hash,
        sha256=file_hash,
        file_size=file_size,
        uploaded_by=uploaded_by,
        user_id=effective_user,
        owner_user_id=effective_user,
        version=version,
        source_version=source_ver,
        parent_source_id=parent_id,
        status="UPLOADED",
    )

    # 1. Canonical runtime upload location: storage/runtime/uploads/{user_id}/{source_id}/
    user_source_dir = settings.upload_dir / effective_user / record.source_id
    user_source_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower()
    persistent_file = user_source_dir / f"original{ext}"

    # Also link/copy to legacy storage/runtime/uploads/{source_id}/ for backward compatibility
    legacy_source_dir = settings.upload_dir / record.source_id
    legacy_source_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = legacy_source_dir / f"original{ext}"

    shutil.copyfile(temp_path, persistent_file)
    if persistent_file != legacy_file:
        try:
            shutil.copyfile(temp_path, legacy_file)
        except Exception:
            pass

    save_source_record(record)
    _record_source_version(record)
    return record, persistent_file


def _record_source_version(record: SourceRecord) -> None:
    """Record immutable version entry in source_versions.json."""
    versions_file = get_registry_dir() / "source_versions.json"
    data: dict[str, list[dict[str, Any]]] = {}
    if versions_file.exists():
        try:
            data = json.loads(versions_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    entry = {
        "source_id": record.source_id,
        "version": record.version,
        "source_version": record.source_version,
        "user_id": record.user_id,
        "file_hash": record.file_hash,
        "sha256": record.sha256,
        "filename": record.filename,
        "created_at": record.created_at,
    }
    data.setdefault(record.source_id, []).append(entry)
    atomic_json(versions_file, data)


@serialized
def save_source_record(record: SourceRecord) -> None:
    """Save/update a SourceRecord in the persistent registry."""
    record.updated_at = datetime.now(timezone.utc).isoformat()
    index = _load_sources_index()
    index[record.source_id] = record.model_dump()
    _save_sources_index(index)


@serialized
def update_source_status(
    source_id: str,
    status: str,
    error_message: str | None = None,
) -> SourceRecord:
    """Update status of a source in the registry."""
    index = _load_sources_index()
    if source_id not in index:
        raise KeyError(f"Source ID '{source_id}' not found in registry.")

    record_data = index[source_id]
    record_data["status"] = status
    record_data["error_message"] = error_message
    record = SourceRecord.model_validate(record_data)
    save_source_record(record)
    return record


def save_content_units(source_id: str, content_units: list[ContentUnit]) -> None:
    """Persist normalized ContentUnits for a source to JSON in runtime registry."""
    source_dir = get_registry_dir() / validate_id(source_id)
    source_dir.mkdir(parents=True, exist_ok=True)
    cu_file = source_dir / "content_units.json"
    data = [cu.model_dump() for cu in content_units]
    atomic_json(cu_file, data)


def load_content_units(source_id: str) -> list[ContentUnit]:
    """Load normalized ContentUnits for a source with runtime, fixture, and legacy fallback."""
    # 1. Check runtime registry
    cu_file = get_registry_dir() / validate_id(source_id) / "content_units.json"
    # 2. Check fixtures registry
    if not cu_file.exists():
        cu_file = get_fixtures_registry_dir() / validate_id(source_id) / "content_units.json"
    # 3. Check legacy storage path
    if not cu_file.exists():
        cu_file = BASE_DIR / "storage" / "registry" / validate_id(source_id) / "content_units.json"

    if not cu_file.exists():
        return []
    data = json.loads(cu_file.read_text(encoding="utf-8"))
    return [ContentUnit.model_validate(item) for item in data]


# Alias for backward compatibility
get_content_units = load_content_units


def save_knowledge_graph(source_id: str, kg: KnowledgeGraph) -> None:
    """Persist Knowledge Graph for a source to JSON in runtime registry."""
    from .concept_id import normalize_knowledge_graph
    normalized_kg, _ = normalize_knowledge_graph(kg, source_id=source_id)
    source_dir = get_registry_dir() / validate_id(source_id)
    source_dir.mkdir(parents=True, exist_ok=True)
    kg_file = source_dir / "knowledge_graph.json"
    atomic_json(kg_file, normalized_kg.model_dump())


def load_knowledge_graph(source_id: str) -> KnowledgeGraph | None:
    """Load Knowledge Graph for a source with runtime, fixture, and legacy fallback."""
    # 1. Check runtime registry
    kg_file = get_registry_dir() / validate_id(source_id) / "knowledge_graph.json"
    # 2. Check fixtures registry
    if not kg_file.exists():
        kg_file = get_fixtures_registry_dir() / validate_id(source_id) / "knowledge_graph.json"
    # 3. Check legacy storage path
    if not kg_file.exists():
        kg_file = BASE_DIR / "storage" / "registry" / validate_id(source_id) / "knowledge_graph.json"

    if not kg_file.exists():
        return None
    try:
        data = json.loads(kg_file.read_text(encoding="utf-8"))
        kg = KnowledgeGraph.model_validate(data)
        from .concept_id import normalize_knowledge_graph
        normalized_kg, _ = normalize_knowledge_graph(kg, source_id=source_id)
        return normalized_kg
    except Exception as exc:
        logger.warning("[registry] Failed to load knowledge graph for %s: %s", source_id, exc)
        return None


def get_source_record(source_id: str) -> SourceRecord | None:
    """Load a single SourceRecord by source_id. Returns None if not found."""
    index = _load_sources_index()
    record_data = index.get(source_id)
    if not record_data:
        return None
    try:
        return SourceRecord.model_validate(record_data)
    except Exception as exc:
        logger.warning("[registry] Failed to validate source record for %s: %s", source_id, exc)
        return None


def get_source(source_id: str) -> SourceRecord | None:
    """Convenience alias for get_source_record."""
    return get_source_record(source_id)



def save_rich_chunks(source_id: str, chunks) -> None:
    atomic_json(get_registry_dir() / validate_id(source_id) / "rich_chunks.json", [c.model_dump() for c in chunks])


def load_rich_chunks(source_id: str) -> list[dict]:
    path = get_registry_dir() / validate_id(source_id) / "rich_chunks.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


# --- Partitioned Ingestion Storage Helpers ---

def save_normalized_records(user_id: str, source_id: str, version: str, records: list[dict[str, Any]]) -> Path:
    """Save normalized content records under storage/runtime/normalized/{user_id}/{source_id}/{version}/normalized.json."""
    norm_dir = settings.runtime_dir / "normalized" / validate_id(user_id) / validate_id(source_id) / validate_id(version)
    norm_dir.mkdir(parents=True, exist_ok=True)
    norm_file = norm_dir / "normalized.json"
    atomic_json(norm_file, records)
    return norm_file


def load_normalized_records(user_id: str, source_id: str, version: str = "v1") -> list[dict[str, Any]]:
    norm_file = settings.runtime_dir / "normalized" / validate_id(user_id) / validate_id(source_id) / validate_id(version) / "normalized.json"
    if not norm_file.exists():
        return []
    return json.loads(norm_file.read_text(encoding="utf-8"))


def save_sanitized_records(user_id: str, source_id: str, version: str, records: list[dict[str, Any]]) -> Path:
    """Save sanitized content records under storage/runtime/sanitized/{user_id}/{source_id}/{version}/sanitized.json."""
    san_dir = settings.runtime_dir / "sanitized" / validate_id(user_id) / validate_id(source_id) / validate_id(version)
    san_dir.mkdir(parents=True, exist_ok=True)
    san_file = san_dir / "sanitized.json"
    atomic_json(san_file, records)
    return san_file


def load_sanitized_records(user_id: str, source_id: str, version: str = "v1") -> list[dict[str, Any]]:
    san_file = settings.runtime_dir / "sanitized" / validate_id(user_id) / validate_id(source_id) / validate_id(version) / "sanitized.json"
    if not san_file.exists():
        return []
    return json.loads(san_file.read_text(encoding="utf-8"))


def save_quarantine_records(user_id: str, source_id: str, version: str, records: list[dict[str, Any]]) -> Path:
    """Save quarantined prompt-injection records under storage/runtime/quarantine/{user_id}/{source_id}/{version}/quarantine.json."""
    quar_dir = settings.runtime_dir / "quarantine" / validate_id(user_id) / validate_id(source_id) / validate_id(version)
    quar_dir.mkdir(parents=True, exist_ok=True)
    quar_file = quar_dir / "quarantine.json"
    atomic_json(quar_file, records)
    return quar_file


def load_quarantine_records(user_id: str, source_id: str, version: str = "v1") -> list[dict[str, Any]]:
    quar_file = settings.runtime_dir / "quarantine" / validate_id(user_id) / validate_id(source_id) / validate_id(version) / "quarantine.json"
    if not quar_file.exists():
        return []
    return json.loads(quar_file.read_text(encoding="utf-8"))

