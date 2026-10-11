"""Authenticated source aggregate; atomic local or historical database transactions."""
from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue, TypeAdapter

from ...core.supabase import AuthenticatedUser, SupabaseRuntime, SupabaseResponseError
from ...core import postgres
from .source_metadata_store import copy_source, copy_version
from ..schemas import ContentUnit, KnowledgeGraph, SourceRecord

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
JSON_ROWS = TypeAdapter(list[dict[str, JsonValue]])
READ_PAGE_SIZE = 1000


class SourceVersion(BaseModel):
    user_id: UUID
    source_id: str
    version: int
    source_version: str
    file_hash: str
    sha256: str | None = None
    filename: str
    file_location: str
    provenance: dict[str, JsonValue] = Field(default_factory=dict)
    normalized_content: list[dict[str, JsonValue]] = Field(default_factory=list)
    sanitized_content: list[dict[str, JsonValue]] = Field(default_factory=list)
    quarantined_content: list[dict[str, JsonValue]] = Field(default_factory=list)
    rich_chunks: list[dict[str, JsonValue]] = Field(default_factory=list)
    topic_blueprint: dict[str, JsonValue] | None = None
    knowledge_diagnostics: dict[str, JsonValue] = Field(default_factory=dict)


class SupabaseSourceRepository:
    """Never uses file fallback or admin credentials for canonical source state."""

    def __init__(self, user: AuthenticatedUser, token: str, runtime: SupabaseRuntime) -> None:
        self.user = user
        self._token = token
        from .learning_storage import wrap
        self.runtime = wrap(runtime, user, token)

    @property
    def owner_id(self) -> str:
        return str(self.user.user_id)

    def _rows(self, table: str, **filters: str) -> list[dict[str, JsonValue]]:
        rows: list[dict[str, JsonValue]] = []
        while True:
            page = JSON_ROWS.validate_python(self.runtime.user_request(
                'GET', '/rest/v1/' + table, token=self._token,
                params={'select': '*', 'user_id': 'eq.' + self.owner_id,
                        'order': {'sources': 'source_id', 'source_versions': 'version',
                                  'content_units': 'sequence_index,content_id'}[table],
                        'limit': str(READ_PAGE_SIZE), 'offset': str(len(rows)), **filters}))
            if any(row.get('user_id') != self.owner_id for row in page):
                raise SupabaseResponseError('Source ownership mismatch')
            rows.extend(page)
            if len(page) < READ_PAGE_SIZE:
                return rows

    def decode_source(self, row: dict[str, JsonValue]) -> SourceRecord:
        """Explicit DB/model mapping: source_type is distinct from unit modality."""
        if row.get("user_id") != self.owner_id:
            raise SupabaseResponseError("Source ownership mismatch")
        data = {key: value for key, value in row.items() if key in SourceRecord.model_fields}
        data.update(user_id=self.owner_id, owner_user_id=self.owner_id, uploaded_by=self.owner_id)
        record = SourceRecord.model_validate(data)
        copy_source(self.owner_id, record)
        return record

    def encode_source(self, record: SourceRecord) -> dict[str, JsonValue]:
        data = JSON_OBJECT.validate_python(record.model_dump(mode='json'))
        data.pop('owner_user_id')
        data.pop('uploaded_by')
        data['user_id'] = self.owner_id
        return data

    def get_source(self, source_id: str) -> SourceRecord | None:
        rows = self._rows('sources', source_id='eq.' + source_id)
        return self.decode_source(rows[0]) if rows else None

    def list_sources(self) -> list[SourceRecord]:
        return [self.decode_source(row) for row in self._rows('sources')]

    def find_upload(self, filename: str, file_hash: str) -> SourceRecord | None:
        rows = self._rows('sources', filename='eq.' + filename, file_hash='eq.' + file_hash)
        return self.decode_source(rows[0]) if rows else None

    def latest_filename(self, filename: str) -> SourceRecord | None:
        rows = self._rows('sources', filename='eq.' + filename)
        return max((self.decode_source(row) for row in rows), key=lambda r: r.version, default=None)

    def get_source_version(self, source_id: str, version: int | None = None) -> SourceVersion | None:
        if version is None or postgres.enabled():
            record = self.get_source(source_id)
            if record is None:
                return None
            if version is None:
                version = record.version
        rows = self._rows('source_versions', source_id='eq.' + source_id, version='eq.' + str(version))
        result = SourceVersion.model_validate(rows[0]) if rows else None
        if result is not None:
            if result.source_id != source_id or result.version != version:
                raise SupabaseResponseError('Source/version mismatch')
            copy_version(self.owner_id, result)
        return result

    def sync_metadata(self) -> dict[str, int]:
        """Explicit, authenticated reconciliation of all owned metadata versions."""
        if not postgres.enabled():
            raise postgres.VideoDatabaseError('VIDEO_DATABASE_CONFIGURATION_INVALID')
        if self.runtime.verify_user(self._token).user_id != self.user.user_id:
            raise SupabaseResponseError('Source ownership mismatch')
        sources = self.list_sources()
        versions = 0
        for source in sources:
            for row in self._rows('source_versions', source_id='eq.' + source.source_id):
                version = SourceVersion.model_validate(row)
                if version.source_id != source.source_id:
                    raise SupabaseResponseError('Source/version mismatch')
                copy_version(self.owner_id, version)
                versions += 1
        return {'sources': len(sources), 'source_versions': versions}

    def get_content_units(self, source_id: str, version: int | None = None) -> list[ContentUnit]:
        if version is None:
            record = self.get_source(source_id)
            if record is None:
                return []
            version = record.version
        return [ContentUnit.model_validate(row) for row in self._rows(
            'content_units', source_id='eq.' + source_id, source_version='eq.' + str(version))]

    def has_content_units(self, source_id: str, version: int) -> bool:
        """Read one owned identity rather than downloading a document to list it."""
        return bool(self._rows('content_units', source_id='eq.' + source_id,
            source_version='eq.' + str(version), select='content_id,user_id', limit='1'))

    def commit_ingestion(self, record: SourceRecord, version: SourceVersion,
                         units: list[ContentUnit]) -> SourceRecord:
        """One HTTP RPC = one PostgreSQL transaction; never separate table writes."""
        if version.source_id != record.source_id or version.version != record.version:
            raise SupabaseResponseError('Source/version mismatch')
        unit_rows: list[dict[str, JsonValue]] = []
        for unit in units:
            if unit.source_id != record.source_id or unit.asset_id != record.asset_id:
                raise SupabaseResponseError('Content provenance mismatch')
            row = JSON_OBJECT.validate_python(unit.model_dump(mode='json'))
            row.update(user_id=self.owner_id, source_version=record.version, provenance=unit.provenance)
            unit_rows.append(row)
        version_row = JSON_OBJECT.validate_python(version.model_dump(mode='json'))
        version_row['user_id'] = self.owner_id
        result = self.runtime.user_request('POST', '/rest/v1/rpc/visualai_commit_source_ingestion',
            token=self._token, body={'p_source': self.encode_source(record),
                                    'p_version': version_row, 'p_units': unit_rows})
        committed = self.decode_source(JSON_OBJECT.validate_python(result))
        if postgres.enabled():
            # Read the committed version, including idempotent RPC responses; never
            # copy a proposed version that Supabase may not have accepted.
            if self.get_source_version(committed.source_id, committed.version) is None:
                raise postgres.VideoDatabaseError('SOURCE_METADATA_COPY_PENDING')
        return committed

    def mark_status(self, record: SourceRecord, status: Literal['INDEXING', 'READY', 'FAILED'],
                    error_message: str | None = None) -> SourceRecord:
        result = self.runtime.user_request('POST', '/rest/v1/rpc/visualai_source_index_status',
            token=self._token, body={'p_source_id': record.source_id, 'p_version': record.version,
                                    'p_status': status, 'p_error': error_message})
        return self.decode_source(JSON_OBJECT.validate_python(result))

    def save_source(self, record: SourceRecord) -> None:
        raise SupabaseResponseError('Use atomic ingestion or indexing status RPC')

    def save_content_units(self, source_id: str, units: list[ContentUnit]) -> None:
        raise SupabaseResponseError('Use atomic ingestion RPC')

    def get_knowledge_graph(self, source_id: str, version: int | None = None) -> KnowledgeGraph | None:
        """Compatibility projection requires an explicit immutable canonical version."""
        from .knowledge_repository import KnowledgeRepository, KnowledgeError
        from ..knowledge_service import KnowledgeService
        if version is None:
            raise KnowledgeError('INVALID_SCOPE')
        repo = KnowledgeRepository(self.user, self._token, self.runtime)
        return KnowledgeService(repo).project_graph(repo.scope(source_id, version))

    def save_knowledge_graph(self, source_id: str, kg: KnowledgeGraph) -> None:
        raise SupabaseResponseError('Use the internal typed canonical snapshot adapter')
