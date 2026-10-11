# Local embedding configuration

Production uses `EMBEDDING_PROVIDER=ollama` and `EMBEDDING_MODEL=embeddinggemma`.
The legacy `OLLAMA_EMBED_MODEL` alias takes precedence when supplied; all application
callers resolve to the same effective model. Keep the alias absent or identical.
Reasoning remains `llama3.2:3b`; selecting a reasoning model does not change embeddings.

`EMBEDDING_FALLBACK_MODEL=embeddinggemma` is the explicit fallback. An empty value
disables fallback. Supported fallback families are `embeddinggemma` and
`nomic-embed-text`, subject to actual vector validation. Only a model-not-found 404
permits fallback. Service failures, malformed responses, invalid dimensions and
zero vectors fail closed. One safe warning identifies the configured and fallback
models. Model names, provider, dimension and fallback status appear in source-job
embedding diagnostics; prompts and credentials do not.

Ollama `/api/embed` accepts arrays of input texts. Requests use `truncate=false`
to reject oversized inputs rather than silently dropping evidence. Returned
vectors must be finite, nonzero and 768-dimensional. Existing Qdrant collection
dimensions are checked before an upsert. Existing collections are never deleted
or rebuilt to resolve a mismatch.

`EMBEDDING_PROVIDER=mock` is an explicit automated-test setting for isolated test
storage. Production never falls back to hash, random or zero vectors. The direct
hash helper also rejects calls outside that explicit test configuration.

Safe source-job reason codes distinguish `MODEL_TIMEOUT`, `MODEL_UNAVAILABLE`,
`INVALID_MODEL_OUTPUT`, `NO_GROUNDED_CONCEPTS`, `EMBEDDING_MODEL_UNAVAILABLE`,
`EMBEDDING_FAILED`, and `VECTOR_INDEX_FAILED`. Existing stage-level codes remain
compatible. Failed indexing keeps the canonical source and its chunks available
for an explicit retry.

Matching dimensions do not prove matching embedding spaces. Previously stored
synthetic vectors or vectors produced by another model need an explicitly planned
reindex before semantic retrieval can be trusted. Configuration cleanup does not
silently rewrite historical vectors.

The active production namespace for embeddinggemma is `visualai_embeddinggemma_v2`.
For this model, the generic legacy `COLLECTION_NAME` values `visualai_layer_a` and
`visualai_layer_a_v1` resolve to that new namespace; their existing points remain
untouched. Explicit custom collection names remain unchanged. The optional
`SEMANTIC_COLLECTION_NAME` overrides this selection. Runtime diagnostics show both
the requested and active names. Existing collections must use unnamed
768-dimensional Cosine vectors; incompatible collections are rejected.

New points include provider, actual model tag, dimension, semantic kind, embedding
version, collection name, collection version `2`, and preprocessing identity.
Queries require this complete provenance. Canonical evidence retrieval additionally
checks owned source versions and rehydrates supporting content from Supabase.
Unknown-provenance legacy points are excluded. Changing model weights or
preprocessing requires a separately validated namespace and controlled reindex.

To prepare an existing source, use **My sources → Prepare source search**. This
calls the existing authenticated `POST /sources/{source_id}/retry-index?version=N`
route and refreshes even a READY source. A stale version returns HTTP 409. A failed
refresh preserves canonical READY content; it does not prove that vectors in the
active collection are available. No automatic bulk migration is performed.

See [the repair evidence and rollback report](qdrant-embedding-repair.md).

API contract: [Ollama embedding documentation](https://docs.ollama.com/api/embed).
