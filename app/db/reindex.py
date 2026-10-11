"""Explicit offline vector repair from canonical Supabase evidence; dry-run by default."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Mapping

from pydantic import JsonValue, TypeAdapter
from qdrant_client import QdrantClient, models

from ..core.config import settings
from ..core.supabase import SupabaseRuntime, get_supabase_runtime
from ..services.schemas import RichChunk
from . import vector_store

DIMENSION = 768
HASH_TOLERANCE = 1e-6
SEMANTIC_COSINE_MIN = 0.9999
READ_PAGE_SIZE = 256
JSON_ROWS = TypeAdapter(list[dict[str, JsonValue]])
EmbeddingFunction = Callable[[list[str]], list[list[float]]]


@dataclass(frozen=True)
class CanonicalChunk:
    owner_id: str
    source_id: str
    chunk: RichChunk
    content_ids: frozenset[str]

    def matches(self, point: models.Record) -> bool:
        """Require point ID, ownership, version, layer, text and evidence identifiers."""
        payload = point.payload or {}
        chunk = self.chunk
        return (str(point.id) == vector_store._point_id(chunk) and
                payload.get('user_id') == self.owner_id == chunk.user_id and
                payload.get('source_id') == self.source_id == chunk.source_id and
                payload.get('chunk_id') == chunk.chunk_id and payload.get('text') == chunk.text and
                payload.get('layer') == chunk.layer and
                payload.get('source_version') == chunk.source_version and
                payload.get('content_ids') == chunk.content_ids and
                bool(chunk.text.strip()) and bool(chunk.content_ids) and
                set(chunk.content_ids) <= self.content_ids)


def valid_vector(vector: object) -> bool:
    return (isinstance(vector, list) and len(vector) == DIMENSION and
            all(isinstance(value, (int, float)) and not isinstance(value, bool) and
                math.isfinite(value) for value in vector) and any(vector))


def is_historical(point: models.Record) -> bool:
    """Exact legacy signature is secondary to source/payload provenance, never length alone."""
    payload = point.payload or {}
    text = payload.get('text')
    if not isinstance(text, str) or not text.strip() or not valid_vector(point.vector):
        return False
    expected = [0.0] * DIMENSION
    for raw in text.lower().split():
        word = re.sub(r'[^\w]', '', raw)
        if word:
            expected[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSION] += 1
    norm = math.sqrt(sum(value * value for value in expected))
    if not norm:
        return False
    expected = [value / norm for value in expected]
    vector = point.vector
    assert isinstance(vector, list)
    return max(abs(a - b) for a, b in zip(vector, expected)) < HASH_TOLERANCE


def semantic_metadata(payload: Mapping[str, object]) -> bool:
    return all(payload.get(key) == value for key, value in provenance().items())


def provenance() -> dict[str, str | int]:
    return vector_store.embedding_contract('embeddinggemma')


def read_points(client: QdrantClient, collection: str) -> list[models.Record]:
    points: list[models.Record] = []
    offset: models.ExtendedPointId | None = None
    while True:
        page, offset = client.scroll(collection, limit=READ_PAGE_SIZE, offset=offset,
                                     with_payload=True, with_vectors=True)
        points.extend(page)
        if offset is None:
            return points


def load_canonical(runtime: SupabaseRuntime, token: str | None) -> tuple[dict[str, CanonicalChunk], set[tuple[str, str]]]:
    """GET only; caller-scoped RLS or explicitly configured backend administrative access."""
    def rows(table: str, order: str) -> list[dict[str, JsonValue]]:
        result: list[dict[str, JsonValue]] = []
        while True:
            params = {'select': '*', 'limit': str(READ_PAGE_SIZE), 'offset': str(len(result)), 'order': order}
            response = (runtime.user_request('GET', '/rest/v1/' + table, token=token, params=params)
                        if token else runtime.admin_request('GET', '/rest/v1/' + table, params=params))
            page = JSON_ROWS.validate_python(response)
            result.extend(page)
            if len(page) < READ_PAGE_SIZE:
                return result
    sources = {(str(row['user_id']), str(row['source_id'])) for row in rows('sources', 'source_id')}
    units: dict[tuple[str, str, int], set[str]] = {}
    for row in rows('content_units', 'user_id,source_id,source_version,content_id'):
        key = (str(row['user_id']), str(row['source_id']), int(str(row['source_version'])))
        units.setdefault(key, set()).add(str(row['content_id']))
    canonical: dict[str, CanonicalChunk] = {}
    for row in rows('source_versions', 'user_id,source_id,version'):
        owner, source = str(row['user_id']), str(row['source_id'])
        chunks = row.get('rich_chunks')
        if (owner, source) not in sources or not isinstance(chunks, list):
            continue
        for raw in chunks:
            chunk = RichChunk.model_validate(raw)
            entry = CanonicalChunk(owner, source, chunk,
                frozenset(units.get((owner, source, int(str(row['version']))), set())))
            key = vector_store._point_id(chunk)
            if key in canonical and canonical[key] != entry:
                raise RuntimeError('Ambiguous canonical point identity')
            canonical[key] = entry
    return canonical, sources


@dataclass
class ReindexReport:
    total: int = 0
    historical: int = 0
    semantic: int = 0
    unclassified: int = 0
    orphan: int = 0
    unreindexable: int = 0
    replacements_validated: int = 0
    attestations_validated: int = 0
    applied: int = 0
    attested: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.unreindexable += 1
        self.reasons[reason] = self.reasons.get(reason, 0) + 1


@dataclass(frozen=True)
class PlannedUpdate:
    point: models.Record
    vector: list[float]
    historical: bool


def reindex(client: QdrantClient, collection: str, canonical: Mapping[str, CanonicalChunk],
            sources: set[tuple[str, str]], *, apply: bool = False,
            embed: EmbeddingFunction = vector_store.embed_documents) -> ReindexReport:
    """Validate the complete plan before any write; preserve IDs and all unrelated payload fields."""
    params = client.get_collection(collection).config.params.vectors
    if getattr(params, 'size', None) != DIMENSION:
        raise RuntimeError('Existing collection dimension is incompatible; no changes made')
    points = read_points(client, collection)
    report = ReindexReport(total=len(points))
    plan: list[PlannedUpdate] = []
    for point in points:
        payload = point.payload or {}
        if (str(payload.get('user_id')), str(payload.get('source_id'))) not in sources:
            report.orphan += 1
        historical = is_historical(point)
        if historical:
            report.historical += 1
        elif valid_vector(point.vector) and semantic_metadata(payload):
            report.semantic += 1
            continue
        else:
            report.unclassified += 1
        entry = canonical.get(str(point.id))
        if not entry or not entry.matches(point):
            report.reject('missing_or_mismatched_canonical_evidence')
            continue
        vectors = embed([entry.chunk.text])
        if len(vectors) != 1 or not valid_vector(vectors[0]):
            raise RuntimeError('Invalid replacement embedding; no changes made')
        diagnostic = vector_store.get_last_embed_diagnostics()
        if (diagnostic is None or diagnostic.provider_used != 'ollama' or
                not diagnostic.dimension_validated or
                (diagnostic.model_used or '').removesuffix(':latest') != 'embeddinggemma'):
            raise RuntimeError('Replacement model provenance is incompatible; no changes made')
        fresh = vectors[0]
        if historical:
            if is_historical(models.Record(id=point.id, vector=fresh, payload=payload)):
                raise RuntimeError('Synthetic replacement refused; no changes made')
            report.replacements_validated += 1
        else:
            stored = point.vector
            if not isinstance(stored, list) or not valid_vector(stored):
                report.reject('invalid_existing_vector')
                continue
            cosine = sum(a*b for a,b in zip(stored,fresh)) / math.sqrt(
                sum(a*a for a in stored)*sum(b*b for b in fresh))
            if cosine < SEMANTIC_COSINE_MIN:
                report.reject('unverified_embedding_space')
                continue
            report.unclassified -= 1
            report.semantic += 1
            report.attestations_validated += 1
        plan.append(PlannedUpdate(point, fresh, historical))
    if not apply:
        return report
    # Verify the collection snapshot before writing: operators must stop concurrent writers.
    current = {str(point.id): point for point in read_points(client, collection)}
    if len(current) != len(points) or any(current.get(str(point.id)) != point for point in points):
        raise RuntimeError('Collection changed during validation; no changes made')
    for update in plan:
        point = update.point
        if update.historical:
            client.upsert(collection, points=[models.PointStruct(id=point.id, vector=update.vector,
                payload={**(point.payload or {}), **provenance()})], wait=True)
            report.applied += 1
        else:
            # Positive fresh-model comparison attests existing real vectors without replacing them.
            client.set_payload(collection, payload=provenance(), points=[point.id], wait=True)
            report.attested += 1
        saved = client.retrieve(collection, ids=[point.id], with_vectors=True, with_payload=True)
        if len(saved) != 1 or not semantic_metadata(saved[0].payload or {}) or is_historical(saved[0]):
            raise RuntimeError('Replacement verification failed; stop and inspect counts')
        original = point.payload or {}
        if any(saved[0].payload.get(key) != value for key, value in original.items() if key not in provenance()):
            raise RuntimeError('Canonical provenance changed unexpectedly')
    if client.count(collection, exact=True).count != len(points):
        raise RuntimeError('Unexpected collection point count')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--email', help='Operator account; password is prompted securely')
    args = parser.parse_args()
    if settings.embedding_provider != 'ollama' or settings.embedding_model.removesuffix(':latest') != 'embeddinggemma':
        parser.error('Real configured embeddinggemma is required')
    runtime = get_supabase_runtime()
    token = os.getenv('VISUALAI_REINDEX_ACCESS_TOKEN')
    acquired_token = False
    try:
        if args.email:
            session = runtime.login(args.email, getpass.getpass('Supabase password: '))
            token = str(session['access_token'])
            acquired_token = True
        if token:
            runtime.verify_user(token)
        canonical, sources = load_canonical(runtime, token)
        report = reindex(vector_store.get_client(), settings.collection_name, canonical, sources, apply=args.apply)
        from dataclasses import asdict
        print(json.dumps({'mode': 'apply' if args.apply else 'dry_run', **asdict(report)}))
    except Exception as error:
        # Deliberately omit upstream error bodies, credentials and source material.
        print(json.dumps({'status': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1) from None
    finally:
        vector_store.close_client()
        if acquired_token and token:
            runtime.logout(token)
        runtime.close()


if __name__ == '__main__':
    main()
