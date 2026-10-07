# Phase 6A.3: canonical knowledge access

## Files changed

- `app/api/knowledge.py` (new)
- `app/services/knowledge_models.py` (new)
- `app/services/knowledge_service.py` (new)
- `app/services/repositories/knowledge_repository.py` (new)
- `app/core/supabase.py`
- `app/main.py`
- `app/services/registry.py`
- `app/services/repositories/factory.py`
- `app/services/repositories/source_repository.py`
- `tests/test_knowledge_repository.py` (new)
- `docs/phase6a3_knowledge_repository.md` (new)

## Verified foundation

Workspace: `C:\Users\ANVESH\Desktop\AI-VIDEO-GENERATOR`, branch
`stabilization-python312`. The initial working tree was clean.

Supabase project `hqszkkvuxwdedhegqbec` contains exactly one deployed
`20261007062312 canonical_knowledge_snapshot` migration. The unchanged local
`migrations/20261007055251_canonical_knowledge_snapshot.sql` has SHA256
`15f6871070288d1d0fc180cd7aa433a58985f88d60a4f2330810ed125f6b2e21`.
The MCP catalog check confirms RLS is enabled on `topics`, `subtopics`,
`concepts`, `content_concepts`, and `concept_relationships`.

No migration, hosted data, Auth setting, or Qdrant change was made in this phase.
Normal test-account logins refresh Auth sessions as part of live acceptance.

## Architecture and typed contracts

`get_knowledge_repository` creates a request-scoped `KnowledgeRepository` only
in Supabase mode. It verifies the Bearer token with the existing GoTrue `/user`
boundary before using its UUID. If an internal caller supplies an identity,
the constructor checks it against that verified UUID. No request ownership
field, local JSON, vector payload, or admin key establishes identity.

All reads use frozen, strict, extra-forbidden `SourceScope` contracts with an
exact positive integer version. There is no latest-version lookup. Returned
records are checked against the verified UUID, source, and version, including
the nested evidence content record. Record IDs are validated before composing
PostgREST filters. A factory import is deferred to avoid DTO/repository import
cycles; standalone-import tests cover the new layers.

Domain DTOs cover topics, subtopics, concepts, relationships, evidence,
readiness, hierarchical maps, and internal snapshot requests/results. Schema
version is a strict integer constrained to 1; booleans, strings, and floats are
rejected. Snapshot arrays follow the deployed RPC's cardinality limits.

`ScopedContentUnit` preserves the verified UUID, source, integer version,
content ID, original provenance, and the existing `ContentUnit`. Its round-trip
test verifies this information survives decoding without changing ContentUnit
semantics. Full-content reads are internal and are not used by the map API.

## Service responsibilities

`KnowledgeService` validates the complete READY hierarchy before projection:
unique IDs and sibling sequence values, topic/subtopic/concept membership,
matching concept content references and actual evidence associations, valid
directed edges, prerequisite evidence, and an acyclic prerequisite graph.

Topics, subtopics within their topic, and concepts within their subtopic are
ordered by sequence and ID. Evidence and relationship IDs are deterministic.
A prerequisite edge `A -> B` means A depends on B; it is never reversed. Related
edges retain their stored direction. Selecting a subtopic under another topic
fails at the same safe not-found boundary.

The service does not generate knowledge, call an LLM, query Qdrant, or mutate
assessment, mastery, learning sessions, or videos.

## Read-only API

`GET /sources/{source_id}/versions/{version}/knowledge`

Requires a normally verified Bearer token. The typed `KnowledgeMap` returns:
owner UUID, source ID, integer version, knowledge state, schema version,
ordered topics/subtopics/concepts, evidence summaries, and prerequisite/related
concept IDs. Evidence includes exact scope, content ID, support kind, offsets,
confidence, pages/slides/timestamps, heading path, chapter, section, sequence,
and extraction method. Original arbitrary provenance JSON is retained internally;
it is omitted from the public response to avoid exposing unreviewed strings.

The response does not include ContentUnit text, image paths, embeddings,
vectors, tokens, prompts, RPC metadata, operation hashes, or database privilege
details. Success and application error responses have private, no-store caching;
they vary by Authorization. Query parameters are rejected, including forged
`user_id`/`student_id` or alternate source/version selectors.

| HTTP | Meaning |
| --- | --- |
| 200 | Exact owned scope with explicit readiness state |
| 401 | Missing or invalid verified Bearer identity |
| 404 | Missing or foreign source/version, identical safe response |
| 409 | Canonical endpoint unsupported in explicit file/local mode |
| 422 | Invalid source/version or unsupported query selector |
| 413 | Bounded result size exceeded |
| 502 | Malformed/inconsistent provider response |
| 503 | Unknown/unavailable provider, upstream rate limit/server outage |

The sole new operation ID is `read_canonical_source_version_knowledge`.
`app.openapi()` and live `/openapi.json` succeed with a typed response and
documented errors. No public snapshot/graph mutation route was added.

## Readiness

| State | Result |
| --- | --- |
| LEGACY_UNMAPPED | Explicit state and empty hierarchy |
| PENDING | Explicit processing state and empty hierarchy |
| FAILED | Empty hierarchy and constant `KNOWLEDGE_BUILD_FAILED` diagnostic |
| READY | Validated canonical hierarchy and schema version 1 |

Source ingestion/index status is not used as a substitute for knowledge
readiness. Non-READY states never invent topics. Provider failures never become
empty successful maps. Service selection/projection helpers report NOT_READY
when the exact owned version has not completed canonical mapping.

## Query strategy and bounds

An exact `source_versions` query establishes visibility/readiness and checks
the integer-to-`vN` label. A READY map uses five additional set queries:
topics, subtopics, concepts, evidence associations with a scoped content metadata
embed, and relationships. The existing composite foreign key supports the
PostgREST content join; no new SQL object is necessary.

There is no per-topic/concept query loop. Small READY maps require **6 database
calls plus 1 Auth verification**, excluding login and separately requested
content envelopes. Non-READY maps require 1 database call plus 1 Auth check.
Each table is fetched in deterministic 500-row pages with a 10,000-row safety
bound; larger maps add page calls, rather than N+1 calls per concept. The row
bound exceeds the deployed maximum of 8,192 evidence associations. The response
and internal snapshot body are limited to 2 MiB, matching the RPC payload cap.

The accepted live map is **1,276 bytes**, containing one topic, one subtopic,
one concept, one evidence association, and no relationships. Real database
tests also cover a multi-topic, multi-subtopic graph with evidence and a directed
prerequisite, including shuffled input and sibling concept ordering.

## Internal snapshot adapter

The typed repository/service adapter calls only the existing
`visualai_commit_knowledge_snapshot` RPC using the verified caller's JWT,
exact scope, operation UUID, and `KnowledgeSnapshot`. It does not submit an
owner field or calculate an authoritative hash. The server result must match
the requested source/version/operation and contains the server hash/timestamp.

The shared transport now preserves HTTP 409 as a safe `SupabaseConflict`;
the adapter surfaces CONFLICT separately from provider errors. Actual disposable
PostgreSQL tests verify identical retries return the same receipt, changed
operation IDs are rejected, and foreign scopes cannot be committed. The adapter
is never called automatically and no live snapshot commit was issued here.

## Legacy compatibility audit

The structurer produces transient graph and TopicBlueprint artifacts during
the existing Phase 5B ingestion pipeline. It does not read canonical knowledge
or local graph files. It remains unchanged; generation is outside this phase.

In Supabase mode, source-repository graph reads require an explicit integer
version and use the canonical service projection. Source-repository graph
writes are rejected. Direct registry graph loads fail closed before accessing
runtime, fixture, or historical JSON. Explicit file/local mode retains its
existing registry behavior.

The unchanged Phase 5B pipeline still saves a local ingestion diagnostic graph
artifact and retains its existing artifact failure handling. That artifact is
not a second canonical graph: Supabase knowledge consumers cannot load it,
and it cannot be promoted to READY canonical knowledge through registry writes.
Its retirement belongs to a separately scoped ingestion change.

KnowledgeGraph projection preserves canonical IDs and directed relationships.
Legacy DTO normalization that would rename IDs or cause collisions fails
explicitly rather than silently changing canonical identity. TopicBlueprint
projection was not introduced because no enabled canonical consumer needs it
and its generated difficulty fields cannot be inferred by this read layer.
Phase 6A.1 legacy API guards remain installed.

## Observability

Read logs include a generated request ID, source/version, state, counts, database
call count, and safe provider outcome. Internal commit logs include operation
UUID, exact source/version, counts, and outcome. Passwords, JWTs, arbitrary
provenance, upstream error bodies, and complete documents are never logged.

## Acceptance and regressions

Three verification layers are distinguished:

1. HTTP transport doubles exercise GoTrue response validation and error handling;
   SQL-backed bridge tests run the actual migrations, grants, RLS, constraints,
   hash calculation, and RPC idempotency in disposable PostgreSQL 17.11. These
   tests do not connect to the hosted project or mock away tenant isolation.
   A deliberately unfiltered foreign query confirms RLS independently of the
   repository's owner filter. Strict DTO and standalone import tests need no DB.
2. The pre-hardening targeted run passed 270 tests. The expanded canonical
   repository/service run passed 47 tests. The final complete suite result is
   recorded below. Frontend Auth tests passed 14/14 with Node's test runner.
3. Live acceptance used the two existing dedicated identities through normal
   Supabase login/JWT verification and real Data API reads. Before process
   restart, the new ASGI route passed owner/foreign/anonymous checks. After
   restarting the VisualAI server, real HTTP calls repeated the same checks.

Live owner reads returned the accepted READY hierarchy and exact evidence
scope. Foreign topic/subtopic/concept selectors and the knowledge route were
unavailable; foreign and missing API responses matched. Forged owner queries
were rejected. The serialized map matched across restart. Digests of all owner
source/version/content/knowledge rows were unchanged before and after reads;
the accepted operation ID, hash, and timestamp still match the Phase 6A.2D
receipt. No additional snapshot was created. Migration history and local
migration SHA remained unchanged. Qdrant was neither queried nor modified by
the knowledge layer/acceptance.

Final full suite: **802 passed, 1 existing skip, 4 existing warning emissions**
in 120.47 seconds. This includes the 47 new access-layer tests, 95 Phase 6A.1
security tests, and 75 actual PostgreSQL Phase 6A.2 database tests, plus source,
Auth, runtime, and remaining regressions. Frontend Auth: **14 passed**.
`git diff --check`: **PASS**.

## Remaining risks and Phase 6B requirements

No canonical integration blocker remains. Existing baseline warnings remain:
the dashboard's duplicate GET/HEAD OpenAPI operation ID, unregistered `e2e`
pytest marker, and Python 3.12 `audioop` deprecation. The existing optional live
model-dependent E2E test is not enabled by this phase.

Maximum-size maps can duplicate evidence metadata; the response cap is enforced
after bounded reads. Public cursor pagination/lazy evidence loading should be
designed before interactive consumers require larger maps. Arbitrary provenance
can also enlarge internal provider responses; the public map intentionally
omits it. Offset paging is stable for immutable READY snapshots.

Legacy graph IDs containing characters its historical normalizer cannot
represent should be consumed through canonical DTOs; do not change canonical
IDs merely to satisfy a compatibility DTO. Phase 6B must generate/validate
knowledge separately, supply a stable operation UUID, invoke the typed adapter
deliberately, and preserve atomic immutable READY commits. It must use these
exact-scope canonical reads rather than resurrecting file graph fallback or
using Qdrant as the domain database. Supabase remains canonical; Qdrant remains
the derived semantic retrieval index.
